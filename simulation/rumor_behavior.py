"""
Rumor belief → NPC action — close the loop from gossip to behavior.
"""

from storage import load

MEM_FILE = "characters/npc_memories.json"
RUMOR_FILE = "rumors/rumors.json"

# interpretation / memory text hints -> behavior toward player
RUMOR_PROFILES = {
    "murderer": {
        "keywords": ("murder", "killed", "blood on", "slain", "assassin"),
        "weights": {"hide": 1.6, "fight": 1.2, "socialise": 0.4, "help": 0.3, "trade": 0.7},
        "rel": ("betrayal", 0.8),
        "narrator": "They believe you killed someone — fear or hatred in every glance.",
    },
    "hero": {
        "keywords": ("slew", "monster", "saved", "hero", "brave", "rescued"),
        "weights": {"help": 1.4, "socialise": 1.3, "trade": 1.1},
        "rel": ("kindness", 0.6),
        "narrator": "Word says you did something brave — hope mixes with envy.",
    },
    "thief": {
        "keywords": ("stole", "theft", "pickpocket", "thief", "snatch"),
        "weights": {"hide": 1.3, "socialise": 0.6, "trade": 0.75, "plan": 1.2},
        "rel": ("betrayal", 0.7),
        "narrator": "They think you steal — hands kept close, eyes sharp.",
    },
    "dangerous": {
        "keywords": ("dangerous", "violent", "menace", "threaten", "feared"),
        "weights": {"hide": 1.4, "fight": 1.15, "socialise": 0.55},
        "rel": ("threat", 0.5),
        "narrator": "Rumors paint you as dangerous — space widens around you.",
    },
    "charmer": {
        "keywords": ("charm", "silver tongue", "persuad", "liked", "popular"),
        "weights": {"socialise": 1.35, "help": 1.15, "trade": 1.1},
        "rel": ("charm", 0.5),
        "narrator": "People have heard you talk your way through trouble.",
    },
}


def _classify_text(text):
    t = (text or "").lower()
    for name, spec in RUMOR_PROFILES.items():
        if any(k in t for k in spec["keywords"]):
            return name, spec
    if "outsider" in t or "stranger" in t:
        return "unknown", None
    return None, None


def npc_player_rumor_profile(npc_id, mem_store=None, rumors=None):
    """What this NPC believes about the player from memories + recent rumors."""
    mem_store = mem_store if mem_store is not None else load(MEM_FILE, {})
    rumors = rumors if rumors is not None else load(RUMOR_FILE, [])

    scores = {k: 0.0 for k in RUMOR_PROFILES}
    for mem in mem_store.get(npc_id, [])[-12:]:
        if not mem.get("about_player") and "outsider" not in (mem.get("summary") or ""):
            continue
        name, spec = _classify_text(mem.get("summary", ""))
        if name and name in scores:
            sal = mem.get("salience", 10)
            val = mem.get("valence", 0)
            scores[name] += sal * (1.2 if val < -0.3 else 0.8 if val > 0.3 else 1.0)

    for rumor in rumors[-15:]:
        if "player" not in (rumor.get("text") or "").lower() and "outsider" not in (rumor.get("text") or "").lower():
            continue
        name, spec = _classify_text(rumor.get("text", ""))
        if name and name in scores:
            scores[name] += rumor.get("spread", 20) * 0.15

    if not any(scores.values()):
        return None, None
    best = max(scores, key=scores.get)
    if scores[best] < 8:
        return None, None
    return best, RUMOR_PROFILES[best]


def rumor_action_bias(npc_id, weights):
    """Apply rumor-driven action multipliers for this NPC."""
    name, spec = npc_player_rumor_profile(npc_id)
    if not spec:
        return name
    for action, mult in spec.get("weights", {}).items():
        if action in weights:
            weights[action] *= mult
    return name


def rumor_relationship_nudge(npc_id, player_present=False):
    """When player is in area, nudge NPC→player relationship from rumor belief."""
    if not player_present:
        return
    name, spec = npc_player_rumor_profile(npc_id)
    if not spec or not spec.get("rel"):
        return
    from simulation.relationship_engine import apply_npc_toward_player
    kind, intensity = spec["rel"]
    apply_npc_toward_player(npc_id, kind, intensity=intensity * 0.35)


def rumor_narrator_line(npc_id):
    name, spec = npc_player_rumor_profile(npc_id)
    if not spec:
        return ""
    return spec.get("narrator", "")
