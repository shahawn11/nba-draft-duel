# NBA Draft Duel

A PvP twist on [82-0.com](https://www.82-0.com/): you're handed a random
**decade × NBA team**, draft a player from that pool, and build a starting 5.
Your lineup is scored against an opponent's by **production, positional fit,
and head-to-head matchups** — winner gets a W, loser gets an L.

## Game modes

| Mode | Opponent | Status |
|------|----------|--------|
| **Offline** | A random *current* NBA starting 5 | ✅ scoring engine done |
| **Async PvP** | Another player's previously submitted 5 | planned |
| **Live PvP** | Real-time draft vs another player (WebSockets) | planned |

## Stack

- **Backend:** FastAPI + SQLite
- **Frontend:** React + Vite *(not scaffolded yet)*
- **Data:** pre-computed static dataset (no live API calls during gameplay)

## Layout

```
backend/
  app/
    scoring.py        # deterministic winner-calc engine (production+fit+matchups)
    seed_data.py      # curated playable dataset (current 5s + historical pool)
    demo.py           # `python -m app.demo` -> simulate one offline duel
    data/             # players.db lives here after the pipeline runs
  pipeline/
    build_dataset.py  # nba_api -> SQLite historical pull
  requirements.txt
frontend/             # React + Vite (draft board, results, record)
  src/
    App.jsx           # state machine: setup -> drafting -> result
    api.js            # backend client (Vite proxies /api -> :8000 in dev)
    components/
      DraftBoard.jsx  # 5 prompts, selectable distinct candidates
      Results.jsx     # outcome banner, matchups, scored lineups, fit notes
    styles.css        # sporty dark theme
```

## Quick start

```bash
cd backend
python3 -m app.demo          # runs a sample offline duel, no deps needed

# One-time setup of the backend venv (this host needs a real arm64 interpreter
# with PYTHONPATH cleared — see Troubleshooting):
PY=/Users/shahawn/.local/share/mise/installs/python/3.12.13/bin/python3
env PYTHONPATH= $PY -m venv .venv312
env PYTHONPATH= ./.venv312/bin/python -m pip install -r requirements.txt

# Run the API (launcher clears PYTHONPATH + uses the clean venv):
./run.sh                     # http://127.0.0.1:8000  (docs at /docs)

env PYTHONPATH= ./.venv312/bin/python -m tests.test_api   # end-to-end smoke test
```

> ⚠️ Do **not** launch with a bare `python3 -m venv .venv` on this host: it
> produces an x86_64 / wrong-pip venv and you'll hit
> `incompatible architecture (have 'x86_64', need 'arm64')` on pydantic_core.
> Always use `.venv312` + `./run.sh`.

Then start the frontend (separate terminal):

```bash
cd frontend
npm install
npm run dev      # http://127.0.0.1:5173  (proxies /api -> backend :8000)
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | liveness |
| GET  | `/teams` | current NBA teams usable as opponents |
| POST | `/match` | start an offline match → 5 draft prompts (opponent hidden) |
| GET  | `/match/{id}` | inspect a match (prompts; result once resolved) |
| POST | `/match/{id}/draft` | submit your 5 picks → scored result + updated record |
| GET  | `/record/{username}` | current W/L/T record |

**Flow:** `POST /match {username}` returns 5 prompts, each a random
decade × team pool with candidate players. The opponent (a random current
starting 5) stays hidden. Submit one pick per prompt (players must be distinct)
to `POST /match/{id}/draft`; the engine scores both lineups, reveals the
opponent, and records the W/L/T.


## Scoring model (v1)

```
PlayerScore   = 0.65 * normalized(box-score composite) + 0.35 * normalized(BPM)
PositionalFit = +6 perfect coverage; -4 per missing position; -2 per duplicate
Matchups      = head-to-head best-per-position, count wins
FinalScore    = 0.70 * (teamTotal + fit) + 0.30 * matchupSwing
```

All weights live at the top of `app/scoring.py` and are easy to tune.

## Data pipeline

`pipeline/build_dataset.py` pulls per-game stats from stats.nba.com and fills the
two fields scoring relies on:

- **Position** — `commonplayerinfo` gives coarse Guard/Forward/Center; we
  disambiguate to PG/SG/SF/PF/C via an assist/rebound heuristic and **cache**
  each player's position by id (fetched once ever, not per season).
- **Impact ("bpm" column)** — stats.nba.com does **not** expose true Box
  Plus/Minus (a Basketball-Reference metric). We pull **PIE** (native) and map
  it onto the BPM scale: `bpm_est = clamp((PIE - 0.10) * 100, -6, +13)`. Raw PIE
  is also stored for transparency.

Franchise abbreviations (incl. historical aliases like SEA→OKC, VAN→MEM) map to
full team names so `decade × team` keys stay consistent.

```bash
cd backend
# quick validation (one recent season, capped, ~30s of API calls):
./.venv/bin/python -m pip install nba_api pandas
./.venv/bin/python pipeline/build_dataset.py --since 2023 --limit 40
# full historical pull (slow — hours; resumable, position cache persists):
./.venv/bin/python pipeline/build_dataset.py --since 1997
```

Once `app/data/players.db` exists, the game auto-switches to it
(`app/dataset.py`); otherwise it falls back to `seed_data.py`. Check which is
active via `GET /health` → `pool_source`.

> **Troubleshooting (this host):** if `import numpy`/`pandas` fails with
> "import numpy from its source directory", a stray `PYTHONPATH` is leaking the
> toolbox's site-packages into your venv. Build the venv from a real mise
> interpreter and clear `PYTHONPATH`:
> ```bash
> PY=/Users/shahawn/.local/share/mise/installs/python/3.12.13/bin/python3
> env PYTHONPATH= $PY -m venv .venv312
> env PYTHONPATH= ./.venv312/bin/python -m pip install nba_api pandas
> env PYTHONPATH= ./.venv312/bin/python pipeline/build_dataset.py --since 2023 --limit 8
> ```
