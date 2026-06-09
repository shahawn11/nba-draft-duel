"""
Final overall = 0.5*BBRef_teamdecade + 0.5*K2_gamescale, on the game's 9-100 scale.
  BBRef_teamdecade = score_player(p).total  (advanced-metric: real BPM + TS% + DBPM, 50/50 peak/decade)
  K2_gamescale     = f_inv( era_cap( resolve_2K ) )   2K mapped back onto the game scale
Shows the new top-50 and the biggest movers vs BBRef-only.
"""
from __future__ import annotations
import sqlite3, importlib.util, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
def load(n, fn):
    s = importlib.util.spec_from_file_location(n, HERE / fn); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
kr = load("kr", "k2_resolve.py"); cal = load("cal", "k2_calibrate.py")

W_2K = 0.30   # 70/30 BBRef/2K


def main():
    conn = sqlite3.connect(HERE.parent / "app/data/players.db"); cur = conn.cursor()
    idx = kr._k2_index(cur)
    from app import dataset, scoring, rating
    pools = dataset.historical_pool()
    f, mono = cal.build_f(kr, idx, pools, scoring, cur)
    f_inv = cal.invert(mono)

    rows = []
    for key, players in pools.items():
        dec, team = key.split("|", 1)
        for p in players:
            bbref = scoring.score_player(p).total
            pk = cal.peak_rating(p, cur, scoring)
            k2, src = kr.resolve(idx, p.name, dec, team)
            k2c = cal.era_cap(k2, src, pk, f)
            blend2k = (1 - W_2K) * f(bbref) + W_2K * k2c          # clean blend on 2K scale
            rows.append([blend2k, p.name, dec, team, bbref, k2c, src, 0.0])

    # linear stretch: observed [lo, hi] of the 2K-scale blend -> game [GAME_LO, GAME_HI]
    vals = [r[0] for r in rows]
    lo, hi = min(vals), max(vals)
    GAME_LO, GAME_HI = 18.0, 99.0
    for r in rows:
        g = GAME_LO + (r[0] - lo) / (hi - lo) * (GAME_HI - GAME_LO)
        r[7] = rating.tier_round(round(g, 1))

    print(f"2K-scale blend range [{lo:.1f}, {hi:.1f}] -> game [{GAME_LO:.0f}, {GAME_HI:.0f}]\n")
    rows.sort(key=lambda r: -r[7])
    print("=== TOP 40 (final game-scale)  [final | 2Kblend | bb | 2Kcap] ===")
    for blend2k, n, d, t, bb, k2c, src, g in rows[:40]:
        print(f"  {g:5.1f}  2Kb {blend2k:4.1f}  bb {bb:5.1f}  2K {k2c}  {d} {t:<22} {n} [{src}]")

    # tier distribution (game scale): S80+/A70-79/B60-69/C50-59/D35-49/E<35
    import collections
    tc = collections.Counter()
    for *_, g in rows:
        tier = ("S" if g >= 80 else "A" if g >= 70 else "B" if g >= 60 else
                "C" if g >= 50 else "D" if g >= 35 else "E")
        tc[tier] += 1
    print("\ntier distribution:", {k: tc[k] for k in "SABCDE"})
    conn.close()


def _old():
    rows = []


def _old():
    rows = []

    rows.sort(reverse=True)
    print(f"=== TOP 40 by FINAL (50/50)   [final | BBRef | 2Kcap -> 2Kgame] ===")
    for fin, n, d, t, bb, k2c, k2g, src in rows[:40]:
        print(f"  {fin:5.1f}  bb {bb:5.1f}  2K {k2c}->{k2g:5.1f}  {d} {t:<22} {n} [{src}]")

    movers = sorted(rows, key=lambda r: r[6] - r[4])  # k2g - bbref
    print("\n=== BBRef pulled DOWN most by 2K (2K rates them lower) ===")
    for fin, n, d, t, bb, k2c, k2g, src in movers[:12]:
        print(f"  final {fin:5.1f}  bb {bb:5.1f} -> 2Kgame {k2g:5.1f}  {d} {t:<20} {n}")
    print("\n=== BBRef pushed UP most by 2K (2K rates them higher) ===")
    for fin, n, d, t, bb, k2c, k2g, src in movers[-12:][::-1]:
        print(f"  final {fin:5.1f}  bb {bb:5.1f} -> 2Kgame {k2g:5.1f}  {d} {t:<20} {n}")
    conn.close()


if __name__ == "__main__":
    main()
