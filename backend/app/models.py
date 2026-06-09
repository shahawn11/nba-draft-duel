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
        # display-only decade averages + peak season the rating is based on
        "decade_ppg": p.decade_ppg,
        "decade_rpg": p.decade_rpg,
        "decade_apg": p.decade_apg,
        "decade_spg": p.decade_spg,
        "decade_bpg": p.decade_bpg,
        "peak_ppg": p.peak_ppg,
        "peak_rpg": p.peak_rpg,
        "peak_apg": p.peak_apg,
        "peak_bpm": p.peak_bpm,
        "peak_season": p.peak_season,
        "ts_pct": p.ts_pct,
        "dbpm": p.dbpm,
        "three_pa": p.three_pa,
        "three_pct": p.three_pct,
        "rating_override": p.rating_override,
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
        decade_ppg=d.get("decade_ppg", 0.0),
        decade_rpg=d.get("decade_rpg", 0.0),
        decade_apg=d.get("decade_apg", 0.0),
        decade_spg=d.get("decade_spg", 0.0),
        decade_bpg=d.get("decade_bpg", 0.0),
        peak_ppg=d.get("peak_ppg", 0.0),
        peak_rpg=d.get("peak_rpg", 0.0),
        peak_apg=d.get("peak_apg", 0.0),
        peak_bpm=d.get("peak_bpm", 0.0),
        peak_season=d.get("peak_season", ""),
        ts_pct=d.get("ts_pct", 0.0),
        dbpm=d.get("dbpm", 0.0),
        three_pa=d.get("three_pa", 0.0),
        three_pct=d.get("three_pct", 0.0),
        rating_override=d.get("rating_override", 0.0),
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
    display_name: str | None = None   # guest display label


class AuthRequest(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)
    guest_id: str | None = None   # signup: transfer this guest's stats


class AvatarRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    avatar: str = Field(min_length=1, max_length=32)


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
    rating: int = 1000
    peak_rating: int = 1000
    tier: str = "Amateur"
    next_tier: str | None = None
    next_tier_at: int | None = None
    display_name: str | None = None
    avatar: str = "amateur"
    unlocked: list[str] = []
    achievements: list[str] = []
    win_streak: int = 0
    on_streak: bool = False
    best_streak: int = 0
    best_team_strength: float = 0
    best_team: list | None = None


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
