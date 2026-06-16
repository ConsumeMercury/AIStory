"""Memory context assembly."""

from simulation.memory_context import build_memory_context


def test_build_memory_context_includes_plot_summary():
    player = {
        "starting_pipeline": {"title": "Test", "hook": "Something wrong", "current": "stage one"},
        "journal": [{"day": 1, "action": "look around", "place": "Market", "excerpt": "grease and smoke"}],
    }
    block, debug = build_memory_context(player, {}, [], focal_npc_id=None, present_ids=[])
    assert "PLOT SUMMARY" in block
    assert "RECENT BEATS" in block
    assert debug["tokens_cap"]["plot_summary"] == 400
