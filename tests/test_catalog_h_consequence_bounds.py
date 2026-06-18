"""
Catalog H — consequence propagation bounds (priority 4).
"""

import copy

from simulation.consequence_propagation import propagate, template_for_fatal_kill


def _merchant_ctx():
    player = {"area": "city:market", "pending_consequences": [], "institution_standing": {}}
    areas = {
        "city:market": {"state": {"prosperity": 50, "crime_level": 20, "flags": {}}},
        "city:docks": {"state": {"prosperity": 60, "crime_level": 10, "flags": {}}},
    }
    target = {
        "id": "m1",
        "name": "Hadd",
        "role": "merchant",
        "status": "dead",
        "area": "city:market",
        "location": "city",
        "institution": {"id": "guild1"},
    }
    institutions = {"guild1": {"type": "guild", "city": "city", "name": "Merchants Guild"}}
    return player, areas, target, institutions


def test_merchant_death_triggers_bounded_cascade():
    player, areas, target, institutions = _merchant_ctx()
    changed, trace = propagate(
        "fatal_kill_merchant",
        player=player,
        world={"day": 3},
        areas=areas,
        target_npc=target,
        institutions=institutions,
        memory_id="mem1",
        tick=10,
    )
    assert changed
    assert trace["template"] == "fatal_kill_merchant"
    assert areas["city:market"]["state"]["prosperity"] < 50
    assert areas["city:market"]["state"]["flags"].get("trade_disrupted")
    assert player.get("emergent_hooks")


def test_cascade_does_not_over_propagate():
    player, areas, target, institutions = _merchant_ctx()
    docks_before = areas["city:docks"]["state"]["prosperity"]
    propagate(
        "fatal_kill_merchant",
        player=player,
        world={"day": 1},
        areas=areas,
        target_npc=target,
        institutions=institutions,
        tick=5,
    )
    assert areas["city:docks"]["state"]["prosperity"] == docks_before


def test_cascade_effects_are_idempotent_on_area_flags():
    player, areas, target, institutions = _merchant_ctx()
    propagate(
        "fatal_kill_merchant",
        player=player,
        world={"day": 1},
        areas=areas,
        target_npc=target,
        institutions=institutions,
        tick=5,
    )
    pending_after_first = len(player["pending_consequences"])
    flags_after_first = dict(areas["city:market"]["state"]["flags"])
    propagate(
        "fatal_kill_merchant",
        player=player,
        world={"day": 2},
        areas=areas,
        target_npc=target,
        institutions=institutions,
        tick=6,
    )
    assert areas["city:market"]["state"]["flags"] == flags_after_first
    assert len(player["pending_consequences"]) > pending_after_first


def test_authority_death_distinct_from_merchant():
    assert template_for_fatal_kill({"role": "merchant"}) == "fatal_kill_merchant"
    assert template_for_fatal_kill({"role": "guard"}) == "fatal_kill_authority"
    player, areas, _, institutions = _merchant_ctx()
    guard = {
        "id": "g1",
        "name": "Holt",
        "role": "guard",
        "status": "dead",
        "area": "city:market",
    }
    _, merchant_trace = propagate(
        "fatal_kill_merchant",
        player=copy.deepcopy(player),
        world={"day": 1},
        areas=copy.deepcopy(areas),
        target_npc={"id": "m1", "role": "merchant", "name": "Hadd", "status": "dead"},
        institutions=institutions,
        tick=1,
    )
    _, guard_trace = propagate(
        "fatal_kill_authority",
        player=player,
        world={"day": 1},
        areas=areas,
        target_npc=guard,
        institutions=institutions,
        tick=1,
    )
    assert merchant_trace["template"] != guard_trace["template"]
    merchant_effects = {s["effect"] for s in merchant_trace["steps"]}
    guard_effects = {s["effect"] for s in guard_trace["steps"]}
    assert merchant_effects != guard_effects


def test_emergent_hook_generated_from_high_importance():
    player, areas, target, institutions = _merchant_ctx()
    _, trace = propagate(
        "fatal_kill_merchant",
        player=player,
        world={"day": 1},
        areas=areas,
        target_npc=target,
        institutions=institutions,
        memory_id="mem_hook",
        tick=5,
    )
    assert player.get("emergent_hooks")
    assert any(h.get("kind") == "trade_vacuum" for h in player["emergent_hooks"])


def test_delayed_consequences_queue_correctly():
    player, areas, target, institutions = _merchant_ctx()
    propagate(
        "fatal_kill_merchant",
        player=player,
        world={"day": 5},
        areas=areas,
        target_npc=target,
        institutions=institutions,
        tick=10,
    )
    queued = player["pending_consequences"]
    assert queued
    assert all(q.get("fires_at_day", 0) > 5 for q in queued)
