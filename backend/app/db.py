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
    opponent_json  TEXT NOT NULL,   -- frozen opponent lineup (hidden until resolve)
    state_json     TEXT NOT NULL,   -- evolving draft state (slot order, picks, current step)
    status         TEXT NOT NULL DEFAULT 'open',  -- open | resolved
    result_json    TEXT,            -- scored DuelResult once drafted
    created_at     REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS submitted_lineups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL,
    players_json TEXT NOT NULL,     -- the drafted five (list of player dicts, slot=position)
    label       TEXT,               -- how this squad reads as an opponent
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


# ---- async PvP opponent pool ----------------------------------------------
def save_submitted_lineup(username: str, players_json: list, label: str) -> None:
    """Store a completed drafted five so future PvP matches can face it."""
    with _conn() as c:
        c.execute(
            "INSERT INTO submitted_lineups(username, players_json, label, created_at) VALUES (?,?,?,?)",
            (username, json.dumps(players_json), label, time.time()),
        )


def random_submitted_lineup(exclude_username: str | None = None) -> dict | None:
    """Return a random previously-submitted lineup, preferably from someone else."""
    with _conn() as c:
        row = c.execute(
            "SELECT username, players_json, label FROM submitted_lineups "
            "WHERE username != ? ORDER BY RANDOM() LIMIT 1",
            (exclude_username or "",),
        ).fetchone()
        if row is None:
            # no rivals from other users yet
            return None
    return {
        "username": row["username"],
        "players": json.loads(row["players_json"]),
        "label": row["label"],
    }
