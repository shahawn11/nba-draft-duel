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
    rating   INTEGER NOT NULL DEFAULT 1000,
    avatar       TEXT NOT NULL DEFAULT 'amateur',
    peak_rating  INTEGER NOT NULL DEFAULT 1000,
    achievements TEXT NOT NULL DEFAULT '',
    games_played INTEGER NOT NULL DEFAULT 0,
    games_won    INTEGER NOT NULL DEFAULT 0
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
        if "avatar" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN avatar TEXT NOT NULL DEFAULT 'amateur'")
        if "peak_rating" not in cols:
            # Backfill peak to at least the current rating so existing players
            # keep any rank avatars their rating already qualifies for.
            c.execute(f"ALTER TABLE users ADD COLUMN peak_rating INTEGER NOT NULL DEFAULT {rating.START_RATING}")
            c.execute("UPDATE users SET peak_rating = rating WHERE rating > peak_rating")
        if "achievements" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN achievements TEXT NOT NULL DEFAULT ''")
        if "games_played" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN games_played INTEGER NOT NULL DEFAULT 0")
        if "games_won" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN games_won INTEGER NOT NULL DEFAULT 0")


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
    peak = max(d.get("peak_rating") or r, r)
    d["peak_rating"] = peak
    d["tier"] = rating.tier_name(r)
    nxt = rating.next_tier(r)
    d["next_tier"] = nxt["name"] if nxt else None
    d["next_tier_at"] = nxt["min"] if nxt else None
    d["display_name"] = d.get("display_name") or d.get("username")
    # Avatars: default to the always-unlocked Amateur brown shirt.
    d["avatar"] = d.get("avatar") or "amateur"
    earned = [a for a in (d.get("achievements") or "").split(",") if a]
    d["achievements"] = earned
    d["unlocked"] = rating.unlocked_avatar_ids(peak) + earned
    # Ties are no longer tracked in records (OT resolves all games).
    d.pop("ties", None)
    return d


def get_record(username: str) -> dict:
    with _conn() as c:
        row = c.execute(
            "SELECT username, wins, losses, rating, peak_rating, display_name, avatar, achievements "
            "FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row:
        return _record_dict({"username": username, "wins": 0, "losses": 0,
                             "rating": rating.START_RATING,
                             "peak_rating": rating.START_RATING, "avatar": "amateur",
                             "achievements": ""})
    return _record_dict(row)


def set_avatar(username: str, avatar_id: str) -> dict:
    """Set the player's avatar. Rank avatars require the tier to be unlocked
    (by peak rating); unknown/locked ids are rejected with ValueError."""
    ensure_user(username)
    rec = get_record(username)
    if avatar_id not in rec["unlocked"]:
        raise ValueError("locked")
    with _conn() as c:
        c.execute("UPDATE users SET avatar = ? WHERE username = ?", (avatar_id, username))
    return get_record(username)


def award_achievements(username: str, won: bool, players: list[dict]) -> tuple[dict, list[str]]:
    """Record a finished match for `username` and unlock any newly-earned
    achievement avatars. `players` is the user's own scored lineup (each with
    `status` and a `game` box line). Cosmetic only -- never touches rating/W-L.
    Returns (updated_record, newly_unlocked_ids)."""
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
        big = sum(1 for k in ("pts", "reb", "ast") if (g.get(k) or 0) >= 10)
        if big >= 3:
            newly.add("tripledouble")

    with _conn() as c:
        row = c.execute(
            "SELECT achievements, games_played, games_won FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        earned = {a for a in ((row["achievements"] if row else "") or "").split(",") if a}
        gp = (row["games_played"] if row else 0) + 1
        gw = (row["games_won"] if row else 0) + (1 if won else 0)
        if gp >= 25:
            newly.add("games25")
        if gw >= 100:
            newly.add("wins100")
        newly &= rating.ACHIEVEMENT_IDS
        newly_unlocked = sorted(newly - earned)   # only those not already earned
        earned |= newly
        c.execute(
            "UPDATE users SET achievements = ?, games_played = ?, games_won = ? WHERE username = ?",
            (",".join(sorted(earned)), gp, gw, username),
        )
    return get_record(username), newly_unlocked


def apply_result(username: str, outcome: str) -> dict:
    """outcome in {'win','loss'}; updates W/L + rating (+peak); returns record.
    Ties no longer occur (OT resolves them) but are tolerated as a no-op."""
    ensure_user(username)
    if outcome == "tie":
        return get_record(username)
    col = {"win": "wins", "loss": "losses"}[outcome]
    with _conn() as c:
        row = c.execute("SELECT rating, peak_rating FROM users WHERE username = ?", (username,)).fetchone()
        cur = row["rating"] if row and row["rating"] is not None else rating.START_RATING
        peak = row["peak_rating"] if row and row["peak_rating"] is not None else cur
        new_rating = rating.apply_outcome(cur, outcome)
        new_peak = max(peak, new_rating)
        c.execute(
            f"UPDATE users SET {col} = {col} + 1, rating = ?, peak_rating = ? WHERE username = ?",
            (new_rating, new_peak, username),
        )
    return get_record(username)


def leaderboard(limit: int = 20) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT username, wins, losses, rating, peak_rating, display_name, avatar, achievements "
            "FROM users "
            "WHERE (wins + losses) > 0 "
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
        s = c.execute("SELECT wins, losses, ties, rating, peak_rating, avatar, "
                      "achievements, games_played, games_won FROM users WHERE username = ?", (src,)).fetchone()
        if not s:
            return
        c.execute("INSERT OR IGNORE INTO users(username) VALUES (?)", (dst,))
        d = c.execute("SELECT peak_rating, achievements, games_played, games_won "
                      "FROM users WHERE username = ?", (dst,)).fetchone()
        dst_peak = d["peak_rating"] if d and d["peak_rating"] is not None else rating.START_RATING
        new_peak = max(dst_peak, s["peak_rating"] or s["rating"], s["rating"])
        src_ach = {a for a in (s["achievements"] or "").split(",") if a}
        dst_ach = {a for a in ((d["achievements"] if d else "") or "").split(",") if a}
        merged_ach = ",".join(sorted(src_ach | dst_ach))
        gp = (d["games_played"] if d else 0) + (s["games_played"] or 0)
        gw = (d["games_won"] if d else 0) + (s["games_won"] or 0)
        c.execute(
            "UPDATE users SET wins = wins + ?, losses = losses + ?, ties = ties + ?, "
            "rating = ?, peak_rating = ?, avatar = ?, achievements = ?, "
            "games_played = ?, games_won = ? WHERE username = ?",
            (s["wins"], s["losses"], s["ties"], s["rating"], new_peak,
             s["avatar"] or "amateur", merged_ach, gp, gw, dst),
        )
        c.execute("DELETE FROM users WHERE username = ?", (src,))
