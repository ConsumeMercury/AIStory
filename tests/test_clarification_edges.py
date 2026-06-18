"""Clarification flow edge cases."""

from simulation.target_ambiguity import (
    should_abandon_clarification,
    resolve_clarification_pick,
    note_pending_pick_failed,
    pending_clarification_exhausted,
)
from tests.fixtures.catalog_fixtures import npc, player


def test_abandon_clarification_on_new_action():
    pl = player(scene_focus=None)
    pl["pending_target_clarification"] = {
        "kind": "attack",
        "options": [{"id": "a", "chip": "attack Holt"}],
    }
    assert should_abandon_clarification("explore the market", pl)


def test_clarification_pick_by_constraint_gender():
    a = npc("a", role="guard", name="Holt", gender="male")
    b = npc("b", role="merchant", name="Mara", gender="female")
    pl = player(scene_focus=None)
    pl["pending_target_clarification"] = {
        "kind": "talk",
        "options": [
            {"id": "a", "label": "Holt (guard)", "chip": "talk to Holt"},
            {"id": "b", "label": "Mara (merchant)", "chip": "talk to Mara"},
        ],
    }
    kind, nid = resolve_clarification_pick(
        "talk to the woman", pl, [a, b], {"a": a, "b": b},
    )
    assert kind == "talk"
    assert nid == "b"


def test_failed_pick_increments_fail_count():
    pl = player(scene_focus=None)
    pl["pending_target_clarification"] = {
        "kind": "talk",
        "options": [{"id": "a", "chip": "talk to Holt"}],
        "fail_count": 0,
    }
    a = npc("a", role="guard", name="Holt")
    kind, nid = resolve_clarification_pick("maybe later", pl, [a], {"a": a})
    assert kind is None
    assert pl["pending_target_clarification"]["fail_count"] == 1


def test_pending_exhausted_after_max_failures():
    pl = player(scene_focus=None)
    pl["pending_target_clarification"] = {"fail_count": 3}
    assert pending_clarification_exhausted(pl)
