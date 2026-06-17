"""Narrator prompt gating, memory retrieval, and directive arbitration."""

from simulation.directive_validator import arbitrate_prompt, find_directive_conflicts
from simulation.memory_retrieval import get_relevant_memories
from simulation.narrator_blocks import join_sections


def test_arbitrate_prompt_adds_header():
    prompt = "HARD CONSTRAINTS\nContinue conversation"
    conflicts = find_directive_conflicts(
        prompt + "\nWrite a fresh chapter with weather opener on first arrival."
    )
    out = arbitrate_prompt(prompt, conflicts)
    assert out.startswith("ARBITRATION")
    assert "HARD CONSTRAINTS" in out


def test_standard_profile_omits_tier_blocks_for_ask_name():
    sections = {
        "craft_core": "VOICE:",
        "story_graph": "STORY GRAPH",
        "entropy": "ENTROPY",
        "closing": "Write the scene now.",
    }
    prompt = join_sections(
        sections,
        kind="ask_name",
        has_focal=True,
        has_journal=True,
        profile="standard",
    )
    assert "VOICE:" in prompt
    assert "STORY GRAPH" not in prompt
    assert "ENTROPY" not in prompt


def test_full_profile_includes_tier_blocks():
    sections = {"story_graph": "STORY GRAPH", "closing": "done"}
    prompt = join_sections(
        sections,
        kind="ask_name",
        has_focal=False,
        has_journal=False,
        profile="full",
    )
    assert "STORY GRAPH" in prompt


def test_focal_memory_boost_ranks_target_event():
    events = [
        {"type": "player_action", "actor": "player", "action": "talk about seals", "target": "npc_b", "id": "e2"},
        {"type": "player_action", "actor": "player", "action": "talk about seals", "target": "npc_a", "id": "e1"},
    ]
    hits = get_relevant_memories(
        events,
        "talk about seals",
        limit=2,
        focal_npc_id="npc_a",
        npcs={"npc_a": {"name": "Ada", "role": "merchant"}},
        kind="talk",
    )
    assert hits[0].get("target") == "npc_a"


def test_semantic_disabled_for_observe_kind():
    from simulation.memory_retrieval import semantic_retrieval_enabled_for_kind
    assert semantic_retrieval_enabled_for_kind("observe") is False
