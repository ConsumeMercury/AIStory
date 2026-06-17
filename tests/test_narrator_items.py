"""Narrator-foregrounded items — register from prose, resolve on pickup."""

from simulation.narrator_items import (
    extract_narrator_items,
    record_narrator_items,
    match_narrator_item_pickup,
    consume_narrator_item,
)
from simulation.action_resolution import validate_acquire_item, try_acquire_item


def test_extract_parchment_from_prose():
    scene = (
        "You notice a parchment scrap half-hidden under a loose cobble, "
        "its edge singed by lamp-oil."
    )
    items = extract_narrator_items(scene)
    assert items
    assert any("parchment" in i["label"].lower() for i in items)


def test_record_and_pickup_parchment():
    player = {"area": "stormbridge:docks", "inventory": [], "equipment": {}}
    scene = "You see a parchment scrap lying at your feet near the chutes."
    assert record_narrator_items(player, scene, "stormbridge:docks", tick=1)
    ok, msg = validate_acquire_item("pick up the parchment scrap", player, {"id": "stormbridge:docks", "type": "district"})
    assert ok, msg
    matched = match_narrator_item_pickup("pick up the parchment scrap", player, "stormbridge:docks")
    assert matched
    note, item = try_acquire_item(
        "pick up the parchment scrap", player,
        {"id": "stormbridge:docks", "type": "district"}, tick=2,
    )
    assert note
    assert item
    assert player.get("inventory")
    assert consume_narrator_item(player, "stormbridge:docks", matched["id"]) is False


def test_coal_chute_location_does_not_register_schedulable_item():
    scene = "The coal chutes rise ahead, dark gaping mouths against the sky."
    assert not extract_narrator_items(scene)


def test_pickup_still_refuses_unregistered():
    player = {"area": "stormbridge:docks", "narrator_items": {}}
    ok, msg = validate_acquire_item("pick up the mystery widget", player, {"id": "stormbridge:docks"})
    assert not ok
    assert "nothing here to pick up" in msg.lower()
