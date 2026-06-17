"""
Undo last player turn — restores pre-action snapshots of managed state.
"""

import copy

from storage import load, save, MANAGED_PATHS

UNDO_FILE = "player/_undo.json"
PLAYER_FILE = "player/player.json"

_UNDO_PATHS = (
    "player/player.json",
    "characters/npcs.json",
    "characters/monsters.json",
    "world/world_state.json",
    "characters/relationships.json",
    "world/areas.json",
    "world/institutions.json",
    "world/factions.json",
    "rumors/rumors.json",
    "events/event_log.json",
)


def push_undo_snapshot():
    """Call at start of a player turn (inside state transaction)."""
    player = load(PLAYER_FILE, {})
    if not player:
        return
    journal = player.get("journal") or []
    snapshots = {}
    for path in _UNDO_PATHS:
        if path in MANAGED_PATHS:
            snapshots[path] = copy.deepcopy(load(path, {}))
    save(UNDO_FILE, {
        "player": copy.deepcopy(player),
        "journal_len": len(journal),
        "snapshots": snapshots,
    })


def can_undo():
    undo = load(UNDO_FILE, {})
    player = load(PLAYER_FILE, {})
    if not undo or not player:
        return False
    return len(player.get("journal") or []) > undo.get("journal_len", 0)


def undo_last_turn():
    undo = load(UNDO_FILE, {})
    if not undo:
        raise RuntimeError("Nothing to undo.")
    player = load(PLAYER_FILE, {})
    journal = player.get("journal") or []
    if len(journal) <= undo.get("journal_len", 0):
        raise RuntimeError("Nothing to undo.")
    snapshots = undo.get("snapshots") or {}
    for path, data in snapshots.items():
        save(path, copy.deepcopy(data))
    restored = copy.deepcopy(undo["player"])
    save(PLAYER_FILE, restored)
    return restored
