"""Scene cast persistence — bounded population survives across beats."""

from simulation.scene_population import (
    bootstrap_scene_cast,
    resolve_scene_present,
    persist_scene_cast,
    should_reset_scene_cast,
    build_clarification_identity_directive,
)


def _npc(nid, role="guard", name=""):
    return {
        "id": nid,
        "name": name or nid,
        "role": role,
        "status": "alive",
        "age": 30,
        "physique": {"presentation": 50},
    }


def test_cast_persists_across_wait():
    guard = _npc("g1", role="guard", name="Kasah Stonehand")
    scholar = _npc("s1", role="scholar", name="Razar al-Zahir")
    merchant = _npc("m1", role="merchant", name="Lusah al-Zahir")
    area = [
        guard,
        scholar,
        merchant,
        _npc("x1", role="scribe"),
        _npc("x2", role="scribe"),
        _npc("x3", role="merchant"),
        _npc("x4", role="guard"),
    ]
    npcs = {n["id"]: n for n in area}
    player = {
        "area": "high_quarter",
        "scene_subplace": {"id": "lower_gate"},
        "scene_focus": "g1",
        "scene_cast": {
            "area": "high_quarter",
            "subplace": "lower_gate",
            "ids": ["g1", "s1", "m1"],
        },
        "known_npcs": {"g1": {"name_known": True, "seen_before": True}},
    }
    ctx = {"kind": "wait", "action_summary": "wait for the night crews"}
    present = resolve_scene_present(area, player, ctx, npcs)
    ids = {n["id"] for n in present}
    assert ids == {"g1", "s1", "m1"}
    focus, _, fid = __import__(
        "simulation.scene_cast", fromlist=["select_scene_cast"]
    ).select_scene_cast(present, player, ctx)
    assert fid == "g1"
    assert focus[0]["id"] == "g1"


def test_relocate_resets_cast():
    old_guard = _npc("g1", role="guard")
    new_scribe = _npc("c1", role="scribe", name="Corus Maric")
    area = [old_guard, new_scribe, _npc("z1", role="merchant")]
    npcs = {n["id"]: n for n in area}
    player = {
        "area": "high_quarter",
        "scene_subplace": {"id": "lower_gate"},
        "scene_cast": {
            "area": "high_quarter",
            "subplace": "merchant_row",
            "ids": ["g1"],
        },
        "known_npcs": {},
    }
    ctx = {"kind": "approach", "relocated": True, "target_id": "c1"}
    present = resolve_scene_present(area, player, ctx, npcs)
    assert any(n["id"] == "c1" for n in present)
    assert len(present) <= 6
    assert len(present) > 1


def test_subplace_mismatch_resets():
    area = [_npc("a1"), _npc("a2"), _npc("a3")]
    npcs = {n["id"]: n for n in area}
    player = {
        "area": "high_quarter",
        "scene_subplace": {"id": "lower_gate"},
        "scene_cast": {
            "area": "high_quarter",
            "subplace": "merchant_row",
            "ids": ["a1"],
        },
        "known_npcs": {},
    }
    assert should_reset_scene_cast({}, player)
    present = resolve_scene_present(area, player, {}, npcs)
    assert len(present) >= 1


def test_journal_fallback_when_scene_cast_missing():
    guard = _npc("g1", role="guard")
    scholar = _npc("s1", role="scholar")
    area = [guard, scholar]
    npcs = {n["id"]: n for n in area}
    player = {
        "area": "high_quarter",
        "scene_subplace": {"id": "lower_gate"},
        "scene_focus": "g1",
        "journal": [{
            "area": "high_quarter",
            "subplace": "lower_gate",
            "scene_cast_ids": ["g1", "s1"],
        }],
        "known_npcs": {},
    }
    present = resolve_scene_present(area, player, {"kind": "talk"}, npcs)
    assert {n["id"] for n in present} == {"g1", "s1"}


def test_clarification_directive_binds_identity():
    npc = _npc("g1", role="guard", name="Kasah Stonehand")
    text = build_clarification_identity_directive(npc)
    assert "Kasah Stonehand" in text
    assert "g1" in text
    assert "YOU ARE this person" in text
    assert "third person" in text


def test_persist_scene_cast_caps_size():
    area = [_npc(f"n{i}") for i in range(10)]
    npcs = {n["id"]: n for n in area}
    player = {"area": "hq", "scene_subplace": {"id": "gate"}, "known_npcs": {}}
    ctx = {}
    boot = bootstrap_scene_cast(area, player, ctx, npcs)
    persist_scene_cast(player, boot, ctx)
    assert len(player["scene_cast"]["ids"]) <= 6
