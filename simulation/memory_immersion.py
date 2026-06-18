"""
Memory immersion — subjective NPC POV, salience decay, callbacks, gossip.

Makes memory feel alive: each NPC remembers differently, old trivia fades,
high-stakes beats surface sparingly, and strong memories ripple through society.
"""

from storage import load, save

MEM_FILE = "characters/npc_memories.json"
RUMOR_FILE = "rumors/rumors.json"
NPC_FILE = "characters/npcs.json"

DECAY_PER_TICK = 0.984
_HIGH_STAKES_TAGS = frozenset({"attack", "help", "threat", "insult", "theft", "gift"})
_MEM_TAG_TO_KIND = {
    "attack": "attack",
    "help": "help",
    "gift": "give",
    "threat": "threaten",
    "insult": "insult",
    "trade": "trade",
}


def ticks_elapsed(mem_tick, current_tick):
    if mem_tick is None or current_tick is None:
        return 0
    return max(0, int(current_tick) - int(mem_tick))


def effective_salience(mem, current_tick):
    """Salience at retrieval — decays with age, boosted by emotional weight."""
    sal = float(mem.get("salience") or mem.get("importance") or 20)
    elapsed = ticks_elapsed(mem.get("tick"), current_tick)
    decayed = sal * (DECAY_PER_TICK ** min(elapsed, 180))
    val = abs(float(mem.get("valence") or 0))
    return decayed * (1.0 + val * 0.35)


def score_at_retrieval(record, *, player=None, current_tick=None):
    """Importance × recency × emotional weight for ranked retrieval."""
    from simulation.importance_router import score_memory_record

    base = float(score_memory_record(record, player=player))
    tick = record.get("tick")
    if current_tick is not None and tick is not None:
        base *= DECAY_PER_TICK ** min(ticks_elapsed(tick, current_tick), 120)
    val = record.get("valence")
    if val is not None:
        base *= 1.0 + abs(float(val)) * 0.25
    sal = record.get("salience")
    if sal is not None:
        base = max(base, float(sal) * 0.35)
    return max(1.0, min(100.0, base))


def format_subjective_line(mem, npc_name):
    summary = (mem.get("summary") or "")[:110]
    if not summary:
        return ""
    val = float(mem.get("valence") or 0)
    if val <= -0.55:
        tone = "still raw for them — guarded or hostile"
    elif val <= -0.2:
        tone = "sits uneasy — shorter answers, watching"
    elif val >= 0.45:
        tone = "warms them — may offer a little more"
    else:
        tone = "colors their caution"
    return f'{npc_name} remembers ({tone}): "{summary}"'


def subjective_memory_lines(npc_id, npcs, *, current_tick, limit=2, query_words=None):
    """Top player-related memories from this NPC's POV."""
    from simulation.npc_memory_engine import player_memories

    if not npc_id:
        return []
    mems = player_memories(npc_id, n=10)
    scored = []
    for m in mems:
        score = effective_salience(m, current_tick)
        if query_words:
            text = (m.get("summary") or "").lower()
            score += sum(10 for w in query_words if w in text)
        if score >= 8:
            scored.append((score, m))
    scored.sort(key=lambda row: row[0], reverse=True)
    npc = (npcs or {}).get(npc_id, {})
    name = npc.get("name") or "They"
    return [
        format_subjective_line(m, name)
        for _, m in scored[:limit]
        if format_subjective_line(m, name)
    ]


def pick_memory_callback(player, focal_npc_id, *, kind, action_ctx, current_tick, npcs=None):
    """
    One salient past detail to echo in prose — used sparingly (not every beat).
    """
    if kind in ("wait", "rest", "withdraw", "meta"):
        return None
    ctx = action_ctx or {}
    plan = ctx.get("beat_plan") or {}
    if (plan.get("scene_plan") or {}).get("structure_hint") == "arrival":
        return None
    if not player.get("journal") and kind in ("explore", "travel"):
        return None

    candidates = []
    query_words = set((plan.get("memory_query") or "").lower().split())

    if focal_npc_id:
        for line in subjective_memory_lines(
            focal_npc_id, npcs, current_tick=current_tick, limit=1, query_words=query_words,
        ):
            candidates.append({"text": line, "source": "npc_pov", "score": 50})

    for rec in (player.get("beat_memory_log") or [])[:24]:
        if focal_npc_id and rec.get("target_id") not in (None, focal_npc_id):
            continue
        text = (rec.get("story_meaning") or rec.get("action") or "").strip()
        if not text:
            continue
        score = score_at_retrieval(rec, player=player, current_tick=current_tick)
        if query_words:
            score += sum(12 for w in query_words if w in text.lower())
        if score >= 28:
            candidates.append({
                "text": (
                    f"CALLBACK — let one concrete detail from earlier land naturally "
                    f"(do not announce 'I remember'): {text[:85]}"
                ),
                "source": "beat_log",
                "score": score,
            })

    if not candidates:
        return None
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[0]


def build_memory_trace(player, focal_npc_id, *, kind, action_ctx, current_tick, npcs=None):
    """Observability payload for boundary trace / debug."""
    callback = pick_memory_callback(
        player, focal_npc_id, kind=kind, action_ctx=action_ctx,
        current_tick=current_tick, npcs=npcs,
    )
    focal = subjective_memory_lines(
        focal_npc_id, npcs, current_tick=current_tick, limit=2,
    ) if focal_npc_id else []
    return {
        "callback_source": callback.get("source") if callback else None,
        "callback_preview": (callback.get("text") or "")[:120] if callback else None,
        "focal_memory_count": len(focal),
        "focal_preview": focal[0][:100] if focal else None,
    }


def surface_memory_limit(kind):
    """How many retrieved memories to inject — tight curation."""
    if kind in ("investigate", "accuse", "find", "search"):
        return 3
    if kind in ("talk", "personal_talk", "ask_about", "ask_name"):
        return 2
    return 2


def reinforce_target_relationship(target_id, mem_tag, *, check=None):
    """
    Supplemental relationship nudge from emotional memory (on top of action mechanics).
    Small — familiarity still gates large swings.
    """
    if not target_id or mem_tag not in _HIGH_STAKES_TAGS:
        return None
    action_kind = _MEM_TAG_TO_KIND.get(mem_tag)
    if not action_kind:
        return None
    from simulation.relationship_engine import (
        PLAYER_ACTION_REL,
        apply_npc_toward_player,
    )
    kind, intensity = PLAYER_ACTION_REL.get(action_kind, (None, 0))
    if not kind:
        return None
    return apply_npc_toward_player(
        target_id, kind, intensity=intensity * 0.4, check=check,
    )


def update_witness_beliefs(witness_ids, interaction_event, *, tick, target_id=None, limit=2):
    """Witnesses form lighter beliefs about what they saw."""
    if not interaction_event or not witness_ids:
        return False
    from simulation.belief_model import update_beliefs_from_event

    npcs = load(NPC_FILE, {})
    changed = False
    for wid in witness_ids[:limit]:
        if wid == target_id:
            continue
        npc = npcs.get(wid)
        if not npc or npc.get("status") != "alive":
            continue
        evt = dict(interaction_event)
        evt["importance"] = max(18, int(evt.get("importance", 40) * 0.45))
        update_beliefs_from_event(npc, evt, tick=tick)
        changed = True
    if changed:
        save(NPC_FILE, npcs)
    return changed


def absorb_npc_memories_into_reputation(player):
    """Fold episodic NPC memories about the player into reputation_profile."""
    from simulation.player_reputation import build_reputation_profile

    store = load(MEM_FILE, {})
    bumps = {"violent": 0.0, "merciful": 0.0, "suspicious": 0.0, "heroic": 0.0}
    current_tick = player.get("last_tick") or player.get("tick") or 0

    for mems in store.values():
        for m in mems:
            if not m.get("about_player") and "outsider" not in (m.get("summary") or ""):
                continue
            sal = effective_salience(m, current_tick)
            if sal < 12:
                continue
            val = float(m.get("valence") or 0)
            weight = sal / 80.0
            if val <= -0.45:
                bumps["violent"] += 5 * weight
                bumps["suspicious"] += 4 * weight
            elif val >= 0.35:
                bumps["merciful"] += 6 * weight
                bumps["heroic"] += 4 * weight

    profile = build_reputation_profile(player)
    for key, delta in bumps.items():
        profile[key] = min(100, profile.get(key, 0) + int(delta))
    player["reputation_profile"] = profile
    return profile


def propagate_social_memory_gossip(world, player, target_id, mem, *, tick, day, npcs):
    """
    Strong memories about the player spread to an ally's circle via information packets.
    Bounded — only high salience + emotional weight, only when target has allies.
    """
    if not mem or not target_id:
        return None
    if effective_salience(mem, tick) < 38:
        return None
    if abs(float(mem.get("valence") or 0)) < 0.3:
        return None

    from simulation.social_circles import circle_for_npc
    from simulation.information_packets import emit_information

    circle = circle_for_npc(target_id, npcs or {})
    allies = circle.get("allies") or []
    if not allies:
        return None

    target = (npcs or {}).get(target_id, {})
    target_name = target.get("name") or "someone"
    summary = (mem.get("summary") or "")[:90]
    text = f"{allies[0]} heard that {target_name} had trouble with the outsider — {summary}"
    interp = "dangerous" if mem.get("valence", 0) < -0.2 else "heroic"
    return emit_information(
        world,
        origin_area=player.get("area"),
        origin_city=player.get("location"),
        text=text,
        credibility=0.5,
        speed=1,
        tick=tick,
        interpretation=interp,
    )


def maybe_append_gossip_rumor(player, mem, *, tick):
    """High-salience player memories become local rumors."""
    if not mem:
        return None
    sal = float(mem.get("salience") or 0)
    if sal < 55:
        return None
    if abs(float(mem.get("valence") or 0)) < 0.4:
        return None

    rumors = load(RUMOR_FILE, [])
    if not isinstance(rumors, list):
        rumors = []
    summary = (mem.get("summary") or "something about the outsider")[:120]
    text = f"Word spreads: {summary}"
    rumor_id = f"mem_{tick}_{hash(summary) & 0xffff}"
    for r in rumors[-30:]:
        if isinstance(r, dict) and r.get("source_memory") == rumor_id:
            return None

    rumors.append({
        "source_event_id": rumor_id,
        "source_memory": rumor_id,
        "text": text,
        "interpretation": "dangerous" if mem.get("valence", 0) < -0.15 else "suspicious",
        "spread": min(100, int(sal * 0.7)),
        "importance": min(100, int(sal * 0.6)),
        "location": player.get("location"),
    })
    save(RUMOR_FILE, rumors[-200:])
    return text


def packets_as_rumor_whispers(world, player, *, limit=2):
    """Convert arrived information packets into narrator-ready whispers."""
    from simulation.information_packets import packets_for_area

    packets = packets_for_area(
        world, player.get("area"), city=player.get("location"), limit=limit,
    )
    lines = []
    for p in packets:
        text = (p.get("text") or "").strip()
        if text:
            cred = p.get("credibility", 0.5)
            prefix = "Whisper (uncertain)" if cred < 0.45 else "Whisper"
            lines.append(f"{prefix}: {text[:140]}")
    return lines
