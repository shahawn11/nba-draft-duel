"""
Curated CURRENT-NBA starting fives (offline-mode opponents).

One healthy PG/SG/SF/PF/C per team, hand-picked from the real 2025-26 roster in
players.db (membership reflects actual trades). This replaces the auto-derived
"most-used lineup" fives, which were injury/trade-distorted and produced broken
position groups (e.g. four SGs). Slots here are AUTHORITATIVE -- the builder
assigns each player to the listed slot regardless of stored eligibility.

Ratings come from the current-form blend (current 2K card + this-season BBRef);
box-score stats come from each player's most-recent season row.

`*` = franchise starter who missed the current season to injury and is absent
from the 2025-26 stat pull (rated from his 2K card + last healthy season).

Format:  team -> [(player_name, slot), ...]  (names MUST match players.db exactly)
"""
from __future__ import annotations

CURATED_STARTING_FIVES: dict[str, list[tuple[str, str]]] = {
    "Atlanta Hawks": [
        ("Dyson Daniels", "PG"), ("CJ McCollum", "SG"), ("Jalen Johnson", "SF"),
        ("Zaccharie Risacher", "PF"), ("Onyeka Okongwu", "C"),
    ],
    "Boston Celtics": [
        ("Derrick White", "PG"), ("Jaylen Brown", "SG"), ("Jayson Tatum", "SF"),  # *
        ("Sam Hauser", "PF"), ("Nikola Vučević", "C"),
    ],
    "Brooklyn Nets": [
        ("Egor Dëmin", "PG"), ("Terance Mann", "SG"), ("Michael Porter Jr.", "SF"),
        ("Noah Clowney", "PF"), ("Nic Claxton", "C"),
    ],
    "Charlotte Hornets": [
        ("LaMelo Ball", "PG"), ("Kon Knueppel", "SG"), ("Brandon Miller", "SF"),
        ("Miles Bridges", "PF"), ("Ryan Kalkbrenner", "C"),
    ],
    "Chicago Bulls": [
        ("Josh Giddey", "PG"), ("Coby White", "SG"), ("Matas Buzelis", "SF"),
        ("Patrick Williams", "PF"), ("Jalen Smith", "C"),
    ],
    "Cleveland Cavaliers": [
        ("James Harden", "PG"), ("Donovan Mitchell", "SG"), ("Jaylon Tyson", "SF"),
        ("Evan Mobley", "PF"), ("Jarrett Allen", "C"),
    ],
    "Dallas Mavericks": [
        ("Ryan Nembhard", "PG"), ("Max Christie", "SG"), ("Cooper Flagg", "SF"),
        ("P.J. Washington", "PF"), ("Daniel Gafford", "C"),
    ],
    "Denver Nuggets": [
        ("Jamal Murray", "PG"), ("Christian Braun", "SG"), ("Cameron Johnson", "SF"),
        ("Aaron Gordon", "PF"), ("Nikola Jokić", "C"),
    ],
    "Detroit Pistons": [
        ("Cade Cunningham", "PG"), ("Ausar Thompson", "SG"), ("Tobias Harris", "SF"),
        ("Isaiah Stewart", "PF"), ("Jalen Duren", "C"),
    ],
    "Golden State Warriors": [
        ("Stephen Curry", "PG"), ("Brandin Podziemski", "SG"), ("Jimmy Butler III", "SF"),
        ("Draymond Green", "PF"), ("Kristaps Porziņģis", "C"),
    ],
    "Houston Rockets": [
        ("Reed Sheppard", "PG"), ("Amen Thompson", "SG"), ("Kevin Durant", "SF"),
        ("Jabari Smith Jr.", "PF"), ("Alperen Sengun", "C"),
    ],
    "Indiana Pacers": [
        ("Tyrese Haliburton", "PG"), ("Andrew Nembhard", "SG"), ("Aaron Nesmith", "SF"),  # *
        ("Pascal Siakam", "PF"), ("Ivica Zubac", "C"),
    ],
    "Los Angeles Clippers": [
        ("Darius Garland", "PG"), ("Bennedict Mathurin", "SG"), ("Kawhi Leonard", "SF"),
        ("John Collins", "PF"), ("Brook Lopez", "C"),
    ],
    "Los Angeles Lakers": [
        ("Luka Dončić", "PG"), ("Austin Reaves", "SG"), ("LeBron James", "SF"),
        ("Rui Hachimura", "PF"), ("Deandre Ayton", "C"),
    ],
    "Memphis Grizzlies": [
        ("Ja Morant", "PG"), ("Cedric Coward", "SG"), ("Jaylen Wells", "SF"),  # Morant *
        ("GG Jackson", "PF"), ("Santi Aldama", "C"),
    ],
    "Miami Heat": [
        ("Davion Mitchell", "PG"), ("Tyler Herro", "SG"), ("Andrew Wiggins", "SF"),
        ("Bam Adebayo", "PF"), ("Kel'el Ware", "C"),
    ],
    "Milwaukee Bucks": [
        ("Ryan Rollins", "PG"), ("Kevin Porter Jr.", "SG"), ("Giannis Antetokounmpo", "SF"),
        ("Bobby Portis", "PF"), ("Myles Turner", "C"),
    ],
    "Minnesota Timberwolves": [
        ("Mike Conley", "PG"), ("Anthony Edwards", "SG"), ("Jaden McDaniels", "SF"),
        ("Julius Randle", "PF"), ("Rudy Gobert", "C"),
    ],
    "New Orleans Pelicans": [
        ("Jordan Poole", "PG"), ("Saddiq Bey", "SG"), ("Trey Murphy III", "SF"),
        ("Zion Williamson", "PF"), ("Derik Queen", "C"),
    ],
    "New York Knicks": [
        ("Jalen Brunson", "PG"), ("Josh Hart", "SG"), ("OG Anunoby", "SF"),
        ("Mikal Bridges", "PF"), ("Karl-Anthony Towns", "C"),
    ],
    "Oklahoma City Thunder": [
        ("Shai Gilgeous-Alexander", "PG"), ("Luguentz Dort", "SG"), ("Jalen Williams", "SF"),
        ("Chet Holmgren", "PF"), ("Isaiah Hartenstein", "C"),
    ],
    "Orlando Magic": [
        ("Jalen Suggs", "PG"), ("Desmond Bane", "SG"), ("Franz Wagner", "SF"),
        ("Paolo Banchero", "PF"), ("Wendell Carter Jr.", "C"),
    ],
    "Philadelphia 76ers": [
        ("Tyrese Maxey", "PG"), ("VJ Edgecombe", "SG"), ("Kelly Oubre Jr.", "SF"),
        ("Paul George", "PF"), ("Joel Embiid", "C"),
    ],
    "Phoenix Suns": [
        ("Devin Booker", "PG"), ("Jalen Green", "SG"), ("Dillon Brooks", "SF"),
        ("Royce O'Neale", "PF"), ("Mark Williams", "C"),
    ],
    "Portland Trail Blazers": [
        ("Jrue Holiday", "PG"), ("Shaedon Sharpe", "SG"), ("Deni Avdija", "SF"),
        ("Jerami Grant", "PF"), ("Donovan Clingan", "C"),
    ],
    "Sacramento Kings": [
        ("Russell Westbrook", "PG"), ("Zach LaVine", "SG"), ("DeMar DeRozan", "SF"),
        ("Precious Achiuwa", "PF"), ("Maxime Raynaud", "C"),
    ],
    "San Antonio Spurs": [
        ("De'Aaron Fox", "PG"), ("Stephon Castle", "SG"), ("Devin Vassell", "SF"),
        ("Julian Champagnie", "PF"), ("Victor Wembanyama", "C"),
    ],
    "Toronto Raptors": [
        ("Immanuel Quickley", "PG"), ("RJ Barrett", "SG"), ("Brandon Ingram", "SF"),
        ("Scottie Barnes", "PF"), ("Jakob Poeltl", "C"),
    ],
    "Utah Jazz": [
        ("Keyonte George", "PG"), ("Ace Bailey", "SG"), ("Lauri Markkanen", "SF"),
        ("Jaren Jackson Jr.", "PF"), ("Jusuf Nurkić", "C"),
    ],
    "Washington Wizards": [
        ("Trae Young", "PG"), ("Bilal Coulibaly", "SG"), ("Kyshawn George", "SF"),  # Young *
        ("Anthony Davis", "PF"), ("Alex Sarr", "C"),  # Davis *
    ],
}
