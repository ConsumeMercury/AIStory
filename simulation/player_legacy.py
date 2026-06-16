"""
Player legacy — the world remembers your deeds in rumors and texture.
"""

import random

from storage import load, save

RUMOR_FILE = "rumors/rumors.json"
PLAYER_FILE = "player/player.json"

LEGACY_TEMPLATES = {
    "heroism": [
        "Children still tell how the outsider {deed}.",
        "Old folk say the stranger {deed} — whether they believe it varies.",
    ],
    "violence": [
        "Some say the outsider {deed}; others cross themselves.",
        "A song in the warrens mocks how the stranger {deed}.",
    ],
    "crime": [
        "Merchants warn apprentices: the outsider {deed} once.",
        "The watch still mutters that the stranger {deed}.",
    ],
    "kindness": [
        "A beggar claims the outsider {deed} — and was not laughed at.",
        "Temple acolytes whisper that the stranger {deed}.",
    ],
}


def record_legacy(player, category, deed_text, day=None):
    """Record a notable deed for long-term recall."""
    leg = player.setdefault("legacy", [])
    leg.append({
        "category": category,
        "deed": deed_text[:120],
        "day": day,
    })
    player["legacy"] = leg[-25:]
    return leg[-1]


def legacy_from_action(player, kind, action_ctx, world, target_npc=None):
    """Auto-record legacy on major beats."""
    day = (world or {}).get("day")
    check = (action_ctx or {}).get("skill_check") or {}
    if kind == "help" and check.get("success"):
        name = (target_npc or {}).get("name", "someone in need")
        return record_legacy(player, "kindness", f"helped {name} when others would not", day)
    if kind == "attack" and check.get("success"):
        return record_legacy(player, "violence", "won a fight that people still talk about", day)
    if kind == "steal" and check.get("success"):
        return record_legacy(player, "crime", "slipped past guards and lived to boast of it", day)
    return None


def seed_legacy_rumors(player, tick=None):
    """Occasionally spawn rumors referencing past deeds."""
    leg = player.get("legacy") or []
    if not leg or random.random() > 0.08:
        return
    entry = random.choice(leg)
    cat = entry.get("category", "heroism")
    templates = LEGACY_TEMPLATES.get(cat, LEGACY_TEMPLATES["heroism"])
    text = random.choice(templates).format(deed=entry.get("deed", "did something unforgettable"))
    rumors = load(RUMOR_FILE, [])
    rumors.append({
        "source_event_id": f"legacy_{tick}",
        "text": text,
        "interpretation": {"heroism": "heroic", "kindness": "heroic", "violence": "dangerous",
                          "crime": "suspicious"}.get(cat, "mysterious"),
        "spread": random.randint(15, 40),
    })
    save(RUMOR_FILE, rumors[-200:])


def legacy_narrator_block(player):
    leg = player.get("legacy") or []
    if not leg:
        return ""
    recent = leg[-2:]
    lines = [f"- {e.get('deed', '')[:90]}" for e in recent]
    return (
        "YOUR LEGACY (people remember — weave as rumor, story, or glance):\n"
        + "\n".join(lines)
    )
