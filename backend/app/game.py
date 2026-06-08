"""
Game logic: 82-0-style sequential blind draft with free slot choice.

You fill five slots (PG/SG/SF/PF/C). Each step reveals a fresh random
decade x team and that franchise's top-10 players (decade-averaged stats). You
pick ANY player and assign them to ANY still-open slot they're eligible for;
players with no eligible open slot are shown but not selectable. The opponent
and future steps stay hidden until the draft resolves.
"""
from __future__ import annotations

import random
import uuid

from . import db, dataset, teams, rating
from .models import player_from_dict, player_to_dict
from .positions import SLOTS
from .scoring import duel, roll_status, score_player, HOT_STAT_MULT, SLUMP_STAT_MULT


def _picked_names(state: dict) -> set[str]:
    return {p["player"]["name"] for p in state["picks"]}


def _spent(picks: list[dict]) -> int:
    """Total salary-cap cost of the players drafted so far."""
    return sum(int(p["player"].get("cost", 0)) for p in picks)


def _player_rating(p) -> float:
    """A player's intrinsic 0-100 rating (drives their cap tier/cost)."""
    try:
        return score_player(p).total
    except Exception:
        return 0.0


def _annotate(p, open_slots: list[str], picked: set[str], spent: int) -> dict:
    """Build a candidate dict with cap tier/cost + selectability. A candidate is
    selectable only if it isn't already drafted, can fill an open slot, AND is
    affordable under the remaining budget (pick-time feasibility guard)."""
    d = player_to_dict(p)
    eligible_positions = d["eligible_positions"]
    available = p.name not in picked
    elig_open = [s for s in open_slots if s in eligible_positions]

    r = _player_rating(p)
    tier = rating.player_tier(r)
    cost = tier["cost"]
    affordable = rating.is_affordable(spent, cost, len(open_slots))

    d["rating_value"] = round(r, 1)
    d["tier"] = tier["id"]
    d["cost"] = cost
    d["affordable"] = affordable
    d["taken"] = not available
    selectable = available and affordable and bool(elig_open)
    d["eligible_slots"] = elig_open if selectable else []
    d["eligible"] = selectable
    return d


def _build_step(rng: random.Random, open_slots: list[str], picked: set[str],
                spent: int = 0) -> dict:
    """Pick a random (decade, team) with >=1 selectable player for an open slot."""
    pool = dataset.historical_pool()
    keys = list(pool.keys())
    rng.shuffle(keys)

    def selectable(players) -> bool:
        return any(
            p.name not in picked and any(s in p.eligible() for s in open_slots)
            for p in players
        )

    chosen = next((k for k in keys if selectable(pool[k])), None)
    if chosen is None:
        chosen = rng.choice(keys)

    decade, team = chosen.split("|", 1)
    candidates = [_annotate(p, open_slots, picked, spent) for p in pool[chosen]]

    # Feasibility fallback: if the random pool offers no AFFORDABLE+eligible
    # option for an open slot, force the cheapest position-eligible candidate
    # selectable so the draft can never soft-lock. (Rare; never lets a planner
    # stack stars — it only fires when no cheap option was offered.)
    if not any(c["eligible"] for c in candidates):
        forced = [c for c in candidates
                  if not c["taken"]
                  and any(s in c["eligible_positions"] for s in open_slots)]
        if forced:
            cheapest = min(forced, key=lambda c: c["cost"])
            cheapest["affordable"] = True
            cheapest["forced"] = True
            cheapest["eligible_slots"] = [s for s in open_slots
                                          if s in cheapest["eligible_positions"]]
            cheapest["eligible"] = True

    return {"decade": decade, "team": teams.era_team_name(team, decade),
            "budget": rating.CAP_BUDGET, "spent": spent,
            "remaining": rating.CAP_BUDGET - spent, "candidates": candidates}


def _public_view(match: dict, state: dict) -> dict:
    spent = _spent(state["picks"])
    return {
        "match_id": match["id"],
        "username": match["username"],
        "mode": match["mode"],
        "status": match["status"],
        "total_slots": len(SLOTS),
        "picks_made": len(state["picks"]),
        "open_slots": state["open_slots"],
        "budget": rating.CAP_BUDGET,
        "spent": spent,
        "remaining": rating.CAP_BUDGET - spent,
        "filled": [
            {"slot": p["slot"], "name": p["player"]["name"],
             "cost": p["player"].get("cost"), "tier": p["player"].get("tier")}
            for p in state["picks"]
        ],
        "current_step": state.get("current"),
    }


def new_match(username: str, seed: int | None = None) -> dict:
    rng = random.Random(seed)
    db.ensure_user(username)

    opp_team, opponent = dataset.random_current_opponent(rng)
    open_slots = list(SLOTS)
    state = {
        "open_slots": open_slots,
        "picks": [],
        "current": _build_step(rng, open_slots, set()),
    }

    match_id = uuid.uuid4().hex[:12]
    db.create_match(
        match_id=match_id,
        username=username,
        opponent_team=opp_team,
        opponent_json=[player_to_dict(p) for p in opponent],
        state_json=state,
    )
    match = {"id": match_id, "username": username, "mode": "offline", "status": "open"}
    return _public_view(match, state)


class DraftError(ValueError):
    pass


def pick(match_id: str, player_name: str, slot: str) -> dict:
    match = db.get_match(match_id)
    if not match:
        raise DraftError("match not found")
    if match["status"] == "resolved":
        raise DraftError("match already resolved")

    state = match["state_json"]
    current = state["current"]

    cand = next((c for c in current["candidates"] if c["name"] == player_name), None)
    if cand is None:
        raise DraftError(f"'{player_name}' is not in the current pool")
    if player_name in _picked_names(state):
        raise DraftError(f"'{player_name}' is already drafted")
    if slot not in state["open_slots"]:
        raise DraftError(f"slot {slot} is not open")
    if slot not in cand.get("eligible_positions", []):
        raise DraftError(f"'{player_name}' cannot play {slot}")
    if not cand.get("eligible") or slot not in cand.get("eligible_slots", []):
        raise DraftError(
            f"'{player_name}' is not selectable at {slot} "
            f"(over budget — costs {cand.get('cost')}, "
            f"{state and rating.CAP_BUDGET - _spent(state['picks'])} left)"
        )

    picked_player = {k: v for k, v in cand.items()
                     if k not in ("eligible", "eligible_slots", "affordable",
                                  "taken", "forced")}
    picked_player["position"] = slot
    state["picks"].append({"slot": slot, "player": picked_player})
    state["open_slots"] = [s for s in state["open_slots"] if s != slot]

    rng = random.Random()
    if state["open_slots"]:
        state["current"] = _build_step(rng, state["open_slots"],
                                       _picked_names(state), _spent(state["picks"]))
        db.update_state(match_id, state)
        return {"done": False, **_public_view(match, state)}

    state["current"] = None
    return _resolve(match, state)


def _poisson(rng: random.Random, lam: float) -> int:
    """Sample a Poisson(lam) — variance equals the mean, so low averages (e.g.
    a guard's 0.2 blocks) almost always read 0 and never inflate."""
    if lam <= 0:
        return 0
    import math
    target = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= target:
            return k - 1


def _simulate_box(players: list, team_pts: int, rng: random.Random,
                  status: dict | None = None) -> dict:
    """Simulate a single-game box score per player; points sum to the team's
    final score. Hot players get boosted lines, slumping players reduced ones."""
    status = status or {}

    def mult(name):
        st = status.get(name)
        return HOT_STAT_MULT if st == "hot" else SLUMP_STAT_MULT if st == "slump" else 1.0

    # Points: allocate the team total by scoring ability (hot/slump tilt it).
    weights = [max(p.ppg, 1.0) * rng.uniform(0.7, 1.35) * mult(p.name) for p in players]
    tot = sum(weights) or 1.0
    raw = [team_pts * w / tot for w in weights]
    pts = [max(0, int(round(x))) for x in raw]
    diff = int(team_pts) - sum(pts)
    order = sorted(range(len(players)), key=lambda i: -raw[i])
    i = 0
    while diff != 0 and order:
        idx = order[i % len(order)]
        step = 1 if diff > 0 else -1
        if pts[idx] + step >= 0:
            pts[idx] += step
            diff -= step
        i += 1

    lines = {}
    for p, pt in zip(players, pts):
        m = mult(p.name)
        lines[p.name] = {
            "pts": pt,
            "reb": _poisson(rng, p.rpg * m),
            "ast": _poisson(rng, p.apg * m),
            "stl": _poisson(rng, p.spg * m),
            "blk": _poisson(rng, p.bpg * m),
            "status": status.get(p.name),
        }
    return lines


def score_lineups(home_players: list, away_players: list, opponent_label: str,
                  rng: random.Random | None = None,
                  home_status: dict | None = None, away_status: dict | None = None) -> tuple[str, dict]:
    """Score two lineups head-to-head from the home side's POV. Returns
    (outcome, payload) where payload omits match_id/record (caller adds them).
    Pass home_status/away_status to reuse pre-rolled Hot/Slump (so both players
    in a PvP match see identical statuses); otherwise they're rolled here."""
    rng = rng or random.Random()
    home_status = roll_status(home_players, rng) if home_status is None else home_status
    away_status = roll_status(away_players, rng) if away_status is None else away_status
    result = duel(home_players=home_players, away_players=away_players,
                  home_status=home_status, away_status=away_status, rng=rng)
    outcome = {"home": "win", "away": "loss", "tie": "tie"}[result.winner]

    home_box = _simulate_box([s.player for s in result.home.player_scores],
                             int(result.home_final), rng, home_status)
    away_box = _simulate_box([s.player for s in result.away.player_scores],
                             int(result.away_final), rng, away_status)

    def team_payload(team, box, status, delta_by_pos) -> dict:
        return {
            "base_total": round(team.base_total, 2),
            "fit_adjustment": round(team.fit_adjustment, 2),
            "adjusted_total": round(team.adjusted_total, 2),
            "fit_notes": team.fit_notes,
            "players": [
                {
                    "name": s.player.name,
                    "position": s.player.position,
                    "team": teams.era_team_name(s.player.team, s.player.decade),
                    "decade": s.player.decade,
                    "height_in": s.player.height_in,
                    "tier": rating.player_tier(_player_rating(s.player))["id"],
                    "cost": rating.player_cost(_player_rating(s.player)),
                    "rating": round(s.total - team.status_deltas.get(s.player.name, 0.0), 1),
                    "delta": round(delta_by_pos.get(s.player.position, 0.0), 1),
                    "status_delta": round(team.status_deltas.get(s.player.name, 0.0), 1),
                    "status": status.get(s.player.name),
                    "game": box.get(s.player.name, {}),
                }
                for s in sorted(
                    team.player_scores,
                    key=lambda s: ["PG", "SG", "SF", "PF", "C"].index(s.player.position)
                    if s.player.position in ("PG", "SG", "SF", "PF", "C") else 99,
                )
            ],
        }

    home_delta_by_pos = {m.position: m.home_delta for m in result.matchups}
    away_delta_by_pos = {m.position: m.away_delta for m in result.matchups}

    payload = {
        "outcome": outcome,
        "your_final": round(result.home_final, 2),
        "opponent_final": round(result.away_final, 2),
        "opponent_team": opponent_label,
        "overtime": result.overtime,
        "regulation": result.regulation,
        "your_team": team_payload(result.home, home_box, home_status, home_delta_by_pos),
        "opponent_team_scored": team_payload(result.away, away_box, away_status, away_delta_by_pos),
        "matchups": [
            {
                "position": m.position,
                "home_player": m.home_player,
                "away_player": m.away_player,
                "home_score": round(m.home_score, 2),
                "away_score": round(m.away_score, 2),
                "winner": m.winner,
                "note": m.note,
                "home_delta": round(m.home_delta, 1),
                "away_delta": round(m.away_delta, 1),
                "home_status": home_status.get(m.home_player),
                "away_status": away_status.get(m.away_player),
                "home_status_delta": round(result.home.status_deltas.get(m.home_player, 0.0), 1),
                "away_status_delta": round(result.away.status_deltas.get(m.away_player, 0.0), 1),
            }
            for m in result.matchups
        ],
        "your_matchup_wins": result.home_matchup_wins,
        "opponent_matchup_wins": result.away_matchup_wins,
    }
    return outcome, payload


def _resolve(match: dict, state: dict) -> dict:
    drafted = [player_from_dict(p["player"]) for p in state["picks"]]
    opponent = [player_from_dict(d) for d in match["opponent_json"]]

    outcome, result_payload = score_lineups(drafted, opponent, match["opponent_team"])
    # Offline is unranked & casual: no W/L, rating, streaks, achievements, or
    # best-team tracking — purely a warm-up.
    result_payload["match_id"] = match["id"]
    result_payload["record"] = db.get_record(match["username"])
    result_payload["newly_unlocked"] = []
    result_payload["ranked"] = False
    result_payload["rating_change"] = 0

    db.resolve_match(match["id"], state, result_payload)
    return {"done": True, "result": result_payload}


def list_current_teams() -> list[str]:
    return list(dataset.current_starters().keys())
