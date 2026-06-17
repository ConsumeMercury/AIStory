"""Narrative boundary trace and shadow validation."""

from simulation.narrative_trace import build_narrative_trace, validate_narrative_function
from simulation.story_manager import record_turn_story_progress


def test_build_narrative_trace_includes_stakes():
    player = {
        "scene_stakes": {
            "dramatic_question": "Will the dockmaster talk?",
            "gain": "a lead",
            "lose": "time",
            "arc_id": "area_stormbridge:docks",
        },
        "starting_pipeline": {
            "area_id": "stormbridge:docks",
            "title": "Smuggler's Toll",
            "stage": 0,
            "stages": ["hook"],
            "current": "watch the crates",
        },
        "area": "stormbridge:docks",
    }
    trace = build_narrative_trace(
        player,
        kind="talk",
        action_ctx={"structure_mode": "continuation", "narrator_blocks_included": ["story_manager"]},
        structure_mode="continuation",
    )
    assert trace["dramatic_question"] == "Will the dockmaster talk?"
    assert trace["structure_mode"] == "continuation"
    assert "story_manager" in trace["narrator_blocks_included"]


def test_validate_flags_generic_dramatic_question():
    player = {"scene_stakes": {"dramatic_question": "What will the plot reveal next?"}}
    issues = validate_narrative_function(player, kind="ask_about", action_ctx={})
    assert any("generic placeholder" in i for i in issues)


def test_validate_flags_missing_social_stakes():
    player = {"scene_stakes": {}}
    issues = validate_narrative_function(player, kind="talk", action_ctx={})
    assert any("lacks dramatic_question" in i for i in issues)


def test_record_turn_story_progress_uses_case_not_generic_plot():
    player = {
        "active_case": {
            "id": "case1",
            "title": "The Missing Ledger",
            "stage": 1,
            "stages": ["gather suspects", "confront"],
            "suspect_ids": ["s1"],
            "evidence": [],
        },
        "area": "stormbridge:docks",
    }
    npcs = {"s1": {"name": "Bessa", "status": "alive"}}
    record_turn_story_progress(player, kind="ask_about", action_ctx={"target_id": "s1"}, npcs=npcs)
    q = player["scene_stakes"]["dramatic_question"]
    assert q
    assert "the plot" not in q.lower()
    assert "Bessa" in q or "Missing Ledger" in q or "confront" in q.lower()
