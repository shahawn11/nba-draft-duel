"""
Export the CURRENT-FORM blended overall for active players, used to rate the
offline-mode opponents (current-NBA starting fives).

  current = 0.5*f(BBRef_this_season) + 0.5*current_2K_card     [2K scale]

- BBRef_this_season: the live score_player formula on the player's MOST RECENT
  season row in players.db (this season for active players; last healthy season
  for stars who missed the current year, e.g. returning-from-injury).
- f(): the same BBRef->2K calibration learned for the decade blend
  (k2_calibrate.build_f), so a current player lands on the same 0-100 scale as
  the draft pool (a current 2K 98 -> game 98).
- current_2K_card: the player's NBA 2K "current" roster card (source='current').

Unlike the decade blend (peak/era-capped), this is intentionally CURRENT FORM:
no era-cap, the live card and this-season production decide the number.

Writes app/data/current_ratings.json : {"__season__": "<season>", "<name>": overall}
keyed by the players.db display name (what PlayerStats.name carries), so live
scoring can look it up directly.

Run:  python pipeline/export_current_ratings.py
"""
from __future__ import annotations
import json, sqlite3, importlib.util, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


def _load(n, fn):
    s = importlib.util.spec_from_file_location(n, HERE / fn)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


kr = _load("kr", "k2_resolve.py")
cal = _load("cal", "k2_calibrate.py")

W_2K = 0.60   # lean toward the 2K current card; BBRef is the differentiating half

# Current-form BBRef -> game scale. The SHARED decade calibration plateaus at 77
# across bb 26-77, which collapses ~every current starter to 77 and caps stars.
# This dedicated curve SPREADS the current single-season distribution so this
# season's production actually differentiates players (and lifts the field).
# (bb is the raw 0-100 score_player formula value; anchors below were set from
# the current-season bb percentiles.) Draft-pool ratings are unaffected.
CF_ANCHORS = [(9, 68), (18, 71), (27, 74), (36, 77), (47, 80),
              (60, 83), (77, 87), (86, 91), (92, 95), (100, 99)]
cf_scale = cal._piecewise(CF_ANCHORS)


def _bbref_form(scoring, row) -> float:
    """Live BBRef formula total on a single season's stats (no decade/JSON
    lookup): the raw 0.5*production*ts + 0.5*impact + defensive rescue."""
    from app.scoring import PlayerStats
    p = PlayerStats(
        name=row["name"], position=row["position"] or "SF",
        ppg=row["ppg"] or 0, rpg=row["rpg"] or 0, apg=row["apg"] or 0,
        spg=row["spg"] or 0, bpg=row["bpg"] or 0, bpm=row["bpm"] or 0,
        ts_pct=row["ts_pct"] or 0, dbpm=row["dbpm"] or 0,
    )
    prod = scoring._normalize_production(p.production())
    adv = scoring._normalize_advanced(p.bpm)
    total = prod * scoring.PRODUCTION_WEIGHT + adv * scoring.ADVANCED_WEIGHT
    total = max(total, min(total + scoring.defensive_bonus(p.dbpm), scoring.DEF_BONUS_CEIL))
    return total


def main():
    conn = sqlite3.connect(HERE.parent / "app/data/players.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    idx = kr._k2_index(cur)

    from app import dataset, scoring
    pools = dataset.historical_pool()
    f, _mono = cal.build_f(kr, idx, pools, scoring, cur)  # only used for sanity refs

    season = cur.execute("SELECT MAX(season) FROM players").fetchone()[0]
    current_names = {r["name"] for r in
                     cur.execute("SELECT name FROM players WHERE season=?", (season,))}

    # Most-recent season row per player name (prefer the current season; a star
    # who missed it falls back to his last DB season for the production half).
    rows = cur.execute(
        "SELECT name, position, season, team, ppg, rpg, apg, spg, bpg, bpm, "
        "ts_pct, dbpm FROM players ORDER BY season"
    ).fetchall()
    latest: dict[str, sqlite3.Row] = {}
    for r in rows:
        latest[r["name"]] = r   # ordered ascending -> last write is most recent
    # current + prior season -> the curated fallback only applies to recent
    # players (so retired legends in k2_curated aren't pulled in as "current").
    recent_seasons = set(sorted({r["season"] for r in rows}, reverse=True)[:2])

    out: dict[str, float] = {"__season__": season}
    n_blend = n_inject = n_bbonly = 0
    for name, row in latest.items():
        d = idx.get(kr.ALIAS.get(kr.norm(name), kr.norm(name)), {})
        card = d.get("current", 0)
        if not card and row["season"] in recent_seasons:
            card = d.get("curated", 0)   # hand-set fallback (recent players only)
        played = name in current_names
        if not card and not played:
            continue   # retired / no data
        if not played:
            # Out the ENTIRE current season (e.g. Tatum, Haliburton): no this-
            # season production to blend -> use the 2K current card directly.
            out[name] = float(card)
            n_inject += 1
            continue
        bb = _bbref_form(scoring, row)
        if card:
            out[name] = round((1 - W_2K) * cf_scale(bb) + W_2K * card, 1)
            n_blend += 1
        else:
            out[name] = round(cf_scale(bb), 1)   # active, no card -> BBRef-only
            n_bbonly += 1

    dest = HERE.parent / "app/data/current_ratings.json"
    dest.write_text(json.dumps(out, indent=0, ensure_ascii=False))
    print(f"wrote {dest}: season={season}, {n_blend} blended, {n_inject} 2K-only "
          f"(missed season), {n_bbonly} BBRef-only, {len(out)-1} total")
    # spot check
    for nm in ["Nikola Jokić", "Shai Gilgeous-Alexander", "Luka Dončić",
               "Victor Wembanyama", "Jayson Tatum", "Tyrese Haliburton",
               "Stephen Curry", "Jaylen Brown", "Aaron Gordon", "Bub Carrington"]:
        if nm in out:
            print(f"  {nm:<28} {out[nm]}")
    conn.close()


if __name__ == "__main__":
    main()
