"""
Validate resolved 2K ratings AFTER era-correction:
  - calibration f learned from ERA-CORRECT sources + low floor (k2_calibrate.build_f)
  - era_cap applied to decade-agnostic all-time/curated values
Reports remaining "high 2K but low decade-BBRef" cases and the before/after of capping.
"""
from __future__ import annotations
import sqlite3, importlib.util, sys, statistics
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

def _load(name, fn):
    s = importlib.util.spec_from_file_location(name, HERE / fn)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
kr = _load("kr", "k2_resolve.py")
cal = _load("cal", "k2_calibrate.py")


def main():
    conn = sqlite3.connect(HERE.parent / "app/data/players.db"); cur = conn.cursor()
    idx = kr._k2_index(cur)
    from app import dataset, scoring
    pools = dataset.historical_pool()
    f, mono = cal.build_f(kr, idx, pools, scoring, cur)

    rows = []
    capped = []
    for key, players in pools.items():
        dec, team = key.split("|", 1)
        for p in players:
            bb = cal.peak_rating(p, cur, scoring)
            ovr, src = kr.resolve(idx, p.name, dec, team)
            capv = cal.era_cap(ovr, src, bb, f)
            if capv != ovr:
                capped.append((ovr - capv, p.name, dec, team, bb, ovr, capv))
            rows.append((p.name, dec, team, bb, capv, src))

    badhi = [r for r in rows if r[4] >= 80 and r[3] < 35]
    print(f"After era-cap + new floor:")
    print(f"  combos with capped (lowered) 2K: {len(capped)}")
    print(f"  combos 2K>=80 with peak BBRef<35: {len(badhi)} (was ~many; 2K floor is high by design)")

    capped.sort(reverse=True)
    print("\nTop era-cap corrections (biggest drops):")
    for drop, n, d, t, bb, ovr, capv in capped[:18]:
        print(f"   {ovr}->{capv} (-{drop})  {d} {t:<22} {n} (BBRef {bb:.0f})")

    # distribution after cap
    bysrc = {}
    for n, d, t, bb, capv, src in rows:
        bysrc.setdefault(src, []).append(capv)
    print("\nResolved 2K (post-cap) by source  min/med/max:")
    for src, v in sorted(bysrc.items()):
        print(f"  {src:<11} n={len(v):>4}  min {min(v)}  med {int(statistics.median(v))}  max {max(v)}")
    conn.close()


if __name__ == "__main__":
    main()
