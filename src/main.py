import os
import sys
import random

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.load_env import load_env

load_env()

from generation.world_generator import generate_world, save_world
from generation.location_generator import generate_locations, save_locations
from generation.faction_generator import generate_factions, save_factions
from generation.npc_generator import generate_population
from generation.area_generator import build_areas
from generation.monster_generator import spawn_for_area
from generation.stats_generator import generate_stats
from generation.family_generator import build_families
from generation.institution_generator import build_institutions
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
from storage import load, save


from game.setup import (
    BACKGROUNDS,
    ensure_world_data,
    build_player,
    save_new_player,
    has_player,
    world_data_ready,
    _path as setup_path,
)


WORLD_REQUIRED = (
    "world/world_state.json",
    "world/factions.json",
    "world/locations.json",
    "world/areas.json",
    "world/institutions.json",
    "characters/npcs.json",
    "characters/monsters.json",
    "characters/relationships.json",
    "player/player.json",
)


def _world_is_complete():
    return world_data_ready() and has_player()


def _clear_world_state():
    from game.setup import _clear_world_state as clear_all
    clear_all()


def path(*parts):
    return os.path.join(BASE_DIR, *parts)


def _skills_from_background(flat_skills):
    from game.setup import _skills_from_background as conv
    return conv(flat_skills)


def create_character(location_keys, city_display_name=None, auto=False):
    if auto or os.environ.get("AISTORY_AUTO_CHAR"):
        name = "The Wanderer"
        age = 30
        background_key = "soldier"
        appearance = "unremarkable in feature, the kind of face a crowd forgets"
        motivation = "The road brought you here."
    else:
        print("\n" + "=" * 50)
        print("  WHO ARE YOU?")
        print("=" * 50 + "\n")

        name = input("  Name: ").strip()
        if not name:
            name = "The Wanderer"

        age = 30
        raw_age = input("  Age (16-70, Enter for 30): ").strip()
        if raw_age.isdigit():
            age = max(16, min(70, int(raw_age)))

        print("\n  Background — what life prepared you for:\n")
        bg_keys = list(BACKGROUNDS.keys())
        for i, key in enumerate(bg_keys, 1):
            bg = BACKGROUNDS[key]
            print(f"  [{i}] {key.upper()}")
            print(f"      {bg['description']}\n")

        while True:
            choice = input(f"  Choose (1-{len(bg_keys)}): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(bg_keys):
                background_key = bg_keys[int(choice) - 1]
                break
            print("  Enter a number from the list.")

        background = BACKGROUNDS[background_key]

        print("\n  Appearance — what people notice first:")
        appearance = input("  > ").strip()
        if not appearance:
            appearance = "unremarkable in feature, the kind of face a crowd forgets"

        print("\n  What you carry or wear on your person (optional):")
        attire = input("  > ").strip()
        if attire:
            appearance = f"{appearance}; {attire}"

        print("\n  Why are you here — one sentence (optional):")
        motivation = input("  > ").strip()
        if not motivation:
            motivation = "You are not sure yet. The road brought you."

    player = build_player(name, age, background_key, appearance, motivation)
    locations = load("world/locations.json", {})
    cities = locations.get("cities", {})
    city_key = player.get("location")
    city_name = cities.get(city_key, {}).get("name") or (city_key or "unknown").replace("_", " ").title()
    if not (auto or os.environ.get("AISTORY_AUTO_CHAR")):
        background = BACKGROUNDS[background_key]
        print("\n" + "-" * 50)
        print(f"  {name}, {age}. {background['description']}")
        print(f"\n  You look like: {player['appearance']}")
        print(f"  You are here because: {motivation}")
        if player["goals"]:
            print(f"\n  What drives you: {player['goals'][0]['text']}")
        print(f"\n  You arrive in {city_name} with little more than that.")
        print("  (Type 'help' anytime — status, goals, map, factions, routines, bonds.)")
        print("-" * 50 + "\n")

    return player


def bootstrap_world():
    ensure_world_data()
    if has_player():
        return

    locations = load("world/locations.json", {})
    player = create_character(
        list(locations.get("cities", {}).keys()),
        auto=bool(os.environ.get("AISTORY_AUTO_CHAR")),
    )
    save_new_player(player)


def game_loop():
    from storage import load
    from simulation.story_loop import process_player_action, generate_opening_scene
    from simulation import simulation_runner
    from simulation.gemini_client import api_key
    from simulation.world_patch import ensure_world_extensions

    player_path = path("player", "player.json")
    if not os.path.exists(player_path):
        print("\nNo character found.\n")
        return

    if not api_key():
        print(
            "\nSet GEMINI_API_KEY (or GOOGLE_API_KEY) before playing.\n"
            "Get a key: https://aistudio.google.com/apikey\n"
        )
        return

    ensure_world_extensions()

    simulation_runner.start()

    opening = generate_opening_scene()
    if opening:
        print()
        print(opening)

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
                from simulation.player_commands import try_meta_command
                from simulation.action_hints import build_action_hints
                if try_meta_command(action) is None:
                    player = load("player/player.json", {})
                    last_kind = (player.get("journal") or [{}])[-1].get("kind")
                    hint = build_action_hints(player, last_kind=last_kind)
                    if hint:
                        print(hint)
            except Exception as e:
                print(f"\n[{e}]")

    finally:
        simulation_runner.stop()


if __name__ == "__main__":
    bootstrap_world()
    game_loop()