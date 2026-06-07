"""
Curated seed dataset so the game is playable immediately, before running the
full `nba_api` historical scrape (see pipeline/build_dataset.py).

Two pools:
  CURRENT_STARTERS  -> opponents for offline mode (real recent starting 5s)
  HISTORICAL_POOL   -> draftable players keyed by (decade, team), 10 deep

Historical stats are approximate *decade averages* for that player with that
franchise, and each player carries `eligible_positions` (the lineup slots they
may be drafted into). Genuine combos are multi-eligible; most players are not.
The pipeline replaces these with exact data when players.db is built.
"""
from __future__ import annotations

from .scoring import PlayerStats


def _p(name, pos, ppg, rpg, apg, spg, bpg, bpm, team, decade, elig=()):
    return PlayerStats(
        name=name, position=pos, ppg=ppg, rpg=rpg, apg=apg, spg=spg, bpg=bpg,
        bpm=bpm, team=team, season=decade, decade=decade, eligible_positions=elig,
    )


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

# --- Historical draftable pools (10 deep), keyed "<decade>|<team>" ----------
HISTORICAL_POOL: dict[str, list[PlayerStats]] = {
    "1990s|Chicago Bulls": [
        _p("Michael Jordan", "SG", 30.1, 6.2, 5.3, 2.6, 0.7, 9.5, "CHI", "1990s", ("SG", "SF")),
        _p("Scottie Pippen", "SF", 19.0, 7.0, 5.8, 2.0, 0.8, 6.0, "CHI", "1990s", ("SF", "PF")),
        _p("Dennis Rodman", "PF", 5.7, 15.3, 2.9, 0.6, 0.5, 3.0, "CHI", "1990s", ("PF", "C")),
        _p("Toni Kukoc", "SF", 13.1, 4.2, 4.2, 1.0, 0.4, 2.0, "CHI", "1990s", ("SF", "PF")),
        _p("Horace Grant", "PF", 12.6, 8.9, 2.4, 1.0, 1.0, 2.5, "CHI", "1990s", ("PF", "C")),
        _p("B.J. Armstrong", "PG", 11.5, 2.3, 4.0, 1.0, 0.1, 1.0, "CHI", "1990s", ("PG",)),
        _p("Ron Harper", "PG", 8.0, 3.2, 3.0, 1.3, 0.5, 0.8, "CHI", "1990s", ("PG", "SG")),
        _p("Steve Kerr", "SG", 8.2, 1.5, 2.1, 0.8, 0.1, 1.5, "CHI", "1990s", ("PG", "SG")),
        _p("Luc Longley", "C", 7.9, 5.1, 1.8, 0.4, 0.9, 0.5, "CHI", "1990s", ("C",)),
        _p("John Paxson", "PG", 7.0, 1.4, 3.4, 0.9, 0.1, 0.5, "CHI", "1990s", ("PG",)),
    ],
    "1980s|Los Angeles Lakers": [
        _p("Magic Johnson", "PG", 19.5, 7.3, 11.4, 1.8, 0.4, 9.0, "LAL", "1980s", ("PG", "SF")),
        _p("Kareem Abdul-Jabbar", "C", 21.5, 7.2, 3.0, 0.7, 2.4, 6.0, "LAL", "1980s", ("C",)),
        _p("James Worthy", "SF", 19.0, 5.5, 3.0, 1.1, 0.6, 3.5, "LAL", "1980s", ("SF", "PF")),
        _p("Byron Scott", "SG", 15.0, 3.2, 3.0, 1.3, 0.3, 2.0, "LAL", "1980s", ("SG",)),
        _p("Norm Nixon", "PG", 16.5, 2.6, 8.0, 1.5, 0.1, 2.5, "LAL", "1980s", ("PG",)),
        _p("Jamaal Wilkes", "SF", 17.0, 5.0, 2.2, 1.3, 0.4, 2.0, "LAL", "1980s", ("SF",)),
        _p("Michael Cooper", "SG", 9.0, 3.2, 4.2, 1.3, 0.6, 2.5, "LAL", "1980s", ("SG", "SF")),
        _p("A.C. Green", "PF", 9.5, 7.5, 1.1, 0.8, 0.5, 1.5, "LAL", "1980s", ("PF", "C")),
        _p("Bob McAdoo", "C", 11.5, 4.2, 1.2, 0.4, 0.9, 1.5, "LAL", "1980s", ("PF", "C")),
        _p("Kurt Rambis", "PF", 5.8, 6.2, 1.0, 0.8, 0.4, 1.0, "LAL", "1980s", ("PF", "C")),
    ],
    "2010s|Golden State Warriors": [
        _p("Stephen Curry", "PG", 25.3, 4.5, 6.8, 1.7, 0.2, 9.5, "GSW", "2010s", ("PG",)),
        _p("Kevin Durant", "SF", 25.8, 6.9, 5.0, 0.8, 1.1, 8.0, "GSW", "2010s", ("SF", "PF")),
        _p("Klay Thompson", "SG", 19.8, 3.6, 2.2, 0.9, 0.5, 2.5, "GSW", "2010s", ("SG",)),
        _p("Draymond Green", "PF", 11.5, 7.8, 6.0, 1.5, 1.1, 5.5, "GSW", "2010s", ("PF", "C")),
        _p("Andre Iguodala", "SF", 7.5, 4.0, 3.4, 1.1, 0.4, 2.5, "GSW", "2010s", ("SG", "SF")),
        _p("David Lee", "PF", 13.0, 8.8, 2.8, 0.7, 0.4, 1.5, "GSW", "2010s", ("PF", "C")),
        _p("Harrison Barnes", "SF", 10.2, 4.3, 1.5, 0.7, 0.3, 1.0, "GSW", "2010s", ("SF", "PF")),
        _p("Shaun Livingston", "PG", 5.9, 2.2, 3.0, 0.7, 0.4, 1.0, "GSW", "2010s", ("PG", "SG")),
        _p("Andrew Bogut", "C", 6.0, 8.0, 2.2, 0.6, 1.6, 2.5, "GSW", "2010s", ("C",)),
        _p("Festus Ezeli", "C", 5.0, 5.2, 0.5, 0.3, 1.0, 0.5, "GSW", "2010s", ("C",)),
    ],
    "2000s|San Antonio Spurs": [
        _p("Tim Duncan", "PF", 21.0, 11.4, 3.2, 0.8, 2.4, 8.0, "SAS", "2000s", ("PF", "C")),
        _p("Tony Parker", "PG", 16.5, 3.2, 5.8, 1.0, 0.1, 3.5, "SAS", "2000s", ("PG",)),
        _p("Manu Ginobili", "SG", 15.0, 4.0, 3.9, 1.5, 0.3, 5.0, "SAS", "2000s", ("SG", "SF")),
        _p("David Robinson", "C", 11.5, 8.0, 1.7, 0.8, 2.2, 4.0, "SAS", "2000s", ("C",)),
        _p("Bruce Bowen", "SF", 6.5, 3.0, 1.5, 0.9, 0.4, 1.0, "SAS", "2000s", ("SF",)),
        _p("Michael Finley", "SG", 10.0, 3.3, 1.9, 0.7, 0.2, 1.0, "SAS", "2000s", ("SG", "SF")),
        _p("Robert Horry", "PF", 5.5, 4.6, 1.8, 0.8, 0.9, 1.5, "SAS", "2000s", ("PF", "C")),
        _p("Stephen Jackson", "SG", 11.5, 3.6, 2.8, 1.1, 0.3, 1.0, "SAS", "2000s", ("SG", "SF")),
        _p("Brent Barry", "SG", 8.0, 2.5, 2.4, 0.8, 0.2, 1.5, "SAS", "2000s", ("SG", "SF")),
        _p("Rasho Nesterovic", "C", 7.5, 6.0, 1.0, 0.4, 1.1, 1.0, "SAS", "2000s", ("C",)),
    ],
}


def random_current_opponent(rng) -> tuple[str, list[PlayerStats]]:
    team = rng.choice(list(CURRENT_STARTERS.keys()))
    return team, CURRENT_STARTERS[team]


def available_draft_prompts() -> list[tuple[str, str]]:
    return [tuple(key.split("|", 1)) for key in HISTORICAL_POOL]
