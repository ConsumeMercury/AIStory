"""
Slow-burn relationships.

Each directed relationship (who -> toward) has six dimensions, 0-100:
    trust, respect, fear, affection, attraction, resentment
plus `familiarity`, which GATES how fast anything else can move. A
stranger (low familiarity) cannot suddenly trust or love you no matter
what happens; bonds are earned over many interactions.

Two entry points:
  * update_relationships(): the ambient drift run every tick — relationships
    inch toward what the NPC's personality predicts, and unused bonds
    slowly decay toward neutral. Deltas are tiny on purpose.
  * apply_interaction(toward_id, kind, intensity): a discrete nudge from a
    specific event (you helped them, you threatened them, you fought beside
    them). Still small, still gated by familiarity.
"""

from storage import load, save

DIMS = ["trust", "respect", "fear", "affection", "attraction", "resentment", "rivalry", "obligation"]

NPC_FILE = "characters/npcs.json"
REL_FILE = "characters/relationships.json"

# how a kind of interaction pushes each dimension (per point of intensity)
INTERACTION_EFFECTS = {
    "kindness":   {"trust": +0.8, "affection": +0.6, "resentment": -0.4},
    "aid":        {"trust": +1.0, "respect": +0.6, "affection": +0.5},
    "gift":       {"affection": +0.7, "trust": +0.4},
    "threat":     {"fear": +1.2, "respect": +0.3, "trust": -0.8, "resentment": +0.7},
    "violence":   {"fear": +1.6, "resentment": +1.2, "trust": -1.4, "respect": +0.2},
    "betrayal":   {"trust": -2.0, "resentment": +1.8, "affection": -1.0},
    "fought_beside": {"trust": +1.1, "respect": +1.3, "affection": +0.4},
    "charm":      {"attraction": +0.9, "affection": +0.5},
    "insult":     {"respect": -0.7, "resentment": +0.9, "rivalry": +0.6},
    "respect":    {"respect": +1.1, "trust": +0.5, "fear": -0.4, "resentment": -0.3},
    "bested":     {"rivalry": +1.2, "respect": +0.5, "resentment": +0.6},
    "rescued":    {"obligation": +1.6, "trust": +1.0, "affection": +0.6},
    "owed_debt":  {"obligation": +1.4, "resentment": +0.3},
    "debt_repaid":{"obligation": -1.8, "trust": +0.4},
}

MAX_PER_INTERACTION = 6.0   # hard cap on movement from a single event

# player action kind -> (interaction kind, base intensity toward NPC->player)
PLAYER_ACTION_REL = {
    "talk": ("charm", 0.55),
    "personal_talk": ("charm", 0.45),
    "ask_name": ("charm", 0.35),
    "help": ("kindness", 1.0),
    "give": ("gift", 0.85),
    "threaten": ("threat", 1.25),
    "insult": ("insult", 0.95),
    "show_respect": ("respect", 1.0),
    "trade": ("charm", 0.4),
    "find": ("charm", 0.35),
    "attack": ("violence", 1.5),
}


def _clamp(v):
    return round(max(0.0, min(100.0, v)), 2)


def _blank():
    return {d: 0.0 for d in DIMS} | {"familiarity": 0.0, "interactions": 0}


def _gate(familiarity):
    """0..1 multiplier — strangers barely move, intimates move freely."""
    return 0.15 + 0.85 * min(1.0, familiarity / 60.0)


def _familiarity_gain(toward_id, intensity, prior_interactions):
    """Strangers accumulate familiarity slowly; repeated contact earns more."""
    if toward_id == "player":
        if prior_interactions <= 0:
            return 0.35 * intensity
        if prior_interactions < 3:
            return 0.75 * intensity
        if prior_interactions < 8:
            return 1.35 * intensity
        return 2.0 * intensity
    if prior_interactions < 3:
        return 0.9 * intensity
    return 1.5 * intensity


def apply_interaction(toward_id, kind, intensity=1.0, actor_id="player"):
    """Record a discrete interaction's effect on actor's feelings toward target."""
    rels = load(REL_FILE, {})
    book = rels.setdefault(actor_id, {})
    rel = book.setdefault(toward_id, _blank())

    prior = rel.get("interactions", 0)
    rel["familiarity"] = _clamp(
        rel["familiarity"] + _familiarity_gain(toward_id, intensity, prior)
    )
    rel["interactions"] = prior + 1
    gate = _gate(rel["familiarity"])

    for dim, per in INTERACTION_EFFECTS.get(kind, {}).items():
        delta = per * intensity * gate
        delta = max(-MAX_PER_INTERACTION, min(MAX_PER_INTERACTION, delta))
        rel[dim] = _clamp(rel.get(dim, 0.0) + delta)

    rels[actor_id] = book
    save(REL_FILE, rels)
    return rel


def apply_npc_toward_player(npc_id, kind, intensity=1.0, check=None):
    """
    How an NPC feels about the player after a player action.
    Updates relationships[npc_id][player], not the reverse.
    """
    if not npc_id or npc_id == "player":
        return None

    mult = 1.0
    if check:
        margin = check.get("margin", 0)
        if check.get("success"):
            mult = 1.0 + min(0.6, max(0, margin) * 0.06)
            if check.get("critical_success"):
                mult += 0.25
        else:
            mult = 0.45
            if check.get("critical_fail"):
                mult = 0.25
            # failed intimidation / charm often backfires
            if kind in ("threat", "charm", "insult"):
                apply_interaction("player", "insult", intensity=0.55 * mult, actor_id=npc_id)
                return relationship(npc_id, "player")

    rel = apply_interaction("player", kind, intensity=intensity * mult, actor_id=npc_id)
    return rel


def apply_player_action_relationship(action_kind, npc_id, action_ctx=None, check=None):
    """Apply relationship change from a interpreted player action."""
    if not npc_id:
        return None
    spec = (action_ctx or {}).get("relationship")
    if spec:
        kind, intensity = spec
    else:
        kind, intensity = PLAYER_ACTION_REL.get(action_kind, (None, 0))
    if not kind:
        return None
    return apply_npc_toward_player(npc_id, kind, intensity=intensity, check=check)


def update_relationships():
    """Ambient per-tick drift between NPCs. Very small; mostly decay."""
    npcs = load(NPC_FILE, {})
    rels = load(REL_FILE, {})
    if not isinstance(npcs, dict):
        return

    dirty = False
    ids = [i for i, n in npcs.items() if n.get("status") == "alive"]

    for npc_id in ids:
        traits = npcs[npc_id].get("traits", {})
        kindness = traits.get("kindness", 50)
        book = rels.setdefault(npc_id, {})

        for other_id in book:
            rel = book[other_id]
            fam = rel.get("familiarity", 0.0)
            gate = _gate(fam)

            # trust gravitates toward the NPC's own kindness, slowly
            trust_target = kindness * 0.5
            rel["trust"] = _clamp(rel.get("trust", 0) + (trust_target - rel.get("trust", 0)) * 0.02 * gate)

            # everything decays a hair toward neutral if not reinforced
            for d in ("fear", "resentment", "attraction", "affection", "respect"):
                rel[d] = _clamp(rel.get(d, 0) * 0.997)

            # familiarity itself fades very slowly when apart
            rel["familiarity"] = _clamp(fam * 0.999)
            dirty = True

    if dirty:
        save(REL_FILE, rels)


def relationship(actor_id, toward_id):
    return load(REL_FILE, {}).get(actor_id, {}).get(toward_id, _blank())


def apply_impression_nudge(npc_id, player_id, impression):
    """One-time first-impression nudge: NPC -> player."""
    if not impression:
        return
    from simulation.appearance_impression import impression_relationship_nudge
    nudges = impression_relationship_nudge(impression)
    if not nudges:
        return
    rels = load(REL_FILE, {})
    book = rels.setdefault(npc_id, {})
    rel = book.setdefault(player_id, _blank())
    for dim, delta in nudges.items():
        rel[dim] = _clamp(rel.get(dim, 0) + delta)
    rel["familiarity"] = _clamp(rel.get("familiarity", 0) + 0.25)
    save(REL_FILE, rels)
