import random

from storage import load, save
from simulation.importance_router import score_event
from simulation.sim_priorities import build_sim_priorities, rumor_spread_threshold

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
        "Someone saw blood on {name}'s hands near the stalls.",
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


def _event_rumor_action(event):
    """Map event to a rumor template key."""
    action = event.get("action", "")
    if action in RUMOR_TEMPLATES:
        return action
    etype = event.get("type") or ""
    if etype in ("combat", "conflict", "death") or action in ("attack", "kill"):
        return "fight"
    effects = event.get("effects") or []
    if effects:
        head = effects[0] if isinstance(effects[0], str) else ""
        if head in RUMOR_TEMPLATES:
            return head
    return None


def _rumor_actor(event, npcs):
    actor_id = event.get("actor", "someone")
    if actor_id == "player":
        target_id = event.get("target")
        if target_id and isinstance(npcs, dict):
            target = npcs.get(target_id, {})
            if target.get("name"):
                return target.get("name"), "the outsider"
        return "the outsider", "the outsider"
    actor_npc = npcs.get(actor_id, {}) if isinstance(npcs, dict) else {}
    return actor_npc.get("name", actor_id), actor_id


def spread_rumors():
    config = load("system/config.json", {})
    if isinstance(config, dict) and not config.get("enable_rumors", True):
        return

    events = load("events/event_log.json", [])
    rumors = load("rumors/rumors.json", [])
    npcs = load("characters/npcs.json", {})
    player = load("player/player.json", {})
    areas = load("world/areas.json", {})

    if not isinstance(events, list):
        events = []
    if not isinstance(rumors, list):
        rumors = []
    if not isinstance(npcs, dict):
        npcs = {}

    sim_priorities = build_sim_priorities(player, npcs=npcs, areas=areas)
    min_importance = rumor_spread_threshold(sim_priorities)

    recent = events[-12:] if len(events) > 12 else events

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

        rumor_action = _event_rumor_action(e)
        if not rumor_action:
            continue

        importance = score_event(e, player=player if player else None)
        is_template_action = e.get("action") in RUMOR_TEMPLATES
        if not is_template_action and importance < min_importance and random.random() > 0.25:
            continue

        actor_name, _ = _rumor_actor(e, npcs)
        location = e.get("location", "the city")

        template = random.choice(RUMOR_TEMPLATES[rumor_action])
        if e.get("actor") == "player" and rumor_action == "fight":
            rumor_text = template.format(name="the outsider", location=location)
        else:
            rumor_text = template.format(name=actor_name, location=location)

        spread = min(100, max(importance, random.randint(max(1, importance // 2), importance + 12)))

        new_rumors.append({
            "source_event_id": event_id,
            "text": rumor_text,
            "interpretation": random.choice(DISTORTIONS),
            "spread": spread,
            "importance": importance,
        })

        existing_event_ids.add(event_id)

    rumors.extend(new_rumors)

    if len(rumors) > MAX_RUMORS:
        rumors.sort(key=lambda r: int((r or {}).get("importance") or (r or {}).get("spread") or 0))
        rumors = rumors[-MAX_RUMORS:]

    save("rumors/rumors.json", rumors)
