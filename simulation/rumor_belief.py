"""
NPCs hear rumors and store distorted beliefs — reputation ripples through memory.
"""

import random

from storage import load, save

MEM_FILE = "characters/npc_memories.json"
RUMOR_FILE = "rumors/rumors.json"
NPC_FILE = "characters/npcs.json"


def spread_rumor_beliefs(tick=None, day=None):
    """Sample recent rumors into NPC memories at low salience."""
    rumors = load(RUMOR_FILE, [])
    if not rumors:
        return

    npcs = load(NPC_FILE, {})
    store = load(MEM_FILE, {})
    recent = rumors[-6:]

    for rumor in recent:
        if random.random() > 0.35:
            continue
        text = rumor.get("text", "")
        if not text:
            continue
        interp = rumor.get("interpretation", "uncertain")
        valence = {
            "dangerous": -0.35, "heroic": 0.25, "suspicious": -0.2,
            "mysterious": -0.1, "false": 0.0, "worrying": -0.25,
            "scandalous": -0.15, "hushed": -0.1,
        }.get(interp, 0.0)

        # Prefer NPCs in same city/area as rumor origin
        rumor_area = rumor.get("area_id")
        rumor_city = rumor.get("city")
        candidates = []
        for nid, n in npcs.items():
            if n.get("status") != "alive":
                continue
            if rumor_area and n.get("area") == rumor_area:
                candidates.append(nid)
            elif rumor_city and n.get("location") == rumor_city:
                candidates.append(nid)
        if not candidates:
            candidates = [nid for nid, n in npcs.items() if n.get("status") == "alive"]
        if not candidates:
            continue
        for nid in random.sample(candidates, k=min(3, len(candidates))):
            npc = npcs.get(nid, {})
            summary = f"heard a rumour ({interp}): {text[:70]}"
            mems = store.setdefault(nid, [])
            if any(summary[:40] in m.get("summary", "") for m in mems[-8:]):
                continue
            mems.append({
                "tick": tick or 0,
                "day": day or 0,
                "summary": summary,
                "valence": round(valence, 2),
                "salience": random.uniform(12, 22),
                "participants": [],
                "location": npc.get("location"),
                "source": "rumor",
                "about_player": "outsider" in text.lower() or "stranger" in text.lower(),
            })
            from simulation.belief_model import update_beliefs_from_rumor
            update_beliefs_from_rumor(npc, rumor, tick=tick, day=day)

    save(MEM_FILE, store)
    save(NPC_FILE, npcs)
