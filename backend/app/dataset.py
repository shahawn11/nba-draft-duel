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
from .scoring import PlayerStats

DB_PATH = Path(__file__).parent / "data" / "players.db"
MIN_CANDIDATES = 3      # a (decade, team) pool needs at least this many to be draftable
MAX_CANDIDATES = 10     # cap candidates shown per prompt


def _load_from_db(path: Path) -> dict[str, list[PlayerStats]]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT decade, team, name, position, season,
                      ppg, rpg, apg, spg, bpg, bpm, mpg
               FROM players"""
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()

    # key -> name -> (mpg, PlayerStats)  keeping each player's best season
    best: dict[str, dict[str, tuple[float, PlayerStats]]] = defaultdict(dict)
    for r in rows:
        key = f"{r['decade']}|{r['team']}"
        ps = PlayerStats(
            name=r["name"], position=r["position"],
            ppg=r["ppg"] or 0, rpg=r["rpg"] or 0, apg=r["apg"] or 0,
            spg=r["spg"] or 0, bpg=r["bpg"] or 0, bpm=r["bpm"] or 0,
            team=r["team"], season=r["season"], decade=r["decade"],
        )
        mpg = r["mpg"] or 0
        prev = best[key].get(r["name"])
        if prev is None or mpg > prev[0]:
            best[key][r["name"]] = (mpg, ps)

    pool: dict[str, list[PlayerStats]] = {}
    for key, namemap in best.items():
        cands = [ps for _, ps in namemap.values()]
        cands.sort(key=lambda p: p.bpm, reverse=True)
        cands = cands[:MAX_CANDIDATES]
        if len(cands) >= MIN_CANDIDATES:
            pool[key] = cands
    return pool


@lru_cache(maxsize=1)
def historical_pool() -> dict[str, list[PlayerStats]]:
    """Draftable pools keyed 'decade|team'. DB-backed if available, else seed."""
    if DB_PATH.exists():
        pool = _load_from_db(DB_PATH)
        if pool:
            return pool
    return seed_data.HISTORICAL_POOL


def source() -> str:
    """Where pools came from -- handy for /health and debugging."""
    return "players.db" if (DB_PATH.exists() and _load_from_db(DB_PATH)) else "seed"


def current_starters() -> dict[str, list[PlayerStats]]:
    return seed_data.CURRENT_STARTERS


def random_current_opponent(rng):
    return seed_data.random_current_opponent(rng)
