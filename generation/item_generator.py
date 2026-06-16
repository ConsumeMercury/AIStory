"""
Item catalog — types, rarities, stat mods, and procedural generation.
"""

import random

from generation.id_generator import generate_id

RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]

RARITY_ORDER = {r: i for i, r in enumerate(RARITIES)}

RARITY_MULTIPLIER = {
    "common": 1.0,
    "uncommon": 1.6,
    "rare": 2.8,
    "epic": 5.5,
    "legendary": 12.0,
}

# Weights per loot source — tune where good gear comes from
SOURCE_RARITY_WEIGHTS = {
    "wilderness":   [55, 28, 12, 4, 1],
    "monster":      [45, 28, 18, 7, 2],
    "monster_elite": [20, 30, 30, 15, 5],
    "bandit":       [35, 30, 22, 10, 3],
    "merchant":     [40, 35, 18, 6, 1],
    "guild":        [25, 35, 25, 12, 3],
    "temple":       [30, 30, 25, 12, 3],
    "quest":        [10, 25, 35, 22, 8],
    "npc_default":  [50, 30, 15, 4, 1],
}

ITEM_ADJECTIVES = {
    "common":    ["Worn", "Battered", "Plain", "Old", "Crude", "Road-weary"],
    "uncommon":  ["Sturdy", "Keen", "Polished", "Tempered", "Etched", "Well-made"],
    "rare":      ["Masterwork", "Engraved", "Runed", "Gilded", "Fine", "Trusted"],
    "epic":      ["Ancient", "Bloodforged", "Void-touched", "Dragonbone", "Soulbound"],
    "legendary": ["Mythic", "Worldbreaker", "Eternal", "God-touched", "Abyssal"],
}

# category -> slot, base value range, stat scaling per rarity tier
CATEGORIES = {
    "weapon": {
        "slot": "weapon",
        "types": ["dagger", "sword", "axe", "bow", "staff"],
        "value": (12, 45),
        "mods": {"attack": (1, 4), "speed": (0, 2)},
        "skills": {"swordsmanship": 1, "knife_fighting": 1, "archery": 1},
    },
    "armor": {
        "slot": "armor",
        "types": ["leather coat", "chain vest", "padded jack", "brigandine"],
        "value": (15, 50),
        "mods": {"defense": (1, 5), "max_health": (0, 8)},
        "skills": {},
    },
    "trinket": {
        "slot": "trinket",
        "types": ["ring", "amulet", "charm", "signet"],
        "value": (20, 80),
        "mods": {"attack": (0, 1), "defense": (0, 1), "speed": (0, 1)},
        "skills": {"persuasion": 1, "empathy": 1},
    },
    "consumable": {
        "slot": None,
        "types": ["healing draught", "stamina tonic", "bitter root", "smoked ration"],
        "value": (5, 25),
        "mods": {},
        "effects": {"heal": (8, 22), "stamina": (6, 18)},
    },
    "trophy": {
        "slot": None,
        "types": ["pelt", "fang", "tusk", "scale", "horn"],
        "value": (6, 30),
        "mods": {},
    },
    "reagent": {
        "slot": None,
        "types": ["dust", "gland", "shard", "venom", "essence"],
        "value": (8, 35),
        "mods": {},
        "skills": {"medicine": 1, "arcana": 1},
    },
    "material": {
        "slot": None,
        "types": ["iron scrap", "linen bolt", "salt packet", "tallow cake"],
        "value": (3, 15),
        "mods": {},
    },
}

# Named templates for monster-specific flavor (merged with generated stats)
NAMED_TEMPLATES = {
    "grey pelt": {"category": "trophy", "tags": ["beast", "wolf"], "value": 14},
    "wolf fang": {"category": "trophy", "tags": ["beast", "wolf"], "value": 8, "mods": {"attack": 1}},
    "stolen coin purse": {"category": "material", "tags": ["coin"], "coin": True, "value": 18},
    "notched blade": {"category": "weapon", "tags": ["bandit"], "rarity_min": "uncommon", "mods": {"attack": 2}},
    "lurker scale": {"category": "trophy", "tags": ["marsh"], "value": 22},
    "reeking gland": {"category": "reagent", "tags": ["marsh", "poison"], "value": 12},
    "grave dust": {"category": "reagent", "tags": ["undead"], "value": 14},
    "tarnished ring": {"category": "trinket", "tags": ["undead"], "rarity_min": "uncommon", "value": 20},
    "boar tusk": {"category": "trophy", "tags": ["beast"], "value": 24, "mods": {"attack": 1}},
    "smoked haunch": {"category": "consumable", "tags": ["food"], "effects": {"stamina": 12}, "value": 9},
    "cold shard": {"category": "reagent", "tags": ["wraith", "arcane"], "rarity_min": "rare", "value": 28},
    "knucklebone charm": {"category": "trinket", "tags": ["undead"], "value": 18, "mods": {"defense": 1}},
    "marrow vial": {"category": "reagent", "tags": ["undead"], "value": 14},
    "adder venom": {"category": "reagent", "tags": ["poison"], "rarity_min": "uncommon", "value": 22},
    "striped hide": {"category": "trophy", "tags": ["beast"], "value": 12},
}


def roll_rarity(source="monster", shift=0):
    """shift: +1 bumps one tier toward rare (elite kills, guild rewards)."""
    weights = list(SOURCE_RARITY_WEIGHTS.get(source, SOURCE_RARITY_WEIGHTS["monster"]))
    idx = random.choices(range(len(RARITIES)), weights=weights, k=1)[0]
    idx = min(len(RARITIES) - 1, max(0, idx + shift))
    return RARITIES[idx]


def _scale_mod(base_lo, base_hi, rarity):
    tier = RARITY_ORDER[rarity]
    mult = 1 + tier * 0.35
    lo = max(0, int(base_lo * mult))
    hi = max(lo, int(base_hi * mult))
    return random.randint(lo, hi) if hi > lo else lo


def _build_stat_mods(category_spec, rarity):
    mods = {}
    for stat, (lo, hi) in category_spec.get("mods", {}).items():
        val = _scale_mod(lo, hi, rarity)
        if val:
            mods[stat] = val
    return mods


def _build_skill_mods(category_spec, rarity):
    tier = RARITY_ORDER[rarity]
    if tier < 1:
        return {}
    skills = category_spec.get("skills") or {}
    if not skills:
        return {}
    pick = random.choice(list(skills.keys()))
    return {pick: 1 + (1 if tier >= 3 else 0)}


def generate_item(category=None, source="npc_default", rarity=None, template_name=None, created_tick=0):
    """Create one item with rarity, value, and optional combat mods."""
    if template_name and template_name in NAMED_TEMPLATES:
        tpl = NAMED_TEMPLATES[template_name]
        category = tpl.get("category", category or "trophy")
        rarity = rarity or tpl.get("rarity_min") or roll_rarity(source)
        min_r = tpl.get("rarity_min")
        if min_r and RARITY_ORDER[rarity] < RARITY_ORDER[min_r]:
            rarity = min_r
    else:
        category = category or random.choice(list(CATEGORIES.keys()))
        rarity = rarity or roll_rarity(source)

    spec = CATEGORIES.get(category, CATEGORIES["material"])
    item_type = template_name or random.choice(spec["types"])
    adj = random.choice(ITEM_ADJECTIVES[rarity])
    name = template_name.title() if template_name else f"{adj} {item_type}"

    lo, hi = spec.get("value", (5, 20))
    base_value = random.randint(lo, hi)
    value = int(base_value * RARITY_MULTIPLIER[rarity])

    if template_name and template_name in NAMED_TEMPLATES:
        value = max(value, int(NAMED_TEMPLATES[template_name].get("value", value) * RARITY_MULTIPLIER[rarity] * 0.5))

    item_id = generate_id("itm")
    item = {
        "id": item_id,
        "name": name,
        "category": category,
        "slot": spec.get("slot"),
        "rarity": rarity,
        "base_value": base_value,
        "value": value,
        "condition": random.randint(50, 100),
        "owner": None,
        "source": source,
        "stat_mods": _build_stat_mods(spec, rarity),
        "skill_mods": _build_skill_mods(spec, rarity),
        "tags": list(NAMED_TEMPLATES.get(template_name or "", {}).get("tags", [])),
        "history": [],
        "created_tick": created_tick,
    }

    if template_name and NAMED_TEMPLATES.get(template_name, {}).get("mods"):
        for k, v in NAMED_TEMPLATES[template_name]["mods"].items():
            item["stat_mods"][k] = item["stat_mods"].get(k, 0) + v

    if category == "consumable":
        eff_spec = spec.get("effects") or {}
        tpl_eff = NAMED_TEMPLATES.get(template_name or "", {}).get("effects")
        if tpl_eff:
            item["effect"] = dict(tpl_eff)
        elif eff_spec:
            item["effect"] = {
                k: _scale_mod(lo, hi, rarity)
                for k, (lo, hi) in eff_spec.items()
            }

    if NAMED_TEMPLATES.get(template_name or "", {}).get("coin"):
        item["category"] = "coin"
        item["type"] = "coin"
        item["slot"] = None

    return item_id, item


def generate_items(count=30, source="merchant", created_tick=0):
    items = {}
    for _ in range(count):
        cat = random.choices(
            list(CATEGORIES.keys()),
            weights=[15, 12, 8, 20, 15, 12, 18],
            k=1,
        )[0]
        item_id, item = generate_item(category=cat, source=source, created_tick=created_tick)
        items[item_id] = item
    return items
