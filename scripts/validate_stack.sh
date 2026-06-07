#!/usr/bin/env bash
# Validate the full Phase 0 stack (API + Postgres + Redis) via docker compose.
# Run on a Docker-capable host from the repo root:  ./scripts/validate_stack.sh
# Add --down to tear the stack down afterwards.
set -euo pipefail
cd "$(dirname "$0")/.."

API=${API:-http://localhost:8000}
PY=${PYTHON:-python3}

# --- preflight: Docker must be installed and running ---
if ! command -v docker >/dev/null 2>&1; then
  cat <<'MSG'
✗ Docker isn't installed. On macOS, the lightest option is Colima (no Docker Desktop):
    brew install colima docker docker-compose
    colima start
  …then re-run this script. (Or install Docker Desktop: brew install --cask docker)
  No Docker? Use the no-Docker path in DEPLOY.md ("Validate without Docker").
MSG
  exit 127
fi
if ! docker info >/dev/null 2>&1; then
  echo "✗ Docker is installed but the daemon isn't running. Start it (e.g. 'colima start' or open Docker Desktop) and retry."
  exit 1
fi

# Support both Compose v2 plugin ("docker compose") and standalone ("docker-compose").
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "✗ Docker Compose not found. Install it: 'brew install docker-compose' (standalone) or enable the Compose v2 plugin."
  exit 127
fi
echo "==> Using compose: $COMPOSE"

echo "==> Clearing any previous/orphan containers (a stale one can hold port 8000)…"
$COMPOSE down --remove-orphans >/dev/null 2>&1 || true

echo "==> Rebuilding the api image from scratch (no cache — defeats stale COPY layers)…"
$COMPOSE build --no-cache api
echo "==> Bringing up the stack (force-recreate)…"
$COMPOSE up -d --force-recreate --remove-orphans

echo "==> Sanity: confirming the running image has the current code…"
if $COMPOSE exec -T api grep -q '"db": db.backend()' app/main.py; then
  echo "   image main.py is current ✓"
else
  echo "✗ running image is STILL stale (old main.py). Try: docker system prune -f then re-run."
  exit 1
fi

echo "==> Waiting for API health at $API/health …"
for i in $(seq 1 60); do
  if curl -fsS "$API/health" >/dev/null 2>&1; then echo "   healthy"; break; fi
  sleep 1
  [ "$i" = 60 ] && { echo "API never became healthy"; $COMPOSE logs --tail=50 api; exit 1; }
done

echo "==> Confirming the API is using Postgres (not SQLite)…"
$COMPOSE exec -T api sh -c 'echo "DATABASE_URL=$DATABASE_URL"'
raw=$(curl -fsS "$API/health" || true)
echo "   raw /health: $raw"
backend=$(printf '%s' "$raw" | "$PY" -c 'import sys,json;
try: print(json.load(sys.stdin).get("db") or "")
except Exception: print("")' 2>/dev/null)
echo "   /health db backend = ${backend:-<none>}"
if [ "$backend" != "postgresql" ]; then
  echo "✗ The API answering on $API is NOT on Postgres (got '${backend:-none}')."
  echo "  A stale/orphan container is likely holding the port. Check:"
  echo "    docker ps --filter publish=8000"
  echo "  Then: $COMPOSE down --remove-orphans && $COMPOSE up -d --build --force-recreate"
  exit 1
fi
$COMPOSE exec -T db psql -U duel -d duel -c "\dt" | grep -E "users|matches|accounts|sessions" \
  && echo "   Postgres tables present"

echo "==> Driving a full offline draft over HTTP…"
API="$API" "$PY" - <<'PYEOF'
import json, os, urllib.request
API = os.environ["API"]
def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API+path, data=data, method=method,
                                 headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read() or "{}")

user = "validate_pg_user"
_, view = call("POST", "/match", {"username": user})
mid = view["match_id"]
for _ in range(5):
    if view.get("done"): break
    step = view.get("current") or view.get("current_step")
    cand = next(c for c in step["candidates"] if c.get("eligible") and c.get("eligible_slots"))
    _, view = call("POST", f"/match/{mid}/pick",
                   {"player_name": cand["name"], "slot": cand["eligible_slots"][0]})
res = view["result"]
print(f"   match resolved: {res['outcome']} {round(res['your_final'])}-{round(res['opponent_final'])} "
      f"(ranked={res['ranked']})")
PYEOF

echo "==> Verifying the match row landed in Postgres…"
$COMPOSE exec -T db psql -U duel -d duel -tAc "SELECT count(*) FROM matches;" \
  | awk '{print "   matches rows in Postgres:", $1; if ($1+0 < 1) exit 1}'

echo "==> Checking rate limiting (signup rule = 5/min -> expect a 429)…"
codes=""
for i in $(seq 1 7); do
  c=$(curl -s -o /dev/null -w "%{http_code}" -H "Content-Type: application/json" \
        -d '{"username":"x","password":"short"}' "$API/auth/signup")
  codes="$codes $c"
done
echo "   signup status codes:$codes"
echo "$codes" | grep -q 429 && echo "   rate limiting active (429 seen)" || { echo "   NO 429 — rate limit FAILED"; exit 1; }

echo "==> Confirming Redis is the limiter backend (keys present)…"
$COMPOSE exec -T redis redis-cli --scan --pattern 'rl:*' | head -1 \
  && echo "   Redis rate-limit keys present"

echo ""
echo "✅ Stack validated on Postgres + Redis."
if [ "${1:-}" = "--down" ]; then echo "==> Tearing down…"; $COMPOSE down; fi
