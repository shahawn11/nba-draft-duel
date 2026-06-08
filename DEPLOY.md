# Deploying 5v5 Duel

**Live:** https://5v5duel.com · API https://api.5v5duel.com
(Frontend on Cloudflare Pages; API + Postgres + Redis on Railway.)

## Local prod-parity stack
```bash
docker compose up --build
# API on http://localhost:8000  (Postgres + Redis alongside)
```

### Validate it (Postgres + Redis + rate limiting)
```bash
./scripts/validate_stack.sh            # boots compose, drives a match, checks PG + Redis
./scripts/validate_stack.sh --down     # …and tears the stack down afterwards
```
The script confirms: API health, that the API is on Postgres (tables + a match
row land in PG), a full offline draft resolves over HTTP, the signup rate limit
returns 429, and Redis holds the rate-limit keys.

> No Docker? On macOS the lightest fix is Colima:
> `brew install colima docker docker-compose && colima start`, then re-run.

### Validate without Docker (local Postgres + Redis)
```bash
brew install postgresql@16 redis
brew services start postgresql@16 && brew services start redis
createdb duel
./scripts/validate_local.sh        # runs the API from .venv312 against local PG+Redis
```
Same checks (Postgres match row, rate-limit 429) without containers.

- Rate limiting uses **Redis** immediately (shared across replicas).
- Runtime SQLite DB lives on the `api_data` volume at `GAME_DB_PATH=/data/game.db`.
- The read-only historical dataset (`app/data/players.db`) is **baked into the image**.
- `DATABASE_URL` is wired for the upcoming SQLite→Postgres migration (API still uses SQLite until then).

## Image
`backend/Dockerfile` — `python:3.12-slim`, non-root, gunicorn + 1 UvicornWorker.

> ⚠️ **Single worker on purpose.** Live PvP keeps match state in-process until
> the Phase 1 Redis-matchmaking refactor. Scale with **replicas behind the load
> balancer**, not `-w N`. (Multiple workers would split the matchmaking queue.)

## Deploy to Railway (recommended start)
Railway builds from `backend/Dockerfile` (config in `backend/railway.json`) and
provides Postgres + Redis as one-click plugins.

1. **Create the project**: railway.com → New Project → Deploy from GitHub repo.
2. **API service**: add a service from this repo. In its **Settings → Root
   Directory set `backend`** (so the Docker build context matches the Dockerfile's
   `COPY app` paths). Railway auto-detects `railway.json` (Dockerfile build,
   `/health` healthcheck, 1 replica).
3. **Add plugins**: New → **Database → PostgreSQL**, and New → **Database → Redis**.
4. **Wire env vars** on the API service (Variables tab) using reference variables:
   - `DATABASE_URL = ${{Postgres.DATABASE_URL}}`
   - `REDIS_URL = ${{Redis.REDIS_URL}}`
   - `ALLOWED_ORIGINS = https://5v5duel.com`
   - `TRUST_PROXY = true`
   - `SESSION_TTL_SECONDS = 2592000`
   - (leave `GAME_DB_PATH` unset — Postgres is used once `DATABASE_URL` is set)
5. **Deploy** → grab the service's public URL, e.g. `https://duel-api.up.railway.app`.
   Verify: `curl https://<url>/health` → expect `"db":"postgresql","db_ready":true`.
6. **Keep live PvP on one replica** (`numReplicas: 1` in railway.json). Scale the
   HTTP load via Cloudflare caching + vertical sizing; multi-replica WS needs Phase 1b.
7. **Frontend → Cloudflare Pages** with `VITE_API=https://api.5v5duel.com` (see below).
8. **Domain**: point `api.5v5duel.com` at Railway (custom domain in service
   settings), apex/`www` at Cloudflare Pages.

CI is optional — Railway auto-deploys on push once the repo is connected. A
CLI-based GitHub Actions alternative lives at `.github/workflows/deploy-railway.yml`
(needs a `RAILWAY_TOKEN` secret).

## Container host + Cloudflare (Phase 0 target)
1. **Build & push** the image to your registry (GHCR/Docker Hub):
   `docker build -t <registry>/duel-api ./backend && docker push ...`
2. **Run** on your container host (Fly.io / Railway / Render / a VM) with env:
   - `ALLOWED_ORIGINS=https://5v5duel.com`
   - `REDIS_URL=redis://<managed-redis>:6379/0`
   - `DATABASE_URL=postgresql://...` (after the PG migration)
   - `TRUST_PROXY=true` (Cloudflare forwards the client IP)
   - `GAME_DB_PATH=/data/game.db` (mount a volume) — temporary until PG
3. **Frontend** (Cloudflare Pages):
   - Build command `npm run build`, output dir `dist`, root `frontend/`.
   - Set build env **`VITE_API=https://api.5v5duel.com`** — both REST and the
     PvP WebSocket (`wss://api.5v5duel.com/ws/pvp`) derive from it.
   - `frontend/public/_redirects` ships an SPA fallback (`/* /index.html 200`).
   - Put the app on your apex/`www` domain; the API on `api.` subdomain.
4. **Cloudflare**:
   - DNS + proxied (orange-cloud) record for the API host → TLS at the edge.
   - **WAF rate-limiting rules** as a coarse first layer (per-IP); the app's
     Redis limiter is the fine-grained second layer.
   - WebSockets: enabled by default on proxied records (needed for `/ws/pvp`).
   - Set the API behind a subdomain (e.g. `api.5v5duel.com`).

## Scaling note
Phase 0 = one API container + managed Postgres + Redis behind Cloudflare. To run
multiple API replicas (Phase 1) the live-PvP matchmaking must move to Redis
(pub/sub + an atomic queue) and WebSocket routing needs stickiness or a shared
broker.

## Phase 1 (Option A) — stateless HTTP scale-out + a single WS node
- **Sessions live in Redis** (TTL, sliding expiry) when `REDIS_URL` is set, so the
  HTTP tier is **stateless** — run as many HTTP replicas as you like behind the LB.
- **Live PvP runs on ONE WS node** (its match state is in-process). Route the
  WebSocket path there and everything else to the HTTP pool:
  - Cloudflare/LB rule: `*/ws/pvp` → the WS service; all other paths → HTTP replicas.
  - Run the WS service as a single replica (scale it vertically). One node handles
    thousands of concurrent matches; HTTP + static carry the request volume.
- Matchmaking stays **in-process on that one WS node** (Redis matchmaking + a
  pub/sub relay are only needed for multi-node WS — a future Phase 1b).
- `SESSION_TTL_SECONDS` (default 30d) controls token lifetime.
