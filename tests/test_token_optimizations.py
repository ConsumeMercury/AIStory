"""Safe token/latency optimizations — block gating, classifier fast-path, memory caps."""

from simulation.action_classifier import needs_llm_classifier
from simulation.memory_index import memory_limit_for_kind, retrieve_memories_for_beat
from simulation.narrator_blocks import list_included_blocks, should_include_block
from simulation.scene_state import SceneState


def _scene(*, subplace_id="gate", cast_ids=("g1",)):
    cast = tuple({"id": i, "name": i, "role": "guard", "status": "alive"} for i in cast_ids)
    return SceneState(
        tick=1, day=1, hour=1, time_of_day="day",
        area_id="hq", subplace_id=subplace_id, place_label="High Quarter — gate",
        area_present=cast, cast=cast, cast_ids=frozenset(cast_ids),
        scene_focus=cast_ids[0] if cast_ids else None, pending_events=(),
    )


def test_approach_omits_heavy_blocks_without_focal():
    included = list_included_blocks(
        "approach", has_focal=False, has_journal=True, profile="standard",
    )
    assert "immersion" not in included
    assert "story_graph" not in included
    assert "causality" not in included


def test_continuation_without_focal_omits_story_layers():
    included = list_included_blocks(
        "explore", has_focal=False, has_journal=True, profile="standard",
        structure_hint="continuation",
    )
    assert "story_manager" not in included
    assert "causality" not in included
    assert "promises" not in included


def test_continuation_with_focal_keeps_story_layers():
    included = list_included_blocks(
        "explore", has_focal=True, has_journal=True, profile="standard",
        structure_hint="continuation",
    )
    assert "story_manager" in included
    assert "causality" in included


def test_should_include_block_immersion_false_for_approach():
    assert not should_include_block(
        "immersion", "approach", has_focal=False, has_journal=True,
    )


def test_needs_classifier_false_for_approach_with_subplace():
    scene = _scene(subplace_id="alcove")
    regex_ctx = {"kind": "approach", "target_id": None}
    assert not needs_llm_classifier("approach the alcove", regex_ctx, scene)


def test_needs_classifier_false_for_travel_with_subplace():
    scene = _scene(subplace_id="market_stall")
    regex_ctx = {"kind": "travel", "target_id": None}
    assert not needs_llm_classifier("go to the stall", regex_ctx, scene)


def test_memory_limit_by_kind():
    from simulation.memory_immersion import surface_memory_limit
    assert surface_memory_limit("talk") == 2
    assert surface_memory_limit("investigate") == 3
    assert memory_limit_for_kind("talk") >= surface_memory_limit("talk")


def test_retrieve_memories_respects_limit():
    events = [
        {
            "type": "player_action", "actor": "player",
            "action": f"event number {i}", "id": f"e{i}",
        }
        for i in range(20)
    ]
    hits = retrieve_memories_for_beat(
        events, "event", limit=memory_limit_for_kind("talk"), player={"journal": [], "last_tick": 50},
        kind="talk",
    )
    assert len(hits) <= 2
