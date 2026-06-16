"""Regressions from live playtest — focus stickiness, ask_name speech, streaming, time."""

from simulation.action_interpreter import interpret_action, speech_for_ask_name
from simulation.gemini_client import _append_stream_piece
from simulation.target_resolution import resolve_action_target
from simulation.world_clock import ACTION_TIME_HOURS


def _npc(nid, role="priest", gender="female", name="Gwen Reed"):
    return {
        "id": nid,
        "name": name,
        "role": role,
        "gender": gender,
        "status": "alive",
        "physique": {"build": "gaunt"},
    }


def test_sticky_focus_keeps_known_priest_on_role_address():
    gwen = _npc("gwen", name="Gwen Reed")
    other = _npc("other", name="Drear Valcorin")
    player = {
        "scene_focus": "gwen",
        "known_npcs": {"gwen": {"name_known": True, "seen_before": True}},
    }
    target = resolve_action_target(
        "Ask the priest for her name",
        player,
        [gwen, other],
        kind="ask_name",
    )
    assert target["id"] == "gwen"


def test_talk_to_priest_still_overrides_non_priest_focus():
    soldier = _npc("soldier", role="soldier", name="Solia", gender="male")
    priest = _npc("priest", role="priest", name="Father Hale")
    player = {
        "scene_focus": "soldier",
        "known_npcs": {"soldier": {"name_known": True}},
    }
    target = resolve_action_target(
        "Talk to the priest",
        player,
        [soldier, priest],
        kind="talk",
    )
    assert target["id"] == "priest"


def test_ask_priest_for_name_uses_canonical_question():
    assert speech_for_ask_name('Ask the priest for her name') == "What is your name?"
    assert speech_for_ask_name('ask "what is your name?"') == "what is your name?"


def test_ask_name_interpret_does_not_quote_meta_phrase():
    gwen = _npc("gwen")
    player = {"scene_focus": "gwen", "known_npcs": {}}
    ctx = interpret_action(
        "Ask the priest for her name",
        player,
        [gwen],
        {},
        npcs={"gwen": gwen},
    )
    assert ctx["kind"] == "ask_name"
    assert ctx["player_speech"] == "What is your name?"
    assert "priest for her name" not in ctx["player_speech"].lower()


def test_stream_raw_join_preserves_model_spacing():
    assert "".join(["trest", "le"]) == "trestle"
    assert "".join(["from", " her"]) == "from her"
    assert "".join(["from", "her"]) == "fromher"


def test_stream_piece_merge_legacy_heuristic():
    parts = ["from"]
    out = _append_stream_piece(parts, "her")
    assert out == " her"
    assert "".join(parts) == "from her"


def test_dialogue_actions_cost_zero_hours():
    for kind in ("talk", "ask_name", "withdraw", "ask_about", "personal_talk"):
        assert ACTION_TIME_HOURS.get(kind) == 0


def test_focus_role_switch_issue_detects_swap():
    from simulation.prose_validator import focus_role_switch_issue

    npcs = {
        "gwen": _npc("gwen"),
        "other": _npc("other"),
    }
    player = {"journal": [{"kind": "talk", "focus_npc": "gwen", "action": "talk to the priest"}]}
    issue = focus_role_switch_issue(
        player,
        {
            "kind": "ask_name",
            "target_id": "other",
            "action_summary": "Ask the priest for her name",
            "present_npcs": [npcs["gwen"], npcs["other"]],
        },
        player["journal"],
        npcs,
    )
    assert issue is not None
    assert "Gwen Reed" in issue
