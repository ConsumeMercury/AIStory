"""
Google Gemini API — scene prose generation (google-genai SDK).

Gemini 3.x: max_output_tokens is a combined budget for thinking + visible text.
Use minimal thinking and a generous cap so prose is not cut off mid-sentence.
"""

import os
import re
import time

from config.load_env import load_env

load_env()

from google import genai
from google.genai import types

DEFAULT_MODEL = "gemini-3.5-flash"
FALLBACK_MODELS = ("gemini-2.5-flash", "gemini-3-flash-preview")
DEFAULT_MAX_OUTPUT_TOKENS = 4096
API_RETRY_ATTEMPTS = 5
API_RETRY_BASE_SEC = 2.0


def api_key():
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def model_name():
    return os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)


def get_max_output_tokens():
    raw = os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "")
    if raw.isdigit():
        return max(512, int(raw))
    return DEFAULT_MAX_OUTPUT_TOKENS


def require_api_key():
    key = api_key()
    if not key:
        raise RuntimeError(
            "Missing API key. Set GEMINI_API_KEY (or GOOGLE_API_KEY) to your "
            "Google AI Studio key: https://aistudio.google.com/apikey"
        )
    return key


def _thinking_config(model):
    """Creative prose needs visible tokens, not long internal reasoning."""
    m = model.lower()
    if "3.5" in m or m.startswith("gemini-3"):
        return types.ThinkingConfig(thinking_level="minimal")
    if "2.5" in m:
        return types.ThinkingConfig(thinking_budget=0)
    return types.ThinkingConfig(thinking_level="minimal")


def _generation_config(model, *, max_tokens, temperature=None, top_p=None):
    kwargs = {
        "max_output_tokens": max_tokens,
        "thinking_config": _thinking_config(model),
    }
    if "2.5" in model.lower() and temperature is not None:
        kwargs["temperature"] = temperature
        kwargs["top_p"] = top_p
    return types.GenerateContentConfig(**kwargs)


def _finish_reason(response):
    try:
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            return getattr(candidates[0], "finish_reason", None)
    except (IndexError, AttributeError, TypeError):
        pass
    return None


def _extract_text(response):
    text = getattr(response, "text", None)
    if text and str(text).strip():
        return str(text).strip()

    parts = []
    for cand in getattr(response, "candidates", None) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", None) or []:
            part_text = getattr(part, "text", None)
            if part_text and not getattr(part, "thought", False):
                parts.append(part_text)
    return "".join(parts).strip()


def _retryable_api_error(err):
    from google.genai import errors as genai_errors

    if isinstance(err, genai_errors.ServerError):
        code = getattr(err, "status_code", None)
        if code in (429, 500, 502, 503, 504):
            return True
    if isinstance(err, genai_errors.ClientError):
        code = getattr(err, "status_code", None)
        if code == 429:
            return True
    msg = str(err).upper()
    return "UNAVAILABLE" in msg or "RESOURCE_EXHAUSTED" in msg or "HIGH DEMAND" in msg


def _generate_once(client, model, prompt, *, cap, temperature, top_p):
    return client.models.generate_content(
        model=model,
        contents=prompt,
        config=_generation_config(
            model,
            max_tokens=cap,
            temperature=temperature,
            top_p=top_p,
        ),
    )


def _looks_truncated(text, response):
    reason = _finish_reason(response)
    if reason is not None and "MAX_TOKENS" in str(reason).upper():
        return True
    stripped = (text or "").strip()
    if len(stripped) < 80:
        return True
    if stripped[-1] not in ".!?\"":
        return True
    if re.search(
        r"\b(your|the|a|an|to|with|and|or|of|in|on|at|for|from|that|this|their|you)\s*$",
        stripped,
        re.I,
    ):
        return True
    return False


def _call_with_retries(client, model, prompt, *, cap, temperature, top_p):
    """Retry transient Gemini overload / rate-limit errors with backoff."""
    last_err = None
    for attempt in range(API_RETRY_ATTEMPTS):
        try:
            return _generate_once(
                client, model, prompt, cap=cap, temperature=temperature, top_p=top_p,
            )
        except Exception as e:
            last_err = e
            if not _retryable_api_error(e) or attempt >= API_RETRY_ATTEMPTS - 1:
                raise
            delay = min(API_RETRY_BASE_SEC * (2 ** attempt), 30.0)
            time.sleep(delay)
    raise last_err


def _generate_stream_once(client, model, prompt, *, cap, temperature, top_p):
    return client.models.generate_content_stream(
        model=model,
        contents=prompt,
        config=_generation_config(
            model,
            max_tokens=cap,
            temperature=temperature,
            top_p=top_p,
        ),
    )


def generate_text_stream(prompt, *, temperature=0.78, top_p=0.88, max_tokens=None, on_chunk=None):
    """Stream generated prose; invoke on_chunk for each text delta; return full text."""
    from google.genai import errors as genai_errors

    client = genai.Client(api_key=require_api_key())
    token_cap = max_tokens or get_max_output_tokens()
    models_to_try = [model_name()]
    for m in FALLBACK_MODELS:
        if m not in models_to_try:
            models_to_try.append(m)

    caps = (token_cap, min(token_cap * 2, 8192))
    last_err = None

    for model in models_to_try:
        try:
            for cap in caps:
                parts = []
                last_response = None
                stream = _call_with_retries_stream(
                    client, model, prompt, cap=cap, temperature=temperature, top_p=top_p,
                )
                for chunk in stream:
                    last_response = chunk
                    piece = _extract_text(chunk)
                    if not piece:
                        continue
                    parts.append(piece)
                    if on_chunk:
                        on_chunk(piece)
                text = "".join(parts).strip()
                if not text:
                    raise RuntimeError("Gemini returned an empty response.")
                if _looks_truncated(text, last_response):
                    if cap < caps[-1]:
                        continue
                    raise RuntimeError(
                        "Gemini response was cut off mid-sentence. "
                        "Try raising GEMINI_MAX_OUTPUT_TOKENS (e.g. 8192)."
                    )
                return text
        except genai_errors.ClientError as e:
            last_err = e
            if getattr(e, "status_code", None) == 404:
                continue
            if _retryable_api_error(e):
                continue
            raise
        except genai_errors.ServerError as e:
            last_err = e
            if _retryable_api_error(e):
                continue
            raise

    hint = (
        f"Tried models: {', '.join(models_to_try)}. "
        f"Set GEMINI_MODEL to a model your key supports "
        f"(see https://ai.google.dev/gemini-api/docs/models)."
    )
    if last_err:
        raise RuntimeError(f"{last_err}. {hint}") from last_err
    raise RuntimeError(hint)


def _call_with_retries_stream(client, model, prompt, *, cap, temperature, top_p):
    """Retry transient Gemini overload / rate-limit errors with backoff (streaming)."""
    last_err = None
    for attempt in range(API_RETRY_ATTEMPTS):
        try:
            return _generate_stream_once(
                client, model, prompt, cap=cap, temperature=temperature, top_p=top_p,
            )
        except Exception as e:
            last_err = e
            if not _retryable_api_error(e) or attempt >= API_RETRY_ATTEMPTS - 1:
                raise
            delay = min(API_RETRY_BASE_SEC * (2 ** attempt), 30.0)
            time.sleep(delay)
    raise last_err


def generate_text(prompt, *, temperature=0.78, top_p=0.88, max_tokens=None):
    """Send a single prompt; return complete generated prose."""
    from google.genai import errors as genai_errors

    client = genai.Client(api_key=require_api_key())
    token_cap = max_tokens or get_max_output_tokens()
    models_to_try = [model_name()]
    for m in FALLBACK_MODELS:
        if m not in models_to_try:
            models_to_try.append(m)

    caps = (token_cap, min(token_cap * 2, 8192))
    last_err = None

    for model in models_to_try:
        try:
            for cap in caps:
                response = _call_with_retries(
                    client, model, prompt, cap=cap, temperature=temperature, top_p=top_p,
                )
                text = _extract_text(response)
                if not text:
                    raise RuntimeError("Gemini returned an empty response.")

                if _looks_truncated(text, response):
                    if cap < caps[-1]:
                        continue
                    raise RuntimeError(
                        "Gemini response was cut off mid-sentence. "
                        "Try raising GEMINI_MAX_OUTPUT_TOKENS (e.g. 8192)."
                    )
                return text
        except genai_errors.ClientError as e:
            last_err = e
            if getattr(e, "status_code", None) == 404:
                continue
            if _retryable_api_error(e):
                continue
            raise
        except genai_errors.ServerError as e:
            last_err = e
            if _retryable_api_error(e):
                continue
            raise

    hint = (
        f"Tried models: {', '.join(models_to_try)}. "
        f"Set GEMINI_MODEL to a model your key supports "
        f"(see https://ai.google.dev/gemini-api/docs/models)."
    )
    if last_err:
        raise RuntimeError(f"{last_err}. {hint}") from last_err
    raise RuntimeError(hint)
