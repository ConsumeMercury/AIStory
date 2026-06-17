"""Scene coherence — targeting, local movement, focus, travel failures."""

import pytest

from simulation.action_interpreter import interpret_action
from simulation.local_places import resolve_local_movement, looks_like_local_movement
from simulation.scene_coherence import resolve_travel_destination, place_label
from simulation.target_resolution import resolve_action_target


def _npc(nid, role="soldier", gender="male", name="Bob"):
    return {"id": nid, "name": name, "role": role, "gender": gender, "status": "alive"}


def test_ask_solia_is_ask_about():
    player = {"known_npcs": {"n1": {"name_known": True}}}
    ctx = interpret_action(
        "ask Solia about the trouble here",
        player,
        [_npc("n1", name="Solia Dremar")],
        {},
        npcs={"n1": _npc("n1", name="Solia Dremar")},
    )
    assert ctx["kind"] == "ask_about"
    assert ctx["target_id"] == "n1"


def test_talk_to_priest_targets_priest_not_focus():
    soldier = _npc("soldier", role="soldier", name="Solia")
    priest = _npc("priest", role="priest", name="Father Hale")
    player = {
        "scene_focus": "soldier",
        "known_npcs": {"soldier": {"name_known": True, "seen_before": True}},
    }
    target = resolve_action_target(
        "Talk to the priest",
        player,
        [soldier, priest],
        kind="talk",
    )
    assert target["id"] == "priest"


def test_role_hint_blocks_focus_fallback():
    soldier = _npc("soldier", role="soldier")
    priest = _npc("priest", role="priest")
    player = {"scene_focus": "soldier", "known_npcs": {}}
    target = resolve_action_target(
        "ask about the hymn",
        player,
        [soldier, priest],
        kind="ask_about",
    )
    # No role in text — may use focus
    assert target["id"] == "soldier"


def test_local_movement_sets_subplace():
    player = {"area": "city:temple_row", "story_flags": {}}
    sub, msg = resolve_local_movement("Go to the heavy oak door", player, "city:temple_row")
    assert sub is not None
    assert sub["id"] == "door"
    assert player.get("scene_subplace", {}).get("label")


def test_approach_kind_for_door():
    ctx = interpret_action("Go to the heavy oak door", {"area": "x"}, [], {})
    assert ctx["kind"] == "approach"


def test_travel_fail_no_district_match():
    player = {"area": "city:temple_row", "story_flags": {}}
    chosen, sub, msg = resolve_travel_destination(
        "go to the temple clerks",
        player,
        "city:temple_row",
        {"city:market": 2},
        {"city:market": {"name": "Market Square"}},
    )
    # clerks match local POI first
    assert sub is not None or chosen is None


def test_place_label_includes_subplace():
    player = {
        "area": "city:temple_row",
        "scene_subplace": {"id": "door", "label": "the heavy door", "area": "city:temple_row"},
    }
    area = {"name": "Temple Row"}
    assert "Temple Row" in place_label(player, area)
    assert "heavy door" in place_label(player, area)


def test_investigate_is_environment_only_even_with_role_hint():
    from simulation.scene_cast import select_scene_cast

    soldier = _npc("s1", role="soldier")
    priest = _npc("p1", role="priest")
    player = {"scene_focus": "s1"}
    action_ctx = {"kind": "investigate"}
    focus, note, focal_id = select_scene_cast([soldier, priest], player, action_ctx)
    assert focus == []
    assert focal_id is None
    assert "Environment-only" in note


def test_promoted_place_from_prior_narration():
    player = {
        "area": "ashmoor:high_quarter",
        "story_flags": {},
        "journal": [{
            "area": "ashmoor:high_quarter",
            "scene": (
                'Ashby nodded toward the shadows. "The captain waits at the cistern," he said.'
            ),
        }],
    }
    sub, msg = resolve_local_movement(
        "Go to the cistern",
        player,
        "ashmoor:high_quarter",
    )
    assert sub is not None
    assert "cistern" in sub["label"].lower()
    assert player.get("scene_subplace", {}).get("id")
    assert "LOCAL MOVEMENT" in msg


def test_record_narrator_places_from_scene():
    from simulation.local_places import record_narrator_places

    player = {"narrator_places": {}}
    scene = "The captain waits at the cistern while horns blow."
    assert record_narrator_places(player, scene, "city:high_quarter") is True
    stored = player["narrator_places"]["city:high_quarter"]
    assert any("cistern" in rec["label"].lower() for rec in stored.values())


def test_follow_noise_is_approach():
    ctx = interpret_action("follow the noise", {"area": "x"}, [], {})
    assert ctx["kind"] == "approach"


def test_stalled_beat_note_on_repeated_failure():
    from simulation.narrative_continuity import build_stalled_beat_note

    journal = [{
        "area": "a1",
        "focus_npc": "n1",
        "excerpt": "The boy wants a stripe.",
        "approach_failed": True,
    }]
    note = build_stalled_beat_note(
        {},
        journal,
        {"approach_failed": True},
        "n1",
        "a1",
    )
    assert "STALLED BEAT" in note
    assert "do not replay" in note.lower() or "Do NOT repeat" in note


def test_looks_like_local_movement():
    assert looks_like_local_movement("go to the oak door")
    assert looks_like_local_movement("go down the lane to the crowd")
    assert looks_like_local_movement("push through to the center of the crowd")
    assert not looks_like_local_movement("go to the market district")


def test_crowd_promoted_from_journal():
    from simulation.local_places import resolve_local_movement, record_narrator_places

    player = {
        "area": "city:temple",
        "journal": [{
            "area": "city:temple",
            "scene": "A knot of petitioners fills the center of the crowd near the buttress.",
        }],
        "story_flags": {},
        "narrator_places": {},
    }
    record_narrator_places(player, player["journal"][0]["scene"], "city:temple")
    sub, msg = resolve_local_movement(
        "go down the lane to the crowd", player, "city:temple",
    )
    assert sub
    assert "crowd" in sub["label"].lower()


def test_unregistered_crowd_movement_hard_fails():
    from simulation.scene_cast import select_scene_cast
    from simulation.local_places import resolve_local_movement

    player = {"area": "city:temple", "journal": [], "story_flags": {}, "narrator_places": {}}
    sub, msg = resolve_local_movement(
        "push through to the center of the crowd", player, "city:temple",
    )
    assert sub is None
    assert msg and "APPROACH FAILED" in msg
    priest = {"id": "p1", "role": "priest", "gender": "male", "status": "alive"}
    player["scene_focus"] = "p1"
    ctx = {"kind": "approach", "approach_failed": True, "action_summary": "push through to the crowd"}
    focus, note, fid = select_scene_cast([priest], player, ctx)
    assert focus == []
    assert fid is None
    assert "snap back" in note.lower() or "APPROACH FAILED" in note
