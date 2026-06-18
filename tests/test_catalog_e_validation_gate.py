"""Catalog E — facts gate, validators, regen governor."""

import os

from simulation.fact_gate import validate_schedule_emission, validate_turn_output
from simulation.narrator_facts import (
    dialogue_place_fact_gap,
    parse_narrator_facts,
    strip_narrator_facts,
    validate_narrator_facts,
)
from simulation.prose_validator import place_drift, role_mismatch
from simulation.regen_governor import (
    apply_regen_governor,
    build_regen_exhausted_directive,
    max_regen_attempts,
)
from simulation.scene_state import SceneState
from tests.fixtures.isolated_game import bootstrap_isolated_game, run_mocked_actions


def _scene(ids=("g1",)):
    cast = tuple({"id": i, "name": i, "role": "guard", "status": "alive"} for i in ids)
    return SceneState(
        tick=1, day=1, hour=1, time_of_day="day",
        area_id="hq", subplace_id=None, place_label="Temple Row",
        area_present=cast, cast=cast, cast_ids=frozenset(ids),
        scene_focus=ids[0], pending_events=(),
    )


def test_speaking_fact_matches_actual_speaker():
    scene = _scene(["g1"])
    facts = {"speaking": ["stranger"], "death": [], "places": [], "schedules": []}
    issues = validate_narrator_facts(facts, {}, {}, scene, {"kind": "talk"}, "g1")
    assert any("not in scene cast" in i for i in issues)


def test_death_fact_matches_state():
    scene = _scene(["v1"])
    npcs = {"v1": {"id": "v1", "name": "Victim", "status": "alive", "role": "merchant"}}
    text = "He falls. [FACT: death | v1]"
    _, facts, _, fact_issues, _, _ = validate_turn_output(
        text, player={}, npcs=npcs, action_ctx={"kind": "attack"},
        focal_npc_id="v1", scene_place="Row", present_npcs=[npcs["v1"]], scene_state=scene,
    )
    assert facts.get("death") == ["v1"]
    assert fact_issues


def test_place_fact_emitted_for_move_target():
    text = "You step toward the gate.\n[FACT: place | stable yard]\n"
    facts = parse_narrator_facts(text)
    assert "stable yard" in facts.get("places", [])


def test_place_fact_emitted_for_dialogue_named_place():
    scene = (
        'The priest whispers, "Meet me at the customs house before dawn."\n'
        "[FACT: speaking | g1]\n"
    )
    facts = parse_narrator_facts(scene)
    gap = dialogue_place_fact_gap(scene, facts)
    assert gap
    assert "customs house" in gap.lower()


def test_role_imagery_mismatch_caught():
    issue = role_mismatch(
        "He wears the guard's boots as he blocks the door.",
        "priest",
        "male",
    )
    assert issue


def test_role_imagery_false_positive_guard_vocative():
    text = '"Use my name, soldier," the merchant says.'
    assert role_mismatch(text, "merchant", "male") is None


def test_location_lock_violation_caught():
    issue = place_drift(
        "You enter the harbor district and the stalls rise around you.",
        "Temple Row — the heavy door",
    )
    assert issue
    assert "harbor" in issue.lower() or "moves toward" in issue.lower()


def test_regen_governor_bounds_attempts(monkeypatch):
    monkeypatch.setenv("AISTORY_PROSE_RETRIES", "1")
    assert max_regen_attempts() == 1
    issues = ["Wrong speaker: Solia spoke but focal is priest"]
    _, should_retry, meta = apply_regen_governor(issues, attempt=1, kind="talk")
    assert not should_retry
    assert meta.get("exhausted") or meta.get("skip_reason")


def test_regen_exhausted_queues_directive():
    directive = build_regen_exhausted_directive(["LOCATION LOCK violation", "Wrong speaker"])
    assert "UNRESOLVED" in directive
    assert "LOCATION LOCK" in directive


def test_regen_succeeds_within_budget_for_speaker_violation():
    issues = ["Wrong speaker: absent NPC spoke"]
    _, should_retry, _ = apply_regen_governor(issues, attempt=0, kind="talk")
    assert should_retry


def test_schedule_untagged_is_flagged():
    scene = 'She says, "Wait for the third toll before you go behind the wall."'
    issues = validate_schedule_emission(scene)
    assert issues


def test_machine_tags_stripped_from_journal(tmp_path, monkeypatch):
    bootstrap_isolated_game(tmp_path, monkeypatch)

    def scene_with_tags(_kw):
        return 'He nods.\n[FACT: speaking | sch_a]\n[SCHEDULE: x | event | +1h]\n'

    run_mocked_actions(["Ask the scholar about archives"], scene_with_tags)
    import storage
    pl = storage.load("player/player.json", {})
    entry = (pl.get("journal") or [])[-1]
    excerpt = entry.get("excerpt") or entry.get("scene") or ""
    assert "[FACT:" not in excerpt
    assert "[SCHEDULE:" not in excerpt


def test_strip_narrator_facts_removes_tags():
    raw = 'Line.\n[FACT: speaking | g1]\n[SCHEDULE: x | y | +1h]\n'
    cleaned = strip_narrator_facts(raw)
    assert "[FACT:" not in cleaned
    assert "[SCHEDULE:" not in cleaned
