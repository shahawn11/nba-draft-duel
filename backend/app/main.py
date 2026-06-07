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
    DraftRequest,
    MatchOut,
    NewMatchRequest,
    Record,
    ResultOut,
)

app = FastAPI(title="NBA Draft Duel", version="0.1.0")

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


@app.post("/match", response_model=MatchOut)
def create_match(req: NewMatchRequest) -> MatchOut:
    data = game.new_match(req.username)
    return MatchOut(**data)


@app.get("/match/{match_id}")
def get_match(match_id: str) -> dict:
    match = db.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="match not found")
    out = {
        "match_id": match["id"],
        "username": match["username"],
        "mode": match["mode"],
        "status": match["status"],
        "prompts": match["prompts_json"],
    }
    # Reveal opponent + result only once resolved.
    if match["status"] == "resolved":
        out["result"] = match["result_json"]
    return out


@app.post("/match/{match_id}/draft", response_model=ResultOut)
def submit_draft(match_id: str, req: DraftRequest) -> ResultOut:
    try:
        payload = game.resolve_draft(
            match_id, [p.model_dump() for p in req.picks]
        )
    except game.DraftError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ResultOut(**payload)


@app.get("/record/{username}", response_model=Record)
def record(username: str) -> Record:
    return Record(**db.get_record(username))
