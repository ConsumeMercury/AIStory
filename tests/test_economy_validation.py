"""Validate-or-refuse for trade, give, acquire, and accuse."""

from simulation.economy_engine import (
    validate_trade,
    validate_give,
    parse_give_amount,
    resolve_trade,
    resolve_give,
)
from simulation.action_resolution import validate_acquire_item, try_acquire_item
from simulation.investigation_engine import validate_accuse
from simulation.action_interpreter import speech_for_ask_about, extract_player_speech


def _priestess():
    return {
        "id": "p1",
        "name": "Sister Mara",
        "role": "priest",
        "gender": "female",
        "inventory": [],
        "wealth": 10,
    }


def _merchant_with_sword():
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


def test_trade_refuses_non_vendor():
    ok, msg, item = validate_trade("Buy a sword from the priestess", _priestess())
    assert not ok
    assert "nothing to sell" in msg.lower()
    assert item is None


def test_trade_refuses_missing_stock():
    merchant = _merchant_with_sword()
    merchant["inventory"] = []
    ok, msg, item = validate_trade("Buy a sword", merchant)
    assert not ok
    assert item is None


def test_trade_succeeds_with_vendor_stock():
    ok, msg, item = validate_trade("Buy a sword", _merchant_with_sword())
    assert ok
    assert item is not None


def test_trade_does_not_mutate_wealth_when_refused():
    player = {"wealth": 30, "inventory": []}
    npc = _priestess()
    ok, _, sale_item = validate_trade("Buy a sword", npc)
    assert not ok
    directive, changed, _ = resolve_trade(player, npc, True, sale_item=sale_item)
    assert not changed
    assert player["wealth"] == 30
    assert "REFUSED" in directive


def test_give_uses_authoritative_wealth_cap():
    player = {"wealth": 22}
    assert parse_give_amount("Give the priestess 500 silver", player) == 22


def test_give_transfers_exact_amount():
    player = {"wealth": 22, "inventory": []}
    npc = _priestess()
    ok, _, amount = validate_give("Give 500 silver", player, npc)
    assert ok
    assert amount == 22
    directive, changed, _ = resolve_give(player, npc, True, amount=amount)
    assert changed
    assert player["wealth"] == 0
    assert "22 coin" in directive


def test_pick_up_body_refuses_and_adds_no_item():
    player = {"wealth": 0, "inventory": []}
    ok, msg = validate_acquire_item("Pick up the body", player, {"type": "district"})
    assert not ok
    note, item = try_acquire_item("Pick up the body", player, {"type": "district"}, tick=1)
    assert note is None
    assert item is None
    assert not player["inventory"]


def test_accuse_refused_without_active_case():
    priestess = _priestess()
    ok, msg = validate_accuse(
        "Accuse the priestess of killing Zaya",
        {"active_case": None},
        priestess,
        {"p1": priestess},
    )
    assert not ok
    assert "no active investigation" in msg.lower()


def test_clause_ask_produces_no_broken_speech():
    action = "Ask her why she didn't go into the woods"
    assert speech_for_ask_about(action) is None
    speech = extract_player_speech(action, {}, kind="ask_about")
    assert speech is None


def test_noun_topic_ask_still_works():
    action = "Ask her about the wood-pile trial"
    speech = speech_for_ask_about(action)
    assert speech
    assert "wood-pile trial" in speech.lower()
