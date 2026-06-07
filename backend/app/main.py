"""
NBA Draft Duel — FastAPI backend.

Endpoints:
  GET  /health
  POST /match               start an offline match -> prompts (opponent hidden)
  GET  /match/{id}          inspect a match (prompts; result if resolved)
  POST /match/{id}/draft    submit your 5 picks -> scored result + updated record
  GET  /record/{username}   current W/L/T record
  GET  /teams               current NBA teams available as opponents

Run:  uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, WebSocket, Header
from fastapi.middleware.cors import CORSMiddleware

from . import db, game, live, auth, moderation, config
from .ratelimit import RateLimitMiddleware
from .models import (
    AuthRequest,
    AvatarRequest,
    NewMatchRequest,
    PickRequest,
    Record,
)

app = FastAPI(title="5v5 Duel", version="0.2.0")

# Ensure schema exists as soon as the app module is imported (covers TestClient
# usage and any ASGI server, not just the startup event).
db.init_db()

# Per-IP rate limiting (Redis-backed in prod; in-memory fallback locally).
app.add_middleware(RateLimitMiddleware)

# Allowed origins come from config (env-driven for prod domains).
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "db": db.backend(),
        "db_ready": db.ping(),
        "pool_source": game.dataset.source(),
        "opponent_season": game.dataset.current_season(),
        "starters_source": game.dataset.starters_source(),
    }


@app.get("/teams")
def teams() -> dict:
    return {"current_teams": game.list_current_teams()}


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _authorize_identity(username: str, token: str | None) -> None:
    """A registered username may only be written to by its owner (valid token).
    Guest ids (no account) are open."""
    if db.account_exists(username):
        if db.username_for_token(token) != username:
            raise HTTPException(status_code=403, detail="log in to play as this account")


@app.post("/match")
def create_match(req: NewMatchRequest, authorization: str | None = Header(default=None)) -> dict:
    """Start an offline match -> returns the first draft step (opponent hidden)."""
    _authorize_identity(req.username, _bearer(authorization))
    if req.display_name and not db.account_exists(req.username):
        err = moderation.validate_display_name(req.display_name)
        if err:
            raise HTTPException(status_code=400, detail=err)
        db.set_display_name(req.username, req.display_name)
    return game.new_match(req.username)


@app.get("/match/{match_id}")
def get_match(match_id: str) -> dict:
    match = db.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="match not found")
    view = game._public_view(match, match["state_json"])
    if match["status"] == "resolved":
        view["result"] = match["result_json"]
    return view


@app.post("/match/{match_id}/pick")
def submit_pick(match_id: str, req: PickRequest) -> dict:
    """Draft a player into a chosen open slot. Returns next step or final result."""
    try:
        return game.pick(match_id, req.player_name, req.slot)
    except game.DraftError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/record/{username}", response_model=Record)
def record(username: str) -> Record:
    return Record(**db.get_record(username))


@app.post("/avatar", response_model=Record)
def set_avatar(req: AvatarRequest, authorization: str | None = Header(default=None)) -> Record:
    """Select a rank avatar. Registered accounts require their token; the chosen
    avatar must be unlocked by the player's peak rating."""
    _authorize_identity(req.username, _bearer(authorization))
    try:
        return Record(**db.set_avatar(req.username, req.avatar))
    except ValueError:
        raise HTTPException(status_code=403, detail="that avatar is still locked")


@app.get("/leaderboard")
def leaderboard(limit: int = 20) -> dict:
    return {"leaderboard": db.leaderboard(min(max(limit, 1), 100))}


# ---- auth ------------------------------------------------------------------
@app.post("/auth/signup")
def signup(req: AuthRequest) -> dict:
    uname = req.username.strip()
    err = moderation.validate_username(uname) or moderation.validate_password(req.password)
    if err:
        raise HTTPException(status_code=400, detail=err)
    if db.account_exists(uname):
        raise HTTPException(status_code=409, detail="username already taken")
    pw_hash, salt = auth.hash_password(req.password)
    db.create_account(uname, pw_hash, salt)
    db.ensure_user(uname)
    if req.guest_id:
        db.transfer_stats(req.guest_id, uname)  # keep current guest stats
    db.set_display_name(uname, uname, force=True)  # the username is now their official name
    token = auth.new_token()
    db.create_session(uname, token)
    return {"token": token, "username": uname, "record": db.get_record(uname)}


@app.post("/auth/login")
def login(req: AuthRequest) -> dict:
    acct = db.get_account(req.username.strip())
    if not acct or not auth.verify_password(req.password, acct["pw_hash"], acct["salt"]):
        raise HTTPException(status_code=401, detail="invalid username or password")
    token = auth.new_token()
    db.create_session(acct["username"], token)
    return {"token": token, "username": acct["username"], "record": db.get_record(acct["username"])}


@app.post("/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    tok = _bearer(authorization)
    if tok:
        db.delete_session(tok)
    return {"ok": True}


@app.get("/auth/me")
def me(authorization: str | None = Header(default=None)) -> dict:
    uname = db.username_for_token(_bearer(authorization))
    if not uname:
        raise HTTPException(status_code=401, detail="not logged in")
    return {"username": uname, "record": db.get_record(uname)}


@app.websocket("/ws/pvp")
async def ws_pvp(ws: WebSocket) -> None:
    """Live real-time PvP: matchmaking + synchronized timed draft."""
    await ws.accept()
    username = (ws.query_params.get("username") or "anon")[:40]
    token = ws.query_params.get("token")
    if db.account_exists(username) and db.username_for_token(token) != username:
        await ws.send_json({"type": "error", "detail": "log in to play as this account"})
        await ws.close()
        return
    display_name = ws.query_params.get("display_name")
    if display_name and not db.account_exists(username) and not moderation.validate_display_name(display_name):
        db.set_display_name(username, display_name)
    await live.manager.handle(ws, username)
