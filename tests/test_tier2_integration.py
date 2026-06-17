"""Tier 2 story integration — beliefs, graph, promises, causality, entropy."""

from simulation.belief_model import (
    infer_propositions,
    top_beliefs,
    update_beliefs_from_rumor,
    upsert_belief,
)
from simulation.story_graph import build_story_graph, story_graph_narrator_block
from simulation.scene_objectives import build_scene_objectives_block
from simulation.narrative_promises import (
    detect_promises_in_scene,
    record_promise,
    resolve_promise,
    try_resolve_from_action,
    unresolved_promises_block,
)
from simulation.narrative_causality import record_causal_link, record_from_beat
from simulation.memory_consolidator import maybe_consolidate_player_memories
from simulation.story_entropy import score_story_entropy, entropy_narrator_block


def test_belief_model_from_rumor():
    npc = {}
    rumor = {"text": "They say the outsider murdered a guard last night", "interpretation": "dangerous"}
    updated = update_beliefs_from_rumor(npc, rumor, tick=1)
    assert "player_is_murderer" in updated
    beliefs = top_beliefs(npc, min_confidence=0.2)
    assert beliefs[0]["proposition"] == "player_is_murderer"


def test_story_graph_links_case_to_suspects():
    player = {
        "active_case": {
            "id": "c1",
            "title": "Dock Murder",
            "victim_id": "v1",
            "suspect_ids": ["s1"],
            "solved": False,
        }
    }
    npcs = {"v1": {"name": "Victim"}, "s1": {"name": "Suspect"}}
    graph = build_story_graph(player, npcs)
    rels = {e["rel"] for e in graph["edges"]}
    assert "victim" in rels
    assert "suspect" in rels


def test_scene_objectives_use_stakes():
    player = {
        "scene_stakes": {
            "dramatic_question": "Who moved the cargo?",
            "lose": "trust",
            "gain": "a lead",
            "purpose": "follow the trail",
        }
    }
    block = build_scene_objectives_block(player, "ask_about", {}, structure_mode="revelation")
    assert "SCENE OBJECTIVES" in block
    assert "Open question: Who moved the cargo?" in block
    assert "a lead" in block


def test_narrative_promises_record_and_resolve():
    player = {}
    rec = record_promise(player, label="strange key", kind="object", source_tick=5)
    assert rec
    assert len(player["narrative_promises"]) == 1
    assert resolve_promise(player, "strange key", tick=10)
    assert player["narrative_promises"][0]["resolved"] is True


def test_detect_promises_in_scene():
    player = {}
    found = detect_promises_in_scene(
        player,
        "She handed you a strange key wrapped in oiled cloth.",
        tick=3,
        kind="search",
        action_ctx={"acquired_item": {"name": "Rusty Ledger"}},
    )
    assert found
    assert len(player["narrative_promises"]) >= 1


def test_causal_link_from_beat():
    player = {"scene_stakes": {"arc_id": "arc1"}}
    ok = record_from_beat(
        player, "accuse", {"action_summary": "accuse the merchant", "skill_check": {"success": True}}, {},
        tick=7,
    )
    assert ok
    assert player["causal_links"][0]["importance"] >= 70


def test_memory_consolidator_dedupes():
    player = {
        "narrative_memories": [
            {"story_meaning": "The outsider pursued answers in the market", "importance": 60},
            {"story_meaning": "The outsider pursued answers in the market district", "importance": 55},
        ],
        "_last_consolidation_tick": 0,
    }
    assert maybe_consolidate_player_memories(player, tick=30)
    assert len(player["narrative_memories"]) == 1


def test_story_entropy_rises_with_open_threads():
    player = {
        "active_case": {"solved": False, "stage": 2, "evidence": []},
        "pending_consequences": [{}, {}, {}],
        "narrative_promises": [{"resolved": False}, {"resolved": False}],
        "journal": [{}] * 130,
    }
    score = score_story_entropy(player, {})
    assert score >= 55


def test_unresolved_promises_block():
    player = {}
    record_promise(player, label="third bell gathering", kind="event")
    block = unresolved_promises_block(player)
    assert "UNRESOLVED SETUPS" in block
    assert "third bell" in block
