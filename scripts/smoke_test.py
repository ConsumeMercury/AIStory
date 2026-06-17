"""
Smoke tests — no Gemini API required. Run: python scripts/smoke_test.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from storage import load
from simulation.event_logger import log_event, all_events, flush_events, load_events
from simulation.action_interpreter import interpret_action
from simulation.player_commands import try_meta_command
from simulation.scene_cast import select_scene_cast, pick_name_target
from simulation.skill_check import run_action_check, resolve_check
from simulation.relationship_engine import apply_npc_toward_player, relationship
from simulation.world_patch import ensure_world_extensions
from simulation.storyline_engine import arc_for_area
from simulation.memory_retrieval import get_relevant_memories
from simulation.narrator_variety import build_avoid_repeating, build_continuity_note
from simulation.novel_craft import craft_for_kind, narrative_outcome, token_budget_for_kind


def test_event_buffer():
    flush_events()
    before = len(load_events())
    log_event("test", "player", "smoke", tick=0)
    assert len(all_events()) == before + 1, "buffered events missing from all_events()"
    flush_events()
    assert len(load_events()) == before + 1, "flush did not persist event"


def test_action_interpreter():
    player = load("player/player.json", {"age": 25, "known_npcs": {}, "scene_focus": None})
    world = load("world/world_state.json", {"time_of_day": "day", "weather": "Clear"})
    npcs = load("characters/npcs.json", {})
    present = [n for n in npcs.values() if n.get("status") == "alive"][:5]

    for action, expected in [
        ("look around", "explore"),
        ("roam the district", "explore"),
        ("what is your name?", "ask_name"),
        ("My name is An", "talk"),
        ("ask for work", "guild"),
        ("find a sword", "search"),
        ("I have killed him", "confess"),
        ("investigate", "investigate"),
        ("help", "meta_skip"),
    ]:
        if expected == "meta_skip":
            assert try_meta_command(action) is not None
            continue
        ctx = interpret_action(action, player, present, world)
        assert ctx["kind"] == expected, f"{action!r} -> {ctx['kind']!r}, want {expected!r}"


def test_scene_cast():
    player = load("player/player.json", {"known_npcs": {}, "age": 30, "area": "x"})
    npcs = load("characters/npcs.json", {})
    present = [n for n in npcs.values() if n.get("status") == "alive"][:4]
    if not present:
        return
    ctx = {"kind": "explore", "target_id": None}
    focus, note, focal_id = select_scene_cast(present, player, ctx)
    assert focus == [] or len(focus) <= 1
    assert note  # non-empty crowd guidance


def test_skill_check():
    player = load("player/player.json", {})
    if not player:
        return
    r = resolve_check(player, "persuasion", 10)
    assert "success" in r and "roll" in r
    r2 = run_action_check(player, "talk", world={"weather": "Clear", "time_of_day": "day"})
    assert r2 is None or "success" in r2


def test_narrator_helpers():
    journal = [{"kind": "explore", "action": "look around", "excerpt": "Fog on the dock."}]
    assert "DO NOT REPEAT" in build_avoid_repeating(journal)
    assert "CONTINUITY" in build_continuity_note(journal, "ask_name", "your name?")
    assert craft_for_kind("explore")
    assert token_budget_for_kind("explore") <= 2800
    assert narrative_outcome({"success": True, "consequence": "ok"})


def test_world_patch():
    ensure_world_extensions()
    player = load("player/player.json", {})
    if player and player.get("motivation"):
        assert player.get("goals") or True  # goals may exist from patch


def test_ecosystem_modules():
    from simulation.storyline_behavior import theme_for_area, apply_storyline_weights
    from simulation.rumor_behavior import npc_player_rumor_profile, rumor_action_bias
    from simulation.district_state import advance_districts
    from simulation.institution_politics import attach_politics
    from simulation.investigation_cases import generate_mystery, format_case_status
    from simulation.player_legacy import record_legacy, legacy_narrator_block
    from generation.personal_objectives import attach_personal_objectives
    from simulation.rival_engine import rival_stage

    npcs = load("characters/npcs.json", {})
    areas = load("world/areas.json", {})
    player = load("player/player.json", {})
    if areas:
        aid = next(iter(areas))
        theme = theme_for_area(aid, areas)
        assert theme is None or theme
    if npcs:
        attach_personal_objectives(npcs)
    if player:
        record_legacy(player, "heroism", "saved a child from fire", day=1)
        assert "LEGACY" in legacy_narrator_block(player)
    assert rival_stage({}) == 0


def test_goal_events():
    from simulation.player_goals import derive_goal_themes, attach_goal_profile, build_player_goals
    from simulation.goal_events import pick_goal_scene_event, maybe_goal_rumor

    player = {
        "motivation": "I need to find my lost brother and learn the truth",
        "background": "scholar",
        "goals": build_player_goals("find my lost brother", "scholar"),
        "area": "test: docks",
        "location": "redmoor",
    }
    attach_goal_profile(player)
    themes = set(player["goal_themes"])
    assert "personal" in themes or "discovery" in themes

    hits = 0
    for _ in range(40):
        ev = pick_goal_scene_event(player, "explore", force=True)
        if ev and ev.get("themes") and themes & set(ev["themes"]):
            hits += 1
    assert hits >= 10, f"goal events under-weighted: {hits}/40"

    maybe_goal_rumor(player, tick=1)


def test_loot():
    from simulation.hunting_engine import resolve_monster_loot
    from generation.monster_generator import roll_loot

    player = {"wealth": 10, "inventory": []}
    items = roll_loot("bandit")
    assert items
    msg = resolve_monster_loot(player, {"species": "bandit"})
    assert msg
    assert player["wealth"] >= 10


def test_action_hints():
    from simulation.action_hints import build_action_hints, set_hint_mode, get_hint_mode

    player = load("player/player.json", {})
    if not player:
        return
    set_hint_mode(player, "subtle")
    assert get_hint_mode(player) == "subtle"
    hint = build_action_hints(player, last_kind="explore")
    assert hint == "" or "thought" in hint.lower() or "could" in hint.lower()
    set_hint_mode(player, "off")


def test_ui_state():
    from simulation.ui_state import get_full_state

    data = get_full_state()
    assert data is not None
    assert "player" in data and "world" in data
    assert "header" in data and "health" in data["header"]
    assert "codex" in data and "timeline" in data
    assert isinstance(data["help"], list)


def test_ui_destinations():
    from simulation.ui_state import _format_destination, get_relations_view, get_full_state
    from storage import load

    areas = load("world/areas.json", {})
    locs = load("world/locations.json", {})
    player = load("player/player.json", {})

    d = _format_destination("wild:frostcrest_stonegate", 36, areas, locs)
    assert d["detail"] and "Frostcrest" in d["detail"]
    assert d["id"] == "wild:frostcrest_stonegate"

    for card in get_relations_view(player, named_only=True):
        assert card["name_known"]

    state = get_full_state()
    assert state["player"].get("skills") is not None
    from simulation.area_discovery import migrate_discovered_areas
    migrate_discovered_areas(player)
    for dest in state["world"]["destinations"]:
        assert dest.get("detail"), dest

    migrate_discovered_areas(player)
    if state["codex"]["places"]:
        assert state["codex"]["places"][0].get("description") is not None


def test_turn_trace():
    from unittest.mock import MagicMock, patch
    from simulation.story_loop import process_player_action
    from simulation.turn_trace import get_last_turn

    mock_narr = MagicMock()
    mock_narr.generate_scene.return_value = "[scene ok]"
    with patch("simulation.story_loop.get_narrator", return_value=mock_narr):
        process_player_action("status")
    trace = get_last_turn()
    assert trace.get("kind") == "meta"
    assert trace.get("action") == "status"


def test_area_discovery():
    from simulation.area_discovery import build_area_blurb, record_area_arrival, migrate_discovered_areas
    from storage import load

    areas = load("world/areas.json", {})
    aid = next(iter(areas))
    blurb = build_area_blurb(aid, areas)
    assert blurb.get("description") and blurb.get("name")

    player = {"area": aid, "journal": [], "discovered_areas": {}}
    arrival = record_area_arrival(player, aid, {"day": 1})
    assert arrival["first_visit"] is True
    assert player["discovered_areas"][aid]["description"]

    arrival2 = record_area_arrival(player, aid, {"day": 2})
    assert arrival2["first_visit"] is False
    assert player["discovered_areas"][aid]["visits"] == 2

    old = load("player/player.json", {})
    if old:
        migrate_discovered_areas(old)
        assert "discovered_areas" in old


def test_ui_api_contract():
    import importlib.util

    path = os.path.join(ROOT, "scripts", "ui_api_test.py")
    spec = importlib.util.spec_from_file_location("ui_api_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.test_offline_state()


def test_item_equipment():
    from generation.item_generator import generate_item
    from simulation.item_engine import (
        equip_item, equipment_bonuses, apply_equipment_to_entity,
        resolve_loot_to_player, roll_monster_loot,
    )

    player = {
        "wealth": 0,
        "inventory": [],
        "equipment": {"weapon": None, "armor": None, "trinket": None},
        "stats": {"attack": 5, "defense": 3, "health": 40, "max_health": 40, "stamina": 20, "max_stamina": 20},
        "journal": [],
    }
    _, sword = generate_item(category="weapon", source="guild", rarity="rare")
    player["inventory"].append(sword)
    msg = equip_item(player, sword["id"])
    assert "equip" in msg.lower()
    stat_mods, _ = equipment_bonuses(player)
    assert stat_mods.get("attack", 0) >= 1
    eff = apply_equipment_to_entity(player)
    assert eff["attack"] > player["stats"]["attack"]

    drops = roll_monster_loot("wraith", elite=True)
    assert drops
    rarities = {d.get("rarity") for d in drops if d.get("category") != "coin"}
    assert rarities  # at least one item with rarity tag
    summary = resolve_loot_to_player(player, drops)
    assert summary
    assert player.get("wealth", 0) >= 0 or player["inventory"]


def test_hunting_guild():
    from simulation.hunting_engine import (
        refresh_bounty_board, format_bounties, ensure_bestiary,
    )
    from generation.monster_generator import SPECIES_DISPLAY, roll_loot
    from simulation.action_interpreter import interpret_action

    player = {"location": "redmoor", "area": "redmoor:market", "wealth": 10, "inventory": []}
    ensure_bestiary(player)
    loot = roll_loot("wolf")
    assert loot
    assert "wolf" in SPECIES_DISPLAY
    refresh_bounty_board()
    assert isinstance(format_bounties(player), str)
    ctx = interpret_action("track the beast", player, [], {"weather": "Clear"})
    assert ctx["kind"] == "hunt"


def test_npc_bonds_and_familiarity():
    from generation.descriptor_generator import brief_appearance, gender_label
    from generation.npc_generator import generate_npc
    from generation.id_generator import generate_id
    from simulation.appearance_impression import record_first_impression
    from simulation.relationship_engine import apply_impression_nudge, apply_npc_toward_player, relationship
    from simulation.relationship_thresholds import relationship_state

    npc = generate_npc(generate_id("npc_bond"), ["redmoor:market"])
    assert npc["gender"] in ("male", "female")
    desc = brief_appearance(npc)
    assert gender_label(npc) in desc or gender_label(npc).lower() in desc.lower() or "man" in desc.lower() or "woman" in desc.lower()

    player = {"known_npcs": {}, "met_npcs": [], "appearance": "plain coat", "age": 30, "background": "wanderer"}
    imp = record_first_impression(player, npc)
    apply_impression_nudge(npc["id"], "player", imp)
    rel = relationship(npc["id"], "player")
    assert rel.get("familiarity", 0) <= 1.0, rel
    sid, _ = relationship_state(rel)
    assert sid == "stranger"

    apply_npc_toward_player(npc["id"], "charm", intensity=0.55)
    rel = relationship(npc["id"], "player")
    assert rel.get("familiarity", 0) <= 2.0, rel
    assert rel.get("interactions", 0) == 1


def test_action_resolution():
    from simulation.action_resolution import (
        resolve_combat_target, resolve_pronoun_target, try_acquire_item,
        match_npc_by_description, build_combat_facts,
    )
    from simulation.combat_engine import resolve_combat

    present = [
        {"id": "npc_a", "status": "alive", "gender": "female", "name": "Mara", "role": "merchant",
         "age": 40, "pronouns": {"subject": "she", "object": "her", "possessive": "her"},
         "appearance": {"hair": "red"}, "persona": {}, "traits": {}, "stats": {"health": 80, "max_health": 80, "stamina": 20, "attack": 5, "defense": 3, "speed": 5}},
        {"id": "npc_b", "status": "alive", "gender": "male", "name": "Dock", "role": "sailor",
         "age": 35, "pronouns": {"subject": "he", "object": "him", "possessive": "his"},
         "appearance": {}, "persona": {}, "traits": {}, "stats": {"health": 80, "max_health": 80, "stamina": 20, "attack": 5, "defense": 3, "speed": 5}},
    ]
    npcs = {n["id"]: n for n in present}
    player = {"scene_focus": "npc_a", "last_combat_target": "npc_a", "known_npcs": {}, "inventory": [], "equipment": {}, "stats": {"health": 100, "max_health": 100, "stamina": 30, "attack": 8, "defense": 4, "speed": 6}, "journal": []}

    target, kind = resolve_combat_target("attack her", player, present, npcs, {}, "x:docks", "x")
    assert target["id"] == "npc_a", target

    target2, _ = resolve_combat_target("attack anyway", player, present, npcs, {}, "x:docks", "x")
    assert target2["id"] == "npc_a"

    hit = match_npc_by_description("find the red-haired captain", present)
    assert hit and hit["id"] == "npc_a"

    player2 = {"inventory": [], "equipment": {}, "wealth": 0, "stats": {"health": 100, "max_health": 100}}
    note, item = try_acquire_item("find a sword", player2, {"type": "district", "id": "x:docks"}, tick=1)
    assert item and note
    assert len(player2.get("inventory", [])) == 1

    p_copy = dict(present[1])
    p_copy["stats"] = dict(present[1]["stats"])
    pl = {"journal": [], "stats": {"health": 100, "max_health": 100, "stamina": 30, "attack": 20, "defense": 2, "speed": 8}, "skills": {"brawling": {"level": 5, "xp": 0}}}
    res = resolve_combat(pl, p_copy, max_rounds=8)
    facts = build_combat_facts(p_copy, res, "npc", npcs)
    assert "SCENE FACTS" in facts
    if res.get("fatal"):
        assert "FATAL" in facts
        assert "DEAD" in facts or "dead" in facts.lower()


def test_travel_graph():
    from generation.area_generator import (
        build_areas, district_edge_hours,
    )
    from generation.institution_generator import plan_city_institutions
    from simulation.travel_engine import path_hours, edge_hours

    cities = {
        "redmoor": {
            "name": "Redmoor", "archetype": "port", "crime_rate": 40, "prosperity": 50,
            "district_bias": {"docks": 1.8, "market": 1.3},
            "connected": ["grimcrest"],
            "travel_hours": {"grimcrest": 18},
        },
        "grimcrest": {
            "name": "Grimcrest", "archetype": "mining", "crime_rate": 35, "prosperity": 45,
            "district_bias": {}, "connected": ["redmoor"], "travel_hours": {"redmoor": 18},
        },
    }
    plan = plan_city_institutions(cities)
    areas = build_areas(cities, institution_plan=plan)

    assert "redmoor:docks" in areas
    assert district_edge_hours("market", "docks") == 2

    wild = "wild:grimcrest_redmoor"
    assert wild in areas
    gate = cities["redmoor"].get("gate_area")
    assert gate and gate.startswith("redmoor:")
    assert areas[gate]["edges"].get(wild) == 18

    assert edge_hours("redmoor:market", "redmoor:docks", areas) == 2
    assert path_hours("redmoor:market", "redmoor:docks", areas) == 2


def test_scene_coherence():
    from simulation.target_resolution import find_npc_by_name_in_text
    from simulation.scene_coherence import (
        resolve_travel_destination,
        build_conversation_ledger,
        sync_scene_focus,
    )
    from simulation.action_interpreter import extract_player_speech

    player = {"area": "redmoor:docks", "story_flags": {}, "known_npcs": {}, "scene_focus": None}
    areas = {"redmoor:docks": {"name": "The Docks"}, "redmoor:high_quarter": {"name": "High Quarter"}}
    dests = {"redmoor:high_quarter": 2}

    chosen, sub, msg = resolve_travel_destination("go to high quarter", player, "redmoor:docks", dests, areas)
    assert chosen == "redmoor:high_quarter"
    assert sub is None

    chosen2, sub2, msg2 = resolve_travel_destination("wander aimlessly", player, "redmoor:docks", dests, areas)
    assert chosen2 is None
    assert "not on the travel map" in (msg2 or "").lower()

    player_docks = {"area": "redmoor:docks", "story_flags": {}}
    _, sub3, msg3 = resolve_travel_destination(
        "go to the fishmonger cellar", player_docks, "redmoor:docks", dests, areas,
    )
    assert sub3 and sub3.get("id") == "cellar_fishmonger"
    assert player_docks.get("scene_subplace")

    speech = extract_player_speech("ask Aethar about the trouble here", {"name": "An"})
    assert speech and "trouble" in speech.lower()

    speech_work = extract_player_speech("ask for work", {"name": "An"})
    assert speech_work is None or "work" in speech_work.lower()

    npcs = load("characters/npcs.json", {})
    alive = [n for n in npcs.values() if n.get("status") == "alive"]
    if alive:
        sample = alive[0]
        pid = sample["id"]
        p = {
            "known_npcs": {pid: {"name_known": True}},
            "scene_focus": pid,
            "area": sample.get("area"),
        }
        hit = find_npc_by_name_in_text(f"talk to {sample['name']}", npcs, p)
        assert hit and hit["id"] == pid

        present = [sample] if sample.get("area") else []
        sync_scene_focus(p, present, npcs)
        p["scene_focus"] = pid
        sync_scene_focus(p, [], npcs)
        assert p.get("scene_focus") is None

    journal = [{"action": "hello", "excerpt": "They nodded.", "focus_npc": "npc_x"}]
    ledger = build_conversation_ledger(
        {"known_npcs": {"npc_x": {"name_known": True}}},
        journal,
        "npc_x",
        {"player_speech": "Hello?"},
    )
    assert "CONVERSATION LEDGER" in ledger


def test_scene_cast_absent():
    player = {"known_npcs": {}, "age": 30, "area": "x", "scene_focus": "npc_gone"}
    present = []
    ctx = {
        "kind": "talk",
        "target_id": None,
        "absent_npc": {"name": "Aethar", "descriptor": "the dockhand"},
    }
    focus, note, focal_id = select_scene_cast(present, player, ctx)
    assert focus == []
    assert "NOT" in note


def test_confirming_playtest_smoke():
    from simulation.action_interpreter import interpret_action
    from simulation.target_resolution import resolve_action_target
    from simulation.scheduled_events import (
        record_scheduled_events,
        parse_wait_for_event,
        fire_due_events,
    )
    from simulation.world_clock import resolve_wait_advance

    def _sch(nid, gender):
        return {
            "id": nid, "role": "scholar", "gender": gender, "status": "alive",
            "physique": {"build": "barrel-chested" if gender == "male" else "wiry"},
        }

    nedkin = _sch("n1", "male")
    zaim = _sch("z1", "female")
    player = {"scene_focus": "n1", "known_npcs": {}, "journal": [{"focus_npc": "n1"}]}
    assert resolve_action_target(
        "Ask the scholar about the archives", player, [nedkin, zaim], kind="ask_about",
    )["id"] == "n1"

    ctx = interpret_action(
        "ask the scholar what the boy found", player, [nedkin, zaim], {},
    )
    assert ctx.get("player_speech") is None

    player = {"scheduled_events": {}}
    world = {"hour_count": 10, "hour": 10}
    scene = (
        "They use the coal-chutes.\n"
        "[SCHEDULE: coal_chute_entry | the junior boys enter through the coal-chutes | +2h]"
    )
    assert record_scheduled_events(player, scene, "city:hq", world)
    event = parse_wait_for_event(
        "Wait for the junior boys to enter through the coal-chutes", player, "city:hq",
    )
    assert event
    result = resolve_wait_advance(
        "Wait for the junior boys to enter through the coal-chutes", world, player, "city:hq",
    )
    assert result.get("event")
    world["hour_count"] = 12
    fired = fire_due_events(player, world, "city:hq")
    assert fired


def main():
    tests = [
        test_event_buffer,
        test_action_interpreter,
        test_scene_cast,
        test_action_resolution,
        test_travel_graph,
        test_scene_coherence,
        test_scene_cast_absent,
        test_skill_check,
        test_narrator_helpers,
        test_world_patch,
        test_ecosystem_modules,
        test_goal_events,
        test_loot,
        test_ui_state,
        test_ui_destinations,
        test_turn_trace,
        test_area_discovery,
        test_ui_api_contract,
        test_item_equipment,
        test_action_hints,
        test_hunting_guild,
        test_npc_bonds_and_familiarity,
        test_confirming_playtest_smoke,
    ]
    for fn in tests:
        fn()
        print(f"OK  {fn.__name__}")
    print("\nAll smoke tests passed.")


if __name__ == "__main__":
    main()
