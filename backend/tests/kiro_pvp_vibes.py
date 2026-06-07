"""Kiro plays live PvP in VIBES MODE: no math, just draft the names a casual
fan recognizes, into a sensible open slot. Replicates a real user."""
import asyncio, json, random
import websockets

URL = "wss://nba-draft-duel-production.up.railway.app/ws/pvp?username=Kiro&display_name=Kiro"

# Names a casual fan instantly recognizes (no stats involved).
FAMOUS = {
    "Michael Jordan","LeBron James","Kobe Bryant","Shaquille O'Neal","Stephen Curry",
    "Kevin Durant","Magic Johnson","Larry Bird","Wilt Chamberlain","Kareem Abdul-Jabbar",
    "Tim Duncan","Hakeem Olajuwon","Allen Iverson","Kevin Garnett","Dirk Nowitzki",
    "Giannis Antetokounmpo","Luka Dončić","Nikola Jokić","Joel Embiid","James Harden",
    "Russell Westbrook","Scottie Pippen","Charles Barkley","Karl Malone","John Stockton",
    "Patrick Ewing","David Robinson","Gary Payton","Jason Kidd","Steve Nash","Dwyane Wade",
    "Chris Paul","Vince Carter","Tracy McGrady","Ray Allen","Paul Pierce","Damian Lillard",
    "Anthony Davis","Kawhi Leonard","Kyrie Irving","Carmelo Anthony","Victor Wembanyama",
}

def vibe(c):
    # A human: grabs a recognizable star if present; otherwise eyeballs the
    # stat line on the card (mostly points) and takes who looks good. No impact
    # metric, no height/fit math — just what's visible.
    card = (c.get("ppg") or 0) + 0.4*(c.get("rpg") or 0) + 0.6*(c.get("apg") or 0)
    fame = 100 if c["name"] in FAMOUS else 0
    return fame + card

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
                c = max(cands, key=vibe)                       # the name I recognize
                slot = next(s for s in c["eligible_slots"] if s in open_slots)
                open_slots.discard(slot)
                known = "★" if c["name"] in FAMOUS else "?"
                await ws.send(json.dumps({"type":"pick","round":rnd,"player_name":c["name"],"slot":slot}))
                print(f"R{rnd}: {c['name']} {known} ({c.get('decade')}) -> {slot}", flush=True)
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
