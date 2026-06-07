"""
Bridges the pipeline output (players.db) to the live game.

If app/data/players.db exists, draft pools are built from it: per (decade, team)
we take each player's best season (most minutes) and keep the top candidates by
impact. Otherwise we fall back to the curated seed pools so the game always
runs.

Current-NBA opponents still come from seed_data -- the historical pipeline does
not define "current starting fives" (that's a separate, smaller dataset).
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from . import seed_data
from .positions import eligible_from_raw
from .scoring import PlayerStats

DB_PATH = Path(__file__).parent / "data" / "players.db"
POOL_SIZE = 10          # every draftable (decade, team) pool shows exactly this many
MIN_CANDIDATES = POOL_SIZE
MAX_CANDIDATES = POOL_SIZE


def _load_from_db(path: Path) -> dict[str, list[PlayerStats]]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(players)")}
        if not {"decade", "team", "name"} <= cols:
            return {}
        has_elig = "eligible" in cols
        has_gp = "gp" in cols
        sel = "decade, team, name, position, ppg, rpg, apg, spg, bpg, bpm"
        sel += ", eligible" if has_elig else ""
        sel += ", gp" if has_gp else ""
        rows = conn.execute(f"SELECT {sel} FROM players").fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()

    # Aggregate each player's DECADE AVERAGE for a franchise (games-weighted).
    # key -> name -> accumulator
    agg: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        key = f"{r['decade']}|{r['team']}"
        w = float(r["gp"]) if has_gp and r["gp"] else 1.0
        a = agg[key].get(r["name"])
        if a is None:
            a = {
                "w": 0.0, "ppg": 0.0, "rpg": 0.0, "apg": 0.0, "spg": 0.0,
                "bpg": 0.0, "bpm": 0.0, "position": r["position"],
                "eligible": (r["eligible"] if has_elig else "") or "",
            }
            agg[key][r["name"]] = a
        a["w"] += w
        for s in ("ppg", "rpg", "apg", "spg", "bpg", "bpm"):
            a[s] += (r[s] or 0) * w

    pool: dict[str, list[PlayerStats]] = {}
    for key, namemap in agg.items():
        decade, team = key.split("|", 1)
        cands: list[PlayerStats] = []
        for name, a in namemap.items():
            w = a["w"] or 1.0
            elig = tuple(p for p in a["eligible"].split(",") if p) or \
                eligible_from_raw(None, a["position"])
            cands.append(PlayerStats(
                name=name, position=a["position"],
                ppg=round(a["ppg"] / w, 1), rpg=round(a["rpg"] / w, 1),
                apg=round(a["apg"] / w, 1), spg=round(a["spg"] / w, 1),
                bpg=round(a["bpg"] / w, 1), bpm=round(a["bpm"] / w, 2),
                team=team, season=decade, decade=decade,
                eligible_positions=elig,
            ))
        # "Top 10" = most notable players: scoring-led with a light impact nudge.
        # Pure PIE/impact buried high scorers like Klay Thompson behind forgettable
        # role players, so we lead with points.
        cands.sort(key=lambda p: p.ppg + 0.5 * p.bpm, reverse=True)
        cands = cands[:MAX_CANDIDATES]
        if len(cands) >= MIN_CANDIDATES:
            pool[key] = cands
    return pool


@lru_cache(maxsize=1)
def historical_pool() -> dict[str, list[PlayerStats]]:
    """Draftable pools keyed 'decade|team'.

    Curated seed pools (1960s-1980s) are merged with pipeline pools from
    players.db (1996-present); the DB wins on any key conflict (real data
    over curated). Only pools with a full POOL_SIZE roster are kept.
    """
    seed = {k: v for k, v in seed_data.HISTORICAL_POOL.items() if len(v) >= MIN_CANDIDATES}
    if DB_PATH.exists():
        db = _load_from_db(DB_PATH)
        if db:
            return {**seed, **db}
    return seed


def source() -> str:
    """Where pools came from -- handy for /health and debugging."""
    if DB_PATH.exists() and _load_from_db(DB_PATH):
        return "players.db + seed"
    return "seed"


def current_starters() -> dict[str, list[PlayerStats]]:
    return seed_data.CURRENT_STARTERS


def random_current_opponent(rng):
    return seed_data.random_current_opponent(rng)
