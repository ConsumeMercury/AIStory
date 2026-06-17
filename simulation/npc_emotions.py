"""
Temporary NPC emotions — decay over hours; bias actions and narrator tone.
"""

EMOTIONS = ("anger", "fear", "joy", "grief", "stress")
DECAY_PER_TICK = 0.08


def get_emotions(npc):
    return npc.setdefault("emotions", {})


def nudge_emotion(npc, name, delta, *, cap=100):
    if name not in EMOTIONS:
        return
    em = get_emotions(npc)
    em[name] = max(0, min(cap, int(em.get(name, 0) + delta)))


def emotions_from_beat(npc, kind, *, success=True, intensity=1.0):
    scale = intensity
    if kind in ("attack", "threaten"):
        nudge_emotion(npc, "anger", int(12 * scale))
        nudge_emotion(npc, "fear", int(8 * scale))
        nudge_emotion(npc, "stress", int(10 * scale))
    elif kind in ("insult", "accuse", "blackmail"):
        nudge_emotion(npc, "anger", int(10 * scale))
        nudge_emotion(npc, "stress", int(8 * scale))
    elif kind in ("help", "give", "show_respect"):
        if success:
            nudge_emotion(npc, "joy", int(10 * scale))
            nudge_emotion(npc, "stress", -int(6 * scale))
    elif kind == "confess":
        nudge_emotion(npc, "stress", int(14 * scale))
        nudge_emotion(npc, "grief", int(6 * scale))


def decay_emotions(npc):
    em = get_emotions(npc)
    if not em:
        return False
    changed = False
    for name in EMOTIONS:
        val = em.get(name, 0)
        if val <= 0:
            continue
        new_val = max(0, int(val - max(1, val * DECAY_PER_TICK)))
        if new_val != val:
            em[name] = new_val
            changed = True
    return changed


def decay_all_npcs(npcs):
    changed = False
    for npc in (npcs or {}).values():
        if npc.get("status") != "alive":
            continue
        if decay_emotions(npc):
            changed = True
    return changed


def emotion_action_bias(npc, weights):
    em = get_emotions(npc)
    if em.get("anger", 0) >= 40:
        weights["fight"] = weights.get("fight", 5) * 1.2
        weights["socialise"] = weights.get("socialise", 5) * 0.75
    if em.get("fear", 0) >= 35:
        weights["hide"] = weights.get("hide", 5) * 1.35
    if em.get("stress", 0) >= 45:
        weights["plan"] = weights.get("plan", 5) * 1.15
    if em.get("joy", 0) >= 30:
        weights["help"] = weights.get("help", 5) * 1.2
        weights["socialise"] = weights.get("socialise", 5) * 1.15


def focal_emotion_block(npc_id, npcs):
    npc = (npcs or {}).get(npc_id, {})
    em = get_emotions(npc)
    active = [(k, v) for k, v in em.items() if v >= 25]
    if not active:
        return ""
    bits = ", ".join(f"{k} {v}" for k, v in sorted(active, key=lambda x: -x[1])[:3])
    label = npc.get("name") or npc_id
    return f"FOCAL MOOD ({label} — show in posture/tone, not labels): {bits}."
