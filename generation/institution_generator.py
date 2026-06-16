"""
Institutions: the structures that give a world its story pipelines.

Each is placed in a city district, recruits AGE-APPROPRIATE members from
the local population (students are young, masters old), has a leader, and
carries a slow-moving STORY ARC with stages. The storyline_engine advances
these arcs over time; the narrator surfaces the arc of wherever the player is.
"""

import random
from generation.id_generator import generate_id
from generation.area_storylines import preferred_areas_for_institution
from generation.district_population import retag_institution_member
from generation.institution_arcs import INSTITUTION_ARC_POOLS

# role -> (min_age, max_age, share-of-members)
INSTITUTION_TYPES = {
    "academy": {
        "name_parts": (["The", "Royal", "Grey", "Hollow"], ["Academy", "Lyceum", "College"], ["of Letters", "of the Arcane", "of War", "of Physick"]),
        "roles": {"student": (14, 22, 0.7), "tutor": (28, 55, 0.2), "headmaster": (45, 70, 0.1)},
    },
    "guild": {
        "name_parts": (["The", "Iron", "Gilded", "Silent"], ["Guild", "Company", "Lodge"], ["of Smiths", "of Traders", "of Masons", "of Shadows"]),
        "roles": {"apprentice": (15, 24, 0.5), "journeyman": (24, 40, 0.35), "master": (40, 68, 0.15)},
    },
    "temple": {
        "name_parts": (["The", "High", "Pale", "Sunken"], ["Temple", "Sanctum", "Chapel"], ["of the Dawn", "of the Drowned God", "of Ash", "of the Quiet Saint"]),
        "roles": {"acolyte": (14, 25, 0.55), "cleric": (25, 55, 0.35), "high_priest": (45, 70, 0.1)},
    },
    "garrison": {
        "name_parts": (["The", "Black", "Old", "Border"], ["Garrison", "Watch", "Company"], ["of the Gate", "of the Wall", "of the Marches"]),
        "roles": {"recruit": (16, 24, 0.55), "soldier": (24, 45, 0.35), "captain": (35, 60, 0.1)},
    },
    "hunters_lodge": {
        "name_parts": (["The", "Grey", "Broken", "Wild"], ["Hunters'", "Trackers'", "Stalkers'"], ["Lodge", "Hall", "Company"]),
        "roles": {"tracker": (18, 32, 0.45), "hunter": (22, 45, 0.4), "warden": (38, 62, 0.15)},
    },
}


def _pick_institution_arc(itype):
    pool = INSTITUTION_ARC_POOLS.get(itype) or INSTITUTION_ARC_POOLS["guild"]
    return random.choice(pool)


def _name(parts):
    a, b, c = parts
    return f"{random.choice(a)} {random.choice(b)} {random.choice(c)}"


def plan_city_institutions(cities):
    """Plan institution types per city before areas are built (story district requirements)."""
    plan = {}
    for city in cities:
        n_inst = random.randint(2, min(3, len(INSTITUTION_TYPES)))
        types = random.sample(list(INSTITUTION_TYPES), k=min(n_inst, len(INSTITUTION_TYPES)))
        plan[city] = types
    return plan


def build_institutions(npcs, areas, cities, institution_plan=None):
    """Create 1-2 institutions per city, recruiting local age-appropriate NPCs."""
    institutions = {}
    institution_plan = institution_plan or plan_city_institutions(cities)
    by_city = {}
    for nid, n in npcs.items():
        if n.get("status") == "alive":
            by_city.setdefault(n.get("location"), []).append(nid)

    for city in cities:
        city_areas = [a for a in areas if areas[a].get("city") == city]
        if not city_areas:
            continue
        types = list(institution_plan.get(city, []))
        if not types:
            types = random.sample(
                list(INSTITUTION_TYPES),
                k=random.randint(2, min(3, len(INSTITUTION_TYPES))),
            )

        local = list(by_city.get(city, []))
        random.shuffle(local)

        for itype in types:
            spec = INSTITUTION_TYPES[itype]
            arc_spec = _pick_institution_arc(itype)
            stages = list(arc_spec["stages"])
            inst_id = generate_id("inst")
            candidates = preferred_areas_for_institution(itype, city_areas)
            area = random.choice(candidates)
            members = {}
            leader = None
            used_leaders = {i.get("leader") for i in institutions.values() if i.get("leader")}

            local_in_area = [i for i in local if npcs[i].get("area") == area]
            pool = local_in_area if len(local_in_area) >= 3 else local

            for role, (lo, hi, share) in spec["roles"].items():
                want = max(1, int(8 * share))
                eligible = [
                    i for i in pool
                    if lo <= npcs[i]["age"] <= hi and i not in members
                ]
                random.shuffle(eligible)
                for i in eligible[:want]:
                    members[i] = role
                    npcs[i]["institution"] = {"id": inst_id, "type": itype, "role": role}
                    npcs[i]["area"] = area
                    retag_institution_member(npcs[i])
                    if role in ("headmaster", "master", "high_priest", "captain", "warden"):
                        if i not in used_leaders:
                            leader = i
                            used_leaders.add(i)

            if not members:
                continue

            institutions[inst_id] = {
                "id": inst_id,
                "type": itype,
                "name": _name(spec["name_parts"]),
                "city": city,
                "area": area,
                "leader": leader,
                "members": members,
                "arc": {
                    "spec": arc_spec,
                    "title": arc_spec["title"],
                    "theme": arc_spec.get("theme"),
                    "stages": stages,
                    "stage": 0,
                    "tension": random.randint(10, 35),
                    "current": stages[0],
                },
            }

    return institutions
