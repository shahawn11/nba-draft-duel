"""
Session store for bearer tokens.

  * Redis backend (when REDIS_URL is set): `SET sess:<token> <username> EX ttl`.
    Shared across all HTTP replicas + automatic expiry -> the API tier is
    stateless and tokens age out.
  * DB fallback (no Redis): the `sessions` table via db.py (single-box/local).

Public API mirrors the old db.* session helpers so callers swap 1:1.
"""
from __future__ import annotations

from . import config, db

_PREFIX = "sess:"
_redis = None
if config.REDIS_URL:
    try:
        import redis
        _redis = redis.Redis.from_url(config.REDIS_URL, socket_timeout=0.25)
    except Exception:
        _redis = None


def using_redis() -> bool:
    return _redis is not None


def create(username: str, token: str) -> None:
    if _redis is not None:
        try:
            _redis.set(_PREFIX + token, username, ex=config.SESSION_TTL_SECONDS)
            return
        except Exception:
            pass  # fail over to DB
    db.create_session(username, token)


def username_for(token: str | None) -> str | None:
    if not token:
        return None
    if _redis is not None:
        try:
            v = _redis.get(_PREFIX + token)
            if v is not None:
                # refresh TTL on use (sliding expiry)
                _redis.expire(_PREFIX + token, config.SESSION_TTL_SECONDS)
                return v.decode() if isinstance(v, (bytes, bytearray)) else str(v)
            return None
        except Exception:
            pass
    return db.username_for_token(token)


def delete(token: str) -> None:
    if _redis is not None:
        try:
            _redis.delete(_PREFIX + token)
            return
        except Exception:
            pass
    db.delete_session(token)
