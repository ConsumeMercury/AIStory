"""
Narrative memory — durable story meanings that outlive raw event logs.

Complements journal summaries and event retrieval with human-like consolidation.
"""

from simulation.event_importance import infer_story_meaning, score_event_importance

MAX_NARRATIVE_MEMORIES = 40


def add_narrative_memory(player, *, story_meaning, importance=50, arc_id=None, tick=None):
    if not story_meaning:
        return False
    rec = {
        "story_meaning": story_meaning[:240],
        "importance": max(1, min(100, int(importance))),
        "arc_id": arc_id,
        "tick": tick,
    }
    mems = player.setdefault("narrative_memories", [])
    if any(m.get("story_meaning") == rec["story_meaning"] for m in mems[-12:]):
        return False
    mems.append(rec)
    player["narrative_memories"] = sorted(
        mems, key=lambda m: m.get("importance", 0), reverse=True,
    )[:MAX_NARRATIVE_MEMORIES]
    return True


def record_beat_narrative_memory(player, *, kind, action, action_ctx, tick=None):
    """Capture story meaning from a player beat when importance is high enough."""
    ctx = action_ctx or {}
    meaning = infer_story_meaning(
        "player_action", action, kind=kind, target=ctx.get("target_id"),
    )
    if not meaning:
        return False
    imp = score_event_importance("player_action", action, target=ctx.get("target_id"))
    if kind in ("attack", "accuse", "confess", "blackmail", "investigate"):
        imp = max(imp, 70)
    elif kind in ("help", "give", "find", "search") and ctx.get("skill_check", {}).get("success"):
        imp = max(imp, 55)
    if imp < 50 and kind not in ("attack", "accuse", "confess", "investigate"):
        return False
    stakes = player.get("scene_stakes") or {}
    return add_narrative_memory(
        player,
        story_meaning=meaning,
        importance=imp,
        arc_id=stakes.get("arc_id"),
        tick=tick,
    )


def consolidate_journal_chunk(player, entries, *, npcs=None):
    """
    Compress a journal slice into one narrative memory entry.
    Called from journal compaction.
    """
    if not entries:
        return False
    actions = [e.get("kind") or "beat" for e in entries]
    places = {e.get("place") or e.get("location") for e in entries if e.get("place") or e.get("location")}
    focus_names = []
    npcs = npcs or {}
    for e in entries:
        fid = e.get("focus_npc")
        if fid:
            focus_names.append(npcs.get(fid, {}).get("name") or fid)
    place_bit = next(iter(places), "the district")
    focus_bit = focus_names[-1] if focus_names else "locals"
    kinds = ", ".join(sorted(set(actions))[:5])
    meaning = (
        f"Over several beats in {place_bit}, the outsider "
        f"({kinds}) pressed the thread with {focus_bit}."
    )
    tick = entries[-1].get("tick")
    return add_narrative_memory(player, story_meaning=meaning, importance=62, tick=tick)


def narrative_memory_block(player, *, limit=4):
    mems = player.get("narrative_memories") or []
    if not mems:
        return ""
    lines = []
    for m in mems[:limit]:
        lines.append(f"- [{m.get('importance', '?')}] {m.get('story_meaning', '')[:160]}")
    return (
        "NARRATIVE MEMORY (story meaning — permanent, do not contradict):\n"
        + "\n".join(lines)
    )
