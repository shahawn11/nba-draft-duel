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

# The 8 named tiers on the blended 0-100 overall. ONE source of truth carrying
# both the salary-cap COST and the per-tier DUEL MULTIPLIER (Layer #4):
#   * cost  -> flat price within the tier for the draft economy.
#   * mult  -> amplifies the player's contribution to the simulated duel so a
#              true elite is decisively valuable, not just a 1-2 point edge.
# Costs are re-tuned (sim-validated) for the compressed-high blended scale,
# where ~84% of players sit >=80; budget 250 over 5 slots keeps stacking elites
# infeasible while a full team is always affordable. Descending by min rating.
# (id, label, min player-rating inclusive, flat cost, duel multiplier)
CAP_TIERS: list[dict] = [
    {"id": "goat",     "label": "GOAT",     "min": 98, "cost": 82, "mult": 1.30},
    {"id": "diamond",  "label": "Diamond",  "min": 96, "cost": 75, "mult": 1.20},
    {"id": "amethyst", "label": "Amethyst", "min": 93, "cost": 63, "mult": 1.10},
    {"id": "sapphire", "label": "Sapphire", "min": 88, "cost": 54, "mult": 1.06},
    {"id": "gold",     "label": "Gold",     "min": 84, "cost": 46, "mult": 1.03},
    {"id": "silver",   "label": "Silver",   "min": 82, "cost": 40, "mult": 1.00},
    {"id": "bronze",   "label": "Bronze",   "min": 80, "cost": 34, "mult": 0.97},
    {"id": "unranked", "label": "Unranked", "min": 0,  "cost": 28, "mult": 0.94},
]

CHEAPEST_COST = min(t["cost"] for t in CAP_TIERS)   # floor used by feasibility


# ---------------------------------------------------------------------------
# Duel tiers are the SAME 8 bands (CAP_TIERS), reused so cost + multiplier never
# drift apart. duel_tier()/tier_mult() read the shared list.
DUEL_TIERS = CAP_TIERS


def duel_tier(player_rating: float) -> dict:
    """8-band tier dict for a player's 0-100 overall (GOAT ... Unranked)."""
    for t in DUEL_TIERS:
        if player_rating >= t["min"]:
            return t
    return DUEL_TIERS[-1]


def tier_mult(player_rating: float) -> float:
    """Per-tier duel-power multiplier (Layer #4)."""
    return duel_tier(player_rating)["mult"]


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
    """Identity on the blended scale. The old "round up into the next tier"
    snap was designed for the coarse 10-wide formula bands; the curated blended
    overall sits on fine 2-3 wide bands where snapping would mis-tier players
    (a curated 95 Amethyst must not jump to Diamond). Kept as a stable hook for
    the formula fallback path."""
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
