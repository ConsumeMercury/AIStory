"""
Unified beat memory record — single write path for player-turn memory side effects.

Canonical BeatMemoryRecord on player.beat_memory_log; derived stores updated in one call.
"""

from storage import load, save

NPC_FILE = "characters/npcs.json"
INST_FILE = "world/institutions.json"
BEAT_LOG_CAP = 120


def _witness_ids(focus_npcs, present, *, kind, target_id):
    focus_ids = [n["id"] for n in (focus_npcs or [])]
    mem_ids = focus_ids if focus_ids else []
    if not mem_ids and present:
        mem_ids = [present[0]["id"]]
    if kind == "attack" and target_id:
        mem_ids = list(dict.fromkeys(mem_ids + [target_id]))
    return mem_ids


def _append_beat_memory_record(
    player,
    *,
    kind,
    action,
    action_ctx,
    tick,
    focal_id,
    witness_ids,
    importance,
    story_meaning=None,
    interaction_event=None,
):
    from simulation.memory_schema import build_memory_record
    from simulation.importance_router import score_memory_record

    record = build_memory_record(
        kind=kind,
        action=action,
        action_ctx=action_ctx,
        tick=tick,
        focal_id=focal_id,
        witness_ids=witness_ids,
        importance=importance,
        story_meaning=story_meaning,
        interaction_event=interaction_event,
    )
    log = player.setdefault("beat_memory_log", [])
    log.append(record)
    player["beat_memory_log"] = sorted(
        log,
        key=lambda r: score_memory_record(
            {"importance": r.get("importance"), "story_meaning": r.get("story_meaning") or r.get("fact") or r.get("action")},
            player=player,
        ),
        reverse=True,
    )[:BEAT_LOG_CAP]
    return record


def record_beat_outcome(
    player,
    *,
    kind,
    action,
    action_ctx,
    world,
    tick,
    focal_id,
    focus_npcs,
    present,
    interaction_event=None,
    log_player_action=True,
):
    """
    Authoritative memory write for one player beat.

    Updates: npc_memories, narrative_memories, causal_links, beat_memory_log,
    focal NPC beliefs/claimed memory/emotions, institution memory, embeddings.
    Returns summary dict for callers.
    """
    from simulation.importance_router import score_event
    from simulation.event_importance import infer_story_meaning
    from simulation.memory_embeddings import ingest_event_vector
    from simulation.npc_memory_engine import record_player_action
    from simulation.narrative_memory import record_beat_narrative_memory
    from simulation.narrative_causality import record_from_beat
    from simulation.claimed_memory import record_beat_memory
    from simulation.belief_model import update_beliefs_from_event
    from simulation.npc_emotions import emotions_from_beat
    from simulation.personality_drift import drift_from_beat
    from simulation.institution_memory import record_from_player_action
    from simulation.memory_immersion import (
        absorb_npc_memories_into_reputation,
        maybe_append_gossip_rumor,
        propagate_social_memory_gossip,
        reinforce_target_relationship,
        update_witness_beliefs,
    )
    from simulation.npc_memory_engine import player_memories

    ctx = action_ctx or {}
    target_id = ctx.get("target_id") or focal_id
    player["last_tick"] = tick
    mem_tag = ctx.get("memory_tag", "general")
    witness_ids = _witness_ids(focus_npcs, present, kind=kind, target_id=target_id)

    if log_player_action and witness_ids:
        record_player_action(
            witness_ids,
            mem_tag,
            action,
            player.get("area") or player.get("location"),
            tick,
            world.get("day"),
            target_id=target_id,
            intensity=1.2 if kind in ("threaten", "help", "insult") else 1.0,
        )

    importance = 40
    if interaction_event:
        importance = score_event(interaction_event, player=player)
        interaction_event["importance"] = importance
        ingest_event_vector(player, interaction_event)

    record_beat_narrative_memory(
        player, kind=kind, action=action, action_ctx=ctx, tick=tick,
    )
    record_from_beat(player, kind, ctx, world, tick=tick)

    story_meaning = infer_story_meaning(
        "player_action", action, kind=kind, target=target_id,
    )
    beat_record = _append_beat_memory_record(
        player,
        kind=kind,
        action=action,
        action_ctx=ctx,
        tick=tick,
        focal_id=focal_id,
        witness_ids=witness_ids,
        importance=importance,
        story_meaning=story_meaning,
        interaction_event=interaction_event,
    )

    npcs_live = load(NPC_FILE, {})
    institutions = load(INST_FILE, {})
    target_live = npcs_live.get(target_id) if target_id else None
    check = ctx.get("skill_check") or {}
    success = check.get("success", True)
    target_changed = False

    if target_id and target_live:
        emotions_from_beat(target_live, kind, success=success)
        drift_from_beat(target_live, kind, success=success)
        record_beat_memory(target_live, kind, action, tick=tick)
        if interaction_event:
            update_beliefs_from_event(target_live, interaction_event, tick=tick)
        reinforce_target_relationship(
            target_id, mem_tag, check=ctx.get("skill_check"),
        )
        target_changed = True
        save(NPC_FILE, npcs_live)

    if interaction_event and witness_ids:
        update_witness_beliefs(
            witness_ids, interaction_event, tick=tick, target_id=target_id,
        )

    if log_player_action and target_id:
        top_mem = player_memories(target_id, n=1)
        if top_mem:
            maybe_append_gossip_rumor(player, top_mem[0], tick=tick)
            propagate_social_memory_gossip(
                world, player, target_id, top_mem[0],
                tick=tick, day=world.get("day"), npcs=npcs_live,
            )

    absorb_npc_memories_into_reputation(player)

    if target_live:
        record_from_player_action(
            institutions, player, kind, ctx, target_live, tick=tick,
        )
        save(INST_FILE, institutions)

    return {
        "target_id": target_id,
        "target_live": target_live,
        "witness_ids": witness_ids,
        "importance": importance,
        "target_changed": target_changed,
        "institutions": institutions,
        "npcs_live": npcs_live,
        "memory_id": beat_record.get("id") if beat_record else None,
    }
