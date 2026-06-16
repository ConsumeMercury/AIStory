import random
import json
import os

from storage import save as storage_save

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FACTION_TYPES = ["guild", "empire", "tribe", "cult", "syndicate", "order"]

FACTION_NAME_PARTS = {
    "guild": (
        ["Ironveil", "Goldhand", "Duskmantle", "Silvermark", "Ashwright"],
        ["Trading Co.", "Merchants", "Craftsmen", "Exchange", "Brotherhood"]
    ),
    "empire": (
        ["Valdris", "Korrath", "Aelmar", "Thalos", "Vireth"],
        ["Dominion", "Empire", "Sovereignty", "Throne", "Imperium"]
    ),
    "tribe": (
        ["Stormclaw", "Bloodmane", "Frostpeak", "Ashveil", "Ironhide"],
        ["Clan", "Horde", "Warband", "Kin", "Pack"]
    ),
    "cult": (
        ["Hollow", "Ashen", "Voidborn", "Pale", "Sunken"],
        ["Circle", "Covenant", "Sect", "Vigil", "Embrace"]
    ),
    "syndicate": (
        ["Shadow", "Redhand", "Copperchain", "Nightfall", "Ironweb"],
        ["Syndicate", "Consortium", "Ring", "Cartel", "Compact"]
    ),
    "order": (
        ["Silver", "Ember", "Dawnward", "Iron", "Ashen"],
        ["Order", "Knights", "Vigil", "Wardens", "Sentinels"]
    ),
}


def generate_faction(name_id):
    ftype = random.choice(FACTION_TYPES)
    prefixes, suffixes = FACTION_NAME_PARTS[ftype]

    name = f"{random.choice(prefixes)} {random.choice(suffixes)}"

    # FIX: enforce numeric stability (prevents later float drift issues)
    return {
        "id": name_id,
        "name": name,
        "type": ftype,
        "power": float(random.randint(20, 100)),
        "wealth": float(random.randint(20, 100)),
        "influence": float(random.randint(20, 100)),
        "controlled_locations": [],
        "relations": {},
        "goals": [f"expand {ftype} influence"]
    }


def generate_factions(count=4):
    return {
        f"faction_{i}": generate_faction(f"faction_{i}")
        for i in range(count)
    }


def save_factions(data):
    storage_save("world/factions.json", data)


if __name__ == "__main__":
    factions = generate_factions()
    save_factions(factions)
    print("Factions generated:", [f["name"] for f in factions.values()])