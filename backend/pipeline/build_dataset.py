"""
Build the historical player dataset into SQLite, with real positions and an
impact metric.

Data sources (all via nba_api -> stats.nba.com):
  * LeagueDashPlayerStats  Base      -> per-game PTS/REB/AST/STL/BLK (+ GP/MIN)
  * LeagueDashPlayerStats  Advanced  -> PIE (Player Impact Estimate)
  * CommonPlayerInfo (per player)     -> coarse position (Guard/Forward/Center)

Two gaps from the original scaffold are now handled:

POSITION
  stats.nba.com only gives coarse positions. We disambiguate to PG/SG/SF/PF/C
  with a stat heuristic (assist rate splits guards, rebound rate splits
  forwards) and CACHE the result per player_id so we fetch each player once
  ever, not once per season.

IMPACT METRIC (the "BPM" column)
  stats.nba.com does NOT expose true Box Plus/Minus -- that's a
  Basketball-Reference metric needing team regression coefficients. We instead
  pull PIE (native, real) and map it onto the BPM scale the scoring engine
  expects:  bpm_est = clamp((PIE - 0.10) * 100, -6, +13).
  PIE ~0.10 is league average (-> BPM ~0); elite stars ~0.18-0.20 (-> +8..+10).
  The column stays named `bpm` so the scoring engine is unchanged, but it is an
  *estimate from PIE*, documented here and in the README.

Usage:
    pip install nba_api pandas
    python pipeline/build_dataset.py --since 1997 --out app/data/players.db
    # quick validation of one recent season, capped:
    python pipeline/build_dataset.py --since 2023 --limit 40

stats.nba.com rate-limits hard; the script sleeps between calls, is resumable
(skips seasons already written), and caches positions across runs.
"""
from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path

# Ensure the backend dir (parent of pipeline/) is importable so `app.*` works
# whether this is run as `python pipeline/build_dataset.py` or `-m pipeline...`.
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Franchise abbreviation -> full name (incl. common historical aliases) --
# Keeps decade x team keys consistent (e.g. SEA/OKC, VAN/MEM, CHH/CHA).
TEAM_ABBREV_TO_FULL: dict[str, str] = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
    "NJN": "Brooklyn Nets", "CHA": "Charlotte Hornets", "CHH": "Charlotte Hornets",
    "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers", "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets", "DET": "Detroit Pistons", "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets", "IND": "Indiana Pacers", "LAC": "Los Angeles Clippers",
    "SDC": "Los Angeles Clippers", "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies", "VAN": "Memphis Grizzlies", "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NOH": "New Orleans Pelicans",
    "NOK": "New Orleans Pelicans", "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder", "SEA": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings",
    "KCK": "Sacramento Kings", "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
    "WSB": "Washington Wizards",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id     INTEGER,
    name          TEXT NOT NULL,
    position      TEXT NOT NULL,         -- PG/SG/SF/PF/C
    team          TEXT NOT NULL,         -- franchise full name
    season        TEXT NOT NULL,
    decade        TEXT NOT NULL,
    ppg  REAL, rpg REAL, apg REAL, spg REAL, bpg REAL,
    bpm  REAL,                           -- impact estimate from PIE (see header)
    pie  REAL,                           -- raw PIE, kept for transparency
    eligible TEXT,                       -- comma-joined slots the player may fill
    height_in REAL,                      -- player height in inches
    gp   INTEGER, mpg REAL,
    UNIQUE(name, season, team)
);
CREATE INDEX IF NOT EXISTS idx_decade_team ON players(decade, team);

CREATE TABLE IF NOT EXISTS position_cache (
    player_id   INTEGER PRIMARY KEY,
    position    TEXT NOT NULL,
    raw         TEXT,
    height_in   REAL
);
"""


def parse_height(raw: str | None) -> float:
    """Parse a stats.nba.com height string like '6-6' into inches (78)."""
    if not raw or "-" not in str(raw):
        return 0.0
    try:
        ft, inch = str(raw).split("-", 1)
        return float(int(ft) * 12 + int(inch))
    except (ValueError, TypeError):
        return 0.0


# ---- Pure helpers (unit-testable, no network) ------------------------------
def season_to_decade(season: str) -> str:
    start_year = int(season.split("-")[0])
    return f"{(start_year // 10) * 10}s"


def full_team_name(abbrev: str) -> str:
    return TEAM_ABBREV_TO_FULL.get((abbrev or "").upper(), abbrev or "Unknown")


def pie_to_bpm(pie: float | None) -> float:
    """Map PIE onto an approximate BPM scale used by the scoring engine."""
    if pie is None:
        return 0.0
    est = (pie - 0.10) * 100.0
    return max(-6.0, min(13.0, est))


def map_position(raw: str | None, apg: float, rpg: float) -> str:
    """Coarse NBA position string + stat heuristic -> PG/SG/SF/PF/C."""
    primary = (raw or "").split("-")[0].strip().lower()
    if primary == "center":
        return "C"
    if primary == "guard":
        return "PG" if apg >= 4.5 else "SG"
    if primary == "forward":
        return "PF" if rpg >= 7.5 else "SF"
    # No usable position string: fall back to a pure stat heuristic.
    if apg >= 5.0:
        return "PG"
    if rpg >= 9.0:
        return "C"
    if rpg >= 6.0:
        return "PF"
    return "SF"


# ---- DB ---------------------------------------------------------------------
def init_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _cached_position(conn: sqlite3.Connection, player_id: int) -> tuple[str, str, float] | None:
    row = conn.execute(
        "SELECT position, raw, height_in FROM position_cache WHERE player_id = ?", (player_id,)
    ).fetchone()
    return (row[0], row[1], row[2] or 0.0) if row else None


def _cache_position(conn: sqlite3.Connection, player_id: int, position: str,
                    raw: str, height_in: float) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO position_cache(player_id, position, raw, height_in) VALUES (?,?,?,?)",
        (player_id, position, raw, height_in),
    )


# ---- Network build ----------------------------------------------------------
def resolve_position(conn, player_id, apg, rpg, sleep, _info_endpoint) -> tuple[str, str, float]:
    """Return (position, eligible_csv, height_in). From cache, else CommonPlayerInfo."""
    from app.positions import eligible_from_raw

    cached = _cached_position(conn, player_id)
    if cached:
        pos, raw, height = cached
        return pos, ",".join(eligible_from_raw(raw, pos)), height
    raw, height = "", 0.0
    try:
        info = _info_endpoint(player_id=player_id).get_data_frames()[0]
        raw = str(info.get("POSITION", [""])[0] or "")
        height = parse_height(info.get("HEIGHT", [""])[0])
    except Exception as e:
        print(f"      info lookup failed for {player_id}: {e}")
    pos = map_position(raw, apg, rpg)
    _cache_position(conn, player_id, pos, raw, height)
    conn.commit()
    time.sleep(sleep)
    return pos, ",".join(eligible_from_raw(raw, pos)), height


def build(since: int, out: Path, sleep: float = 0.6, limit: int | None = None,
          min_gp: int = 20, min_mpg: float = 12.0) -> None:
    try:
        from nba_api.stats.endpoints import (
            commonplayerinfo,
            leaguedashplayerstats,
        )
    except ImportError:
        raise SystemExit("nba_api not installed. Run: pip install nba_api pandas")

    conn = init_db(out)
    cur = conn.cursor()
    current_year = time.localtime().tm_year
    seasons = [f"{y}-{str(y + 1)[-2:]}" for y in range(since, current_year)]

    for season in seasons:
        cur.execute("SELECT COUNT(*) FROM players WHERE season = ?", (season,))
        if cur.fetchone()[0] > 0:
            print(f"[skip] {season} already present")
            continue

        print(f"[pull] {season} base + advanced ...")
        try:
            base = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season, per_mode_detailed="PerGame",
                measure_type_detailed_defense="Base",
            ).get_data_frames()[0]
            time.sleep(sleep)
            adv = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season, per_mode_detailed="PerGame",
                measure_type_detailed_defense="Advanced",
            ).get_data_frames()[0]
        except Exception as e:
            print(f"   error on {season}: {e}; backing off")
            time.sleep(5)
            continue

        pie_by_id = dict(zip(adv["PLAYER_ID"], adv["PIE"]))
        decade = season_to_decade(season)

        # Filter to rotation players, optionally cap for quick test runs.
        base = base[(base["GP"] >= min_gp) & (base["MIN"] >= min_mpg)]
        if limit:
            base = base.sort_values("MIN", ascending=False).head(limit)

        rows = 0
        for _, r in base.iterrows():
            pid = int(r["PLAYER_ID"])
            apg, rpg = float(r.get("AST", 0) or 0), float(r.get("REB", 0) or 0)
            position, eligible, height_in = resolve_position(
                conn, pid, apg, rpg, sleep, commonplayerinfo.CommonPlayerInfo
            )
            pie = pie_by_id.get(pid)
            pie = float(pie) if pie is not None else None
            try:
                cur.execute(
                    """INSERT OR IGNORE INTO players
                       (player_id, name, position, team, season, decade,
                        ppg, rpg, apg, spg, bpg, bpm, pie, eligible, height_in, gp, mpg)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        pid, r.get("PLAYER_NAME"), position,
                        full_team_name(r.get("TEAM_ABBREVIATION", "")),
                        season, decade,
                        float(r.get("PTS", 0) or 0), rpg, apg,
                        float(r.get("STL", 0) or 0), float(r.get("BLK", 0) or 0),
                        pie_to_bpm(pie), pie, eligible, height_in,
                        int(r.get("GP", 0) or 0), float(r.get("MIN", 0) or 0),
                    ),
                )
                rows += 1
            except Exception as e:
                print(f"   row error: {e}")
        conn.commit()
        print(f"   wrote {rows} players for {season}")
        time.sleep(sleep)

    conn.close()
    print("done.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=1997, help="first season start year")
    ap.add_argument("--out", type=Path, default=Path("app/data/players.db"))
    ap.add_argument("--sleep", type=float, default=0.6)
    ap.add_argument("--limit", type=int, default=None, help="cap players/season (quick test)")
    ap.add_argument("--min-gp", type=int, default=20)
    ap.add_argument("--min-mpg", type=float, default=12.0)
    args = ap.parse_args()
    build(args.since, args.out, args.sleep, args.limit, args.min_gp, args.min_mpg)
