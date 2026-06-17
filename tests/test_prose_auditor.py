"""Prose auditor + deterministic confirm + regen governor."""

import os

import pytest

from simulation.auditor_confirm import confirm_nominations
from simulation.prose_auditor import run_prose_audit, should_audit_prose
from simulation.regen_governor import apply_regen_governor, dedupe_issues, issues_warrant_regen
from simulation.scene_state import SceneState
from simulation.fact_gate import validate_turn_output


def _scene(cast_ids):
    cast = tuple({"id": i, "name": i, "role": "guard", "status": "alive"} for i in cast_ids)
    return SceneState(
        tick=1, day=1, hour=1, time_of_day="day",
        area_id="hq", subplace_id="gate", place_label="Gate",
        area_present=cast, cast=cast, cast_ids=frozenset(cast_ids),
        scene_focus=cast_ids[0] if cast_ids else None, pending_events=(),
    )


def test_confirm_drops_speaker_in_cast():
    scene = _scene(["g1"])
    nominations = [{"type": "speaker_not_in_cast", "suspected_id": "g1"}]
    confirmed, dropped = confirm_nominations(
        nominations,
        "The guard speaks.",
        player={"area": "hq", "inventory": []},
        npcs={"g1": {"id": "g1", "name": "Guard", "status": "alive", "role": "guard"}},
        scene_state=scene,
        action_ctx={"kind": "talk"},
        focal_npc_id="g1",
        present_npcs=list(scene.cast),
        scene_place="Gate",
    )
    assert not confirmed
    assert dropped


def test_confirm_speaker_role_not_in_cast():
    scene = _scene(["m1"])
    nominations = [{
        "type": "speaker_not_in_cast",
        "role_hint": "priest",
        "quote": "The priest said hello",
    }]
    confirmed, _ = confirm_nominations(
        nominations,
        'The priest said hello.',
        player={"area": "hq", "inventory": []},
        npcs={"m1": {"id": "m1", "name": "Merchant", "status": "alive", "role": "merchant"}},
        scene_state=scene,
        action_ctx={"kind": "talk"},
        focal_npc_id="m1",
        present_npcs=list(scene.cast),
        scene_place="Gate",
    )
    assert confirmed
    assert "priest" in confirmed[0].lower()


_LONG = (
    "The priest stepped from the shadow and spoke in a dry voice, "
    "words settling on the cobbles like dust. You held your ground."
)


def test_auditor_on_mode_with_mock(monkeypatch):
    monkeypatch.setenv("AISTORY_PROSE_AUDITOR", "on")
    monkeypatch.setenv(
        "AISTORY_MOCK_PROSE_AUDITOR_JSON",
        '{"violations":[{"type":"speaker_not_in_cast","role_hint":"priest","quote":"The priest said no"}]}',
    )
    scene = _scene(["g1"])
    confirmed, meta = run_prose_audit(
        _LONG,
        player={"area": "hq", "inventory": []},
        npcs={"g1": {"id": "g1", "name": "Guard", "status": "alive", "role": "guard"}},
        scene_state=scene,
        action_ctx={"kind": "talk", "target_id": "g1"},
        focal_npc_id="g1",
        scene_place="Gate",
        present_npcs=list(scene.cast),
    )
    assert meta["invoked"]
    assert meta["confirmed"] >= 1
    assert confirmed
    monkeypatch.delenv("AISTORY_MOCK_PROSE_AUDITOR_JSON", raising=False)


def test_auditor_shadow_does_not_return_issues(monkeypatch):
    monkeypatch.setenv("AISTORY_PROSE_AUDITOR", "shadow")
    monkeypatch.setenv(
        "AISTORY_MOCK_PROSE_AUDITOR_JSON",
        '{"violations":[{"type":"speaker_not_in_cast","role_hint":"priest","quote":"priest spoke"}]}',
    )
    scene = _scene(["g1"])
    confirmed, meta = run_prose_audit(
        _LONG,
        player={"area": "hq"},
        npcs={"g1": {"id": "g1", "role": "guard", "status": "alive"}},
        scene_state=scene,
        action_ctx={"kind": "talk"},
        focal_npc_id="g1",
        scene_place="Gate",
        present_npcs=list(scene.cast),
    )
    assert not confirmed
    assert meta.get("confirmed", 0) >= 1
    monkeypatch.delenv("AISTORY_MOCK_PROSE_AUDITOR_JSON", raising=False)


def test_regen_governor_respects_priority():
    issues = ["focal npc not clearly referenced", "AUDITOR CONFIRMED: dead NPC 'Bob' portrayed as speaking"]
    assert issues_warrant_regen(issues, 0)
    low = ["scene too short or empty"]
    assert not issues_warrant_regen(low, 0)


def test_regen_governor_max_attempts():
    issues = ["AUDITOR CONFIRMED: speaker 'x' not in scene cast"]
    _, should_retry, meta = apply_regen_governor(issues, attempt=99)
    assert not should_retry
    assert meta.get("exhausted")


def test_fact_gate_integrates_auditor_on(monkeypatch):
    monkeypatch.setenv("AISTORY_PROSE_AUDITOR", "on")
    monkeypatch.setenv(
        "AISTORY_MOCK_PROSE_AUDITOR_JSON",
        '{"violations":[{"type":"speaker_not_in_cast","role_hint":"priest","quote":"The priest spoke"}]}',
    )
    scene = _scene(["g1"])
    text = _LONG
    issues, *_rest = validate_turn_output(
        text,
        player={"area": "hq", "inventory": []},
        npcs={"g1": {"id": "g1", "role": "guard", "status": "alive"}},
        action_ctx={"kind": "talk", "target_id": "g1"},
        focal_npc_id="g1",
        scene_place="Gate",
        present_npcs=list(scene.cast),
        scene_state=scene,
    )
    assert any("AUDITOR CONFIRMED" in i for i in issues)
    monkeypatch.delenv("AISTORY_MOCK_PROSE_AUDITOR_JSON", raising=False)


def test_confirm_left_behind_speaker():
    scene = _scene(["scraper"])
    nominations = [{
        "type": "speaker_not_in_cast",
        "suspected_id": "bessa",
        "quote": "Bessa said wait",
    }]
    confirmed, _ = confirm_nominations(
        nominations,
        'Bessa said, "Wait here."',
        player={"area": "docks", "inventory": []},
        npcs={
            "bessa": {"id": "bessa", "name": "Bessa", "status": "alive", "role": "herbalist"},
            "scraper": {"id": "scraper", "name": "Scraper", "status": "alive", "role": "laborer"},
        },
        scene_state=scene,
        action_ctx={"kind": "explore", "relocated": True, "left_behind_cast": ["bessa"]},
        focal_npc_id=None,
        present_npcs=list(scene.cast),
        scene_place="Cellar",
    )
    assert confirmed
    assert "left-behind" in confirmed[0].lower() or "not in scene cast" in confirmed[0].lower()


def test_schedule_untagged_in_boundary_metrics():
    from simulation.boundary_metrics import build_output_boundary, tag_turn_issues

    raw = "She promises a gathering when the third bell rings."
    out = build_output_boundary(
        kind="talk",
        action_ctx={"kind": "talk", "target_id": "g1"},
        raw_scene=raw,
        prose_issues=[],
        fact_issues=[],
        focal_id="g1",
    )
    assert out.get("schedule_untagged")
    tagged = tag_turn_issues([], [], {}, out)
    assert any("schedule" in t.get("summary", "").lower() for t in tagged)


def test_dedupe_issues():
    d = dedupe_issues(["Same issue", "same issue"])
    assert len(d) == 1
