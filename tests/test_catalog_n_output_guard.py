"""Catalog N — output interpretation guard (prose asserting unauthorized state)."""

from simulation.fact_gate import validate_turn_output
from simulation.prose_assertion_guard import validate_prose_assertions
from simulation.scene_state import SceneState


def _scene():
    return SceneState(
        tick=1, day=1, hour=1, time_of_day="day",
        area_id="hq", subplace_id=None, place_label="Market Gate",
        area_present=(), cast=(), cast_ids=frozenset(),
        scene_focus=None, pending_events=(),
    )


def test_phantom_acquisition_flagged():
    text = 'She hands you the key with a nod. "Take it."'
    issues = validate_prose_assertions(
        text,
        player={},
        npcs={},
        action_ctx={"kind": "talk"},
        focal_npc_id="m1",
        present_npcs=[{"id": "m1", "name": "Mara"}],
    )
    assert any("acquisition" in i.lower() or "grant" in i.lower() for i in issues)


def test_authorized_search_not_flagged():
    text = "You pick up the notched blade from the crate."
    issues = validate_prose_assertions(
        text,
        player={},
        npcs={},
        action_ctx={"kind": "search", "acquired_item": {"name": "notched blade"}},
        focal_npc_id=None,
        present_npcs=[],
    )
    assert not any("acquisition" in i.lower() for i in issues)


def test_time_skip_without_wait_flagged():
    text = "Hours later, the crowd thins."
    issues = validate_prose_assertions(
        text,
        player={},
        npcs={},
        action_ctx={"kind": "talk"},
        focal_npc_id="m1",
        present_npcs=[{"id": "m1"}],
        facts={},
    )
    assert any("time" in i.lower() for i in issues)


def test_invented_named_npc_flagged():
    text = "The merchant Tomas nods, but Doran the smith interrupts."
    issues = validate_prose_assertions(
        text,
        player={},
        npcs={"m1": {"id": "m1", "name": "Tomas"}},
        action_ctx={"kind": "talk"},
        focal_npc_id="m1",
        present_npcs=[{"id": "m1", "name": "Tomas"}],
        known_ids={"m1"},
    )
    assert any("Doran" in i or "not in present cast" in i for i in issues)


def test_atmosphere_mismatch_deep_night_flagged():
    from simulation.scene_state import SceneState

    scene = SceneState(
        tick=1, day=1, hour=1, time_of_day="deep night",
        area_id="hq", subplace_id=None, place_label="Gate",
        area_present=(), cast=(), cast_ids=frozenset(),
        scene_focus=None, pending_events=(),
    )
    text = "Afternoon heat presses down as the sun climbs high."
    issues = validate_prose_assertions(
        text,
        player={},
        npcs={},
        action_ctx={"kind": "talk"},
        focal_npc_id="m1",
        present_npcs=[{"id": "m1"}],
        scene_state=scene,
    )
    assert any("clock" in i.lower() or "daytime" in i.lower() or "deep night" in i.lower() for i in issues)


def test_phantom_injury_flagged():
    text = "You notice you're bleeding from a cut you don't remember."
    issues = validate_prose_assertions(
        text,
        player={"injuries": []},
        npcs={},
        action_ctx={"kind": "talk"},
        focal_npc_id="m1",
        present_npcs=[{"id": "m1"}],
    )
    assert any("injury" in i.lower() or "bleeding" in i.lower() for i in issues)


def test_draw_weapon_without_inventory_flagged():
    text = "You draw your sword and step forward."
    issues = validate_prose_assertions(
        text,
        player={"equipment": {}, "inventory": []},
        npcs={},
        action_ctx={"kind": "talk"},
        focal_npc_id=None,
        present_npcs=[],
    )
    assert any("weapon" in i.lower() for i in issues)


def test_malformed_fact_tag_stripped():
    from simulation.narrator_facts import strip_narrator_facts

    text = 'She nods.\n[FACT: speaking | npc_1'
    cleaned = strip_narrator_facts(text)
    assert "[FACT" not in cleaned
    assert "She nods" in cleaned


def test_fact_gate_includes_assertion_issues():
    scene = _scene()
    text = "Hours later, she gives you a key."
    issues, *_ = validate_turn_output(
        text,
        player={},
        npcs={},
        action_ctx={"kind": "talk"},
        focal_npc_id=None,
        scene_place="Market Gate",
        present_npcs=[],
        scene_state=scene,
    )
    assert any("time" in i.lower() or "acquisition" in i.lower() or "grant" in i.lower() for i in issues)


def test_fact_item_tag_without_authorization():
    from simulation.narrator_facts import validate_narrator_facts
    facts = {"speaking": [], "death": [], "places": [], "items": ["rusty key"], "schedules": []}
    issues = validate_narrator_facts(
        facts, {}, {}, _scene(), {"kind": "talk"}, None,
    )
    assert any("item tag" in i.lower() for i in issues)


def test_inventory_missing_in_fact_gate():
    text = 'You flash the badge. "Let me through."'
    issues, *_ = validate_turn_output(
        text,
        player={"inventory": []},
        npcs={},
        action_ctx={"kind": "talk", "inventory_missing": ["badge"]},
        focal_npc_id="m1",
        scene_place="Gate",
        present_npcs=[{"id": "m1"}],
        scene_state=_scene(),
    )
    assert any("missing inventory" in i.lower() for i in issues)
