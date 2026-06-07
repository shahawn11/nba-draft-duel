"""End-to-end smoke test of the sequential match -> pick* -> result flow."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _first_eligible(step: dict) -> str:
    cand = next(c for c in step["candidates"] if c["eligible"])
    return cand["name"]


def test_full_flow() -> None:
    user = "smoke_tester"

    assert client.get("/health").json()["status"] == "ok"

    # start a match -> first step
    r = client.post("/match", json={"username": user})
    assert r.status_code == 200, r.text
    view = r.json()
    match_id = view["match_id"]
    assert view["total_slots"] == 5
    assert view["picks_made"] == 0
    assert "opponent" not in view and "result" not in view  # blind
    step = view["current_step"]
    assert step and step["slot"] in ("PG", "SG", "SF", "PF", "C")
    assert len(step["candidates"]) >= 3  # top-N pool
    # every step must offer at least one eligible player
    assert any(c["eligible"] for c in step["candidates"])

    result = None
    for n in range(5):
        name = _first_eligible(step)
        r = client.post(f"/match/{match_id}/pick", json={"player_name": name})
        assert r.status_code == 200, r.text
        body = r.json()
        if body.get("done"):
            result = body["result"]
            break
        assert body["picks_made"] == n + 1
        step = body["current_step"]
        assert any(c["eligible"] for c in step["candidates"])

    assert result is not None, "draft should resolve after 5 picks"
    assert result["outcome"] in ("win", "loss", "tie")
    assert result["opponent_team"]
    assert len(result["matchups"]) == 5
    assert len(result["your_team"]["players"]) == 5
    # drafted players occupy exactly the 5 slots
    slots = {p["position"] for p in result["your_team"]["players"]}
    assert slots == {"PG", "SG", "SF", "PF", "C"}

    # picking again after resolution is rejected
    r = client.post(f"/match/{match_id}/pick", json={"player_name": "anyone"})
    assert r.status_code == 400

    # ineligible / unknown player rejected mid-draft
    r2 = client.post("/match", json={"username": user})
    m2 = r2.json()
    r = client.post(f"/match/{m2['match_id']}/pick", json={"player_name": "Nobody McFake"})
    assert r.status_code == 400

    rec = client.get(f"/record/{user}").json()
    assert rec["wins"] + rec["losses"] + rec["ties"] >= 1
    print("OK:", result["outcome"], "vs", result["opponent_team"],
          "| final", result["your_final"], "-", result["opponent_final"],
          "| slots", sorted(slots), "| record", rec)


if __name__ == "__main__":
    test_full_flow()
