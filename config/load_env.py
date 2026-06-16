"""
Load GEMINI_API_KEY (and other vars) from a project-root .env file.

Does not override variables already set in the OS environment.
"""

import os
from pathlib import Path

_LOADED = False
ROOT = Path(__file__).resolve().parent.parent


def load_env(force=False):
    global _LOADED
    if _LOADED and not force:
        return
    env_path = ROOT / ".env"
    if not env_path.is_file():
        _LOADED = True
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    _LOADED = True
