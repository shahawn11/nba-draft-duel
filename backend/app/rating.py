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
TIERS: list[dict] = [
    {"name": "Amateur", "min": 0, "win": 10, "loss": -2},
    {"name": "Pro", "min": 2000, "win": 8, "loss": -3},
    {"name": "All-Star", "min": 5000, "win": 7, "loss": -4},
    {"name": "Veteran", "min": 10000, "win": 6, "loss": -5},
    {"name": "Hall-of-Fame", "min": 25000, "win": 5, "loss": -5},
    {"name": "GOAT", "min": 100000, "win": 4, "loss": -5},
]


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
