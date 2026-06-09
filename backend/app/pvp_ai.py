"""
Persistent PvP AI opponents.

When no human is found in the queue within the wait window, a match is filled by
an AI playing as one of these accounts. They are REAL accounts: wins/losses and
rating persist, so they climb/fall the ladder and appear on the leaderboard like
any player.

The username IS the display name (like a human signup) -- these handles are
reserved for the AI. A guard ensures the AI never adopts a username already held
by a registered human (so it can't hijack a real account/record).
"""
from __future__ import annotations

import random

from . import db

# Realistic basketball/NBA-flavored handles (username == display name).
AI_USERNAMES: list[str] = [
    "MambaForever24", "bb_braydon", "dreamzzz23", "swishgod",
    "ankle_breaker", "downtown_dwill", "DameDolla", "splash_bro30",
    "bucketzzz", "kingofthe4th", "crossover21", "wrecker",
    "boardman_gets_paid", "Iso_Joe", "death_machine", "Fadeaway",
    "Euro_Bro", "DaReal", "clutch_gene21", "netripper99",
    "greenlight", "And1", "Visonzz", "Icyy",
    "BBL_Drizzy", "Westbrick",
]

_ensured: set[str] = set()


def pick_ai_identity(rng: random.Random | None = None) -> str:
    """Choose an AI account (creating it on first use) and return its username.
    Skips any handle already registered by a human, so a real account is never
    hijacked. Reused across matches so each AI builds a real record."""
    rng = rng or random.Random()
    pool = rng.sample(AI_USERNAMES, len(AI_USERNAMES))  # randomized order
    for username in pool:
        if db.account_exists(username):
            continue  # a real human holds this name -- never hijack it
        if username not in _ensured:
            db.ensure_user(username)
            db.set_display_name(username, username, force=True)
            _ensured.add(username)
        return username
    # Extremely unlikely fallback: every handle taken by humans -> a transient one.
    fallback = f"cpu_{rng.randint(1000, 9999)}"
    db.ensure_user(fallback)
    db.set_display_name(fallback, fallback, force=True)
    return fallback
