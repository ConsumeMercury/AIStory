"""
Build-time LLM helpers — JSON generation with schema validation and template fallback.
"""

import json
import logging
import os
import re

log = logging.getLogger(__name__)

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def ai_worldgen_enabled():
    if os.environ.get("AISTORY_AI_WORLDGEN", "").strip().lower() not in ("1", "true", "yes", "on"):
        return False
    from simulation.gemini_client import api_key
    return bool(api_key())


def ai_worldgen_names_enabled():
    if os.environ.get("AISTORY_AI_WORLDGEN_NAMES", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    return False


def npc_batch_size():
    raw = os.environ.get("AISTORY_AI_WORLDGEN_NPC_BATCH", "5")
    try:
        return max(1, min(8, int(raw)))
    except ValueError:
        return 5


def _strip_json(text):
    text = (text or "").strip()
    text = _JSON_FENCE.sub("", text).strip()
    return text


def parse_json_response(text):
    text = _strip_json(text)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    return None


def call_llm_json(prompt, *, system=None, temperature=0.82, max_tokens=2048):
    """Return parsed JSON or None on failure."""
    if not ai_worldgen_enabled():
        return None
    from simulation.gemini_client import generate_text

    parts = []
    if system:
        parts.append(system.strip())
    parts.append(prompt.strip())
    full = "\n\n".join(parts)
    try:
        raw = generate_text(full, temperature=temperature, max_tokens=max_tokens, top_p=0.9)
        return parse_json_response(raw)
    except Exception as err:
        log.warning("AI worldgen LLM call failed: %s", err)
        return None


def _str_field(val, *, min_len=1, max_len=500):
    if not isinstance(val, str):
        return None
    s = val.strip()
    if len(s) < min_len or len(s) > max_len:
        return None
    return s


def _str_list(val, *, min_items=1, max_items=8, item_max=400):
    if not isinstance(val, list):
        return None
    out = []
    for item in val[:max_items]:
        s = _str_field(item, min_len=4, max_len=item_max)
        if s:
            out.append(s)
    if len(out) < min_items:
        return None
    return out


def validate_storyline_spec(data):
    if not isinstance(data, dict):
        return False, None, ["expected object"]
    title = _str_field(data.get("title"), min_len=4, max_len=120)
    theme = _str_field(data.get("theme"), min_len=3, max_len=40) or "intrigue"
    hooks = _str_list(data.get("hooks"), min_items=1, max_items=5, item_max=320)
    stages = _str_list(data.get("stages"), min_items=4, max_items=6, item_max=200)
    if not title or not hooks or not stages:
        return False, None, ["missing title, hooks, or stages"]
    if len(stages) < 5:
        while len(stages) < 5:
            stages.append(stages[-1])
    return True, {
        "title": title,
        "theme": theme,
        "hooks": hooks,
        "stages": stages[:5],
    }, []


def validate_history_events(data):
    if not isinstance(data, list):
        return False, None, ["expected array"]
    out = []
    for item in data[:8]:
        if not isinstance(item, dict):
            continue
        when = _str_field(item.get("when"), min_len=4, max_len=80)
        official = _str_field(item.get("official"), min_len=8, max_len=400)
        folk = _str_field(item.get("folk"), min_len=8, max_len=400)
        rumor = _str_field(item.get("rumor"), min_len=6, max_len=240)
        if when and official:
            out.append({
                "when": when,
                "official": official,
                "folk": folk or official,
                "rumor": rumor or "Someone paid to make it happen.",
            })
    if len(out) < 3:
        return False, None, ["too few history events"]
    return True, out, []


def validate_persona_spec(data):
    if not isinstance(data, dict):
        return False, None, ["expected object"]
    speech = _str_field(data.get("speech_style"), min_len=6, max_len=120)
    quirk = _str_field(data.get("voice_quirk"), min_len=6, max_len=120)
    value = _str_field(data.get("core_value"), min_len=6, max_len=120)
    mood = _str_field(data.get("mood"), min_len=3, max_len=40)
    examples = _str_list(data.get("example_lines"), min_items=1, max_items=3, item_max=120)
    avoids = data.get("avoids_topics")
    avoid_list = []
    if isinstance(avoids, list):
        for a in avoids[:4]:
            s = _str_field(a, min_len=3, max_len=40)
            if s:
                avoid_list.append(s)
    if not speech or not quirk or not examples:
        return False, None, ["incomplete persona"]
    return True, {
        "speech_style": speech,
        "voice_quirk": quirk,
        "core_value": value or "debts must be paid",
        "mood": mood or "wary",
        "example_lines": examples[:2],
        "avoids_topics": avoid_list or ["their past"],
        "dialogue_density": _str_field(data.get("dialogue_density"), min_len=6, max_len=80)
        or "normal",
        "literacy": bool(data.get("literacy", True)),
    }, []


def validate_background_spec(data):
    if not isinstance(data, dict):
        return False, None, ["expected object"]
    summary = _str_field(data.get("summary"), min_len=40, max_len=600)
    childhood = _str_field(data.get("childhood"), min_len=10, max_len=200)
    formative = _str_field(data.get("formative_event"), min_len=10, max_len=200)
    current = _str_field(data.get("current_situation"), min_len=10, max_len=200)
    belief = _str_field(data.get("belief"), min_len=10, max_len=200)
    secret = _str_field(data.get("secret"), min_len=10, max_len=200)
    mannerism = _str_field(data.get("mannerism"), min_len=10, max_len=160)
    hope = _str_field(data.get("hope"), min_len=6, max_len=120)
    if not summary:
        return False, None, ["missing summary"]
    return True, {
        "summary": summary,
        "childhood": childhood or summary[:80],
        "formative_event": formative or "life turned sharply once",
        "current_situation": current or "keeps their trade and their secrets",
        "belief": belief or "coin is honest",
        "secret": secret or "hides something that would cost them",
        "mannerism": mannerism or "watches hands, not faces",
        "hope": hope or "leave this city before the year turns",
        "origin": childhood or summary[:80],
        "wound": formative or "was betrayed once",
        "role_history": _str_field(data.get("role_history"), min_len=6, max_len=160) or "",
    }, []


def validate_objective_spec(data):
    if isinstance(data, str):
        text = _str_field(data, min_len=12, max_len=200)
        if text:
            return True, {"text": text}, []
        return False, None, ["bad objective string"]
    if not isinstance(data, dict):
        return False, None, ["expected object or string"]
    text = _str_field(data.get("text"), min_len=12, max_len=200)
    if not text:
        return False, None, ["missing text"]
    return True, {"text": text}, []


def validate_secrets_list(data):
    if not isinstance(data, list):
        return False, None, ["expected array"]
    out = []
    for item in data[:3]:
        if isinstance(item, str):
            text = _str_field(item, min_len=8, max_len=200)
            if text:
                out.append({"text": text, "severity": "major"})
            continue
        if not isinstance(item, dict):
            continue
        text = _str_field(item.get("text"), min_len=8, max_len=200)
        if not text:
            continue
        sev = item.get("severity", "major")
        if sev not in ("minor", "major", "deadly"):
            sev = "major"
        out.append({"text": text, "severity": sev})
    if not out:
        return False, None, ["no secrets"]
    return True, out, []


def validate_name_spec(data):
    if not isinstance(data, dict):
        return False, None, ["expected object"]
    given = _str_field(data.get("given_name"), min_len=2, max_len=24)
    surname = _str_field(data.get("surname"), min_len=2, max_len=28)
    if not given:
        return False, None, ["missing given_name"]
    return True, {"given_name": given, "surname": surname}, []


def validate_npc_profile(data):
    ok_p, persona, err_p = validate_persona_spec(data.get("persona") if isinstance(data, dict) else None)
    ok_b, background, err_b = validate_background_spec(data.get("background") if isinstance(data, dict) else None)
    appearance = _str_field(
        (data or {}).get("appearance_lock"),
        min_len=20,
        max_len=320,
    ) if isinstance(data, dict) else None
    if not ok_p or not ok_b or not appearance:
        return False, None, err_p + err_b + (["appearance_lock"] if not appearance else [])
    out = {"persona": persona, "background": background, "appearance_lock": appearance}
    ok_n, name, _ = validate_name_spec(data)
    if ok_n and ai_worldgen_names_enabled():
        out["name"] = f"{name['given_name']} {name['surname']}".strip() if name.get("surname") else name["given_name"]
    return True, out, []


def llm_json(prompt, validator, *, system=None, temperature=0.82, max_tokens=2048):
    """Call LLM, validate, return cleaned dict/list or None."""
    raw = call_llm_json(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
    if raw is None:
        return None
    ok, cleaned, errors = validator(raw)
    if not ok:
        log.warning("AI worldgen validation failed: %s", errors)
        return None
    return cleaned
