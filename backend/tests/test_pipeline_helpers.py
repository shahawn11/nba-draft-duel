"""Offline unit tests for the pure pipeline helpers (no network / nba_api)."""
from __future__ import annotations

from pipeline.build_dataset import (
    full_team_name,
    map_position,
    pie_to_bpm,
    season_to_decade,
)


def test_season_to_decade():
    assert season_to_decade("1996-97") == "1990s"
    assert season_to_decade("2009-10") == "2000s"
    assert season_to_decade("2023-24") == "2020s"


def test_full_team_name_current_and_historical():
    assert full_team_name("CHI") == "Chicago Bulls"
    assert full_team_name("SEA") == "Oklahoma City Thunder"  # relocation alias
    assert full_team_name("VAN") == "Memphis Grizzlies"
    assert full_team_name("zzz") == "ZZZ" or full_team_name("zzz") == "zzz"  # unknown passthrough


def test_pie_to_bpm_scale():
    assert pie_to_bpm(0.10) == 0.0          # league average
    assert pie_to_bpm(0.20) == 10.0         # star
    assert pie_to_bpm(0.05) == -5.0
    assert pie_to_bpm(0.30) == 13.0         # clamped
    assert pie_to_bpm(None) == 0.0


def test_map_position():
    assert map_position("Center", 1.0, 11.0) == "C"
    assert map_position("Center-Forward", 2.0, 10.0) == "C"
    assert map_position("Guard", 8.0, 4.0) == "PG"     # high assists
    assert map_position("Guard", 2.0, 3.0) == "SG"     # low assists
    assert map_position("Forward", 2.0, 9.0) == "PF"   # high rebounds
    assert map_position("Forward", 3.0, 4.0) == "SF"   # wing
    assert map_position("Forward-Guard", 5.0, 5.0) == "SF"
    # no position string -> stat fallback
    assert map_position("", 7.0, 3.0) == "PG"
    assert map_position(None, 1.0, 10.0) == "C"


def run_all():
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ok {name}")
    print("ALL PIPELINE HELPER TESTS PASSED")


if __name__ == "__main__":
    run_all()
