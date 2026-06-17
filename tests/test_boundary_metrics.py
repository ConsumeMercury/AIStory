"""Boundary instrumentation — shadow metrics and bug shape tagging."""

from simulation.boundary_metrics import (
    build_classifier_diff,
    build_output_boundary,
    build_turn_boundary,
    facts_expected_for_beat,
    persist_boundary_trace,
    summarize_fact_emission,
    summarize_player_boundary_history,
    tag_turn_issues,
    update_session_boundary_stats,
)
from simulation.bug_ledger import BugShape
from simulation.turn_trace import get_boundary_summary, record_turn, get_last_turn


def test_classifier_diff_detects_disagreement():
    regex = {"kind": "general", "target_id": None, "player_speech": None}
    validated = {"kind": "ask_about", "target_id": "g1", "player_speech": "When?"}
    diff = build_classifier_diff(regex, validated)
    assert diff["disagrees"]
    assert any(d["field"] == "kind" for d in diff["diffs"])


def test_facts_expected_for_dialogue():
    assert facts_expected_for_beat("ask_about", {"target_id": "g1"})
    assert not facts_expected_for_beat("explore", {})


def test_tag_turn_issues_facts_missing():
    boundary = {"facts_missing": True, "facts_expected": True}
    tagged = tag_turn_issues([], [], {"kind": "ask_about", "target_id": "g1"}, boundary)
    assert any(t["shape"] == BugShape.DIRECTIVE_HOPE.value for t in tagged)


def test_output_boundary_parses_tags():
    raw = 'Hello. [FACT: speaking | g1] [SCHEDULE: dawn | bell | +5h]'
    out = build_output_boundary(
        kind="ask_about",
        action_ctx={"kind": "ask_about", "target_id": "g1"},
        raw_scene=raw,
        prose_issues=[],
        fact_issues=[],
        focal_id="g1",
    )
    assert out["facts"]["has_facts"]
    assert out["facts"]["tag_count"] >= 2


def test_session_stats_accumulate():
    player = {}
    tb = {
        "classifier_invoked": True,
        "classifier_disagrees": True,
        "facts": {"has_facts": True},
        "facts_expected": True,
        "facts_missing": False,
        "gate_active": True,
        "regenerated": True,
    }
    update_session_boundary_stats(player, tb, [{"shape": "A", "summary": "x", "overhaul": ""}])
    stats = player["boundary_stats"]
    assert stats["turns"] == 1
    assert stats["classifier_disagrees"] == 1
    assert stats["facts_emitted"] == 1
    assert stats["issue_shapes"]["A"] == 1


def test_persist_boundary_trace_on_player():
    player = {}
    tb = {"classifier_mode": "shadow", "classifier_invoked": True, "facts": {"has_facts": True}}
    persist_boundary_trace(
        player,
        tick=3,
        action="go to the cellar",
        kind="approach",
        turn_boundary=tb,
        action_ctx={
            "relocated": True,
            "left_behind_cast": ["bessa"],
            "narrative_trace": {"dramatic_question": "Who waits below?", "structure_mode": "action"},
            "narrative_issues": ["social beat lacks dramatic_question in scene_stakes"],
        },
        scene_cast_ids=["scraper"],
    )
    assert player["last_boundary_trace"]["tick"] == 3
    assert player["last_boundary_trace"]["reloc"]["left_behind_cast"] == ["bessa"]
    assert player["last_boundary_trace"]["narrative"]["dramatic_question"] == "Who waits below?"
    assert player["last_boundary_trace"]["narrative_issues"]
    assert player["boundary_history"]
    summary = summarize_player_boundary_history(player["boundary_history"])
    assert summary["turns_in_history"] == 1


def test_session_stats_track_narrative_issues():
    player = {}
    tb = {"narrative_issue_count": 2}
    update_session_boundary_stats(player, tb)
    assert player["boundary_stats"]["narrative_issues"] == 2


def test_facts_missing_for_dialogue_requires_speaking_tag():
    from simulation.boundary_metrics import facts_missing_for_beat

    facts = {"speaking": [], "death": [], "places": ["cellars"], "schedules": []}
    emission = summarize_fact_emission(facts)
    assert facts_missing_for_beat("ask_about", {"target_id": "g1"}, facts, emission)
    facts["speaking"] = ["g1"]
    emission = summarize_fact_emission(facts)
    assert not facts_missing_for_beat("ask_about", {"target_id": "g1"}, facts, emission)


def test_tag_turn_issues_skips_duplicate_schedule_shape():
    boundary = {
        "schedule_untagged": True,
        "schedule_regex_captures": [{"label": "third toll"}],
    }
    fact_issues = ["timed event promised in prose (third toll) but no [SCHEDULE: event_id | label | +Nh] tag emitted"]
    tagged = tag_turn_issues([], fact_issues, {"kind": "talk"}, boundary)
    schedule_tags = [t for t in tagged if "schedule" in t["summary"].lower()]
    assert len(schedule_tags) == 1


def test_turn_trace_records_boundary():
    record_turn(tick=1, action="test", kind="talk", boundary={"classifier_mode": "off"})
    last = get_last_turn()
    assert last.get("boundary", {}).get("classifier_mode") == "off"
    summary = get_boundary_summary()
    assert summary.get("turns_in_history", 0) >= 1
