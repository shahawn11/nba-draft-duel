"""End-to-end smoke test of the match -> draft -> record flow."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_full_flow() -> None:
    user = "smoke_tester"

    # health
    assert client.get("/health").json()["status"] == "ok"

    # start a match
    r = client.post("/match", json={"username": user})
    assert r.status_code == 200, r.text
    match = r.json()
    assert len(match["prompts"]) == 5
    # opponent must NOT be revealed pre-draft
    assert "opponent" not in match and "opponent_team" not in match
    match_id = match["match_id"]

    # naive draft: pick the first not-yet-chosen candidate of each prompt
    picks = []
    chosen: set[str] = set()
    for p in match["prompts"]:
        cand = next(c for c in p["candidates"] if c["name"] not in chosen)
        chosen.add(cand["name"])
        picks.append({"prompt_index": p["index"], "player_name": cand["name"]})
    r = client.post(f"/match/{match_id}/draft", json={"picks": picks})
    assert r.status_code == 200, r.text
    result = r.json()

    assert result["outcome"] in ("win", "loss", "tie")
    assert result["opponent_team"]  # revealed now
    assert len(result["matchups"]) == 5
    assert len(result["your_team"]["players"]) == 5
    total = (
        result["record"]["wins"]
        + result["record"]["losses"]
        + result["record"]["ties"]
    )
    assert total >= 1

    # re-drafting the same match is rejected
    r = client.post(f"/match/{match_id}/draft", json={"picks": picks})
    assert r.status_code == 400

    # invalid candidate rejected
    r2 = client.post("/match", json={"username": user})
    m2 = r2.json()
    bad = [{"prompt_index": p["index"], "player_name": "Nobody McFake"} for p in m2["prompts"]]
    r = client.post(f"/match/{m2['match_id']}/draft", json={"picks": bad})
    assert r.status_code == 400

    # record endpoint reflects results
    rec = client.get(f"/record/{user}").json()
    assert rec["username"] == user

    print("OK:", result["outcome"], "vs", result["opponent_team"],
          "| final", result["your_final"], "-", result["opponent_final"],
          "| record", rec)


if __name__ == "__main__":
    test_full_flow()
