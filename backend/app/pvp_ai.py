"""
Persistent PvP AI opponents.

When no human is found in the queue within the wait window, a match is filled by
an AI playing as one of these accounts. Unlike the old cosmetic "Guest", these
are REAL accounts: their wins/losses and rating persist, so they climb/fall the
ladder and appear on the leaderboard like any player.

Usernames are internal handles (prefixed `cpu_`, never shown) so they can't
collide with human signups; the basketball-flavored display_name is what players
see (via db.name_label / frontend nameLabel).
"""
from __future__ import annotations

import random

from . import db

# (internal username, shown display name) -- common basketball/NBA-flavored tags.
AI_ACCOUNTS: list[tuple[str, str]] = [
    ("cpu_buckets", "Buckets"),
    ("cpu_swishking", "SwishKing"),
    ("cpu_anklebreaker", "AnkleBreaker"),
    ("cpu_downtown", "Downtown"),
    ("cpu_dimedropper", "DimeDropper"),
    ("cpu_glasscleaner", "GlassCleaner"),
    ("cpu_sharpshooter", "Sharpshooter"),
    ("cpu_postup", "PostUp"),
    ("cpu_fastbreak", "FastBreak"),
    ("cpu_tripledouble", "TripleDouble"),
    ("cpu_crossover", "Crossover"),
    ("cpu_splash", "SplashBro"),
    ("cpu_rimrocker", "RimRocker"),
    ("cpu_boardman", "BoardMan"),
    ("cpu_isojoe", "IsoJoe"),
    ("cpu_picknroll", "PickNRoll"),
    ("cpu_fadeaway", "Fadeaway"),
    ("cpu_eurostep", "Eurostep"),
    ("cpu_hooper", "Hooper24"),
    ("cpu_ballhog", "BallHawk"),
    ("cpu_clutchgene", "ClutchGene"),
    ("cpu_netripper", "NetRipper"),
    ("cpu_greenlight", "GreenLight"),
    ("cpu_andone", "AndOne"),
]

_ensured: set[str] = set()


def pick_ai_identity(rng: random.Random | None = None) -> str:
    """Choose an AI account (creating it with its display name on first use) and
    return its username. Reused across matches so each AI builds a real record."""
    rng = rng or random.Random()
    username, display = rng.choice(AI_ACCOUNTS)
    if username not in _ensured:
        db.ensure_user(username)
        db.set_display_name(username, display, force=True)
        _ensured.add(username)
    return username
