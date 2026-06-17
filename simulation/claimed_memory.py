"""
Claimed vs actual memory — NPCs may lie about what they know.
"""

import random


def ensure_claimed_memory(npc):
    return npc.setdefault("claimed_memories", [])


def record_actual(npc, summary, *, tick=None, importance=50):
    npc.setdefault("actual_memories", []).append({
        "summary": summary[:160],
        "tick": tick,
        "importance": importance,
    })
    npc["actual_memories"] = npc["actual_memories"][-20:]


def set_claimed(npc, summary, *, truthful=True, tick=None):
    ensure_claimed_memory(npc).append({
        "summary": summary[:160],
        "truthful": truthful,
        "tick": tick,
    })
    npc["claimed_memories"] = npc["claimed_memories"][-15:]


def sync_claim_from_actual(npc, actual_summary, *, lie_chance=0.0, tick=None):
    """When NPC 'remembers' an event, they may distort it."""
    if not actual_summary:
        return
    if lie_chance > 0 and random.random() < lie_chance:
        distorted = actual_summary.replace("stole", "found").replace("attacked", "argued with")
        set_claimed(npc, distorted or actual_summary, truthful=False, tick=tick)
    else:
        set_claimed(npc, actual_summary, truthful=True, tick=tick)


def lie_bias_from_traits(npc):
    t = npc.get("traits", {})
    greed = t.get("greed", 50)
    honesty = t.get("honesty", 50)
    return max(0.05, min(0.65, (greed - honesty) / 120 + 0.1))


def interrogation_directive(npc, kind):
    """Narrator hint when player presses for truth."""
    if kind not in ("ask_about", "accuse", "blackmail", "personal_talk"):
        return ""
    claims = npc.get("claimed_memories") or []
    if not claims:
        return ""
    last = claims[-1]
    if last.get("truthful", True):
        return ""
    return (
        "INTERROGATION — this person may deflect or lie; their claimed memory "
        "does not match what actually happened. Show evasion, not omniscient narration."
    )


def record_beat_memory(npc, kind, action, *, tick=None):
    if kind in ("attack", "steal", "help", "accuse", "confess"):
        summary = f"The outsider {kind}: {(action or '')[:60]}"
        record_actual(npc, summary, tick=tick, importance=60 if kind == "attack" else 45)
        sync_claim_from_actual(npc, summary, lie_chance=lie_bias_from_traits(npc), tick=tick)
