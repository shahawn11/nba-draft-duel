"""
Demo: simulate one offline-mode duel.

Picks a random current NBA starting 5 as the opponent, builds a sample drafted
lineup from the historical pool, and prints the full scored breakdown.

Run from the backend/ dir:  python -m app.demo
"""
from __future__ import annotations

import random

from .scoring import duel
from .seed_data import (
    CURRENT_STARTERS,
    HISTORICAL_POOL,
    random_current_opponent,
)


def main(seed: int = 7) -> None:
    rng = random.Random(seed)

    # Opponent = random current starting 5.
    opp_team, opponent = random_current_opponent(rng)

    # "Player" draft: take the 90s Bulls as a sample drafted lineup.
    drafted = HISTORICAL_POOL["1990s|Chicago Bulls"]

    result = duel(home_players=drafted, away_players=opponent)

    print("=" * 60)
    print(f"YOUR DRAFT (Home)   vs   {opp_team} (Away, current)")
    print("=" * 60)

    print("\n-- Player scores --")
    for label, team in (("HOME", result.home), ("AWAY", result.away)):
        print(f"\n[{label}]  base {team.base_total:.1f}  fit {team.fit_adjustment:+.1f}  -> {team.adjusted_total:.1f}")
        for ps in sorted(team.player_scores, key=lambda s: -s.total):
            p = ps.player
            print(f"   {p.position:<2} {p.name:<26} prod {ps.production:5.1f}  adv {ps.advanced:5.1f}  total {ps.total:5.1f}")
        for note in team.fit_notes:
            print(f"      fit: {note}")

    print("\n-- Positional matchups --")
    for m in result.matchups:
        mark = {"home": "HOME", "away": "AWAY", "tie": "TIE "}[m.winner]
        print(f"   {m.position:<2}  {m.home_player:<24} {m.home_score:5.1f}  vs  {m.away_score:5.1f}  {m.away_player:<24} -> {mark}")

    print("\n" + "=" * 60)
    print(result.summary())
    print("=" * 60)


if __name__ == "__main__":
    main()
