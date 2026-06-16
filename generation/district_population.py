"""
Assign NPCs to districts with roles, ages, and attire that fit the place.
"""

import random

from generation.descriptor_generator import generate_physique, lock_pronouns
from generation.skill_generator import generate_npc_skills, ROLE_SKILLS

DISTRICT_ROLE_WEIGHTS = {
    "market": {
        "merchant": 28, "guard": 12, "innkeeper": 14, "scribe": 10,
        "blacksmith": 8, "thief": 6, "herbalist": 10, "apothecary": 8,
    },
    "docks": {
        "sailor": 32, "merchant": 18, "thief": 12, "guard": 10,
        "mercenary": 8, "scribe": 5, "innkeeper": 8,
    },
    "temple_row": {
        "priest": 35, "scholar": 15, "scribe": 12, "herbalist": 10,
        "merchant": 8, "guard": 8, "innkeeper": 6,
    },
    "the_warrens": {
        "thief": 25, "mercenary": 12, "herbalist": 12, "scribe": 8,
        "innkeeper": 10, "merchant": 8, "guard": 5, "farmer": 8,
    },
    "high_quarter": {
        "guard": 22, "scholar": 18, "merchant": 15, "soldier": 12,
        "mercenary": 10, "scribe": 12, "priest": 8,
    },
}

# institution internal roles -> npc occupation for dress/age
INSTITUTION_NPC_ROLE = {
    "academy": {
        "student": ("scholar", 16, 22),
        "tutor": ("scholar", 28, 55),
        "headmaster": ("scholar", 45, 70),
    },
    "guild": {
        "apprentice": ("blacksmith", 15, 24),
        "journeyman": ("merchant", 24, 40),
        "master": ("merchant", 40, 68),
    },
    "temple": {
        "acolyte": ("priest", 14, 25),
        "cleric": ("priest", 25, 55),
        "high_priest": ("priest", 45, 70),
    },
    "garrison": {
        "recruit": ("soldier", 16, 24),
        "soldier": ("soldier", 24, 45),
        "captain": ("soldier", 35, 60),
    },
    "hunters_lodge": {
        "tracker": ("hunter", 18, 32),
        "hunter": ("hunter", 22, 45),
        "warden": ("hunter", 38, 62),
    },
}


def _district_key(area_id):
    return area_id.split(":")[-1] if area_id else "market"


def _pick_role_for_district(district_key):
    weights = DISTRICT_ROLE_WEIGHTS.get(district_key, DISTRICT_ROLE_WEIGHTS["market"])
    roles = list(weights.keys())
    w = [weights[r] for r in roles]
    return random.choices(roles, weights=w, k=1)[0]


def _retag_npc_for_role(npc, role, district_key=None):
    """Adjust role, age band, physique attire, and skills for district fit."""
    from generation.npc_generator import _ROLE_AGE

    lo, hi = _ROLE_AGE.get(role, (18, 55))
    if npc.get("institution"):
        itype = npc["institution"].get("type")
        irole = npc["institution"].get("role")
        mapping = INSTITUTION_NPC_ROLE.get(itype, {}).get(irole)
        if mapping:
            role, lo, hi = mapping

    npc["role"] = role
    npc["occupation"] = role
    npc["age"] = max(lo, min(hi, npc.get("age", random.randint(lo, hi))))
    if npc["age"] < lo or npc["age"] > hi:
        npc["age"] = random.randint(lo, hi)

    npc["physique"] = generate_physique(npc["age"], role=role, gender=npc.get("gender"))
    npc["pronouns"] = lock_pronouns(npc.get("gender", "male"))
    if district_key == "docks":
        npc["physique"]["scent"] = random.choice([
            "tar and salt", "wet wool and fish", "rope and brine",
        ])
    elif district_key == "temple_row":
        npc["physique"]["attire"] = random.choice([
            npc["physique"].get("attire", ""),
            "plain temple robes", "a novice's cord at the waist",
        ])
    elif district_key == "the_warrens":
        npc["physique"]["attire"] = random.choice([
            "patched clothes too thin for the season",
            "a hood worn up out of habit", "layers that hide what's underneath",
        ])

    npc["skills"] = generate_npc_skills(role)
    npc["district"] = district_key


def assign_npcs_to_districts(npcs, areas):
    """
    Place NPCs into city districts with appropriate roles.
    Runs before institution recruitment; institution members get re-tagged later.
    """
    by_city = {}
    for nid, n in npcs.items():
        if n.get("status") != "alive":
            continue
        by_city.setdefault(n.get("location"), []).append(nid)

    area_ids = list(areas.keys())
    assigned = set()

    for city, nids in by_city.items():
        city_areas = [a for a in area_ids if areas[a].get("city") == city and areas[a].get("type") == "district"]
        if not city_areas:
            continue
        random.shuffle(nids)
        per_area = max(2, len(nids) // max(1, len(city_areas)))

        for aid in city_areas:
            dkey = _district_key(aid)
            batch = [i for i in nids if i not in assigned][:per_area]
            for nid in batch:
                npc = npcs[nid]
                role = _pick_role_for_district(dkey)
                npc["area"] = aid
                _retag_npc_for_role(npc, role, dkey)
                assigned.add(nid)

        for nid in nids:
            if nid in assigned:
                continue
            aid = random.choice(city_areas)
            dkey = _district_key(aid)
            npcs[nid]["area"] = aid
            _retag_npc_for_role(npcs[nid], _pick_role_for_district(dkey), dkey)
            assigned.add(nid)

    return npcs


def retag_institution_member(npc):
    """After institution assignment, sync dress/age to institution role."""
    inst = npc.get("institution")
    if not inst:
        return
    itype = inst.get("type")
    irole = inst.get("role")
    mapping = INSTITUTION_NPC_ROLE.get(itype, {}).get(irole)
    if mapping:
        role, lo, hi = mapping
        npc["role"] = role
        npc["occupation"] = role
        npc["age"] = random.randint(lo, hi)
        npc["physique"] = generate_physique(npc["age"], role=role, gender=npc.get("gender"))
        npc["pronouns"] = lock_pronouns(npc.get("gender", "male"))
        npc["skills"] = generate_npc_skills(role)
        npc["story_role"] = irole
