"""
Memory consolidator — compress noise and merge duplicate narrative memories.
"""

CONSOLIDATE_EVERY_TURNS = 25


def _similar(a, b):
    a = (a or "").lower()
    b = (b or "").lower()
    if not a or not b:
        return False
    if a == b:
        return True
    aw = set(a.split())
    bw = set(b.split())
    if len(aw) < 4:
        return False
    overlap = len(aw & bw) / max(1, len(aw | bw))
    return overlap >= 0.72


def merge_narrative_memories(player):
    from simulation.importance_router import should_retain_memory

    mems = player.get("narrative_memories") or []
    if len(mems) < 2:
        return False
    merged = []
    changed = False
    for m in sorted(mems, key=lambda x: x.get("importance", 0), reverse=True):
        if not should_retain_memory(m, player=player, threshold=28):
            changed = True
            continue
        dup = next((x for x in merged if _similar(x.get("story_meaning"), m.get("story_meaning"))), None)
        if dup:
            dup["importance"] = max(dup.get("importance", 0), m.get("importance", 0))
            changed = True
        else:
            merged.append(dict(m))
    if changed or len(merged) != len(mems):
        player["narrative_memories"] = merged[:40]
        return True
    return changed


def consolidate_causal_links(player):
    links = player.get("causal_links") or []
    if len(links) < 2:
        return False
    merged = []
    changed = False
    for link in sorted(links, key=lambda x: x.get("importance", 0), reverse=True):
        dup = next((x for x in merged if _similar(x.get("summary"), link.get("summary"))), None)
        if dup:
            dup["importance"] = max(dup.get("importance", 0), link.get("importance", 0))
            changed = True
        else:
            merged.append(dict(link))
    if changed:
        player["causal_links"] = merged[:40]
    return changed


def maybe_consolidate_player_memories(player, *, tick=None):
    """
    Periodic dedup of narrative memory and causal links.
    Returns True if player was modified.
    """
    last = player.get("_last_consolidation_tick", 0)
    if tick is not None and tick - last < CONSOLIDATE_EVERY_TURNS:
        return False
    changed = merge_narrative_memories(player)
    changed = consolidate_causal_links(player) or changed
    if tick is not None:
        player["_last_consolidation_tick"] = tick
    return changed
