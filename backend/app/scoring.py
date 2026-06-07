"""
Scoring engine for NBA Draft Duel.

Given two starting-5 lineups, compute a deterministic winner based on:
  1. Player production  (per-game box-score composite)
  2. Advanced metric    (BPM-style ceiling/impact)
  3. Positional fit      (does the 5 cover PG/SG/SF/PF/C cleanly?)
  4. Head-to-head matchups (your PG vs their PG, etc.)

The result is fully explainable: every sub-score is returned so the UI can
say "you won 3 of 5 positional matchups and had the deeper bench score".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Position = Literal["PG", "SG", "SF", "PF", "C"]
CANONICAL_POSITIONS: tuple[Position, ...] = ("PG", "SG", "SF", "PF", "C")

# ---- Tunable weights -------------------------------------------------------
# Box-score composite weights (fantasy-ish, rewards two-way production).
W_PTS, W_REB, W_AST, W_STL, W_BLK = 1.0, 1.2, 1.5, 3.0, 3.0
# Blend between raw production and advanced impact metric.
PRODUCTION_WEIGHT = 0.65
ADVANCED_WEIGHT = 0.35
# Final blend between cumulative team total and head-to-head matchup wins.
TEAM_TOTAL_WEIGHT = 0.70
MATCHUP_WEIGHT = 0.30
# Positional fit bonuses/penalties (added to team total, in score points).
PERFECT_FIT_BONUS = 6.0
MISSING_POSITION_PENALTY = 4.0
DUPLICATE_POSITION_PENALTY = 2.0


@dataclass(frozen=True)
class PlayerStats:
    """Per-game averages + an advanced impact metric for one player-season."""
    name: str
    position: Position
    ppg: float = 0.0
    rpg: float = 0.0
    apg: float = 0.0
    spg: float = 0.0
    bpg: float = 0.0
    bpm: float = 0.0          # Box Plus/Minus (impact, can be negative)
    # Provenance (where this player was drafted from)
    team: str = ""
    season: str = ""
    decade: str = ""
    # Slots this player may be drafted into (PG/SG/SF/PF/C). Empty => single
    # slot equal to `position`. Genuine combos list multiple.
    eligible_positions: tuple[str, ...] = ()

    def eligible(self) -> tuple[str, ...]:
        return self.eligible_positions if self.eligible_positions else (self.position,)

    def production(self) -> float:
        """Raw box-score composite."""
        return (
            self.ppg * W_PTS
            + self.rpg * W_REB
            + self.apg * W_AST
            + self.spg * W_STL
            + self.bpg * W_BLK
        )


@dataclass
class PlayerScore:
    player: PlayerStats
    production: float
    advanced: float
    total: float


@dataclass
class MatchupResult:
    position: Position
    home_player: str
    away_player: str
    home_score: float
    away_score: float
    winner: Literal["home", "away", "tie"]


@dataclass
class TeamScore:
    player_scores: list[PlayerScore] = field(default_factory=list)
    base_total: float = 0.0          # sum of player totals
    fit_adjustment: float = 0.0      # positional fit bonus/penalty
    fit_notes: list[str] = field(default_factory=list)

    @property
    def adjusted_total(self) -> float:
        return self.base_total + self.fit_adjustment


@dataclass
class DuelResult:
    winner: Literal["home", "away", "tie"]
    home_final: float
    away_final: float
    home: TeamScore
    away: TeamScore
    matchups: list[MatchupResult]
    home_matchup_wins: int
    away_matchup_wins: int

    def summary(self) -> str:
        if self.winner == "tie":
            verdict = "It's a dead heat!"
        else:
            side = "Home" if self.winner == "home" else "Away"
            verdict = f"{side} wins {self.home_final:.1f} - {self.away_final:.1f}"
        return (
            f"{verdict} | matchups {self.home_matchup_wins}-{self.away_matchup_wins}"
        )


# ---- Normalization ---------------------------------------------------------
# Production scales roughly 0-60 for elite two-way stars; BPM scales ~ -5..+12.
# We map both onto a comparable ~0-100 scale before blending.
def _normalize_production(raw: float) -> float:
    # 60 raw composite -> 100. Clamp for sanity.
    return max(0.0, min(100.0, (raw / 60.0) * 100.0))


def _normalize_advanced(bpm: float) -> float:
    # BPM of +12 -> 100, 0 -> ~29, -5 -> 0. Linear shift/scale.
    return max(0.0, min(100.0, ((bpm + 5.0) / 17.0) * 100.0))


def score_player(p: PlayerStats) -> PlayerScore:
    prod = _normalize_production(p.production())
    adv = _normalize_advanced(p.bpm)
    total = prod * PRODUCTION_WEIGHT + adv * ADVANCED_WEIGHT
    return PlayerScore(player=p, production=prod, advanced=adv, total=total)


# ---- Positional fit --------------------------------------------------------
def evaluate_fit(players: list[PlayerStats]) -> tuple[float, list[str]]:
    counts: dict[str, int] = {}
    for p in players:
        counts[p.position] = counts.get(p.position, 0) + 1

    notes: list[str] = []
    adjustment = 0.0

    missing = [pos for pos in CANONICAL_POSITIONS if counts.get(pos, 0) == 0]
    duplicates = {pos: c for pos, c in counts.items() if c > 1}

    if not missing and not duplicates and len(players) == 5:
        adjustment += PERFECT_FIT_BONUS
        notes.append(f"Perfect positional balance (+{PERFECT_FIT_BONUS:.0f})")
    else:
        for pos in missing:
            adjustment -= MISSING_POSITION_PENALTY
            notes.append(f"No {pos} on the floor (-{MISSING_POSITION_PENALTY:.0f})")
        for pos, c in duplicates.items():
            extra = c - 1
            pen = DUPLICATE_POSITION_PENALTY * extra
            adjustment -= pen
            notes.append(f"{c} players at {pos} (-{pen:.0f})")

    return adjustment, notes


def score_team(players: list[PlayerStats]) -> TeamScore:
    scores = [score_player(p) for p in players]
    base_total = sum(s.total for s in scores)
    fit_adj, fit_notes = evaluate_fit(players)
    return TeamScore(
        player_scores=scores,
        base_total=base_total,
        fit_adjustment=fit_adj,
        fit_notes=fit_notes,
    )


# ---- Head-to-head matchups -------------------------------------------------
def _by_position(scores: list[PlayerScore]) -> dict[str, PlayerScore]:
    """Best scorer per position (handles duplicates by keeping the top one)."""
    out: dict[str, PlayerScore] = {}
    for s in scores:
        pos = s.player.position
        if pos not in out or s.total > out[pos].total:
            out[pos] = s
    return out


def compute_matchups(home: TeamScore, away: TeamScore) -> list[MatchupResult]:
    home_map = _by_position(home.player_scores)
    away_map = _by_position(away.player_scores)
    results: list[MatchupResult] = []
    for pos in CANONICAL_POSITIONS:
        h = home_map.get(pos)
        a = away_map.get(pos)
        h_score = h.total if h else 0.0
        a_score = a.total if a else 0.0
        if abs(h_score - a_score) < 1e-6:
            winner = "tie"
        elif h_score > a_score:
            winner = "home"
        else:
            winner = "away"
        results.append(
            MatchupResult(
                position=pos,
                home_player=h.player.name if h else "(none)",
                away_player=a.player.name if a else "(none)",
                home_score=h_score,
                away_score=a_score,
                winner=winner,
            )
        )
    return results


def duel(home_players: list[PlayerStats], away_players: list[PlayerStats]) -> DuelResult:
    home = score_team(home_players)
    away = score_team(away_players)
    matchups = compute_matchups(home, away)

    home_wins = sum(1 for m in matchups if m.winner == "home")
    away_wins = sum(1 for m in matchups if m.winner == "away")

    # Matchup component scaled to be comparable to team totals (max 5 wins).
    # Express matchup edge as a points swing relative to team-total magnitude.
    matchup_swing = (home_wins - away_wins) * 6.0  # each matchup ~6 pts

    home_final = home.adjusted_total * TEAM_TOTAL_WEIGHT + max(0.0, matchup_swing) * MATCHUP_WEIGHT
    away_final = away.adjusted_total * TEAM_TOTAL_WEIGHT + max(0.0, -matchup_swing) * MATCHUP_WEIGHT

    if abs(home_final - away_final) < 1e-6:
        winner = "tie"
    elif home_final > away_final:
        winner = "home"
    else:
        winner = "away"

    return DuelResult(
        winner=winner,
        home_final=home_final,
        away_final=away_final,
        home=home,
        away=away,
        matchups=matchups,
        home_matchup_wins=home_wins,
        away_matchup_wins=away_wins,
    )
