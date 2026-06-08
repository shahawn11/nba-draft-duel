"""WetBanana: autonomous live-PvP player that makes RANDOM picks and instantly
plays again. Signs up (or logs in) as 'WetBanana', then loops forever:
connect -> random picks each round -> on result, immediately reconnect.

Pure stdlib + websockets (no app import needed for random picks), so run with
PYTHONPATH cleared:
    env PYTHONPATH= backend/.venv312/bin/python backend/tests/wetbanana_autopvp.py
"""
import asyncio, json, random, urllib.request, urllib.error, time, sys

API = "https://nba-draft-duel-production.up.railway.app"
WS_BASE = "wss://nba-draft-duel-production.up.railway.app/ws/pvp"
USERNAME = "WetBanana"
PASSWORD = "Banana4Real"   # 8+ chars, has letters + a number (passes validate_password)


def _post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(API + path, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def authenticate():
    """Sign up WetBanana; if it already exists, log in. Returns session token."""
    status, body = _post("/auth/signup", {"username": USERNAME, "password": PASSWORD})
    if status == 200:
        rec = body.get("record") or {}
        print(f"[auth] signed up {USERNAME}  ({rec.get('tier')} {rec.get('rating')}, "
              f"{rec.get('wins')}W-{rec.get('losses')}L)", flush=True)
        return body["token"]
    if status == 409:
        status, body = _post("/auth/login", {"username": USERNAME, "password": PASSWORD})
        if status == 200:
            rec = body.get("record") or {}
            print(f"[auth] logged in {USERNAME}  ({rec.get('tier')} {rec.get('rating')}, "
                  f"{rec.get('wins')}W-{rec.get('losses')}L)", flush=True)
            return body["token"]
    print(f"[auth] FAILED status={status} body={body}", flush=True)
    sys.exit(1)


async def play_one_match(token, game_no, tally):
    import websockets
    url = f"{WS_BASE}?username={USERNAME}&token={token}&display_name={USERNAME}"
    async with websockets.connect(url, open_timeout=25) as ws:
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
            t = m.get("type")
            if t == "matched":
                r = m.get("opponent_record") or {}
                print(f"  matched vs {m['opponent']} ({r.get('tier')} {r.get('rating')}, "
                      f"{r.get('wins')}W-{r.get('losses')}L)", flush=True)
            elif t == "round":
                rnd = m["round"]
                cands = [c for c in m["current_step"]["candidates"]
                         if c.get("eligible") and c.get("eligible_slots")]
                if not cands:
                    continue  # server will autopick
                c = random.choice(cands)
                slot = random.choice(c["eligible_slots"])
                await ws.send(json.dumps({"type": "pick", "round": rnd,
                                          "player_name": c["name"], "slot": slot}))
                print(f"  R{rnd}: {c['name']} ({c.get('decade')}) -> {slot}  [random]", flush=True)
            elif t == "result":
                r = m["result"]
                out = r["outcome"].upper()
                tally[r["outcome"]] = tally.get(r["outcome"], 0) + 1
                print(f"  FINAL: {out}  {round(r['your_final'])}-{round(r['opponent_final'])}"
                      f"{' (OT)' if r.get('overtime') else ''} vs {r['opponent_team']}", flush=True)
                me = r.get("record") or {}
                print(f"  WetBanana now: {me.get('rating')} ({me.get('tier')}), "
                      f"{me.get('wins')}W-{me.get('losses')}L  "
                      f"| session {tally.get('win',0)}W-{tally.get('loss',0)}L"
                      f"-{tally.get('tie',0)}T", flush=True)
                return
            elif t == "opponent_left":
                print("  opponent left.", flush=True)
                return
            elif t == "error":
                print("  server error:", m.get("detail"), flush=True)
                # Token rejected -> caller re-auths
                if "log in" in (m.get("detail") or ""):
                    raise PermissionError(m.get("detail"))
                return


async def main():
    token = authenticate()
    tally = {}
    game_no = 0
    while True:
        game_no += 1
        print(f"\n=== game #{game_no} ({time.strftime('%H:%M:%S')}) connecting... ===", flush=True)
        try:
            await play_one_match(token, game_no, tally)
        except PermissionError:
            print("[auth] token expired, re-authenticating...", flush=True)
            token = authenticate()
            continue
        except Exception as e:
            print(f"  [warn] match error: {type(e).__name__}: {e} -- retrying in 5s", flush=True)
            await asyncio.sleep(5)
            continue
        # "play again right after"
        await asyncio.sleep(1.5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped.", flush=True)
