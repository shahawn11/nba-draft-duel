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

DB_PATH = Path(__file__).parent / "data" / "game.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    wins     INTEGER NOT NULL DEFAULT 0,
    losses   INTEGER NOT NULL DEFAULT 0,
    ties     INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS matches (
    id             TEXT PRIMARY KEY,
    username       TEXT NOT NULL,
    mode           TEXT NOT NULL DEFAULT 'offline',
    opponent_team  TEXT NOT NULL,
    opponent_json  TEXT NOT NULL,   -- frozen opponent lineup
    prompts_json   TEXT NOT NULL,   -- the draft prompts shown to the player
    status         TEXT NOT NULL DEFAULT 'open',  -- open | resolved
    result_json    TEXT,            -- scored DuelResult once drafted
    created_at     REAL NOT NULL
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


# ---- users / records -------------------------------------------------------
def ensure_user(username: str) -> None:
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO users(username) VALUES (?)", (username,))


def get_record(username: str) -> dict:
    with _conn() as c:
        row = c.execute(
            "SELECT username, wins, losses, ties FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row:
        return {"username": username, "wins": 0, "losses": 0, "ties": 0}
    return dict(row)


def apply_result(username: str, outcome: str) -> dict:
    """outcome in {'win','loss','tie'}; returns updated record."""
    col = {"win": "wins", "loss": "losses", "tie": "ties"}[outcome]
    ensure_user(username)
    with _conn() as c:
        c.execute(f"UPDATE users SET {col} = {col} + 1 WHERE username = ?", (username,))
    return get_record(username)


# ---- matches ---------------------------------------------------------------
def create_match(
    match_id: str,
    username: str,
    opponent_team: str,
    opponent_json: list,
    prompts_json: list,
    mode: str = "offline",
) -> None:
    with _conn() as c:
        c.execute(
            """INSERT INTO matches
               (id, username, mode, opponent_team, opponent_json, prompts_json,
                status, created_at)
               VALUES (?,?,?,?,?,?, 'open', ?)""",
            (
                match_id,
                username,
                mode,
                opponent_team,
                json.dumps(opponent_json),
                json.dumps(prompts_json),
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
    d["prompts_json"] = json.loads(d["prompts_json"])
    d["result_json"] = json.loads(d["result_json"]) if d["result_json"] else None
    return d


def resolve_match(match_id: str, result_json: dict) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE matches SET status = 'resolved', result_json = ? WHERE id = ?",
            (json.dumps(result_json), match_id),
        )
