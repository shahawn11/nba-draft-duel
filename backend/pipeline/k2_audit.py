"""Audit every pool combo: resolved (post-cap) 2K vs peak-season expectation f(peakBBRef).
Flags biggest over/under-rated combos given peak stats."""
from __future__ import annotations
import sqlite3, importlib.util, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
def load(n, fn):
    s = importlib.util.spec_from_file_location(n, HERE / fn); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
kr = load("kr", "k2_resolve.py"); cal = load("cal", "k2_calibrate.py")


def peak_stats(cur, name, dec, team):
    rows = cur.execute("SELECT ppg,bpm,gp,season FROM players WHERE name=? AND decade=? AND team=?",
                       (name, dec, team)).fetchall()
    q = [r for r in rows if (r[2] or 0) >= 25] or rows
    if not q:
        return (0, 0, "")
    b = max(q, key=lambda r: (r[1] or 0))
    return (b[0] or 0, b[1] or 0, b[3])


def main():
    conn = sqlite3.connect(HERE.parent / "app/data/players.db"); cur = conn.cursor()
    idx = kr._k2_index(cur)
    from app import dataset, scoring
    pools = dataset.historical_pool()
    f, mono = cal.build_f(kr, idx, pools, scoring, cur)

    audit = []
    for key, players in pools.items():
        dec, team = key.split("|", 1)
        for p in players:
            pk = cal.peak_rating(p, cur, scoring)
            ovr, src = kr.resolve(idx, p.name, dec, team)
            capv = cal.era_cap(ovr, src, pk, f)
            exp = round(f(pk))
            audit.append((capv - exp, p.name, dec, team, pk, capv, exp, src))

    over = sorted(audit, reverse=True)[:22]
    under = sorted(audit)[:22]
    print("=== OVER-rated vs peak (resolved 2K >> peak warrants) ===")
    for g, n, d, t, pk, ov, exp, src in over:
        ppg, bpm, ssn = peak_stats(cur, n, d, t)
        print(f"  +{g:>2}  2K {ov} vs exp {exp}  {d} {t:<20} {n:<20} peak {ssn} {ppg:.0f}p/{bpm:.1f}bpm [{src}]")
    print("\n=== UNDER-rated vs peak (resolved 2K << peak warrants) ===")
    for g, n, d, t, pk, ov, exp, src in under:
        ppg, bpm, ssn = peak_stats(cur, n, d, t)
        print(f"  {g:>3}  2K {ov} vs exp {exp}  {d} {t:<20} {n:<20} peak {ssn} {ppg:.0f}p/{bpm:.1f}bpm [{src}]")
    conn.close()


if __name__ == "__main__":
    main()
