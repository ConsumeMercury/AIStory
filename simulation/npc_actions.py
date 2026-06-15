"""
NPC behaviour for one world tick.

Richer than before: NPCs trade, train, study, craft, help, socialise,
hide, plan, hunt monsters, or travel — chosen by personality + role +
weather (read from real world state, not hardcoded). Actions have real
mechanical effects: stamina/health/wealth change, skills earn XP, fights
against monsters run through the combat engine, and social acts feed the
slow-burn relationship system.

Personality biases choice but never forces it (weighted random), so the
same NPC behaves differently day to day — the "natural, not scripted" feel.
"""

import random

from storage import load, save
from simulation.event_logger import log_event
from simulation.goal_engine import check_goal_progress
from simulation.progression_engine import train_from_action
from simulation.combat_engine import resolve_combat
from simulation.relationship_engine import apply_interaction

NPC_FILE = "characters/npcs.json"
MON_FILE = "characters/monsters.json"
CFG_FILE = "system/config.json"
RULES_FILE = "system/npc_rules.json"
LOC_FILE = "world/locations.json"
WORLD_FILE = "world/world_state.json"


def choose_action(npc, trait_weights=None, weather="Clear"):
    t = npc.get("traits", {})
    tw = trait_weights or {}

    def w(trait):
        return t.get(trait, 0) * tw.get(trait, 1.0)

    weights = {
        "trade":     w("greed") + 10,
        "fight":     w("aggression"),
        "hunt":      w("courage") * 0.6 + (t.get("aggression", 0) * 0.2),
        "help":      w("kindness") + w("generosity") * 0.5,
        "hide":      (100 - t.get("courage", 50)) * 0.6 + w("paranoia") * 0.3,
        "plan":      w("ambition") + w("wit") * 0.4,
        "study":     w("curiosity") + t.get("discipline", 0) * 0.3,
        "craft":     t.get("discipline", 0) * 0.5 + 8,
        "socialise": w("humor") + w("kindness") * 0.4 + 8,
        "travel":    w("ambition") * 0.3 + w("curiosity") * 0.2,
    }

    if weather in ("Storm", "Snow", "Fog"):
        weights["hide"] *= 1.5
        weights["trade"] *= 0.7
        weights["hunt"] *= 0.6
        weights["travel"] *= 0.5
    elif weather == "Heatwave":
        weights["fight"] *= 1.2

    total = sum(weights.values())
    if total <= 0:
        return "hide"
    return random.choices(list(weights.keys()), weights=list(weights.values()), k=1)[0]


def _heal_tick(npc):
    s = npc.get("stats")
    if not s:
        return
    s["health"] = min(s.get("max_health", 100), s.get("health", 0) + 1)
    s["stamina"] = min(s.get("max_stamina", 30), s.get("stamina", 0) + 4)


def simulate_npcs(tick=None):
    config = load(CFG_FILE, {})
    rules = load(RULES_FILE, {})
    trait_weights = rules.get("trait_weights", {})
    world = load(WORLD_FILE, {})
    weather = world.get("weather", "Clear")

    npcs = load(NPC_FILE, {})
    monsters = load(MON_FILE, {})
    if not isinstance(npcs, dict):
        npcs = {}

    max_npcs = config.get("max_npcs_per_tick", len(npcs))
    npc_ids = [i for i, n in npcs.items() if n.get("status") == "alive"]
    if not npc_ids:
        save(NPC_FILE, npcs)
        return

    active = random.sample(npc_ids, k=min(max_npcs, len(npc_ids)))

    for npc_id in active:
        npc = npcs[npc_id]
        location = npc.get("location", "unknown")
        action = choose_action(npc, trait_weights, weather)
        effects = []

        try:
            check_goal_progress(npc, action)
        except Exception:
            pass

        if action == "trade":
            npc["wealth"] = npc.get("wealth", 0) + random.randint(1, 10)
            effects.append("wealth_change")

        elif action == "fight":
            effects.append("brawl")
            if npc.get("status") == "alive" and random.random() < 0.02:
                npc["status"] = "dead"
                effects.append("npc_death")

        elif action == "hunt":
            # find a monster sharing this NPC's location (city key) — abstracted
            prey = [m for m in monsters.values()
                    if m.get("status") == "alive" and m.get("location")]
            if prey:
                target = random.choice(prey)
                result = resolve_combat(npc, target)
                effects.append("monster_hunt")
                if result.get("fatal") and result.get("loser") == target["id"]:
                    effects.append("monster_slain")

        elif action == "help":
            effects.append("kindness")
            # build a relationship with a random co-located NPC
            peers = [i for i in npc_ids if i != npc_id and npcs[i].get("location") == location]
            if peers:
                other = random.choice(peers)
                apply_interaction(other, "aid", intensity=1.0, actor_id=npc_id)
                effects.append("relationship_built")
                npc["_interacted_with"] = other

        elif action == "socialise":
            peers = [i for i in npc_ids if i != npc_id and npcs[i].get("location") == location]
            if peers:
                other = random.choice(peers)
                kind = "charm" if npc["traits"].get("humor", 0) > 60 else "kindness"
                apply_interaction(other, kind, intensity=0.7, actor_id=npc_id)
                effects.append("socialised")
                npc["_interacted_with"] = other

        elif action == "hide":
            effects.append("self_preservation")

        elif action in ("plan", "study", "craft"):
            effects.append(action)

        elif action == "travel":
            try:
                locs = load(LOC_FILE, {})
                connected = locs.get("cities", {}).get(location, {}).get("connected", [])
                if connected:
                    npc["location"] = random.choice(connected)
                    effects.append("npc_travelled")
            except Exception:
                pass

        # earned progression + recovery
        if train_from_action(npc, action):
            effects.append("skill_levelled")
        _heal_tick(npc)

        npc["last_action"] = action
        log_event("npc_action", npc_id, action, target=npc.pop("_interacted_with", None),
                  location=location, effects=effects, tick=tick)

    save(NPC_FILE, npcs)
    save(MON_FILE, monsters)
