"""
Storyline advancement — institution arcs + per-district plots.
"""

import logging
import random
from storage import load, save
from simulation.event_logger import log_event

log = logging.getLogger(__name__)

INST_FILE = "world/institutions.json"
AREAS_FILE = "world/areas.json"


def advance_storylines(tick=None):
    institutions = load(INST_FILE, {})
    areas = load(AREAS_FILE, {})
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

        arc["tension"] = max(0, min(100, arc["tension"] + random.randint(-1, 4)))

        if arc["tension"] >= 60 and random.random() < 0.35:
            arc["stage"] += 1
            arc["tension"] = random.randint(15, 35)
            if arc["stage"] < len(arc["stages"]):
                arc["current"] = arc["stages"][arc["stage"]]
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
                from generation.institution_generator import _pick_institution_arc
                arc_spec = _pick_institution_arc(inst["type"])
                stages = list(arc_spec["stages"])
                arc["spec"] = arc_spec
                arc["title"] = arc_spec["title"]
                arc["theme"] = arc_spec.get("theme")
                arc["stages"] = stages
                arc["stage"] = 0
                arc["current"] = stages[0]
                arc["tension"] = random.randint(5, 20)
                changed = True

        aid = inst.get("area")
        if aid and aid in areas:
            from generation.area_storylines import sync_area_storyline_from_institution
            sync_area_storyline_from_institution(areas[aid], inst)

    # standalone district arcs (no institution)
    for aid, area in areas.items():
        sl = area.get("storyline")
        if not sl or sl.get("source") != "district":
            continue
        sl["tension"] = max(0, min(100, sl.get("tension", 20) + random.randint(0, 3)))
        if sl["tension"] >= 55 and random.random() < 0.25:
            stages = sl.get("stages") or []
            if sl.get("stage", 0) + 1 < len(stages):
                sl["stage"] = sl.get("stage", 0) + 1
                sl["current"] = stages[sl["stage"]]
                sl["tension"] = random.randint(12, 30)
                rumors.append({
                    "source_event_id": f"district_{aid}_{sl['stage']}",
                    "text": f"In {area.get('name', 'the district')}: {sl['current']}.",
                    "interpretation": random.choice(["worrying", "hushed", "suspicious"]),
                    "spread": random.randint(10, 50),
                    "area_id": aid,
                    "city": area.get("city"),
                })
                changed = True
                try:
                    from storage import load as _load, save as _save
                    from simulation.story_manager import sync_starting_pipeline_from_area
                    player = _load("player/player.json", {})
                    if sync_starting_pipeline_from_area(player, aid, areas):
                        _save("player/player.json", player)
                except Exception:
                    log.exception("starting pipeline sync failed for area %s", aid)
        save("rumors/rumors.json", rumors[-200:])
    save(INST_FILE, institutions)
    save(AREAS_FILE, areas)


def arc_for_area(area_id):
    """Storyline for the player's current district."""
    if not area_id:
        return None
    areas = load(AREAS_FILE, {})
    area = areas.get(area_id, {})
    sl = area.get("storyline")
    if not sl:
        return None
    return {
        "title": sl.get("title", area.get("name", "")),
        "type": sl.get("type", ""),
        "current": sl.get("current", sl.get("hook", "")),
        "hook": sl.get("hook", ""),
        "tension": sl.get("tension", 0),
        "key_npcs": sl.get("key_npc_ids", []),
        "source": sl.get("source", "district"),
    }


def arc_for_city(city):
    """Fallback: highest-tension institution arc in the city."""
    institutions = load(INST_FILE, {})
    here = [i for i in institutions.values() if i.get("city") == city]
    if not here:
        return None
    inst = max(here, key=lambda i: i.get("arc", {}).get("tension", 0))
    arc = inst.get("arc", {})
    return {
        "institution": inst["name"],
        "title": inst["name"],
        "type": inst["type"],
        "current": arc.get("current"),
        "tension": arc.get("tension"),
    }
