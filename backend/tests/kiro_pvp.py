"""Kiro plays live PvP: connect to the deployed /ws/pvp and draft the best
available player each round."""
import asyncio, json, sys
import websockets

URL = "wss://nba-draft-duel-production.up.railway.app/ws/pvp?username=Kiro&display_name=Kiro"

def score(c):
    # production proxy: points + rebounds + playmaking
    return (c.get("ppg") or 0) + 1.2*(c.get("rpg") or 0) + 1.5*(c.get("apg") or 0)

async def main():
    async with websockets.connect(URL, open_timeout=20, close_timeout=5) as ws:
        opp = None
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
            t = m.get("type")
            if t == "waiting":
                print("… in queue, waiting for an opponent", flush=True)
            elif t == "matched":
                opp = m.get("opponent")
                rec = m.get("opponent_record") or {}
                print(f"MATCHED vs {opp}  ({rec.get('tier')} {rec.get('rating')}, "
                      f"{rec.get('wins')}W-{rec.get('losses')}L)", flush=True)
            elif t == "round":
                rnd = m["round"]
                cands = [c for c in m["current_step"]["candidates"]
                         if c.get("eligible") and c.get("eligible_slots")]
                best = max(cands, key=score)
                slot = best["eligible_slots"][0]
                await ws.send(json.dumps({"type": "pick", "round": rnd,
                                          "player_name": best["name"], "slot": slot}))
                print(f"R{rnd}: drafted {best['name']} ({best.get('decade')} {best.get('team')}) -> {slot}", flush=True)
            elif t == "result":
                r = m["result"]
                print(f"\nFINAL: {r['outcome'].upper()} for Kiro  "
                      f"{round(r['your_final'])}-{round(r['opponent_final'])} vs {r['opponent_team']}"
                      f"{' (OT)' if r.get('overtime') else ''}", flush=True)
                me = r.get("record") or {}
                print(f"Kiro now: {me.get('rating')} ({me.get('tier')}), "
                      f"{me.get('wins')}W-{me.get('losses')}L", flush=True)
                return
            elif t == "opponent_left":
                print("Opponent left.", flush=True); return
            elif t == "error":
                print("server error:", m.get("detail"), flush=True)

asyncio.run(main())
