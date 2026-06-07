"""Live PvP test against a real uvicorn server (two clients, one event loop)."""
import asyncio
import json
import sys

import websockets

URL = "ws://127.0.0.1:8021/ws/pvp?username="


async def recv_until(ws, types, cap=40):
    for _ in range(cap):
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        if m["type"] in types:
            return m
    raise AssertionError(f"did not see {types}")


async def main():
    async with websockets.connect(URL + "Alice") as wa, websockets.connect(URL + "Bob") as wb:
        # Alice connects first -> waiting; Bob triggers match.
        ma = await recv_until(wa, {"matched"})
        mb = await recv_until(wb, {"matched"})
        print("matched: Alice vs", ma["opponent"], "| Bob vs", mb["opponent"])
        res_a = res_b = None
        for _ in range(6):
            ra = await recv_until(wa, {"round", "result"})
            rb = await recv_until(wb, {"round", "result"})
            if ra["type"] == "result":
                res_a, res_b = ra["result"], rb["result"]
                break
            ca = next(c for c in ra["current_step"]["candidates"] if c["eligible"])
            cb = next(c for c in rb["current_step"]["candidates"] if c["eligible"])
            await wa.send(json.dumps({"type": "pick", "player_name": ca["name"], "slot": ca["eligible_slots"][0]}))
            await wb.send(json.dumps({"type": "pick", "player_name": cb["name"], "slot": cb["eligible_slots"][0]}))
        if res_a is None:
            res_a = (await recv_until(wa, {"result"}))["result"]
            res_b = (await recv_until(wb, {"result"}))["result"]
        print("Alice:", res_a["outcome"], f"{res_a['your_final']}-{res_a['opponent_final']}", "vs", res_a["opponent_team"], "| rec", res_a["record"])
        print("Bob:  ", res_b["outcome"], f"{res_b['your_final']}-{res_b['opponent_final']}", "vs", res_b["opponent_team"], "| rec", res_b["record"])
        assert {res_a["outcome"], res_b["outcome"]} in ({"win", "loss"}, {"tie"})
        print("OK: live PvP end-to-end on a real server, both records updated")


try:
    asyncio.run(asyncio.wait_for(main(), timeout=60))
except Exception as e:
    print("LIVE TEST FAILED:", type(e).__name__, e)
    sys.exit(1)
