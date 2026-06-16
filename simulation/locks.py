"""Shared tick lock — avoids import cycles between runner and state_context."""

import threading

_tick_lock = threading.Lock()


def get_tick_lock():
    return _tick_lock
