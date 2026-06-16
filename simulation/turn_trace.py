"""
In-memory trace of the last player turn — for debugging without digging through JSON.

Read via GET /api/debug/last-turn when AISTORY_DEBUG=1, or import get_last_turn().
"""

_last = {}


def record_turn(**fields):
    global _last
    _last = {k: v for k, v in fields.items() if v is not None}


def get_last_turn():
    return dict(_last)
