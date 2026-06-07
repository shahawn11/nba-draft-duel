"""
Era-accurate team names.

Rosters are stored under each franchise's CURRENT name (so data joins are
stable), but for historical decades we display the name the franchise actually
used then (e.g. 1990s Oklahoma City Thunder -> Seattle SuperSonics). This is a
DISPLAY-only mapping; pool keys and stored data keep the modern name.

Keyed by (current_name, decade). Anything not listed keeps its stored name.
"""
from __future__ import annotations

_ERA_NAMES: dict[str, dict[str, str]] = {
    # Seattle SuperSonics -> moved to Oklahoma City in 2008.
    "Oklahoma City Thunder": {
        "1970s": "Seattle SuperSonics",
        "1980s": "Seattle SuperSonics",
        "1990s": "Seattle SuperSonics",
        "2000s": "Seattle SuperSonics",
    },
    # Vancouver Grizzlies -> moved to Memphis in 2001.
    "Memphis Grizzlies": {
        "1990s": "Vancouver Grizzlies",
    },
    # New Jersey Nets -> moved to Brooklyn in 2012.
    "Brooklyn Nets": {
        "1970s": "New Jersey Nets",
        "1980s": "New Jersey Nets",
        "1990s": "New Jersey Nets",
        "2000s": "New Jersey Nets",
    },
    # Washington Bullets -> renamed Wizards in 1997.
    "Washington Wizards": {
        "1960s": "Baltimore Bullets",
        "1970s": "Washington Bullets",
        "1980s": "Washington Bullets",
        "1990s": "Washington Bullets",
    },
    # Current Charlotte franchise was the Bobcats (2004-2014) before reclaiming
    # the Hornets name. (The 1990s "Charlotte Hornets" are the original Hornets.)
    "Charlotte Hornets": {
        "2000s": "Charlotte Bobcats",
    },
    # New Orleans Hornets (2002-2013) -> renamed Pelicans in 2013.
    "New Orleans Pelicans": {
        "2000s": "New Orleans Hornets",
    },
}


def era_team_name(team: str, decade: str) -> str:
    """Return the franchise's era-accurate name for a decade (or the stored
    name if there's no historical difference)."""
    return _ERA_NAMES.get(team, {}).get(decade, team)
