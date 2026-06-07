"""
Game logic: build match prompts and resolve a submitted draft into a duel.

Offline mode: opponent is a random current NBA starting 5. The player gets 5
draft prompts (each a random decade x team pool) and picks one player per
prompt. Positional fit is judged on the natural positions of their 5 picks.
"""
from __future__ import annotations

import random
import uuid

from . import db, dataset
from .models import player_from_dict, player_to_dict
from .scoring import PlayerStats, duel

NUM_PROMPTS = 5


def _make_prompts(rng: random.Random) -> list[dict]:
    pool = dataset.historical_pool()
    keys = list(pool.keys())
    rng.shuffle(keys)
    # Distinct pools first; if fewer pools than prompts, allow repeats.
    chosen: list[str] = []
    while len(chosen) < NUM_PROMPTS:
        if keys:
            chosen.append(keys.pop())
        else:
            chosen.append(rng.choice(list(pool.keys())))

    prompts = []
    for i, key in enumerate(chosen):
        decade, team = key.split("|", 1)
        candidates = [player_to_dict(p) for p in pool[key]]
        prompts.append(
            {"index": i, "decade": decade, "team": team, "candidates": candidates}
        )
    return prompts


def new_match(username: str, seed: int | None = None) -> dict:
    rng = random.Random(seed)
    db.ensure_user(username)

    opp_team, opponent = dataset.random_current_opponent(rng)
    prompts = _make_prompts(rng)

    match_id = uuid.uuid4().hex[:12]
    db.create_match(
        match_id=match_id,
        username=username,
        opponent_team=opp_team,
        opponent_json=[player_to_dict(p) for p in opponent],
        prompts_json=prompts,
    )
    return {"match_id": match_id, "username": username, "mode": "offline", "prompts": prompts}


class DraftError(ValueError):
    pass


def resolve_draft(match_id: str, picks: list[dict]) -> dict:
    match = db.get_match(match_id)
    if not match:
        raise DraftError("match not found")
    if match["status"] == "resolved":
        raise DraftError("match already resolved")

    prompts = {p["index"]: p for p in match["prompts_json"]}
    if {pk["prompt_index"] for pk in picks} != set(prompts.keys()):
        raise DraftError("must submit exactly one pick per prompt")

    drafted: list[PlayerStats] = []
    seen_names: set[str] = set()
    for pk in picks:
        prompt = prompts[pk["prompt_index"]]
        match_player = next(
            (c for c in prompt["candidates"] if c["name"] == pk["player_name"]),
            None,
        )
        if match_player is None:
            raise DraftError(
                f"'{pk['player_name']}' is not a candidate for prompt {pk['prompt_index']}"
            )
        if match_player["name"] in seen_names:
            raise DraftError(f"duplicate pick: {match_player['name']}")
        seen_names.add(match_player["name"])
        drafted.append(player_from_dict(match_player))

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

    payload = {
        "match_id": match_id,
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
    db.resolve_match(match_id, payload)
    return payload


def list_current_teams() -> list[str]:
    return list(dataset.current_starters().keys())
