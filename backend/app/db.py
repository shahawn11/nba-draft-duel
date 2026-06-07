"""
Persistence: user records + match sessions + accounts/sessions.

Backed by SQLAlchemy Core so the same code runs on:
  * Postgres in production  -- set DATABASE_URL=postgresql://user:pass@host/db
  * SQLite locally/tests    -- default file at GAME_DB_PATH (zero config)

Player stats come from the read-only dataset (dataset.py / players.db); this DB
only stores game state, records, and auth.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from sqlalchemy import (
    create_engine, MetaData, Table, Column, String, Integer, Float, Text,
    select, insert, update, delete, func, and_,
)
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from . import rating

# Writable runtime DB (SQLite fallback). Overridable via GAME_DB_PATH so it can
# live on a mounted volume in a container (the read-only players.db stays baked).
DB_PATH = Path(os.environ.get("GAME_DB_PATH") or (Path(__file__).parent / "data" / "game.db"))


def _engine_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        # Use the psycopg (v3) driver we ship in the image.
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        return url
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DB_PATH}"


_URL = _engine_url()
_IS_SQLITE = _URL.startswith("sqlite")
_engine = create_engine(
    _URL,
    pool_pre_ping=not _IS_SQLITE,
    connect_args={"check_same_thread": False} if _IS_SQLITE else {},
    future=True,
)

import sys as _sys
_safe_url = _URL.split("@")[-1] if "@" in _URL else _URL
print(f"[db] backend={_engine.dialect.name} target={_safe_url}", file=_sys.stderr, flush=True)


def backend() -> str:
    """Active SQL dialect: 'postgresql' or 'sqlite'."""
    return _engine.dialect.name


def ping() -> bool:
    from sqlalchemy import text
    try:
        with _engine.connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

metadata = MetaData()
R = rating.START_RATING

users = Table(
    "users", metadata,
    Column("username", String(64), primary_key=True),
    Column("wins", Integer, nullable=False, default=0, server_default="0"),
    Column("losses", Integer, nullable=False, default=0, server_default="0"),
    Column("ties", Integer, nullable=False, default=0, server_default="0"),
    Column("rating", Integer, nullable=False, default=R, server_default=str(R)),
    Column("peak_rating", Integer, nullable=False, default=R, server_default=str(R)),
    Column("display_name", String(64)),
    Column("avatar", String(32), nullable=False, default="amateur", server_default="amateur"),
    Column("achievements", Text, nullable=False, default="", server_default=""),
    Column("games_played", Integer, nullable=False, default=0, server_default="0"),
    Column("games_won", Integer, nullable=False, default=0, server_default="0"),
    Column("win_streak", Integer, nullable=False, default=0, server_default="0"),
)

matches = Table(
    "matches", metadata,
    Column("id", String(64), primary_key=True),
    Column("username", String(64), nullable=False),
    Column("mode", String(16), nullable=False, default="offline", server_default="offline"),
    Column("opponent_team", Text, nullable=False),
    Column("opponent_json", Text, nullable=False),
    Column("state_json", Text, nullable=False),
    Column("status", String(16), nullable=False, default="open", server_default="open"),
    Column("result_json", Text),
    Column("created_at", Float, nullable=False),
)

accounts = Table(
    "accounts", metadata,
    Column("username", String(64), primary_key=True),
    Column("pw_hash", Text, nullable=False),
    Column("salt", Text, nullable=False),
    Column("created_at", Float, nullable=False),
)

sessions = Table(
    "sessions", metadata,
    Column("token", String(128), primary_key=True),
    Column("username", String(64), nullable=False),
    Column("created_at", Float, nullable=False),
)

# Columns that may be missing on a legacy SQLite users table -> ADD COLUMN.
_USER_MIGRATIONS = {
    "rating": f"INTEGER NOT NULL DEFAULT {R}",
    "peak_rating": f"INTEGER NOT NULL DEFAULT {R}",
    "display_name": "TEXT",
    "avatar": "TEXT NOT NULL DEFAULT 'amateur'",
    "achievements": "TEXT NOT NULL DEFAULT ''",
    "games_played": "INTEGER NOT NULL DEFAULT 0",
    "games_won": "INTEGER NOT NULL DEFAULT 0",
    "win_streak": "INTEGER NOT NULL DEFAULT 0",
}


def init_db() -> None:
    metadata.create_all(_engine)
    # Migrate legacy tables that predate newer columns (no-op on fresh DBs).
    from sqlalchemy import inspect, text
    insp = inspect(_engine)
    existing = {c["name"] for c in insp.get_columns("users")}
    with _engine.begin() as c:
        for col, ddl in _USER_MIGRATIONS.items():
            if col not in existing:
                c.execute(text(f"ALTER TABLE users ADD COLUMN {col} {ddl}"))
        if "peak_rating" not in existing:
            c.execute(text("UPDATE users SET peak_rating = rating WHERE rating > peak_rating"))


def _row_dict(row: Row | None) -> dict | None:
    return dict(row._mapping) if row is not None else None


# ---- users / records -------------------------------------------------------
def ensure_user(username: str) -> None:
    with _engine.begin() as c:
        exists = c.execute(select(users.c.username).where(users.c.username == username)).first()
        if not exists:
            try:
                c.execute(insert(users).values(username=username))
            except IntegrityError:
                pass  # created concurrently


def set_display_name(username: str, name: str, force: bool = False) -> None:
    """A guest name is LOCKED once set; later calls are ignored unless force=True
    (used at signup, where the account username becomes the official name)."""
    name = (name or "").strip()[:24]
    if not name:
        return
    ensure_user(username)
    with _engine.begin() as c:
        if not force:
            row = c.execute(select(users.c.display_name).where(users.c.username == username)).first()
            if row and (row[0] or "").strip():
                return  # already named -> locked
        c.execute(update(users).where(users.c.username == username).values(display_name=name))


def _record_dict(row) -> dict:
    d = dict(row)
    r = d.get("rating", rating.START_RATING)
    d["rating"] = r
    peak = max(d.get("peak_rating") or r, r)
    d["peak_rating"] = peak
    d["tier"] = rating.tier_name(r)
    nxt = rating.next_tier(r)
    d["next_tier"] = nxt["name"] if nxt else None
    d["next_tier_at"] = nxt["min"] if nxt else None
    d["display_name"] = d.get("display_name") or d.get("username")
    d["avatar"] = d.get("avatar") or "amateur"
    earned = [a for a in (d.get("achievements") or "").split(",") if a]
    d["achievements"] = earned
    d["unlocked"] = rating.unlocked_avatar_ids(peak) + earned
    d["win_streak"] = d.get("win_streak") or 0
    d["on_streak"] = d["win_streak"] >= rating.STREAK_MIN
    d.pop("ties", None)
    return d


_REC_COLS = (users.c.username, users.c.wins, users.c.losses, users.c.rating,
             users.c.peak_rating, users.c.display_name, users.c.avatar, users.c.achievements,
             users.c.win_streak)


def name_label(record: dict) -> str:
    """UI label for a player record. display_name is not unique (only username
    is the PK), so two guests can both pick "Kiro". Append the guest id suffix
    to a named guest's display name ("Kiro" -> "Kiro_u86v9sbv") so they are
    distinguishable. Registered users and unnamed guests are unchanged.
    Mirrors frontend/src/nameLabel.js."""
    username = record.get("username") or ""
    display = record.get("display_name") or username
    if username.startswith("guest_"):
        suffix = username[len("guest_"):]
        if display and display != username:
            return f"{display}_{suffix}"
        return username
    return display


def get_record(username: str) -> dict:
    with _engine.connect() as c:
        row = c.execute(select(*_REC_COLS).where(users.c.username == username)).first()
    if not row:
        return _record_dict({"username": username, "wins": 0, "losses": 0,
                             "rating": rating.START_RATING, "peak_rating": rating.START_RATING,
                             "avatar": "amateur", "achievements": ""})
    return _record_dict(dict(row._mapping))


def set_avatar(username: str, avatar_id: str) -> dict:
    """Rank avatars require the tier unlocked (by peak rating); locked/unknown
    ids raise ValueError."""
    ensure_user(username)
    rec = get_record(username)
    if avatar_id not in rec["unlocked"]:
        raise ValueError("locked")
    with _engine.begin() as c:
        c.execute(update(users).where(users.c.username == username).values(avatar=avatar_id))
    return get_record(username)


def award_achievements(username: str, won: bool, players: list[dict]) -> tuple[dict, list[str]]:
    """Record a finished match and unlock newly-earned achievement avatars.
    Cosmetic only -- never touches rating/W-L. Returns (record, newly_unlocked)."""
    ensure_user(username)
    newly: set[str] = set()
    for p in players or []:
        if p.get("status") == "hot":
            newly.add("hot")
        elif p.get("status") == "slump":
            newly.add("slump")
        g = p.get("game") or {}
        if (g.get("pts") or 0) >= 50:
            newly.add("fifty")
        if sum(1 for k in ("pts", "reb", "ast") if (g.get(k) or 0) >= 10) >= 3:
            newly.add("tripledouble")

    with _engine.begin() as c:
        row = c.execute(
            select(users.c.achievements, users.c.games_played, users.c.games_won)
            .where(users.c.username == username)
        ).first()
        earned = {a for a in ((row[0] if row else "") or "").split(",") if a}
        gp = (row[1] if row else 0) + 1
        gw = (row[2] if row else 0) + (1 if won else 0)
        if gp >= 25:
            newly.add("games25")
        if gw >= 100:
            newly.add("wins100")
        newly &= rating.ACHIEVEMENT_IDS
        newly_unlocked = sorted(newly - earned)
        earned |= newly
        c.execute(update(users).where(users.c.username == username).values(
            achievements=",".join(sorted(earned)), games_played=gp, games_won=gw))
    return get_record(username), newly_unlocked


def apply_result(username: str, outcome: str) -> dict:
    """outcome in {'win','loss'} updates W/L + rating (+peak). 'tie' is a no-op."""
    ensure_user(username)
    if outcome == "tie":
        return get_record(username)
    col = {"win": "wins", "loss": "losses"}[outcome]
    with _engine.begin() as c:
        row = c.execute(select(users.c.rating, users.c.peak_rating, users.c.win_streak)
                        .where(users.c.username == username)).first()
        cur = row[0] if row and row[0] is not None else rating.START_RATING
        peak = row[1] if row and row[1] is not None else cur
        streak = row[2] if row and row[2] is not None else 0
        if outcome == "win":
            streak += 1
            new_rating = rating.apply_outcome(cur, "win") + rating.streak_bonus(streak)
        else:
            streak = 0
            new_rating = rating.apply_outcome(cur, "loss")
        new_peak = max(peak, new_rating)
        c.execute(update(users).where(users.c.username == username).values(
            **{col: users.c[col] + 1, "rating": new_rating, "peak_rating": new_peak,
               "win_streak": streak}))
    return get_record(username)


def leaderboard(limit: int = 20) -> list[dict]:
    with _engine.connect() as c:
        rows = c.execute(
            select(*_REC_COLS)
            .where((users.c.wins + users.c.losses) > 0)
            .order_by(users.c.rating.desc(), users.c.wins.desc(), users.c.username.asc())
            .limit(limit)
        ).all()
    return [_record_dict(dict(r._mapping)) for r in rows]


# ---- matches ---------------------------------------------------------------
def create_match(match_id, username, opponent_team, opponent_json, state_json, mode="offline") -> None:
    with _engine.begin() as c:
        c.execute(insert(matches).values(
            id=match_id, username=username, mode=mode, opponent_team=opponent_team,
            opponent_json=json.dumps(opponent_json), state_json=json.dumps(state_json),
            status="open", created_at=time.time()))


def get_match(match_id: str) -> dict | None:
    with _engine.connect() as c:
        row = c.execute(select(matches).where(matches.c.id == match_id)).first()
    if not row:
        return None
    d = dict(row._mapping)
    d["opponent_json"] = json.loads(d["opponent_json"])
    d["state_json"] = json.loads(d["state_json"])
    d["result_json"] = json.loads(d["result_json"]) if d["result_json"] else None
    return d


def update_state(match_id: str, state_json: dict) -> None:
    with _engine.begin() as c:
        c.execute(update(matches).where(matches.c.id == match_id)
                  .values(state_json=json.dumps(state_json)))


def resolve_match(match_id: str, state_json: dict, result_json: dict) -> None:
    with _engine.begin() as c:
        c.execute(update(matches).where(matches.c.id == match_id).values(
            status="resolved", state_json=json.dumps(state_json),
            result_json=json.dumps(result_json)))


# ---- accounts / sessions ---------------------------------------------------
def account_exists(username: str) -> bool:
    with _engine.connect() as c:
        return c.execute(select(accounts.c.username)
                         .where(func.lower(accounts.c.username) == func.lower(username))).first() is not None


def get_account(username: str) -> dict | None:
    with _engine.connect() as c:
        row = c.execute(select(accounts.c.username, accounts.c.pw_hash, accounts.c.salt)
                        .where(func.lower(accounts.c.username) == func.lower(username))).first()
    return _row_dict(row)


def create_account(username: str, pw_hash: str, salt: str) -> None:
    with _engine.begin() as c:
        c.execute(insert(accounts).values(
            username=username, pw_hash=pw_hash, salt=salt, created_at=time.time()))


def create_session(username: str, token: str) -> None:
    with _engine.begin() as c:
        c.execute(insert(sessions).values(token=token, username=username, created_at=time.time()))


def username_for_token(token: str | None) -> str | None:
    if not token:
        return None
    with _engine.connect() as c:
        row = c.execute(select(sessions.c.username).where(sessions.c.token == token)).first()
    return row[0] if row else None


def delete_session(token: str) -> None:
    with _engine.begin() as c:
        c.execute(delete(sessions).where(sessions.c.token == token))


def transfer_stats(src: str, dst: str) -> None:
    """Move a guest's W/L/T + rating + avatar/achievements into a (new) account,
    then clear the guest row."""
    if not src or src == dst:
        return
    with _engine.begin() as c:
        s = c.execute(select(users).where(users.c.username == src)).first()
        if not s:
            return
        s = s._mapping
        # ensure dst exists
        if not c.execute(select(users.c.username).where(users.c.username == dst)).first():
            c.execute(insert(users).values(username=dst))
        d = c.execute(select(users.c.peak_rating, users.c.achievements,
                             users.c.games_played, users.c.games_won)
                      .where(users.c.username == dst)).first()
        dst_peak = d[0] if d and d[0] is not None else rating.START_RATING
        new_peak = max(dst_peak, s["peak_rating"] or s["rating"], s["rating"])
        src_ach = {a for a in (s["achievements"] or "").split(",") if a}
        dst_ach = {a for a in ((d[1] if d else "") or "").split(",") if a}
        merged_ach = ",".join(sorted(src_ach | dst_ach))
        gp = (d[2] if d else 0) + (s["games_played"] or 0)
        gw = (d[3] if d else 0) + (s["games_won"] or 0)
        c.execute(update(users).where(users.c.username == dst).values(
            wins=users.c.wins + s["wins"], losses=users.c.losses + s["losses"],
            ties=users.c.ties + s["ties"], rating=s["rating"], peak_rating=new_peak,
            avatar=s["avatar"] or "amateur", achievements=merged_ach,
            games_played=gp, games_won=gw, win_streak=s["win_streak"] or 0))
        c.execute(delete(users).where(users.c.username == src))
