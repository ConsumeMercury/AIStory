"""Catalog D — economy & inventory."""

import storage

from simulation.action_resolution import build_inventory_facts, try_acquire_item, validate_acquire_item
from simulation.economy_engine import resolve_give, resolve_trade, validate_give, validate_trade
from simulation.narrator_items import (
    consume_narrator_item,
    match_narrator_item_pickup,
    record_narrator_items,
)
from tests.fixtures.isolated_game import bootstrap_isolated_game, run_mocked_actions


def _merchant():
    return {
        "id": "m1",
        "name": "Tomas",
        "role": "merchant",
        "inventory": [{
            "id": "s1",
            "name": "Notched Blade",
            "category": "weapon",
            "type": "sword",
            "value": 20,
        }],
        "wealth": 50,
    }


def _priest():
    return {"id": "p1", "name": "Sister Mara", "role": "priest", "wealth": 10, "inventory": []}


def test_trade_with_non_vendor_refused():
    ok, msg, item = validate_trade("Buy a sword", _priest())
    assert not ok
    assert item is None
    assert "nothing to sell" in msg.lower() or "vendor" in msg.lower() or "sell" in msg.lower()


def test_trade_refusal_does_not_mutate_wealth():
    pl = {"wealth": 30, "inventory": []}
    ok, _, sale_item = validate_trade("Buy a sword", _priest())
    assert not ok
    directive, changed, _ = resolve_trade(pl, _priest(), ok, sale_item=sale_item)
    assert not changed
    assert pl["wealth"] == 30
    assert "REFUSED" in directive


def test_trade_success_mutates_both_parties():
    pl = {"wealth": 50, "inventory": []}
    npc = _merchant()
    ok, _, sale_item = validate_trade("Buy a sword", npc)
    assert ok
    directive, changed, _ = resolve_trade(pl, npc, ok, sale_item=sale_item)
    assert changed
    assert pl["wealth"] < 50
    assert pl["inventory"]
    assert not npc["inventory"]


def test_give_uses_authoritative_amount():
    pl = {"wealth": 15, "inventory": []}
    npc = _priest()
    ok, _, amount = validate_give("Give 500 silver", pl, npc)
    assert ok
    assert amount == 15
    _, changed, _ = resolve_give(pl, npc, ok, amount=amount)
    assert changed
    assert pl["wealth"] == 0


def test_give_respects_wealth_floor():
    pl = {"wealth": 0, "inventory": []}
    ok, msg, amount = validate_give("Give 10 silver", pl, _priest())
    assert not ok or amount == 0
    assert pl["wealth"] >= 0


def test_acquire_nonexistent_item_fails():
    pl = {"wealth": 0, "inventory": [], "narrator_items": {}}
    ok, _msg = validate_acquire_item("pick up something vague", pl, {"type": "district"})
    assert not ok
    note, item = try_acquire_item("pick up something vague", pl, {"type": "district"}, tick=1)
    assert item is None
    assert not pl["inventory"]


def test_acquire_scene_item_succeeds():
    pl = {"narrator_items": {}, "inventory": [], "area": "city:market"}
    scene = "You notice a parchment scrap half-hidden at your feet near the gutter."
    assert record_narrator_items(pl, scene, "city:market", tick=1)
    matched = match_narrator_item_pickup("pick up the parchment scrap", pl, "city:market")
    assert matched
    assert consume_narrator_item(pl, "city:market", matched["id"])
    pl["inventory"].append({"id": matched["id"], "name": matched["label"]})
    assert pl["inventory"]


def test_inventory_persists_across_beats(tmp_path, monkeypatch):
    bootstrap_isolated_game(tmp_path, monkeypatch)
    pl = storage.load("player/player.json", {})
    pl["inventory"] = [{"id": "scrap1", "name": "Parchment scrap", "category": "material"}]
    storage.save("player/player.json", pl)

    run_mocked_actions(["Wait until dawn"], lambda _kw: "[scene]")
    pl = storage.load("player/player.json", {})
    assert any(i.get("id") == "scrap1" for i in (pl.get("inventory") or []))


def test_build_inventory_facts_lists_items():
    pl = {"inventory": [{"name": "Notched Blade", "category": "weapon"}]}
    facts = build_inventory_facts(pl, {"acquired_item": {"name": "Notched Blade", "rarity": "common"}})
    assert "Notched Blade" in facts
