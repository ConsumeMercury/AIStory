"""Shared tick lock — avoids import cycles between runner and state_context."""

import threading

_tick_lock = threading.RLock()


def get_tick_lock():
    return _tick_lock
