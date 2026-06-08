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

from . import rating

Position = Literal["PG", "SG", "SF", "PF", "C"]
CANONICAL_POSITIONS: tuple[Position, ...] = ("PG", "SG", "SF", "PF", "C")

# ---- Tunable weights -------------------------------------------------------
# Box-score composite. Steals & blocks are intentionally NOT scored here: they
# weren't tracked before 1973-74, so counting them would unfairly penalize
# pre-1974 players (their values are 0). Defense is instead represented by the
# era-neutral impact metric below (PIE-derived for modern players, hand-set for
# curated legends). Steals/blocks are still shown on the draft cards & box score.
W_PTS, W_REB, W_AST = 1.0, 1.2, 1.5
W_STL, W_BLK = 0.0, 0.0   # excluded from rating (see note above)
# Blend between raw production and the advanced (defensive-inclusive) impact
# metric. Impact (BPM/PIE) is the only era-fair carrier of defense -- steals/blocks
# aren't tracked pre-1974 -- so it's weighted equally with production to give
# defensive value (e.g. Russell, MJ) more pull without penalizing the 1960s.
PRODUCTION_WEIGHT = 0.50
ADVANCED_WEIGHT = 0.50
# Final blend between cumulative team total and head-to-head matchup wins.
TEAM_TOTAL_WEIGHT = 0.70
MATCHUP_WEIGHT = 0.30
# Realistic game-score projection.
MATCHUP_STRENGTH = 7.0    # strength points added per head-to-head matchup won
GAME_BASE = 106.0         # league-ish baseline points both teams sit near
GAME_SCALE = 0.22         # how strongly a strength gap turns into a points margin
GAME_MIN, GAME_MAX = 80, 150
# Positional fit quality (added to team total, in rating points). Slots are
# forced, so balance is automatic; instead we judge how well each player suits
# their slot. A slot expects a signature stat -- a PG should create (assists),
# a center should rebound -- and players short of it are penalized while strong
# fits earn a small bonus. (attr, expected, weight, good_label, bad_note)
SLOT_EXPECTATION: dict[str, dict] = {
    "PG": {"primary": ("apg", 5.0, 0.6), "good": "floor general", "bad": "not a true PG"},
    "SG": {"primary": ("ppg", 16.0, 0.2), "good": "scoring guard", "bad": "pass-first SG"},
    "SF": {"primary": ("ppg", 14.0, 0.2), "good": "scoring wing", "bad": "secondary scorer at SF"},
    # PF/C size is judged by HEIGHT (a tall big isn't "undersized" even with
    # modest rebounds). Falls back to rebounds only when height is unknown.
    "PF": {"primary": ("height_in", 80.0, 0.35), "fallback": ("rpg", 6.0, 0.5),
           "good": "good size at PF", "bad": "undersized PF"},
    "C": {"primary": ("height_in", 82.0, 0.45), "fallback": ("rpg", 9.0, 0.7),
          "good": "true center", "bad": "undersized at C"},
}
FIT_BONUS_SCALE = 0.25      # fraction of the surplus turned into a bonus
MAX_FIT_BONUS = 1.0         # cap on per-player fit bonus
MAX_FIT_PENALTY = 1.0       # cap on per-player fit penalty (fit is a light nudge: -1..+1)
# Size/physical mismatch at a matchup. Uses real height (inches) when both
# players have it, else falls back to a rebounding proxy. Weighted to matter --
# player matchups are the focus, especially for PvP.
HEIGHT_MISMATCH_WEIGHT = 0.5    # rating points per inch of height gap
HEIGHT_MISMATCH_THRESHOLD = 4.0 # inches gap that counts as a notable mismatch
SIZE_MISMATCH_WEIGHT = 0.5      # rating points per rebound of size gap (fallback)
SIZE_MISMATCH_THRESHOLD = 4.0   # rebound gap that counts (fallback)
MAX_SIZE_MISMATCH = 4.0         # cap on the per-matchup nudge
# Hot / Slump: rolled once per team -- a random player runs hot or cold.
HOT_CHANCE = 0.02
SLUMP_CHANCE = 0.01
HOT_RATING = 10.0
SLUMP_RATING = -10.0
HOT_STAT_MULT = 1.5             # box-score boost when hot
SLUMP_STAT_MULT = 0.55          # box-score reduction when slumping


def format_height(inches: float) -> str:
    if not inches:
        return "?"
    return f"{int(inches) // 12}'{int(inches) % 12}\""


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
    height_in: float = 0.0   # height in inches (0 = unknown)
    # Slots this player may be drafted into (PG/SG/SF/PF/C). Empty => single
    # slot equal to `position`. Genuine combos list multiple.
    eligible_positions: tuple[str, ...] = ()
    # Display-only stats. Scoring/rating use the fields above, which hold a
    # 50/50 BLEND of the player's peak season and decade average (the blend
    # tempers one-year spikes like a single MVP season). `decade_*` is the
    # games-weighted decade average and `peak_*` the single best season; both
    # are shown on the card. `peak_season` labels the peak year. All default to
    # 0/"" for curated seed players (where the single curated line is used).
    decade_ppg: float = 0.0
    decade_rpg: float = 0.0
    decade_apg: float = 0.0
    decade_spg: float = 0.0
    decade_bpg: float = 0.0
    peak_ppg: float = 0.0
    peak_rpg: float = 0.0
    peak_apg: float = 0.0
    peak_bpm: float = 0.0
    peak_season: str = ""
    # Manual rating override (0-100). 0 = none; when set, score_player returns
    # this as the player's total (a curated correction for formula outliers).
    rating_override: float = 0.0

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
    note: str = ""
    home_delta: float = 0.0   # fit + size adjustment applied to home (signed)
    away_delta: float = 0.0


@dataclass
class TeamScore:
    player_scores: list[PlayerScore] = field(default_factory=list)
    base_total: float = 0.0          # sum of player totals
    fit_adjustment: float = 0.0      # positional fit bonus/penalty (sum)
    fit_notes: list[str] = field(default_factory=list)
    fit_deltas: dict = field(default_factory=dict)  # per-player signed fit delta
    status_deltas: dict = field(default_factory=dict)  # per-player hot/slump rating delta (actual, post-clamp)

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
    overtime: bool = False
    regulation: int | None = None          # tied regulation points (if OT)
    home_status: dict = field(default_factory=dict)  # {player_name: 'hot'|'slump'}
    away_status: dict = field(default_factory=dict)

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
    if p.rating_override:
        total = p.rating_override   # curated correction (drives tier + duel)
    # Round a score sitting in the top point of a tier UP to the tier floor
    # (79.x -> 80, 69.x -> 70, ...), so the NUMBER itself rounds -- not just the
    # tier badge -- in both the displayed rating and in-duel strength.
    total = rating.tier_round(total)
    return PlayerScore(player=p, production=prod, advanced=adv, total=total)


# ---- Positional fit quality ------------------------------------------------
def evaluate_fit(players: list[PlayerStats]) -> tuple[float, list[str], dict]:
    """Judge how well each player suits the slot they're playing. Players short
    of a slot's signature stat are penalized; strong fits earn a small bonus.
    PF/C size is judged by height (rebound fallback only when height unknown).
    Returns (total_adjustment, notes, {player_name: signed_delta})."""
    notes: list[str] = []
    adjustment = 0.0
    deltas: dict[str, float] = {}

    for p in players:
        spec = SLOT_EXPECTATION.get(p.position)
        if not spec:
            continue  # SG/SF handled below via dict too; SG/SF have specs
        attr, expected, weight = spec["primary"]
        value = getattr(p, attr)
        is_height = attr == "height_in"
        if is_height and not value and "fallback" in spec:
            attr, expected, weight = spec["fallback"]
            value = getattr(p, attr)
            is_height = False

        if value < expected:
            pen = min(MAX_FIT_PENALTY, round((expected - value) * weight, 1))
            if pen < 0.1:
                continue
            adjustment -= pen
            deltas[p.name] = -pen
            if is_height:
                detail = format_height(value)
            elif attr == "rpg":
                detail = "low rebounds"
            elif attr == "apg":
                detail = "low assists"
            else:
                detail = "low scoring"
            notes.append(f"{p.name} — {spec['bad']} ({detail}) (-{pen:.1f})")
        else:
            bonus = min(MAX_FIT_BONUS, round((value - expected) * weight * FIT_BONUS_SCALE, 1))
            if bonus >= 0.5:
                adjustment += bonus
                deltas[p.name] = bonus
                notes.append(f"{p.name} — {spec['good']} (+{bonus:.1f})")

    return adjustment, notes, deltas


def roll_status(players: list[PlayerStats], rng) -> dict:
    """Per team: 2% chance a random player is hot, 1% a random player slumps."""
    if not players:
        return {}
    r = rng.random()
    if r < HOT_CHANCE:
        return {rng.choice(players).name: "hot"}
    if r < HOT_CHANCE + SLUMP_CHANCE:
        return {rng.choice(players).name: "slump"}
    return {}


def score_team(players: list[PlayerStats], status: dict | None = None) -> TeamScore:
    status = status or {}
    scores = [score_player(p) for p in players]
    status_deltas: dict[str, float] = {}
    for s in scores:
        st = status.get(s.player.name)
        if st == "hot":
            before = s.total
            s.total = min(100.0, s.total + HOT_RATING)
            status_deltas[s.player.name] = round(s.total - before, 1)
        elif st == "slump":
            before = s.total
            s.total = max(0.0, s.total + SLUMP_RATING)
            status_deltas[s.player.name] = round(s.total - before, 1)
    base_total = sum(s.total for s in scores)
    fit_adj, fit_notes, fit_deltas = evaluate_fit(players)
    return TeamScore(
        player_scores=scores,
        base_total=base_total,
        fit_adjustment=fit_adj,
        fit_notes=fit_notes,
        fit_deltas=fit_deltas,
        status_deltas=status_deltas,
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
        h_base = h.total if h else 0.0
        a_base = a.total if a else 0.0

        # Size/physical mismatch: prefer real height, fall back to rebounding.
        note = ""
        size_adj = 0.0
        if h and a:
            if h.player.height_in and a.player.height_in:
                gap = h.player.height_in - a.player.height_in  # inches
                size_adj = max(-MAX_SIZE_MISMATCH, min(MAX_SIZE_MISMATCH, gap * HEIGHT_MISMATCH_WEIGHT))
                if abs(gap) >= HEIGHT_MISMATCH_THRESHOLD:
                    big, small = (h, a) if gap > 0 else (a, h)
                    note = (f"{big.player.name} ({format_height(big.player.height_in)}) "
                            f"towers over {small.player.name} ({format_height(small.player.height_in)})")
            else:
                gap = h.player.rpg - a.player.rpg  # rebound proxy
                size_adj = max(-MAX_SIZE_MISMATCH, min(MAX_SIZE_MISMATCH, gap * SIZE_MISMATCH_WEIGHT))
                if abs(gap) >= SIZE_MISMATCH_THRESHOLD:
                    big, small = (h, a) if gap > 0 else (a, h)
                    note = f"{big.player.name} has a size edge over {small.player.name}"

        # Per-player matchup delta = positional fit + size mismatch + hot/slump.
        # Displayed score is the player's TRUE base (pre hot/slump); the status
        # boost/penalty is surfaced in the delta arrow alongside fit & size.
        h_status = home.status_deltas.get(h.player.name, 0.0) if h else 0.0
        a_status = away.status_deltas.get(a.player.name, 0.0) if a else 0.0
        h_true = h_base - h_status
        a_true = a_base - a_status
        h_bonus = max(0.0, size_adj)
        a_bonus = max(0.0, -size_adj)
        h_delta = round((home.fit_deltas.get(h.player.name, 0.0) if h else 0.0) + h_bonus + h_status, 1)
        a_delta = round((away.fit_deltas.get(a.player.name, 0.0) if a else 0.0) + a_bonus + a_status, 1)
        h_eff = h_true + h_delta
        a_eff = a_true + a_delta

        if abs(h_eff - a_eff) < 1e-6:
            winner = "tie"
        elif h_eff > a_eff:
            winner = "home"
        else:
            winner = "away"
        results.append(
            MatchupResult(
                position=pos,
                home_player=h.player.name if h else "(none)",
                away_player=a.player.name if a else "(none)",
                home_score=h_true,
                away_score=a_true,
                winner=winner,
                note=note,
                home_delta=h_delta,
                away_delta=a_delta,
            )
        )
    return results


def _project_points(strength: float, avg: float) -> int:
    """Map a team's blended strength onto a realistic NBA points total."""
    pts = GAME_BASE + (strength - avg) * GAME_SCALE
    return int(round(max(float(GAME_MIN), min(float(GAME_MAX), pts))))


def duel(home_players: list[PlayerStats], away_players: list[PlayerStats],
         home_status: dict | None = None, away_status: dict | None = None,
         rng=None) -> DuelResult:
    import random as _random
    rng = rng or _random.Random()
    home_status = home_status or {}
    away_status = away_status or {}
    home = score_team(home_players, home_status)
    away = score_team(away_players, away_status)
    matchups = compute_matchups(home, away)

    home_wins = sum(1 for m in matchups if m.winner == "home")
    away_wins = sum(1 for m in matchups if m.winner == "away")

    home_strength = home.base_total + home_wins * MATCHUP_STRENGTH
    away_strength = away.base_total + away_wins * MATCHUP_STRENGTH

    avg = (home_strength + away_strength) / 2.0
    home_pts = _project_points(home_strength, avg)
    away_pts = _project_points(away_strength, avg)

    overtime = False
    regulation = None
    if home_pts == away_pts:
        # Regulation tie -> overtime. Stronger lineup tends to win OT.
        overtime = True
        regulation = home_pts
        if home_strength > away_strength:
            ot_winner = "home"
        elif away_strength > home_strength:
            ot_winner = "away"
        else:
            ot_winner = rng.choice(["home", "away"])
        w_ot = rng.randint(8, 14)
        l_ot = rng.randint(3, w_ot - 2)
        if ot_winner == "home":
            home_pts, away_pts = regulation + w_ot, regulation + l_ot
        else:
            away_pts, home_pts = regulation + w_ot, regulation + l_ot

    winner = "home" if home_pts > away_pts else "away"

    return DuelResult(
        winner=winner,
        home_final=float(home_pts),
        away_final=float(away_pts),
        home=home,
        away=away,
        matchups=matchups,
        home_matchup_wins=home_wins,
        away_matchup_wins=away_wins,
        overtime=overtime,
        regulation=regulation,
        home_status=home_status,
        away_status=away_status,
    )
