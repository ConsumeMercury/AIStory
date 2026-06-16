"""
A bestiary. Monsters share the combat stat shape with NPCs/player so the
combat engine treats everyone uniformly, but they have no 20-trait
personality — just a temperament that nudges whether they ambush, stalk,
or flee.
"""

import random
from generation.id_generator import generate_id

BESTIARY = {
    "wolf":        {"hp": (28, 40),  "atk": (8, 14),  "def": (2, 5),  "spd": (14, 18), "temperament": "pack", "habitat": ["wilderness", "forest"]},
    "bandit":      {"hp": (45, 65),  "atk": (10, 16), "def": (6, 10), "spd": (10, 14), "temperament": "greedy", "habitat": ["road", "wilderness"]},
    "bog_lurker":  {"hp": (55, 80),  "atk": (12, 20), "def": (8, 12), "spd": (6, 9),   "temperament": "ambush", "habitat": ["marsh", "ruins"]},
    "ghoul":       {"hp": (40, 60),  "atk": (11, 18), "def": (4, 8),  "spd": (9, 13),  "temperament": "relentless", "habitat": ["ruins", "crypt"]},
    "dire_boar":   {"hp": (70, 100), "atk": (14, 22), "def": (7, 11), "spd": (8, 12),  "temperament": "territorial", "habitat": ["forest", "wilderness"]},
    "wraith":      {"hp": (35, 55),  "atk": (16, 26), "def": (3, 6),  "spd": (12, 16), "temperament": "haunting", "habitat": ["crypt", "ruins"]},
    "bone_stalker": {"hp": (50, 72), "atk": (13, 19), "def": (5, 9),  "spd": (11, 15), "temperament": "ambush", "habitat": ["crypt", "ruins", "marsh"]},
    "marsh_adder":  {"hp": (22, 34),  "atk": (9, 15),  "def": (2, 4),  "spd": (15, 19), "temperament": "ambush", "habitat": ["marsh", "wilderness"]},
}

SPECIES_DISPLAY = {
    "wolf": "grey wolf",
    "bandit": "road bandit",
    "bog_lurker": "bog lurker",
    "ghoul": "ghoul",
    "dire_boar": "dire boar",
    "wraith": "wraith",
    "bone_stalker": "bone stalker",
    "marsh_adder": "marsh adder",
}

SPECIES_BOUNTY = {
    "wolf": 8,
    "bandit": 15,
    "bog_lurker": 22,
    "ghoul": 18,
    "dire_boar": 28,
    "wraith": 35,
    "bone_stalker": 30,
    "marsh_adder": 12,
}


def roll_loot(species):
    """Backward-compatible wrapper — prefer simulation.item_engine.roll_monster_loot."""
    from simulation.item_engine import roll_monster_loot
    return roll_monster_loot(species)


_DESCRIPTORS = {
    "wolf": "a lean grey shape, ribs showing, eyes catching the light",
    "bandit": "a hooded figure with a notched blade and nothing to lose",
    "bog_lurker": "something wide and patient under the surface scum",
    "ghoul": "a grey, hairless thing that used to be a person",
    "dire_boar": "a tusked bulk the size of a cart, breath steaming",
    "wraith": "a cold smear of a shape that the eye keeps sliding off",
    "bone_stalker": "a long-limbed thing of bone and sinew that hunts where the dead gather",
    "marsh_adder": "a striped coil half-submerged, still as a root until it isn't",
}


def generate_monster(species, area=None):
    spec = BESTIARY[species]
    hp = random.randint(*spec["hp"])
    return {
        "id": generate_id("mon"),
        "species": species,
        "descriptor": _DESCRIPTORS[species],
        "temperament": spec["temperament"],
        "location": area,
        "stats": {
            "health": hp, "max_health": hp,
            "attack": random.randint(*spec["atk"]),
            "defense": random.randint(*spec["def"]),
            "speed": random.randint(*spec["spd"]),
            "stamina": 30, "max_stamina": 30,
        },
        "status": "alive",
    }


def spawn_for_area(area_type, count=None):
    candidates = [s for s, d in BESTIARY.items() if area_type in d["habitat"]]
    if not candidates:
        return []
    if count is None:
        count = random.randint(0, 2)
    return [generate_monster(random.choice(candidates), area_type) for _ in range(count)]
