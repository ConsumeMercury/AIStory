"""
Per-district storylines — institution plots or local drama hooks.
"""

import random

from generation.district_storylines import DISTRICT_STORYLINE_POOLS
from generation.institution_arcs import INSTITUTION_HOOKS
from generation.ai_worldgen import maybe_enrich_storyline_spec

# Which institution types fit which district suffix
INSTITUTION_DISTRICT = {
    "academy": ["high_quarter", "market"],
    "guild": ["market", "docks"],
    "temple": ["temple_row"],
    "garrison": ["high_quarter", "docks"],
    "hunters_lodge": ["market", "docks", "the_warrens"],
}

# Backward-compatible default (first variant per district).
DISTRICT_STORYLINES = {
    key: pool[0] for key, pool in DISTRICT_STORYLINE_POOLS.items()
}


def pick_district_storyline(dkey):
    pool = DISTRICT_STORYLINE_POOLS.get(dkey) or DISTRICT_STORYLINE_POOLS["market"]
    return random.choice(pool)


def _district_key(area_id):
    return area_id.split(":")[-1] if area_id else ""


def districts_required_for_institution_types(inst_types):
    """District suffixes needed for a set of institution types."""
    required = set()
    for itype in inst_types or []:
        required.update(INSTITUTION_DISTRICT.get(itype, ["market"]))
    required.add("market")
    return required


def preferred_areas_for_institution(itype, city_areas):
    prefs = INSTITUTION_DISTRICT.get(itype, [])
    matched = [a for a in city_areas if _district_key(a) in prefs]
    return matched or list(city_areas)


def _institution_hook(inst, arc_spec):
    if isinstance(arc_spec, dict):
        if arc_spec.get("hook"):
            return arc_spec["hook"]
        hooks = arc_spec.get("hooks")
        if hooks:
            return random.choice(hooks)
    return INSTITUTION_HOOKS.get(inst.get("type"), "")


def attach_area_storylines(areas, institutions, npcs):
    """Write storyline block onto each district area."""
    inst_by_area = {}
    for inst in institutions.values():
        aid = inst.get("area")
        if aid:
            inst_by_area.setdefault(aid, []).append(inst)

    for aid, area in areas.items():
        if area.get("type") != "district":
            continue

        dkey = _district_key(aid)
        local_insts = inst_by_area.get(aid, [])

        if local_insts:
            inst = max(local_insts, key=lambda i: i.get("arc", {}).get("tension", 0))
            arc = inst.get("arc", {})
            arc_spec = arc.get("spec") or {}
            leader = inst.get("leader")
            members = list((inst.get("members") or {}).keys())
            key_npcs = []
            if leader:
                key_npcs.append(leader)
            for mid in members:
                if mid not in key_npcs and len(key_npcs) < 3:
                    key_npcs.append(mid)

            stages = list(arc.get("stages") or [])
            area["storyline"] = {
                "source": "institution",
                "institution_id": inst["id"],
                "title": arc.get("title") or inst["name"],
                "type": inst["type"],
                "theme": arc.get("theme") or arc_spec.get("theme"),
                "hook": _institution_hook(inst, arc_spec),
                "stages": stages,
                "stage": arc.get("stage", 0),
                "tension": arc.get("tension", 20),
                "current": arc.get("current", stages[0] if stages else ""),
                "key_npc_ids": key_npcs,
            }
            _mark_key_npcs(npcs, key_npcs, inst)
        else:
            spec = pick_district_storyline(dkey)
            spec = maybe_enrich_storyline_spec(
                spec,
                district_name=dkey,
                city_name=area.get("city", ""),
                area_name=area.get("name", dkey),
            )
            hook = random.choice(spec["hooks"])
            stages = list(spec["stages"])
            area["storyline"] = {
                "source": "district",
                "institution_id": None,
                "title": spec["title"],
                "type": dkey,
                "theme": spec.get("theme"),
                "hook": hook,
                "stages": stages,
                "stage": 0,
                "tension": random.randint(12, 35),
                "current": stages[0],
                "key_npc_ids": [],
            }

    return areas


def _mark_key_npcs(npcs, key_ids, inst):
    for nid in key_ids:
        n = npcs.get(nid)
        if not n:
            continue
        n["key_npc"] = True
        n["story_role"] = inst.get("members", {}).get(nid, "member")
        if nid == inst.get("leader"):
            n["story_role"] = "leader"


def sync_area_storyline_from_institution(area, institution):
    """Keep district storyline in step when institution arc advances."""
    if not area.get("storyline") or area["storyline"].get("source") != "institution":
        return
    if area["storyline"].get("institution_id") != institution.get("id"):
        return
    arc = institution.get("arc", {})
    area["storyline"]["stage"] = arc.get("stage", 0)
    area["storyline"]["tension"] = arc.get("tension", 0)
    area["storyline"]["current"] = arc.get("current", "")
    area["storyline"]["stages"] = list(arc.get("stages", []))
    if arc.get("title"):
        area["storyline"]["title"] = arc["title"]
    if arc.get("theme"):
        area["storyline"]["theme"] = arc["theme"]
