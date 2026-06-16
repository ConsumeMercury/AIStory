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


def ai_worldgen_institutions_enabled():
    return os.environ.get("AISTORY_AI_WORLDGEN_INSTITUTIONS", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def ai_worldgen_districts_enabled():
    return os.environ.get("AISTORY_AI_WORLDGEN_DISTRICTS", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def institution_enrich_limit():
    raw = os.environ.get("AISTORY_AI_WORLDGEN_MAX_INSTITUTIONS", "3")
    try:
        return max(1, min(12, int(raw)))
    except ValueError:
        return 3


def npc_batch_size():
    raw = os.environ.get("AISTORY_AI_WORLDGEN_NPC_BATCH", "6")
    try:
        return max(1, min(12, int(raw)))
    except ValueError:
        return 6


def npc_enrich_limit():
    """Max NPCs to LLM-enrich (0 = all alive). Default caps cost while keeping key figures rich."""
    raw = os.environ.get("AISTORY_AI_WORLDGEN_NPC_LIMIT", "20")
    try:
        return max(0, min(80, int(raw)))
    except ValueError:
        return 20


def worldgen_parallel_workers():
    raw = os.environ.get("AISTORY_AI_WORLDGEN_WORKERS", "4")
    try:
        return max(1, min(8, int(raw)))
    except ValueError:
        return 4


def worldgen_retry_failed():
    return os.environ.get("AISTORY_AI_WORLDGEN_RETRY", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def worldgen_split_batches():
    return os.environ.get("AISTORY_AI_WORLDGEN_SPLIT", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def npc_batch_max_tokens():
    raw = os.environ.get("AISTORY_AI_WORLDGEN_NPC_MAX_TOKENS", "4096")
    try:
        return max(1024, min(16384, int(raw)))
    except ValueError:
        return 4096


def ai_worldgen_history_enabled():
    if os.environ.get("AISTORY_AI_WORLDGEN_HISTORY", "").strip().lower() in (
        "0", "false", "no", "off",
    ):
        return False
    return True


def worldgen_max_tokens():
    raw = os.environ.get("AISTORY_AI_WORLDGEN_MAX_TOKENS", "")
    if raw.isdigit():
        return max(1024, int(raw))
    from simulation.gemini_client import get_max_output_tokens
    return max(get_max_output_tokens(), 8192)


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


def call_llm_json(prompt, *, system=None, temperature=0.82, max_tokens=None):
    """Return parsed JSON or None on failure."""
    if not ai_worldgen_enabled():
        return None
    from simulation.gemini_client import generate_text

    parts = []
    if system:
        parts.append(system.strip())
    parts.append(prompt.strip())
    full = "\n\n".join(parts)
    cap = max_tokens or worldgen_max_tokens()
    try:
        raw = generate_text(
            full,
            temperature=temperature,
            max_tokens=cap,
            top_p=0.9,
            json_output=True,
        )
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


def _coerce_str_list(val):
    if isinstance(val, str):
        s = _str_field(val, min_len=4, max_len=320)
        return [s] if s else None
    if isinstance(val, list):
        return val
    return None


def _unwrap_storyline_payload(data):
    if isinstance(data, dict):
        for key in ("storyline", "arc", "institution_arc", "result", "data"):
            inner = data.get(key)
            if isinstance(inner, dict) and (
                inner.get("title") or inner.get("hook") or inner.get("hooks") or inner.get("stages")
            ):
                return inner
    return data


def _unwrap_array_payload(data, keys):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in keys:
            inner = data.get(key)
            if isinstance(inner, list):
                return inner
    return data


def _unwrap_object_payload(data, keys):
    if not isinstance(data, dict):
        return data
    for key in keys:
        inner = data.get(key)
        if isinstance(inner, dict):
            return inner
    return data


def unwrap_npc_batch_payload(raw):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("npcs", "profiles", "characters", "results", "data"):
            inner = raw.get(key)
            if isinstance(inner, list):
                return inner
        if raw.get("persona") and raw.get("background"):
            return [raw]
    return raw


def validate_storyline_spec(data):
    data = _unwrap_storyline_payload(data)
    if not isinstance(data, dict):
        return False, None, ["expected object"]
    title = _str_field(data.get("title"), min_len=4, max_len=120)
    if not title:
        title = _str_field(data.get("name"), min_len=4, max_len=120)
    theme = _str_field(data.get("theme"), min_len=3, max_len=40) or "intrigue"

    hooks_raw = _coerce_str_list(data.get("hooks"))
    if not hooks_raw:
        hook = _str_field(data.get("hook"), min_len=8, max_len=320)
        hooks_raw = [hook] if hook else None
    hooks = _str_list(hooks_raw, min_items=1, max_items=5, item_max=320)

    stages_raw = data.get("stages") or data.get("beats") or data.get("arc_stages")
    stages = _str_list(stages_raw, min_items=3, max_items=6, item_max=200)
    if not title or not hooks or not stages:
        return False, None, ["missing title, hooks, or stages"]
    while len(stages) < 5:
        stages.append(stages[-1])
    return True, {
        "title": title,
        "theme": theme,
        "hook": hooks[0],
        "hooks": hooks,
        "stages": stages[:5],
    }, []


def validate_history_events(data):
    data = _unwrap_array_payload(data, ("events", "history", "history_events"))
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
    data = _unwrap_object_payload(data, ("persona", "character", "profile"))
    if not isinstance(data, dict):
        return False, None, ["expected object"]
    speech = _str_field(data.get("speech_style"), min_len=6, max_len=120)
    quirk = _str_field(data.get("voice_quirk"), min_len=6, max_len=120)
    value = _str_field(data.get("core_value"), min_len=6, max_len=120)
    mood = _str_field(data.get("mood"), min_len=3, max_len=40)
    examples_raw = data.get("example_lines") or data.get("example_line")
    if isinstance(examples_raw, str):
        examples_raw = [examples_raw]
    examples = _str_list(examples_raw, min_items=1, max_items=3, item_max=120)
    avoids = data.get("avoids_topics") or data.get("avoids_topic")
    avoid_list = []
    if isinstance(avoids, str):
        s = _str_field(avoids, min_len=3, max_len=40)
        avoid_list = [s] if s else []
    elif isinstance(avoids, list):
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
    data = _unwrap_object_payload(data, ("background", "character", "profile"))
    if not isinstance(data, dict):
        return False, None, ["expected object"]
    summary = _str_field(data.get("summary"), min_len=24, max_len=600)
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
    if text:
        return True, {"text": text}, []
    for key in ("objective", "personal_objective", "goal", "result", "data"):
        inner = data.get(key)
        if inner is not None:
            return validate_objective_spec(inner)
    return False, None, ["missing text"]


def validate_secrets_list(data):
    data = _unwrap_array_payload(data, ("secrets", "items", "results", "data"))
    if isinstance(data, dict) and data.get("text"):
        data = [data]
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
        sev = str(item.get("severity", "major")).lower()
        if sev not in ("minor", "major", "deadly"):
            sev = "major"
        out.append({"text": text, "severity": sev})
    if not out:
        return False, None, ["no secrets"]
    return True, out, []


def validate_name_spec(data):
    data = _unwrap_object_payload(data, ("name", "character", "result", "data"))
    if not isinstance(data, dict):
        return False, None, ["expected object"]
    given = _str_field(data.get("given_name"), min_len=2, max_len=24)
    surname = _str_field(data.get("surname"), min_len=2, max_len=28)
    if not given:
        return False, None, ["missing given_name"]
    return True, {"given_name": given, "surname": surname}, []


def validate_npc_profile(data):
    data = _unwrap_object_payload(data, ("profile", "character", "npc"))
    if not isinstance(data, dict):
        return False, None, ["expected object"]
    ok_p, persona, err_p = validate_persona_spec(data.get("persona"))
    ok_b, background, err_b = validate_background_spec(data.get("background"))
    appearance = _str_field(data.get("appearance_lock"), min_len=16, max_len=320)
    if not ok_p or not ok_b or not appearance:
        return False, None, err_p + err_b + (["appearance_lock"] if not appearance else [])
    out = {"persona": persona, "background": background, "appearance_lock": appearance}
    ok_o, objective, _ = validate_objective_spec(data.get("personal_objective"))
    if ok_o:
        out["personal_objective"] = objective["text"]
    ok_n, name, _ = validate_name_spec(data)
    if ok_n and ai_worldgen_names_enabled():
        out["name"] = f"{name['given_name']} {name['surname']}".strip() if name.get("surname") else name["given_name"]
    return True, out, []


def llm_json(prompt, validator, *, system=None, temperature=0.82, max_tokens=None):
    """Call LLM, validate, return cleaned dict/list or None."""
    raw = call_llm_json(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
    if raw is None:
        return None
    ok, cleaned, errors = validator(raw)
    if not ok:
        log.warning("AI worldgen validation failed: %s", errors)
        return None
    return cleaned
