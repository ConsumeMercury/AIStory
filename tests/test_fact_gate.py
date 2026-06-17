"""Fact gate — combined prose + structured fact validation."""

from simulation.fact_gate import validate_turn_output
from simulation.scene_state import SceneState


def test_validate_turn_output_death_tag():
    scene = SceneState(
        tick=1, day=1, hour=1, time_of_day="day",
        area_id="hq", subplace_id=None, place_label="Gate",
        area_present=(), cast=(), cast_ids=frozenset(),
        scene_focus=None, pending_events=(),
    )
    npcs = {"v1": {"id": "v1", "name": "Victim", "status": "alive", "role": "merchant"}}
    text = "The body stills. [FACT: death | v1]"
    issues, facts, prose_issues, fact_issues = validate_turn_output(
        text,
        player={},
        npcs=npcs,
        action_ctx={"kind": "observe"},
        focal_npc_id=None,
        scene_place="Gate",
        present_npcs=[],
        scene_state=scene,
    )
    assert fact_issues
    assert facts["death"] == ["v1"]
