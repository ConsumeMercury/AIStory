"""
Undo last player turn — restores pre-action player snapshot.
"""

import copy

from storage import load, save

UNDO_FILE = "player/_undo.json"
PLAYER_FILE = "player/player.json"


def push_undo_snapshot():
    """Call at start of a player turn (inside state transaction)."""
    player = load(PLAYER_FILE, {})
    if not player:
        return
    journal = player.get("journal") or []
    save(UNDO_FILE, {
        "player": copy.deepcopy(player),
        "journal_len": len(journal),
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
    restored = copy.deepcopy(undo["player"])
    save(PLAYER_FILE, restored)
    return restored