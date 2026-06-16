"""
Thread-local state transactions guarded by the simulation tick lock.
"""

import logging
import threading
from contextlib import contextmanager

from game.game_state import GameState
from storage import begin_transaction, commit_transaction, rollback_transaction, in_transaction
from simulation.locks import get_tick_lock

log = logging.getLogger(__name__)
_depth = threading.local()


def _depth_get():
    return getattr(_depth, "n", 0)


def _depth_set(n):
    _depth.n = n


@contextmanager
def state_lock():
    """
    Acquire tick lock and open a storage transaction.
    Nested calls share one transaction; only the outermost commit flushes to disk.
    """
    lock = get_tick_lock()
    lock.acquire()
    depth = _depth_get()
    if depth == 0:
        begin_transaction()
    _depth_set(depth + 1)
    try:
        yield
    except Exception:
        if _depth_get() == 1:
            rollback_transaction()
            log.exception("state transaction rolled back")
        raise
    finally:
        d = _depth_get() - 1
        _depth_set(d)
        if d == 0:
            commit_transaction()
        lock.release()


@contextmanager
def state_lock_readonly():
    """Load state under lock without opening a write transaction."""
    lock = get_tick_lock()
    lock.acquire()
    try:
        if not in_transaction():
            begin_transaction()
            try:
                yield
                commit_transaction()
            except Exception:
                rollback_transaction()
                raise
        else:
            yield
    finally:
        lock.release()
