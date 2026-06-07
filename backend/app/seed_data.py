"""
Curated seed dataset so the game is playable immediately, before running the
full `nba_api` historical scrape (see pipeline/build_dataset.py).

Two pools:
  CURRENT_STARTERS  -> opponents for offline mode (real 2024-25 starting 5s)
  HISTORICAL_POOL   -> draftable players keyed by (decade, team)

Stats are approximate per-game averages for representative seasons and are
meant to make the scoring engine demonstrable, not to be the source of truth.
The pipeline replaces these with exact data.
"""
from __future__ import annotations

from .scoring import PlayerStats

# --- Current NBA starting fives (offline-mode opponents) --------------------
CURRENT_STARTERS: dict[str, list[PlayerStats]] = {
    "Boston Celtics": [
        PlayerStats("Jrue Holiday", "PG", 12.5, 5.4, 4.8, 0.9, 0.8, 2.5, team="BOS", season="2024-25"),
        PlayerStats("Derrick White", "SG", 16.4, 4.5, 5.2, 1.0, 1.1, 3.5, team="BOS", season="2024-25"),
        PlayerStats("Jaylen Brown", "SF", 24.7, 5.9, 4.5, 1.2, 0.4, 3.8, team="BOS", season="2024-25"),
        PlayerStats("Jayson Tatum", "PF", 27.1, 8.5, 5.6, 1.1, 0.6, 6.5, team="BOS", season="2024-25"),
        PlayerStats("Kristaps Porzingis", "C", 19.5, 6.8, 2.0, 0.7, 1.9, 4.0, team="BOS", season="2024-25"),
    ],
    "Denver Nuggets": [
        PlayerStats("Jamal Murray", "PG", 21.0, 4.1, 6.2, 1.0, 0.5, 3.0, team="DEN", season="2024-25"),
        PlayerStats("Christian Braun", "SG", 15.4, 5.1, 2.6, 1.1, 0.6, 2.0, team="DEN", season="2024-25"),
        PlayerStats("Michael Porter Jr.", "SF", 18.2, 7.0, 1.6, 0.8, 0.6, 2.5, team="DEN", season="2024-25"),
        PlayerStats("Aaron Gordon", "PF", 14.7, 5.6, 3.5, 0.8, 0.6, 2.8, team="DEN", season="2024-25"),
        PlayerStats("Nikola Jokic", "C", 29.6, 12.7, 10.2, 1.8, 0.6, 13.7, team="DEN", season="2024-25"),
    ],
    "Oklahoma City Thunder": [
        PlayerStats("Shai Gilgeous-Alexander", "PG", 32.7, 5.0, 6.4, 1.7, 1.0, 11.0, team="OKC", season="2024-25"),
        PlayerStats("Luguentz Dort", "SG", 10.1, 4.1, 1.6, 1.1, 0.5, 1.5, team="OKC", season="2024-25"),
        PlayerStats("Jalen Williams", "SF", 21.6, 5.3, 5.1, 1.6, 0.6, 4.5, team="OKC", season="2024-25"),
        PlayerStats("Chet Holmgren", "PF", 16.0, 8.0, 2.0, 0.6, 2.3, 4.0, team="OKC", season="2024-25"),
        PlayerStats("Isaiah Hartenstein", "C", 11.0, 10.7, 3.8, 1.0, 1.1, 3.5, team="OKC", season="2024-25"),
    ],
}

# --- Historical draftable pool, keyed by (decade, team franchise) -----------
# Keys are "<decade>|<team>" e.g. "1990s|Chicago Bulls".
HISTORICAL_POOL: dict[str, list[PlayerStats]] = {
    "1990s|Chicago Bulls": [
        PlayerStats("Michael Jordan", "SG", 30.1, 6.2, 5.3, 2.7, 0.8, 8.5, team="CHI", season="1996-97", decade="1990s"),
        PlayerStats("Scottie Pippen", "SF", 18.6, 6.4, 5.8, 1.9, 0.8, 5.0, team="CHI", season="1996-97", decade="1990s"),
        PlayerStats("Dennis Rodman", "PF", 5.7, 16.1, 3.1, 0.6, 0.4, 3.0, team="CHI", season="1996-97", decade="1990s"),
        PlayerStats("Toni Kukoc", "SF", 13.2, 4.0, 4.6, 1.0, 0.5, 2.0, team="CHI", season="1996-97", decade="1990s"),
        PlayerStats("Ron Harper", "PG", 6.3, 2.7, 2.6, 1.2, 0.5, 1.0, team="CHI", season="1996-97", decade="1990s"),
    ],
    "1980s|Los Angeles Lakers": [
        PlayerStats("Magic Johnson", "PG", 19.5, 7.3, 12.8, 1.7, 0.3, 8.0, team="LAL", season="1986-87", decade="1980s"),
        PlayerStats("Kareem Abdul-Jabbar", "C", 17.5, 6.7, 2.6, 0.6, 1.2, 3.0, team="LAL", season="1986-87", decade="1980s"),
        PlayerStats("James Worthy", "SF", 19.4, 5.7, 2.8, 1.1, 0.7, 3.5, team="LAL", season="1986-87", decade="1980s"),
        PlayerStats("Byron Scott", "SG", 17.0, 3.1, 3.4, 1.4, 0.2, 2.0, team="LAL", season="1986-87", decade="1980s"),
        PlayerStats("A.C. Green", "PF", 10.8, 7.8, 1.1, 0.9, 0.5, 1.5, team="LAL", season="1986-87", decade="1980s"),
    ],
    "2010s|Golden State Warriors": [
        PlayerStats("Stephen Curry", "PG", 30.1, 5.1, 6.7, 1.8, 0.2, 9.0, team="GSW", season="2015-16", decade="2010s"),
        PlayerStats("Klay Thompson", "SG", 22.1, 3.8, 2.1, 0.8, 0.6, 3.0, team="GSW", season="2015-16", decade="2010s"),
        PlayerStats("Andre Iguodala", "SF", 7.0, 4.0, 3.4, 1.1, 0.3, 2.5, team="GSW", season="2015-16", decade="2010s"),
        PlayerStats("Draymond Green", "PF", 14.0, 9.5, 7.4, 1.5, 1.4, 6.0, team="GSW", season="2015-16", decade="2010s"),
        PlayerStats("Andrew Bogut", "C", 5.4, 7.0, 2.3, 0.5, 1.6, 2.0, team="GSW", season="2015-16", decade="2010s"),
    ],
    "2000s|San Antonio Spurs": [
        PlayerStats("Tony Parker", "PG", 18.6, 3.2, 5.8, 1.0, 0.1, 3.5, team="SAS", season="2004-05", decade="2000s"),
        PlayerStats("Manu Ginobili", "SG", 16.0, 4.4, 3.9, 1.6, 0.4, 4.5, team="SAS", season="2004-05", decade="2000s"),
        PlayerStats("Bruce Bowen", "SF", 8.2, 3.0, 1.7, 0.9, 0.4, 1.0, team="SAS", season="2004-05", decade="2000s"),
        PlayerStats("Tim Duncan", "PF", 20.3, 11.1, 2.7, 0.7, 2.6, 7.5, team="SAS", season="2004-05", decade="2000s"),
        PlayerStats("Rasho Nesterovic", "C", 8.7, 6.5, 1.0, 0.5, 1.2, 1.5, team="SAS", season="2004-05", decade="2000s"),
    ],
}


def random_current_opponent(rng) -> tuple[str, list[PlayerStats]]:
    team = rng.choice(list(CURRENT_STARTERS.keys()))
    return team, CURRENT_STARTERS[team]


def available_draft_prompts() -> list[tuple[str, str]]:
    """Return (decade, team) pairs that have a draftable pool."""
    prompts = []
    for key in HISTORICAL_POOL:
        decade, team = key.split("|", 1)
        prompts.append((decade, team))
    return prompts
