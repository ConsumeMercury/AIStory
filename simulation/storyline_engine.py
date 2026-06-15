"""
Advances institution story arcs slowly so the world has unfolding plots,
not just ambient noise. Each tick an arc has a small chance to gain tension;
when tension crosses a threshold the arc steps to its next stage, logs an
event (which the memory engine turns into members' memories) and seeds a
rumour. Arcs that finish quietly reset with a new plot after a lull.
"""

import random
from storage import load, save
from simulation.event_logger import log_event

INST_FILE = "world/institutions.json"


def advance_storylines(tick=None):
    institutions = load(INST_FILE, {})
    if not isinstance(institutions, dict) or not institutions:
        return
    rumors = load("rumors/rumors.json", [])
    if not isinstance(rumors, list):
        rumors = []

    changed = False
    for inst in institutions.values():
        arc = inst.get("arc")
        if not arc:
            continue

        # tension creeps up; rarely, it relaxes
        arc["tension"] = max(0, min(100, arc["tension"] + random.randint(-1, 4)))

        if arc["tension"] >= 60 and random.random() < 0.35:
            arc["stage"] += 1
            arc["tension"] = random.randint(15, 35)
            if arc["stage"] < len(arc["stages"]):
                arc["current"] = arc["stages"][arc["stage"]]
                # members remember the beat; leader is the named actor
                actor = inst.get("leader") or next(iter(inst.get("members", {})), None)
                if actor:
                    log_event("institution_event", actor, "storyline_beat",
                              location=inst.get("city"),
                              effects=[inst["type"], arc["current"][:40]], tick=tick)
                rumors.append({
                    "source_event_id": f"arc_{inst['id']}_{arc['stage']}",
                    "text": f"At {inst['name']}, {arc['current']}.",
                    "interpretation": random.choice(["worrying", "scandalous", "hushed"]),
                    "spread": random.randint(20, 80),
                })
                changed = True
            else:
                # arc resolved — pick a fresh plot after the dust settles
                from generation.institution_generator import INSTITUTION_TYPES
                spec = INSTITUTION_TYPES.get(inst["type"])
                if spec:
                    arc["stages"] = random.choice(spec["arcs"])
                    arc["stage"] = 0
                    arc["current"] = arc["stages"][0]
                    arc["tension"] = random.randint(5, 20)
                changed = True

    if changed:
        save("rumors/rumors.json", rumors[-200:])
    save(INST_FILE, institutions)


def arc_for_city(city):
    """The most tense arc in a city — what the narrator should be aware of."""
    institutions = load(INST_FILE, {})
    here = [i for i in institutions.values() if i.get("city") == city]
    if not here:
        return None
    inst = max(here, key=lambda i: i.get("arc", {}).get("tension", 0))
    arc = inst.get("arc", {})
    return {"institution": inst["name"], "type": inst["type"],
            "current": arc.get("current"), "tension": arc.get("tension")}
