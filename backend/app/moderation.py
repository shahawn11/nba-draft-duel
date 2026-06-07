"""
Lightweight content moderation + credential validation (no third-party deps).

The profanity list is intentionally small and substring-based; it catches the
obvious cases without claiming to be exhaustive. Swap in a maintained list /
service for production.
"""
from __future__ import annotations

import re

# Curated blocklist of clearly offensive substrings (lowercased).
_BLOCKLIST = {
    "fuck", "shit", "bitch", "cunt", "nigger", "nigga", "faggot", "fag",
    "retard", "rape", "rapist", "whore", "slut", "dick", "pussy", "asshole",
    "bastard", "douche", "wanker", "twat", "kike", "spic", "chink", "coon",
}

# Common leet substitutions to reduce trivial evasion.
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def _normalize(text: str) -> str:
    return (text or "").lower().translate(_LEET)


def contains_profanity(text: str) -> bool:
    norm = _normalize(text)
    collapsed = re.sub(r"[^a-z]", "", norm)  # also catch spaced/punctuated evasions
    return any(b in norm or b in collapsed for b in _BLOCKLIST)


def validate_username(name: str) -> str | None:
    """Return an error message, or None if the username is acceptable."""
    name = (name or "").strip()
    if not _USERNAME_RE.match(name):
        return "Username must be 3-20 characters: letters, numbers, or underscore."
    if name.lower().startswith("guest_"):
        return "Username can't start with 'guest_'."
    if contains_profanity(name):
        return "Please choose a different username."
    return None


def validate_password(pw: str) -> str | None:
    if not pw or len(pw) < 8:
        return "Password must be at least 8 characters."
    if len(pw) > 128:
        return "Password is too long."
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "Password must include at least one letter and one number."
    return None


def validate_display_name(name: str) -> str | None:
    name = (name or "").strip()
    if len(name) > 24:
        return "Name is too long (max 24)."
    if contains_profanity(name):
        return "Please choose a different name."
    return None
