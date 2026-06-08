"""
Rating ladder. Players start at 1000 and can't drop below 0. The win/loss
delta depends on the player's CURRENT tier (climbing gets slower, falling
hurts more). Ties don't change rating.

All tunable here -- thresholds and deltas live in TIERS.
"""
from __future__ import annotations

START_RATING = 1000
MIN_RATING = 0

# (name, min_rating, win_delta, loss_delta), ascending by min_rating.
# `id` is the stable key used for the unlockable rank avatar; `emblem` is the
# cartoon avatar motif for that tier.
TIERS: list[dict] = [
    {"id": "amateur", "name": "Amateur", "emblem": "shirt", "min": 0, "win": 10, "loss": -2},
    {"id": "pro", "name": "Pro", "emblem": "basketball", "min": 1500, "win": 8, "loss": -3},
    {"id": "allstar", "name": "All-Star", "emblem": "star", "min": 4000, "win": 7, "loss": -4},
    {"id": "veteran", "name": "Veteran", "emblem": "trophy", "min": 8000, "win": 7, "loss": -5},
    {"id": "hof", "name": "Hall-of-Fame", "emblem": "crown", "min": 18000, "win": 6, "loss": -5},
    {"id": "goat", "name": "GOAT", "emblem": "goat", "min": 50000, "win": 4, "loss": -5},
]


def tier_by_id(tier_id: str) -> dict | None:
    for t in TIERS:
        if t["id"] == tier_id:
            return t
    return None


def unlocked_avatar_ids(peak_rating: int) -> list[str]:
    """Rank-avatar ids unlocked by a player's PEAK rating (permanent once earned).
    Amateur (brown shirt) is always unlocked."""
    return [t["id"] for t in TIERS if peak_rating >= t["min"]]


# Achievement avatars — unlocked by accomplishments rather than rating. Each id
# is also the avatar's emblem key on the frontend.
ACHIEVEMENTS: list[dict] = [
    {"id": "games25", "name": "Veteran Presence", "how": "Play 25 games"},
    {"id": "wins100", "name": "Centurion", "how": "Win 100 games"},
    {"id": "hot", "name": "Heat Check", "how": "Have a player catch fire (Hot)"},
    {"id": "slump", "name": "Cold Snap", "how": "Have a player go cold (Slump)"},
    {"id": "fifty", "name": "Bucket Getter", "how": "Have a player score 50"},
    {"id": "tripledouble", "name": "Stat Sheet Stuffer", "how": "Have a player record a triple-double"},
]
ACHIEVEMENT_IDS = {a["id"] for a in ACHIEVEMENTS}


# Win streaks: a 🔥 shows at this many straight wins, and each win while on a
# streak grants bonus rating: 3rd straight = +1, 4th = +2, 5th+ = +3.
STREAK_MIN = 3


def streak_bonus(win_streak: int) -> int:
    """Extra rating granted for a win, given the streak count AFTER this win."""
    if win_streak < STREAK_MIN:
        return 0
    return min(3, win_streak - 2)   # 3->1, 4->2, 5+->3


# ---------------------------------------------------------------------------
# Salary cap (draft economy)
#
# Every draftable player has a TIER, derived from their 0-100 player rating
# (scoring.score_player().total), and a flat COST within that tier. A fixed
# team BUDGET makes stacking superstars impossible while keeping them worth it:
#   * flat-within-tier  -> the higher-rated player in the same tier is FREE
#                          upside (pull Jokić over a peer S and you just win
#                          that pick at the same cost).
#   * mild-convex gaps   -> a star is a real spend, never a trap or a steal.
# Enforcement is a HARD cap with a PICK-TIME FEASIBILITY guard: you can't draft
# a player if doing so would leave you unable to fill your remaining slots at
# the cheapest cost. (No "grace" overage — that lets you stack 3 stars.)
#
# Numbers locked via blind-draft simulation (budget-planner beats a careless
# spender ~61%; 5 stars impossible; S drafted ~1/3 of games).
CAP_BUDGET = 250

# (id, label, min player-rating inclusive, flat cost). Descending by min.
CAP_TIERS: list[dict] = [
    {"id": "S", "label": "Diamond", "min": 80, "cost": 80},
    {"id": "A", "label": "A", "min": 70, "cost": 62},
    {"id": "B", "label": "B", "min": 60, "cost": 50},
    {"id": "C", "label": "C", "min": 50, "cost": 38},
    {"id": "D", "label": "D", "min": 35, "cost": 28},
    {"id": "E", "label": "E", "min": 0,  "cost": 18},
]

CHEAPEST_COST = min(t["cost"] for t in CAP_TIERS)   # floor used by feasibility


# Manual rating overrides (0-100 scale), keyed by (player, decade, team) so only
# the player's prime stint is corrected -- other teams/decades keep their real
# formula rating (e.g. Westbrook's Houston year, Love's Cavs years, Wade's Bulls
# cameo stay as computed). The override sets the score DIRECTLY, so tier, cost,
# and in-duel strength all agree. Team is the full franchise name (pool key).
RATING_OVERRIDES: dict[tuple[str, str, str], float] = {
    # Too high -> lowered (prime team only)
    ("Russell Westbrook", "2010s", "Oklahoma City Thunder"): 82.0,
    ("Kevin Love", "2010s", "Minnesota Timberwolves"): 78.0,
    # Too low -> raised
    ("Stephen Curry", "2010s", "Golden State Warriors"): 80.0,
    ("Kobe Bryant", "2000s", "Los Angeles Lakers"): 80.0,
    ("Scottie Pippen", "1990s", "Chicago Bulls"): 70.0,
    ("John Stockton", "1990s", "Utah Jazz"): 70.0,
    # All-time greats (tunable)
    ("Michael Jordan", "1990s", "Chicago Bulls"): 92.0,
    ("Michael Jordan", "1980s", "Chicago Bulls"): 88.0,
    ("LeBron James", "2010s", "Miami Heat"): 92.0,           # peak
    ("LeBron James", "2010s", "Cleveland Cavaliers"): 88.0,  # 2nd Cleveland stint
    ("Dwyane Wade", "2000s", "Miami Heat"): 88.0,
    ("Dwyane Wade", "2010s", "Miami Heat"): 78.0,
    # Buried by the formula (shooters/defenders: no 3-pt / defense credit) -> raised
    ("Klay Thompson", "2010s", "Golden State Warriors"): 62.0,
    ("Reggie Miller", "1990s", "Indiana Pacers"): 63.0,
    ("Ray Allen", "2000s", "Milwaukee Bucks"): 63.0,
    ("Dikembe Mutombo", "1990s", "Denver Nuggets"): 63.0,
    ("Tony Parker", "2000s", "San Antonio Spurs"): 63.0,
    ("Chauncey Billups", "2000s", "Detroit Pistons"): 62.0,
    ("Manu Ginobili", "2000s", "San Antonio Spurs"): 61.0,
    ("Steve Nash", "2000s", "Phoenix Suns"): 72.0,
    ("George Gervin", "1980s", "San Antonio Spurs"): 72.0,
    ("Ben Wallace", "2000s", "Detroit Pistons"): 63.0,   # 4x DPOY (defense uncounted)
}


# Players to force into a (decade, team) draft pool even if they miss the
# scoring-based top-10 -- e.g. elite defenders who never scored much. Pair with
# a RATING_OVERRIDES entry so their rating reflects their real value.
POOL_FORCE_INCLUDE: dict[tuple[str, str], list[str]] = {
    ("2000s", "Detroit Pistons"): ["Ben Wallace"],
}


def tier_round(player_rating: float) -> float:
    """Round a rating that sits in the top point of a tier UP into the next one,
    so a 59.x lands B, 69.x lands A, 79.x lands S (and 49.x lands C). Avoids the
    "just missed the tier" feel for borderline stars (e.g. Carmelo 59.1, a
    Finals-MVP Kawhi season at 69.5). Not applied at the low D/E boundary."""
    for t in CAP_TIERS:
        if t["min"] >= 50 and t["min"] - 1.0 <= player_rating < t["min"]:
            return float(t["min"])
    return player_rating


def player_tier(player_rating: float) -> dict:
    """Tier dict for a player's 0-100 rating (S/A/B/C/D), boundary-rounded."""
    r = tier_round(player_rating)
    for t in CAP_TIERS:
        if r >= t["min"]:
            return t
    return CAP_TIERS[-1]


def player_cost(player_rating: float) -> int:
    return player_tier(player_rating)["cost"]


def is_affordable(spent: int, cost: int, slots_left: int,
                  budget: int = CAP_BUDGET) -> bool:
    """Pick-time feasibility: can we take this `cost` for one of `slots_left`
    open slots and still fill the remaining (slots_left-1) at the cheapest cost
    without exceeding the budget?"""
    return spent + cost + (slots_left - 1) * CHEAPEST_COST <= budget


def tier_for(rating: int) -> dict:
    cur = TIERS[0]
    for t in TIERS:
        if rating >= t["min"]:
            cur = t
    return cur


def tier_name(rating: int) -> str:
    return tier_for(rating)["name"]


def apply_outcome(rating: int, outcome: str) -> int:
    """Return the new rating after a win/loss/tie, clamped at MIN_RATING."""
    t = tier_for(rating)
    if outcome == "win":
        rating += t["win"]
    elif outcome == "loss":
        rating += t["loss"]
    return max(MIN_RATING, rating)


def next_tier(rating: int) -> dict | None:
    """The next tier up (for progress display), or None at the top."""
    for t in TIERS:
        if t["min"] > rating:
            return t
    return None
