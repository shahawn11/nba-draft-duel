"""
Export the canonical FINAL overall per (player, decade, team) the live game uses:
  final = 0.5*f(BBRef_teamdecade) + 0.5*era_cap(resolved_2K)   [2K scale]
  then FINAL OVERRIDES (k2_final_overrides.json) applied on top.
Writes app/data/k2_final_ratings.json : { "name|decade|team": overall }.

This is the single source of truth consumed by app.scoring.
Run after any change to the 2K layer / overrides:  python pipeline/export_final_ratings.py
"""
from __future__ import annotations
import json, sqlite3, importlib.util, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
def _load(n, fn):
    s = importlib.util.spec_from_file_location(n, HERE / fn); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
kr = _load("kr", "k2_resolve.py")
cal = _load("cal", "k2_calibrate.py")

W_2K = 0.50   # 50/50 BBRef / 2K blend


def main():
    conn = sqlite3.connect(HERE.parent / "app/data/players.db")
    cur = conn.cursor()
    idx = kr._k2_index(cur)
    from app import dataset, scoring
    pools = dataset.historical_pool()
    f, mono = cal.build_f(kr, idx, pools, scoring, cur)

    fo_path = HERE / "k2_final_overrides.json"
    fo = {k: v for k, v in json.loads(fo_path.read_text()).items()
          if not k.startswith("_")} if fo_path.exists() else {}

    out: dict[str, float] = {}
    for key, players in pools.items():
        dec, team = key.split("|", 1)
        for p in players:
            bb = scoring.score_player(p).total
            pk = cal.peak_rating(p, cur, scoring)
            k2, src = kr.resolve(idx, p.name, dec, team)
            k2c = cal.era_cap(k2, src, pk, f)
            blend = round((1 - W_2K) * f(bb) + W_2K * k2c, 1)
            combo = f"{p.name}|{dec}|{team}"
            out[combo] = fo.get(combo, blend)

    dest = HERE.parent / "app/data/k2_final_ratings.json"
    dest.write_text(json.dumps(out, indent=0, ensure_ascii=False))
    print(f"wrote {dest} with {len(out)} combos ({len(fo)} overrides applied)")
    conn.close()


if __name__ == "__main__":
    main()
