"""LeBum autonomously plays live PvP forever, making RANDOM picks and
immediately queuing again after each result ("play again").

- Signs up the account "LeBum" (or logs in if it already exists) to obtain a
  session token, which the /ws/pvp endpoint requires for registered accounts.
- Each round: pick a random eligible candidate into a random open slot.
- After every result (or opponent_left / error), reconnect and play again.
- Runs until killed.

No `app` import -> run with PYTHONPATH= cleared. websockets must be installed.
"""
import asyncio
import json
import random
import sys
import time
import urllib.request

API = "https://nba-draft-duel-production.up.railway.app"
WS_BASE = "wss://nba-draft-duel-production.up.railway.app/ws/pvp"
USERNAME = "LeBum"
PASSWORD = "LeBumKing2026"
DISPLAY = "LeBum"

import websockets


def _post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API + path, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8")), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8")), e.code


def authenticate() -> str:
    """Sign up LeBum; if taken, log in. Returns the session token."""
    body = {"username": USERNAME, "password": PASSWORD}
    out, status = _post("/auth/signup", body)
    if status == 200:
        rec = out.get("record") or {}
        print(f"[auth] signed up {USERNAME} -> token ok  ({rec.get('tier')} {rec.get('rating')}, "
              f"{rec.get('wins')}W-{rec.get('losses')}L)", flush=True)
        return out["token"]
    if status == 409:
        out, status = _post("/auth/login", body)
        if status == 200:
            rec = out.get("record") or {}
            print(f"[auth] logged in {USERNAME} -> token ok  ({rec.get('tier')} {rec.get('rating')}, "
                  f"{rec.get('wins')}W-{rec.get('losses')}L)", flush=True)
            return out["token"]
    raise SystemExit(f"[auth] FAILED status={status} detail={out}")


def random_pick(candidates, open_slots):
    """Choose a random eligible candidate + random open eligible slot."""
    choices = []
    for c in candidates:
        if not (c.get("eligible") and c.get("eligible_slots")):
            continue
        slots = [s for s in c["eligible_slots"] if s in open_slots]
        if slots:
            choices.append((c, slots))
    if not choices:
        return None, None
    c, slots = random.choice(choices)
    return c, random.choice(slots)


async def play_one_match(token: str, n: int, tally: dict) -> None:
    url = f"{WS_BASE}?username={USERNAME}&display_name={DISPLAY}&token={token}"
    async with websockets.connect(url, open_timeout=25, close_timeout=5) as ws:
        open_slots = {"PG", "SG", "SF", "PF", "C"}
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
            t = m.get("type")
            if t == "waiting":
                print(f"[match {n}] in queue…", flush=True)
            elif t == "matched":
                r = m.get("opponent_record") or {}
                print(f"[match {n}] MATCHED vs {m.get('opponent')} "
                      f"({r.get('tier')} {r.get('rating')}, {r.get('wins')}W-{r.get('losses')}L)", flush=True)
            elif t == "round":
                rnd = m["round"]
                c, slot = random_pick(m["current_step"]["candidates"], open_slots)
                if c is None:
                    print(f"[match {n}] R{rnd}: no eligible pick?!", flush=True)
                    continue
                open_slots.discard(slot)
                await ws.send(json.dumps({"type": "pick", "round": rnd,
                                          "player_name": c["name"], "slot": slot}))
                print(f"[match {n}] R{rnd}: random {c['name']} ({c.get('decade')}) -> {slot}", flush=True)
            elif t == "result":
                r = m["result"]
                outcome = r["outcome"].upper()
                tally[r["outcome"]] = tally.get(r["outcome"], 0) + 1
                me = r.get("record") or {}
                print(f"[match {n}] FINAL: {outcome}  {round(r['your_final'])}-{round(r['opponent_final'])}"
                      f"{' (OT)' if r.get('overtime') else ''} vs {r['opponent_team']}", flush=True)
                print(f"[match {n}] LeBum now: {me.get('rating')} ({me.get('tier')}), "
                      f"{me.get('wins')}W-{me.get('losses')}L  | session tally {tally}", flush=True)
                return
            elif t == "opponent_left":
                print(f"[match {n}] opponent left.", flush=True)
                return
            elif t == "error":
                print(f"[match {n}] server error: {m.get('detail')}", flush=True)
                return


async def main():
    token = authenticate()
    tally = {}
    n = 0
    while True:
        n += 1
        try:
            await play_one_match(token, n, tally)
        except asyncio.TimeoutError:
            print(f"[match {n}] timed out waiting for server; reconnecting…", flush=True)
        except Exception as e:
            print(f"[match {n}] connection error: {type(e).__name__}: {e}; retrying in 5s…", flush=True)
            await asyncio.sleep(5)
            # token may have expired after a long idle; re-auth defensively
            if "log in" in str(e).lower():
                token = authenticate()
        # brief pause then "play again"
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
