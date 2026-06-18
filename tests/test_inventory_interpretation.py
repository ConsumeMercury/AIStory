"""Inventory-dependent interpretation and narrator-state gating."""

from simulation.action_interpretation import attach_inventory_checks
from simulation.action_interpreter import interpret_action
from simulation.prose_assertion_guard import issues_block_narrator_registration
from tests.fixtures.catalog_fixtures import npc, player


def test_show_badge_without_item_flags_missing():
    pl = player(wealth=10)
    pl["inventory"] = [{"id": "coin_pouch", "name": "coin pouch"}]
    ctx = {"kind": "talk", "story_directive": ""}
    attach_inventory_checks("show her the guild badge", pl, ctx)
    assert ctx.get("inventory_missing")
    assert "badge" in ctx["inventory_missing"][0].lower()
    assert "MISSING ITEM" in ctx.get("story_directive", "")


def test_show_item_player_has_not_flagged():
    pl = player(wealth=10)
    pl["inventory"] = [{"id": "badge1", "name": "guild badge"}]
    ctx = {"kind": "talk", "story_directive": ""}
    attach_inventory_checks("show her the guild badge", pl, ctx)
    assert not ctx.get("inventory_missing")


def test_unlock_without_key():
    pl = player()
    pl["inventory"] = []
    ctx = {"kind": "general", "story_directive": ""}
    attach_inventory_checks("unlock the door", pl, ctx)
    assert ctx.get("inventory_missing")
    assert "NO KEY" in ctx.get("story_directive", "")


def test_issues_block_narrator_registration():
    assert issues_block_narrator_registration([
        "prose asserts receiving an item but simulation did not grant acquisition",
    ])
    assert not issues_block_narrator_registration(["minor prose style issue"])


def test_interpret_show_missing_in_trace():
    pl = player()
    pl["inventory"] = []
    present = [npc("m1", name="Mara", gender="female")]
    ctx = interpret_action("show Mara the letter", pl, present, {})
    trace = ctx.get("interpretation_trace") or {}
    assert trace.get("inventory_missing")
