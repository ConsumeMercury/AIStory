"""
Emergent rival — staged progression from notice to nemesis.
"""

import random

from storage import load, save
from simulation.event_logger import log_event
from simulation.relationship_engine import apply_npc_toward_player

PLAYER_FILE = "player/player.json"
NPC_FILE = "characters/npcs.json"
RUMOR_FILE = "rumors/rumors.json"

NOTORIETY_THRESHOLD = 12

RIVAL_STAGES = [
    (0, "unknown", "No rival yet."),
    (1, "noticed", "A rival has noticed you — envy, not yet action."),
    (2, "competing", "They compete for the same opportunities and whisper against you."),
    (3, "opposing", "Active opposition — sabotage, rumors, turned allies."),
    (4, "nemesis", "Obsessed nemesis — will not let you rise unchallenged."),
]


def bump_notoriety(player, amount=1, reason=""):
    track = player.setdefault("notoriety", {"score": 0, "events": []})
    track["score"] = track.get("score", 0) + amount
    if reason:
        track.setdefault("events", []).append(reason[:80])
        track["events"] = track["events"][-20:]
    return track["score"]


def rival_stage(player):
    return player.get("rival_stage", 0)


def advance_rival_stage(player, npcs):
    rid = player.get("rival_id")
    if not rid:
        return
    rival = npcs.get(rid, {})
    if rival.get("status") != "alive":
        return
    stage = player.get("rival_stage", 1)
    notoriety = player.get("notoriety", {}).get("score", 0)
    thresholds = [0, 12, 22, 35, 50]
    new_stage = stage
    for i, t in enumerate(thresholds):
        if notoriety >= t:
            new_stage = max(new_stage, i)
    if new_stage > stage:
        player["rival_stage"] = new_stage
        _, label, desc = RIVAL_STAGES[min(new_stage, len(RIVAL_STAGES) - 1)]
        player.setdefault("journal", []).append({
            "kind": "rival", "action": f"Rival stage: {label}",
            "excerpt": desc, "tick": 0,
        })


def maybe_spawn_rival(player, npcs, world, tick=None):
    if player.get("rival_id"):
        advance_rival_stage(player, npcs)
        return npcs.get(player["rival_id"])

    score = player.get("notoriety", {}).get("score", 0)
    if score < NOTORIETY_THRESHOLD or random.random() > 0.25:
        return None

    city = player.get("location")
    candidates = [
        n for n in npcs.values()
        if n.get("status") == "alive" and n.get("location") == city
    ]
    if not candidates:
        return None

    rival = max(candidates, key=lambda n: n.get("traits", {}).get("ambition", 50))
    rival["rival_of_player"] = True
    rival.setdefault("goals", []).insert(0, "undermine the rising outsider")
    player["rival_id"] = rival["id"]
    player["rival_stage"] = 1
    player.setdefault("story_flags", {})["has_rival"] = True

    rumors = load(RUMOR_FILE, [])
    rumors.append({
        "source_event_id": f"rival_{rival['id']}",
        "text": f"{rival.get('name', 'Someone')} watches the newcomer with calculating envy.",
        "interpretation": "suspicious",
        "spread": random.randint(15, 45),
    })
    save(RUMOR_FILE, rumors[-200:])
    log_event("rival", rival["id"], "rival_declared", target="player", tick=tick)
    return rival


def rival_directive(player, npcs):
    rid = player.get("rival_id")
    if not rid:
        return ""
    rival = npcs.get(rid, {})
    if rival.get("status") != "alive":
        return ""
    stage = player.get("rival_stage", 1)
    _, label, desc = RIVAL_STAGES[min(stage, len(RIVAL_STAGES) - 1)]
    return (
        f"RIVAL ({label}): {rival.get('name', 'A rival')} — {desc} "
        f"Stage {stage}/4."
    )


def rival_tick(player, npcs, tick=None):
    rid = player.get("rival_id")
    if not rid:
        return
    rival = npcs.get(rid)
    if not rival or rival.get("status") != "alive":
        return

    advance_rival_stage(player, npcs)
    stage = player.get("rival_stage", 1)
    chance = {1: 0.06, 2: 0.10, 3: 0.14, 4: 0.18}.get(stage, 0.08)
    if random.random() > chance:
        return

    rumors = load(RUMOR_FILE, [])
    texts = {
        1: f"{rival.get('name')} asks after you — casually, too casually.",
        2: f"{rival.get('name')} claims credit for what you did.",
        3: f"{rival.get('name')} warns others against trusting you.",
        4: f"{rival.get('name')} swears you will fall — and means it.",
    }
    rumors.append({
        "source_event_id": f"rival_act_{tick}",
        "text": texts.get(stage, texts[2]),
        "interpretation": random.choice(["suspicious", "scandalous", "false"]),
        "spread": random.randint(10, 35 + stage * 5),
    })
    save(RUMOR_FILE, rumors[-200:])

    if stage >= 3:
        apply_npc_toward_player(rid, "insult", intensity=0.4 + stage * 0.15)
