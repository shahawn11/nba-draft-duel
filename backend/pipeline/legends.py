"""
Pre-1996 legends pull.

stats.nba.com's league-wide endpoint (LeagueDashPlayerStats) returns nothing
before the 1996-97 season, and the PIE impact metric doesn't exist pre-1996 at
all. But the PER-PLAYER endpoint (PlayerCareerStats) reaches every era, so we
can still pull real per-season Base stats (PTS/REB/AST/STL/BLK) for the
legends whose primes predate 1996.

Because there's no PIE before 1996, the impact metric (`bpm` column) is
HAND-SET per player here, on the same clamped scale the scoring engine uses
(roughly -6..+13; league-average ~0, MVP-level ~+9..+11). These are caliber
estimates and are meant to be tuned.

Rows are written into the same `players` table as the main pipeline, scoped to
seasons BEFORE 1996-97, so they merge into the existing decade x team pools and
flow through the peak-season / decade-average blend automatically (e.g. they
give 1990s Hakeem his real 1993-95 championship peak).

Usage:
    pip install nba_api pandas
    python pipeline/legends.py --out app/data/players.db
    python pipeline/legends.py --only "Hakeem Olajuwon,Patrick Ewing"   # subset

Resumable: an existing (name, season, team) row is left untouched.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import build_dataset as bd  # sibling module: schema + shared helpers

# --- Curated legends -> hand-set impact (BPM-scale, ~ -6..+13) --------------
# Impact reflects era/peak caliber (PIE is unavailable pre-1996). Tunable.
LEGENDS: dict[str, float] = {
    # All-time inner circle
    "Michael Jordan": 11.0,
    "Magic Johnson": 9.5,
    "Larry Bird": 9.0,
    "Hakeem Olajuwon": 9.0,
    "David Robinson": 9.0,
    "Charles Barkley": 9.0,
    "Karl Malone": 8.5,
    "Kareem Abdul-Jabbar": 8.0,
    "Moses Malone": 8.0,
    "Shaquille O'Neal": 9.0,
    "John Stockton": 7.5,
    "Scottie Pippen": 7.0,
    # Stars
    "Patrick Ewing": 6.5,
    "Clyde Drexler": 7.0,
    "Isiah Thomas": 6.5,
    "Dominique Wilkins": 6.0,
    "Gary Payton": 6.5,
    "Reggie Miller": 5.5,
    "Alonzo Mourning": 6.0,
    "Dikembe Mutombo": 5.5,
    "Chris Webber": 6.0,
    "Shawn Kemp": 5.5,
    "Anfernee Hardaway": 6.0,
    "Tim Hardaway": 5.5,
    "Mitch Richmond": 5.5,
    "Chris Mullin": 5.5,
    "Kevin Johnson": 5.5,
    "Grant Hill": 6.5,
    "Jason Kidd": 6.5,
    "Glen Rice": 4.5,
    "Larry Johnson": 4.5,
    # 1980s greats
    "James Worthy": 5.5,
    "Kevin McHale": 6.0,
    "Robert Parish": 4.5,
    "Dennis Rodman": 4.5,
    "Adrian Dantley": 5.5,
    "Bernard King": 6.0,
    "Sidney Moncrief": 5.5,
    "Mark Price": 5.0,
    "Detlef Schrempf": 4.5,
    "Terry Cummings": 4.5,
    "Joe Dumars": 5.0,
    "Dennis Johnson": 4.5,
    "Kevin Willis": 4.0,
    "Mark Aguirre": 4.5,
    # 1970s-80s legends present in the curated seed pools
    "Julius Erving": 7.5,
    "George Gervin": 6.5,
    "Bob McAdoo": 6.0,
    "Dave Cowens": 5.5,
    "Walt Frazier": 6.0,
    "Willis Reed": 5.5,
    "Bill Walton": 6.0,
    "Bob Lanier": 5.5,
    "Elvin Hayes": 5.5,
    "Pete Maravich": 5.5,
    "Artis Gilmore": 5.5,
    "Dan Issel": 5.0,
    "Alex English": 5.5,
    "Marques Johnson": 5.0,
    "Jack Sikma": 4.5,
    "Bill Laimbeer": 4.0,
    "Norm Nixon": 4.5,
    "Maurice Lucas": 4.5,
    "Bob Dandridge": 4.5,
    "Maurice Cheeks": 4.5,
    "Andrew Toney": 4.5,
    "Ralph Sampson": 5.5,
    "Billy Cunningham": 6.0,
    "Earl Monroe": 5.5,
    "Spencer Haywood": 5.5,
    "Nate Archibald": 5.5,
    # 1980s San Antonio Spurs roster (so a Gervin-era pool forms with real data)
    "Mike Mitchell": 4.0,
    "Johnny Moore": 3.5,
    "Alvin Robertson": 4.5,
    "Gene Banks": 3.5,
    "Mark Olberding": 3.0,
    "Larry Kenon": 4.0,
    "Edgar Jones": 3.0,
    "Jon Sundvold": 3.0,
    "Steve Johnson": 3.5,
    "Walter Berry": 3.0,
    # 1970s Atlanta Hawks roster (Maravich-era pool)
    "Lou Hudson": 4.5,
    "Walt Bellamy": 4.0,
    "Bill Bridges": 4.0,
    "John Drew": 4.5,
    "Dan Roundfield": 4.5,
    "Eddie Johnson": 3.5,
    "Tom Henderson": 3.0,
    "Charlie Criss": 3.0,
    "Steve Hawes": 3.0,
    "Armond Hill": 3.0,
    # Denver Nuggets / misc legends
    "David Thompson": 6.5,
    "Dan Issel": 5.0,
    "Bobby Jones": 4.5,
}

CUTOFF_START_YEAR = 1996   # only write seasons that START before this
MIN_GP = 15                # skip tiny injury/cameo stints


def _season_start_year(season_id: str) -> int:
    try:
        return int(str(season_id).split("-")[0])
    except (ValueError, AttributeError):
        return 9999


def _resolve_id(name: str):
    from nba_api.stats.static import players as static_players
    exact = [p for p in static_players.find_players_by_full_name(name)
             if p["full_name"].lower() == name.lower()]
    pool = exact or static_players.find_players_by_full_name(name)
    return pool[0]["id"] if pool else None


def build_legends(out: Path, sleep: float = 0.5, only: set[str] | None = None) -> None:
    try:
        from nba_api.stats.endpoints import playercareerstats, commonplayerinfo
    except ImportError:
        raise SystemExit("nba_api not installed. Run: pip install nba_api pandas")

    conn = bd.init_db(out)
    cur = conn.cursor()
    names = [n for n in LEGENDS if not only or n in only]
    total_rows = 0

    for name in names:
        impact = LEGENDS[name]
        pid = _resolve_id(name)
        if not pid:
            print(f"[skip] {name}: no player_id match")
            continue
        try:
            df = playercareerstats.PlayerCareerStats(
                player_id=pid, per_mode36="PerGame", timeout=30,
            ).get_data_frames()[0]
            time.sleep(sleep)
        except Exception as e:
            print(f"   {name}: career pull failed: {repr(e)[:100]}; backing off")
            time.sleep(3)
            continue

        pre = df[df["SEASON_ID"].map(_season_start_year) < CUTOFF_START_YEAR]
        pre = pre[(pre["TEAM_ABBREVIATION"].notna()) & (pre["TEAM_ABBREVIATION"] != "TOT")]
        if pre.empty:
            print(f"[none] {name}: no pre-{CUTOFF_START_YEAR} seasons")
            continue

        # Representative apg/rpg (best-scoring pre-96 season) for the position heuristic.
        rep = pre.sort_values("PTS", ascending=False).iloc[0]
        position, eligible, height_in = bd.resolve_position(
            conn, pid, float(rep.get("AST", 0) or 0), float(rep.get("REB", 0) or 0),
            sleep, commonplayerinfo.CommonPlayerInfo,
        )

        wrote = 0
        for _, r in pre.iterrows():
            if int(r.get("GP", 0) or 0) < MIN_GP:
                continue
            season = str(r["SEASON_ID"])
            team_full = bd.full_team_name(r.get("TEAM_ABBREVIATION", ""))
            try:
                cur.execute(
                    """INSERT OR IGNORE INTO players
                       (player_id, name, position, team, season, decade,
                        ppg, rpg, apg, spg, bpg, bpm, pie, eligible, height_in, gp, mpg)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        pid, name, position, team_full, season,
                        bd.season_to_decade(season),
                        float(r.get("PTS", 0) or 0), float(r.get("REB", 0) or 0),
                        float(r.get("AST", 0) or 0), float(r.get("STL", 0) or 0),
                        float(r.get("BLK", 0) or 0),
                        impact, None, eligible, height_in,
                        int(r.get("GP", 0) or 0), float(r.get("MIN", 0) or 0),
                    ),
                )
                wrote += cur.rowcount
            except Exception as e:
                print(f"   {name} {season} row error: {repr(e)[:80]}")
        conn.commit()
        total_rows += wrote
        print(f"[ok] {name:24s} impact {impact:+.1f}  pos {position}  "
              f"pre-96 seasons written: {wrote}")

    conn.close()
    print(f"done. wrote {total_rows} legend season-rows for {len(names)} players.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("app/data/players.db"))
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--only", type=str, default=None,
                    help="comma-separated subset of legend names")
    args = ap.parse_args()
    only = {s.strip() for s in args.only.split(",")} if args.only else None
    build_legends(args.out, args.sleep, only)
