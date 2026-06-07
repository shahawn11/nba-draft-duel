"""
Rate limiting: a fixed-window counter keyed by client IP + path rule.

Two backends, chosen automatically:
  * Redis (when config.REDIS_URL is set) -- atomic INCR + EXPIRE, so the limit
    is shared across all API replicas. This is the production path.
  * In-process dict (fallback) -- correct for a single box / local dev.

Exposed as Starlette middleware returning HTTP 429 with Retry-After when a
client exceeds the window's allowance.
"""
from __future__ import annotations

import time
import threading

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import config


class _MemoryBackend:
    """Per-process fixed-window counters. Not shared across replicas."""

    def __init__(self) -> None:
        self._hits: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def incr(self, key: str, window: int) -> int:
        now = time.time()
        with self._lock:
            count, expires = self._hits.get(key, (0, 0.0))
            if now >= expires:
                count, expires = 0, now + window
            count += 1
            self._hits[key] = (count, expires)
            # opportunistic cleanup
            if len(self._hits) > 10000:
                for k, (_, exp) in list(self._hits.items()):
                    if now >= exp:
                        self._hits.pop(k, None)
            return count


class _RedisBackend:
    """Shared fixed-window counters via Redis INCR/EXPIRE."""

    def __init__(self, url: str) -> None:
        import redis  # lazy: only required when REDIS_URL is configured
        self._r = redis.Redis.from_url(url, socket_timeout=0.25)

    def incr(self, key: str, window: int) -> int:
        # Bucket the window so the key self-expires; INCR is atomic.
        bucket = int(time.time() // window)
        rkey = f"rl:{key}:{bucket}"
        pipe = self._r.pipeline()
        pipe.incr(rkey)
        pipe.expire(rkey, window + 1)
        count, _ = pipe.execute()
        return int(count)


def _make_backend():
    if config.REDIS_URL:
        try:
            return _RedisBackend(config.REDIS_URL)
        except Exception:
            # If Redis is misconfigured/unavailable, fail open to in-memory
            # rather than taking the API down.
            return _MemoryBackend()
    return _MemoryBackend()


_backend = _make_backend()


def _client_key(request: Request) -> str:
    if config.TRUST_PROXY:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rule_for(path: str) -> tuple[int, int]:
    for prefix, rule in config.RATE_LIMIT_RULES.items():
        if path == prefix or path.startswith(prefix + "/"):
            return rule
    return (config.RATE_LIMIT_DEFAULT, config.RATE_LIMIT_WINDOW)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not config.RATE_LIMIT_ENABLED or request.method == "OPTIONS":
            return await call_next(request)

        limit, window = _rule_for(request.url.path)
        key = f"{_client_key(request)}|{request.url.path}"
        try:
            count = _backend.incr(key, window)
        except Exception:
            # Never let limiter errors break real traffic.
            return await call_next(request)

        if count > limit:
            retry = window
            return JSONResponse(
                {"detail": "rate limit exceeded — slow down"},
                status_code=429,
                headers={"Retry-After": str(retry),
                         "X-RateLimit-Limit": str(limit)},
            )
        resp = await call_next(request)
        resp.headers["X-RateLimit-Limit"] = str(limit)
        resp.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
        return resp
