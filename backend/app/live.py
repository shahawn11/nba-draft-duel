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
from .positions import SLOTS
from . import rating

ROUND_SECONDS = 10
NUM_ROUNDS = len(SLOTS)
_INVERSE = {"win": "loss", "loss": "win", "tie": "tie"}


class PlayerLeft(Exception):
    def __init__(self, player):
        self.player = player


class Player:
    def __init__(self, ws, username: str):
        self.ws = ws
        self.username = username
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

    async def send(self, msg: dict) -> None:
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
            p.step = game._build_step(self.rng, p.open_slots, set())
        a_rec = db.get_record(self.a.username)
        b_rec = db.get_record(self.b.username)
        await self.a.send({"type": "matched", "opponent": self.b.username,
                           "opponent_record": b_rec, "total_slots": NUM_ROUNDS})
        await self.b.send({"type": "matched", "opponent": self.a.username,
                           "opponent_record": a_rec, "total_slots": NUM_ROUNDS})

        try:
            for rnd in range(1, NUM_ROUNDS + 1):
                deadline = time.time() + ROUND_SECONDS
                for p in (self.a, self.b):
                    await p.send({"type": "round", "round": rnd, "deadline": deadline,
                                  "current_step": p.step, "picks_made": len(p.picks)})
                await asyncio.gather(self._collect(self.a, deadline, rnd),
                                     self._collect(self.b, deadline, rnd))
                if rnd < NUM_ROUNDS:
                    for p in (self.a, self.b):
                        p.step = game._build_step(self.rng, p.open_slots, p.picked_names())
        except PlayerLeft as left:
            await self._handle_left(left.player)
            return

        await self._finish()

    # ---- per-player round collection ----
    async def _send_autopick(self, p: Player, other: Player) -> None:
        self._autopick(p)
        ap = p.picks[-1] if p.picks else None
        await p.send({"type": "auto_picked", "filled": self._filled(p),
                      "player": ap["player"]["name"] if ap else None,
                      "slot": ap["slot"] if ap else None})
        await other.send({"type": "opponent_progress", "picks_made": len(p.picks)})

    async def _collect(self, p: Player, deadline: float, rnd: int) -> None:
        other = self.b if p is self.a else self.a
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
                                  "picks_made": len(p.picks)})
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
        player = {k: v for k, v in cand.items() if k not in ("eligible", "eligible_slots")}
        player["position"] = slot
        p.picks.append({"slot": slot, "player": player})
        p.open_slots = [s for s in p.open_slots if s != slot]
        return True, ""

    def _autopick(self, p: Player) -> None:
        for c in p.step["candidates"]:
            if c.get("eligible") and c.get("eligible_slots"):
                self._apply(p, c["name"], c["eligible_slots"][0])
                return

    def _filled(self, p: Player) -> list[dict]:
        return [{"slot": pk["slot"], "name": pk["player"]["name"]} for pk in p.picks]

    # ---- end states ----
    async def _finish(self) -> None:
        a_old = db.get_record(self.a.username)["rating"]
        b_old = db.get_record(self.b.username)["rating"]
        a_out, pa = game.score_lineups(self.a.lineup(), self.b.lineup(), f"{self.b.username}'s squad")
        _, pb = game.score_lineups(self.b.lineup(), self.a.lineup(), f"{self.a.username}'s squad")
        b_out = _INVERSE[a_out]
        pa["record"] = db.apply_result(self.a.username, a_out)
        pb["record"] = db.apply_result(self.b.username, b_out)
        pa["ranked"] = pb["ranked"] = True
        pa["rating_change"] = pa["record"]["rating"] - a_old
        pb["rating_change"] = pb["record"]["rating"] - b_old
        a_prev, b_prev = rating.tier_name(a_old), rating.tier_name(b_old)
        pa["previous_tier"] = a_prev
        pb["previous_tier"] = b_prev
        pa["promoted"] = pa["rating_change"] > 0 and pa["record"]["tier"] != a_prev
        pb["promoted"] = pb["rating_change"] > 0 and pb["record"]["tier"] != b_prev
        pa["mode"] = pb["mode"] = "live"
        # Await the sends so results arrive before the sockets close.
        await self.a.send({"type": "result", "result": pa})
        await self.b.send({"type": "result", "result": pb})
        self.a.done.set()
        self.b.done.set()

    async def _handle_left(self, left: Player) -> None:
        other = self.b if left is self.a else self.a
        rec = db.apply_result(other.username, "win")
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
