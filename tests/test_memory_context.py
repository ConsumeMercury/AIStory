"""Memory context assembly."""

from simulation.beat_structure import build_narrative_thread_directive
from simulation.memory_context import build_memory_context


def test_build_memory_context_includes_journal_not_plot():
    player = {
        "starting_pipeline": {"title": "Test", "hook": "Something wrong", "current": "stage one"},
        "journal": [{"day": 1, "action": "look around", "place": "Market", "excerpt": "grease and smoke"}],
    }
    block, debug = build_memory_context(player, {}, [], focal_npc_id=None, present_ids=[])
    assert "PLOT SUMMARY" not in block
    assert "RECENT BEATS" in block
    assert "plot_summary" not in debug["tokens_cap"] or debug["tokens_used"].get("plot_summary", 0) == 0


def test_plot_summary_lives_in_narrative_thread_block():
    player = {
        "starting_pipeline": {"title": "Test", "hook": "Something wrong", "current": "stage one"},
        "goals": [{"text": "Find the truth", "progress": 0, "target": 3, "complete": False}],
    }
    thread = build_narrative_thread_directive(player, {}, kind="talk", action_context={})
    assert "NARRATIVE THREAD" in thread
    assert "Find the truth" in thread
