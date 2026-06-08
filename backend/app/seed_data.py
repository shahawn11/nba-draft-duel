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


# Real heights (inches) for curated legends. Anything missing falls back to a
# position-typical default. (DB-era players carry exact heights from the pull.)
_POS_DEFAULT_H = {"PG": 74, "SG": 77, "SF": 79, "PF": 81, "C": 84}
_HEIGHTS: dict[str, int] = {
    # 1960s Celtics
    "Bill Russell": 82, "Bob Cousy": 73, "John Havlicek": 77, "Sam Jones": 76,
    "Tom Heinsohn": 79, "Bill Sharman": 73, "K.C. Jones": 73, "Frank Ramsey": 75,
    "Tom Sanders": 78, "Don Nelson": 78,
    # 1960s Lakers / 76ers / Royals
    "Wilt Chamberlain": 85, "Jerry West": 74, "Elgin Baylor": 77, "Gail Goodrich": 73,
    "Dick Barnett": 76, "Rudy LaRusso": 80, "Happy Hairston": 79, "Jim McMillian": 77,
    "LeRoy Ellis": 82, "Mel Counts": 84, "Billy Cunningham": 78, "Hal Greer": 74,
    "Chet Walker": 78, "Luke Jackson": 78, "Wali Jones": 74, "Larry Costello": 73,
    "Dave Gambee": 79, "Matt Guokas": 78, "Bill Melchionni": 74, "Oscar Robertson": 77,
    "Jerry Lucas": 80, "Jack Twyman": 78, "Bob Boozer": 80, "Wayne Embry": 80,
    "Adrian Smith": 73, "Arlen Bockhorn": 76, "Connie Dierking": 81, "Tom Hawkins": 77,
    "Tom Van Arsdale": 77,
    # 1970s Knicks / Bucks / Celtics / Lakers / Blazers
    "Walt Frazier": 76, "Willis Reed": 81, "Earl Monroe": 75, "Dave DeBusschere": 78,
    "Bill Bradley": 77, "Cazzie Russell": 77, "Phil Jackson": 80, "Dean Meminger": 75,
    "Kareem Abdul-Jabbar": 86, "Bob Dandridge": 78, "Jon McGlocklin": 77,
    "Lucius Allen": 74, "Greg Smith": 79, "Curtis Perry": 80, "Dick Cunningham": 81,
    "Dave Cowens": 81, "Jo Jo White": 75, "Paul Silas": 79, "Charlie Scott": 77,
    "Paul Westphal": 76, "Don Chaney": 77, "Steve Kuberski": 80, "Dave Bing": 75,
    "Keith Erickson": 77, "Flynn Robinson": 73, "Pat Riley": 76, "Jim Cleamons": 75,
    "Bill Walton": 83, "Maurice Lucas": 81, "Lionel Hollins": 75, "Bob Gross": 78,
    "Dave Twardzik": 72, "Lloyd Neal": 78, "Johnny Davis": 74, "Larry Steele": 77,
    "Herm Gilliam": 75, "Corky Calhoun": 78,
    # 1980s Lakers / Celtics / Pistons / 76ers / Rockets
    "Magic Johnson": 81, "James Worthy": 81, "Byron Scott": 76, "Norm Nixon": 74,
    "Jamaal Wilkes": 78, "Michael Cooper": 79, "A.C. Green": 81, "Bob McAdoo": 81,
    "Kurt Rambis": 80, "Larry Bird": 81, "Kevin McHale": 82, "Robert Parish": 85,
    "Dennis Johnson": 76, "Danny Ainge": 76, "Cedric Maxwell": 80, "Tiny Archibald": 73,
    "Gerald Henderson": 74, "Scott Wedman": 79, "Isiah Thomas": 73, "Joe Dumars": 75,
    "Adrian Dantley": 77, "Bill Laimbeer": 83, "Dennis Rodman": 79, "Mark Aguirre": 78,
    "Vinnie Johnson": 74, "Rick Mahorn": 82, "James Edwards": 84, "John Salley": 83,
    "Julius Erving": 78, "Charles Barkley": 78, "Moses Malone": 82, "Andrew Toney": 75,
    "Maurice Cheeks": 73, "Bobby Jones": 81, "Darryl Dawkins": 83, "Clint Richardson": 75,
    "Steve Mix": 79, "Clemon Johnson": 82, "Hakeem Olajuwon": 84, "Ralph Sampson": 88,
    "Rodney McCray": 79, "Lewis Lloyd": 78, "Robert Reid": 80, "John Lucas": 75,
    "Allen Leavell": 73, "Mitchell Wiggins": 76, "Jim Petersen": 82, "Caldwell Jones": 83,
    # 1990s Bulls / 2000s Spurs / 2010s GSW (curated; usually DB-overridden)
    "Michael Jordan": 78, "Scottie Pippen": 80, "Toni Kukoc": 82, "Horace Grant": 82,
    "B.J. Armstrong": 74, "Ron Harper": 78, "Steve Kerr": 75, "Luc Longley": 86,
    "John Paxson": 74, "Tim Duncan": 83, "Tony Parker": 74, "Manu Ginobili": 78,
    "David Robinson": 85, "Bruce Bowen": 79, "Michael Finley": 79, "Robert Horry": 82,
    "Stephen Jackson": 80, "Brent Barry": 79, "Rasho Nesterovic": 84, "Stephen Curry": 74,
    "Kevin Durant": 82, "Klay Thompson": 78, "Draymond Green": 78, "Andre Iguodala": 78,
    "David Lee": 81, "Harrison Barnes": 80, "Shaun Livingston": 79, "Andrew Bogut": 84,
    "Festus Ezeli": 83,
}


def _p(name, pos, ppg, rpg, apg, spg, bpg, bpm, team, decade, elig=()):
    return PlayerStats(
        name=name, position=pos, ppg=ppg, rpg=rpg, apg=apg, spg=spg, bpg=bpg,
        bpm=bpm, team=team, season=decade, decade=decade, eligible_positions=elig,
        height_in=_HEIGHTS.get(name, _POS_DEFAULT_H.get(pos, 78)),
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
    "1980s|Chicago Bulls": [
        # MJ & Pippen are enriched from real 1980s data + rating overrides; the
        # rest are curated 1980s Bulls (early-decade and mid/late-decade mix).
        _p("Michael Jordan", "SG", 32.6, 5.8, 5.0, 2.7, 0.9, 9.5, "CHI", "1980s", ("SG", "SF")),
        _p("Scottie Pippen", "SF", 14.4, 6.0, 3.5, 1.8, 0.7, 4.0, "CHI", "1980s", ("SF", "PF")),
        _p("Horace Grant", "PF", 9.3, 7.2, 1.4, 0.9, 0.9, 2.0, "CHI", "1980s", ("PF", "C")),
        _p("Charles Oakley", "PF", 12.4, 12.1, 2.4, 1.0, 0.5, 2.5, "CHI", "1980s", ("PF", "C")),
        _p("Artis Gilmore", "C", 17.0, 9.5, 2.0, 0.5, 2.0, 4.0, "CHI", "1980s", ("C",)),
        _p("Reggie Theus", "SG", 18.5, 3.2, 5.5, 1.3, 0.2, 3.0, "CHI", "1980s", ("SG", "PG")),
        _p("Orlando Woolridge", "SF", 17.0, 4.6, 2.0, 0.7, 0.9, 3.0, "CHI", "1980s", ("SF", "PF")),
        _p("Dave Corzine", "C", 9.0, 6.5, 2.0, 0.5, 0.9, 1.0, "CHI", "1980s", ("C",)),
        _p("Quintin Dailey", "SG", 15.1, 2.6, 2.7, 0.7, 0.2, 1.0, "CHI", "1980s", ("SG",)),
        _p("John Paxson", "PG", 9.0, 1.6, 4.2, 0.8, 0.1, 1.0, "CHI", "1980s", ("PG",)),
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

# --- Pre-1996 legends: a few top teams per decade (curated) -----------------
# stats.nba.com lacks reliable advanced metrics (and steals/blocks) before the
# mid-1990s, so the 1960s-1980s come from curated pools instead of the pipeline.
# Steals/blocks are ~0 pre-1973-74 (not tracked); impact (bpm) is hand-set.
HISTORICAL_POOL.update({
    "1960s|Boston Celtics": [
        _p("Bill Russell", "C", 15.1, 22.7, 4.3, 0.0, 0.0, 8.5, "BOS", "1960s", ("C", "PF")),
        _p("Bob Cousy", "PG", 17.0, 4.8, 7.8, 0.0, 0.0, 4.5, "BOS", "1960s", ("PG",)),
        _p("John Havlicek", "SF", 18.0, 6.0, 4.0, 0.0, 0.0, 5.0, "BOS", "1960s", ("SF", "SG")),
        _p("Sam Jones", "SG", 18.9, 4.9, 2.7, 0.0, 0.0, 4.0, "BOS", "1960s", ("SG",)),
        _p("Tom Heinsohn", "PF", 18.6, 8.8, 2.0, 0.0, 0.0, 2.5, "BOS", "1960s", ("PF", "SF")),
        _p("Bill Sharman", "SG", 18.0, 3.8, 3.0, 0.0, 0.0, 3.0, "BOS", "1960s", ("SG", "PG")),
        _p("K.C. Jones", "PG", 7.6, 3.2, 4.3, 0.0, 0.0, 2.0, "BOS", "1960s", ("PG", "SG")),
        _p("Frank Ramsey", "SF", 13.0, 5.0, 1.8, 0.0, 0.0, 1.5, "BOS", "1960s", ("SF", "SG")),
        _p("Tom Sanders", "PF", 9.6, 6.3, 1.1, 0.0, 0.0, 1.0, "BOS", "1960s", ("PF", "SF")),
        _p("Don Nelson", "SF", 10.2, 5.1, 1.4, 0.0, 0.0, 1.0, "BOS", "1960s", ("SF", "PF")),
    ],
    "1960s|Los Angeles Lakers": [
        _p("Wilt Chamberlain", "C", 24.0, 23.9, 4.1, 0.0, 0.0, 9.0, "LAL", "1960s", ("C",)),
        _p("Jerry West", "SG", 27.0, 5.8, 6.3, 0.0, 0.0, 7.5, "LAL", "1960s", ("PG", "SG")),
        _p("Elgin Baylor", "SF", 27.4, 13.5, 4.0, 0.0, 0.0, 7.0, "LAL", "1960s", ("SF", "PF")),
        _p("Gail Goodrich", "PG", 14.0, 3.0, 4.1, 0.0, 0.0, 3.0, "LAL", "1960s", ("PG", "SG")),
        _p("Dick Barnett", "SG", 16.0, 3.2, 3.3, 0.0, 0.0, 2.5, "LAL", "1960s", ("SG", "PG")),
        _p("Rudy LaRusso", "PF", 15.0, 9.0, 2.0, 0.0, 0.0, 2.5, "LAL", "1960s", ("PF", "SF")),
        _p("Happy Hairston", "PF", 12.0, 10.5, 1.4, 0.0, 0.0, 2.0, "LAL", "1960s", ("PF", "C")),
        _p("Jim McMillian", "SF", 13.0, 5.2, 2.4, 0.0, 0.0, 2.0, "LAL", "1960s", ("SF",)),
        _p("LeRoy Ellis", "C", 11.0, 9.0, 1.2, 0.0, 0.0, 1.5, "LAL", "1960s", ("C", "PF")),
        _p("Mel Counts", "C", 8.0, 6.8, 1.8, 0.0, 0.0, 1.0, "LAL", "1960s", ("C", "PF")),
    ],
    "1970s|New York Knicks": [
        _p("Walt Frazier", "PG", 20.0, 6.2, 6.3, 1.9, 0.2, 6.0, "NYK", "1970s", ("PG", "SG")),
        _p("Willis Reed", "C", 18.0, 12.0, 2.0, 0.0, 0.0, 5.0, "NYK", "1970s", ("C", "PF")),
        _p("Earl Monroe", "SG", 17.0, 3.0, 4.0, 1.0, 0.1, 4.0, "NYK", "1970s", ("SG", "PG")),
        _p("Dave DeBusschere", "PF", 16.0, 11.0, 2.8, 0.7, 0.5, 4.0, "NYK", "1970s", ("PF", "SF")),
        _p("Bill Bradley", "SF", 12.4, 3.2, 3.4, 0.6, 0.1, 2.5, "NYK", "1970s", ("SF",)),
        _p("Jerry Lucas", "PF", 11.0, 10.0, 3.3, 0.5, 0.3, 3.0, "NYK", "1970s", ("PF", "C")),
        _p("Dick Barnett", "SG", 11.0, 2.6, 3.0, 0.0, 0.0, 2.0, "NYK", "1970s", ("SG", "PG")),
        _p("Cazzie Russell", "SF", 13.0, 4.0, 2.0, 0.0, 0.0, 2.0, "NYK", "1970s", ("SF", "SG")),
        _p("Phil Jackson", "PF", 7.0, 5.0, 1.2, 0.8, 0.5, 1.0, "NYK", "1970s", ("SF", "PF")),
        _p("Dean Meminger", "PG", 6.4, 2.2, 3.0, 1.0, 0.1, 1.0, "NYK", "1970s", ("PG", "SG")),
    ],
    "1970s|Milwaukee Bucks": [
        _p("Kareem Abdul-Jabbar", "C", 30.4, 15.3, 4.3, 1.0, 3.0, 9.5, "MIL", "1970s", ("C",)),
        _p("Oscar Robertson", "PG", 18.0, 6.0, 8.2, 1.0, 0.1, 6.0, "MIL", "1970s", ("PG", "SG")),
        _p("Bob Dandridge", "SF", 18.6, 7.0, 3.2, 1.2, 0.4, 4.0, "MIL", "1970s", ("SF",)),
        _p("Jon McGlocklin", "SG", 14.0, 3.0, 3.2, 0.5, 0.1, 2.5, "MIL", "1970s", ("SG", "PG")),
        _p("Lucius Allen", "PG", 13.0, 3.2, 4.2, 1.3, 0.2, 2.5, "MIL", "1970s", ("PG", "SG")),
        _p("Bob Boozer", "PF", 11.0, 6.2, 1.6, 0.0, 0.0, 1.5, "MIL", "1970s", ("PF", "SF")),
        _p("Greg Smith", "PF", 9.0, 7.0, 2.0, 0.5, 0.4, 1.5, "MIL", "1970s", ("PF", "SF")),
        _p("Curtis Perry", "PF", 8.0, 8.0, 1.3, 0.8, 0.6, 1.0, "MIL", "1970s", ("PF", "C")),
        _p("Wali Jones", "PG", 9.0, 2.0, 3.2, 0.7, 0.1, 1.0, "MIL", "1970s", ("PG", "SG")),
        _p("Dick Cunningham", "C", 4.0, 5.5, 0.8, 0.2, 0.4, 0.5, "MIL", "1970s", ("C",)),
    ],
    "1980s|Boston Celtics": [
        _p("Larry Bird", "SF", 25.0, 10.0, 6.3, 1.7, 0.8, 8.0, "BOS", "1980s", ("SF", "PF")),
        _p("Kevin McHale", "PF", 18.0, 7.4, 1.9, 0.4, 1.9, 5.0, "BOS", "1980s", ("PF", "C")),
        _p("Robert Parish", "C", 16.5, 10.0, 1.6, 0.9, 1.9, 4.0, "BOS", "1980s", ("C",)),
        _p("Dennis Johnson", "PG", 13.0, 4.0, 6.4, 1.2, 0.4, 3.0, "BOS", "1980s", ("PG", "SG")),
        _p("Danny Ainge", "SG", 12.0, 3.0, 4.4, 1.2, 0.2, 3.0, "BOS", "1980s", ("SG", "PG")),
        _p("Cedric Maxwell", "PF", 13.0, 6.0, 2.4, 0.9, 0.5, 3.0, "BOS", "1980s", ("PF", "SF")),
        _p("Tiny Archibald", "PG", 12.0, 2.4, 7.2, 1.0, 0.1, 3.0, "BOS", "1980s", ("PG",)),
        _p("Bill Walton", "C", 7.6, 6.8, 2.1, 0.5, 1.3, 2.5, "BOS", "1980s", ("C", "PF")),
        _p("Gerald Henderson", "SG", 9.0, 2.0, 3.4, 1.1, 0.1, 1.5, "BOS", "1980s", ("SG", "PG")),
        _p("Scott Wedman", "SF", 8.0, 3.0, 1.4, 0.6, 0.3, 1.0, "BOS", "1980s", ("SF", "PF")),
    ],
    "1980s|Detroit Pistons": [
        _p("Isiah Thomas", "PG", 20.0, 3.8, 9.6, 1.9, 0.3, 5.0, "DET", "1980s", ("PG",)),
        _p("Joe Dumars", "SG", 16.0, 2.4, 4.8, 0.9, 0.1, 4.0, "DET", "1980s", ("SG", "PG")),
        _p("Adrian Dantley", "SF", 20.0, 5.5, 3.0, 0.8, 0.1, 4.0, "DET", "1980s", ("SF", "PF")),
        _p("Bill Laimbeer", "C", 13.5, 10.5, 2.0, 0.6, 0.7, 3.0, "DET", "1980s", ("C", "PF")),
        _p("Dennis Rodman", "SF", 9.0, 8.8, 1.0, 0.7, 0.7, 4.0, "DET", "1980s", ("SF", "PF")),
        _p("Mark Aguirre", "SF", 16.0, 4.0, 3.0, 0.6, 0.2, 3.0, "DET", "1980s", ("SF", "PF")),
        _p("Vinnie Johnson", "SG", 12.0, 3.0, 3.4, 0.8, 0.1, 2.0, "DET", "1980s", ("SG", "PG")),
        _p("Rick Mahorn", "PF", 7.0, 7.0, 1.2, 0.6, 0.9, 2.0, "DET", "1980s", ("PF", "C")),
        _p("James Edwards", "C", 9.0, 4.0, 0.9, 0.3, 0.6, 1.5, "DET", "1980s", ("C",)),
        _p("John Salley", "PF", 7.0, 5.0, 1.0, 0.6, 1.4, 2.0, "DET", "1980s", ("PF", "C")),
    ],
})

HISTORICAL_POOL.update({
    "1960s|Philadelphia 76ers": [
        _p("Wilt Chamberlain", "C", 33.0, 24.0, 5.5, 0.0, 0.0, 10.0, "PHI", "1960s", ("C",)),
        _p("Billy Cunningham", "SF", 20.0, 9.0, 3.5, 0.0, 0.0, 5.0, "PHI", "1960s", ("SF", "PF")),
        _p("Hal Greer", "SG", 20.0, 5.0, 4.5, 0.0, 0.0, 5.0, "PHI", "1960s", ("SG", "PG")),
        _p("Chet Walker", "SF", 18.0, 8.0, 2.0, 0.0, 0.0, 4.0, "PHI", "1960s", ("SF", "PF")),
        _p("Luke Jackson", "PF", 12.0, 9.0, 2.0, 0.0, 0.0, 3.0, "PHI", "1960s", ("PF", "C")),
        _p("Wali Jones", "PG", 13.0, 3.0, 4.0, 0.0, 0.0, 2.0, "PHI", "1960s", ("PG", "SG")),
        _p("Larry Costello", "PG", 11.0, 2.5, 3.6, 0.0, 0.0, 2.0, "PHI", "1960s", ("PG",)),
        _p("Dave Gambee", "PF", 10.0, 5.0, 1.0, 0.0, 0.0, 1.0, "PHI", "1960s", ("PF", "SF")),
        _p("Matt Guokas", "SG", 7.0, 3.0, 3.0, 0.0, 0.0, 1.0, "PHI", "1960s", ("SG", "PG")),
        _p("Bill Melchionni", "PG", 6.0, 1.5, 2.6, 0.0, 0.0, 0.5, "PHI", "1960s", ("PG", "SG")),
    ],
    "1960s|Cincinnati Royals": [
        _p("Oscar Robertson", "PG", 30.3, 8.0, 10.4, 0.0, 0.0, 9.0, "SAC", "1960s", ("PG", "SG")),
        _p("Jerry Lucas", "PF", 19.0, 19.1, 3.2, 0.0, 0.0, 6.0, "SAC", "1960s", ("PF", "C")),
        _p("Jack Twyman", "SF", 19.0, 6.5, 2.5, 0.0, 0.0, 4.0, "SAC", "1960s", ("SF",)),
        _p("Bob Boozer", "PF", 16.0, 8.5, 1.6, 0.0, 0.0, 3.0, "SAC", "1960s", ("PF", "SF")),
        _p("Wayne Embry", "C", 14.0, 10.0, 2.0, 0.0, 0.0, 3.0, "SAC", "1960s", ("C",)),
        _p("Adrian Smith", "SG", 12.0, 3.0, 3.1, 0.0, 0.0, 2.0, "SAC", "1960s", ("SG", "PG")),
        _p("Arlen Bockhorn", "SG", 11.0, 4.0, 4.0, 0.0, 0.0, 2.0, "SAC", "1960s", ("SG", "PG")),
        _p("Connie Dierking", "C", 11.0, 8.0, 1.2, 0.0, 0.0, 1.5, "SAC", "1960s", ("C", "PF")),
        _p("Tom Hawkins", "SF", 10.0, 7.0, 1.1, 0.0, 0.0, 1.0, "SAC", "1960s", ("SF", "PF")),
        _p("Tom Van Arsdale", "SG", 14.0, 4.0, 2.5, 0.0, 0.0, 2.0, "SAC", "1960s", ("SG", "SF")),
    ],
    "1970s|Boston Celtics": [
        _p("John Havlicek", "SF", 22.0, 7.0, 6.0, 1.2, 0.3, 6.5, "BOS", "1970s", ("SF", "SG")),
        _p("Dave Cowens", "C", 19.0, 14.0, 4.0, 1.1, 0.9, 6.0, "BOS", "1970s", ("C", "PF")),
        _p("Jo Jo White", "PG", 19.0, 4.0, 5.5, 1.2, 0.2, 4.0, "BOS", "1970s", ("PG", "SG")),
        _p("Paul Silas", "PF", 11.0, 12.0, 3.0, 0.9, 0.4, 4.0, "BOS", "1970s", ("PF", "C")),
        _p("Charlie Scott", "SG", 16.0, 3.5, 4.0, 1.3, 0.2, 3.0, "BOS", "1970s", ("SG", "PG")),
        _p("Paul Westphal", "PG", 12.0, 2.0, 3.2, 1.2, 0.3, 3.0, "BOS", "1970s", ("PG", "SG")),
        _p("Don Nelson", "SF", 12.0, 5.0, 2.0, 0.4, 0.2, 2.0, "BOS", "1970s", ("SF", "PF")),
        _p("Don Chaney", "SG", 10.0, 4.0, 3.0, 1.5, 0.6, 2.0, "BOS", "1970s", ("SG", "PG")),
        _p("Steve Kuberski", "PF", 7.0, 5.0, 1.0, 0.3, 0.2, 1.0, "BOS", "1970s", ("PF", "SF")),
        _p("Dave Bing", "PG", 13.0, 3.0, 5.0, 1.0, 0.2, 3.0, "BOS", "1970s", ("PG", "SG")),
    ],
    "1970s|Los Angeles Lakers": [
        _p("Jerry West", "PG", 25.0, 4.5, 8.3, 1.5, 0.5, 7.5, "LAL", "1970s", ("PG", "SG")),
        _p("Wilt Chamberlain", "C", 16.0, 19.0, 4.1, 0.0, 0.0, 8.0, "LAL", "1970s", ("C",)),
        _p("Gail Goodrich", "SG", 22.0, 3.0, 5.0, 1.2, 0.1, 5.0, "LAL", "1970s", ("SG", "PG")),
        _p("Jim McMillian", "SF", 18.0, 6.0, 3.0, 1.0, 0.3, 3.5, "LAL", "1970s", ("SF",)),
        _p("Happy Hairston", "PF", 13.0, 13.0, 1.8, 0.7, 0.4, 3.5, "LAL", "1970s", ("PF", "C")),
        _p("Elgin Baylor", "SF", 16.0, 8.0, 3.0, 0.0, 0.0, 4.0, "LAL", "1970s", ("SF", "PF")),
        _p("Keith Erickson", "SF", 9.0, 4.0, 2.5, 1.1, 0.3, 1.5, "LAL", "1970s", ("SF", "SG")),
        _p("Flynn Robinson", "PG", 10.0, 2.0, 3.0, 0.6, 0.1, 1.5, "LAL", "1970s", ("PG", "SG")),
        _p("Pat Riley", "SG", 7.0, 2.0, 2.0, 0.7, 0.1, 1.0, "LAL", "1970s", ("SG", "PG")),
        _p("Jim Cleamons", "PG", 9.0, 3.0, 4.0, 1.4, 0.2, 1.5, "LAL", "1970s", ("PG", "SG")),
    ],
    "1970s|Portland Trail Blazers": [
        _p("Bill Walton", "C", 17.0, 13.5, 4.4, 1.0, 3.0, 7.5, "POR", "1970s", ("C", "PF")),
        _p("Maurice Lucas", "PF", 19.0, 11.0, 2.6, 1.0, 0.6, 5.0, "POR", "1970s", ("PF", "C")),
        _p("Lionel Hollins", "PG", 15.0, 3.2, 4.4, 2.0, 0.2, 3.5, "POR", "1970s", ("PG", "SG")),
        _p("Bob Gross", "SF", 11.0, 5.0, 3.0, 1.4, 0.7, 2.5, "POR", "1970s", ("SF", "PF")),
        _p("Dave Twardzik", "PG", 10.0, 2.2, 3.6, 1.4, 0.1, 2.5, "POR", "1970s", ("PG", "SG")),
        _p("Lloyd Neal", "PF", 11.0, 7.0, 1.5, 0.6, 1.0, 2.0, "POR", "1970s", ("PF", "C")),
        _p("Johnny Davis", "SG", 11.0, 2.2, 3.2, 1.0, 0.2, 1.5, "POR", "1970s", ("SG", "PG")),
        _p("Larry Steele", "SG", 9.0, 3.0, 2.6, 1.8, 0.3, 1.5, "POR", "1970s", ("SG", "PG")),
        _p("Herm Gilliam", "SG", 9.0, 2.5, 2.6, 1.1, 0.2, 1.0, "POR", "1970s", ("SG",)),
        _p("Corky Calhoun", "SF", 6.0, 3.0, 1.2, 0.6, 0.3, 0.5, "POR", "1970s", ("SF", "PF")),
    ],
    "1980s|Philadelphia 76ers": [
        _p("Julius Erving", "SF", 22.0, 7.0, 4.0, 1.7, 1.5, 6.0, "PHI", "1980s", ("SF", "PF")),
        _p("Charles Barkley", "PF", 20.0, 11.5, 3.5, 1.5, 0.8, 6.5, "PHI", "1980s", ("PF", "SF")),
        _p("Moses Malone", "C", 22.0, 13.5, 1.5, 0.9, 1.4, 6.0, "PHI", "1980s", ("C",)),
        _p("Andrew Toney", "SG", 16.0, 2.5, 5.0, 1.1, 0.2, 4.0, "PHI", "1980s", ("SG", "PG")),
        _p("Maurice Cheeks", "PG", 12.0, 2.8, 7.0, 2.3, 0.4, 4.5, "PHI", "1980s", ("PG",)),
        _p("Bobby Jones", "PF", 11.0, 5.0, 2.5, 1.4, 1.5, 4.0, "PHI", "1980s", ("PF", "SF")),
        _p("Darryl Dawkins", "C", 13.0, 7.0, 1.2, 0.5, 1.6, 2.5, "PHI", "1980s", ("C",)),
        _p("Clint Richardson", "SG", 8.0, 2.4, 2.6, 1.0, 0.3, 1.5, "PHI", "1980s", ("SG", "PG")),
        _p("Steve Mix", "SF", 9.0, 4.0, 1.6, 0.9, 0.2, 1.5, "PHI", "1980s", ("SF", "PF")),
        _p("Clemon Johnson", "C", 6.0, 5.0, 0.8, 0.4, 1.0, 1.0, "PHI", "1980s", ("C", "PF")),
    ],
    "1980s|Houston Rockets": [
        _p("Hakeem Olajuwon", "C", 23.0, 12.0, 2.0, 1.9, 3.3, 6.5, "HOU", "1980s", ("C", "PF")),
        _p("Ralph Sampson", "PF", 19.0, 10.0, 3.0, 0.9, 1.9, 4.0, "HOU", "1980s", ("PF", "C")),
        _p("Rodney McCray", "SF", 13.0, 7.0, 4.0, 1.0, 0.6, 3.0, "HOU", "1980s", ("SF", "PF")),
        _p("Lewis Lloyd", "SG", 16.0, 4.0, 4.0, 1.2, 0.2, 2.5, "HOU", "1980s", ("SG", "SF")),
        _p("Robert Reid", "SF", 13.0, 5.0, 3.0, 1.2, 0.5, 2.5, "HOU", "1980s", ("SF", "PF")),
        _p("John Lucas", "PG", 11.0, 2.2, 7.0, 1.8, 0.1, 2.5, "HOU", "1980s", ("PG",)),
        _p("Allen Leavell", "PG", 11.0, 2.2, 5.0, 1.6, 0.2, 2.0, "HOU", "1980s", ("PG", "SG")),
        _p("Mitchell Wiggins", "SG", 13.0, 3.5, 2.0, 1.1, 0.2, 1.5, "HOU", "1980s", ("SG", "SF")),
        _p("Jim Petersen", "C", 9.0, 6.0, 1.5, 0.5, 1.0, 1.5, "HOU", "1980s", ("C", "PF")),
        _p("Caldwell Jones", "C", 8.0, 7.0, 1.4, 0.4, 2.0, 2.0, "HOU", "1980s", ("C", "PF")),
    ],
})


def random_current_opponent(rng) -> tuple[str, list[PlayerStats]]:
    team = rng.choice(list(CURRENT_STARTERS.keys()))
    return team, CURRENT_STARTERS[team]


def available_draft_prompts() -> list[tuple[str, str]]:
    return [tuple(key.split("|", 1)) for key in HISTORICAL_POOL]
