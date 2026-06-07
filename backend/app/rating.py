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
