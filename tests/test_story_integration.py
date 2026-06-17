"""Story registry, importance scoring, narrative memory, and directive validation."""

from simulation.directive_validator import find_directive_conflicts
from simulation.event_importance import infer_story_meaning, score_event_importance
from simulation.narrative_memory import (
    add_narrative_memory,
    narrative_memory_block,
    record_beat_narrative_memory,
)
from simulation.story_manager import (
    build_story_manager_block,
    get_active_arcs,
    sync_starting_pipeline_from_area,
    weighted_npc_sample,
)


def test_sync_starting_pipeline_from_area():
    player = {
        "starting_pipeline": {
            "area_id": "ashmoor:market",
            "stage": 0,
            "current": "old beat",
            "tension": 10,
        }
    }
    areas = {
        "ashmoor:market": {
            "storyline": {
                "stage": 1,
                "current": "new beat",
                "tension": 35,
                "hook": "something wrong",
                "key_npc_ids": ["npc_a"],
            }
        }
    }
    assert sync_starting_pipeline_from_area(player, "ashmoor:market", areas) is True
    pipe = player["starting_pipeline"]
    assert pipe["stage"] == 1
    assert pipe["current"] == "new beat"
    assert pipe["tension"] == 35
    assert pipe["key_npc_ids"] == ["npc_a"]


def test_get_active_arcs_merges_case_and_pipeline():
    player = {
        "area": "ashmoor:market",
        "starting_pipeline": {
            "area_id": "ashmoor:market",
            "title": "Market trouble",
            "stage": 0,
            "current": "whispers",
            "tension": 20,
        },
        "active_case": {
            "id": "case_1",
            "title": "Murder in the stalls",
            "stage": 1,
            "stages": ["learn", "suspect", "proof", "accuse"],
            "victim_id": "v1",
            "suspect_ids": ["s1"],
            "evidence": [],
            "solved": False,
            "summary": "A body was found",
        },
    }
    arcs = get_active_arcs(player, {})
    assert len(arcs) >= 2
    assert arcs[0]["kind"] == "investigation"
    assert any(a["kind"] == "district" for a in arcs)


def test_weighted_npc_sample_prefers_story_cast():
    weights = {"hero": 20.0, "bystander": 1.0, "extra": 1.0}
    picks = []
    for _ in range(30):
        sample = weighted_npc_sample(list(weights), weights, 1)
        picks.extend(sample)
    assert picks.count("hero") >= picks.count("bystander")


def test_build_story_manager_block_includes_stakes():
    player = {
        "starting_pipeline": {
            "area_id": "ashmoor:market",
            "title": "Smugglers",
            "stage": 0,
            "current": "watch the docks",
            "hook": "contraband",
            "tension": 40,
        },
        "scene_stakes": {
            "dramatic_question": "Who moves the cargo?",
            "lose": "trust",
            "gain": "a lead",
        },
    }
    areas = {"ashmoor:market": {"name": "Market", "storyline": {"stage": 0, "current": "watch the docks"}}}
    block = build_story_manager_block(player, {}, areas=areas, kind="talk", focal_npc_id="npc_a")
    assert "ACTIVE STORY" in block
    assert "Smugglers" in block
    assert "Who moves the cargo?" in block


def test_score_event_importance_ranks_combat_high():
    combat = score_event_importance("combat", "attack", target="npc1")
    ambient = score_event_importance("npc_action", "wait")
    assert combat > ambient
    assert combat >= 85


def test_infer_story_meaning_for_investigation():
    meaning = infer_story_meaning("player_action", "ask about the murder", kind="ask_about")
    assert "pursued answers" in meaning


def test_record_beat_narrative_memory_on_accuse():
    player = {"scene_stakes": {"arc_id": "case_1"}}
    ok = record_beat_narrative_memory(
        player,
        kind="accuse",
        action="accuse the merchant",
        action_ctx={"target_id": "m1"},
        tick=5,
    )
    assert ok is True
    assert player["narrative_memories"][0]["story_meaning"]
    assert player["narrative_memories"][0]["importance"] >= 70


def test_narrative_memory_block_dedupes_recent():
    player = {}
    add_narrative_memory(player, story_meaning="Same beat", importance=60)
    add_narrative_memory(player, story_meaning="Same beat", importance=60)
    assert len(player["narrative_memories"]) == 1
    block = narrative_memory_block(player)
    assert "NARRATIVE MEMORY" in block
    assert "Same beat" in block


def test_find_directive_conflicts_detects_opposing_rules():
    prompt = (
        "Continue the same conversation mid-exchange.\n"
        "Write a fresh chapter with weather opener on first arrival."
    )
    issues = find_directive_conflicts(prompt)
    assert issues
    assert "Conflicting directives" in issues[0]


def test_assemble_scene_prompt_includes_story_manager(monkeypatch):
    monkeypatch.setenv("AISTORY_SKIP_MEMORY_BUDGET", "1")
    from simulation.narrator import assemble_scene_prompt

    player = {
        "starting_pipeline": {
            "area_id": "ashmoor:market",
            "title": "Hidden ledgers",
            "stage": 0,
            "current": "follow the trail",
            "hook": "missing coin",
            "tension": 25,
        },
        "journal": [],
        "reputation_profile": {"violent": 80, "merciful": 20, "honorable": 30, "greedy": 10, "suspicious": 40, "heroic": 15},
    }
    world = {"world_name": "Test", "day": 1, "time_of_day": "morning", "season": "spring", "weather": "clear"}
    prompt, _budget, _fid, _debug = assemble_scene_prompt(
        "look around",
        world,
        player,
        [],
        [],
        action_context={"kind": "explore"},
        tick=1,
    )
    assert "ACTIVE STORY" in prompt
    assert "Hidden ledgers" in prompt
    assert "REPUTATION" in prompt
