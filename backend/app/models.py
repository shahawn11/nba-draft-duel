"""Pydantic models for the API surface + PlayerStats (de)serialization."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .scoring import PlayerStats


# ---- serialization helpers -------------------------------------------------
def player_to_dict(p: PlayerStats) -> dict:
    return {
        "name": p.name,
        "position": p.position,
        "team": p.team,
        "season": p.season,
        "decade": p.decade,
        "ppg": p.ppg,
        "rpg": p.rpg,
        "apg": p.apg,
        "spg": p.spg,
        "bpg": p.bpg,
        "bpm": p.bpm,
        "height_in": p.height_in,
        "eligible_positions": list(p.eligible()),
    }


def player_from_dict(d: dict) -> PlayerStats:
    return PlayerStats(
        name=d["name"],
        position=d["position"],
        team=d.get("team", ""),
        season=d.get("season", ""),
        decade=d.get("decade", ""),
        ppg=d.get("ppg", 0.0),
        rpg=d.get("rpg", 0.0),
        apg=d.get("apg", 0.0),
        spg=d.get("spg", 0.0),
        bpg=d.get("bpg", 0.0),
        bpm=d.get("bpm", 0.0),
        height_in=d.get("height_in", 0.0),
        eligible_positions=tuple(d.get("eligible_positions", []) or []),
    )


# ---- API models ------------------------------------------------------------
class PlayerOut(BaseModel):
    name: str
    position: str
    team: str
    season: str
    decade: str
    ppg: float
    rpg: float
    apg: float
    spg: float
    bpg: float
    bpm: float
    eligible_positions: list[str]
    eligible: bool = True   # eligible for the CURRENT slot (set per step)


class NewMatchRequest(BaseModel):
    username: str = Field(min_length=1, max_length=40)


class PickRequest(BaseModel):
    player_name: str = Field(min_length=1)
    slot: str = Field(min_length=1)   # which open lineup slot to assign the player to


class ScoredPlayer(BaseModel):
    name: str
    position: str
    production: float
    advanced: float
    total: float


class MatchupOut(BaseModel):
    position: str
    home_player: str
    away_player: str
    home_score: float
    away_score: float
    winner: str


class TeamOut(BaseModel):
    base_total: float
    fit_adjustment: float
    adjusted_total: float
    fit_notes: list[str]
    players: list[ScoredPlayer]


class Record(BaseModel):
    username: str
    wins: int
    losses: int
    ties: int
    rating: int = 1000
    tier: str = "Amateur"
    next_tier: str | None = None
    next_tier_at: int | None = None


class ResultOut(BaseModel):
    match_id: str
    outcome: str          # "win" | "loss" | "tie" (from player's POV)
    your_final: float
    opponent_final: float
    opponent_team: str
    your_team: TeamOut
    opponent_team_scored: TeamOut
    matchups: list[MatchupOut]
    your_matchup_wins: int
    opponent_matchup_wins: int
    record: Record
