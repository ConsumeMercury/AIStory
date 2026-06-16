"""
Live probe — which sampling fields gemini-3.5-flash / 2.5-flash accept.

Run: python scripts/probe_gemini_config.py
Requires GEMINI_API_KEY in .env or the environment.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config.load_env import load_env

load_env()

from google import genai
from google.genai import types

from simulation.gemini_client import api_key, effective_sampling_params, require_api_key


PROMPT = "Reply with exactly one word: acknowledged."
MODELS = ("gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.0-flash")


def _try(model, *, temperature=None, top_p=None, frequency_penalty=None):
    client = genai.Client(api_key=require_api_key())
    sampling = effective_sampling_params(
        model,
        temperature=temperature,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
    )
    kwargs = {"max_output_tokens": 32, "thinking_config": types.ThinkingConfig(thinking_level="minimal")}
    if sampling["temperature"] is not None:
        kwargs["temperature"] = sampling["temperature"]
    if sampling["top_p"] is not None:
        kwargs["top_p"] = sampling["top_p"]
    if sampling["frequency_penalty"] is not None:
        kwargs["frequency_penalty"] = sampling["frequency_penalty"]
    try:
        response = client.models.generate_content(
            model=model,
            contents=PROMPT,
            config=types.GenerateContentConfig(**kwargs),
        )
        text = (getattr(response, "text", None) or "").strip()[:40]
        return True, text or "(empty)"
    except Exception as err:
        return False, str(err)[:200]


def main():
    if not api_key():
        print("GEMINI_API_KEY not set — skipping live probe.")
        return 1

    print("Gemini sampling field probe\n")
    for model in MODELS:
        print(f"=== {model} ===")
        cases = [
            ("defaults only", {}),
            ("temperature=0.55", {"temperature": 0.55, "top_p": 0.9}),
            ("frequency_penalty=0.35", {"frequency_penalty": 0.35}),
            ("both", {"temperature": 0.55, "top_p": 0.9, "frequency_penalty": 0.35}),
        ]
        for label, params in cases:
            ok, detail = _try(model, **params)
            status = "OK" if ok else "FAIL"
            print(f"  {status:4} {label:28} {detail}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
