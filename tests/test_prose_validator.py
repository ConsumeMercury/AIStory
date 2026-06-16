import logging

from simulation.prose_validator import (
    analyze_prose,
    log_scene_prose_issues,
    place_drift,
    wrong_speaker_dialogue,
)


def _npc(nid, **kw):
    base = {"id": nid, "name": "Father Hale", "role": "priest", "gender": "male", "status": "alive"}
    base.update(kw)
    return base


def test_place_drift_flags_wrong_destination():
    issue = place_drift(
        "You step into the market square and the stalls rise around you.",
        "Temple Row — the heavy door",
    )
    assert issue is not None
    assert "market" in issue


def test_place_drift_allows_subplace_language():
    assert place_drift("You move to the door.", "Temple Row — the heavy door") is None


def test_wrong_speaker_flags_absent_npc():
    npcs = {
        "p1": _npc("p1"),
        "s1": _npc("s1", name="Solia", role="soldier"),
    }
    issue = wrong_speaker_dialogue(
        '"Wait," Solia said.',
        focal_npc_id="p1",
        present_npcs=[npcs["p1"]],
        npcs=npcs,
    )
    assert issue is not None
    assert "Solia" in issue


def test_analyze_prose_includes_place_and_speaker_checks():
    npcs = {"p1": _npc("p1")}
    player = {"scene_focus": "p1", "known_npcs": {"p1": {"name_known": True}}}
    ctx = {
        "kind": "talk",
        "target_id": "p1",
        "scene_place": "Temple Row",
        "present_npcs": [npcs["p1"]],
    }
    text = (
        "You enter the harbor district. The priest watches you. "
        '"Not today," he said, and turned away.'
    )
    issues = analyze_prose(text, ctx, player, npcs)
    assert any("harbor" in i or "LOCATION LOCK" in i or "moves toward" in i for i in issues)


def test_log_scene_prose_issues_warns_but_does_not_raise(caplog):
    npcs = {"p1": _npc("p1")}
    player = {"scene_focus": "p1", "known_npcs": {"p1": {"name_known": True}}}
    ctx = {"kind": "talk", "target_id": "p1", "scene_place": "Temple Row", "present_npcs": [npcs["p1"]]}
    prose = (
        "You wander the empty square alone. The wind moves through the colonnade. "
        "Nothing answers. The stones keep their silence."
    )
    with caplog.at_level(logging.WARNING, logger="simulation.prose_validator"):
        issues = log_scene_prose_issues(
            prose,
            player=player,
            npcs=npcs,
            action_ctx=ctx,
            focal_npc_id="p1",
            scene_place="Temple Row",
            present_npcs=[npcs["p1"]],
        )
    assert issues
    assert any("prose validation" in r.message for r in caplog.records)


def test_prose_issues_recorded_in_turn_trace(monkeypatch):
    from unittest.mock import MagicMock, patch

    from simulation.story_loop import process_player_action
    from simulation.turn_trace import get_last_turn

    mock_narr = MagicMock()
    mock_narr.generate_scene.return_value = (
        "You step into the harbor district alone. The wind moves through empty stalls. "
        "Nothing answers. The stones keep their silence."
    )
    monkeypatch.setattr(
        "simulation.story_loop.try_meta_command",
        lambda action: None,
    )
    with patch("simulation.story_loop.get_narrator", return_value=mock_narr):
        with patch("simulation.story_loop.simulation_runner.get_current_tick", return_value=1):
            process_player_action("talk to priest")

    trace = get_last_turn()
    assert trace.get("prose_issues")
