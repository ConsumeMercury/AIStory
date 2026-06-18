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
from simulation.target_resolution import (
    action_mentions_target_constraint,
    npc_matches_action_role_hint,
)
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
    if kind in FAST_PATH_KINDS:
        if regex_ctx.get("target_id"):
            if kind not in SPEECH_KINDS or regex_ctx.get("player_speech"):
                return False
        elif kind in ("approach", "travel") and scene and scene.subplace_id:
            return False
    if kind == "general":
        return True
    if kind in SPEECH_KINDS and not regex_ctx.get("player_speech"):
        if re.search(r"\b(why|what|how|where|when|who|whether|if)\b", action, re.I):
            return True
        if re.search(r"^\s*ask\s+", action, re.I):
            return True
    if not regex_ctx.get("target_id"):
        from simulation.target_resolution import action_mentions_target_constraint
        if action_mentions_target_constraint(action, present=list(scene.cast)):
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
        "Return ONLY valid JSON with keys: kind, player_speech, time_target, confidence, abstain, constraints.\n"
        "Rules:\n"
        f"- kind MUST be one of: {kinds}\n"
        "- constraints: object naming what the player expressed — NOT final resolution:\n"
        '  {gender: "male"|"female"|null, role: string|null, name_query: string|null,\n'
        "   physical: [strings], topic: string|null, negated_kind: string|null}\n"
        "- Do NOT resolve target_id — leave target resolution to deterministic code.\n"
        "- player_speech: reconstructed quote the protagonist speaks, or null\n"
        "- time_target: parsed wait target phrase or null\n"
        "- confidence: float 0.0-1.0 how sure you are\n"
        "- abstain: true if you cannot interpret safely — prefer abstain over guessing\n"
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


def _parse_constraints(raw):
    c = raw.get("constraints") if isinstance(raw, dict) else None
    if not isinstance(c, dict):
        return {}
    out = {}
    g = c.get("gender")
    if g in ("male", "female"):
        out["gender"] = g
    role = c.get("role")
    if role:
        out["role"] = str(role).strip().lower()[:32]
    nq = c.get("name_query")
    if nq:
        out["name_query"] = str(nq).strip()[:48]
    topic = c.get("topic")
    if topic:
        out["topic"] = str(topic).strip()[:120]
    nk = c.get("negated_kind")
    if nk:
        out["negated_kind"] = normalize_kind(nk) or str(nk).strip()[:24]
    phys = c.get("physical")
    if isinstance(phys, list):
        out["physical"] = [str(p).strip().lower()[:32] for p in phys if p][:6]
    return out


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
    confidence = raw.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else 1.0
    except (TypeError, ValueError):
        confidence = 1.0
    confidence = max(0.0, min(1.0, confidence))
    abstain = bool(raw.get("abstain"))
    if confidence < 0.55:
        abstain = True
    constraints = _parse_constraints(raw)
    return {
        "kind": kind,
        "target_id": target_id,
        "player_speech": speech,
        "time_target": time_target,
        "confidence": confidence,
        "abstain": abstain,
        "constraints": constraints,
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
    rc = regex_ctx.get("regex_constraints") or {}
    cc = validated.get("constraints") or {}
    for field in ("gender", "role", "name_query", "topic"):
        rv = rc.get(field) or (regex_ctx.get("ask_topic") if field == "topic" else None)
        cv = cc.get(field)
        if cv and cv != rv:
            diffs.append(f"constraints.{field} {rv!r}→{cv!r}")
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
        "regex_constraints": regex_ctx.get("regex_constraints"),
        "ask_topic": regex_ctx.get("ask_topic"),
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

    if validated.get("target_id") and action_mentions_target_constraint(
        action, present=present_npcs,
    ):
        target = next((n for n in present_npcs if n["id"] == validated["target_id"]), None)
        if not target and npcs:
            raw = npcs.get(validated["target_id"])
            if raw and raw.get("status") == "alive":
                target = raw
        if target and not npc_matches_action_role_hint(action, target):
            validated = dict(validated)
            validated["target_id"] = None

    regex_ctx["classifier_confidence"] = validated.get("confidence", 1.0)
    if validated.get("abstain"):
        bc["skip_reason"] = "classifier_abstain"
        bc["validated"] = validated
        regex_ctx["classifier_abstain"] = True
        regex_ctx["interpretation_clarify"] = True
        regex_ctx["interpretation_clarify_reason"] = (
            "classifier abstained — intent unclear; say what you mean plainly"
        )
        regex_ctx["boundary_classifier"] = bc
        return regex_ctx

    diff = build_classifier_diff(regex_snapshot, validated)
    bc.update(diff)
    bc["validated"] = validated

    if mode == "shadow":
        _log_shadow_diff(action, regex_snapshot, validated)
        regex_ctx["classifier_shadow"] = validated
        if validated.get("constraints"):
            regex_ctx["classifier_shadow_constraints"] = validated["constraints"]
        regex_ctx["boundary_classifier"] = bc
        return regex_ctx

    # mode == "on" — apply kind/speech/time; resolve target via constraints + code, not classifier id
    old_kind = regex_ctx.get("kind")
    regex_ctx["kind"] = validated["kind"]
    regex_ctx["classifier_applied"] = True
    if validated.get("constraints"):
        regex_ctx["classifier_constraints"] = validated["constraints"]
        topic = validated["constraints"].get("topic")
        if topic and validated.get("kind") == "ask_about":
            from simulation.topic_resolution import classify_topic
            if not regex_ctx.get("ask_topic"):
                regex_ctx["ask_topic"] = topic
                regex_ctx["topic_type"] = classify_topic(topic)
    if validated.get("player_speech") and validated["kind"] in SPEECH_KINDS:
        regex_ctx["player_speech"] = validated["player_speech"]
    if validated.get("time_target"):
        regex_ctx["time_target_hint"] = validated["time_target"]
    if validated["kind"] in HIGH_STAKES_KINDS and old_kind != validated["kind"]:
        regex_ctx["classifier_high_stakes"] = True
    # Constraint-based target resolution — never trust classifier target_id when constraints bind
    if action_mentions_target_constraint(action, present=present_npcs) or validated.get("constraints"):
        from simulation.target_constraints import resolve_target
        result = resolve_target(action, player, present_npcs, npcs=npcs, kind=validated["kind"])
        from simulation.target_resolution import apply_resolved_target_to_ctx
        apply_resolved_target_to_ctx(regex_ctx, result)
    elif validated.get("target_id") and not validated.get("constraints"):
        regex_ctx["target_id"] = validated["target_id"]
        target = next((n for n in present_npcs if n["id"] == validated["target_id"]), None)
        if not target and npcs:
            target = npcs.get(validated["target_id"])
        if target:
            regex_ctx["target_descriptor"] = short_descriptor(target)
    regex_ctx["boundary_classifier"] = bc
    return regex_ctx


CLASSIFIER_SHADOW_CORPUS = [
    (
        "talk to the woman",
        {
            "kind": "talk",
            "player_speech": None,
            "time_target": None,
            "confidence": 0.92,
            "abstain": False,
            "constraints": {"gender": "female", "role": None, "name_query": None, "topic": None},
        },
    ),
    (
        "ask the guard about the murder",
        {
            "kind": "ask_about",
            "player_speech": "What do you know about the murder?",
            "time_target": None,
            "confidence": 0.9,
            "abstain": False,
            "constraints": {"gender": None, "role": "guard", "name_query": None, "topic": "the murder"},
        },
    ),
    (
        "ask Holt when the gate opens",
        {
            "kind": "ask_about",
            "player_speech": "When does the gate open?",
            "time_target": "gate opens",
            "confidence": 0.88,
            "abstain": False,
            "constraints": {"gender": None, "role": None, "name_query": "Holt", "topic": "gate opens"},
        },
    ),
    (
        "don't attack, just talk to the priest",
        {
            "kind": "talk",
            "player_speech": None,
            "time_target": None,
            "confidence": 0.85,
            "abstain": False,
            "constraints": {"gender": None, "role": "priest", "negated_kind": "attack", "topic": None},
        },
    ),
    (
        "give her five silver",
        {
            "kind": "give",
            "player_speech": None,
            "time_target": None,
            "confidence": 0.9,
            "abstain": False,
            "constraints": {"gender": "female", "role": None, "name_query": None, "topic": None},
        },
    ),
    (
        "uh",
        {
            "kind": "general",
            "player_speech": None,
            "time_target": None,
            "confidence": 0.3,
            "abstain": True,
            "constraints": {},
        },
    ),
]


def run_classifier_shadow_corpus(*, present=None, pl=None, npcs=None, scene=None):
    """
    Offline shadow run — mock classifier JSON per case, no Gemini API.
    Returns rows with regex vs classifier diffs for regression review.
    """
    import json
    import os

    from simulation.action_interpreter import interpret_action
    from simulation.scene_state import SceneState
    from tests.fixtures.catalog_fixtures import npc, player

    present = present or [
        npc("p1", role="priest", name="Hale", gender="male"),
        npc("g1", role="guard", name="Holt", gender="male"),
        npc("w1", role="merchant", name="Mara", gender="female"),
    ]
    npcs = npcs or {n["id"]: n for n in present}
    pl = pl or player(scene_focus="g1", wealth=50)
    cast_ids = frozenset(n["id"] for n in present)
    scene = scene or SceneState(
        tick=1, day=1, hour=10, time_of_day="day",
        area_id="hq", subplace_id="gate", place_label="High Quarter — gate",
        area_present=tuple(present), cast=tuple(present), cast_ids=cast_ids,
        scene_focus="g1", pending_events=(),
    )
    world = {"time_of_day": "day", "weather": "Clear"}
    rows = []
    old_mode = os.environ.get("AISTORY_ACTION_CLASSIFIER")
    old_mock = os.environ.get("AISTORY_MOCK_CLASSIFIER_JSON")
    try:
        os.environ["AISTORY_ACTION_CLASSIFIER"] = "shadow"
        for action, mock in CLASSIFIER_SHADOW_CORPUS:
            os.environ["AISTORY_MOCK_CLASSIFIER_JSON"] = json.dumps(mock)
            ctx = interpret_action(action, pl, present, world, npcs=npcs, scene_state=scene)
            bc = ctx.get("boundary_classifier") or {}
            rows.append({
                "action": action[:80],
                "regex_kind": bc.get("regex_kind") or ctx.get("kind"),
                "classifier_kind": bc.get("classifier_kind") or mock.get("kind"),
                "disagrees": bool(bc.get("disagrees")),
                "diffs": bc.get("diffs") or [],
                "classifier_constraints": mock.get("constraints") or {},
                "abstain": mock.get("abstain"),
            })
    finally:
        if old_mode is None:
            os.environ.pop("AISTORY_ACTION_CLASSIFIER", None)
        else:
            os.environ["AISTORY_ACTION_CLASSIFIER"] = old_mode
        if old_mock is None:
            os.environ.pop("AISTORY_MOCK_CLASSIFIER_JSON", None)
        else:
            os.environ["AISTORY_MOCK_CLASSIFIER_JSON"] = old_mock
    return rows
