"""
Item engine — loot rolls, equipment, consumables, combat stat bonuses.
"""

import random
import copy

from generation.id_generator import generate_id
from generation.item_generator import (
    generate_item, roll_rarity, RARITIES, RARITY_ORDER, RARITY_MULTIPLIER,
    NAMED_TEMPLATES,
)

# species -> drop configuration
SPECIES_LOOT = {
    "wolf": {
        "source": "monster",
        "templates": ["grey pelt", "wolf fang"],
        "extra_categories": ["material"],
        "coin": (2, 10),
    },
    "bandit": {
        "source": "bandit",
        "templates": ["stolen coin purse", "notched blade"],
        "extra_categories": ["weapon", "trinket"],
        "coin": (5, 22),
        "rarity_shift": 1,
    },
    "bog_lurker": {
        "source": "monster_elite",
        "templates": ["lurker scale", "reeking gland"],
        "extra_categories": ["reagent"],
        "coin": (4, 14),
        "rarity_shift": 1,
    },
    "ghoul": {
        "source": "monster",
        "templates": ["grave dust", "tarnished ring"],
        "extra_categories": ["reagent", "trinket"],
        "coin": (3, 12),
        "rarity_shift": 1,
    },
    "dire_boar": {
        "source": "monster_elite",
        "templates": ["boar tusk", "smoked haunch"],
        "extra_categories": ["trophy", "consumable"],
        "coin": (6, 18),
        "rarity_shift": 1,
    },
    "wraith": {
        "source": "monster_elite",
        "templates": ["cold shard"],
        "extra_categories": ["reagent", "trinket"],
        "coin": (8, 25),
        "rarity_shift": 2,
    },
    "bone_stalker": {
        "source": "monster_elite",
        "templates": ["knucklebone charm", "marrow vial"],
        "extra_categories": ["reagent"],
        "coin": (5, 20),
        "rarity_shift": 1,
    },
    "marsh_adder": {
        "source": "monster",
        "templates": ["adder venom", "striped hide"],
        "extra_categories": ["reagent"],
        "coin": (2, 9),
    },
}

ROLE_LOOT_BIAS = {
    "merchant": ("merchant", ["trinket", "material", "consumable"]),
    "blacksmith": ("merchant", ["weapon", "armor", "material"]),
    "guard": ("guild", ["weapon", "armor"]),
    "soldier": ("guild", ["weapon", "armor"]),
    "hunter": ("wilderness", ["weapon", "consumable", "trophy"]),
    "priest": ("temple", ["trinket", "consumable", "reagent"]),
    "scholar": ("temple", ["trinket", "reagent", "consumable"]),
    "herbalist": ("merchant", ["consumable", "reagent"]),
    "thief": ("bandit", ["weapon", "trinket", "material"]),
}


def ensure_equipment(player):
    eq = player.setdefault("equipment", {})
    for slot in ("weapon", "armor", "trinket"):
        eq.setdefault(slot, None)
    return eq


def _find_item(player, item_id):
    for item in player.get("inventory") or []:
        if isinstance(item, dict) and item.get("id") == item_id:
            return item
    return None


def equipment_bonuses(player):
    """Sum stat and skill mods from equipped items."""
    ensure_equipment(player)
    stat_mods = {}
    skill_mods = {}
    for slot, iid in player["equipment"].items():
        if not iid:
            continue
        item = _find_item(player, iid)
        if not item:
            continue
        for k, v in (item.get("stat_mods") or {}).items():
            stat_mods[k] = stat_mods.get(k, 0) + v
        for k, v in (item.get("skill_mods") or {}).items():
            skill_mods[k] = skill_mods.get(k, 0) + v
    return stat_mods, skill_mods


def apply_equipment_to_entity(entity):
    """Return combat stats with equipment layered on (does not mutate base)."""
    stats = copy.deepcopy(entity.get("stats") or {})
    if "journal" not in entity:
        return stats
    stat_mods, _ = equipment_bonuses(entity)
    for k, v in stat_mods.items():
        if k in ("max_health", "max_stamina"):
            stats[k] = stats.get(k, 0) + v
            if k == "max_health":
                stats["health"] = min(stats.get("health", 0) + v, stats["max_health"])
        else:
            stats[k] = stats.get(k, 0) + v
    return stats


def equip_item(player, item_id):
    item = _find_item(player, item_id)
    if not item:
        return "No such item in your pack."
    slot = item.get("slot")
    if not slot:
        return f"{item.get('name')} cannot be equipped."
    ensure_equipment(player)
    old = player["equipment"].get(slot)
    player["equipment"][slot] = item_id
    if old and old != item_id:
        old_item = _find_item(player, old)
        oname = old_item.get("name", "item") if old_item else "previous item"
        return f"You equip {item['name']} ({item['rarity']}) — {oname} stowed."
    return f"You equip {item['name']} ({item['rarity']})."


def unequip_item(player, slot):
    ensure_equipment(player)
    if slot not in player["equipment"]:
        return "Unknown slot. Use: weapon, armor, trinket."
    iid = player["equipment"].get(slot)
    if not iid:
        return f"Nothing equipped in {slot}."
    item = _find_item(player, iid)
    player["equipment"][slot] = None
    name = item.get("name", "item") if item else "item"
    return f"You remove {name}."


def use_consumable(player, item_id):
    item = _find_item(player, item_id)
    if not item:
        return "You don't have that.", False
    if item.get("category") != "consumable":
        return "That is not meant to be swallowed or applied.", False
    effect = item.get("effect") or {}
    stats = player.setdefault("stats", {})
    notes = []
    if effect.get("heal"):
        before = stats.get("health", 0)
        stats["health"] = min(stats.get("max_health", 100), before + effect["heal"])
        notes.append(f"health +{stats['health'] - before}")
    if effect.get("stamina"):
        before = stats.get("stamina", 0)
        stats["stamina"] = min(stats.get("max_stamina", 30), before + effect["stamina"])
        notes.append(f"stamina +{stats['stamina'] - before}")
    inv = player.get("inventory") or []
    player["inventory"] = [i for i in inv if i.get("id") != item_id]
    return f"You use {item['name']} ({', '.join(notes) or 'no effect'}).", True


def roll_monster_loot(species, elite=False):
    """Roll drops for a slain beast or bandit."""
    profile = SPECIES_LOOT.get(species, {
        "source": "monster",
        "templates": [],
        "extra_categories": ["trophy", "material"],
        "coin": (2, 8),
    })
    source = profile.get("source", "monster")
    shift = profile.get("rarity_shift", 0)
    if elite:
        shift += 1
        source = "monster_elite"

    drops = []
    templates = list(profile.get("templates") or [])
    if templates:
        for tpl_name in random.sample(templates, k=min(len(templates), random.randint(1, 2))):
            _, item = generate_item(
                template_name=tpl_name,
                source=source,
                rarity=roll_rarity(source, shift=shift),
            )
            drops.append(item)

    if random.random() < 0.35:
        cat = random.choice(profile.get("extra_categories") or ["material"])
        _, item = generate_item(category=cat, source=source, rarity=roll_rarity(source, shift=shift))
        drops.append(item)

    coin_lo, coin_hi = profile.get("coin", (0, 0))
    if coin_lo or coin_hi:
        amount = random.randint(coin_lo, coin_hi)
        if shift >= 2:
            amount = int(amount * 1.4)
        if amount > 0:
            drops.append({
                "id": generate_id("itm"),
                "name": f"{amount} coin",
                "category": "coin",
                "rarity": "common",
                "value": amount,
                "type": "coin",
            })

    return drops


def roll_npc_inventory_item(role):
    from generation.item_generator import CATEGORIES
    source, cats = ROLE_LOOT_BIAS.get(role, ("npc_default", list(CATEGORIES.keys())[:4]))
    cat = random.choice(cats)
    _, item = generate_item(category=cat, source=source)
    return item


def resolve_loot_to_player(player, drops):
    """Add drops to inventory/wealth; return prose summary."""
    gained = []
    coin = 0
    for item in drops:
        if item.get("category") == "coin" or item.get("type") == "coin":
            coin += item.get("value", 0)
        else:
            item["owner"] = "player"
            player.setdefault("inventory", []).append(item)
            tag = item.get("rarity", "common")
            mods = item.get("stat_mods") or {}
            mod_str = ""
            if mods:
                mod_str = " (" + ", ".join(f"+{v} {k}" for k, v in mods.items()) + ")"
            gained.append(f"{item['name']} [{tag}]{mod_str}")
    if coin:
        player["wealth"] = player.get("wealth", 0) + coin
        gained.append(f"{coin} coin")
    if not gained:
        return "You find nothing worth keeping."
    return "Taken: " + "; ".join(gained)


def format_item_line(item):
    if not isinstance(item, dict):
        return f"    • {item}"
    rarity = item.get("rarity", "common")
    slot = item.get("slot")
    slot_note = f", {slot}" if slot else ""
    mods = item.get("stat_mods") or {}
    mod_note = ""
    if mods:
        mod_note = " — " + ", ".join(f"+{v} {k}" for k, v in mods.items())
    skill_mods = item.get("skill_mods") or {}
    if skill_mods:
        mod_note += " skills: " + ", ".join(f"+{v} {k}" for k, v in skill_mods.items())
    effect = item.get("effect")
    if effect:
        mod_note += " use: " + ", ".join(f"{v} {k}" for k, v in effect.items())
    return f"    • {item.get('name', '?')} [{rarity}]{slot_note} — {item.get('value', '?')} coin{mod_note}"


def format_equipment_block(player):
    ensure_equipment(player)
    lines = ["  Equipped:"]
    for slot in ("weapon", "armor", "trinket"):
        iid = player["equipment"].get(slot)
        if not iid:
            lines.append(f"    {slot}: —")
            continue
        item = _find_item(player, iid)
        if item:
            lines.append(f"    {slot}: {item['name']} [{item.get('rarity', '?')}]")
        else:
            lines.append(f"    {slot}: (missing)")
    stat_mods, skill_mods = equipment_bonuses(player)
    if stat_mods or skill_mods:
        parts = [f"+{v} {k}" for k, v in stat_mods.items()]
        parts += [f"+{v} {k} skill" for k, v in skill_mods.items()]
        lines.append("  Bonuses: " + ", ".join(parts))
    return "\n".join(lines)


# backward compat for monster_generator
def roll_loot(species):
    return roll_monster_loot(species)
