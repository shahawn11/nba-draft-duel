"""
NBA2K-style player attributes.

Rates a player in distinct areas on a 0-100 scale, then combines them into an
overall via a WEIGHTED blend (not a flat average -- a flat mean would reward
generalists and crush specialists). Areas use fixed, clamped anchors so a score
"feels" like 2K (e.g. ~30 ppg ≈ 99 scoring) and stays era-comparable; pre-data
eras (no 3PT, no DBPM) fall back to neutral so old players aren't punished.

Areas: scoring (PPG), efficiency (TS%), three (3P% x volume), rebounding (RPG),
playmaking (APG), defense (DBPM), impact (BPM).

This is a transparent tuning/UX layer (radar chart) over the holistic rating.
"""
from __future__ import annotations

from .scoring import PlayerStats


def _lin(x: float, lo: float, hi: float, out_lo: float = 0.0, out_hi: float = 99.0) -> float:
    """Clamped linear map x in [lo,hi] -> [out_lo,out_hi]."""
    if hi == lo:
        return out_lo
    t = (x - lo) / (hi - lo)
    return max(out_lo, min(out_hi, out_lo + t * (out_hi - out_lo)))


# Area weights for the overall (tunable; we renormalize over the areas that are
# actually available for a player's era). Impact (real BPM) dominates so the
# overall tracks Basketball-Reference and the all-time greats sit high.
AREA_WEIGHTS = {
    "impact": 0.40,
    "scoring": 0.16,
    "efficiency": 0.12,
    "defense": 0.10,
    "playmaking": 0.10,
    "rebounding": 0.07,
    "three": 0.05,
}


def _available(p: PlayerStats) -> set[str]:
    """Areas with real data for this player's era (others are dropped, not
    scored 0, so pre-3pt / pre-DBPM legends aren't penalized for missing stats)."""
    av = {"scoring", "efficiency", "rebounding", "playmaking", "impact"}
    if p.decade not in ("1960s", "1970s"):
        av.add("three")          # 3PT only from 1979-80
    if p.decade != "1960s":
        av.add("defense")        # DBPM only from 1973-74
    return av


def areas(p: PlayerStats) -> dict[str, float]:
    """Per-area 0-100 ratings for a player (only areas available for the era)."""
    if p.three_pa and p.three_pa >= 1.0:
        acc = _lin(p.three_pct, 0.30, 0.43, 30, 99)
        vol = _lin(p.three_pa, 1.0, 9.0, 40, 99)
        three = 0.6 * acc + 0.4 * vol
    else:
        three = 12.0
    full = {
        "scoring": _lin(p.ppg, 8, 30, 30, 99),
        "efficiency": _lin(p.ts_pct, 0.47, 0.64, 35, 99) if p.ts_pct else 55,
        "three": three,
        "rebounding": _lin(p.rpg, 2, 14, 20, 99),
        "playmaking": _lin(p.apg, 1, 10, 25, 99),
        # Muted: box DBPM tops out ~+4-5 and over-credits rebounding bigs, so no
        # one earns a 99 on defense from it alone.
        "defense": _lin(p.dbpm, -1.5, 5.5, 30, 92),
        # Generous for the stars: real BPM is the headline impact metric.
        "impact": _lin(p.bpm, -1.0, 12.0, 30, 99),
    }
    av = _available(p)
    return {k: round(v, 0) for k, v in full.items() if k in av}


def overall(p: PlayerStats) -> float:
    """Weighted blend over the player's AVAILABLE areas (weights renormalized)."""
    a = areas(p)
    wsum = sum(AREA_WEIGHTS[k] for k in a)
    if not wsum:
        return 0.0
    return round(sum(a[k] * AREA_WEIGHTS[k] for k in a) / wsum, 1)
