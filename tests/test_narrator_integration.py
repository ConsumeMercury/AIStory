"""Integration tests — cast, narrator, and ledger use the same focal id."""

import pytest

from simulation.generation_guardrails import build_hard_constraints_block, audit_capture_anomalies
from simulation.scene_cast import select_scene_cast
from simulation.scene_coherence import build_conversation_ledger
from simulation.target_resolution import find_npc_by_name_in_text


def _npc(nid, role="soldier", name="Bob", gender="male"):
    return {"id": nid, "name": name, "role": role, "gender": gender, "status": "alive"}


def test_select_scene_cast_returns_focal_id():
    soldier = _npc("s1", role="soldier", name="Solia")
    priest = _npc("p1", role="priest", name="Father Hale")
    player = {"scene_focus": "s1", "known_npcs": {}}
    ctx = {"kind": "talk", "target_id": "p1"}
    focus, _note, focal_id = select_scene_cast([soldier, priest], player, ctx)
    assert focus[0]["id"] == "p1"
    assert focal_id == "p1"


def test_generate_scene_uses_explicit_focal_id(monkeypatch):
    from simulation.narrator import generate_scene

    captured = {}

    def fake_generate_text(prompt, **kwargs):
        captured["prompt"] = prompt
        return "scene text"

    monkeypatch.setattr("simulation.narrator.generate_text", fake_generate_text)

    npc = _npc("p1", role="priest", name="Father Hale")
    player = {"journal": [], "known_npcs": {}, "area": "city:temple", "location": "city"}
    world = {"world_name": "Test", "day": 1, "time_of_day": "night", "season": "winter", "weather": "Clear"}
    hard = build_hard_constraints_block("p1", npc, "Temple Row — the heavy door", {})

    generate_scene(
        player_action="Talk to the priest",
        world=world,
        player=player,
        present_npcs=[npc],
        memories=[],
        action_context={"kind": "talk"},
        focal_npc_id="p1",
        scene_place="Temple Row — the heavy door",
        hard_constraints=hard,
    )

    assert "FOCAL PERSON THIS BEAT: id=p1" in captured["prompt"]
    assert "LOCATION LOCK: Temple Row — the heavy door" in captured["prompt"]
    assert "HARD CONSTRAINTS" in captured["prompt"]
    assert captured["prompt"].strip().endswith("DO NOT REPEAT.")


def test_ledger_uses_same_focal_id_as_cast():
    player = {
        "journal": [{
            "focus_npc": "p1",
            "action": "ask about trouble",
            "excerpt": "He deflected.",
        }],
        "known_npcs": {"p1": {"name_known": True}},
    }
    ledger = build_conversation_ledger(player, player["journal"], "p1", {"kind": "talk"})
    assert "Father" in ledger or "CONVERSATION LEDGER" in ledger


def test_ambiguous_name_hope_not_matched():
    npcs = {"h1": _npc("h1", name="Hope", role="merchant")}
    player = {"known_npcs": {"h1": {"name_known": True}}, "scene_focus": None}
    hit = find_npc_by_name_in_text("I hope so", npcs, player)
    assert hit is None


def test_dynamic_role_acolyte_in_present():
    from simulation.target_resolution import action_mentions_role_or_descriptor

    present = [_npc("a1", role="acolyte", name="Tern")]
    assert action_mentions_role_or_descriptor("talk to the acolyte", present=present)


def test_audit_detects_focal_ledger_mismatch():
    warnings = audit_capture_anomalies(
        {
            "focal_npc_id": "a",
            "ledger_focal_id": "b",
            "focus_ids": ["a"],
        },
        {},
        {},
    )
    assert any("ledger" in w for w in warnings)
