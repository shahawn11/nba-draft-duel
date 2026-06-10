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
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

from . import seed_data
from .positions import SLOTS, eligible_from_raw
from .scoring import PlayerStats, score_player, final_overall
from . import rating

DB_PATH = Path(__file__).parent / "data" / "players.db"
POOL_SIZE = 10          # every draftable (decade, team) pool shows exactly this many
MIN_CANDIDATES = POOL_SIZE
MAX_CANDIDATES = POOL_SIZE
PEAK_MIN_GP = 25        # a season needs this many games to qualify as the "peak"

# Real heights (inches) for draftable players the pipeline left without one
# (mostly 1990s rows). Used as a fallback so the fit/size logic judges them on
# true size instead of the rebound proxy. Keyed by player name.
HEIGHT_OVERRIDES: dict[str, float] = {
    "Luc Longley": 86,        # 7'2"
    "Matt Geiger": 84,        # 7'0"
    "Chris Gatling": 82,      # 6'10"
    "Chris Mullin": 78,       # 6'6"
    "Todd Day": 78,           # 6'6"
    "Eddie Johnson": 79,      # 6'7"
    "Isaiah Rider": 77,       # 6'5"
    "Sam Mack": 79,           # 6'7"
    "Vinny Del Negro": 76,    # 6'4"
    "Mookie Blaylock": 72,    # 6'0"
}


def _blended_by_key(path: Path) -> dict[str, dict[str, tuple[float, PlayerStats]]]:
    """Per (decade|team, player): a PlayerStats whose scoring stats are a 50/50
    blend of the player's peak season and decade average, plus display fields
    (decade_*, peak_*). Returns key -> {name: (notability, PlayerStats)}; no
    roster-size filter (so it also feeds seed-pool enrichment for pre-1996)."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(players)")}
        if not {"decade", "team", "name"} <= cols:
            return {}
        has_elig = "eligible" in cols
        has_gp = "gp" in cols
        has_height = "height_in" in cols
        has_season = "season" in cols
        has_ts = "ts_pct" in cols
        has_dbpm = "dbpm" in cols
        has_three = "three_pa" in cols
        sel = "decade, team, name, position, ppg, rpg, apg, spg, bpg, bpm"
        sel += ", eligible" if has_elig else ""
        sel += ", gp" if has_gp else ""
        sel += ", height_in" if has_height else ""
        sel += ", season" if has_season else ""
        sel += ", ts_pct" if has_ts else ""
        sel += ", dbpm" if has_dbpm else ""
        sel += ", three_pa, three_pct" if has_three else ""
        rows = conn.execute(f"SELECT {sel} FROM players").fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()

    # Collect every (decade, team) player's individual SEASON rows.
    by_player: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        key = f"{r['decade']}|{r['team']}"
        by_player[key][r["name"]].append({
            "ppg": r["ppg"] or 0.0, "rpg": r["rpg"] or 0.0, "apg": r["apg"] or 0.0,
            "spg": r["spg"] or 0.0, "bpg": r["bpg"] or 0.0, "bpm": r["bpm"] or 0.0,
            "ts_pct": (r["ts_pct"] if has_ts else 0.0) or 0.0,
            "dbpm": (r["dbpm"] if has_dbpm else 0.0) or 0.0,
            "three_pa": (r["three_pa"] if has_three else 0.0) or 0.0,
            "three_pct": (r["three_pct"] if has_three else 0.0) or 0.0,
            "gp": float(r["gp"]) if has_gp and r["gp"] else 1.0,
            "position": r["position"],
            "eligible": (r["eligible"] if has_elig else "") or "",
            "height_in": (r["height_in"] if has_height else 0.0) or HEIGHT_OVERRIDES.get(r["name"], 0.0),
            "season": (r["season"] if has_season else "") or "",
        })

    out: dict[str, dict[str, tuple[float, PlayerStats]]] = {}
    for key, namemap in by_player.items():
        decade, team = key.split("|", 1)
        per_name: dict[str, tuple[float, PlayerStats]] = {}
        for name, seasons in namemap.items():
            # Games-weighted decade average (a full season is more representative
            # than a short one).
            wtot = sum(s["gp"] for s in seasons) or 1.0
            def avg(stat: str) -> float:
                return sum(s[stat] * s["gp"] for s in seasons) / wtot
            d_ppg, d_rpg, d_apg = avg("ppg"), avg("rpg"), avg("apg")
            d_spg, d_bpg = avg("spg"), avg("bpg")

            sample = seasons[0]
            elig = tuple(p for p in sample["eligible"].split(",") if p) or \
                eligible_from_raw(None, sample["position"])

            def mk_from_stats(ppg, rpg, apg, spg, bpg, bpm, ts, dbpm, t3a, t3p, *, peak_label: str) -> PlayerStats:
                return PlayerStats(
                    name=name, position=sample["position"],
                    ppg=round(ppg, 1), rpg=round(rpg, 1), apg=round(apg, 1),
                    spg=round(spg, 1), bpg=round(bpg, 1), bpm=round(bpm, 2),
                    ts_pct=round(ts, 3), dbpm=round(dbpm, 2),
                    three_pa=round(t3a, 1), three_pct=round(t3p, 3),
                    team=team, season=peak_label, decade=decade,
                    height_in=sample["height_in"], eligible_positions=elig,
                    decade_ppg=round(d_ppg, 1), decade_rpg=round(d_rpg, 1),
                    decade_apg=round(d_apg, 1), decade_spg=round(d_spg, 1),
                    decade_bpg=round(d_bpg, 1),
                    peak_season=peak_label,
                )

            def score_of(s: dict) -> float:
                return score_player(mk_from_stats(
                    s["ppg"], s["rpg"], s["apg"], s["spg"], s["bpg"], s["bpm"],
                    s["ts_pct"], s["dbpm"], s["three_pa"], s["three_pct"], peak_label="")).total

            qualifying = [s for s in seasons if s["gp"] >= PEAK_MIN_GP] or seasons
            pk = max(qualifying, key=score_of)

            def blend(stat: str, peak_val: float) -> float:
                return 0.5 * peak_val + 0.5 * avg(stat)
            player = mk_from_stats(
                blend("ppg", pk["ppg"]), blend("rpg", pk["rpg"]),
                blend("apg", pk["apg"]), blend("spg", pk["spg"]),
                blend("bpg", pk["bpg"]), blend("bpm", pk["bpm"]),
                blend("ts_pct", pk["ts_pct"]), blend("dbpm", pk["dbpm"]),
                blend("three_pa", pk["three_pa"]), blend("three_pct", pk["three_pct"]),
                peak_label=pk["season"],
            )
            player = replace(
                player,
                peak_ppg=round(pk["ppg"], 1), peak_rpg=round(pk["rpg"], 1),
                peak_apg=round(pk["apg"], 1), peak_bpm=round(pk["bpm"], 2),
            )
            notability = d_ppg + 0.5 * avg("bpm")
            per_name[name] = (notability, player)
        out[key] = per_name
    return out


# Stat/display fields copied when a seed player is enriched from real DB data
# (their curated position / eligibility / height / team identity are kept).
_INJECT_FIELDS = (
    "ppg", "rpg", "apg", "spg", "bpg", "bpm", "season", "ts_pct", "dbpm",
    "three_pa", "three_pct",
    "decade_ppg", "decade_rpg", "decade_apg", "decade_spg", "decade_bpg",
    "peak_ppg", "peak_rpg", "peak_apg", "peak_bpm", "peak_season",
)


def _select_pool(key: str, per_name: dict[str, tuple[float, PlayerStats]]) -> list[PlayerStats]:
    """The decade's top-N by notability, with any POOL_FORCE_INCLUDE players
    guaranteed a slot (dropping the lowest-notability non-forced member to keep
    the pool size). Lets elite non-scorers (e.g. Ben Wallace) be draftable."""
    decade, team = key.split("|", 1)
    forced = set(rating.POOL_FORCE_INCLUDE.get((decade, team), []))
    ranked = sorted(per_name.values(), key=lambda t: t[0], reverse=True)  # (notability, ps)
    top = ranked[:MAX_CANDIDATES]
    have = {ps.name for _, ps in top}
    missing = [per_name[n] for n in forced if n in per_name and n not in have]
    if missing:
        # Drop the lowest-notability non-forced members to make room.
        keep = [t for t in top if t[1].name in forced]
        droppable = [t for t in top if t[1].name not in forced]
        room = MAX_CANDIDATES - len(keep) - len(missing)
        keep += sorted(droppable, key=lambda t: t[0], reverse=True)[:max(0, room)]
        top = keep + missing
    return [ps for _, ps in top]


def _load_from_db(path: Path) -> dict[str, list[PlayerStats]]:
    """Full (decade|team) pools from players.db: the decade's top-N most notable
    players (plus force-includes), each rated on the peak/decade blend."""
    pool: dict[str, list[PlayerStats]] = {}
    for key, per_name in _blended_by_key(path).items():
        if len(per_name) >= MIN_CANDIDATES:
            pool[key] = _select_pool(key, per_name)
    return pool


def _enrich_seed(seed: dict[str, list[PlayerStats]],
                 blended: dict[str, dict[str, tuple[float, PlayerStats]]]) -> dict[str, list[PlayerStats]]:
    """Overlay real peak/decade stats onto curated seed players that have pulled
    data (e.g. pre-1990 legends). Keeps the seed player's position, eligibility,
    height and team; only the stats + peak/decade display fields are injected."""
    enriched: dict[str, list[PlayerStats]] = {}
    for key, players in seed.items():
        by_name = blended.get(key, {})
        new_list = []
        for p in players:
            entry = by_name.get(p.name)
            if entry:
                ov = entry[1]
                new_list.append(replace(p, **{f: getattr(ov, f) for f in _INJECT_FIELDS}))
            else:
                new_list.append(p)
        enriched[key] = new_list
    return enriched


@lru_cache(maxsize=1)
def historical_pool() -> dict[str, list[PlayerStats]]:
    """Draftable pools keyed 'decade|team'.

    Curated seed pools (1960s-1980s) are ENRICHED with real peak/decade stats
    for any player we pulled (pre-1990 legends), then merged with the full
    pipeline pools from players.db (1996-present); the DB wins on any key
    conflict. Only pools with a full POOL_SIZE roster are kept.
    """
    seed = {k: v for k, v in seed_data.HISTORICAL_POOL.items() if len(v) >= MIN_CANDIDATES}
    if DB_PATH.exists():
        blended = _blended_by_key(DB_PATH)
        if blended:
            db = {
                key: _select_pool(key, per_name)
                for key, per_name in blended.items()
                if len(per_name) >= MIN_CANDIDATES
            }
            enriched = _enrich_seed(seed, blended)
            return _apply_overrides({**enriched, **db})
    return _apply_overrides(seed)


def _apply_overrides(pools: dict[str, list[PlayerStats]]) -> dict[str, list[PlayerStats]]:
    """Stamp each player's final rating, keyed by the pool KEY's decade+team
    (ALWAYS the full franchise name -- so it works whether the player's own team
    field is an abbreviation (pre-1996 seed) or a full name (DB)). Precedence:
      1. curated 2K+BBRef blended overall (k2_final_ratings.json), else
      2. legacy formula override (rating.RATING_OVERRIDES), else
      3. leave the player to the live formula.
    Stamping as rating_override guarantees the blend reaches score_player even
    for seed players whose team field is an abbreviation the JSON can't key on."""
    ov = rating.RATING_OVERRIDES
    out: dict[str, list[PlayerStats]] = {}
    for key, players in pools.items():
        decade, team = key.split("|", 1)
        new: list[PlayerStats] = []
        for p in players:
            blend = final_overall(p.name, decade, team)
            if blend is not None:
                new.append(replace(p, rating_override=blend))
            elif (p.name, decade, team) in ov:
                new.append(replace(p, rating_override=ov[(p.name, decade, team)]))
            else:
                new.append(p)
        out[key] = new
    return out


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
    FILL_ORDER = ["C", "PF", "SF", "PG", "SG"]

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

    def _elig(r) -> tuple:
        return tuple(p for p in ((r["eligible"] if has_elig else "") or "").split(",") if p) \
            or eligible_from_raw(None, r["position"])

    # Pick each slot by the stat that defines it, so the right guard plays PG
    # (most assists) and the scorer plays SG, the biggest body anchors C, etc.
    SLOT_KEY = {
        "PG": lambda r: r["apg"] or 0,
        "SG": lambda r: r["ppg"] or 0,
        "SF": lambda r: r["mpg"] or 0,
        "PF": lambda r: (r["rpg"] or 0) + _height(r) / 12,
        "C": lambda r: _height(r) or (r["rpg"] or 0),
    }

    assigned: dict[str, PlayerStats] = {}
    used: set[str] = set()
    for slot in FILL_ORDER:
        key = SLOT_KEY.get(slot, lambda r: r["mpg"] or 0)
        best = None
        for r in players:
            if r["name"] in used or slot not in _elig(r):
                continue
            if best is None or key(r) > key(best):
                best = r
        if best is not None:
            assigned[slot] = _mk(best, slot, _elig(best))
            used.add(best["name"])
    if len(assigned) < len(SLOTS):
        ordered = sorted(players, key=lambda r: -(r["mpg"] or 0))
        for slot in FILL_ORDER:
            if slot in assigned:
                continue
            remaining = [r for r in ordered if r["name"] not in used]
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


_CURATED_COLS = ("ppg rpg apg spg bpg bpm ts_pct dbpm height_in three_pa three_pct")


def _load_curated_starters(path: Path) -> dict[str, list[PlayerStats]]:
    """Authoritative curated current-NBA fives (app/current_fives.py): each named
    player is placed in his listed slot and flagged current_form=True so scoring
    uses the current-form blend. Stats come from his most-recent season row (so
    a star who missed the current season still gets a sensible statline)."""
    from .current_fives import CURATED_STARTING_FIVES
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(players)")}
        if not {"name", "season", "ppg"} <= cols:
            return {}
        sel = "name, position, season, height_in, " + ", ".join(_CURATED_COLS.split())
        season = conn.execute("SELECT MAX(season) FROM players").fetchone()[0]
        # most-recent row per player (ascending order -> last write wins)
        rows = conn.execute(f"SELECT {sel} FROM players ORDER BY season").fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()
    latest: dict[str, sqlite3.Row] = {r["name"]: r for r in rows}

    def _mk(name: str, slot: str, team: str) -> PlayerStats | None:
        r = latest.get(name)
        if r is None:
            return None
        g = lambda k: (r[k] if k in r.keys() else 0) or 0
        return PlayerStats(
            name=name, position=slot,
            ppg=g("ppg"), rpg=g("rpg"), apg=g("apg"), spg=g("spg"), bpg=g("bpg"),
            bpm=g("bpm"), ts_pct=g("ts_pct"), dbpm=g("dbpm"),
            three_pa=g("three_pa"), three_pct=g("three_pct"),
            team=team, season=season, height_in=g("height_in"),
            eligible_positions=(slot,), current_form=True,
        )

    out: dict[str, list[PlayerStats]] = {}
    for team, five in CURATED_STARTING_FIVES.items():
        built = [_mk(name, slot, team) for name, slot in five]
        if all(built) and len(built) == 5:
            out[team] = built  # already in PG/SG/SF/PF/C order
    return out


@lru_cache(maxsize=1)
def current_starters() -> dict[str, list[PlayerStats]]:
    """Curated, healthy current-NBA fives (current_fives.py) are authoritative.
    Falls back to derived top-minutes / most-used lineups for any team the
    curated list misses, then to the seed list if there's no DB."""
    if DB_PATH.exists():
        curated = _load_curated_starters(DB_PATH)
        derived = _load_current_starters(DB_PATH)
        real = _load_starters_from_lineups(DB_PATH)
        merged = {**derived, **real, **curated}  # curated wins per team
        if merged:
            return merged
    return seed_data.CURRENT_STARTERS


def starters_source() -> str:
    if DB_PATH.exists() and _load_curated_starters(DB_PATH):
        return "curated fives"
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
