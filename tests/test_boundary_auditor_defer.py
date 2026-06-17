"""Deferred shadow auditor backfills boundary traces."""

from simulation.boundary_metrics import patch_boundary_trace_auditor


def test_patch_boundary_trace_auditor_updates_last_trace():
    player = {
        "last_boundary_trace": {
            "tick": 12,
            "auditor": {"invoked": False, "skip_reason": "deferred_async"},
            "boundary": {"auditor_invoked": False, "auditor_skip_reason": "deferred_async"},
        },
        "boundary_history": [{
            "tick": 12,
            "auditor": {"invoked": False},
            "boundary": {"auditor_invoked": False},
        }],
        "boundary_session": {"auditor_invoked": 0, "auditor_nominations": 0, "auditor_confirmed": 0},
    }
    meta = {
        "mode": "shadow",
        "invoked": True,
        "skip_reason": None,
        "nominations": 2,
        "confirmed": 1,
        "dropped": 1,
        "dropped_samples": [],
    }
    assert patch_boundary_trace_auditor(player, tick=12, auditor_meta=meta)
    assert player["last_boundary_trace"]["auditor"]["invoked"] is True
    assert player["last_boundary_trace"]["auditor"]["nominations"] == 2
    assert player["boundary_session"]["auditor_invoked"] == 1
    assert player["boundary_session"]["auditor_confirmed"] == 1
