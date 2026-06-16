"""
Layered past events — official, folk, and rumor history the world remembers.
"""

import random

HISTORY_TEMPLATES = [
    ("{years} years ago", "the {gate} gate burned for three days"),
    ("{years} years ago", "Lord {name} disappeared after a debt to the guild"),
    ("{years} years ago", "a plague winter emptied the warrens"),
    ("last {season}", "merchants hanged a thief without trial — folk still argue"),
    ("{years} years ago", "the temple split over a forbidden rite"),
    ("{years} years ago", "soldiers put down a riot in the high quarter"),
]


def generate_world_history(cities=None, count=5):
    cities = cities or {}
    city = next(iter(cities.values()), {})
    gates = ["East", "North", "River", "Old"]
    names = ["Arven", "Sera", "Koth", "Mael", "Vire"]
    events = []
    used = set()
    for _ in range(count):
        years = random.choice([2, 3, 5, 8, 12, 20])
        tpl = random.choice(HISTORY_TEMPLATES)
        when, what = tpl
        when = when.format(years=years, season=random.choice(["winter", "summer", "autumn"]))
        what = what.format(
            gate=random.choice(gates),
            name=random.choice(names),
        )
        key = what[:30]
        if key in used:
            continue
        used.add(key)
        events.append({
            "when": when,
            "official": what.capitalize() + ".",
            "folk": random.choice([
                what + " — but the rich started it.",
                what + " — everyone knows who profited.",
                "Old people say: " + what + ", and worse besides.",
            ]),
            "rumor": random.choice([
                "It wasn't an accident.",
                "Someone paid to make it happen.",
                "The temple still hides records from that year.",
            ]),
        })
    return events


def history_block(world):
    hist = (world or {}).get("history") or []
    if not hist:
        return ""
    picked = random.sample(hist, k=min(2, len(hist)))
    lines = []
    for h in picked:
        lines.append(f"{h.get('when', 'Once')}: {h.get('folk', h.get('official', ''))[:100]}")
    return (
        "WORLD MEMORY (texture only — do not lecture):\n"
        + "\n".join(f"- {l}" for l in lines)
    )
