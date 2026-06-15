import random
import json
import os
from generation.id_generator import generate_id

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ITEM_TYPES = [
    "sword", "dagger", "shield", "potion",
    "ring", "armor", "scroll", "gem"
]

RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]

RARITY_MULTIPLIER = {
    "common": 1,
    "uncommon": 1.5,
    "rare": 2.5,
    "epic": 5,
    "legendary": 10
}

# Immersive item name parts instead of "Common Sword 247"
ITEM_ADJECTIVES = {
    "common":    ["Worn", "Battered", "Plain", "Old", "Crude"],
    "uncommon":  ["Sturdy", "Keen", "Polished", "Tempered", "Etched"],
    "rare":      ["Masterwork", "Engraved", "Enchanted", "Runed", "Gilded"],
    "epic":      ["Ancient", "Bloodforged", "Voidtouched", "Dragonbone", "Soulbound"],
    "legendary": ["Mythic", "Worldbreaker", "Eternal", "Godtouched", "Abyssal"],
}


def generate_item(created_tick=0):
    item_type = random.choice(ITEM_TYPES)
    rarity = random.choices(RARITIES, weights=[50, 25, 15, 8, 2], k=1)[0]
    base_value = random.randint(10, 100)

    # FIX: generate ID once here; do NOT also generate in generate_items()
    item_id = generate_id("itm")

    adjective = random.choice(ITEM_ADJECTIVES[rarity])
    name = f"{adjective} {item_type.capitalize()}"

    return item_id, {
        "id": item_id,
        "name": name,
        "type": item_type,
        "rarity": rarity,
        "base_value": base_value,
        "value": int(base_value * RARITY_MULTIPLIER[rarity]),
        "condition": random.randint(40, 100),
        "owner": None,
        "location": None,
        "history": [],
        "created_tick": created_tick
    }


def generate_items(count=30, created_tick=0):
    items = {}
    for _ in range(count):
        # FIX: was calling generate_id("itm") here AND inside generate_item()
        # causing two different IDs — the dict key never matched item["id"]
        item_id, item = generate_item(created_tick)
        items[item_id] = item
    return items


def save_items(items):
    # FIX: was "../world/items.json"
    path = os.path.join(BASE_DIR, "world", "items.json")
    with open(path, "w") as f:
        json.dump(items, f, indent=2)
