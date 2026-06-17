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

import logging
import random

from storage import load, save
from simulation.event_logger import log_event
from simulation.goal_engine import check_goal_progress
from simulation.progression_engine import train_from_action
from simulation.combat_engine import resolve_combat
from simulation.relationship_engine import apply_interaction
from simulation.npc_memory_engine import player_memories
from simulation.npc_schedule import apply_schedules_to_npcs
from simulation.storyline_behavior import apply_storyline_to_npc, apply_storyline_weights
from simulation.hunting_engine import monsters_in_area
from simulation.rumor_behavior import rumor_action_bias, rumor_relationship_nudge
from simulation.institution_politics import politics_action_bias

NPC_FILE = "characters/npcs.json"
MON_FILE = "characters/monsters.json"
CFG_FILE = "system/config.json"
RULES_FILE = "system/npc_rules.json"
LOC_FILE = "world/locations.json"
WORLD_FILE = "world/world_state.json"
AREAS_FILE = "world/areas.json"
INST_FILE = "world/institutions.json"
PLAYER_FILE = "player/player.json"

log = logging.getLogger(__name__)


_ROLE_BIAS = {
    "merchant": {"trade": 18, "plan": 6},
    "guard": {"fight": 12, "hide": 4},
    "scholar": {"study": 16, "craft": 4},
    "thief": {"hide": 10, "plan": 8},
    "soldier": {"fight": 10, "hunt": 6},
    "priest": {"help": 12, "socialise": 8},
    "herbalist": {"craft": 14, "help": 8},
    "blacksmith": {"craft": 16, "trade": 6},
    "innkeeper": {"socialise": 14, "trade": 10},
    "hunter": {"hunt": 18, "travel": 4},
    "farmer": {"craft": 10, "trade": 6},
    "sailor": {"travel": 14, "socialise": 6},
    "mercenary": {"fight": 14, "hunt": 8},
    "apothecary": {"craft": 14, "study": 6},
    "scribe": {"study": 12, "craft": 8},
}


def _memory_bias(npc_id):
    mems = player_memories(npc_id, 2)
    if not mems:
        return {}
    top = mems[0]
    val = top.get("valence", 0)
    sal = top.get("salience", 0)
    if val < -0.5 and sal > 28:
        return {"fear_player": True}
    if val > 0.45 and sal > 25:
        return {"trust_player": True}
    return {}


def choose_action(npc, trait_weights=None, weather="Clear", memory_bias=None,
                  areas=None, institutions=None, npc_id=None, npcs=None):
    t = npc.get("traits", {})
    tw = trait_weights or {}
    bp = npc.get("behavior_profile", {})
    mb = memory_bias or {}

    def w(trait):
        return t.get(trait, 0) * tw.get(trait, 1.0)

    weights = {
        "trade":     w("greed") + 10 + bp.get("work", 0) * 0.08,
        "fight":     w("aggression") + bp.get("risk", 0) * 0.1,
        "hunt":      w("courage") * 0.6 + t.get("aggression", 0) * 0.2,
        "help":      w("kindness") + w("generosity") * 0.5 + bp.get("kindness", 0) * 0.12,
        "hide":      (100 - t.get("courage", 50)) * 0.6 + w("paranoia") * 0.3 + bp.get("caution", 0) * 0.1,
        "plan":      w("ambition") + w("wit") * 0.4,
        "study":     w("curiosity") + t.get("discipline", 0) * 0.3,
        "craft":     t.get("discipline", 0) * 0.5 + 8 + bp.get("work", 0) * 0.06,
        "socialise": w("humor") + w("kindness") * 0.4 + 8 + bp.get("social", 0) * 0.12,
        "travel":    w("ambition") * 0.3 + w("curiosity") * 0.2,
    }

    for action, bonus in _ROLE_BIAS.get(npc.get("role"), {}).items():
        weights[action] = weights.get(action, 5) + bonus

    # Scheduled activity strongly preferred when on routine
    sched_act = npc.get("schedule_activity")
    if sched_act and sched_act in weights:
        weights[sched_act] = weights.get(sched_act, 5) + 22

    primary_goal = (npc.get("goals") or [None])[0]
    if primary_goal:
        goal_actions = {
            "accumulate wealth": "trade",
            "gain power": "plan",
            "help others": "help",
            "settle an old score": "fight",
            "uncover a secret": "study",
        }
        for fragment, act in goal_actions.items():
            if fragment in primary_goal:
                weights[act] = weights.get(act, 5) + 14
                break

    if mb.get("fear_player"):
        weights["hide"] *= 2.2
        weights["socialise"] *= 0.35
        weights["fight"] *= 1.15
    if mb.get("trust_player"):
        weights["help"] *= 1.4
        weights["socialise"] *= 1.2

    if weather in ("Storm", "Snow", "Fog"):
        weights["hide"] *= 1.5
        weights["trade"] *= 0.7
        weights["hunt"] *= 0.6
        weights["travel"] *= 0.5
    elif weather == "Heatwave":
        weights["fight"] *= 1.2

    if areas:
        sl = areas.get(npc.get("area"), {}).get("storyline") or {}
        mults, area_override = apply_storyline_to_npc(
            npc, areas, tension=sl.get("tension", 30),
        )
        apply_storyline_weights(weights, mults)
        if area_override:
            npc["area"] = area_override

    if npc_id:
        rumor_action_bias(npc_id, weights)

    from simulation.npc_planning import apply_plan_weights, advance_subgoal
    from simulation.npc_emotions import emotion_action_bias
    from simulation.social_circles import social_circle_action_bias

    apply_plan_weights(npc, weights)
    emotion_action_bias(npc, weights)
    if npc_id:
        if npcs is None:
            npcs = load(NPC_FILE, {})
        social_circle_action_bias(npc_id, npcs, weights)

    if institutions and isinstance(npc.get("institution"), dict):
        inst = institutions.get(npc["institution"].get("id"), {})
        for act, mult in politics_action_bias(npc, inst).items():
            weights[act] = weights.get(act, 5) * mult

    obj = npc.get("personal_objective")
    obj_text = obj.get("text", "") if isinstance(obj, dict) else (obj or "")
    if obj_text:
        lower_obj = obj_text.lower()
        if any(w in lower_obj for w in ("steal", "rob", "heirloom", "fence")):
            weights["plan"] = weights.get("plan", 5) + 14
            weights["hide"] = weights.get("hide", 5) + 6
        if any(w in lower_obj for w in ("prove", "expose", "catch", "avenge", "ruin")):
            weights["plan"] = weights.get("plan", 5) + 12
            weights["study"] = weights.get("study", 5) + 8
        if any(w in lower_obj for w in ("wealth", "guild", "marry", "sell", "coin")):
            weights["trade"] = weights.get("trade", 5) + 12
        if any(w in lower_obj for w in ("save", "protect", "witness", "penitent")):
            weights["help"] = weights.get("help", 5) + 10

    for fear in (npc.get("fears") or [])[:2]:
        fl = fear.lower()
        if "violence" in fl or "betrayal" in fl:
            weights["hide"] = weights.get("hide", 5) * 1.25
            weights["fight"] = weights.get("fight", 5) * 0.85
        if "watch" in fl or "public" in fl:
            weights["socialise"] = weights.get("socialise", 5) * 0.8

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

    apply_schedules_to_npcs(npcs, world, load(AREAS_FILE, {}))
    areas = load(AREAS_FILE, {})
    institutions = load(INST_FILE, {})
    player = load(PLAYER_FILE, {})
    player_area = player.get("area")

    max_npcs = config.get("max_npcs_per_tick", len(npcs))
    npc_ids = [i for i, n in npcs.items() if n.get("status") == "alive"]
    if not npc_ids:
        save(NPC_FILE, npcs)
        return

    from simulation.story_manager import npc_simulation_weights
    from simulation.sim_tiers import hierarchical_npc_sample, run_abstract_regional_pulse

    weights = npc_simulation_weights(player, npcs, areas=areas, institutions=institutions)
    active, pulse_ids = hierarchical_npc_sample(
        npc_ids, npcs, player, weights, min(max_npcs, len(npc_ids)),
    )
    if pulse_ids:
        run_abstract_regional_pulse(pulse_ids, npcs, tick=tick)

    for npc_id in active:
        npc = npcs[npc_id]
        ts = npc.get("travel_state") or {}
        if ts.get("hours_remaining", 0) > 0:
            npc["last_action"] = "travel"
            log_event(
                "npc_action", npc_id, "travel",
                location=npc.get("location"), effects=["in_transit"],
                tick=tick,
            )
            continue
        location = npc.get("location", "unknown")
        action = choose_action(
            npc, trait_weights, weather, _memory_bias(npc_id),
            areas=areas, institutions=institutions, npc_id=npc_id, npcs=npcs,
        )
        from simulation.npc_planning import advance_subgoal
        from simulation.personality_drift import drift_from_survival
        advance_subgoal(npc, action)
        drift_from_survival(npc)
        if player_area and npc.get("area") == player_area:
            rumor_relationship_nudge(npc_id, player_present=True)
        effects = []

        try:
            check_goal_progress(npc, action)
        except Exception:
            log.exception("goal progress check failed for npc %s action %s", npc_id, action)

        if action == "trade":
            npc["wealth"] = npc.get("wealth", 0) + random.randint(1, 10)
            effects.append("wealth_change")

        elif action == "fight":
            effects.append("brawl")
            if npc.get("status") == "alive" and random.random() < 0.02:
                npc["status"] = "dead"
                effects.append("npc_death")

        elif action == "hunt":
            prey = monsters_in_area(npc.get("area"), monsters, city=npc.get("location"))
            if not prey:
                prey = [m for m in monsters.values()
                        if m.get("status") == "alive" and m.get("location") == npc.get("location")]
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
                kind = "charm" if npc.get("traits", {}).get("humor", 0) > 60 else "kindness"
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
                log.exception("npc travel failed for %s", npc_id)
        if train_from_action(npc, action):
            effects.append("skill_levelled")
        _heal_tick(npc)

        npc["last_action"] = action
        log_event("npc_action", npc_id, action, target=npc.pop("_interacted_with", None),
                  location=location, effects=effects, tick=tick)

    save(NPC_FILE, npcs)
    save(MON_FILE, monsters)
