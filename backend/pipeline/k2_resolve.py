"""
Resolve a 2K overall per (player, decade) from k2_ratings, by precedence:
    classic peak  ->  all-time  ->  all-decade  ->  (none: fall back to Peak+BBRef)
Current-team ratings are used ONLY for 2020s peak (and, separately, offline rosters).

Also reports pool (player, decade, team) combos that have NO 2K match (BBRef-only),
and combos missing BBRef too (no NBA data at all).

Usage:  python pipeline/k2_resolve.py            # prints coverage + missing report
        python pipeline/k2_resolve.py --resolved # also dump resolved 2K-per-decade
"""
from __future__ import annotations

import argparse
import sqlite3
import unicodedata
from pathlib import Path

# 2K uses some nicknames / spellings our dataset doesn't. Map 2K-name -> our-name
# (normalized comparison still applies on top of this).
ALIAS = {
    "penny hardaway": "anfernee hardaway",
    "metta world peace": "ron artest",
    "nene": "nene hilario",
    "clifford robinson": "cliff robinson",
}


def norm(s: str) -> str:
    """lowercase, strip accents, normalize apostrophes, drop periods/jr/sr."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("\u2019", "'").replace("`", "'").replace(".", "").strip()
    for suf in (" jr", " sr", " iii", " ii"):
        if s.endswith(suf):
            s = s[: -len(suf)].strip()
    return s


def _k2_index(cur) -> dict:
    """name(normalized) -> {classic:{decade:max}, alltime:max, decade:{dec:ovr}, current:max, curated:ovr}."""
    idx: dict[str, dict] = {}
    for name, source, decade, overall in cur.execute(
        "SELECT name, source, decade, overall FROM k2_ratings"
    ):
        key = ALIAS.get(norm(name), norm(name))
        d = idx.setdefault(key, {"classic": {}, "alltime": 0, "decade": {}, "current": 0, "curated": 0})
        if source == "classic" and decade:
            d["classic"][decade] = max(d["classic"].get(decade, 0), overall or 0)
        elif source == "alltime":
            d["alltime"] = max(d["alltime"], overall or 0)
        elif source == "decade" and decade:
            d["decade"][decade] = max(d["decade"].get(decade, 0), overall or 0)
        elif source == "current":
            d["current"] = max(d["current"], overall or 0)
    # merge curated (web-searched) overalls for players absent from scraped pages
    cpath = Path(__file__).resolve().parent / "k2_curated.json"
    if cpath.exists():
        import json
        for name, ovr in json.loads(cpath.read_text()).items():
            if name.startswith("_") or not isinstance(ovr, int):
                continue
            key = ALIAS.get(norm(name), norm(name))
            d = idx.setdefault(key, {"classic": {}, "alltime": 0, "decade": {}, "current": 0, "curated": 0})
            d["curated"] = max(d.get("curated", 0), ovr)
    # merge calibrated (BBRef->2K) estimates, keyed "name|decade|team"
    idx["_calibrated"] = {}
    kpath = Path(__file__).resolve().parent / "k2_calibrated.json"
    if kpath.exists():
        import json
        for combo, ovr in json.loads(kpath.read_text()).items():
            idx["_calibrated"][combo] = ovr
    # explicit per-combo overrides, keyed "name|decade|team" (highest precedence)
    idx["_override"] = {}
    opath = Path(__file__).resolve().parent / "k2_overrides.json"
    if opath.exists():
        import json
        for combo, ovr in json.loads(opath.read_text()).items():
            if not combo.startswith("_") and isinstance(ovr, int):
                idx["_override"][combo] = ovr
    return idx


def era_correct_raw(idx: dict, name: str, decade: str):
    """Raw value from ERA-CORRECT sources (classic/all-decade/current) for f-learning,
    independent of max-card resolution. Returns (value, source) or (None, None)."""
    d = idx.get(ALIAS.get(norm(name), norm(name)))
    if not d:
        return (None, None)
    cands = []
    if d["classic"].get(decade):
        cands.append((d["classic"][decade], "classic"))
    if d["decade"].get(decade):
        cands.append((d["decade"][decade], "all-decade"))
    if decade == "2020s" and d["current"]:
        cands.append((d["current"], "current"))
    return max(cands) if cands else (None, None)


def resolve(idx: dict, name: str, decade: str, team: str | None = None):
    """Resolve 2K via: explicit override -> MAX card across all tiers -> calibrated.
    (Era-cap is applied separately by callers that have the combo's peak BBRef.)"""
    if team is not None:
        ov = idx.get("_override", {}).get(f"{name}|{decade}|{team}")
        if ov:
            return (ov, "override")
    d = idx.get(ALIAS.get(norm(name), norm(name)))
    if d:
        cards = []
        if d["classic"].get(decade):
            cards.append((d["classic"][decade], "classic"))
        if d["alltime"]:
            cards.append((d["alltime"], "alltime"))
        if d["decade"].get(decade):
            cards.append((d["decade"][decade], "all-decade"))
        if decade == "2020s" and d["current"]:
            cards.append((d["current"], "current"))
        if d.get("curated"):
            cards.append((d["curated"], "curated"))
        if cards:
            return max(cards)   # best available card; era-cap pulls down off-peak combos
    if team is not None:
        est = idx.get("_calibrated", {}).get(f"{name}|{decade}|{team}")
        if est:
            return (est, "calibrated")
    return (None, None)


def main(db_path: Path, dump_resolved: bool) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    idx = _k2_index(cur)

    from pathlib import Path as _P
    import sys
    sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
    from app import dataset
    pools = dataset.historical_pool()
    combos = []
    for key, players in pools.items():
        decade, team = key.split("|", 1)
        for p in players:
            combos.append((p.name, decade, team, getattr(p, "bpm", None)))

    matched, no2k, nodata = [], [], []
    src_counts: dict[str, int] = {}
    for name, decade, team, bpm in combos:
        ovr, src = resolve(idx, name, decade, team)
        if ovr is not None:
            matched.append((name, decade, team, ovr, src))
            src_counts[src] = src_counts.get(src, 0) + 1
        else:
            no2k.append((name, decade, team))
            if bpm is None:
                nodata.append((name, decade, team))

    total = len(combos) or 1
    print(f"draftable pool combos: {len(combos)}  ({len(pools)} pools)")
    print(f"  2K-matched:         {len(matched)} ({100*len(matched)//total}%)  by source: {src_counts}")
    print(f"  no 2K (BBRef-only): {len(no2k)} ({100*len(no2k)//total}%)")
    print(f"  NO NBA data at all: {len(nodata)} (no 2K AND no BBRef bpm)")

    print("\n--- combos with NO 2K match (will use Peak+BBRef fallback) ---")
    for name, decade, team in sorted(no2k):
        flag = "  <-- NO BBRef EITHER" if (name, decade, team) in nodata else ""
        print(f"  {decade}  {team:<26} {name}{flag}")

    if dump_resolved:
        print("\n--- resolved 2K-per-decade (matched), top 40 by overall ---")
        for name, decade, team, ovr, src in sorted(matched, key=lambda x: -x[3])[:40]:
            print(f"  {ovr:>3} {src:<10} {decade} {team:<24} {name}")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=Path("app/data/players.db"))
    ap.add_argument("--resolved", action="store_true")
    args = ap.parse_args()
    main(args.db, args.resolved)
