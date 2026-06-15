import os
import sys
import json
import random

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Without this, running `python src/main.py` fails with
# ModuleNotFoundError: No module named 'generation' — because only the
# src/ directory is on sys.path, not the project root that holds the
# generation/ and simulation/ packages.
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from generation.world_generator import generate_world, save_world
from generation.location_generator import generate_locations, save_locations
from generation.faction_generator import generate_factions, save_factions
from generation.npc_generator import generate_population
from generation.area_generator import build_areas
from generation.monster_generator import spawn_for_area
from generation.stats_generator import generate_stats
from generation.family_generator import build_families
from generation.institution_generator import build_institutions
from simulation.progression_engine import level_for_xp


def path(*parts):
    return os.path.join(BASE_DIR, *parts)


def _skills_from_background(flat_skills):
    """Convert the background's flat skill scores into earned-XP skill nodes."""
    # map legacy player skill names onto the shared skill vocabulary
    rename = {"combat": "swordsmanship", "stealth": "lockpicking"}
    skills = {}
    for name, val in flat_skills.items():
        key = rename.get(name, name)
        xp = int(val) * 25
        skills[key] = {"xp": xp, "level": level_for_xp(xp)}
    return skills


BACKGROUNDS = {
    "soldier": {
        "description": (
            "You have spent years in service — enough to know that most wars "
            "are decided before the first blow lands. Your body carries the record "
            "of that education in ways no surgeon can fully explain."
        ),
        "skills": {"combat": 60, "persuasion": 20, "stealth": 15, "survival": 40, "arcana": 5},
        "wealth": 30,
        "traits": {"reputation": 40, "notoriety": 10},
    },
    "merchant": {
        "description": (
            "Coin and contracts are your native tongue. You have sat across negotiating "
            "tables from men who wanted to ruin you, and you are still here. "
            "You know the value of everything — and the price of silence."
        ),
        "skills": {"combat": 15, "persuasion": 65, "stealth": 25, "survival": 20, "arcana": 10},
        "wealth": 80,
        "traits": {"reputation": 55, "notoriety": 5},
    },
    "scholar": {
        "description": (
            "Years in dusty libraries left you soft in body but sharp in mind. "
            "You see patterns where others see noise, and you have learned that "
            "knowing the right question is worth more than a sword."
        ),
        "skills": {"combat": 10, "persuasion": 40, "stealth": 20, "survival": 15, "arcana": 70},
        "wealth": 40,
        "traits": {"reputation": 45, "notoriety": 0},
    },
    "thief": {
        "description": (
            "The city's underside raised you. You learned early that the law "
            "is a story told by people with walls and locks, and that most doors "
            "will open if you understand what they are afraid of."
        ),
        "skills": {"combat": 35, "persuasion": 30, "stealth": 75, "survival": 35, "arcana": 15},
        "wealth": 20,
        "traits": {"reputation": 25, "notoriety": 30},
    },
    "wanderer": {
        "description": (
            "No roots, no allegiances. The road has been your only constant, "
            "and you have learned to read weather, people, and trouble "
            "with the same practiced eye."
        ),
        "skills": {"combat": 30, "persuasion": 35, "stealth": 40, "survival": 60, "arcana": 20},
        "wealth": 15,
        "traits": {"reputation": 30, "notoriety": 5},
    },
}


def create_character(location_keys):
    print("\n" + "=" * 50)
    print("  CHARACTER CREATION")
    print("=" * 50 + "\n")

    name = input("  Your name: ").strip()
    if not name:
        name = "The Wanderer"

    # age — matters for how the world treats you (academies, guilds, garrisons)
    age = 30
    raw_age = input("  Your age (16-70, Enter for 30): ").strip()
    if raw_age.isdigit():
        age = max(16, min(70, int(raw_age)))

    print("\n  Choose your background:\n")
    bg_keys = list(BACKGROUNDS.keys())
    for i, key in enumerate(bg_keys, 1):
        bg = BACKGROUNDS[key]
        print(f"  [{i}] {key.upper()}")
        print(f"      {bg['description']}")
        print()

    while True:
        choice = input(f"  Enter a number (1-{len(bg_keys)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(bg_keys):
            background_key = bg_keys[int(choice) - 1]
            break
        print("  Invalid choice, try again.")

    background = BACKGROUNDS[background_key]

    print("\n  Describe your appearance")
    print("  (what others notice first — or press Enter to leave it unwritten):")
    appearance = input("  > ").strip()
    if not appearance:
        appearance = "unremarkable in feature, the kind of face a crowd forgets"

    starting_location = location_keys[0] if location_keys else "unknown"
    city_name = starting_location.replace("_", " ").title()

    # combat stats for the player, derived from real age + background
    stats = generate_stats(age=age, role=background_key, traits={
        "courage": background["traits"].get("reputation", 40),
        "aggression": 50, "discipline": 50,
    })

    player = {
        "name": name,
        "age": age,
        "background": background_key,
        "appearance": appearance,
        "location": starting_location,
        "area": None,                      # set in bootstrap once areas exist
        "stats": stats,
        "level": 1,
        "xp": 0,
        "health": stats["health"],         # legacy mirror
        "wealth": background["wealth"],
        "inventory": [],
        "skills": _skills_from_background(background["skills"]),
        "traits": background["traits"],
        "story_flags": {},
        "journal": [],
        "met_npcs": [],
        "known_npcs": {},                  # per-NPC: {name_known, seen_before, ...}
    }

    print(f"\n  {background['description']}")
    print(f"\n  You find yourself in {city_name}.\n")
    print("=" * 50)

    return player


def bootstrap_world():
    os.makedirs(path("world"), exist_ok=True)
    os.makedirs(path("characters"), exist_ok=True)
    os.makedirs(path("events"), exist_ok=True)
    os.makedirs(path("rumors"), exist_ok=True)
    os.makedirs(path("saves"), exist_ok=True)
    os.makedirs(path("player"), exist_ok=True)

    if os.path.exists(path("world", "world_state.json")):
        return

    world = generate_world()
    save_world(world)

    locations = generate_locations()
    save_locations(locations)

    factions = generate_factions()
    save_factions(factions)

    location_keys = list(locations["cities"].keys())

    npcs = generate_population(count=50, locations=location_keys)

    # ---- families: cluster NPCs into households, seed kin bonds ----
    npcs, relationships_seed = build_families(npcs, {})

    # ---- area graph + assign NPCs to specific areas (districts) ----
    areas = build_areas(locations["cities"])
    # map each NPC into a district of the city it lives in
    for npc in npcs.values():
        city = npc.get("location")
        city_areas = [a for a in areas if areas[a].get("city") == city]
        if city_areas:
            chosen = random.choice(city_areas)
            npc["area"] = chosen

    # ---- institutions: academies/guilds/temples/garrisons with arcs ----
    institutions = build_institutions(npcs, areas, locations["cities"])

    # ---- initial monsters in wilderness areas ----
    monsters = {}
    for aid, area in areas.items():
        if area.get("type") == "wilderness":
            for mon in spawn_for_area(area.get("area_type", "wilderness"),
                                      count=random.randint(1, 3)):
                mon["location"] = aid
                mon["area"] = aid
                monsters[mon["id"]] = mon

    with open(path("characters", "npcs.json"), "w") as f:
        json.dump(npcs, f, indent=2)
    with open(path("world", "areas.json"), "w") as f:
        json.dump(areas, f, indent=2)
    with open(path("world", "institutions.json"), "w") as f:
        json.dump(institutions, f, indent=2)
    with open(path("characters", "monsters.json"), "w") as f:
        json.dump(monsters, f, indent=2)
    with open(path("characters", "relationships.json"), "w") as f:
        json.dump(relationships_seed, f, indent=2)
    with open(path("characters", "npc_memories.json"), "w") as f:
        json.dump({}, f, indent=2)
    with open(path("characters", "_mem_state.json"), "w") as f:
        json.dump({"processed": []}, f, indent=2)
    with open(path("characters", "memories.json"), "w") as f:
        json.dump({}, f, indent=2)
    with open(path("events", "event_log.json"), "w") as f:
        json.dump([], f, indent=2)
    with open(path("rumors", "rumors.json"), "w") as f:
        json.dump([], f, indent=2)

    player = create_character(location_keys)

    # drop the player into a district of their starting city
    start_city = player.get("location")
    start_areas = [a for a in areas if areas[a].get("city") == start_city]
    if start_areas:
        player["area"] = sorted(start_areas)[0]

    with open(path("player", "player.json"), "w") as f:
        json.dump(player, f, indent=2)


def game_loop():
    from simulation.story_loop import process_player_action
    from simulation import simulation_runner

    player_path = path("player", "player.json")
    if not os.path.exists(player_path):
        print("\nNo character found.\n")
        return

    simulation_runner.start()

    try:
        while True:
            print()
            action = input("> ").strip()

            if not action:
                continue

            if action.lower() in ["quit", "exit"]:
                print()
                break

            try:
                scene = process_player_action(action)
                print()
                print(scene)
            except Exception as e:
                print(f"\n[{e}]")

    finally:
        simulation_runner.stop()


if __name__ == "__main__":
    bootstrap_world()
    game_loop()