"""Autonomous PvP bot: signs up (or logs in) as 'jose22', then plays live PvP
forever making RANDOM legal picks and hitting "play again" right after each
match. Runs until killed (Ctrl-C / SIGTERM).

Usage (from backend/, venv python, PYTHONPATH cleared is fine -- no app import):
    env PYTHONPATH= .venv312/bin/python tests/jose22_autopvp.py
"""
import asyncio
import json
import random
import sys
import urllib.request
import urllib.error

import websockets

API = "https://nba-draft-duel-production.up.railway.app"
WS_BASE = "wss://nba-draft-duel-production.up.railway.app/ws/pvp"
USERNAME = "jose22"
PASSWORD = "Jose2024!"            # 8+ chars, has letters + a number
DISPLAY = "jose22"


def _post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        API + path, data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def authenticate() -> str:
    """Sign up jose22; if already taken, log in. Returns the session token."""
    try:
        res = _post("/auth/signup", {"username": USERNAME, "password": PASSWORD})
        print(f"[auth] signed up as {USERNAME}", flush=True)
        return res["token"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 409:
            res = _post("/auth/login", {"username": USERNAME, "password": PASSWORD})
            print(f"[auth] account existed -> logged in as {USERNAME}", flush=True)
            return res["token"]
        print(f"[auth] signup failed {e.code}: {body}", flush=True)
        raise


async def play_one_match(token: str, n: int) -> bool:
    """Play a single PvP match with random picks. Returns True on a clean finish."""
    url = f"{WS_BASE}?username={USERNAME}&display_name={DISPLAY}&token={token}"
    async with websockets.connect(url, open_timeout=30, close_timeout=5) as ws:
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
            t = m.get("type")
            if t == "waiting":
                print(f"[game {n}] in queue, waiting for opponent…", flush=True)
            elif t == "matched":
                rec = m.get("opponent_record") or {}
                print(f"[game {n}] MATCHED vs {m.get('opponent')} "
                      f"({rec.get('tier')} {rec.get('rating')}, "
                      f"{rec.get('wins')}W-{rec.get('losses')}L)", flush=True)
            elif t == "round":
                rnd = m["round"]
                cands = [c for c in m["current_step"]["candidates"]
                         if c.get("eligible") and c.get("eligible_slots")]
                if not cands:
                    print(f"[game {n}] R{rnd}: no eligible candidates?!", flush=True)
                    continue
                pick = random.choice(cands)                 # RANDOM pick
                slot = random.choice(pick["eligible_slots"])
                await ws.send(json.dumps({"type": "pick", "round": rnd,
                                          "player_name": pick["name"], "slot": slot}))
                print(f"[game {n}] R{rnd}: random -> {pick['name']} "
                      f"({pick.get('decade')} {pick.get('team')}) @ {slot}", flush=True)
            elif t == "result":
                r = m["result"]
                me = r.get("record") or {}
                print(f"[game {n}] FINAL: {r['outcome'].upper()} "
                      f"{round(r['your_final'])}-{round(r['opponent_final'])} vs "
                      f"{r['opponent_team']}{' (OT)' if r.get('overtime') else ''} | "
                      f"jose22 now {me.get('rating')} ({me.get('tier')}) "
                      f"{me.get('wins')}W-{me.get('losses')}L", flush=True)
                return True
            elif t == "opponent_left":
                print(f"[game {n}] opponent left.", flush=True)
                return True
            elif t == "error":
                print(f"[game {n}] server error: {m.get('detail')}", flush=True)
                return False


async def main() -> None:
    token = authenticate()
    n = 0
    while True:                                  # play again, forever
        n += 1
        try:
            await play_one_match(token, n)
        except asyncio.TimeoutError:
            print(f"[game {n}] timed out waiting for message; reconnecting…", flush=True)
        except websockets.ConnectionClosed as e:
            print(f"[game {n}] connection closed ({e}); reconnecting…", flush=True)
        except Exception as e:                   # noqa: BLE001 - keep the loop alive
            print(f"[game {n}] unexpected error: {e!r}; reconnecting…", flush=True)
            # If our token went stale, re-auth.
            try:
                token = authenticate()
            except Exception as e2:              # noqa: BLE001
                print(f"[auth] re-auth failed: {e2!r}; backing off 10s", flush=True)
                await asyncio.sleep(10)
        await asyncio.sleep(1.0)                  # brief "click play again" pause


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[stopped] interrupted by user.", flush=True)
        sys.exit(0)
