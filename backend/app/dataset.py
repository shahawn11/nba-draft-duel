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
        has_height = "height_in" in cols
        sel = "decade, team, name, position, ppg, rpg, apg, spg, bpg, bpm"
        sel += ", eligible" if has_elig else ""
        sel += ", gp" if has_gp else ""
        sel += ", height_in" if has_height else ""
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
                "height_in": (r["height_in"] if has_height else 0.0) or 0.0,
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
                height_in=a["height_in"],
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


_STARTER_COLS = "team, name, position, ppg, rpg, apg, spg, bpg, bpm, mpg"


def _slot_team(team: str, season: str, players: list, has_elig: bool,
               has_height: bool) -> list[PlayerStats] | None:
    """Assign a set of player rows to PG/SG/SF/PF/C. Fills scarce frontcourt
    slots first; a height-aware fallback covers any gap. Returns 5 or None."""
    FILL_ORDER = ["C", "PF", "SF", "SG", "PG"]

    def _height(r) -> float:
        return (r["height_in"] if has_height else 0.0) or 0.0

    def _mk(r, slot, elig) -> PlayerStats:
        return PlayerStats(
            name=r["name"], position=slot,
            ppg=r["ppg"] or 0, rpg=r["rpg"] or 0, apg=r["apg"] or 0,
            spg=r["spg"] or 0, bpg=r["bpg"] or 0, bpm=r["bpm"] or 0,
            team=team, season=season, height_in=_height(r),
            eligible_positions=elig,
        )

    players = sorted(players, key=lambda r: -(r["mpg"] or 0))
    assigned: dict[str, PlayerStats] = {}
    used: set[str] = set()
    for slot in FILL_ORDER:
        for r in players:
            if r["name"] in used:
                continue
            elig = tuple(p for p in ((r["eligible"] if has_elig else "") or "").split(",") if p) \
                or eligible_from_raw(None, r["position"])
            if slot in elig:
                assigned[slot] = _mk(r, slot, elig)
                used.add(r["name"])
                break
    if len(assigned) < len(SLOTS):
        for slot in FILL_ORDER:
            if slot in assigned:
                continue
            remaining = [r for r in players if r["name"] not in used]
            if not remaining:
                break
            r = max(remaining, key=_height) if slot in ("C", "PF") else remaining[0]
            assigned[slot] = _mk(r, slot, (slot,))
            used.add(r["name"])
    if len(assigned) == 5:
        return [assigned[s] for s in SLOTS]
    return None


def _current_season_rows(path: Path):
    """Return (season, rows-by-player_id, rows-by-team, has_elig, has_height)."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(players)")}
        if "season" not in cols or "mpg" not in cols:
            return None
        season = conn.execute("SELECT MAX(season) FROM players").fetchone()[0]
        if not season:
            return None
        has_elig, has_height = "eligible" in cols, "height_in" in cols
        sel = "player_id, " + _STARTER_COLS
        sel += ", eligible" if has_elig else ""
        sel += ", height_in" if has_height else ""
        rows = conn.execute(f"SELECT {sel} FROM players WHERE season = ?", (season,)).fetchall()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
    by_id = {r["player_id"]: r for r in rows}
    by_team: dict[str, list] = defaultdict(list)
    for r in rows:
        by_team[r["team"]].append(r)
    return season, by_id, by_team, has_elig, has_height


def _load_starters_from_lineups(path: Path) -> dict[str, list[PlayerStats]]:
    """Build starting 5s from the real most-used lineups (starting_lineups table),
    slotting those exact five players by position."""
    info = _current_season_rows(path)
    if not info:
        return {}
    season, by_id, _, has_elig, has_height = info
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        if not conn.execute("SELECT name FROM sqlite_master WHERE name='starting_lineups'").fetchone():
            return {}
        rows = conn.execute("SELECT team, player_id FROM starting_lineups").fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()

    team_ids: dict[str, list] = defaultdict(list)
    for r in rows:
        team_ids[r["team"]].append(r["player_id"])

    out: dict[str, list[PlayerStats]] = {}
    for team, ids in team_ids.items():
        starter_rows = [by_id[i] for i in ids if i in by_id]
        if len(starter_rows) != 5:
            continue  # a starter missing from filtered stats -> fall back later
        slotted = _slot_team(team, season, starter_rows, has_elig, has_height)
        if slotted:
            out[team] = slotted
    return out


def _load_current_starters(path: Path) -> dict[str, list[PlayerStats]]:
    """Derived fallback: build each team's 5 from its highest-minutes players."""
    info = _current_season_rows(path)
    if not info:
        return {}
    season, _, by_team, has_elig, has_height = info
    out: dict[str, list[PlayerStats]] = {}
    for team, players in by_team.items():
        slotted = _slot_team(team, season, players, has_elig, has_height)
        if slotted:
            out[team] = slotted
    return out


@lru_cache(maxsize=1)
def current_starters() -> dict[str, list[PlayerStats]]:
    """Real starting 5s (most-used lineups) when available; derived top-minutes
    fives fill any gaps; curated list only if there's no DB."""
    if DB_PATH.exists():
        real = _load_starters_from_lineups(DB_PATH)
        derived = _load_current_starters(DB_PATH)
        if real or derived:
            return {**derived, **real}  # real lineups win per team
    return seed_data.CURRENT_STARTERS


def starters_source() -> str:
    if DB_PATH.exists() and _load_starters_from_lineups(DB_PATH):
        return "real lineups"
    if DB_PATH.exists() and _load_current_starters(DB_PATH):
        return "derived (top minutes)"
    return "seed"


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
