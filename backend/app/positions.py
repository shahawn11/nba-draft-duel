"""
Position slots + eligibility.

The lineup has five fixed slots. A player may only be drafted into a slot they
are eligible for. Eligibility is derived from the coarse NBA position label
(stats.nba.com gives Guard / Forward / Center and hyphenated combos), so only
genuine combo players end up multi-eligible -- which is exactly the 82-0-style
constraint we want.
"""
from __future__ import annotations

SLOTS: tuple[str, ...] = ("PG", "SG", "SF", "PF", "C")

# Coarse label (lowercased, hyphen-joined) -> eligible slots.
_RAW_TO_SLOTS: dict[str, set[str]] = {
    "guard": {"PG", "SG"},
    "forward": {"SF", "PF"},
    "center": {"C"},
    "guard-forward": {"SG", "SF"},
    "forward-guard": {"SG", "SF"},
    "forward-center": {"PF", "C"},
    "center-forward": {"PF", "C"},
}

# Fallback adjacency when only a granular position (PG/SG/...) is known and no
# raw label is available. Kept tight so most players stay single-slot.
_GRANULAR_FALLBACK: dict[str, set[str]] = {
    "PG": {"PG"},
    "SG": {"SG"},
    "SF": {"SF"},
    "PF": {"PF"},
    "C": {"C"},
}


def eligible_from_raw(raw: str | None, fallback_position: str = "SF") -> tuple[str, ...]:
    """Map a coarse NBA position string to a tuple of eligible slots."""
    key = "-".join(p.strip() for p in (raw or "").lower().split("-") if p.strip())
    if key in _RAW_TO_SLOTS:
        return tuple(s for s in SLOTS if s in _RAW_TO_SLOTS[key])  # ordered
    # Unknown/empty raw: fall back to the granular position.
    fb = _GRANULAR_FALLBACK.get(fallback_position, {fallback_position})
    return tuple(s for s in SLOTS if s in fb)


def can_play(eligible: tuple[str, ...], slot: str) -> bool:
    return slot in eligible
