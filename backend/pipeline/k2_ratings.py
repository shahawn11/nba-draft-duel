"""
NBA 2K ratings ingest (internal use; 2kratings.com is an independent fan site,
data is Take-Two IP -- used here only for internal rating calibration, not
redistributed).

Scrapes team pages for player OVERALL ratings, tagged by source so each can be
matched to a player's era:
  * All-Decade teams (1960s-2010s) -> a decade-appropriate 2K overall  [best match]
  * All-Time teams (per franchise) -> a peak/all-time overall
  * Current teams                  -> the current-season overall

Stored in k2_ratings(name, source, decade, overall). A (player, decade) pool
instance picks the best-matching 2K overall (same-decade > all-time > current).

Usage:  pip install beautifulsoup4
        python pipeline/k2_ratings.py            # scrape all-decade + all-time + current
Resumable: skips a (source) already present.
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
BASE = "https://www.2kratings.com/teams/"

FRANCHISES = [
    "atlanta-hawks", "boston-celtics", "brooklyn-nets", "charlotte-hornets",
    "chicago-bulls", "cleveland-cavaliers", "dallas-mavericks", "denver-nuggets",
    "detroit-pistons", "golden-state-warriors", "houston-rockets", "indiana-pacers",
    "los-angeles-clippers", "los-angeles-lakers", "memphis-grizzlies", "miami-heat",
    "milwaukee-bucks", "minnesota-timberwolves", "new-orleans-pelicans", "new-york-knicks",
    "oklahoma-city-thunder", "orlando-magic", "philadelphia-76ers", "phoenix-suns",
    "portland-trail-blazers", "sacramento-kings", "san-antonio-spurs", "toronto-raptors",
    "utah-jazz", "washington-wizards",
]
DECADES = ["1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS k2_ratings (
    name    TEXT NOT NULL,
    source  TEXT NOT NULL,   -- 'decade' | 'classic' | 'alltime' | 'current'
    decade  TEXT,            -- set for source in ('decade','classic')
    team    TEXT,            -- franchise / classic-team name
    season  TEXT,            -- set for source='classic' (e.g. '1995-96')
    overall INTEGER,
    three   INTEGER
);
"""


def _fetch(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def _parse_team(html: str) -> list[tuple[str, int]]:
    """[(player_name, overall)] from a 2K team page table."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[tuple[str, int]] = []
    table = soup.find("table")
    if not table or not table.tbody:
        return out

    def is_player_link(h):
        return (h and h.startswith("/") and "/teams/" not in h and "/lists/" not in h
                and "/countries/" not in h and h not in ("/", "#"))

    for tr in table.tbody.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        name = None
        for a in tr.find_all("a", href=is_player_link):
            txt = a.get_text(strip=True)
            if txt:
                name = txt
                break
        if not name:
            continue
        ovr = None
        for cdl in cells:
            t = cdl.get_text(strip=True)
            if t.isdigit() and 40 <= int(t) <= 99:   # first 2-digit cell = OVR
                ovr = int(t)
                break
        if ovr is not None:
            out.append((name, ovr))
    return out


def build(db_path: Path, sleep: float = 2.5) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    cur = conn.cursor()
    jobs: list[tuple[str, str, str | None, str]] = []
    for d in DECADES:
        jobs.append((f"{BASE}all-decade-{d}-all-stars", "decade", d, d))
    for f in FRANCHISES:
        jobs.append((f"{BASE}all-time-{f}", "alltime", None, f))
        jobs.append((f"{BASE}{f}", "current", None, f))
    total = 0
    for url, source, decade, team in jobs:
        if cur.execute("SELECT 1 FROM k2_ratings WHERE source=? AND team=? LIMIT 1",
                       (source, team)).fetchone():
            print(f"[skip] {source}:{team}"); continue
        try:
            rows = _parse_team(_fetch(url))
        except Exception as e:
            print(f"   {source}:{team} failed: {repr(e)[:80]}; backing off"); time.sleep(6); continue
        w = 0
        for name, ovr in rows:
            cur.execute("INSERT OR IGNORE INTO k2_ratings(name, source, decade, team, overall) "
                        "VALUES (?,?,?,?,?)", (name, source, decade, team, ovr))
            w += cur.rowcount
        conn.commit(); total += w
        print(f"[ok] {source}:{team} -> {w}")
        time.sleep(sleep)
    conn.close()
    print(f"done. {total} 2K overall rows.")


import re


def _parse_team_full(html: str) -> list[tuple[str, int, int | None]]:
    """[(name, overall, three_pt)] from a saved 2K team page.
    Pages may have MULTIPLE tables (main 15-man roster + extra-legends table +
    a 'Classic Teams' table). We scan ALL tables; non-player rows (team links)
    are filtered by is_player_link. Table columns: #, Player, OVR, 3PT, DNK."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[tuple[str, int, int | None]] = []
    seen: set[str] = set()

    def is_player_link(h):
        if not h:
            return False
        h = h.replace("https://www.2kratings.com", "").replace("http://www.2kratings.com", "")
        return (h.startswith("/") and "/teams/" not in h and "/lists/" not in h
                and "/countries/" not in h and "/wnba" not in h and h not in ("/", "#"))

    for table in soup.find_all("table"):
        body = table.tbody or table
        for tr in body.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            name = None
            for a in tr.find_all("a", href=is_player_link):
                txt = a.get_text(strip=True)
                if txt:
                    name = txt
                    break
            if not name:
                continue
            nums = [int(c.get_text(strip=True)) for c in cells
                    if c.get_text(strip=True).isdigit() and 0 <= int(c.get_text(strip=True)) <= 99]
            ovr = next((n for n in nums if 40 <= n <= 99), None)
            if ovr is None:
                continue
            if name in seen:          # keep first (highest table) occurrence
                continue
            seen.add(name)
            rest = nums[nums.index(ovr) + 1:]
            three = rest[0] if rest else None
            out.append((name, ovr, three))
    return out


def _season_to_decade(start_year: int) -> str:
    return f"{(start_year // 10) * 10}s"


def _classify(html: str):
    """Return (source, decade, season, team) from the page <title>/<h1>.
    source in {'decade','classic','alltime','current'}."""
    m = re.search(r"<title>\s*(.*?)\s*(?:\||</title>)", html, re.I | re.S)
    title = (m.group(1) if m else "").strip()

    # All-Decade 1980s All-Stars
    md = re.search(r"All-Decade\s+(\d{4}s)", title)
    if md:
        return ("decade", md.group(1), None, None)

    # Classic season team: "1992-93 Chicago Bulls ..."
    mc = re.match(r"(\d{4})-(\d{2,4})\s+(.+?)\s+NBA\s*2K", title)
    if mc:
        yr = int(mc.group(1))
        return ("classic", _season_to_decade(yr), f"{mc.group(1)}-{mc.group(2)}", mc.group(3).strip())

    # All-Time {franchise}: "All-Time Lakers ..."
    ma = re.search(r"All-Time\s+(.+?)\s+NBA\s*2K", title)
    if ma:
        return ("alltime", None, None, ma.group(1).strip())

    # Current team: "Los Angeles Lakers NBA 2K26 Roster"
    mt = re.match(r"(.+?)\s+NBA\s*2K", title)
    if mt:
        return ("current", None, None, mt.group(1).strip())

    return (None, None, None, None)


def ingest_dir(db_path: Path, src_dir: Path) -> None:
    """Parse saved 2K .html roster pages (all-decade / classic / all-time / current)."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS k2_ratings")   # rebuild with current schema
    conn.executescript(SCHEMA)
    total = 0
    by_source: dict[str, int] = {}
    for f in sorted(src_dir.glob("*.html")):
        html = f.read_text(encoding="utf-8", errors="replace")
        if "Just a moment" in html or "sgcaptcha" in html:
            print(f"[skip] {f.name[:45]}: Cloudflare challenge stub"); continue
        source, decade, season, team = _classify(html)
        if not source:
            print(f"[skip] {f.name[:45]}: unclassified"); continue
        rows = _parse_team_full(html)
        w = 0
        for name, ovr, three in rows:
            cur.execute(
                "INSERT INTO k2_ratings(name, source, decade, team, season, overall, three) "
                "VALUES (?,?,?,?,?,?,?)", (name, source, decade, team, season, ovr, three))
            w += 1
        conn.commit(); total += w
        by_source[source] = by_source.get(source, 0) + w
        tag = season or decade or team or "?"
        print(f"[ok] {source:>8} {tag:>14} ({f.name[:34]}...) -> {w}")
    print(f"\ndone. {total} rows loaded by source: {by_source}")
    print(f"k2_ratings total: {cur.execute('SELECT COUNT(*) FROM k2_ratings').fetchone()[0]}")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=Path("app/data/players.db"))
    ap.add_argument("--sleep", type=float, default=2.5)
    ap.add_argument("--from-dir", type=Path, default=None,
                    help="parse saved .html roster pages from this dir instead of scraping")
    args = ap.parse_args()
    if args.from_dir:
        ingest_dir(args.db, args.from_dir)
    else:
        build(args.db, args.sleep)
