#!/usr/bin/env bash
# Validate the Postgres code path WITHOUT Docker, using a locally-installed
# Postgres + Redis (e.g. Homebrew) and the project's .venv312.
#
#   brew install postgresql@16 redis
#   brew services start postgresql@16 && brew services start redis
#   createdb duel        # one-time
#   ./scripts/validate_local.sh
#
# Override endpoints via env if needed:
#   DATABASE_URL=postgresql://user:pass@localhost:5432/duel REDIS_URL=redis://localhost:6379/0 ./scripts/validate_local.sh
set -euo pipefail
cd "$(dirname "$0")/.."

API=${API:-http://127.0.0.1:8077}
PORT=8077
export DATABASE_URL=${DATABASE_URL:-postgresql://localhost:5432/duel}
export REDIS_URL=${REDIS_URL:-redis://localhost:6379/0}
export ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-http://localhost:5173}
VENV=backend/.venv312/bin

[ -x "$VENV/python" ] || { echo "✗ missing backend/.venv312 — create it first (see backend/run.sh)"; exit 1; }

echo "==> DATABASE_URL=$DATABASE_URL"
echo "==> Ensuring the Postgres driver is in the venv…"
env PYTHONPATH= "$VENV/pip" install -q "psycopg[binary]>=3.1" >/dev/null

echo "==> Quick connectivity check (Postgres + Redis)…"
env PYTHONPATH= "$VENV/python" - <<'PYEOF'
import os
from sqlalchemy import create_engine, text
url = os.environ["DATABASE_URL"]
if url.startswith("postgres://"): url = "postgresql+psycopg://"+url[len("postgres://"):]
elif url.startswith("postgresql://"): url = "postgresql+psycopg://"+url[len("postgresql://"):]
create_engine(url).connect().execute(text("select 1"))
print("   Postgres OK")
import redis
redis.Redis.from_url(os.environ["REDIS_URL"], socket_timeout=1).ping()
print("   Redis OK")
PYEOF

echo "==> Starting API (uvicorn) on :$PORT against Postgres…"
( cd backend && env PYTHONPATH= "./.venv312/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" >/tmp/ndd_local_api.log 2>&1 & echo $! > /tmp/ndd_local_api.pid )
trap 'kill "$(cat /tmp/ndd_local_api.pid 2>/dev/null)" 2>/dev/null || true' EXIT
for i in $(seq 1 40); do curl -fsS "$API/health" >/dev/null 2>&1 && break; sleep 0.5; [ "$i" = 40 ] && { echo "API never healthy"; cat /tmp/ndd_local_api.log; exit 1; }; done
echo "   healthy"

echo "==> Driving a full offline draft over HTTP…"
API="$API" env PYTHONPATH= "$VENV/python" - <<'PYEOF'
import json, os, urllib.request
API=os.environ["API"]
def call(m,p,b=None):
    d=json.dumps(b).encode() if b is not None else None
    r=urllib.request.Request(API+p,data=d,method=m,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r) as x: return json.loads(x.read() or "{}")
view=call("POST","/match",{"username":"validate_local_user"}); mid=view["match_id"]
for _ in range(5):
    if view.get("done"): break
    step=view["current_step"]
    c=next(x for x in step["candidates"] if x.get("eligible") and x.get("eligible_slots"))
    view=call("POST",f"/match/{mid}/pick",{"player_name":c["name"],"slot":c["eligible_slots"][0]})
res=view["result"]; print(f"   resolved: {res['outcome']} {round(res['your_final'])}-{round(res['opponent_final'])}")
PYEOF

echo "==> Verifying the match row is in Postgres…"
env PYTHONPATH= "$VENV/python" - <<'PYEOF'
import os
from sqlalchemy import create_engine, text
url=os.environ["DATABASE_URL"]
if url.startswith("postgresql://"): url="postgresql+psycopg://"+url[len("postgresql://"):]
n=create_engine(url).connect().execute(text("select count(*) from matches")).scalar()
print(f"   matches rows in Postgres: {n}")
assert n>=1
PYEOF

echo "==> Rate limiting (signup 5/min -> expect 429)…"
codes=""; for i in $(seq 1 7); do codes="$codes $(curl -s -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d '{"username":"x","password":"short"}' "$API/auth/signup")"; done
echo "   codes:$codes"; echo "$codes" | grep -q 429 && echo "   rate limiting active" || { echo "   NO 429 — FAILED"; exit 1; }

echo ""
echo "✅ Validated on local Postgres + Redis (no Docker)."
