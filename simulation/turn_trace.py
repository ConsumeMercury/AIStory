"""
In-memory trace of the last player turn — for debugging without digging through JSON.

Read via GET /api/debug/last-turn when AISTORY_DEBUG=1, or import get_last_turn().
Ring buffer of recent boundary metrics when AISTORY_BOUNDARY_HISTORY is set.
"""

import os

_last = {}
_history = []
_HISTORY_LIMIT = 50


def _history_limit():
    raw = os.environ.get("AISTORY_BOUNDARY_HISTORY", "20")
    try:
        return max(0, min(100, int(raw)))
    except ValueError:
        return 20


def record_turn(**fields):
    global _last
    _last = {k: v for k, v in fields.items() if v is not None}
    boundary = fields.get("boundary")
    if boundary and _history_limit() > 0:
        global _history
        entry = {
            "tick": fields.get("tick"),
            "action": (fields.get("action") or "")[:80],
            "kind": fields.get("kind"),
            "boundary": boundary,
            "tagged_issues": fields.get("tagged_issues"),
        }
        _history.append(entry)
        cap = _history_limit()
        if len(_history) > cap:
            _history = _history[-cap:]


def get_last_turn():
    return dict(_last)


def get_boundary_history():
    return list(_history)


def get_boundary_summary():
    """Aggregate counters from in-memory history (current session)."""
    hist = _history
    if not hist:
        return {}
    n = len(hist)
    invoked = sum(1 for h in hist if (h.get("boundary") or {}).get("classifier_invoked"))
    disagrees = sum(1 for h in hist if (h.get("boundary") or {}).get("classifier_disagrees"))
    facts_emitted = sum(
        1 for h in hist if (h.get("boundary") or {}).get("facts", {}).get("has_facts")
    )
    facts_expected = sum(1 for h in hist if (h.get("boundary") or {}).get("facts_expected"))
    facts_missing = sum(1 for h in hist if (h.get("boundary") or {}).get("facts_missing"))
    gate = sum(1 for h in hist if (h.get("boundary") or {}).get("gate_active"))
    return {
        "turns_in_history": n,
        "classifier_invoked": invoked,
        "classifier_disagrees": disagrees,
        "facts_emitted": facts_emitted,
        "facts_expected": facts_expected,
        "facts_missing": facts_missing,
        "gate_violations": gate,
        "classifier_invoked_rate": round(invoked / n, 3) if n else 0,
        "facts_emission_rate": round(facts_emitted / n, 3) if n else 0,
        "auditor_invoked": sum(1 for h in hist if (h.get("boundary") or {}).get("auditor_invoked")),
        "auditor_confirmed_total": sum(
            (h.get("boundary") or {}).get("auditor_confirmed", 0) for h in hist
        ),
        "facts_miss_rate": round(facts_missing / facts_expected, 3) if facts_expected else 0,
    }
