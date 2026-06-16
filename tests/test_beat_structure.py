"""Beat structure and narrative thread prompt blocks."""

from simulation.beat_structure import (
    classify_beat_structure,
    build_beat_structure_block,
    build_narrative_thread_directive,
    recent_same_area,
)


def _player_with_case():
    return {
        "starting_pipeline": {
            "title": "Fang Market",
            "hook": "Forged lodge seals.",
            "current": "fakes implicate the clerk",
        },
        "goals": [
            {"text": "Uncover the market fraud", "progress": 2, "target": 3, "complete": False},
        ],
        "active_case": {
            "title": "Death in Market",
            "victim_id": "v1",
            "stage": 1,
            "stages": ["learn", "identify", "prove"],
            "solved": False,
        },
        "journal": [
            {"area": "ashmoor:market", "focus_npc": "f1", "kind": "talk", "excerpt": "Heat rises."},
            {"area": "ashmoor:market", "focus_npc": "f1", "kind": "talk", "excerpt": "She waits."},
            {"area": "ashmoor:market", "focus_npc": "f1", "kind": "talk", "excerpt": "Another line."},
        ],
    }


def test_classify_stalled_on_failed_approach():
    mode = classify_beat_structure(
        "approach",
        {"approach_failed": True},
        {},
        [],
        "ashmoor:market",
        None,
    )
    assert mode == "stalled"


def test_classify_revelation_on_item_acquire():
    mode = classify_beat_structure(
        "search",
        {"acquired_item": {"name": "Notched Blade"}},
        {},
        [],
        "ashmoor:market",
        None,
    )
    assert mode == "revelation"


def test_classify_continuation_after_many_same_spot_beats():
    journal = [{"area": "x:market", "kind": "talk"} for _ in range(4)]
    mode = classify_beat_structure("talk", {}, {}, journal, "x:market", "f1")
    assert mode == "continuation"


def test_structure_block_includes_same_spot_warning():
    player = _player_with_case()
    block = build_beat_structure_block(
        "talk", {}, player, player["journal"], "ashmoor:market", "f1",
    )
    assert "PROSE STRUCTURE" in block
    assert "SAME SPOT" in block
    assert "OPENING VARIATION" in block


def test_narrative_thread_includes_case_and_plot_summary():
    npcs = {"f1": {"id": "f1", "name": "Fahir", "role": "merchant"}}
    block = build_narrative_thread_directive(
        _player_with_case(), npcs,
        focal_npc_id="f1", present_ids=["f1"], kind="talk", action_context={},
    )
    assert "NARRATIVE THREAD" in block
    assert "Death in Market" in block
    assert "Uncover the market fraud" in block
    assert "PLOT SUMMARY" in block


def test_recent_same_area_filters_by_area():
    journal = [
        {"area": "a:market"},
        {"area": "b:docks"},
        {"area": "a:market"},
    ]
    assert len(recent_same_area(journal, "a:market")) == 2
