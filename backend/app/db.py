"""
SQLite persistence: user W/L records + match sessions.

Player stats themselves come from seed_data (or the pipeline-built players.db
later); this DB only stores game state.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from . import rating

DB_PATH = Path(__file__).parent / "data" / "game.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    wins     INTEGER NOT NULL DEFAULT 0,
    losses   INTEGER NOT NULL DEFAULT 0,
    ties     INTEGER NOT NULL DEFAULT 0,
    rating   INTEGER NOT NULL DEFAULT 1000
);
CREATE TABLE IF NOT EXISTS matches (
    id             TEXT PRIMARY KEY,
    username       TEXT NOT NULL,
    mode           TEXT NOT NULL DEFAULT 'offline',
    opponent_team  TEXT NOT NULL,
    opponent_json  TEXT NOT NULL,   -- frozen opponent lineup (hidden until resolve)
    state_json     TEXT NOT NULL,   -- evolving draft state (slot order, picks, current step)
    status         TEXT NOT NULL DEFAULT 'open',  -- open | resolved
    result_json    TEXT,            -- scored DuelResult once drafted
    created_at     REAL NOT NULL
);
"""

AUTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    username    TEXT PRIMARY KEY,
    pw_hash     TEXT NOT NULL,
    salt        TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    username    TEXT NOT NULL,
    created_at  REAL NOT NULL
);
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as c:
        c.executescript(SCHEMA)
        c.executescript(AUTH_SCHEMA)
        # Migration: add rating to pre-existing users tables.
        cols = {r[1] for r in c.execute("PRAGMA table_info(users)")}
        if "rating" not in cols:
            c.execute(f"ALTER TABLE users ADD COLUMN rating INTEGER NOT NULL DEFAULT {rating.START_RATING}")
        if "display_name" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN display_name TEXT")


# ---- users / records -------------------------------------------------------
def ensure_user(username: str) -> None:
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO users(username) VALUES (?)", (username,))


def set_display_name(username: str, name: str) -> None:
    """Set a guest's display label (record key stays the username/guest id).
    Ignored for registered accounts (their display is the account name)."""
    name = (name or "").strip()[:24]
    if not name:
        return
    ensure_user(username)
    with _conn() as c:
        c.execute("UPDATE users SET display_name = ? WHERE username = ?", (name, username))


def _record_dict(row) -> dict:
    d = dict(row)
    r = d.get("rating", rating.START_RATING)
    d["rating"] = r
    d["tier"] = rating.tier_name(r)
    nxt = rating.next_tier(r)
    d["next_tier"] = nxt["name"] if nxt else None
    d["next_tier_at"] = nxt["min"] if nxt else None
    d["display_name"] = d.get("display_name") or d.get("username")
    return d


def get_record(username: str) -> dict:
    with _conn() as c:
        row = c.execute(
            "SELECT username, wins, losses, ties, rating, display_name FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row:
        return _record_dict({"username": username, "wins": 0, "losses": 0,
                             "ties": 0, "rating": rating.START_RATING})
    return _record_dict(row)


def apply_result(username: str, outcome: str) -> dict:
    """outcome in {'win','loss','tie'}; updates W/L/T and rating; returns record."""
    col = {"win": "wins", "loss": "losses", "tie": "ties"}[outcome]
    ensure_user(username)
    with _conn() as c:
        row = c.execute("SELECT rating FROM users WHERE username = ?", (username,)).fetchone()
        cur = row["rating"] if row and row["rating"] is not None else rating.START_RATING
        new_rating = rating.apply_outcome(cur, outcome)
        c.execute(
            f"UPDATE users SET {col} = {col} + 1, rating = ? WHERE username = ?",
            (new_rating, username),
        )
    return get_record(username)


def leaderboard(limit: int = 20) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT username, wins, losses, ties, rating, display_name FROM users "
            "WHERE (wins + losses + ties) > 0 "
            "ORDER BY rating DESC, wins DESC, username ASC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_record_dict(r) for r in rows]


# ---- matches ---------------------------------------------------------------
def create_match(
    match_id: str,
    username: str,
    opponent_team: str,
    opponent_json: list,
    state_json: dict,
    mode: str = "offline",
) -> None:
    with _conn() as c:
        c.execute(
            """INSERT INTO matches
               (id, username, mode, opponent_team, opponent_json, state_json,
                status, created_at)
               VALUES (?,?,?,?,?,?, 'open', ?)""",
            (
                match_id,
                username,
                mode,
                opponent_team,
                json.dumps(opponent_json),
                json.dumps(state_json),
                time.time(),
            ),
        )


def get_match(match_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["opponent_json"] = json.loads(d["opponent_json"])
    d["state_json"] = json.loads(d["state_json"])
    d["result_json"] = json.loads(d["result_json"]) if d["result_json"] else None
    return d


def update_state(match_id: str, state_json: dict) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE matches SET state_json = ? WHERE id = ?",
            (json.dumps(state_json), match_id),
        )


def resolve_match(match_id: str, state_json: dict, result_json: dict) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE matches SET status = 'resolved', state_json = ?, result_json = ? WHERE id = ?",
            (json.dumps(state_json), json.dumps(result_json), match_id),
        )


# ---- accounts / sessions ---------------------------------------------------
def account_exists(username: str) -> bool:
    with _conn() as c:
        return c.execute(
            "SELECT 1 FROM accounts WHERE lower(username) = lower(?)", (username,)
        ).fetchone() is not None


def get_account(username: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT username, pw_hash, salt FROM accounts WHERE lower(username) = lower(?)",
            (username,),
        ).fetchone()
    return dict(row) if row else None


def create_account(username: str, pw_hash: str, salt: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO accounts(username, pw_hash, salt, created_at) VALUES (?,?,?,?)",
            (username, pw_hash, salt, time.time()),
        )


def create_session(username: str, token: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO sessions(token, username, created_at) VALUES (?,?,?)",
            (token, username, time.time()),
        )


def username_for_token(token: str | None) -> str | None:
    if not token:
        return None
    with _conn() as c:
        row = c.execute("SELECT username FROM sessions WHERE token = ?", (token,)).fetchone()
    return row["username"] if row else None


def delete_session(token: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM sessions WHERE token = ?", (token,))


def transfer_stats(src: str, dst: str) -> None:
    """Move a guest's W/L/T + rating into a (new) account, then clear the guest."""
    if not src or src == dst:
        return
    with _conn() as c:
        s = c.execute("SELECT wins, losses, ties, rating FROM users WHERE username = ?", (src,)).fetchone()
        if not s:
            return
        c.execute("INSERT OR IGNORE INTO users(username) VALUES (?)", (dst,))
        c.execute(
            "UPDATE users SET wins = wins + ?, losses = losses + ?, ties = ties + ?, rating = ? WHERE username = ?",
            (s["wins"], s["losses"], s["ties"], s["rating"], dst),
        )
        c.execute("DELETE FROM users WHERE username = ?", (src,))
