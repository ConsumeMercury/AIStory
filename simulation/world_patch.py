"""
Patch older saves with storylines, goals, schedules, secrets, drama, and history.
"""

from storage import load, save
from simulation.player_goals import build_player_goals, attach_goal_profile
from generation.area_storylines import attach_area_storylines
from generation.area_generator import build_areas, ensure_story_districts, annotate_city_gates
from generation.institution_generator import plan_city_institutions
from simulation.npc_schedule import attach_schedules, apply_schedules_to_npcs
from generation.npc_secrets import attach_secrets
from generation.personal_objectives import attach_personal_objectives
from simulation.npc_drama import seed_drama
from simulation.institution_politics import attach_politics
from generation.world_history import generate_world_history


def ensure_world_extensions():
    """Run at game start so existing saves gain new systems without full reset."""
    areas = load("world/areas.json", {})
    institutions = load("world/institutions.json", {})
    npcs = load("characters/npcs.json", {})
    player = load("player/player.json", {})
    world = load("world/world_state.json", {})
    factions = load("world/factions.json", {})
    locations = load("world/locations.json", {})

    changed = False
    inst_changed = False
    loc_changed = False

    cities = locations.get("cities", {})
    if not areas and cities:
        institution_plan = plan_city_institutions(cities)
        areas = build_areas(cities, institution_plan=institution_plan)
        annotate_city_gates(cities, areas)
        ensure_story_districts(areas, cities, institution_plan=institution_plan, institutions=institutions)
        changed = True
        loc_changed = True

    if areas and cities:
        before_ids = set(areas.keys())
        needs_travel_patch = any(
            a.get("type") == "wilderness" and not a.get("inter_city_hours")
            for a in areas.values()
        )
        ensure_story_districts(areas, cities, institutions=institutions)
        annotate_city_gates(cities, areas)
        if set(areas.keys()) != before_ids or needs_travel_patch:
            changed = True
            loc_changed = True

    if areas and not any(a.get("storyline") for a in areas.values() if a.get("type") == "district"):
        attach_area_storylines(areas, institutions, npcs)
        changed = True

    if npcs and not any(n.get("schedule") for n in npcs.values() if n.get("status") == "alive"):
        attach_schedules(npcs, areas)
        changed = True

    if npcs and not any(n.get("secrets") for n in npcs.values() if n.get("status") == "alive"):
        attach_secrets(npcs, factions, institutions)
        changed = True

    if npcs:
        from simulation.secret_activity import enrich_all_secrets
        enrich_all_secrets(npcs)

    if npcs and not any(n.get("personal_objective") for n in npcs.values() if n.get("status") == "alive"):
        attach_personal_objectives(npcs)
        changed = True

    if institutions and not any(i.get("politics") for i in institutions.values()):
        attach_politics(institutions, npcs)
        inst_changed = True
        changed = True

    if world and not world.get("history"):
        world["history"] = generate_world_history(locations.get("cities", {}))
        save("world/world_state.json", world)

    if npcs and not load("world/world_state.json", {}).get("drama_seeded"):
        seed_drama(npcs)
        world = load("world/world_state.json", {})
        world["drama_seeded"] = True
        save("world/world_state.json", world)

    if player and not player.get("goals"):
        player["goals"] = build_player_goals(
            player.get("motivation", ""),
            player.get("background", "wanderer"),
        )
        player.setdefault("goal_trackers", {})
        save("player/player.json", player)

    if player:
        from simulation.faction_reputation import ensure_faction_standing
        from simulation.institution_membership import ensure_institution_standing
        ensure_faction_standing(player, factions)
        ensure_institution_standing(player, institutions)
        if not player.get("goal_themes"):
            attach_goal_profile(player)
        if not player.get("bestiary"):
            from simulation.hunting_engine import ensure_bestiary
            ensure_bestiary(player)
        from simulation.item_engine import ensure_equipment
        ensure_equipment(player)
        from simulation.area_discovery import migrate_discovered_areas
        migrate_discovered_areas(player)
        if areas and player.get("area") and player["area"] not in areas:
            from game.starting_placement import ensure_start_area
            city = player.get("location")
            if city:
                player["area"] = ensure_start_area(
                    areas, city, player.get("background", "wanderer"),
                )
        save("player/player.json", player)

    if not load("world/world_state.json", {}).get("bounty_board"):
        from simulation.hunting_engine import refresh_bounty_board
        refresh_bounty_board()

    if npcs:
        apply_schedules_to_npcs(npcs, world, areas)
        save("characters/npcs.json", npcs)

    if changed:
        save("world/areas.json", areas)
        save("characters/npcs.json", npcs)
    if loc_changed:
        save("world/locations.json", locations)
    if inst_changed:
        save("world/institutions.json", institutions)
