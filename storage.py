"""
storage.py  — single, safe persistence layer for the whole project.

Every read/write goes through here so behaviour is consistent:
  * loads never crash on missing / empty / corrupt files
  * writes are ATOMIC (temp file + os.replace) so a crash or a killed
    daemon thread can never leave a half-written, corrupt JSON save.
  * optional in-memory transactions batch all writes for one sim tick / player turn

BASE_DIR is the project root (the folder that contains world/, characters/,
simulation/, ...). It is on sys.path because src/main.py inserts it.
"""

import json
import os
import tempfile
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Runtime files mutated by simulation + story loop (save slots mirror this set).
MANAGED_PATHS = (
    "player/player.json",
    "world/world_state.json",
    "world/locations.json",
    "world/areas.json",
    "world/institutions.json",
    "world/factions.json",
    "characters/npcs.json",
    "characters/monsters.json",
    "characters/relationships.json",
    "characters/memories.json",
    "characters/npc_memories.json",
    "characters/_mem_state.json",
    "rumors/rumors.json",
    "events/event_log.json",
)

_tx = threading.local()


def full_path(relpath):
    return os.path.join(BASE_DIR, relpath)


def in_transaction():
    return getattr(_tx, "state", None) is not None


def begin_transaction():
    """Load all managed paths into memory. Caller must hold tick lock."""
    if in_transaction():
        raise RuntimeError("Storage transaction already active")
    from game.game_state import GameState
    _tx.state = GameState.load_all()


def commit_transaction():
    """Flush in-memory state to disk."""
    state = getattr(_tx, "state", None)
    if state is None:
        return
    flush_active_state()
    _tx.state = None


def rollback_transaction():
    """Discard in-memory changes."""
    _tx.state = None


def get_active_state():
    return getattr(_tx, "state", None)


def _disk_load(relpath, default=None):
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


def _disk_save(relpath, data):
    path = full_path(relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        try:
            os.replace(tmp, path)
        except OSError:
            if os.path.exists(path):
                os.remove(path)
            os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def load(relpath, default=None):
    """Load JSON. Returns `default` ({} if not given) on any failure."""
    state = get_active_state()
    if state is not None and relpath in MANAGED_PATHS:
        if default is None:
            default = {}
        return state.get(relpath, default)
    return _disk_load(relpath, default)


def save(relpath, data):
    """Write JSON — managed paths use active transaction; others write disk immediately."""
    state = get_active_state()
    if state is not None and relpath in MANAGED_PATHS:
        state.set(relpath, data)
        return
    _disk_save(relpath, data)


def flush_active_state():
    """Write in-memory transaction to disk (used by commit_transaction)."""
    state = get_active_state()
    if state is None:
        return
    for path, data in state._data.items():
        _disk_save(path, data)
