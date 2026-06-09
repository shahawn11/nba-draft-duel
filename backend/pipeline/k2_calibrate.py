"""
Calibrate a 2K-scale rating for pool combos that have NO real 2K rating, from
their peak-season-in-decade BBRef rating (score_player.total), using the
BBRef<->2K relationship learned on combos that DO have both.

Avoids era-mismatch (uses the combo's own decade rating) and keeps everything on
2K's compressed scale. Covers licensing-blocked legends (Barkley, Reggie) too.

Writes k2_calibrated.json keyed "name|decade|team" -> est 2K overall.
Usage: python pipeline/k2_calibrate.py [--write]
"""
from __future__ import annotations
import argparse, json, sqlite3, importlib.util, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


def _load_resolver():
    spec = importlib.util.spec_from_file_location("kr", HERE / "k2_resolve.py")
    kr = importlib.util.module_from_spec(spec); spec.loader.exec_module(kr)
    return kr


def _piecewise(anchors):
    """Return f(x) monotonic piecewise-linear through (x,y) anchors, clamped to y-range."""
    xs = [a for a, _ in anchors]; ys = [b for _, b in anchors]
    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        for i in range(1, len(xs)):
            if x <= xs[i]:
                t = (x - xs[i-1]) / (xs[i] - xs[i-1])
                return ys[i-1] + t * (ys[i] - ys[i-1])
        return ys[-1]
    return f


def invert(mono):
    """Inverse of the monotonic (x=BBRef, y=2K) anchors: maps a 2K value -> game-scale BBRef.
    Flat y-regions invert to the lowest x achieving that y (conservative)."""
    # collapse to strictly-increasing-y points, keeping the first x for each y
    seen = {}
    pts = []
    for x, y in mono:
        if y not in seen:
            seen[y] = x
            pts.append((y, x))   # (2K, BBRef)
    return _piecewise(pts)


# Era-correct sources reflect a player's actual level THAT decade (peak-season
# blend), unlike decade-agnostic all-time/curated peaks.
ERA_CORRECT_SOURCES = ("classic", "current", "all-decade")
# Low-end floor: pool players weaker than the matched-data floor extrapolate down
# into 2K's true rotation range (~68-77) instead of bottoming at 80.
LOW_FLOOR_ANCHORS = [(8, 68), (18, 73), (26, 77)]
ERA_CAP_MARGIN = 3    # all-time/curated capped at expectation(decade BBRef)+margin
ERA_CAP_DEADBAND = 3  # only cap when it would lower the value by >= this (ignore small gaps)

_PEAK_CACHE: dict = {}


def peak_rating(p, cur, scoring):
    """Pure PEAK-SEASON-in-decade/team BBRef rating (best qualifying season, >=25 GP),
    recomputed from raw DB seasons. Falls back to the blended rating if no seasons found."""
    from dataclasses import replace
    key = (p.name, p.decade, p.team)
    if key in _PEAK_CACHE:
        return _PEAK_CACHE[key]
    rows = cur.execute(
        "SELECT ppg,rpg,apg,spg,bpg,bpm,ts_pct,dbpm,three_pa,three_pct,gp FROM players "
        "WHERE name=? AND decade=? AND team=?", (p.name, p.decade, p.team)).fetchall()
    if not rows:
        val = scoring.score_player(p).total
        _PEAK_CACHE[key] = val
        return val
    qual = [r for r in rows if (r[10] or 0) >= 25] or rows
    best = 0.0
    for ppg, rpg, apg, spg, bpg, bpm, ts, dbpm, t3a, t3p, gp in qual:
        cand = replace(p, ppg=ppg or 0, rpg=rpg or 0, apg=apg or 0, spg=spg or 0,
                       bpg=bpg or 0, bpm=bpm or 0, ts_pct=ts or 0, dbpm=dbpm or 0,
                       three_pa=t3a or 0, three_pct=t3p or 0, rating_override=None)
        best = max(best, scoring.score_player(cand).total)
    _PEAK_CACHE[key] = best
    return best


def build_f(kr, idx, pools, scoring, cur, return_missing=False):
    """Learn peakBBRef->2K piecewise from ERA-CORRECT matched combos, plus a low floor."""
    import statistics
    bins: dict[int, list] = {}
    missing = []
    for key, players in pools.items():
        dec, team = key.split("|", 1)
        for p in players:
            bb = peak_rating(p, cur, scoring)
            raw, rsrc = kr.era_correct_raw(idx, p.name, dec)
            if raw is not None:
                bins.setdefault(int(bb // 5 * 5), []).append(raw)
            ovr, src = kr.resolve(idx, p.name, dec, team)
            if src in (None, "calibrated"):
                missing.append((p.name, dec, team, bb))
    data = [(k + 2, statistics.median(v)) for k, v in sorted(bins.items()) if len(v) >= 5]
    # prepend low floor anchors below the data's lowest x
    lo_x = data[0][0] if data else 30
    anchors = [a for a in LOW_FLOOR_ANCHORS if a[0] < lo_x] + data
    mono = []
    for x, y in anchors:
        if mono and y < mono[-1][1]:
            y = mono[-1][1]
        mono.append((x, y))
    f = _piecewise(mono)
    return (f, mono, missing) if return_missing else (f, mono)


def era_cap(ovr, src, bbref, f):
    """Cap real 2K cards at this combo's peak-season expectation+margin, but only when
    the correction is meaningful (drop >= deadband). Exempts 'override'/'calibrated'."""
    if src in ("classic", "alltime", "all-decade", "current", "curated"):
        target = round(f(bbref)) + ERA_CAP_MARGIN
        if ovr - target >= ERA_CAP_DEADBAND:
            return target
    return ovr


def main(write: bool):
    kr = _load_resolver()
    conn = sqlite3.connect(HERE.parent / "app/data/players.db"); cur = conn.cursor()
    idx = kr._k2_index(cur)
    from app import dataset, scoring
    pools = dataset.historical_pool()

    f, mono, missing = build_f(kr, idx, pools, scoring, cur, return_missing=True)

    print("calibration anchors (BBRef -> 2K):")
    print("  " + ", ".join(f"{x:.0f}->{y:.0f}" for x, y in mono))

    # 2) apply to missing combos
    out = {}
    for name, dec, team, bb in missing:
        out[f"{name}|{dec}|{team}"] = round(f(bb))
    print(f"\ncalibrated {len(out)} missing combos")

    show = ["Charles Barkley", "Reggie Miller", "Rasheed Wallace", "Mookie Blaylock",
            "Sam Jones", "Jack Twyman", "Paul Silas", "Mark Jackson", "Antoine Walker"]
    print("\nsamples:")
    for name, dec, team, bb in sorted(missing, key=lambda x: -x[3]):
        if name in show:
            print(f"  {dec} {team:<22} {name:<18} BBRef {bb:5.1f} -> 2K-est {round(f(bb))}")

    if write:
        p = HERE / "k2_calibrated.json"
        p.write_text(json.dumps(out, indent=0, ensure_ascii=False))
        print(f"\nwrote {p}")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    main(ap.parse_args().write)
