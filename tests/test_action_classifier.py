"""Structured action classifier — validation and shadow mode."""

import os

import pytest

from simulation.action_classifier import (
    apply_classifier_to_ctx,
    classifier_mode,
    needs_llm_classifier,
    validate_classifier_result,
)
from simulation.scene_state import SceneState


def _scene(*ids):
    cast = tuple({"id": i, "name": i, "role": "guard", "status": "alive"} for i in ids)
    return SceneState(
        tick=1, day=1, hour=1, time_of_day="day",
        area_id="hq", subplace_id="gate", place_label="High Quarter — gate",
        area_present=cast, cast=cast, cast_ids=frozenset(ids),
        scene_focus=ids[0] if ids else None, pending_events=(),
    )


def test_validate_rejects_invented_target():
    scene = _scene("g1", "g2")
    raw = {"kind": "ask_about", "target_id": "phantom", "player_speech": "Why?"}
    out = validate_classifier_result(raw, scene)
    assert out["target_id"] is None


def test_validate_accepts_cast_target():
    scene = _scene("g1")
    raw = {"kind": "talk", "target_id": "g1", "player_speech": "Hello"}
    out = validate_classifier_result(raw, scene)
    assert out["target_id"] == "g1"


def test_needs_classifier_for_general():
    scene = _scene("g1")
    regex_ctx = {"kind": "general", "target_id": None}
    assert needs_llm_classifier("I shrug and stay quiet", regex_ctx, scene)


def test_needs_classifier_false_for_attack_with_target():
    scene = _scene("g1")
    regex_ctx = {"kind": "attack", "target_id": "g1"}
    assert not needs_llm_classifier("attack him", regex_ctx, scene)


def test_mock_classifier_on_mode(monkeypatch):
    monkeypatch.setenv("AISTORY_ACTION_CLASSIFIER", "on")
    monkeypatch.setenv(
        "AISTORY_MOCK_CLASSIFIER_JSON",
        '{"kind":"ask_about","target_id":"g1","player_speech":"When does the carriage clear?","time_target":null}',
    )
    scene = _scene("g1")
    ctx = {"kind": "general", "target_id": None, "player_speech": None}
    out = apply_classifier_to_ctx(
        "ask the guard when the carriage clears the archway",
        {"known_npcs": {}},
        list(scene.cast),
        {"g1": scene.cast[0]},
        ctx,
        scene,
    )
    assert out["kind"] == "ask_about"
    assert out["target_id"] == "g1"
    assert "carriage" in (out.get("player_speech") or "").lower()
    monkeypatch.delenv("AISTORY_MOCK_CLASSIFIER_JSON", raising=False)


def test_classifier_failure_surfaces_error(monkeypatch):
    monkeypatch.setenv("AISTORY_ACTION_CLASSIFIER", "shadow")

    def _fail_llm(*_a, **_k):
        return "not json at all"

    monkeypatch.setattr(
        "simulation.gemini_client.generate_text",
        _fail_llm,
    )
    scene = _scene("g1")
    ctx = {"kind": "general", "target_id": None, "player_speech": None}
    out = apply_classifier_to_ctx(
        "ask the guard when the carriage clears",
        {"known_npcs": {}},
        list(scene.cast),
        {"g1": scene.cast[0]},
        ctx,
        scene,
    )
    bc = out.get("boundary_classifier") or {}
    assert bc.get("invoked")
    assert bc.get("skip_reason") == "classifier_failed"
    assert bc.get("error")


def test_classifier_off_by_default():
    assert classifier_mode() == "off" or os.environ.get("AISTORY_ACTION_CLASSIFIER")
