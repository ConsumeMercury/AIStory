"""Catalog K — prompt assembly & token discipline."""

import os

from simulation.narrator import assemble_scene_prompt
from simulation.narrator_blocks import list_included_blocks, narrator_block_profile
from simulation.novel_craft import token_budget_for_kind
from tests.fixtures.catalog_fixtures import npc, player


def test_token_budgets_by_kind():
    assert token_budget_for_kind("attack") == 2600
    assert token_budget_for_kind("talk") == 1100
    assert token_budget_for_kind("ask_name") == 550
    assert token_budget_for_kind("explore", opening=True) == 2400
    assert token_budget_for_kind("explore", opening=False) == 1800


def test_narrator_blocks_gated_by_kind():
    approach_blocks = set(list_included_blocks(
        "approach", has_focal=False, has_journal=True, profile="standard",
    ))
    ask_blocks = set(list_included_blocks(
        "ask_about", has_focal=True, has_journal=True, profile="standard",
    ))
    assert "immersion" not in approach_blocks
    assert len(ask_blocks) >= len(approach_blocks)


def test_minimal_profile_drops_tier_blocks(monkeypatch):
    monkeypatch.setenv("AISTORY_NARRATOR_BLOCKS", "minimal")
    assert narrator_block_profile() == "minimal"
    included = list_included_blocks(
        "withdraw", has_focal=False, has_journal=False, profile="minimal",
    )
    assert "story_graph" not in included
    assert "causality" not in included
    assert "immersion" not in included


def test_assemble_scene_prompt_records_block_profile():
    pl = player(journal=[{"action": "prior", "kind": "explore"}])
    world = {"world_name": "Test", "day": 1, "time_of_day": "day", "season": "", "weather": "Clear"}
    focal = npc("g1", role="guard", name="Holt")
    prompt, budget, _fid, _debug = assemble_scene_prompt(
        "talk to Holt",
        world,
        pl,
        [focal],
        [],
        action_context={"kind": "talk", "target_id": "g1"},
        focal_npc_id="g1",
        hard_constraints="HARD",
    )
    assert budget == token_budget_for_kind("talk")
    assert "Holt" in prompt or "guard" in prompt.lower()


def test_prose_retry_reduces_token_budget(monkeypatch):
    monkeypatch.setenv("AISTORY_DEBUG_TOKENS", "0")
    from unittest.mock import MagicMock, patch

    captured = {}

    def fake_generate_text(prompt, **kwargs):
        captured.update(kwargs)
        return "scene prose"

    pl = player()
    world = {"world_name": "T", "day": 1, "time_of_day": "day", "season": "", "weather": ""}
    guard = npc("g1", role="guard", name="Holt")
    with patch("simulation.narrator.generate_text", side_effect=fake_generate_text):
        from simulation.narrator import generate_scene
        generate_scene(
            player_action="talk",
            world=world,
            player=pl,
            present_npcs=[guard],
            memories=[],
            action_context={"kind": "talk", "prose_retry": True},
            focal_npc_id="g1",
            hard_constraints="",
        )
    base = token_budget_for_kind("talk")
    assert captured.get("max_tokens", base) <= base
    assert captured.get("max_tokens", 0) >= 400
