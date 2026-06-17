"""Shared tick lock — avoids import cycles between runner and state_context."""

import threading

_tick_lock = threading.RLock()
_action_turn_lock = threading.Lock()


def get_tick_lock():
    return _tick_lock


def get_action_turn_lock():
    """Serializes player turns and deferred post-turn work (e.g. shadow audit)."""
    return _action_turn_lock

