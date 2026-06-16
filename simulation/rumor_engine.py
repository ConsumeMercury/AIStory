import json
import random
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAX_RUMORS = 200

DISTORTIONS = ["dangerous", "heroic", "suspicious", "mysterious", "false"]

RUMOR_TEMPLATES = {
    "trade": [
        "{name} has been spotted making shady deals at the docks.",
        "Word is {name} sold something they shouldn't have.",
        "Merchants say {name} drives a harder bargain than anyone.",
    ],
    "fight": [
        "{name} was seen brawling outside the tavern last night.",
        "Three men needed a healer after crossing {name}.",
        "They say {name} started the riot near the market.",
    ],
    "help": [
        "{name} pulled a stranger from the mud after the storm.",
        "Folk in {location} claim {name} fed half the district.",
        "Some say {name} is too kind for this world.",
    ],
    "hide": [
        "{name} hasn't been seen in days — some fear the worst.",
        "Rumour has it {name} is lying low after some trouble.",
        "Nobody knows where {name} disappeared to.",
    ],
    "plan": [
        "{name} has been meeting with powerful people in secret.",
        "Whispers say {name} is plotting something big.",
        "A servant overheard {name} speaking of 'the right moment'.",
    ],
}


# -------------------------
# SAFE LOAD / SAVE
# -------------------------
def load(filename):
    path = os.path.join(BASE_DIR, filename)
    try:
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return []


def save(filename, data):
    path = os.path.join(BASE_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# -------------------------
# MAIN SYSTEM
# -------------------------
def spread_rumors():

    # 🔥 CONFIG FLAG CHECK (FIX-1)
    config = load("system/config.json")
    if isinstance(config, dict):
        if not config.get("enable_rumors", True):
            return

    events = load("events/event_log.json")
    rumors = load("rumors/rumors.json")
    npcs   = load("characters/npcs.json")

    recent = events[-10:] if len(events) > 10 else events

    # Track already processed event IDs
    existing_event_ids = set()
    for r in rumors:
        if isinstance(r, dict) and r.get("source_event_id"):
            existing_event_ids.add(r["source_event_id"])

    new_rumors = []

    for e in recent:
        if not isinstance(e, dict):
            continue

        event_id = e.get("id")
        if not event_id:
            event_id = f"{e.get('actor')}_{e.get('action')}_{e.get('tick')}"

        if event_id in existing_event_ids:
            continue

        action = e.get("action", "")
        if action not in RUMOR_TEMPLATES:
            continue

        actor_id = e.get("actor", "someone")
        actor_npc = npcs.get(actor_id, {}) if isinstance(npcs, dict) else {}
        actor_name = actor_npc.get("name", actor_id)

        location = e.get("location", "the city")

        template = random.choice(RUMOR_TEMPLATES[action])
        rumor_text = template.format(name=actor_name, location=location)

        new_rumors.append({
            "source_event_id": event_id,
            "text": rumor_text,
            "interpretation": random.choice(DISTORTIONS),
            "spread": random.randint(1, 100),
        })

        existing_event_ids.add(event_id)

    rumors.extend(new_rumors)

    if len(rumors) > MAX_RUMORS:
        rumors = rumors[-MAX_RUMORS:]

    save("rumors/rumors.json", rumors)