"""SceneState — single authoritative scene snapshot."""

from simulation.scene_state import assemble_scene_state, SceneState


def _npc(nid, role="guard"):
    return {"id": nid, "name": nid, "role": role, "status": "alive", "area": "hq"}


def test_assemble_scene_state_cast_persistence():
    npcs = {f"n{i}": _npc(f"n{i}") for i in range(8)}
    for n in npcs.values():
        n["area"] = "hq"
    player = {
        "area": "hq",
        "scene_subplace": {"id": "gate"},
        "scene_focus": "n0",
        "scene_cast": {"area": "hq", "subplace": "gate", "ids": ["n0", "n1", "n2"]},
        "known_npcs": {},
        "scheduled_events": {},
    }
    world = {"day": 1, "hour": 3, "time_of_day": "night", "hour_count": 3}
    state = assemble_scene_state(player, npcs, world, {"kind": "wait"}, tick=1, persist=False)
    assert isinstance(state, SceneState)
    assert len(state.cast) == 3
    assert state.cast_ids == frozenset({"n0", "n1", "n2"})
    assert len(state.area_present) == 8


def test_scene_state_immutable():
    npcs = {"a": _npc("a")}
    player = {"area": "hq", "known_npcs": {}, "scheduled_events": {}}
    world = {"day": 1, "hour": 1, "time_of_day": "day", "hour_count": 1}
    s1 = assemble_scene_state(player, npcs, world, {}, tick=1, persist=False)
    s2 = assemble_scene_state(player, npcs, world, {}, tick=1, persist=False)
    assert s1.cast_ids == s2.cast_ids
