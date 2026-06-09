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

import json
import os
from dataclasses import dataclass, field
from typing import Literal

from . import rating

Position = Literal["PG", "SG", "SF", "PF", "C"]
CANONICAL_POSITIONS: tuple[Position, ...] = ("PG", "SG", "SF", "PF", "C")

# ---- Final blended overall (2K + BBRef 50/50, curated) ---------------------
# The canonical per-(player, decade, team) overall lives in this exported file.
# It is the SOURCE OF TRUTH for a draftable player's rating: score_player()
# returns it directly when present, so tiers, cost and duel power all agree with
# the curated blend. Players not in the file (e.g. current-season opponents,
# uncurated seed stints) fall back to the live formula below.
_FINAL_RATINGS_PATH = os.path.join(os.path.dirname(__file__), "data", "k2_final_ratings.json")
_FINAL_RATINGS: dict[str, float] | None = None


def _final_ratings() -> dict[str, float]:
    global _FINAL_RATINGS
    if _FINAL_RATINGS is None:
        try:
            with open(_FINAL_RATINGS_PATH) as f:
                _FINAL_RATINGS = {k: float(v) for k, v in json.load(f).items()}
        except (OSError, ValueError):
            _FINAL_RATINGS = {}
    return _FINAL_RATINGS


def final_overall(name: str, decade: str, team: str) -> float | None:
    """The curated blended overall for a (player, decade, team), or None."""
    if not (name and decade and team):
        return None
    return _final_ratings().get(f"{name}|{decade}|{team}")


# ---- Current-form blend (offline-mode opponents) ---------------------------
# Active players are rated by CURRENT FORM -- their NBA 2K "current" card blended
# 50/50 with this season's BBRef -- rather than the decade/peak blend used for
# the draftable history. Keyed by players.db display name; gated to the current
# season so it ONLY affects current-NBA opponents, never the draft pool.
_CURRENT_RATINGS_PATH = os.path.join(os.path.dirname(__file__), "data", "current_ratings.json")
_CURRENT_RATINGS: dict[str, float] | None = None
_CURRENT_SEASON: str | None = None


def _current_ratings() -> dict[str, float]:
    global _CURRENT_RATINGS, _CURRENT_SEASON
    if _CURRENT_RATINGS is None:
        try:
            with open(_CURRENT_RATINGS_PATH) as f:
                data = json.load(f)
            _CURRENT_SEASON = data.pop("__season__", None)
            _CURRENT_RATINGS = {k: float(v) for k, v in data.items()}
        except (OSError, ValueError):
            _CURRENT_RATINGS, _CURRENT_SEASON = {}, None
    return _CURRENT_RATINGS


def current_overall(name: str) -> float | None:
    """Current-form blended overall for an active player, or None if unlisted.
    Gating to offline opponents is done by the caller via PlayerStats.current_form."""
    if not name:
        return None
    return _current_ratings().get(name)

# ---- Tunable weights -------------------------------------------------------
# Box-score composite. Steals & blocks are intentionally NOT scored here: they
# weren't tracked before 1973-74, so counting them would unfairly penalize
# pre-1974 players (their values are 0). Defense is instead represented by the
# era-neutral impact metric below (PIE-derived for modern players, hand-set for
# curated legends). Steals/blocks are still shown on the draft cards & box score.
W_PTS, W_REB, W_AST = 1.0, 1.2, 1.5
W_STL, W_BLK = 0.0, 0.0   # excluded from rating (see note above)
# Shooting-efficiency scaling for the scoring term. Points are weighted by the
# player's True Shooting % vs a league baseline, so efficient volume scorers
# (Curry, Durant) are rewarded and inefficient chuckers aren't. Capped so it's a
# meaningful nudge, not a runaway. Unknown TS% (pre-1974 / unmatched) -> 1.0.
TS_BASELINE = 0.53
TS_EFF_MIN, TS_EFF_MAX = 0.85, 1.25


def ts_efficiency(ts_pct: float) -> float:
    if not ts_pct:
        return 1.0
    return max(TS_EFF_MIN, min(TS_EFF_MAX, ts_pct / TS_BASELINE))


# Extra defensive credit on top of total BPM: box DBPM under-weights elite
# defense (even DPOYs cap ~+3-4), so we add a bonus on positive DBPM. It only
# RESCUES under-rated defenders up to a ceiling -- it never inflates players who
# already rate above it from offense/impact (so two-way stars aren't double-paid).
DEF_BONUS_PER_DBPM = 4.0
DEF_BONUS_MAX = 12.0
DEF_BONUS_CEIL = 76.0


def defensive_bonus(dbpm: float) -> float:
    if dbpm <= 0:
        return 0.0
    return min(DEF_BONUS_MAX, dbpm * DEF_BONUS_PER_DBPM)
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
# ---- Per-player duel simulation (Layer #1 stretch + #3 sim + #4 tier mult) --
# Each player plays ONE simulated game. We de-compress the rating off a floor
# (#1, mild), amplify it by tier (#4), fold in the matchup's fit/size/hot-slump
# adjustment, then add a random performance swing (#3). The team's REAL result
# is the SUM of its five simulated scores; winning a positional matchup adds
# only a SMALL bonus on top -- so the total duel score is the true decider.
DUEL_FLOOR = 50.0       # ratings are de-compressed relative to this floor
DUEL_STRETCH = 1.5      # mild stretch: meaningful, not blown-out, separation
# Performance swing is PROPORTIONAL to a player's expected duel power: every
# player varies by ~the same PERCENTAGE around his level (a star's good/bad
# night moves more points than a role player's), rather than a flat absolute
# swing that made scrubs the most volatile in relative terms.
SIM_REL_SIGMA = 0.12    # per-player performance swing (std dev, fraction of power)
# The gem tiers (Sapphire and up) are CONSISTENT stars: their DOWNSIDE swing is
# dampened so a bad night doesn't sink them as far (the floor rises), while their
# upside is unchanged. Role players keep the full symmetric swing.
GEM_TIER_MIN = 88          # Sapphire+ (the gem-named tiers: Sapphire/Amethyst/Diamond/GOAT)
GEM_DOWNSIDE_DAMP = 0.5    # negative swings for gem tiers are halved
GOAT_DOWNSIDE_DAMP = 0.25  # GOAT (98+) is the most consistent: downside dampened further
MATCHUP_WIN_BONUS = 3.0 # small team strength bonus per positional matchup won
# Positional fit quality (added to team total, in rating points). Slots are
# forced, so balance is automatic; instead we judge how well each player suits
# their slot. A slot expects a signature stat -- a PG should create (assists),
# a center should rebound -- and players short of it are penalized while strong
# fits earn a small bonus. (attr, expected, weight, good_label, bad_note)
# Penalty side (UNCHANGED): a player short of a slot's expected primary stat is
# nudged down. PF/C size is judged by HEIGHT (a tall big isn't "undersized" even
# with modest rebounds); falls back to rebounds only when height is unknown.
SLOT_EXPECTATION: dict[str, dict] = {
    "PG": {"primary": ("apg", 5.0, 0.6), "good": "floor general", "bad": "not a true PG"},
    "SG": {"primary": ("ppg", 16.0, 0.2), "good": "scoring guard", "bad": "pass-first SG"},
    "SF": {"primary": ("ppg", 14.0, 0.2), "good": "scoring wing", "bad": "secondary scorer at SF"},
    "PF": {"primary": ("height_in", 80.0, 0.35), "fallback": ("rpg", 6.0, 0.5),
           "good": "good size at PF", "bad": "undersized PF"},
    "C": {"primary": ("height_in", 82.0, 0.45), "fallback": ("rpg", 9.0, 0.7),
          "good": "true center", "bad": "undersized at C"},
}
MAX_FIT_PENALTY = 1.0       # cap on per-player fit penalty (penalties stay light)
# A SG who scores little is only "pass-first" if he ACTUALLY creates (assists);
# otherwise he's just a limited scorer at the slot.
SG_PASSFIRST_APG = 4.5

# Bonus side (NEW, the strategic lever): hitting a slot's SIGNATURE quality earns
# a STEPPED bonus -- multiple cutoffs so even a lower-minutes player who clears
# the first tier is still rewarded, while elite production is worth much more.
# The signature is a value FUNCTION of the player (SF rewards all-around
# versatility = pts+reb+ast, not pure scoring). Highest tier met wins.
# slot -> (value_fn, [(threshold, bonus, label), ...] descending)
FIT_BONUS_TIERS: dict[str, tuple] = {
    "PG": (lambda p: p.apg or 0.0, [
        (10.0, 3.0, "court maestro"),
        (8.0, 2.0, "elite floor general"),
        (6.0, 1.0, "true point guard")]),
    "SG": (lambda p: p.ppg or 0.0, [
        (26.0, 3.0, "flamethrower"),
        (22.0, 2.0, "bucket-getter"),
        (18.0, 1.0, "scoring guard")]),
    "SF": (lambda p: (p.ppg or 0.0) + (p.rpg or 0.0) + (p.apg or 0.0), [
        (44.0, 3.0, "point forward"),
        (36.0, 2.0, "two-way force"),
        (28.0, 1.0, "do-it-all wing")]),
    "PF": (lambda p: p.rpg or 0.0, [
        (11.0, 3.0, "the enforcer"),
        (9.0, 2.0, "glass cleaner"),
        (7.0, 1.0, "rebounding forward")]),
    "C": (lambda p: p.rpg or 0.0, [
        (14.0, 3.0, "the brick wall"),
        (12.0, 2.0, "glass dominator"),
        (9.0, 1.0, "rebounding center")]),
}
# Stat-stuffing bonuses (slot-independent, stack on top of the signature bonus):
# a player who averages a double/triple-double is valuable anywhere.
DOUBLE_DOUBLE_BONUS = 1.5   # >=10 in two of pts/reb/ast
TRIPLE_DOUBLE_BONUS = 3.0   # >=10 in all three (rare -- a jackpot)
# Size/physical mismatch at a matchup. Uses real height (inches) when both
# players have it, else falls back to a rebounding proxy. Weighted to matter --
# player matchups are the focus, especially for PvP.
HEIGHT_MISMATCH_WEIGHT = 0.5    # rating points per inch of height gap
HEIGHT_MISMATCH_THRESHOLD = 4.0 # inches gap that counts as a notable mismatch
SIZE_MISMATCH_WEIGHT = 0.5      # rating points per rebound of size gap (fallback)
SIZE_MISMATCH_THRESHOLD = 4.0   # rebound gap that counts (fallback)
MAX_SIZE_MISMATCH = 4.0         # cap on the per-matchup nudge
# Hot / Slump: rolled once per team -- a random player runs hot or cold. This
# is applied PURELY as a proportional multiplier on the player's simulated duel
# score (HOT_SIM_MULT/SLUMP_SIM_MULT) -- the rare "career night" / "ice cold"
# swing on top of normal variance. It does NOT change his rating. The higher
# (or lower) duel score then flows through to his box-score statline (see
# game._simulate_box), so a hot player also puts up bigger numbers.
HOT_CHANCE = 0.02
SLUMP_CHANCE = 0.01
HOT_SIM_MULT = 1.20             # hot: simulated duel score multiplied up
SLUMP_SIM_MULT = 0.78           # slump: simulated duel score multiplied down


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
    # True Shooting % (0 = unknown -> neutral). Scales the scoring term so
    # efficient volume scorers (Curry, Durant) are rewarded and chuckers aren't.
    ts_pct: float = 0.0
    # Defensive Box Plus/Minus (real, 1973-74+). Drives an extra defensive bonus
    # so elite stoppers/rim-protectors (Mutombo, Ben Wallace) get credit the
    # total-BPM impact half under-weights.
    dbpm: float = 0.0
    # 3-point shooting (1979-80+; 0 = none/pre-3pt era).
    three_pa: float = 0.0
    three_pct: float = 0.0
    # Manual rating override (0-100). 0 = none; when set, score_player returns
    # this as the player's total (a curated correction for formula outliers).
    rating_override: float = 0.0
    # True only for current-NBA offline opponents: rate by CURRENT FORM (the
    # current-form blend keyed by name), never the decade/peak blend. Draft-pool
    # players leave this False so their rating path is unchanged.
    current_form: bool = False

    def eligible(self) -> tuple[str, ...]:
        return self.eligible_positions if self.eligible_positions else (self.position,)

    def production(self) -> float:
        """Raw box-score composite. Scoring is scaled by shooting efficiency
        (True Shooting %) vs a league baseline, so points scored efficiently are
        worth more. Unknown TS% (pre-1974 / unmatched) -> neutral 1.0."""
        return (
            self.ppg * W_PTS * ts_efficiency(self.ts_pct)
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
    home_sim: float = 0.0     # simulated duel score this game (decides the matchup)
    away_sim: float = 0.0
    home_sim_delta: float = 0.0  # duel-score points from bonuses/penalties (signed)
    away_sim_delta: float = 0.0


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
    # Per-player performance factor = simulated score / expected power (~1.0 is
    # an average night, >1 a good game, <1 a poor one). Drives the box score.
    home_perf: dict = field(default_factory=dict)
    away_perf: dict = field(default_factory=dict)

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
    # Current-NBA opponents (offline mode): rate by CURRENT FORM -- the player's
    # 2K current card blended with this season's BBRef. Flagged at build time,
    # so draft-pool combos (current_form=False) fall through to the decade blend.
    if p.current_form:
        cf = current_overall(p.name)
        if cf is not None:
            return PlayerScore(player=p, production=prod, advanced=adv, total=cf)
    # Primary source: the curated 2K+BBRef blended overall for this exact
    # (player, decade, team). Already final (overrides + era-cap baked in), so
    # it is used as-is -- no formula, no tier-rounding.
    blended = final_overall(p.name, p.decade, p.team)
    if blended is not None:
        return PlayerScore(player=p, production=prod, advanced=adv, total=blended)
    # Fallback (opponents / uncurated stints): live formula + overrides.
    total = prod * PRODUCTION_WEIGHT + adv * ADVANCED_WEIGHT
    if p.rating_override:
        total = p.rating_override   # curated correction (drives tier + duel)
    else:
        # Extra defensive credit, but only to RESCUE under-rated defenders up to
        # a ceiling (never inflates players already above it from offense).
        total = max(total, min(total + defensive_bonus(p.dbpm), DEF_BONUS_CEIL))
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
        delta = 0.0
        # --- Penalty (unchanged): short of the slot's expected primary stat ---
        spec = SLOT_EXPECTATION.get(p.position)
        if spec:
            attr, expected, weight = spec["primary"]
            value = getattr(p, attr)
            is_height = attr == "height_in"
            if is_height and not value and "fallback" in spec:
                attr, expected, weight = spec["fallback"]
                value = getattr(p, attr)
                is_height = False
            if value < expected:
                pen = min(MAX_FIT_PENALTY, round((expected - value) * weight, 1))
                if pen >= 0.1:
                    delta -= pen
                    if is_height:
                        detail = format_height(value)
                    elif attr == "rpg":
                        detail = "low rebounds"
                    elif attr == "apg":
                        detail = "low assists"
                    else:
                        detail = "low scoring"
                    bad_label = spec["bad"]
                    # "Pass-first SG" only fits if he actually creates; a low-
                    # scoring AND low-assist guard is just a limited scorer.
                    if p.position == "SG" and (p.apg or 0.0) < SG_PASSFIRST_APG:
                        bad_label = "limited scorer at SG"
                    notes.append(f"{p.name} — {bad_label} ({detail}) (-{pen:.1f})")

        # --- Bonus (stepped): clearing a signature-quality cutoff earns a bonus ---
        sig = FIT_BONUS_TIERS.get(p.position)
        if sig:
            value_fn, tiers = sig
            v = value_fn(p)
            for thresh, bonus, label in tiers:   # descending -> highest met wins
                if v >= thresh:
                    delta += bonus
                    notes.append(f"{p.name} — {label} (+{bonus:.1f})")
                    break

        # --- Stat-stuffing bonus (slot-independent): double / triple-double ---
        n10 = sum(1 for s in (p.ppg, p.rpg, p.apg) if (s or 0.0) >= 10.0)
        if n10 >= 3:
            delta += TRIPLE_DOUBLE_BONUS
            notes.append(f"{p.name} — triple-double machine (+{TRIPLE_DOUBLE_BONUS:.1f})")
        elif n10 == 2:
            delta += DOUBLE_DOUBLE_BONUS
            notes.append(f"{p.name} — double-double threat (+{DOUBLE_DOUBLE_BONUS:.1f})")

        if abs(delta) >= 0.05:
            adjustment += delta
            deltas[p.name] = round(delta, 1)

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
    # `status` (hot/slump) no longer alters a player's RATING -- it is applied
    # purely as a multiplier on the simulated duel score (see _sim_score). We
    # keep the param + the empty status_deltas for payload compatibility.
    scores = [score_player(p) for p in players]
    status_deltas: dict[str, float] = {}
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


def duel_power(rating_value: float, eff_adjust: float = 0.0) -> float:
    """A player's expected 'duel power' (pre-randomness).

    Layer #1 (stretch): de-compress the rating off DUEL_FLOOR so a 2-point
    rating edge becomes a meaningful gap -- mildly, not blown out.
    Layer #4 (tier): amplify ONLY the player's intrinsic rating by his tier
    multiplier, so a true elite is decisively valuable. Tier is taken from the
    TRUE base rating, so a bonus never bumps someone into a higher tier.

    `eff_adjust` (positional fit + size/height mismatch) is a matchup
    bonus/penalty. It is added AFTER the tier multiply -- stretched to the duel
    scale but NOT tier-amplified -- so the same +2 fit edge is worth the same
    duel points to a GOAT and to a role player. This keeps high tiers from
    compounding their multiplier on top of situational bonuses.
    """
    tier_m = rating.tier_mult(rating_value)
    intrinsic = max(0.0, rating_value - DUEL_FLOOR) * DUEL_STRETCH * tier_m
    bonus = eff_adjust * DUEL_STRETCH    # tier-independent
    return max(0.0, intrinsic + bonus)


def _sim_score(rng, rating_value: float, eff_adjust: float,
               status: str | None) -> tuple[float, float]:
    """One player's simulated duel score for the night, plus the portion of it
    attributable to bonuses/penalties.

    Layer #3 (variance): a PROPORTIONAL swing -- the score moves by a random
    PERCENTAGE of the player's expected power, so a star's good/bad night is a
    bigger point swing than a role player's, but everyone varies by the same
    relative amount. Hot/Slump (rare) then FURTHER multiplies the score up/down
    on top of the normal swing -- the career-night / ice-cold game.

    Returns (score, bonus_delta) where bonus_delta is how many duel-score points
    the player gained/lost vs a clean baseline (no fit/size adjust, no hot/slump)
    under the SAME random swing -- i.e. the net effect of bonuses & penalties.
    """
    swing = rng.gauss(0.0, SIM_REL_SIGMA)
    # Gem tiers don't fall as far on a bad night (floor rises, upside unchanged);
    # GOAT is the most consistent of all, so its downside is dampened the most.
    if swing < 0:
        if rating_value >= 98:
            swing *= GOAT_DOWNSIDE_DAMP
        elif rating_value >= GEM_TIER_MIN:
            swing *= GEM_DOWNSIDE_DAMP
    swing = 1.0 + swing
    score = duel_power(rating_value, eff_adjust) * swing
    baseline = max(0.0, duel_power(rating_value, 0.0) * swing)
    if status == "hot":
        score *= HOT_SIM_MULT
    elif status == "slump":
        score *= SLUMP_SIM_MULT
    score = max(0.0, score)
    return score, round(score - baseline, 1)


# How far a player's box-score line can stretch from his per-game averages on a
# great/poor night. Keeps statlines believable (a 1.0 night = his averages).
PERF_MIN = 0.40
PERF_MAX = 2.10


def _perf_factor(sim: float, expected: float) -> float:
    """How well a player performed vs his expected level (sim / expected),
    clamped so a hot night inflates -- but never breaks -- his statline."""
    if expected <= 1e-6:
        return 1.0
    return max(PERF_MIN, min(PERF_MAX, sim / expected))


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

    # ---- Per-player simulation -------------------------------------------
    # Each player plays ONE simulated game: expected duel power (stretch + tier
    # mult + the matchup's fit/size/hot-slump adjustment) swung by a random
    # PROPORTIONAL performance factor, then -- if he's hot or slumping (rare) --
    # FURTHER multiplied up or down. The matchup winner is whoever had the
    # better *simulated* game (a small upset is possible -- the lower-rated
    # player can outplay the favorite that night). The team's real result is the
    # SUM of its five simulated scores; each matchup won adds only a small bonus.
    home_sim_total = 0.0
    away_sim_total = 0.0
    home_wins = 0
    away_wins = 0
    home_perf: dict[str, float] = {}
    away_perf: dict[str, float] = {}
    for m in matchups:
        if m.home_player != "(none)":
            h_exp = duel_power(m.home_score, m.home_delta)
            h_sim, h_sim_delta = _sim_score(rng, m.home_score, m.home_delta,
                                            home_status.get(m.home_player))
            home_perf[m.home_player] = _perf_factor(h_sim, h_exp)
            m.home_sim_delta = h_sim_delta
        else:
            h_sim = 0.0
        if m.away_player != "(none)":
            a_exp = duel_power(m.away_score, m.away_delta)
            a_sim, a_sim_delta = _sim_score(rng, m.away_score, m.away_delta,
                                            away_status.get(m.away_player))
            away_perf[m.away_player] = _perf_factor(a_sim, a_exp)
            m.away_sim_delta = a_sim_delta
        else:
            a_sim = 0.0
        m.home_sim = round(h_sim, 1)
        m.away_sim = round(a_sim, 1)
        home_sim_total += h_sim
        away_sim_total += a_sim
        if abs(h_sim - a_sim) < 1e-9:
            m.winner = "tie"
        elif h_sim > a_sim:
            m.winner = "home"
            home_wins += 1
        else:
            m.winner = "away"
            away_wins += 1

    # Total simulated score is the true decider; matchup wins are a small bonus.
    home_strength = home_sim_total + home_wins * MATCHUP_WIN_BONUS
    away_strength = away_sim_total + away_wins * MATCHUP_WIN_BONUS

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
        home_perf=home_perf,
        away_perf=away_perf,
    )
