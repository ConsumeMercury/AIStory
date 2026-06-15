"""
Per-NPC episodic memory.

Each tick (after events are flushed) this turns fresh world events into
MEMORIES held by the specific people they happened to or near:
  * the actor and target of an event remember it strongly,
  * co-located NPCs remember it faintly as witnesses,
  * when someone dies, everyone who had a bond with them grieves
    (bereavement), weighted by how close the bond was.

Memories carry a salience (0-100) and an emotional valence (-1..1).
Salience decays every tick; weak memories are forgotten so the store
stays bounded (top MAX_PER_NPC kept). The narrator reads the strongest
memories of whoever is on stage, so the past colours the present.
"""

import random
from storage import load, save

MEM_FILE = "characters/npc_memories.json"
STATE_FILE = "characters/_mem_state.json"
EVENT_FILE = "events/event_log.json"
NPC_FILE = "characters/npcs.json"
REL_FILE = "characters/relationships.json"

MAX_PER_NPC = 24
DECAY = 0.985
FORGET_BELOW = 6.0

# event/action -> (template, valence, base_salience) for actor's memory
_ACTOR_MEM = {
    "help":      ("did a kindness for {target}", 0.4, 30),
    "socialise": ("shared words with {target}", 0.2, 18),
    "fight":     ("was in a brawl", -0.3, 35),
    "trade":     ("struck a deal", 0.1, 14),
    "hunt":      ("hunted in the wilds", 0.2, 28),
    "study":     ("buried themselves in study", 0.1, 12),
}
# things done TO a target create the target's memory
_TARGET_MEM = {
    "help":      ("was helped by {actor}", 0.6, 55),
    "socialise": ("was sought out by {actor}", 0.3, 25),
    "attack":    ("was attacked by {actor}", -0.9, 95),
}


def _name(npcs, nid):
    if nid == "player":
        return "the outsider"
    n = npcs.get(nid)
    return n["name"] if n else "someone"


def _add(store, nid, text, valence, salience, tick, day, participants, location):
    mem = store.setdefault(nid, [])
    mem.append({
        "tick": tick, "day": day, "summary": text,
        "valence": round(valence, 2), "salience": float(salience),
        "participants": participants, "location": location,
    })


def _decay_and_trim(store):
    for nid, mems in list(store.items()):
        for m in mems:
            m["salience"] *= DECAY
        kept = [m for m in mems if m["salience"] >= FORGET_BELOW]
        kept.sort(key=lambda m: m["salience"], reverse=True)
        store[nid] = kept[:MAX_PER_NPC]


def process_memories():
    events = load(EVENT_FILE, [])
    if not isinstance(events, list) or not events:
        return
    npcs = load(NPC_FILE, {})
    rels = load(REL_FILE, {})
    store = load(MEM_FILE, {})
    state = load(STATE_FILE, {"processed": []})
    processed = set(state.get("processed", []))

    # decay existing memories once per call
    _decay_and_trim(store)

    fresh = [e for e in events[-60:] if isinstance(e, dict) and e.get("id") not in processed]

    for e in fresh:
        eid = e.get("id")
        if eid:
            processed.add(eid)
        actor = e.get("actor")
        target = e.get("target")
        action = e.get("action", "")
        etype = e.get("type", "")
        loc = e.get("location")
        tick = e.get("tick")
        day = None  # filled by narrator from world if needed

        # actor's own memory
        if actor and actor != "player" and action in _ACTOR_MEM:
            tmpl, val, sal = _ACTOR_MEM[action]
            _add(store, actor, tmpl.format(target=_name(npcs, target) if target else "someone"),
                 val, sal, tick, day, [a for a in (actor, target) if a], loc)

        # target's memory (incl. being attacked by the player)
        key = "attack" if etype == "combat" else action
        if target and key in _TARGET_MEM:
            tmpl, val, sal = _TARGET_MEM[key]
            _add(store, target, tmpl.format(actor=_name(npcs, actor)),
                 val, sal, tick, day, [a for a in (actor, target) if a], loc)

        # witnesses: co-located NPCs remember violence faintly
        if etype in ("combat", "conflict") and loc:
            witnesses = [i for i, n in npcs.items()
                         if n.get("location") == loc and i not in (actor, target)
                         and n.get("status") == "alive"]
            for w in random.sample(witnesses, k=min(3, len(witnesses))):
                _add(store, w, "saw violence done nearby", -0.3, 22, tick, day,
                     [a for a in (actor, target) if a], loc)

        # bereavement: a death is felt by everyone who had a bond with the dead
        if etype == "death" and actor:
            dead = actor
            dead_name = _name(npcs, dead)
            for other_id, book in rels.items():
                bond = book.get(dead)
                if not bond:
                    continue
                closeness = bond.get("affection", 0) + bond.get("familiarity", 0) * 0.5
                if closeness < 20:
                    continue
                sal = min(100, 40 + closeness * 0.5)
                _add(store, other_id, f"lost {dead_name}", -1.0, sal, tick, day,
                     [dead], loc)

    _decay_and_trim(store)
    save(MEM_FILE, store)
    state["processed"] = list(processed)[-3000:]
    save(STATE_FILE, state)


def top_memories(npc_id, n=4):
    store = load(MEM_FILE, {})
    mems = store.get(npc_id, [])
    return sorted(mems, key=lambda m: m["salience"], reverse=True)[:n]
