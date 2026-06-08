"""
Live real-time PvP over WebSockets.

Two players are matched from a waiting queue and draft on a synchronized,
timed clock. Each round both players get their own random decade x team prompt
(blind to the opponent); they pick a player into an open eligible slot before
the deadline (auto-picked otherwise). After five rounds both lineups are scored
head-to-head and BOTH records update. Disconnect = the other player wins.

State is in-memory (single process). This is intentionally simple; a multi-
process deployment would need a shared broker.
"""
from __future__ import annotations

import asyncio
import time

from . import db, game
from .models import player_from_dict
from .scoring import score_player, roll_status
from .positions import SLOTS
from . import rating

ROUND_SECONDS = 10
INTRO_SECONDS = 3.6      # brief pause after match-up so the intro animation plays
AI_WAIT_SECONDS = 60     # how long to wait for a human before falling back to AI
NUM_ROUNDS = len(SLOTS)
_INVERSE = {"win": "loss", "loss": "win", "tie": "tie"}


def _ai_record() -> dict:
    """The fabricated record for the AI fallback opponent (never persisted)."""
    return {
        "username": "Guest", "display_name": "Guest",
        "wins": 0, "losses": 0, "rating": 1000, "peak_rating": 1000,
        "tier": "Amateur", "next_tier": "Pro", "next_tier_at": 1500,
        "avatar": "amateur", "unlocked": ["amateur"], "achievements": [],
    }


class PlayerLeft(Exception):
    def __init__(self, player):
        self.player = player


class Player:
    def __init__(self, ws, username: str, is_ai: bool = False):
        self.ws = ws
        self.username = username
        self.is_ai = is_ai
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.done = asyncio.Event()
        self.reader: asyncio.Task | None = None
        self.open_slots: list[str] = []
        self.picks: list[dict] = []
        self.step: dict | None = None

    def picked_names(self) -> set[str]:
        return {p["player"]["name"] for p in self.picks}

    def lineup(self):
        return [player_from_dict(p["player"]) for p in self.picks]

    def record(self) -> dict:
        return _ai_record() if self.is_ai else db.get_record(self.username)

    async def send(self, msg: dict) -> None:
        if self.is_ai:
            return
        try:
            await self.ws.send_json(msg)
        except Exception:
            pass


class LiveGame:
    def __init__(self, a: Player, b: Player):
        self.a, self.b = a, b
        import random
        self.rng = random.Random()

    async def run(self) -> None:
        for p in (self.a, self.b):
            p.open_slots = list(SLOTS)
            p.picks = []
            p.step = game._build_step(self.rng, p.open_slots, set(), 0)
        a_rec = self.a.record()
        b_rec = self.b.record()
        await self.a.send({"type": "matched", "opponent": self.b.username,
                           "opponent_record": b_rec, "total_slots": NUM_ROUNDS})
        await self.b.send({"type": "matched", "opponent": self.a.username,
                           "opponent_record": a_rec, "total_slots": NUM_ROUNDS})

        # Let the match-up intro animation play before the first timed round.
        await asyncio.sleep(INTRO_SECONDS)

        try:
            for rnd in range(1, NUM_ROUNDS + 1):
                deadline = time.time() + ROUND_SECONDS
                for p in (self.a, self.b):
                    await p.send({"type": "round", "round": rnd, "deadline": deadline,
                                  "current_step": p.step, "picks_made": len(p.picks),
                                  **self._budget(p)})
                await asyncio.gather(self._collect(self.a, deadline, rnd),
                                     self._collect(self.b, deadline, rnd))
                if rnd < NUM_ROUNDS:
                    for p in (self.a, self.b):
                        p.step = game._build_step(self.rng, p.open_slots,
                                                  p.picked_names(), game._spent(p.picks))
        except PlayerLeft as left:
            await self._handle_left(left.player)
            return

        await self._finish()

    # ---- per-player round collection ----
    def _budget(self, p: Player) -> dict:
        s = game._spent(p.picks)
        return {"budget": rating.CAP_BUDGET, "spent": s,
                "remaining": rating.CAP_BUDGET - s}

    async def _send_autopick(self, p: Player, other: Player) -> None:
        self._autopick(p)
        ap = p.picks[-1] if p.picks else None
        await p.send({"type": "auto_picked", "filled": self._filled(p),
                      "player": ap["player"]["name"] if ap else None,
                      "slot": ap["slot"] if ap else None, **self._budget(p)})
        await other.send({"type": "opponent_progress", "picks_made": len(p.picks)})

    async def _collect(self, p: Player, deadline: float, rnd: int) -> None:
        other = self.b if p is self.a else self.a
        if p.is_ai:
            # AI "thinks" briefly (under the clock), then drafts its best option.
            think = min(self.rng.uniform(1.0, 3.0), max(0.0, deadline - time.time() - 0.2))
            if think > 0:
                await asyncio.sleep(think)
            self._ai_best_pick(p)
            await other.send({"type": "opponent_progress", "picks_made": len(p.picks)})
            return
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                await self._send_autopick(p, other)
                return
            try:
                msg = await asyncio.wait_for(p.inbox.get(), timeout=remaining)
            except asyncio.TimeoutError:
                await self._send_autopick(p, other)
                return
            if msg.get("type") == "_disconnect":
                raise PlayerLeft(p)
            if msg.get("type") == "pick":
                # Ignore picks for a stale round (e.g. a click that lands just
                # after the timer auto-picked and advanced the round).
                if msg.get("round") is not None and msg.get("round") != rnd:
                    continue
                ok, err = self._apply(p, msg.get("player_name"), msg.get("slot"))
                if ok:
                    await p.send({"type": "picked_ok", "filled": self._filled(p),
                                  "picks_made": len(p.picks), **self._budget(p)})
                    await other.send({"type": "opponent_progress", "picks_made": len(p.picks)})
                    return
                await p.send({"type": "error", "detail": err})

    def _apply(self, p: Player, name, slot):
        if not p.step:
            return False, "no active step"
        cand = next((c for c in p.step["candidates"] if c["name"] == name), None)
        if cand is None:
            return False, f"'{name}' is not in the current pool"
        if name in p.picked_names():
            return False, f"'{name}' already drafted"
        if slot not in p.open_slots:
            return False, f"slot {slot} is not open"
        if slot not in cand.get("eligible_positions", []):
            return False, f"'{name}' cannot play {slot}"
        if not cand.get("eligible") or slot not in cand.get("eligible_slots", []):
            return False, f"'{name}' is over budget for {slot}"
        player = {k: v for k, v in cand.items()
                  if k not in ("eligible", "eligible_slots", "affordable",
                               "taken", "forced")}
        player["position"] = slot
        p.picks.append({"slot": slot, "player": player})
        p.open_slots = [s for s in p.open_slots if s != slot]
        return True, ""

    def _autopick(self, p: Player) -> None:
        for c in p.step["candidates"]:
            if c.get("eligible") and c.get("eligible_slots"):
                self._apply(p, c["name"], c["eligible_slots"][0])
                return

    def _ai_best_pick(self, p: Player) -> None:
        """Draft the highest-rated eligible candidate into its first open slot."""
        best = None
        best_score = -1.0
        for c in p.step["candidates"]:
            if not (c.get("eligible") and c.get("eligible_slots")):
                continue
            if c["name"] in p.picked_names():
                continue
            try:
                score = score_player(player_from_dict(c)).total
            except Exception:
                score = 0.0
            if score > best_score:
                best_score, best = score, c
        if best is not None:
            self._apply(p, best["name"], best["eligible_slots"][0])
        else:
            self._autopick(p)

    def _filled(self, p: Player) -> list[dict]:
        return [{"slot": pk["slot"], "name": pk["player"]["name"]} for pk in p.picks]

    # ---- end states ----
    async def _finish(self) -> None:
        a_rec = self.a.record()
        b_rec = self.b.record()
        a_old = a_rec["rating"]
        b_old = b_rec["rating"]
        a_disp = db.name_label(a_rec)
        b_disp = db.name_label(b_rec)
        # Roll Hot/Slump ONCE per lineup and reuse for both players' scorings, so
        # both views agree on who's hot/cold (and the same boost/penalty applies).
        a_status = roll_status(self.a.lineup(), self.rng)
        b_status = roll_status(self.b.lineup(), self.rng)
        a_out, pa = game.score_lineups(self.a.lineup(), self.b.lineup(), f"{b_disp}'s squad",
                                       home_status=a_status, away_status=b_status)
        _, pb = game.score_lineups(self.b.lineup(), self.a.lineup(), f"{a_disp}'s squad",
                                   home_status=b_status, away_status=a_status)
        b_out = _INVERSE[a_out]
        self._settle(self.a, pa, a_out, a_old)
        self._settle(self.b, pb, b_out, b_old)
        pa["mode"] = pb["mode"] = "live"
        # Await the sends so results arrive before the sockets close.
        await self.a.send({"type": "result", "result": pa})
        await self.b.send({"type": "result", "result": pb})
        self.a.done.set()
        self.b.done.set()

    def _settle(self, p: Player, payload: dict, outcome: str, old_rating: int) -> None:
        """Apply a finished result for one player. The AI ('Guest') is cosmetic
        only -- its record/rating/achievements are never persisted."""
        prev_tier = rating.tier_name(old_rating)
        if p.is_ai:
            payload["record"] = _ai_record()
            payload["ranked"] = True
            payload["rating_change"] = 0
            payload["previous_tier"] = prev_tier
            payload["promoted"] = False
            return
        db.apply_result(p.username, outcome)
        _, newly = db.award_achievements(p.username, outcome == "win", payload["your_team"]["players"])
        db.record_best_team(p.username, payload["your_team"]["players"])
        rec = db.get_record(p.username)
        payload["record"] = rec
        payload["newly_unlocked"] = newly
        payload["ranked"] = True
        payload["rating_change"] = rec["rating"] - old_rating
        payload["previous_tier"] = prev_tier
        payload["promoted"] = payload["rating_change"] > 0 and rec["tier"] != prev_tier
        payload["win_streak"] = rec["win_streak"]
        payload["streak_bonus"] = rating.streak_bonus(rec["win_streak"]) if outcome == "win" else 0

    async def _handle_left(self, left: Player) -> None:
        other = self.b if left is self.a else self.a
        rec = other.record() if other.is_ai else db.apply_result(other.username, "win")
        await other.send({"type": "opponent_left", "record": rec})
        self.a.done.set()
        self.b.done.set()


class LiveManager:
    def __init__(self):
        self.waiting: Player | None = None
        self.lock = asyncio.Lock()

    async def _reader(self, p: Player) -> None:
        try:
            while True:
                msg = await p.ws.receive_json()
                await p.inbox.put(msg)
        except Exception:
            await p.inbox.put({"type": "_disconnect"})
            async with self.lock:
                if self.waiting is p:
                    self.waiting = None
                    p.done.set()

    async def handle(self, ws, username: str) -> None:
        p = Player(ws, username)
        p.reader = asyncio.create_task(self._reader(p))
        async with self.lock:
            if self.waiting is None:
                self.waiting = p
                waiter = True
            else:
                other, self.waiting, waiter = self.waiting, None, False
        try:
            if waiter:
                await p.send({"type": "waiting"})
                # Wait for a human; after AI_WAIT_SECONDS, fall back to the AI.
                try:
                    await asyncio.wait_for(p.done.wait(), timeout=AI_WAIT_SECONDS)
                except asyncio.TimeoutError:
                    async with self.lock:
                        start_ai = self.waiting is p
                        if start_ai:
                            self.waiting = None
                    if start_ai:
                        ai = Player(None, "Guest", is_ai=True)
                        await LiveGame(p, ai).run()
                    else:
                        # A human matched us right at the deadline; their game
                        # is already running -- just wait for it to finish.
                        await p.done.wait()
            else:
                await LiveGame(other, p).run()
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            if p.reader:
                p.reader.cancel()


manager = LiveManager()
