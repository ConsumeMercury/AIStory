"""
Player trade and gift mechanics — coin and items actually move.
All mutations require validate-or-refuse checks first (see validate_trade / validate_give).
"""

import re
import random

from simulation.event_logger import log_event

VENDOR_ROLES = frozenset({"merchant", "innkeeper", "trader", "blacksmith", "sailor"})

_ITEM_KEYWORDS = (
    (re.compile(r"\b(sword|blade|cutlass|sabre|saber)\b", re.I), "weapon", "sword"),
    (re.compile(r"\b(dagger|knife|stiletto)\b", re.I), "weapon", "dagger"),
    (re.compile(r"\b(axe|hatchet)\b", re.I), "weapon", "axe"),
    (re.compile(r"\b(bow|arrow)\b", re.I), "weapon", "bow"),
    (re.compile(r"\b(armor|armour|coat|vest|jack)\b", re.I), "armor", "armor"),
    (re.compile(r"\b(weapon|blade|steel)\b", re.I), "weapon", "sword"),
)

_GIVE_AMOUNT = re.compile(r"\b(\d+)\s*(?:coin|coins|silver|copper|gold)?\b", re.I)
_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "a": 1, "an": 1, "couple": 2, "few": 3, "handful": 5,
}


def parse_give_amount(action, player):
    """Authoritative coin amount the player intends to give (capped at wealth)."""
    wealth = max(0, int(player.get("wealth") or 0))
    if wealth <= 0:
        return 0
    text = action or ""
    m = _GIVE_AMOUNT.search(text)
    if m:
        return min(wealth, int(m.group(1)))
    wm = re.search(
        r"\b(" + "|".join(_WORD_NUMBERS.keys()) + r")\s+(?:coin|coins|silver|copper|gold|pieces?)\b",
        text,
        re.I,
    )
    if wm:
        return min(wealth, _WORD_NUMBERS.get(wm.group(1).lower(), 0))
    if re.search(r"\bgive\s+all\b|\ball\s+(?:my\s+)?(?:money|coin|silver|gold)\b", text, re.I):
        return wealth
    if re.search(r"\bgive\b", text, re.I):
        return wealth
    return 0


_BUY_VERBS = re.compile(r"\b(buy|purchase|trade for|barter for)\b", re.I)


def _npc_is_vendor(npc):
    if not npc:
        return False
    role = (npc.get("role") or "").lower()
    occ = (npc.get("occupation") or "").lower()
    if role in VENDOR_ROLES:
        return True
    return any(k in occ for k in ("merchant", "trader", "vendor", "shop", "stall"))


def _find_sale_item(npc, action):
    """Return inventory item matching a named purchase, or None."""
    inv = npc.get("inventory") or []
    if not inv or not action:
        return None
    for pattern, category, item_type in _ITEM_KEYWORDS:
        if not pattern.search(action):
            continue
        for item in inv:
            if not isinstance(item, dict):
                continue
            name = (item.get("name") or "").lower()
            cat = (item.get("category") or "").lower()
            itype = (item.get("type") or item.get("item_type") or "").lower()
            if item_type in name or item_type in itype or cat == category:
                return item
        return None
    return None


def _action_names_item(action):
    return any(p.search(action or "") for p, _, _ in _ITEM_KEYWORDS)


def validate_trade(action, npc):
    """
    Refuse before any wealth mutation.
    Returns (ok, refusal_message, sale_item_or_none).
    """
    if not npc:
        return False, "There is no one here to trade with.", None

    if not _npc_is_vendor(npc):
        label = npc.get("name") or npc.get("role") or "They"
        return False, f"{label} has nothing to sell.", None

    inv = npc.get("inventory") or []
    names_item = _action_names_item(action)

    if names_item:
        item = _find_sale_item(npc, action)
        if not item:
            return False, "There is no such item for sale here.", None
        return True, "", item

    if _BUY_VERBS.search(action or ""):
        if not inv:
            return False, "They have nothing to sell.", None
        return True, "", random.choice(inv)

    if not inv:
        return False, "They have nothing to sell.", None

    return True, "", None


def validate_give(action, player, npc):
    """Refuse before wealth mutation. Returns (ok, message, amount)."""
    if not npc:
        return False, "There is no one here to give to.", 0
    amount = parse_give_amount(action, player)
    if amount <= 0:
        return False, "You have no coin to give.", 0
    return True, "", amount


def _remove_npc_item(npc, item):
    inv = npc.get("inventory") or []
    npc["inventory"] = [i for i in inv if i.get("id") != item.get("id")]
    item = dict(item)
    item["owner"] = "player"
    return item


def resolve_trade(player, npc, success, tick=None, location=None, *, sale_item=None):
    """
    On success: player buys a validated item — coin moves.
    Returns (directive_text, player_changed, npc_changed).
    """
    if sale_item is None:
        return (
            "TRADE REFUSED — no goods change hands; wealth unchanged.",
            False, False,
        )

    p_wealth = player.get("wealth", 0)
    n_wealth = npc.get("wealth", random.randint(20, 80))
    npc.setdefault("wealth", n_wealth)

    if not success:
        return (
            "The deal falls apart — no coin or goods change hands.",
            False, False,
        )

    price = max(5, int(sale_item.get("value", 20) * random.uniform(0.85, 1.15)))
    if p_wealth < price:
        return (
            f"You cannot afford {sale_item.get('name', 'that')} ({price} coin). "
            "No wealth deducted.",
            False, False,
        )

    player["wealth"] = p_wealth - price
    npc["wealth"] = n_wealth + price
    gained = _remove_npc_item(npc, sale_item)
    player.setdefault("inventory", []).append(gained)
    log_event("trade", "player", "trade", target=npc.get("id"),
              location=location, effects=[gained.get("name", "goods")], tick=tick)
    rarity = gained.get("rarity", "common")
    mods = gained.get("stat_mods") or {}
    mod_hint = ""
    if mods:
        mod_hint = " (" + ", ".join(f"+{v} {k}" for k, v in mods.items()) + ")"
    return (
        f"MECHANICAL FACT: {price} coin deducted; wealth now {player['wealth']}. "
        f"Player acquires {gained.get('name', 'something')} [{rarity}]{mod_hint}. "
        f"Describe exactly this exchange — do not invent other prices or goods.",
        True, True,
    )


def resolve_give(player, npc, success, tick=None, location=None, *, amount=0):
    """Offer coin to the focal NPC — amount is simulation-authoritative."""
    if amount <= 0:
        return (
            "GIVE REFUSED — you have nothing to give; wealth unchanged.",
            False, False,
        )

    if not success:
        return (
            "The offer is refused or misread — no coin changes hands.",
            False, False,
        )

    wealth_before = player.get("wealth", 0)
    if wealth_before < amount:
        return (
            "You do not have that much coin.",
            False, False,
        )

    player["wealth"] = wealth_before - amount
    npc["wealth"] = npc.get("wealth", 0) + amount
    log_event("help", "player", "help", target=npc.get("id"),
              location=location, effects=[f"{amount}_coin"], tick=tick)
    return (
        f"MECHANICAL FACT: {amount} coin given; your wealth is now {player['wealth']}. "
        f"Describe exactly {amount} coin — single unit, no invented denominations.",
        True, True,
    )
