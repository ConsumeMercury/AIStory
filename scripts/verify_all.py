"""
Full offline verification — no Gemini API. Run: python scripts/verify_all.py
"""

import importlib
import os
import pkgutil
import sys
import traceback
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from storage import load, save


def _import_all_packages():
    errors = []
    for pkg_name in ("generation", "simulation"):
        pkg = importlib.import_module(pkg_name)
        pkg_path = pkg.__path__
        for mod in pkgutil.walk_packages(pkg_path, prefix=pkg.__name__ + "."):
            try:
                importlib.import_module(mod.name)
            except Exception as e:
                errors.append(f"{mod.name}: {e}")
    return errors


def _require_world_files():
    required = [
        "world/world_state.json",
        "world/areas.json",
        "world/locations.json",
        "world/factions.json",
        "world/institutions.json",
        "characters/npcs.json",
        "player/player.json",
    ]
    missing = [p for p in required if not os.path.exists(os.path.join(ROOT, p))]
    return missing


def test_imports():
    errors = _import_all_packages()
    assert not errors, "Import failures:\n" + "\n".join(errors)


def test_world_patch():
    from simulation.world_patch import ensure_world_extensions
    ensure_world_extensions()
    player = load("player/player.json", {})
    npcs = load("characters/npcs.json", {})
    areas = load("world/areas.json", {})
    institutions = load("world/institutions.json", {})
    assert player, "player.json missing or empty"
    assert npcs, "npcs.json missing or empty"
    assert areas, "areas.json missing or empty"
    alive = [n for n in npcs.values() if n.get("status") == "alive"]
    assert alive, "no alive NPCs"
    if any(a.get("type") == "district" for a in areas.values()):
        assert any(n.get("schedule") for n in alive), "schedules not patched"
    assert any(n.get("secrets") for n in alive), "secrets not patched"
    assert any(n.get("personal_objective") for n in alive), "objectives not patched"
    if institutions:
        assert any(i.get("politics") for i in institutions.values()), "politics not patched"


def test_sim_tick():
    from simulation.simulation_runner import _run_tick, get_current_tick
    before = get_current_tick()
    _run_tick()
    after = get_current_tick()
    assert after == before + 1, f"tick did not advance: {before} -> {after}"


def test_npc_choose_action():
    from simulation.npc_actions import choose_action
    npcs = load("characters/npcs.json", {})
    world = load("world/world_state.json", {})
    areas = load("world/areas.json", {})
    institutions = load("world/institutions.json", {})
    alive = [n for n in npcs.values() if n.get("status") == "alive"][:5]
    for npc in alive:
        act = choose_action(
            npc, areas=areas, institutions=institutions, npc_id=npc["id"],
            weather=world.get("weather", "Clear"),
        )
        assert act in (
            "trade", "fight", "hunt", "help", "socialise", "hide",
            "plan", "study", "craft", "travel",
        ), f"invalid action {act!r} for {npc['id']}"


def test_meta_commands():
    from simulation.player_commands import try_meta_command
    cmds = ["status", "skills", "map", "where", "goals", "bonds", "factions", "case", "help"]
    for c in cmds:
        out = try_meta_command(c)
        assert out is not None, f"meta command {c!r} returned None"


def test_investigation_flow():
    from simulation.investigation_cases import ensure_case, advance_case, format_case_status
    player = load("player/player.json", {})
    npcs = load("characters/npcs.json", {})
    areas = load("world/areas.json", {})
    area_id = player.get("area") or next(iter(areas))
    case = ensure_case(player, area_id, npcs, areas)[0]
    if case:
        note = advance_case(player, "investigate", {"skill_check": {"success": True, "margin": 2}}, npcs)
        assert isinstance(note, str)
        status = format_case_status(player, npcs)
        assert status


def test_story_loop_offline():
    from simulation.story_loop import process_player_action
    from simulation.turn_trace import get_last_turn
    with patch("simulation.story_loop.get_narrator") as mock_get:
        mock_get.return_value.generate_scene.return_value = "[scene ok]"
        for action in ("look around", "status", "wait for an hour"):
            result = process_player_action(action)
            assert result and isinstance(result, str), f"bad result for {action!r}: {result!r}"
    trace = get_last_turn()
    assert trace.get("kind"), trace


def test_starting_placement():
    import random
    from game.starting_placement import pick_start_area, pick_start_city, seed_starting_pipeline

    cities = {"alpha": {"name": "Alpha"}, "beta": {"name": "Beta"}}
    city_hits = {pick_start_city(cities, rng=random.Random(i)) for i in range(30)}
    assert len(city_hits) >= 2

    areas = {
        f"test:{suffix}": {
            "city": "test",
            "type": "district",
            "name": suffix.replace("_", " ").title(),
            "storyline": {
                "title": f"Plot in {suffix}",
                "hook": "Something is wrong.",
                "stages": ["a", "b", "c", "d"],
                "current": "a",
                "tension": 20,
            },
        }
        for suffix in ("docks", "market", "temple_row", "the_warrens", "high_quarter")
    }
    wanderer_starts = {
        pick_start_area(areas, "test", "wanderer", rng=random.Random(i))
        for i in range(40)
    }
    assert len(wanderer_starts) >= 3
    assert not all(a.endswith(":docks") for a in wanderer_starts)

    thief_starts = [
        pick_start_area(areas, "test", "thief", rng=random.Random(i))
        for i in range(20)
    ]
    warren_count = sum(1 for a in thief_starts if a.endswith(":the_warrens"))
    assert warren_count >= 5

    player = {"background": "scholar", "motivation": "seek truth", "goals": [], "story_flags": {}}
    npcs = {
        f"npc{i}": {"id": f"npc{i}", "status": "alive", "area": "test:market", "name": f"Npc {i}"}
        for i in range(4)
    }
    pipe = seed_starting_pipeline(player, "test:market", areas, npcs)
    assert pipe["title"]
    assert player.get("starting_pipeline")
    assert player["goals"][0]["id"] == "local_opening"


def test_storyline_catalog():
    from generation.district_storylines import DISTRICT_STORYLINE_POOLS
    from generation.institution_arcs import INSTITUTION_ARC_POOLS

    for district, pool in DISTRICT_STORYLINE_POOLS.items():
        assert len(pool) >= 7, f"{district} should have at least 7 pipelines"
        for entry in pool:
            assert entry.get("title") and entry.get("hooks") and entry.get("stages")
            assert len(entry["hooks"]) >= 3
            assert len(entry["stages"]) >= 5
            assert entry.get("theme")

    for itype, pool in INSTITUTION_ARC_POOLS.items():
        assert len(pool) >= 7, f"{itype} should have at least 7 arcs"
        for entry in pool:
            assert entry.get("title") and entry.get("hook") and entry.get("stages")
            assert len(entry["stages"]) >= 5
            assert entry.get("theme")


def test_llm_content_validators():
    from generation.llm_content import (
        ai_worldgen_enabled,
        validate_storyline_spec,
    )

    assert ai_worldgen_enabled() is False
    ok, cleaned, _ = validate_storyline_spec({
        "title": "Test Arc",
        "theme": "intrigue",
        "hooks": ["A merchant whispers about fixed scales."],
        "stages": ["rumour", "accusation", "bribe", "witness", "reckoning"],
    })
    assert ok and cleaned["title"] == "Test Arc"


def test_bootstrap_import():
    import src.main as main_mod
    assert hasattr(main_mod, "bootstrap_world")
    assert hasattr(main_mod, "game_loop")


def test_generation_report_offline():
    import scripts.generation_report as rep
    from scripts.generation_checks import FULL_SCENARIOS, backup_saves, restore_saves

    backups = backup_saves()
    sim_was = rep._pause_background_sim()
    mock_scene = (
        "You stand at the docks. Rain on the pilings. She watches you, "
        "a scholar in grey wool. (offline mock scene)"
    )
    try:
        with patch("simulation.story_loop.get_narrator") as mock_get:
            mock_get.return_value.generate_scene.return_value = mock_scene
            results = []
            for name, actions in list(FULL_SCENARIOS.items())[:3]:
                results.append(rep.run_scenario(name, actions, live=False))
        mech = sum(len(r["mech_issues"]) for r in results)
        api = sum(len(r.get("api_issues", [])) for r in results)
        assert api == 0, f"api errors in offline report: {api}"
        assert mech == 0, f"mech issues in offline report: {mech}"
    finally:
        restore_saves(backups)
        rep._resume_background_sim(sim_was)


def test_simulation_audit():
    import scripts.simulation_audit as audit
    from simulation import simulation_runner
    simulation_runner.stop()
    try:
        for name, fn in [
            ("explore_anchor", audit.audit_explore_anchor),
            ("attack_her", audit.audit_attack_her),
            ("find_sword_inventory", audit.audit_find_sword_inventory),
            ("confession_witness", audit.audit_confession_witness),
            ("find_person_role", audit.audit_find_person_role),
            ("non_fatal_focal", audit.audit_non_fatal_no_ghost_speaker),
            ("talk_priest_overrides_focus", audit.audit_talk_priest_overrides_focus),
            ("withdraw_clears_focus", audit.audit_withdraw_clears_focus),
            ("focal_id_integrity", audit.audit_focal_id_integrity),
            ("travel_failed_empty_cast", audit.audit_travel_failed_empty_cast),
        ]:
            fn()
    finally:
        simulation_runner.start()


def test_smoke_test():
    import scripts.smoke_test as smoke
    smoke.main()


def main():
    missing = _require_world_files()
    if missing:
        print("Building test world (AISTORY_AUTO_CHAR=1)...")
        os.environ["AISTORY_AUTO_CHAR"] = "1"
        from src.main import bootstrap_world
        bootstrap_world()
        missing = _require_world_files()
        if missing:
            raise RuntimeError(f"bootstrap failed; still missing: {missing}")

    tests = [
        ("imports", test_imports),
        ("bootstrap_import", test_bootstrap_import),
        ("world_patch", test_world_patch),
        ("sim_tick", test_sim_tick),
        ("npc_choose_action", test_npc_choose_action),
        ("meta_commands", test_meta_commands),
        ("starting_placement", test_starting_placement),
        ("storyline_catalog", test_storyline_catalog),
        ("llm_content_validators", test_llm_content_validators),
        ("investigation_flow", test_investigation_flow),
        ("story_loop_offline", test_story_loop_offline),
        ("generation_report_offline", test_generation_report_offline),
        ("simulation_audit", test_simulation_audit),
        ("smoke_test", test_smoke_test),
    ]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print(f"OK    {name}")
        except Exception:
            failed.append(name)
            print(f"FAIL  {name}")
            traceback.print_exc()
    if failed:
        print(f"\n{len(failed)} check(s) failed: {', '.join(failed)}")
        sys.exit(1)
    print(f"\nAll {len(tests)} verification checks passed.")


if __name__ == "__main__":
    main()
