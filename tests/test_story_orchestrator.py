"""Story orchestrator — beat planning layer tests."""

from simulation.story_orchestrator import prepare_beat, build_memory_query, build_scene_plan, finalize_beat
from simulation.memory_index import retrieve_memories_for_beat


def test_prepare_beat_writes_plan_on_action_ctx():
    player = {
        "area": "stormbridge:docks",
        "location": "stormbridge",
        "starting_pipeline": {
            "area_id": "stormbridge:docks",
            "title": "Smuggler's Toll",
            "stage": 0,
            "stages": ["hook", "crisis"],
            "current": "watch the crates",
            "key_npc_ids": ["npc_a"],
        },
    }
    npcs = {"npc_a": {"name": "Bessa", "status": "alive", "area": "stormbridge:docks"}}
    areas = {"stormbridge:docks": {"storyline": {"stages": ["hook"], "stage": 0, "tension": 20}}}
    ctx = {"kind": "ask_about", "target_id": "npc_a", "action_summary": "ask about the crates"}
    plan = prepare_beat(player, kind="ask_about", action_ctx=ctx, npcs=npcs, areas=areas, tick=5)
    assert ctx.get("beat_plan")
    assert plan.get("memory_query")
    assert "Bessa" in plan["memory_query"] or "crates" in plan["memory_query"]
    assert player.get("scene_stakes", {}).get("dramatic_question")
    assert ctx.get("story_orchestrator", {}).get("arc_id")
    assert player.get("sim_priorities", {}).get("priority_npc_ids")
    assert plan.get("sim_priorities")


def test_memory_index_uses_beat_plan_query():
    player = {"narrative_memories": []}
    ctx = {
        "beat_plan": {
            "memory_query": "accuse dockmaster forgery investigation",
            "dramatic_question": "Who forged the seal?",
        },
    }
    events = [
        {
            "type": "player_interaction",
            "actor": "player",
            "action": "accuse the dockmaster of forgery",
            "importance": 80,
        },
    ]
    hits = retrieve_memories_for_beat(
        events, "hello", limit=5, player=player, action_ctx=ctx,
    )
    assert hits
    assert "forgery" in (hits[0].get("action") or "").lower()


def test_build_scene_plan_includes_must_surface():
    player = {
        "scene_stakes": {"dramatic_question": "Who moved the crates?"},
        "narrative_promises": [{"label": "strange key", "resolved": False}],
        "starting_pipeline": {"area_id": "x", "title": "Plot", "stage": 0, "stages": ["h"]},
    }
    arc = {"arc_id": "a1", "title": "Plot", "next_beat": "confront the foreman", "stage": 0}
    plan = build_scene_plan(player, kind="talk", action_ctx={}, arc=arc)
    assert plan.get("must_surface")
    assert any("crates" in s or "foreman" in s or "key" in s for s in plan["must_surface"])


def test_finalize_beat_propagates_causal_pressure():
    player = {
        "area": "stormbridge:docks",
        "causal_links": [{
            "summary": "Because the outsider accusation: accused guard → trust fractures.",
            "importance": 72,
        }],
    }
    areas = {"stormbridge:docks": {"storyline": {"tension": 20, "stages": ["a"], "stage": 0}}}
    npcs = {"g1": {"status": "alive", "beliefs": []}}
    ctx = {"target_id": "g1", "kind": "accuse"}
    changed = finalize_beat(
        player, kind="accuse", action_ctx=ctx, npcs=npcs, areas=areas, tick=10,
    )
    assert changed
    assert areas["stormbridge:docks"]["storyline"]["tension"] >= 21
    assert npcs["g1"].get("beliefs")
