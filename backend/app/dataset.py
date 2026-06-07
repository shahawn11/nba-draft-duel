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
from .positions import SLOTS, eligible_from_raw
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


def _load_current_starters(path: Path) -> dict[str, list[PlayerStats]]:
    """Build each team's starting 5 from the most recent season in the DB:
    greedily assign the highest-minutes eligible player to each slot."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(players)")}
        if "season" not in cols or "mpg" not in cols:
            return {}
        season = conn.execute("SELECT MAX(season) FROM players").fetchone()[0]
        if not season:
            return {}
        has_elig = "eligible" in cols
        sel = "team, name, position, ppg, rpg, apg, spg, bpg, bpm, mpg"
        sel += ", eligible" if has_elig else ""
        rows = conn.execute(f"SELECT {sel} FROM players WHERE season = ?", (season,)).fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()

    by_team: dict[str, list] = defaultdict(list)
    for r in rows:
        by_team[r["team"]].append(r)

    out: dict[str, list[PlayerStats]] = {}
    for team, players in by_team.items():
        players.sort(key=lambda r: -(r["mpg"] or 0))  # minutes => starter proxy
        assigned: dict[str, PlayerStats] = {}
        used: set[str] = set()
        for slot in SLOTS:
            for r in players:
                if r["name"] in used:
                    continue
                elig = tuple(p for p in ((r["eligible"] if has_elig else "") or "").split(",") if p) \
                    or eligible_from_raw(None, r["position"])
                if slot in elig:
                    assigned[slot] = PlayerStats(
                        name=r["name"], position=slot,
                        ppg=r["ppg"] or 0, rpg=r["rpg"] or 0, apg=r["apg"] or 0,
                        spg=r["spg"] or 0, bpg=r["bpg"] or 0, bpm=r["bpm"] or 0,
                        team=team, season=season, eligible_positions=elig,
                    )
                    used.add(r["name"])
                    break
        # Fallback: if eligibility left a slot open (thin/odd roster, e.g. a team
        # gutted by injuries/trades), fill it with the best remaining player.
        if len(assigned) < len(SLOTS):
            remaining = [r for r in players if r["name"] not in used]
            for slot in SLOTS:
                if slot in assigned or not remaining:
                    continue
                r = remaining.pop(0)
                assigned[slot] = PlayerStats(
                    name=r["name"], position=slot,
                    ppg=r["ppg"] or 0, rpg=r["rpg"] or 0, apg=r["apg"] or 0,
                    spg=r["spg"] or 0, bpg=r["bpg"] or 0, bpm=r["bpm"] or 0,
                    team=team, season=season,
                    eligible_positions=(slot,),
                )
                used.add(r["name"])
        if len(assigned) == 5:
            out[team] = [assigned[s] for s in SLOTS]
    return out


@lru_cache(maxsize=1)
def current_starters() -> dict[str, list[PlayerStats]]:
    """Latest-season starting 5s from the DB; falls back to the curated list."""
    if DB_PATH.exists():
        cs = _load_current_starters(DB_PATH)
        if cs:
            return cs
    return seed_data.CURRENT_STARTERS


def current_season() -> str | None:
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        try:
            return conn.execute("SELECT MAX(season) FROM players").fetchone()[0]
        except sqlite3.OperationalError:
            return None
        finally:
            conn.close()
    return None


def random_current_opponent(rng):
    cs = current_starters()
    team = rng.choice(list(cs.keys()))
    return team, cs[team]
