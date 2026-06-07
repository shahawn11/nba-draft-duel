"""
Game logic: 82-0-style sequential blind draft.

You fill five fixed slots (PG/SG/SF/PF/C) one at a time. Each step reveals a
fresh random decade x team and that franchise's top-10 players for the decade
(stats are decade averages). You may only place a player in the current slot if
they're eligible for it; ineligible / already-taken players are shown but not
selectable. Future steps and the opponent stay hidden until the draft resolves.
"""
from __future__ import annotations

import random
import uuid

from . import db, dataset
from .models import player_from_dict, player_to_dict
from .positions import SLOTS, can_play
from .scoring import PlayerStats, duel


def _picked_names(state: dict) -> set[str]:
    return {p["player"]["name"] for p in state["picks"]}


def _build_step(rng: random.Random, slot: str, picked: set[str]) -> dict:
    """Pick a random (decade, team) that has a selectable player for `slot`."""
    pool = dataset.historical_pool()
    keys = list(pool.keys())
    rng.shuffle(keys)

    chosen = None
    for k in keys:
        if any(can_play(p.eligible(), slot) and p.name not in picked for p in pool[k]):
            chosen = k
            break
    if chosen is None:                       # safety net (shouldn't happen)
        chosen = rng.choice(keys)

    decade, team = chosen.split("|", 1)
    candidates = []
    for p in pool[chosen]:
        d = player_to_dict(p)
        d["eligible"] = can_play(p.eligible(), slot) and (p.name not in picked)
        candidates.append(d)
    return {"slot": slot, "decade": decade, "team": team, "candidates": candidates}


def _public_view(match: dict, state: dict) -> dict:
    return {
        "match_id": match["id"],
        "username": match["username"],
        "mode": match["mode"],
        "status": match["status"],
        "total_slots": len(state["slot_order"]),
        "picks_made": len(state["picks"]),
        "filled": [
            {"slot": p["slot"], "name": p["player"]["name"],
             "position": p["player"]["position"]}
            for p in state["picks"]
        ],
        "current_step": state.get("current"),
    }


def new_match(username: str, seed: int | None = None) -> dict:
    rng = random.Random(seed)
    db.ensure_user(username)

    opp_team, opponent = dataset.random_current_opponent(rng)

    slot_order = list(SLOTS)
    rng.shuffle(slot_order)
    state = {
        "slot_order": slot_order,
        "step": 0,
        "picks": [],
        "current": _build_step(rng, slot_order[0], set()),
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


def pick(match_id: str, player_name: str) -> dict:
    match = db.get_match(match_id)
    if not match:
        raise DraftError("match not found")
    if match["status"] == "resolved":
        raise DraftError("match already resolved")

    state = match["state_json"]
    current = state["current"]
    slot = current["slot"]

    cand = next((c for c in current["candidates"] if c["name"] == player_name), None)
    if cand is None:
        raise DraftError(f"'{player_name}' is not in the current pool")
    if not cand.get("eligible"):
        raise DraftError(f"'{player_name}' cannot play {slot} (or is already drafted)")

    # Record the pick, forcing the player's effective position to the slot.
    picked_player = dict(cand)
    picked_player.pop("eligible", None)
    picked_player["position"] = slot
    state["picks"].append({"slot": slot, "player": picked_player})

    state["step"] += 1
    rng = random.Random()

    if state["step"] < len(state["slot_order"]):
        next_slot = state["slot_order"][state["step"]]
        state["current"] = _build_step(rng, next_slot, _picked_names(state))
        db.update_state(match_id, state)
        return {"done": False, **_public_view(match, state)}

    # All slots filled -> resolve the duel.
    state["current"] = None
    return _resolve(match, state)


def _resolve(match: dict, state: dict) -> dict:
    drafted = [player_from_dict(p["player"]) for p in state["picks"]]
    opponent = [player_from_dict(d) for d in match["opponent_json"]]

    result = duel(home_players=drafted, away_players=opponent)
    outcome = {"home": "win", "away": "loss", "tie": "tie"}[result.winner]
    record = db.apply_result(match["username"], outcome)

    def team_payload(team) -> dict:
        return {
            "base_total": round(team.base_total, 2),
            "fit_adjustment": round(team.fit_adjustment, 2),
            "adjusted_total": round(team.adjusted_total, 2),
            "fit_notes": team.fit_notes,
            "players": [
                {
                    "name": s.player.name,
                    "position": s.player.position,
                    "production": round(s.production, 2),
                    "advanced": round(s.advanced, 2),
                    "total": round(s.total, 2),
                }
                for s in sorted(team.player_scores, key=lambda s: -s.total)
            ],
        }

    result_payload = {
        "match_id": match["id"],
        "outcome": outcome,
        "your_final": round(result.home_final, 2),
        "opponent_final": round(result.away_final, 2),
        "opponent_team": match["opponent_team"],
        "your_team": team_payload(result.home),
        "opponent_team_scored": team_payload(result.away),
        "matchups": [
            {
                "position": m.position,
                "home_player": m.home_player,
                "away_player": m.away_player,
                "home_score": round(m.home_score, 2),
                "away_score": round(m.away_score, 2),
                "winner": m.winner,
            }
            for m in result.matchups
        ],
        "your_matchup_wins": result.home_matchup_wins,
        "opponent_matchup_wins": result.away_matchup_wins,
        "record": record,
    }
    db.resolve_match(match["id"], state, result_payload)
    return {"done": True, "result": result_payload}


def list_current_teams() -> list[str]:
    return list(dataset.current_starters().keys())
