"""
Dynamic leadership — when institution leaders die, successors shift priorities.
"""

import random

from storage import load, save
from simulation.event_logger import log_event

INST_FILE = "world/institutions.json"
NPC_FILE = "characters/npcs.json"
RUMOR_FILE = "rumors/rumors.json"


def _eligible_successors(inst, npcs, dead_id):
    members = inst.get("members") or {}
    candidates = []
    for mid, role in members.items():
        if mid == dead_id or npcs.get(mid, {}).get("status") != "alive":
            continue
        score = {"captain": 90, "high_priest": 90, "master": 85, "headmaster": 85,
                 "cleric": 50, "journeyman": 40, "soldier": 35}.get(role, 20)
        score += npcs.get(mid, {}).get("traits", {}).get("ambition", 50) * 0.3
        candidates.append((score, mid, role))
    candidates.sort(reverse=True)
    return candidates


def process_leadership_succession(tick=None, day=None):
    """Check for dead leaders and promote successors."""
    institutions = load(INST_FILE, {})
    npcs = load(NPC_FILE, {})
    rumors = load(RUMOR_FILE, [])
    changed = False

    for inst in institutions.values():
        leader = inst.get("leader")
        if not leader:
            continue
        if npcs.get(leader, {}).get("status") == "alive":
            continue

        old_name = npcs.get(leader, {}).get("name", "the old leader")
        candidates = _eligible_successors(inst, npcs, leader)
        if not candidates:
            inst["leader"] = None
            changed = True
            continue

        _, new_id, role = candidates[0]
        inst["leader"] = new_id
        new_name = npcs.get(new_id, {}).get("name", "someone new")

        arc = inst.get("arc") or {}
        arc["tension"] = min(100, arc.get("tension", 20) + random.randint(15, 30))
        arc["current"] = f"After {old_name}'s fall, {new_name} leads — priorities shift."
        inst["arc"] = arc

        rumors.append({
            "source_event_id": f"succession_{inst['id']}",
            "text": f"At {inst.get('name', 'the institution')}, {new_name} now holds authority.",
            "interpretation": random.choice(["worrying", "hushed", "scandalous"]),
            "spread": random.randint(25, 55),
        })
        log_event("institution_event", new_id, "leadership_change",
                  location=inst.get("area"), effects=[inst.get("type")], tick=tick)
        changed = True

    if changed:
        save(INST_FILE, institutions)
        save(RUMOR_FILE, rumors[-200:])
    return changed
