# 5v5 Duel — backend image.
# Clean python base (no host PYTHONPATH leak), runtime deps only.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Install runtime deps first for layer caching. The data pipeline deps
# (nba_api/pandas) aren't needed to SERVE, so install a slim runtime set.
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install "fastapi>=0.110" "uvicorn[standard]>=0.29" "gunicorn>=22.0" "redis>=5.0" \
                "psycopg[binary]>=3.1"

# App code + baked read-only dataset (app/data/players.db). game.db is written
# at runtime to GAME_DB_PATH (a mounted volume), not into the image.
COPY app ./app

# Non-root user.
RUN useradd -m appuser && \
    mkdir -p /data && chown -R appuser:appuser /app /data
USER appuser

ENV GAME_DB_PATH=/data/game.db

EXPOSE 8000

# Single worker: live PvP keeps match state in-process until the Phase 1
# Redis-matchmaking refactor. Scale via replicas behind the LB, not workers.
# UvicornWorker handles WebSockets.
CMD ["gunicorn", "app.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "1", "-b", "0.0.0.0:8000", \
     "--timeout", "120", "--access-logfile", "-"]
