"""Importance router and memory index tests."""

from simulation.importance_router import score_npc, score_rumor, rank_rumors, should_retain_memory
from simulation.memory_index import retrieve_memories_for_beat
from simulation.belief_model import upsert_belief, GROUNDING_FROM_SOURCE
from simulation.story_manager import maybe_advance_arc_stage, beat_obligation_directive
from simulation.narrative_trace import narrative_issues_for_regen


def test_score_npc_boosts_story_cast():
    player = {"area": "stormbridge:docks", "location": "stormbridge", "scene_focus": "hero1"}
    arc = {"key_npc_ids": ["hero1"]}
    npc = {"id": "hero1", "status": "alive", "area": "stormbridge:docks"}
    w = score_npc(npc, player=player, arc=arc)
    assert w > 50


def test_narrative_regen_filters_by_mode(monkeypatch):
    monkeypatch.setenv("AISTORY_NARRATIVE_REGEN", "soft")
    issues = [
        "social beat lacks dramatic_question in scene_stakes",
        "continuation beat may ignore open narrative promises",
    ]
    gated = narrative_issues_for_regen(issues)
    assert any("dramatic_question" in g for g in gated)
    assert not any("promises" in g for g in gated)


def test_belief_grounding_merge():
    npc = {}
    upsert_belief(npc, "player_is_thief", 0.2, source="rumor")
    assert npc["beliefs"][0]["grounding"] == "rumored"
    upsert_belief(npc, "player_is_thief", 0.2, source="witnessed")
    assert npc["beliefs"][0]["grounding"] == "witnessed"


def test_memory_index_merges_narrative_layer():
    player = {
        "narrative_memories": [
            {"story_meaning": "The outsider accused the dockmaster of forgery", "importance": 70},
        ],
        "journal": [],
    }
    events = [
        {"type": "player_interaction", "actor": "player", "action": "accuse dockmaster", "importance": 80},
    ]
    hits = retrieve_memories_for_beat(
        events, "accuse dockmaster", limit=5, player=player, area="stormbridge:docks",
    )
    kinds = {h.get("type") for h in hits}
    assert "narrative_memory" in kinds or "player_interaction" in kinds


def test_arc_stage_advances_on_investigation_beats():
    player = {
        "active_case": {
            "id": "c1",
            "title": "Case",
            "stage": 0,
            "stages": ["a", "b", "c"],
            "evidence": [],
        },
        "area": "stormbridge:docks",
        "starting_pipeline": {
            "area_id": "stormbridge:docks",
            "title": "Plot",
            "stage": 0,
            "stages": ["hook"],
        },
    }
    areas = {
        "stormbridge:docks": {
            "storyline": {"stages": ["s1", "s2"], "stage": 0, "tension": 10},
        },
    }
    for i in range(3):
        maybe_advance_arc_stage(
            player,
            kind="investigate",
            action_ctx={"skill_check": {"success": True}},
            areas=areas,
            npcs={},
        )
    assert player["active_case"]["stage"] >= 1


def test_beat_obligation_includes_dramatic_question():
    player = {
        "scene_stakes": {"dramatic_question": "Who moved the crates?"},
        "starting_pipeline": {"area_id": "x", "title": "T", "stage": 0, "stages": ["h"]},
    }
    text = beat_obligation_directive(player, "talk", {}, npcs={}, areas={})
    assert "Who moved the crates" in text
