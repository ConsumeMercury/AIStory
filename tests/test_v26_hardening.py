"""Guards for v26 scan findings — token budget, scene_focus ownership, module wiring."""

from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def test_narrator_generate_scene_passes_max_tokens():
    from simulation.narrator import generate_scene

    with patch("simulation.narrator.assemble_scene_prompt") as asp:
        asp.return_value = ("prompt", 900, "npc_a", {})
        with patch("simulation.narrator.generate_text") as gen:
            gen.return_value = "scene"
            generate_scene(
                "look around",
                world={"day": 1, "hour": 8},
                player={"name": "Test", "journal": []},
                present_npcs=[],
                memories=[],
            )
    gen.assert_called_once()
    assert gen.call_args.kwargs.get("max_tokens") == 900


def test_story_modules_do_not_write_scene_focus():
    for rel in ("simulation/story_manager.py", "simulation/story_graph.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert 'player["scene_focus"]' not in text, rel
        assert "player['scene_focus']" not in text, rel
        assert 'player["scene_focus"] =' not in text, rel


def test_tier_modules_wired_in_narrator_or_turn_loop():
    narrator = (ROOT / "simulation" / "narrator.py").read_text(encoding="utf-8")
    story_loop = (ROOT / "simulation" / "story_loop.py").read_text(encoding="utf-8")
    npc_actions = (ROOT / "simulation" / "npc_actions.py").read_text(encoding="utf-8")
    event_logger = (ROOT / "simulation" / "event_logger.py").read_text(encoding="utf-8")

    assert "validate_directives" in narrator
    assert "cultural_reaction_block" in narrator
    assert "build_scene_objectives_block" in narrator
    assert "story_graph_narrator_block" in narrator
    assert "focal_circle_block" in narrator
    assert "score_event_importance" in event_logger or "event_importance" in event_logger
    assert "apply_plan_weights" in npc_actions or "advance_subgoal" in npc_actions
    assert "sync_all_pipelines" in story_loop or "record_turn_story_progress" in story_loop
