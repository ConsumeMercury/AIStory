"""Regressions from live playtest — focus stickiness, ask_name speech, streaming, time."""

from simulation.action_interpreter import interpret_action, speech_for_ask_name, speech_for_ask_about, extract_player_speech
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


def test_ask_about_reconstructs_why_question():
    action = "Ask Tomas the herbalist why he warned me about the shout"
    speech = speech_for_ask_about(action)
    assert speech
    assert "warn" in speech.lower()
    assert "shout" in speech.lower()
    assert "tomas" not in speech.lower()
    assert "?" in speech
    ctx = interpret_action(action, {"scene_focus": "h1", "known_npcs": {}}, [_npc("h1", role="herbalist")], {})
    assert ctx["kind"] == "ask_about"
    assert ctx.get("player_speech")
    assert "tomas" not in ctx["player_speech"].lower()


def test_ask_about_reconstructs_what_question():
    action = "Ask the herbalist what she meant about the garden gates"
    speech = speech_for_ask_about(action)
    assert speech
    assert "garden gates" in speech.lower()
    assert "herbalist" not in speech.lower()
    ctx = interpret_action(action, {"scene_focus": "h1", "known_npcs": {}}, [_npc("h1", role="herbalist")], {})
    assert ctx["kind"] == "ask_about"
    assert ctx.get("player_speech")
    assert "herbalist what" not in ctx["player_speech"].lower()


def test_travel_failed_inherits_prior_focus_in_cast():
    from simulation.scene_cast import select_scene_cast

    herbalist = _npc("h1", role="herbalist", name="", gender="female")
    guard = _npc("g1", role="guard", name="Holt", gender="male")
    player = {
        "scene_focus": "h1",
        "journal": [{"focus_npc": "h1", "kind": "talk"}],
        "known_npcs": {},
    }
    ctx = {"kind": "travel", "travel_failed": True}
    focus, note, fid = select_scene_cast([herbalist, guard], player, ctx)
    assert len(focus) == 1
    assert focus[0]["id"] == "h1"
    assert fid == "h1"
    assert "Same people" in note


def test_mangled_ask_without_prefix_reconstructs_speech():
    action = "The herbalist what she meant about the garden gates?"
    speech = speech_for_ask_about(action)
    assert speech
    assert "garden gates" in speech.lower()
    assert "herbalist what" not in speech.lower()
    ctx = interpret_action(action, {"scene_focus": "h1", "known_npcs": {}}, [_npc("h1", role="herbalist")], {})
    assert ctx["kind"] == "ask_about"
    assert ctx.get("player_speech")
    assert "herbalist what" not in ctx["player_speech"].lower()


def test_travel_failed_inherits_prior_present_set():
    from simulation.scene_cast import select_scene_cast

    herbalist = _npc("h1", role="herbalist", name="", gender="female")
    guard = _npc("g1", role="guard", name="Holt", gender="male")
    local = _npc("l1", role="merchant", name="", gender="male")
    player = {
        "area": "city:high_quarter",
        "scene_focus": "h1",
        "journal": [{
            "focus_npc": "h1",
            "area": "city:high_quarter",
            "present_ids": ["h1", "g1", "l1"],
            "focus_cast": ["h1"],
        }],
        "known_npcs": {},
    }
    ctx = {"kind": "travel", "travel_failed": True}
    focus, note, fid = select_scene_cast([herbalist, guard, local], player, ctx)
    assert len(focus) == 3
    assert {n["id"] for n in focus} == {"h1", "g1", "l1"}
    assert fid == "h1"
    assert "Same people" in note


def test_ask_when_reconstructs_shipment_question():
    action = "Ask the man when the next shipment comes through"
    speech = speech_for_ask_about(action)
    assert speech == "When does the next shipment come through?"
    ctx = interpret_action(action, {"scene_focus": "m1", "known_npcs": {}}, [_npc("m1", role="merchant")], {})
    assert ctx["kind"] == "ask_about"
    assert ctx["player_speech"] == speech


def test_compound_tell_and_ask_produces_no_speech():
    action = (
        "Tell him I'll wait here until the morning crews arrive, "
        "and ask what time they start"
    )
    speech = extract_player_speech(action, {}, kind="talk")
    assert speech is None
    ctx = interpret_action(action, {"scene_focus": "m1", "known_npcs": {}}, [_npc("m1")], {})
    assert ctx.get("player_speech") is None


def test_mangled_when_fragment_reconstructs_not_echoes():
    action = "When the next shipment comes through?"
    speech = speech_for_ask_about(action)
    assert speech == "When does the next shipment come through?"
    assert "shipment comes through?" != speech


def test_misname_directive_flags_wrong_name():
    from simulation.generation_guardrails import build_misname_directive

    herbalist = _npc("h1", role="herbalist", name="", gender="female")
    directive = build_misname_directive(
        "Ask Tomas the herbalist why he warned me",
        herbalist,
        {"h1": herbalist, "t1": _npc("t1", name="Tomas", role="merchant")},
        "h1",
    )
    assert directive
    assert "Tomas" in directive
    assert "NOT Tomas" in directive or "NOT" in directive


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
