"""Kiro plays live PvP with a STRATEGY:
   value = real score_player rating + slot fit (assists@PG, scoring@SG/SF, height@PF/C).
   Maximizes team strength AND matchup wins (size/fit)."""
import asyncio, json
import websockets
from app.scoring import score_player
from app.models import player_from_dict

URL = "wss://nba-draft-duel-production.up.railway.app/ws/pvp?username=Kiro&display_name=Kiro"

def value(c, slot):
    base = score_player(player_from_dict({**c, "position": slot})).total
    h = c.get("height_in") or 0
    ppg = c.get("ppg") or 0; apg = c.get("apg") or 0
    if slot == "C":   base += max(0, h - 80) * 0.8        # tallest rim anchor
    elif slot == "PF":base += max(0, h - 78) * 0.5
    elif slot == "PG":base += max(0, apg - 5) * 0.6       # true floor general
    else:             base += max(0, ppg - 16) * 0.25     # scoring SG/SF
    return base

async def main():
    async with websockets.connect(URL, open_timeout=20) as ws:
        open_slots = {"PG","SG","SF","PF","C"}
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
            t = m.get("type")
            if t == "matched":
                r = m.get("opponent_record") or {}
                print(f"MATCHED vs {m['opponent']} ({r.get('tier')} {r.get('rating')}, {r.get('wins')}W-{r.get('losses')}L)", flush=True)
            elif t == "round":
                rnd = m["round"]
                cands = [c for c in m["current_step"]["candidates"] if c.get("eligible") and c.get("eligible_slots")]
                best = None
                for c in cands:
                    for slot in c["eligible_slots"]:
                        if slot not in open_slots: continue
                        v = value(c, slot)
                        if best is None or v > best[0]:
                            best = (v, c, slot)
                _, c, slot = best
                open_slots.discard(slot)
                await ws.send(json.dumps({"type":"pick","round":rnd,"player_name":c["name"],"slot":slot}))
                print(f"R{rnd}: {c['name']} ({c.get('decade')}) -> {slot}  [val {best[0]:.1f}]", flush=True)
            elif t == "result":
                r = m["result"]
                print(f"\nFINAL: {r['outcome'].upper()} for Kiro  {round(r['your_final'])}-{round(r['opponent_final'])}"
                      f"{' (OT)' if r.get('overtime') else ''} vs {r['opponent_team']}", flush=True)
                me = r.get("record") or {}
                print(f"Kiro now: {me.get('rating')} ({me.get('tier')}), {me.get('wins')}W-{me.get('losses')}L", flush=True)
                return
            elif t == "opponent_left":
                print("Opponent left.", flush=True); return
            elif t == "error":
                print("server error:", m.get("detail"), flush=True)

asyncio.run(main())
