"""
World bootstrap and player character creation — shared by CLI and web UI.
"""

import os
import random

from storage import load, save
from generation.world_generator import generate_world, save_world
from generation.location_generator import generate_locations, save_locations
from generation.faction_generator import generate_factions, save_factions
from generation.npc_generator import generate_population
from generation.area_generator import build_areas, annotate_city_gates
from generation.monster_generator import spawn_for_area
from generation.stats_generator import generate_stats
from generation.family_generator import build_families
from generation.institution_generator import build_institutions, plan_city_institutions
from generation.population_tuning import cap_area_density, tune_for_player
from generation.district_population import assign_npcs_to_districts
from generation.area_storylines import attach_area_storylines
from generation.world_history import generate_world_history
from simulation.npc_schedule import attach_schedules
from generation.npc_secrets import attach_secrets
from generation.personal_objectives import attach_personal_objectives
from simulation.institution_politics import attach_politics
from simulation.npc_drama import seed_drama
from simulation.player_goals import build_player_goals, attach_goal_profile
from simulation.progression_engine import level_for_xp
from game.starting_placement import pick_start_city, pick_start_area, seed_starting_pipeline

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORLD_DATA_FILES = (
    "world/world_state.json",
    "world/factions.json",
    "world/locations.json",
    "world/areas.json",
    "world/institutions.json",
    "characters/npcs.json",
    "characters/monsters.json",
    "characters/relationships.json",
)

PLAYER_FILE = "player/player.json"


def _path(*parts):
    return os.path.join(BASE_DIR, *parts)


def _skills_from_background(flat_skills):
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


def list_backgrounds():
    return [
        {"id": key, "label": key.replace("_", " ").title(), "description": val["description"]}
        for key, val in BACKGROUNDS.items()
    ]


def has_player():
    return bool(load(PLAYER_FILE, {}))


def world_data_ready():
    return all(os.path.exists(_path(*rel.split("/"))) for rel in WORLD_DATA_FILES)


def _clear_world_state():
    for rel in WORLD_DATA_FILES + (
        PLAYER_FILE,
        "characters/memories.json",
        "characters/npc_memories.json",
        "characters/_mem_state.json",
        "events/event_log.json",
        "rumors/rumors.json",
    ):
        p = _path(*rel.split("/"))
        if os.path.exists(p):
            os.remove(p)


def _ensure_dirs():
    for sub in ("world", "characters", "events", "rumors", "saves", "player"):
        os.makedirs(_path(sub), exist_ok=True)


def ensure_world_data():
    """Generate world JSON if missing. Does not create the player."""
    _ensure_dirs()
    if world_data_ready():
        return

    if os.path.exists(_path("world", "world_state.json")):
        _clear_world_state()

    world = generate_world()
    save_world(world)

    locations = generate_locations()
    save_locations(locations)

    factions = generate_factions()
    save_factions(factions)

    world = load("world/world_state.json", {})
    world["history"] = generate_world_history(locations.get("cities", {}))
    world["drama_seeded"] = True
    save("world/world_state.json", world)

    location_keys = list(locations["cities"].keys())
    npcs = generate_population(count=50, locations=location_keys)
    npcs, relationships_seed = build_families(npcs, {})

    institution_plan = plan_city_institutions(locations["cities"])
    areas = build_areas(locations["cities"], institution_plan=institution_plan)
    annotate_city_gates(locations["cities"], areas)
    save_locations(locations)

    assign_npcs_to_districts(npcs, areas)
    cap_area_density(npcs, areas)

    institutions = build_institutions(
        npcs, areas, locations["cities"], institution_plan=institution_plan,
    )
    attach_schedules(npcs, areas)
    attach_secrets(npcs, factions, institutions)
    attach_personal_objectives(npcs)

    from generation.ai_worldgen import enrich_world_narrative
    enrich_world_narrative(world, locations, areas, institutions, npcs, factions)
    save("world/world_state.json", world)

    attach_area_storylines(areas, institutions, npcs)
    institutions = attach_politics(institutions, npcs)
    seed_drama(npcs)

    monsters = {}
    for aid, area in areas.items():
        if area.get("type") == "wilderness":
            for mon in spawn_for_area(area.get("area_type", "wilderness"), count=random.randint(1, 3)):
                mon["location"] = aid
                mon["area"] = aid
                monsters[mon["id"]] = mon

    save("characters/npcs.json", npcs)
    save("world/areas.json", areas)
    save("world/institutions.json", institutions)

    from simulation.faction_reputation import institution_faction
    for inst in institutions.values():
        if not inst.get("faction_id"):
            inst["faction_id"] = institution_faction(inst, factions)
    save("world/institutions.json", institutions)

    from simulation.hunting_engine import refresh_bounty_board
    refresh_bounty_board()
    save("characters/monsters.json", monsters)
    save("characters/relationships.json", relationships_seed)
    save("characters/npc_memories.json", {})
    save("characters/_mem_state.json", {"processed": []})
    save("characters/memories.json", {})
    save("events/event_log.json", [])
    save("rumors/rumors.json", [])


def get_starting_info():
    locations = load("world/locations.json", {})
    cities = locations.get("cities", {})
    if not cities:
        return {"city_key": None, "city_name": "Unknown", "cities": []}
    city_list = [
        {
            "key": key,
            "name": data.get("name", key.replace("_", " ").title()),
        }
        for key, data in cities.items()
    ]
    preview = random.choice(city_list)
    return {
        "city_key": preview["key"],
        "city_name": preview["name"],
        "cities": city_list,
    }


def build_player(name, age, background_key, appearance, motivation, attire=None):
    if background_key not in BACKGROUNDS:
        raise ValueError(f"Unknown background: {background_key}")

    background = BACKGROUNDS[background_key]
    locations = load("world/locations.json", {})
    cities = locations.get("cities", {})
    starting_location = pick_start_city(cities) or "unknown"

    if attire:
        appearance = f"{appearance}; {attire}" if appearance else attire

    stats = generate_stats(age=age, role=background_key, traits={
        "courage": background["traits"].get("reputation", 40),
        "aggression": 50,
        "discipline": 50,
    })

    player = {
        "name": name or "The Wanderer",
        "age": age,
        "background": background_key,
        "appearance": appearance or "unremarkable in feature, the kind of face a crowd forgets",
        "motivation": motivation or "You are not sure yet. The road brought you.",
        "location": starting_location,
        "area": None,
        "stats": stats,
        "level": 1,
        "xp": 0,
        "health": stats["health"],
        "injuries": [],
        "wealth": background["wealth"],
        "inventory": [],
        "equipment": {"weapon": None, "armor": None, "trinket": None},
        "skills": _skills_from_background(background["skills"]),
        "traits": background["traits"],
        "story_flags": {},
        "journal": [],
        "identity": {"alias": "a stranger", "revealed_to": [], "revealed_areas": []},
        "scene_focus": None,
        "met_npcs": [],
        "known_npcs": {},
        "discovered_areas": {},
        "goals": [],
        "goal_trackers": {},
    }
    player["goals"] = build_player_goals(player["motivation"], background_key)
    attach_goal_profile(player)
    return player


def save_new_player(player):
    """Place player in world and persist."""
    areas = load("world/areas.json", {})
    npcs = load("characters/npcs.json", {})
    tune_for_player(npcs, player, start_city=player.get("location"))
    start_city = player.get("location")
    start_area = pick_start_area(areas, start_city, player.get("background", "wanderer"))
    if start_area:
        player["area"] = start_area
        seed_starting_pipeline(player, start_area, areas, npcs)
        sl = areas.get(start_area, {}).get("storyline") or {}
        for nid in sl.get("key_npc_ids") or []:
            npc = npcs.get(nid)
            if npc and npc.get("area") != start_area:
                npc["area"] = start_area
    save("characters/npcs.json", npcs)
    save(PLAYER_FILE, player)
    return player


def create_player_from_form(data):
    """Web/API character creation."""
    if has_player():
        raise RuntimeError("A character already exists.")

    ensure_world_data()

    name = (data.get("name") or "").strip() or "The Wanderer"
    raw_age = data.get("age", 30)
    try:
        age = max(16, min(70, int(raw_age)))
    except (TypeError, ValueError):
        age = 30

    background_key = (data.get("background") or "wanderer").strip().lower()
    appearance = (data.get("appearance") or "").strip()
    motivation = (data.get("motivation") or "").strip()
    attire = (data.get("attire") or "").strip()

    player = build_player(name, age, background_key, appearance, motivation, attire=attire or None)
    save_new_player(player)
    return player
