"""End-to-end smoke test of the sequential match -> pick(player,slot)* -> result flow."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _first_selectable(step: dict):
    for c in step["candidates"]:
        if c["eligible"] and c["eligible_slots"]:
            return c["name"], c["eligible_slots"][0]
    raise AssertionError("no selectable candidate in step")


def test_full_flow() -> None:
    user = "smoke_tester"

    assert client.get("/health").json()["status"] == "ok"

    r = client.post("/match", json={"username": user})
    assert r.status_code == 200, r.text
    view = r.json()
    match_id = view["match_id"]
    assert view["total_slots"] == 5
    assert sorted(view["open_slots"]) == ["C", "PF", "PG", "SF", "SG"]
    assert "result" not in view  # blind
    step = view["current_step"]
    assert len(step["candidates"]) == 10  # pools are exactly 10 deep
    assert any(c["eligible"] for c in step["candidates"])

    result = None
    for n in range(5):
        name, slot = _first_selectable(step)
        r = client.post(f"/match/{match_id}/pick", json={"player_name": name, "slot": slot})
        assert r.status_code == 200, r.text
        body = r.json()
        if body.get("done"):
            result = body["result"]
            break
        assert body["picks_made"] == n + 1
        assert slot not in body["open_slots"]  # slot consumed
        step = body["current_step"]

    assert result is not None
    assert result["outcome"] in ("win", "loss", "tie")
    assert len(result["matchups"]) == 5
    assert {p["position"] for p in result["your_team"]["players"]} == {"PG", "SG", "SF", "PF", "C"}

    # picking again after resolution rejected
    r = client.post(f"/match/{match_id}/pick", json={"player_name": "x", "slot": "PG"})
    assert r.status_code == 400

    # assigning a player to a slot they can't play is rejected
    r2 = client.post("/match", json={"username": user})
    m2 = r2.json()
    s2 = m2["current_step"]
    # find a player and a slot NOT in their eligibility
    bad = None
    for c in s2["candidates"]:
        for slot in ("PG", "SG", "SF", "PF", "C"):
            if slot not in c["eligible_positions"]:
                bad = (c["name"], slot)
                break
        if bad:
            break
    if bad:
        r = client.post(f"/match/{m2['match_id']}/pick",
                        json={"player_name": bad[0], "slot": bad[1]})
        assert r.status_code == 400, "ineligible slot assignment should be rejected"

    # Offline mode is unranked: result is flagged and W/L/T must NOT change.
    assert result["ranked"] is False
    assert result["rating_change"] == 0
    rec = client.get(f"/record/{user}").json()
    assert rec["wins"] + rec["losses"] == 0
    print("OK:", result["outcome"], "vs", result["opponent_team"],
          "| final", round(result["your_final"]), "-", round(result["opponent_final"]),
          "| unranked, record", rec)


if __name__ == "__main__":
    test_full_flow()
