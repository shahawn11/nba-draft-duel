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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import db, game
from .models import (
    NewMatchRequest,
    PickRequest,
    Record,
)

app = FastAPI(title="NBA Draft Duel", version="0.2.0")

# Ensure schema exists as soon as the app module is imported (covers TestClient
# usage and any ASGI server, not just the startup event).
db.init_db()

# Frontend (Vite dev server) will call this cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "pool_source": game.dataset.source()}


@app.get("/teams")
def teams() -> dict:
    return {"current_teams": game.list_current_teams()}


@app.post("/match")
def create_match(req: NewMatchRequest) -> dict:
    """Start a match -> returns the first draft step (opponent hidden)."""
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
