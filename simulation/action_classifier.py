"""
Structured LLM action classifier — validates against authoritative scene cast.

Modes (AISTORY_ACTION_CLASSIFIER):
  off    — regex interpreter only (tests, default when unset in CI)
  shadow — run classifier, log diffs, keep regex result
  on     — use classifier when needs_llm_classifier; regex is fallback
"""

import json
import logging
import os
import re

from generation.descriptor_generator import short_descriptor
from simulation.boundary_metrics import build_classifier_diff
from simulation.action_vocab import (
    FAST_PATH_KINDS,
    HIGH_STAKES_KINDS,
    SPEECH_KINDS,
    VALID_ACTION_KINDS,
    normalize_kind,
)

log = logging.getLogger(__name__)

_CLASSIFIER_MODES = frozenset({"off", "shadow", "on"})


def classifier_mode():
    raw = (os.environ.get("AISTORY_ACTION_CLASSIFIER") or "off").strip().lower()
    return raw if raw in _CLASSIFIER_MODES else "off"


def _mock_classifier_json():
    """Test hook — inject fixed classifier JSON without API."""
    return os.environ.get("AISTORY_MOCK_CLASSIFIER_JSON", "").strip()


def needs_llm_classifier(action, regex_ctx, scene):
    """True when regex interpretation is likely insufficient."""
    if not action or not scene:
        return False
    kind = regex_ctx.get("kind", "general")
    if kind in FAST_PATH_KINDS and regex_ctx.get("target_id"):
        if kind not in SPEECH_KINDS or regex_ctx.get("player_speech"):
            return False
    if kind == "general":
        return True
    if kind in SPEECH_KINDS and not regex_ctx.get("player_speech"):
        if re.search(r"\b(why|what|how|where|when|who|whether|if)\b", action, re.I):
            return True
        if re.search(r"^\s*ask\s+", action, re.I):
            return True
    if not regex_ctx.get("target_id"):
        from simulation.target_resolution import action_mentions_role_or_descriptor
        if action_mentions_role_or_descriptor(action, present=list(scene.cast)):
            return True
    return False


def _build_prompt(action, scene, player, regex_ctx):
    cast_lines = []
    for row in scene.cast_for_classifier():
        label = row["name"] or row["role"] or row["id"]
        cast_lines.append(f"- id={row['id']} name={label!r} role={row['role']!r}")
    cast_block = "\n".join(cast_lines) if cast_lines else "- (empty cast)"
    kinds = ", ".join(sorted(VALID_ACTION_KINDS))
    focus = scene.scene_focus or "null"
    return (
        "Classify the player's action into structured simulation fields.\n"
        "Return ONLY valid JSON with keys: kind, target_id, player_speech, time_target.\n"
        "Rules:\n"
        f"- kind MUST be one of: {kinds}\n"
        "- target_id MUST be null or one of the present cast ids listed below\n"
        "- player_speech: reconstructed quote the protagonist speaks, or null\n"
        "- time_target: parsed wait target phrase or null\n"
        f"- scene focus npc id: {focus}\n"
        f"- place: {scene.place_label}\n"
        f"Regex guess (may be wrong): kind={regex_ctx.get('kind')!r} "
        f"target_id={regex_ctx.get('target_id')!r}\n"
        "Present cast:\n"
        f"{cast_block}\n"
        f"Player action: {action.strip()[:400]}\n"
        "JSON:"
    )


def _parse_json(text):
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    m = re.search(r"\{[^{}]*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def validate_classifier_result(raw, scene):
    """Reject fabricated ids/kinds — return sanitized dict or None."""
    validated, _reason = validate_classifier_result_with_reason(raw, scene)
    return validated


def validate_classifier_result_with_reason(raw, scene):
    """Like validate_classifier_result but returns (result, error_reason)."""
    if not raw or not isinstance(raw, dict):
        return None, "not_a_dict"
    kind = normalize_kind(raw.get("kind"))
    if not kind:
        return None, f"invalid_kind:{raw.get('kind')!r}"
    target_id = raw.get("target_id")
    if target_id is not None:
        target_id = str(target_id).strip()
        if target_id not in scene.cast_ids:
            target_id = None
    speech = raw.get("player_speech")
    if speech is not None:
        speech = str(speech).strip()[:200] or None
    time_target = raw.get("time_target")
    if time_target is not None:
        time_target = str(time_target).strip()[:120] or None
    return {
        "kind": kind,
        "target_id": target_id,
        "player_speech": speech,
        "time_target": time_target,
    }, None


def classify_action_llm(action, scene, player, regex_ctx):
    """Call Gemini for structured interpretation. Returns (validated|None, error|None)."""
    mock = _mock_classifier_json()
    if mock:
        validated, err = validate_classifier_result_with_reason(_parse_json(mock), scene)
        return validated, err
    if classifier_mode() == "off":
        return None, None
    if not needs_llm_classifier(action, regex_ctx, scene):
        return None, None
    try:
        from simulation.gemini_client import generate_text, structured_json_max_tokens
        prompt = _build_prompt(action, scene, player, regex_ctx)
        text = generate_text(
            prompt,
            temperature=0.15,
            top_p=0.9,
            max_tokens=structured_json_max_tokens(),
            json_output=True,
        )
        if not (text or "").strip():
            return None, "empty_llm_response"
        parsed = _parse_json(text)
        if not parsed:
            return None, f"json_parse_failed:{text[:160]}"
        validated, reason = validate_classifier_result_with_reason(parsed, scene)
        if not validated:
            return None, reason or "validation_rejected"
        return validated, None
    except Exception as e:
        log.debug("Action classifier failed: %s", e)
        return None, str(e)[:200]


def _log_shadow_diff(action, regex_ctx, validated):
    if not validated:
        return
    diffs = []
    if validated["kind"] != regex_ctx.get("kind"):
        diffs.append(f"kind {regex_ctx.get('kind')!r}→{validated['kind']!r}")
    if validated.get("target_id") != regex_ctx.get("target_id"):
        diffs.append(
            f"target {regex_ctx.get('target_id')!r}→{validated.get('target_id')!r}"
        )
    if validated.get("player_speech") and validated["player_speech"] != regex_ctx.get("player_speech"):
        diffs.append("speech reconstructed")
    if diffs:
        log.info(
            "Action classifier shadow diff (%r): %s",
            (action or "")[:60],
            "; ".join(diffs),
        )


def apply_classifier_to_ctx(action, player, present_npcs, npcs, regex_ctx, scene):
    """
    Enhance regex action_ctx with validated classifier output.
    Returns updated ctx (same dict, mutated).
    """
    mode = classifier_mode()
    regex_snapshot = {
        "kind": regex_ctx.get("kind"),
        "target_id": regex_ctx.get("target_id"),
        "player_speech": regex_ctx.get("player_speech"),
    }
    bc = {
        "mode": mode,
        "invoked": False,
        "disagrees": False,
        "diffs": [],
        "skip_reason": None,
        "error": None,
    }
    if mode == "off" or not scene:
        bc["skip_reason"] = "mode_off" if mode == "off" else "no_scene"
        regex_ctx["boundary_classifier"] = bc
        return regex_ctx

    if not needs_llm_classifier(action, regex_ctx, scene):
        bc["skip_reason"] = "fast_path"
        regex_ctx["boundary_classifier"] = bc
        return regex_ctx

    bc["invoked"] = True
    validated, fail_reason = classify_action_llm(action, scene, player, regex_ctx)

    if not validated:
        bc["skip_reason"] = "classifier_failed"
        bc["error"] = fail_reason
        regex_ctx["boundary_classifier"] = bc
        return regex_ctx

    diff = build_classifier_diff(regex_snapshot, validated)
    bc.update(diff)
    bc["validated"] = validated

    if mode == "shadow":
        _log_shadow_diff(action, regex_snapshot, validated)
        regex_ctx["classifier_shadow"] = validated
        regex_ctx["boundary_classifier"] = bc
        return regex_ctx

    # mode == "on"
    old_kind = regex_ctx.get("kind")
    regex_ctx["kind"] = validated["kind"]
    regex_ctx["classifier_applied"] = True
    if validated.get("target_id"):
        regex_ctx["target_id"] = validated["target_id"]
        target = next((n for n in present_npcs if n["id"] == validated["target_id"]), None)
        if not target and npcs:
            target = npcs.get(validated["target_id"])
        if target:
            regex_ctx["target_descriptor"] = short_descriptor(target)
    if validated.get("player_speech") and validated["kind"] in SPEECH_KINDS:
        regex_ctx["player_speech"] = validated["player_speech"]
    if validated.get("time_target"):
        regex_ctx["time_target_hint"] = validated["time_target"]
    if validated["kind"] in HIGH_STAKES_KINDS and old_kind != validated["kind"]:
        regex_ctx["classifier_high_stakes"] = True
    regex_ctx["boundary_classifier"] = bc
    return regex_ctx
