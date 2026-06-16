"""
Per-NPC episodic memory.

Events become memories for actors, targets, witnesses, and bereaved kin.
Player actions are recorded for every NPC present so the past shapes future
behaviour in simulation and narration.
"""

import random
from storage import load, save

MEM_FILE = "characters/npc_memories.json"
STATE_FILE = "characters/_mem_state.json"
EVENT_FILE = "events/event_log.json"
NPC_FILE = "characters/npcs.json"
REL_FILE = "characters/relationships.json"

MAX_PER_NPC = 28
DECAY = 0.984
FORGET_BELOW = 6.0

_ACTOR_MEM = {
    "help":      ("did a kindness for {target}", 0.4, 30),
    "socialise": ("shared words with {target}", 0.2, 18),
    "fight":     ("was in a brawl", -0.3, 35),
    "trade":     ("struck a deal", 0.1, 14),
    "hunt":      ("hunted in the wilds", 0.2, 28),
    "study":     ("buried themselves in study", 0.1, 12),
}

_TARGET_MEM = {
    "help":      ("was helped by {actor}", 0.6, 55),
    "socialise": ("was sought out by {actor}", 0.3, 25),
    "attack":    ("was attacked by {actor}", -0.9, 95),
}

# player action tag -> (summary template, valence, salience for direct target)
# {action} = shortened player action text
_PLAYER_MEM = {
    "attack":    ("the outsider attacked them", -0.95, 98),
    "help":      ("the outsider helped them", 0.7, 60),
    "gift":      ("the outsider gave them something", 0.5, 45),
    "threat":    ("the outsider threatened them", -0.8, 75),
    "insult":    ("the outsider insulted them", -0.6, 55),
    "theft":     ("the outsider tried to steal from them", -0.85, 80),
    "trade":     ("the outsider traded with them", 0.15, 22),
    "socialise": ("the outsider spoke with them", 0.2, 28),
    "observation": ("the outsider watched them too closely", -0.15, 20),
    "general":   ("the outsider did something they won't forget", 0.0, 18),
    "withdrawal": ("the outsider turned away without a word", -0.1, 15),
    "rest":      ("the outsider rested nearby", 0.05, 10),
}


def _name(npcs, nid):
    if nid == "player":
        return "the outsider"
    n = npcs.get(nid)
    return n["name"] if n else "someone"


def _add(store, nid, text, valence, salience, tick, day, participants, location, source="world"):
    mem = store.setdefault(nid, [])
    mem.append({
        "tick": tick, "day": day, "summary": text,
        "valence": round(valence, 2), "salience": float(salience),
        "participants": participants, "location": location,
        "source": source,
        "about_player": "player" in (participants or []) or "outsider" in text,
    })


def _decay_and_trim(store):
    for nid, mems in list(store.items()):
        for m in mems:
            m["salience"] *= DECAY
        kept = [m for m in mems if m["salience"] >= FORGET_BELOW]
        kept.sort(key=lambda m: m["salience"], reverse=True)
        store[nid] = kept[:MAX_PER_NPC]


def record_player_action(present_npc_ids, memory_tag, action_text, location, tick, day,
                         target_id=None, intensity=1.0):
    """
    Write episodic memories for NPCs who witnessed or were targeted by the player.
    Called synchronously from story_loop on every player turn.
    """
    store = load(MEM_FILE, {})
    tpl, val, sal = _PLAYER_MEM.get(memory_tag, _PLAYER_MEM["general"])
    action_snip = (action_text or "")[:80].strip()
    if action_snip:
        witness_text = f"saw the outsider: {action_snip}"
    else:
        witness_text = f"saw the outsider nearby"

    for nid in present_npc_ids:
        if nid == target_id:
            text = tpl
            s = min(100, sal * intensity)
            v = val
        else:
            text = witness_text
            s = min(50, 14 * intensity)
            v = val * 0.35

        _add(store, nid, text, v, s, tick, day, ["player"], location, source="player")
        if target_id and nid == target_id and action_snip:
            _add(store, nid, f"when they {action_snip[:50]}", val, s * 0.6, tick, day,
                 ["player"], location, source="player")

    _decay_and_trim(store)
    save(MEM_FILE, store)


def player_memories(npc_id, n=5):
    """Memories involving the player, strongest first."""
    mems = load(MEM_FILE, {}).get(npc_id, [])
    about = [m for m in mems if m.get("about_player") or "outsider" in m.get("summary", "")]
    return sorted(about, key=lambda m: m["salience"], reverse=True)[:n]


def memory_behavior(npc_id):
    """
    Behavioural directive for narrator/sim based on what this NPC remembers
    about the player and recent strong memories.
    """
    about = player_memories(npc_id, 4)
    if not about:
        return "No history with the player — react as a stranger would."

    top = about[0]
    val = top.get("valence", 0)
    sal = top.get("salience", 0)
    summary = top.get("summary", "")

    if val <= -0.7 and sal > 40:
        return (
            f"Remembers: {summary}. Behaviour: fear, hostility, or cold refusal — "
            f"do not greet warmly; body language first."
        )
    if val <= -0.3 and sal > 25:
        return (
            f"Remembers: {summary}. Behaviour: guarded, shorter answers, watches exits."
        )
    if val >= 0.5 and sal > 35:
        return (
            f"Remembers: {summary}. Behaviour: slightly softer, may offer small help — "
            f"still not effusive."
        )
    if val >= 0.2:
        return f"Remembers: {summary}. Behaviour: neutral-positive, willing to talk briefly."

    return f"Remembers: {summary}. Behaviour: cautious, noncommittal."


def process_memories():
    events = load(EVENT_FILE, [])
    if not isinstance(events, list) or not events:
        return
    npcs = load(NPC_FILE, {})
    rels = load(REL_FILE, {})
    store = load(MEM_FILE, {})
    state = load(STATE_FILE, {"processed": []})
    processed = set(state.get("processed", []))

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
        day = e.get("day")

        if actor and actor != "player" and action in _ACTOR_MEM:
            tmpl, val, sal = _ACTOR_MEM[action]
            _add(store, actor, tmpl.format(target=_name(npcs, target) if target else "someone"),
                 val, sal, tick, day, [a for a in (actor, target) if a], loc)

        key = "attack" if etype == "combat" else action
        if target and key in _TARGET_MEM:
            tmpl, val, sal = _TARGET_MEM[key]
            _add(store, target, tmpl.format(actor=_name(npcs, actor)),
                 val, sal, tick, day, [a for a in (actor, target) if a], loc)

        # player combat — target remembers (also handled in record_player_action, but events persist)
        if etype == "combat" and actor == "player" and target:
            _add(store, target, "was attacked by the outsider", -0.9, 95, tick, day,
                 ["player", target], loc, source="player")

        if etype in ("combat", "conflict") and loc:
            witnesses = [
                i for i, n in npcs.items()
                if n.get("status") == "alive" and i not in (actor, target)
                and (n.get("location") == loc or n.get("area") == loc)
            ]
            for w in random.sample(witnesses, k=min(3, len(witnesses))):
                _add(store, w, "saw violence done nearby", -0.3, 22, tick, day,
                     [a for a in (actor, target) if a], loc)

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
