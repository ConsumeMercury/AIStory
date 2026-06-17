"""Structured narrator fact tags."""

from simulation.narrator_facts import (
    parse_narrator_facts,
    strip_narrator_facts,
    validate_narrator_facts,
)
from simulation.scene_state import SceneState


def _scene(ids):
    cast = tuple({"id": i, "name": i, "role": "guard", "status": "alive"} for i in ids)
    return SceneState(
        tick=1, day=1, hour=1, time_of_day="day",
        area_id="hq", subplace_id=None, place_label="Gate",
        area_present=cast, cast=cast, cast_ids=frozenset(ids),
        scene_focus=ids[0], pending_events=(),
    )


def test_parse_and_strip_facts():
    text = (
        'He speaks.\n[FACT: speaking | g1]\n'
        '[SCHEDULE: dawn | dawn bell | +5h]\n'
        '[FACT: place | stable yard]\n'
    )
    facts = parse_narrator_facts(text)
    assert facts["speaking"] == ["g1"]
    assert facts["places"] == ["stable yard"]
    assert len(facts["schedules"]) == 1
    cleaned = strip_narrator_facts(text)
    assert "[FACT:" not in cleaned
    assert "[SCHEDULE:" not in cleaned
    assert "He speaks." in cleaned


def test_validate_death_without_combat():
    scene = _scene(["g1"])
    npcs = {"g1": {"id": "g1", "name": "Guard", "status": "alive"}}
    facts = {"speaking": [], "death": ["g1"], "places": [], "schedules": []}
    issues = validate_narrator_facts(
        facts, {}, npcs, scene, {"kind": "talk"}, "g1",
    )
    assert any("death" in i.lower() for i in issues)


def test_validate_speaking_not_in_cast():
    scene = _scene(["g1"])
    facts = {"speaking": ["stranger"], "death": [], "places": [], "schedules": []}
    issues = validate_narrator_facts(facts, {}, {}, scene, {}, "g1")
    assert any("not in scene cast" in i for i in issues)
