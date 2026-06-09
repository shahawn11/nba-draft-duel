"""
Basketball-Reference advanced-stats ingest (internal use).

Pulls per-season Advanced tables (PER, TS%, USG%, WS, OBPM/DBPM/BPM, VORP) from
basketball-reference.com and stores one row per (player, season) -- the
minutes-weighted combined row for players who were traded mid-season. This
gives us a REAL historical impact metric (BPM/VORP back to 1973-74), far better
than the PIE->BPM proxy (1996+ only) and the hand-set pre-1996 legend values.

Data is for INTERNAL rating computation only (not redistributed).

Usage:
    pip install beautifulsoup4
    python pipeline/bbref_advanced.py --from 1974 --to 2026
Resumable: skips seasons already present. Gentle rate limit (~3s/page).
"""
from __future__ import annotations

import argparse
import sqlite3
import time
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

SCHEMA = """
CREATE TABLE IF NOT EXISTS bbref_advanced (
    name   TEXT NOT NULL,
    season TEXT NOT NULL,
    team   TEXT,
    per    REAL, ts_pct REAL, usg_pct REAL,
    ws     REAL, ws48 REAL,
    obpm   REAL, dbpm REAL, bpm REAL, vorp REAL,
    UNIQUE(name, season)
);
"""


def _season_label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def _f(s):
    try:
        return float(s) if s not in (None, "") else None
    except ValueError:
        return None


def _fetch(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def _stat(tr, stat):
    c = tr.find(["td", "th"], attrs={"data-stat": stat})
    return c.get_text(strip=True) if c else None


def _parse_season(html: str) -> dict[str, dict]:
    """Return {player_name: row dict} using the combined (multi-team) line when present."""
    soup = BeautifulSoup(html, "html.parser")
    tbl = soup.find("table", id="advanced") or soup.find("table", id="advanced_stats")
    if not tbl or not tbl.tbody:
        return {}
    out: dict[str, dict] = {}
    for tr in tbl.tbody.find_all("tr"):
        cls = tr.get("class") or []
        if "thead" in cls:
            continue
        name = _stat(tr, "name_display") or _stat(tr, "player")
        if not name:
            continue
        team = _stat(tr, "team_name_abbr") or _stat(tr, "team_id") or ""
        row = {
            "team": team,
            "per": _f(_stat(tr, "per")), "ts_pct": _f(_stat(tr, "ts_pct")),
            "usg_pct": _f(_stat(tr, "usg_pct")), "ws": _f(_stat(tr, "ws")),
            "ws48": _f(_stat(tr, "ws_per_48")), "obpm": _f(_stat(tr, "obpm")),
            "dbpm": _f(_stat(tr, "dbpm")), "bpm": _f(_stat(tr, "bpm")),
            "vorp": _f(_stat(tr, "vorp")),
        }
        # Prefer the combined "2TM"/"3TM"/... row (whole-season value) over team stints.
        prev = out.get(name)
        is_combined = team.upper().endswith("TM")
        if prev is None or is_combined:
            out[name] = row
    return out


def build(db_path: Path, from_year: int, to_year: int, sleep: float = 3.0) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    cur = conn.cursor()
    total = 0
    for end_year in range(from_year, to_year + 1):
        season = _season_label(end_year)
        if cur.execute("SELECT 1 FROM bbref_advanced WHERE season=? LIMIT 1", (season,)).fetchone():
            print(f"[skip] {season} already present")
            continue
        url = f"https://www.basketball-reference.com/leagues/NBA_{end_year}_advanced.html"
        try:
            rows = _parse_season(_fetch(url))
        except Exception as e:
            print(f"   {season}: fetch/parse failed: {repr(e)[:100]}; backing off")
            time.sleep(8)
            continue
        wrote = 0
        for name, r in rows.items():
            cur.execute(
                """INSERT OR IGNORE INTO bbref_advanced
                   (name, season, team, per, ts_pct, usg_pct, ws, ws48, obpm, dbpm, bpm, vorp)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (name, season, r["team"], r["per"], r["ts_pct"], r["usg_pct"], r["ws"],
                 r["ws48"], r["obpm"], r["dbpm"], r["bpm"], r["vorp"]),
            )
            wrote += cur.rowcount
        conn.commit()
        total += wrote
        print(f"[ok] {season}: {wrote} players")
        time.sleep(sleep)
    conn.close()
    print(f"done. wrote {total} player-season advanced rows.")


def _parse_pergame_threes(html: str) -> dict[str, dict]:
    """{player: {three_pa, three_pct}} from a Per Game page (combined row)."""
    soup = BeautifulSoup(html, "html.parser")
    tbl = soup.find("table", id="per_game_stats") or soup.find("table", id="per_game")
    if not tbl or not tbl.tbody:
        return {}
    out: dict[str, dict] = {}
    for tr in tbl.tbody.find_all("tr"):
        if "thead" in (tr.get("class") or []):
            continue
        name = _stat(tr, "name_display") or _stat(tr, "player")
        if not name:
            continue
        team = _stat(tr, "team_name_abbr") or _stat(tr, "team_id") or ""
        row = {"three_pa": _f(_stat(tr, "fg3a_per_g")), "three_pct": _f(_stat(tr, "fg3_pct"))}
        if name not in out or team.upper().endswith("TM"):
            out[name] = row
    return out


def build_threes(db_path: Path, from_year: int = 1980, to_year: int = 2026, sleep: float = 3.0) -> None:
    conn = sqlite3.connect(db_path)
    if "three_pa" not in {r[1] for r in conn.execute("PRAGMA table_info(bbref_advanced)")}:
        conn.execute("ALTER TABLE bbref_advanced ADD COLUMN three_pa REAL")
        conn.execute("ALTER TABLE bbref_advanced ADD COLUMN three_pct REAL")
    cur = conn.cursor()
    total = 0
    for end_year in range(from_year, to_year + 1):
        season = _season_label(end_year)
        if cur.execute("SELECT 1 FROM bbref_advanced WHERE season=? AND three_pa IS NOT NULL LIMIT 1",
                       (season,)).fetchone():
            print(f"[skip] threes {season}"); continue
        try:
            rows = _parse_pergame_threes(_fetch(
                f"https://www.basketball-reference.com/leagues/NBA_{end_year}_per_game.html"))
        except Exception as e:
            print(f"   threes {season}: {repr(e)[:80]}; backing off"); time.sleep(8); continue
        w = 0
        for name, r in rows.items():
            cur.execute("UPDATE bbref_advanced SET three_pa=?, three_pct=? WHERE name=? AND season=?",
                        (r["three_pa"], r["three_pct"], name, season))
            w += cur.rowcount
        conn.commit(); total += w
        print(f"[ok] threes {season}: {w}")
        time.sleep(sleep)
    conn.close()
    print(f"done. set 3PT on {total} rows.")


def _norm(s: str) -> str:
    """Accent/punctuation-insensitive name key (nba_api is ASCII, bbref accented)."""
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.replace(".", "").replace("'", "").lower().strip()


def apply_to_players(db_path: Path) -> None:
    """Overwrite players.bpm with the real BBRef BPM and set players.ts_pct from
    BBRef where (name, season) match (accent-insensitive). Players without a
    match (pre-1974, name variants) keep their existing bpm / null ts_pct. Makes
    the rating's impact half a real metric and enables efficiency-aware scoring."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    have = {r[1] for r in conn.execute("PRAGMA table_info(players)")}
    if "ts_pct" not in have:
        conn.execute("ALTER TABLE players ADD COLUMN ts_pct REAL")
    if "dbpm" not in have:
        conn.execute("ALTER TABLE players ADD COLUMN dbpm REAL")
    if "three_pa" not in have:
        conn.execute("ALTER TABLE players ADD COLUMN three_pa REAL")
        conn.execute("ALTER TABLE players ADD COLUMN three_pct REAL")
    bcols = {r[1] for r in conn.execute("PRAGMA table_info(bbref_advanced)")}
    has3 = "three_pa" in bcols
    sel = "name, season, bpm, ts_pct, dbpm" + (", three_pa, three_pct" if has3 else "")
    bb = {(_norm(r["name"]), r["season"]): r for r in conn.execute(f"SELECT {sel} FROM bbref_advanced")}
    bpm_n = ts_n = db_n = th_n = 0
    for r in conn.execute("SELECT id, name, season FROM players WHERE season >= '1973'").fetchall():
        m = bb.get((_norm(r["name"]), r["season"]))
        if not m:
            continue
        if m["bpm"] is not None:
            conn.execute("UPDATE players SET bpm=? WHERE id=?", (m["bpm"], r["id"])); bpm_n += 1
        if m["ts_pct"] is not None:
            conn.execute("UPDATE players SET ts_pct=? WHERE id=?", (m["ts_pct"], r["id"])); ts_n += 1
        if m["dbpm"] is not None:
            conn.execute("UPDATE players SET dbpm=? WHERE id=?", (m["dbpm"], r["id"])); db_n += 1
        if has3 and m["three_pa"] is not None:
            conn.execute("UPDATE players SET three_pa=?, three_pct=? WHERE id=?",
                         (m["three_pa"], m["three_pct"], r["id"])); th_n += 1
    conn.commit()
    conn.close()
    print(f"applied real BBRef BPM to {bpm_n} rows, TS% {ts_n}, DBPM {db_n}, 3PT {th_n}.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=Path("app/data/players.db"))
    ap.add_argument("--from", dest="from_year", type=int, default=1974)
    ap.add_argument("--to", dest="to_year", type=int, default=2026)
    ap.add_argument("--sleep", type=float, default=3.0)
    ap.add_argument("--apply", action="store_true",
                    help="only update players.bpm from the already-pulled bbref_advanced table")
    ap.add_argument("--threes", action="store_true",
                    help="pull per-game 3PT (3PA, 3P%) into bbref_advanced")
    args = ap.parse_args()
    if args.threes:
        build_threes(args.db, max(args.from_year, 1980), args.to_year, args.sleep)
    elif args.apply:
        apply_to_players(args.db)
    else:
        build(args.db, args.from_year, args.to_year, args.sleep)
