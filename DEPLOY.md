# Deploying 5v5 Duel

## Local prod-parity stack
```bash
docker compose up --build
# API on http://localhost:8000  (Postgres + Redis alongside)
```
- Rate limiting uses **Redis** immediately (shared across replicas).
- Runtime SQLite DB lives on the `api_data` volume at `GAME_DB_PATH=/data/game.db`.
- The read-only historical dataset (`app/data/players.db`) is **baked into the image**.
- `DATABASE_URL` is wired for the upcoming SQLite→Postgres migration (API still uses SQLite until then).

## Image
`backend/Dockerfile` — `python:3.12-slim`, non-root, gunicorn + 1 UvicornWorker.

> ⚠️ **Single worker on purpose.** Live PvP keeps match state in-process until
> the Phase 1 Redis-matchmaking refactor. Scale with **replicas behind the load
> balancer**, not `-w N`. (Multiple workers would split the matchmaking queue.)

## Container host + Cloudflare (Phase 0 target)
1. **Build & push** the image to your registry (GHCR/Docker Hub):
   `docker build -t <registry>/duel-api ./backend && docker push ...`
2. **Run** on your container host (Fly.io / Railway / Render / a VM) with env:
   - `ALLOWED_ORIGINS=https://yourdomain.com`
   - `REDIS_URL=redis://<managed-redis>:6379/0`
   - `DATABASE_URL=postgresql://...` (after the PG migration)
   - `TRUST_PROXY=true` (Cloudflare forwards the client IP)
   - `GAME_DB_PATH=/data/game.db` (mount a volume) — temporary until PG
3. **Frontend** (Cloudflare Pages):
   - Build command `npm run build`, output dir `dist`, root `frontend/`.
   - Set build env **`VITE_API=https://api.yourdomain.com`** — both REST and the
     PvP WebSocket (`wss://api.yourdomain.com/ws/pvp`) derive from it.
   - `frontend/public/_redirects` ships an SPA fallback (`/* /index.html 200`).
   - Put the app on your apex/`www` domain; the API on `api.` subdomain.
4. **Cloudflare**:
   - DNS + proxied (orange-cloud) record for the API host → TLS at the edge.
   - **WAF rate-limiting rules** as a coarse first layer (per-IP); the app's
     Redis limiter is the fine-grained second layer.
   - WebSockets: enabled by default on proxied records (needed for `/ws/pvp`).
   - Set the API behind a subdomain (e.g. `api.yourdomain.com`).

## Scaling note
Phase 0 = one API container + managed Postgres + Redis behind Cloudflare. To run
multiple API replicas (Phase 1) the live-PvP matchmaking must move to Redis
(pub/sub + an atomic queue) and WebSocket routing needs stickiness or a shared
broker.
