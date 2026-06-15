"""
Institutions: the structures that give a world its story pipelines.

Each is placed in a city district, recruits AGE-APPROPRIATE members from
the local population (students are young, masters old), has a leader, and
carries a slow-moving STORY ARC with stages. The storyline_engine advances
these arcs over time; the narrator surfaces the arc of wherever the player is.
"""

import random
from generation.id_generator import generate_id

# role -> (min_age, max_age, share-of-members)
INSTITUTION_TYPES = {
    "academy": {
        "name_parts": (["The", "Royal", "Grey", "Hollow"], ["Academy", "Lyceum", "College"], ["of Letters", "of the Arcane", "of War", "of Physick"]),
        "roles": {"student": (14, 22, 0.7), "tutor": (28, 55, 0.2), "headmaster": (45, 70, 0.1)},
        "arcs": [
            ["whispers of cheating on the coming examinations", "a tutor accuses a favoured student", "the matter reaches the headmaster", "someone is expelled — or covered for"],
            ["a student has gone missing", "their belongings are found, they are not", "a tutor knows more than they say", "the truth surfaces, ugly"],
            ["a forbidden text is circulating among students", "a tutor confiscates a copy", "students meet in secret to read on", "the headmaster must choose: burn it or learn from it"],
        ],
    },
    "guild": {
        "name_parts": (["The", "Iron", "Gilded", "Silent"], ["Guild", "Company", "Lodge"], ["of Smiths", "of Traders", "of Masons", "of Shadows"]),
        "roles": {"apprentice": (15, 24, 0.5), "journeyman": (24, 40, 0.35), "master": (40, 68, 0.15)},
        "arcs": [
            ["a lucrative contract is up for bidding", "a rival guild undercuts the price", "an apprentice is caught spying", "the contract is won or lost in blood"],
            ["coin has gone missing from the guild coffers", "suspicion falls on a journeyman", "the master demands a reckoning", "a thief is named — rightly or not"],
            ["a feud with a rival guild simmers", "a brawl spills into the street", "the city watch takes an interest", "the feud ends in a pact or a body"],
        ],
    },
    "temple": {
        "name_parts": (["The", "High", "Pale", "Sunken"], ["Temple", "Sanctum", "Chapel"], ["of the Dawn", "of the Drowned God", "of Ash", "of the Quiet Saint"]),
        "roles": {"acolyte": (14, 25, 0.55), "cleric": (25, 55, 0.35), "high_priest": (45, 70, 0.1)},
        "arcs": [
            ["a heresy is spreading among the acolytes", "a cleric is implicated", "the high priest convenes a judgement", "the temple purges itself, or splits"],
            ["a relic has been promised to the temple", "it does not arrive as expected", "an acolyte claims to have seen a sign", "faith is rewarded or made a fool of"],
        ],
    },
    "garrison": {
        "name_parts": (["The", "Black", "Old", "Border"], ["Garrison", "Watch", "Company"], ["of the Gate", "of the Wall", "of the Marches"]),
        "roles": {"recruit": (16, 24, 0.55), "soldier": (24, 45, 0.35), "captain": (35, 60, 0.1)},
        "arcs": [
            ["recruits are deserting in the night", "a soldier is suspected of helping them", "the captain tightens the leash", "an example is made"],
            ["scouts report movement beyond the wall", "the garrison is undermanned", "a recruit raises a false alarm", "something is coming, or already here"],
            ["the captain is taking bribes to look away", "a soldier of conscience gathers proof", "loyalties fracture", "the truth costs someone everything"],
        ],
    },
}


def _name(parts):
    a, b, c = parts
    return f"{random.choice(a)} {random.choice(b)} {random.choice(c)}"


def build_institutions(npcs, areas, cities):
    """Create 1-2 institutions per city, recruiting local age-appropriate NPCs."""
    institutions = {}
    by_city = {}
    for nid, n in npcs.items():
        if n.get("status") == "alive":
            by_city.setdefault(n.get("location"), []).append(nid)

    for city in cities:
        city_areas = [a for a in areas if areas[a].get("city") == city]
        if not city_areas:
            continue
        n_inst = random.randint(1, 2)
        types = random.sample(list(INSTITUTION_TYPES), k=min(n_inst, len(INSTITUTION_TYPES)))
        local = list(by_city.get(city, []))
        random.shuffle(local)

        for itype in types:
            spec = INSTITUTION_TYPES[itype]
            inst_id = generate_id("inst")
            area = random.choice(city_areas)
            members = {}
            leader = None

            # recruit by role, respecting age windows
            for role, (lo, hi, share) in spec["roles"].items():
                want = max(1, int(8 * share))
                eligible = [i for i in local
                            if lo <= npcs[i]["age"] <= hi and i not in members]
                random.shuffle(eligible)
                for i in eligible[:want]:
                    members[i] = role
                    npcs[i]["institution"] = {"id": inst_id, "type": itype, "role": role}
                    if role in ("headmaster", "master", "high_priest", "captain"):
                        leader = i

            if not members:
                continue

            arc = random.choice(spec["arcs"])
            institutions[inst_id] = {
                "id": inst_id, "type": itype, "name": _name(spec["name_parts"]),
                "city": city, "area": area, "leader": leader,
                "members": members,
                "arc": {"stages": arc, "stage": 0, "tension": random.randint(10, 35),
                        "current": arc[0]},
            }

    return institutions
