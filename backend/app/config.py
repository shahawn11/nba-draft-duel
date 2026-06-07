"""
Runtime configuration, driven by environment variables so the same image runs
locally and in production. Sensible defaults keep local dev zero-config.
"""
from __future__ import annotations

import os


def _csv(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


# --- CORS ---------------------------------------------------------------
# Comma-separated allowed origins. Defaults cover Vite local dev.
ALLOWED_ORIGINS = _csv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)

# Optional regex for origins (e.g. Cloudflare Pages preview subdomains that get
# a new hash each deploy). Example: https://([a-z0-9-]+\.)?5v5-duel\.pages\.dev
ALLOWED_ORIGIN_REGEX = os.environ.get("ALLOWED_ORIGIN_REGEX") or None

# --- Redis (sessions / rate limiting / matchmaking later) ---------------
# When unset, rate limiting falls back to an in-process limiter (single box).
REDIS_URL = os.environ.get("REDIS_URL") or None

# --- Rate limiting ------------------------------------------------------
RATE_LIMIT_ENABLED = _bool("RATE_LIMIT_ENABLED", True)
# Global default: requests per window per client key.
RATE_LIMIT_DEFAULT = _int("RATE_LIMIT_DEFAULT", 120)     # req / window
RATE_LIMIT_WINDOW = _int("RATE_LIMIT_WINDOW", 60)        # seconds
# Per-path overrides (path prefix -> (limit, window_seconds)). Tighter on the
# write/expensive endpoints.
RATE_LIMIT_RULES: dict[str, tuple[int, int]] = {
    "/auth/signup": (5, 60),
    "/auth/login": (10, 60),
    "/match": (30, 60),
    "/avatar": (20, 60),
}

# Trust X-Forwarded-For (set true when behind a CDN/ALB that appends client IP).
TRUST_PROXY = _bool("TRUST_PROXY", False)

# --- Sessions -----------------------------------------------------------
# Bearer-token TTL. Stored in Redis (with expiry) when REDIS_URL is set, so the
# HTTP tier is stateless across replicas; otherwise falls back to the DB table.
SESSION_TTL_SECONDS = _int("SESSION_TTL_SECONDS", 30 * 24 * 3600)  # 30 days
