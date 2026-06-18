"""World integrity audit and clock coherence."""

from simulation.world_clock import (
    ensure_clock_coherent,
    clock_coherence_issue,
    time_of_day_from_hour,
)
from simulation.world_integrity import run_integrity_audit, expected_time_of_day


def test_time_of_day_from_hour_deep_night():
    assert time_of_day_from_hour(0) == "deep night"
    assert time_of_day_from_hour(1) == "deep night"
    assert time_of_day_from_hour(4) == "deep night"
    assert time_of_day_from_hour(5) == "dawn"
    assert time_of_day_from_hour(12) == "afternoon"


def test_ensure_clock_coherent_fixes_stale_time_of_day():
    world = {"hour_count": 1, "hour": 1, "day": 1, "time_of_day": "day", "season": "Spring"}
    world, changed = ensure_clock_coherent(world, persist=False)
    assert changed
    assert world["time_of_day"] == "deep night"
    assert clock_coherence_issue(world) is None


def test_clock_coherence_issue_detects_drift():
    world = {"hour": 1, "time_of_day": "morning"}
    issue = clock_coherence_issue(world)
    assert issue
    assert "deep night" in issue


def test_integrity_audit_flags_dangling_focus():
    player = {"area": "hq", "scene_focus": "missing_npc"}
    npcs = {"alive_one": {"status": "alive", "name": "A", "role": "guard", "gender": "male"}}
    areas = {"hq": {"name": "Headquarters"}}
    issues, warnings = run_integrity_audit(
        player=player,
        npcs=npcs,
        areas=areas,
        institutions={},
        rumors=[],
        events=[],
        world={"hour_count": 1, "hour": 1, "time_of_day": "deep night"},
    )
    assert any("scene_focus" in i for i in issues)


def test_integrity_audit_relationship_out_of_bounds():
    player = {"area": "hq"}
    npcs = {
        "a": {"status": "alive", "name": "A", "role": "guard", "gender": "male", "area": "hq"},
        "b": {"status": "alive", "name": "B", "role": "merchant", "gender": "female", "area": "hq"},
    }
    rels = {"a": {"b": {"trust": 150.0, "familiarity": 10.0}}}
    issues, _ = run_integrity_audit(
        player=player,
        npcs=npcs,
        areas={"hq": {}},
        institutions={},
        rumors=[],
        events=[],
        world={"hour_count": 10, "hour": 10, "time_of_day": "morning"},
        relationships=rels,
    )
    assert any("out of bounds" in i for i in issues)


def test_expected_time_of_day_from_hour():
    world = {"hour": 3, "time_of_day": "day"}
    assert expected_time_of_day(world) == "deep night"
