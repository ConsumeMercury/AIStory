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


def test_dialogue_place_fact_gap():
    from simulation.narrator_facts import dialogue_place_fact_gap

    scene = (
        'The priest whispers, "Meet me at the customs house before dawn."\n'
        "[FACT: speaking | g1]\n"
    )
    facts = parse_narrator_facts(scene)
    gap = dialogue_place_fact_gap(scene, facts)
    assert gap is not None
    assert "customs house" in gap.lower()
    assert "dialogue names place" in gap.lower()


def test_dialogue_place_fact_gap_ignores_narrative_scenery():
    from simulation.narrator_facts import dialogue_place_fact_gap

    scene = (
        "You stop a yard from the low stone wall, sinking into the wet grit between the pavers. "
        "He looks at your boots, then at the breadth of your chest. "
        'His eyes dart toward the dark mouth of the cellars down the lane. '
        '"The headmaster\'s ash is already in the river, friend."\n'
        "[FACT: speaking | g1]\n"
        "[FACT: place | cellars]\n"
        "[FACT: place | the gutter]\n"
    )
    facts = parse_narrator_facts(scene)
    assert dialogue_place_fact_gap(scene, facts) is None


def test_extract_dialogue_place_names():
    from simulation.narrator_facts import extract_dialogue_place_names

    text = 'He says, "Meet me at the customs house before dawn."'
    assert "customs house" in extract_dialogue_place_names(text)
    assert not extract_dialogue_place_names(
        "You stop a yard from the low stone wall near the wet grit."
    )
