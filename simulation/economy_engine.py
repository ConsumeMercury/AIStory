"""
Player trade and gift mechanics — coin and items actually move.
"""

import random

from simulation.event_logger import log_event


def _pick_npc_item(npc):
    inv = npc.get("inventory") or []
    if not inv:
        return None
    return random.choice(inv)


def _remove_npc_item(npc, item):
    inv = npc.get("inventory") or []
    npc["inventory"] = [i for i in inv if i.get("id") != item.get("id")]
    item = dict(item)
    item["owner"] = "player"
    return item


def resolve_trade(player, npc, success, tick=None, location=None):
    """
    On success: player buys from NPC or sells nothing — coin moves.
    Returns (directive_text, player_changed, npc_changed).
    """
    p_wealth = player.get("wealth", 0)
    n_wealth = npc.get("wealth", random.randint(20, 80))
    npc.setdefault("wealth", n_wealth)

    if not success:
        loss = random.randint(2, 8)
        player["wealth"] = max(0, p_wealth - loss)
        return (
            f"The deal falls apart — you lose {loss} coin to pride or a sharper tongue.",
            True, False,
        )

    item = _pick_npc_item(npc)
    if item and p_wealth >= item.get("value", 15):
        price = max(5, int(item.get("value", 20) * random.uniform(0.85, 1.15)))
        if p_wealth >= price:
            player["wealth"] = p_wealth - price
            npc["wealth"] = n_wealth + price
            gained = _remove_npc_item(npc, item)
            player.setdefault("inventory", []).append(gained)
            log_event("trade", "player", "trade", target=npc.get("id"),
                      location=location, effects=[gained.get("name", "goods")], tick=tick)
            rarity = gained.get("rarity", "common")
            mods = gained.get("stat_mods") or {}
            mod_hint = ""
            if mods:
                mod_hint = " (" + ", ".join(f"+{v} {k}" for k, v in mods.items()) + ")"
            return (
                f"Coin changes hands — you acquire {gained.get('name', 'something')} "
                f"[{rarity}]{mod_hint} for {price} coin. The exchange is real; show the weight of it.",
                True, True,
            )

    # coin-only haggle when no item or too poor
    if success:
        discount = random.randint(3, 12)
        player["wealth"] = p_wealth + discount
        npc["wealth"] = max(0, n_wealth - discount)
        log_event("trade", "player", "trade", target=npc.get("id"),
                  location=location, effects=["haggle"], tick=tick)
        return (
            f"You wring {discount} coin from the bargain — small victory, remembered.",
            True, True,
        )

    return ("No goods change hands.", False, False)


def resolve_give(player, npc, success, tick=None, location=None):
    """Offer coin or an item to the focal NPC."""
    if not success:
        return (
            "The offer is refused or misread — awkwardness, not gratitude.",
            False, False,
        )

    inv = player.get("inventory") or []
    if inv and random.random() < 0.55:
        item = inv.pop(0)
        player["inventory"] = inv
        npc.setdefault("inventory", []).append(item)
        item["owner"] = npc.get("id")
        log_event("help", "player", "help", target=npc.get("id"),
                  location=location, effects=[item.get("name", "gift")], tick=tick)
        return (
            f"You give {item.get('name', 'something')} — a real loss, their surprise matters.",
            True, True,
        )

    amount = min(player.get("wealth", 0), random.randint(3, 15))
    if amount > 0:
        player["wealth"] = player.get("wealth", 0) - amount
        npc["wealth"] = npc.get("wealth", 0) + amount
        log_event("help", "player", "help", target=npc.get("id"),
                  location=location, effects=[f"{amount}_coin"], tick=tick)
        return (
            f"You press {amount} coin into their hand. Charity or bribe — they will read it their way.",
            True, True,
        )

    return (
        "You have nothing to give but words — make that enough or not.",
        False, False,
    )
