# 5v5 Duel

A draft-battler inspired by [82-0.com](https://www.82-0.com/). You fill a
starting five **one slot at a time** — each pick reveals a random
**decade × NBA team** and that franchise's **10 best players for the decade**;
you choose one and assign them to an open lineup slot they're eligible for. Your
five is then scored against an opponent's in a simulated game. Win → W, lose → L.

## Game modes

| Mode | Opponent | Status |
|------|----------|--------|
| **Offline** | A real **current NBA starting five** (random team) | ✅ playable |
| **PvP** | Real-time head-to-head draft vs another player (WebSockets); falls back to a **"Guest" AI** after 60s in the queue | ✅ playable |

Plus: **rating ladder + leaderboard** (6 tiers, Amateur→GOAT), **unlockable avatars**
(rank avatars + accomplishment achievements — Hot/Slump/50pt/triple-double/25 games/100 wins),
Hot & Slump player streaks, overtime (no ties), and **era-accurate team names**
(1990s Seattle SuperSonics, Vancouver Grizzlies, etc.).

## Stack

- **Backend:** FastAPI, **SQLAlchemy** (Postgres in prod via `DATABASE_URL`, SQLite locally)
- **Frontend:** React + Vite
- **Infra:** Docker; **Redis** for per-IP rate limiting + bearer-token sessions
  (stateless HTTP tier); deployed on **Railway** (API + Postgres + Redis) and
  **Cloudflare Pages** (frontend). See `DEPLOY.md`.
- **Data:** pre-computed static dataset (`players.db`, committed); no live API calls during gameplay

## How a match works

1. `POST /match {username}` → match id + **step 1**: a random decade × team and
   its top-10 players (decade-averaged stats). The opponent and future steps
   stay hidden (blind draft).
2. `POST /match/{id}/pick {player_name, slot}` → assign that player to an open,
   eligible slot. You get the next step, or — once all five slots are filled —
   the **scored result**: a realistic final score, both lineups' simulated box
   scores, head-to-head matchups, and your updated record.

Rules: five slots (PG/SG/SF/PF/C); a player can only go in a slot they're
eligible for (most are single-slot, true combos are multi); a player already
drafted can't be picked again even if they reappear from another team/decade.

**PvP** (`WebSocket /ws/pvp?username=…`): two players are matched from a queue
and draft simultaneously on a **10s-per-pick clock** (auto-pick on timeout).
After five rounds both lineups are scored head-to-head and **both records
update**; a disconnect awards the other player the win. State is in-memory
(single process); `app/live.py` holds the match manager.

## Layout

```
backend/
  app/
    scoring.py        # deterministic engine: ratings, fit, matchups, game score
    positions.py      # slots + position eligibility from coarse NBA labels
    dataset.py        # builds draft pools + current starters (DB, else seed)
    seed_data.py      # curated fallback pools (1960s–1980s legends) + heights
    game.py           # sequential draft state machine + box-score simulation
    db.py             # SQLAlchemy (Postgres/SQLite): users (W/L) + matches + accounts/sessions
    models.py         # Pydantic API models + PlayerStats (de)serialization
    main.py           # FastAPI app (CORS, rate limiting, routes)
    demo.py           # `python -m app.demo` — simulate one duel
    data/players.db   # prebuilt dataset (committed so deploys include it)
  pipeline/
    build_dataset.py  # nba_api -> SQLite (stats, position, height, lineups)
  tests/              # test_api.py (end-to-end), test_pipeline_helpers.py
  run.sh              # launch the API from the clean arm64 venv
  requirements.txt
frontend/
  src/
    App.jsx           # state machine: setup -> drafting -> result
    api.js            # backend client (Vite proxies /api -> :8000 in dev)
    components/
      DraftBoard.jsx  # one step: lineup strip + 10 candidates + slot-pick modal
      Results.jsx     # final score, box scores, matchups, fit notes
    styles.css        # sporty dark theme
```

## Quick start

```bash
cd backend
python3 -m app.demo          # sample duel, no deps needed

# One-time venv setup (this host needs a real arm64 interpreter, PYTHONPATH
# cleared — see Troubleshooting):
PY=/Users/shahawn/.local/share/mise/installs/python/3.12.13/bin/python3
env PYTHONPATH= $PY -m venv .venv312
env PYTHONPATH= ./.venv312/bin/python -m pip install -r requirements.txt

./run.sh                     # http://127.0.0.1:8000  (docs at /docs)
env PYTHONPATH= ./.venv312/bin/python -m tests.test_api   # end-to-end smoke test
```

Frontend (separate terminal):

```bash
cd frontend
npm install
npm run dev                  # http://127.0.0.1:5173  (proxies /api -> :8000)
```

> ⚠️ Do **not** use a bare `python3 -m venv .venv` on this host — it yields an
> x86_64 / wrong-pip venv and `incompatible architecture` errors on pydantic_core.
> Always use `.venv312` + `./run.sh`.

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | status + DB backend/readiness, CORS, pool counts, data sources |
| GET  | `/teams` | current NBA teams usable as opponents |
| POST | `/match` | start a match → first draft step (opponent hidden) |
| GET  | `/match/{id}` | inspect a match (current step; result once resolved) |
| POST | `/match/{id}/pick` | draft `{player_name, slot}` → next step or final result |
| GET  | `/record/{username}` | current W/L + rating & tier |
| GET  | `/leaderboard` | top players by rating (W/L + tier) |
| POST | `/avatar` | select an avatar (must be unlocked) |
| POST | `/auth/signup` | create account `{username,password,guest_id?}` → token (migrates guest stats) |
| POST | `/auth/login` | `{username,password}` → token |
| POST | `/auth/logout` | invalidate the bearer token |
| GET  | `/auth/me` | current account + record (bearer token) |

## Deployment

Container image (`backend/Dockerfile`) + `docker-compose.yml` (API + Postgres +
Redis) for local prod-parity. Validate the full stack with
`./scripts/validate_stack.sh` (or `scripts/validate_local.sh` without Docker).

Production runs on **Railway** (API container, Postgres, Redis) behind
**Cloudflare Pages** (static frontend). Key env vars: `DATABASE_URL`,
`REDIS_URL`, `ALLOWED_ORIGINS` (+ optional `ALLOWED_ORIGIN_REGEX` for Pages
preview subdomains), `TRUST_PROXY=true`, `SESSION_TTL_SECONDS`. The frontend
build takes `VITE_API` (drives both REST and the PvP WebSocket origin). Live
PvP keeps match state in-process, so it runs on a **single WS instance** while
HTTP scales horizontally (stateless via Redis sessions). Full runbook in
`DEPLOY.md`.

## Accounts & guests

You can play immediately as a **guest** — a persistent `guest_xxxx` id is stored
in the browser and your record/rating accumulate under it. **Sign up** (username
+ password) to claim your progress: the guest's W/L + rating transfer to the new
account. Passwords are hashed with PBKDF2 (stdlib); sessions are bearer tokens.
Writing to a *registered* username requires its token (guests stay open).

## Rating & tiers

Players start at **1000** (floor 0). **Only PvP is ranked** — offline matches
don't change your W/L or rating (good for warm-ups). Each ranked result moves
your rating by an amount that depends on your **current tier** — climbing gets
slower, slipping costs more:

| Tier | Reached at | Win | Loss |
|------|-----------|-----|------|
| Amateur | 0 | +10 | −2 |
| Pro | 1,500 | +8 | −3 |
| All-Star | 4,000 | +7 | −4 |
| Veteran | 8,000 | +7 | −5 |
| Hall-of-Fame | 18,000 | +6 | −5 |
| GOAT | 50,000 | +4 | −5 |

Ties don't change rating. Tunable in `app/rating.py`. The header shows your tier
badge + rating; the 🏆 Leaderboard ranks the top players.

**Win streaks:** 3+ straight ranked wins shows a 🔥 next to your name (player
card, match intro, live banner, leaderboard) and grants **bonus rating per win**
— +1 at a 3-game streak, +2 at 4, +3 at 5 and beyond. A loss resets the streak.

## Scoring model

Per player:
```
production = pts + 1.2·reb + 1.5·ast           # steals/blocks excluded (see below)
rating     = 0.50·normalized(production) + 0.50·normalized(impact)
```
- **Impact** is the era-neutral defensive-inclusive metric: PIE-derived for
  modern players, hand-set for curated legends. Steals/blocks are left out of
  `production` because they weren't tracked before 1973-74 — defense flows
  through the impact term instead (they're still shown on cards & box scores).
  Impact is weighted equally with production (0.50/0.50) so defensive value
  (e.g. Russell, Jordan) carries real weight without penalizing the 1960s.

Team & game:
```
fit        = small per-player bonus/penalty for slot quality (PG=assists,
             SG/SF=scoring, PF/C=height); capped ±1 — a light tiebreaker
matchups   = head-to-head per slot by rating + a size mismatch (real height
             ~0.5/inch, capped ±4; rebound fallback); each matchup won adds 7
             to team strength
strength   = Σ rating + (fit + size in the matchups) + 7·matchupWins
finalScore = realistic NBA total projected from the strength gap (≈106 baseline)
```
Each player's **box score is simulated for that game** (points allocated by
scoring ability and summed to the team total; rebounds/assists/steals/blocks via
Poisson around their averages). All weights live at the top of `app/scoring.py`.

**Hot / Slump:** rolled once per team — a **2%** chance a random player is 🔥 Hot
(rating +10, boosted box line) and **1%** they're 🥶 in a Slump (rating −10,
reduced line).

**No ties:** a tied regulation score goes to **overtime** (the stronger lineup
usually prevails, with a little randomness). The result reveal shows the tied
regulation score, a countdown, then the OT outcome.

## Data pipeline

`pipeline/build_dataset.py` pulls from stats.nba.com via `nba_api`:

- **Per-game stats** (`leaguedashplayerstats` Base + Advanced/PIE), bucketed into
  decades; franchise abbreviations (incl. SEA→OKC, VAN→MEM) mapped to full names.
- **Position + height** (`commonplayerinfo`, one call per player, **cached**):
  coarse Guard/Forward/Center → PG/SG/SF/PF/C via an assist/rebound heuristic;
  eligibility (single slot or combo); height parsed `6-6`→78 in.
- **Impact** = `clamp((PIE − 0.10)·100, −6, +13)` (true BPM isn't exposed; raw
  PIE is stored too).
- **Real starting fives** (`leaguedashlineups`): each team's highest-minutes
  5-man unit → `starting_lineups` table.

```bash
cd backend
# full historical pull (slow, resumable; position/height cache persists):
env PYTHONPATH= ./.venv312/bin/python pipeline/build_dataset.py --since 1996
# quick validation (one capped season):
env PYTHONPATH= ./.venv312/bin/python pipeline/build_dataset.py --since 2023 --limit 40
# (re)build real current starting fives — one API call:
env PYTHONPATH= ./.venv312/bin/python pipeline/build_dataset.py --lineups
```

**Draft pools** (`app/dataset.py`): per (decade, team), each player's
**games-weighted decade average**, top 10 by scoring-led notability; only
10-deep pools are draftable. DB pools (1996–present) are **merged with curated
seed pools** (1960s–1980s top teams), DB winning on conflicts. Without a DB the
game runs entirely on `seed_data.py`.

**Current opponents** (`app/dataset.py`): the real `starting_lineups`, slotted
by eligibility + height; teams without a stored lineup fall back to a derived
top-minutes five, then seed. `GET /health` → `starters_source`.

## Troubleshooting (this host)

`import numpy`/`pandas` failing with "import numpy from its source directory"
means a stray `PYTHONPATH` is leaking the toolbox's site-packages into the venv.
Build the venv from a real mise interpreter and clear `PYTHONPATH`:

```bash
PY=/Users/shahawn/.local/share/mise/installs/python/3.12.13/bin/python3
env PYTHONPATH= $PY -m venv .venv312
env PYTHONPATH= ./.venv312/bin/python -m pip install -r requirements.txt
```
