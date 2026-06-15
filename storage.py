"""
storage.py  — single, safe persistence layer for the whole project.

Every read/write goes through here so behaviour is consistent:
  * loads never crash on missing / empty / corrupt files
  * writes are ATOMIC (temp file + os.replace) so a crash or a killed
    daemon thread can never leave a half-written, corrupt JSON save.

BASE_DIR is the project root (the folder that contains world/, characters/,
simulation/, ...). It is on sys.path because src/main.py inserts it.
"""

import json
import os
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def full_path(relpath):
    return os.path.join(BASE_DIR, relpath)


def load(relpath, default=None):
    """Load JSON. Returns `default` ({} if not given) on any failure."""
    if default is None:
        default = {}
    path = full_path(relpath)
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return default
        return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return default


def save(relpath, data):
    """Atomically write JSON to relpath."""
    path = full_path(relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)   # atomic on POSIX & Windows
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
