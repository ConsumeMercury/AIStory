"""Catalog I — classifier boundary."""

import os

import pytest

from simulation.action_classifier import (
    apply_classifier_to_ctx,
    classifier_mode,
    needs_llm_classifier,
    validate_classifier_result,
)
from simulation.action_vocab import FAST_PATH_KINDS
from simulation.boundary_metrics import build_classifier_diff
from simulation.scene_state import SceneState


def _scene(*ids, subplace="gate"):
    cast = tuple({"id": i, "name": i, "role": "guard", "status": "alive"} for i in ids)
    return SceneState(
        tick=1, day=1, hour=1, time_of_day="day",
        area_id="hq", subplace_id=subplace, place_label="Gate",
        area_present=cast, cast=cast, cast_ids=frozenset(ids),
        scene_focus=ids[0] if ids else None, pending_events=(),
    )


def test_classifier_output_validated_against_cast():
    scene = _scene("g1")
    out = validate_classifier_result(
        {"kind": "talk", "target_id": "phantom", "player_speech": "Hi"},
        scene,
    )
    assert out["target_id"] is None


def test_classifier_invalid_kind_rejected():
    scene = _scene("g1")
    out = validate_classifier_result(
        {"kind": "fly_to_moon", "target_id": "g1", "player_speech": None},
        scene,
    )
    assert out is None


def test_classifier_truncation_surfaces_error(monkeypatch):
    monkeypatch.setenv("AISTORY_ACTION_CLASSIFIER", "shadow")

    def _fail(*_a, **_k):
        return "truncated { not json"

    monkeypatch.setattr("simulation.gemini_client.generate_text", _fail)
    scene = _scene("g1")
    ctx = {"kind": "general", "target_id": None, "player_speech": None}
    out = apply_classifier_to_ctx(
        "ask the guard about the toll",
        {"known_npcs": {}},
        list(scene.cast),
        {"g1": scene.cast[0]},
        ctx,
        scene,
    )
    bc = out.get("boundary_classifier") or {}
    assert bc.get("error") or bc.get("skip_reason") == "classifier_failed"


@pytest.mark.parametrize("kind", sorted(FAST_PATH_KINDS & {"attack", "wait", "travel", "withdraw"}))
def test_classifier_fast_path_skips_llm_for_resolved_targets(kind):
    scene = _scene("g1")
    ctx = {"kind": kind, "target_id": "g1", "player_speech": "hello" if kind == "talk" else None}
    if kind in ("approach", "travel"):
        scene = _scene("g1", subplace="alcove")
        ctx = {"kind": kind, "target_id": None}
    assert not needs_llm_classifier(f"action for {kind}", ctx, scene)


def test_classifier_off_uses_regex_only(monkeypatch):
    monkeypatch.delenv("AISTORY_ACTION_CLASSIFIER", raising=False)
    monkeypatch.delenv("AISTORY_MOCK_CLASSIFIER_JSON", raising=False)
    assert classifier_mode() == "off"


def test_classifier_token_budget_adequate(monkeypatch):
    monkeypatch.setenv("AISTORY_ACTION_CLASSIFIER", "shadow")
    seen = {}

    def _capture(_prompt, **kwargs):
        seen.update(kwargs)
        return '{"kind":"talk","target_id":"g1","player_speech":null,"time_target":null}'

    monkeypatch.setattr("simulation.gemini_client.generate_text", _capture)
    scene = _scene("g1")
    ctx = {"kind": "general", "target_id": None, "player_speech": None}
    apply_classifier_to_ctx(
        "ask the guard",
        {"known_npcs": {}},
        list(scene.cast),
        {"g1": scene.cast[0]},
        ctx,
        scene,
    )
    assert seen.get("max_tokens", 0) >= 2048


def test_classifier_shadow_diff_metrics():
    diff = build_classifier_diff(
        {"kind": "general", "target_id": None, "player_speech": None},
        {"kind": "ask_about", "target_id": "g1", "player_speech": "Why?"},
    )
    assert diff.get("disagrees")
    assert diff.get("classifier_kind") == "ask_about"
