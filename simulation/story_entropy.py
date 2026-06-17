"""
Story entropy — measure unresolved plot noise; hint when arcs stagnate.
"""

STALE_TENSION_THRESHOLD = 85
ENTROPY_WARN = 55


def score_story_entropy(player, npcs=None, *, areas=None):
    """Higher = more unresolved/stale narrative pressure."""
    from storage import load

    score = 0
    npcs = npcs or {}
    areas = areas if areas is not None else load("world/areas.json", {})

    case = player.get("active_case") or {}
    if case and not case.get("solved"):
        stage = case.get("stage", 0)
        score += 15 + stage * 8
        if stage >= 2 and len(case.get("evidence") or []) == 0:
            score += 12

    pending = player.get("pending_consequences") or []
    score += min(20, len(pending) * 4)

    promises = [p for p in (player.get("narrative_promises") or []) if not p.get("resolved")]
    score += min(18, len(promises) * 5)

    journal = player.get("journal") or []
    if len(journal) > 120:
        score += 10

    aid = player.get("area")
    if aid:
        sl = (areas.get(aid) or {}).get("storyline") or {}
        tension = int(sl.get("tension") or 0)
        if tension >= STALE_TENSION_THRESHOLD:
            score += 14

    goals = [g for g in (player.get("goals") or []) if not g.get("complete")]
    if len(goals) > 3:
        score += 8

    focus = player.get("scene_focus")
    if focus and focus not in npcs:
        score += 6

    return min(100, score)


def entropy_narrator_block(player, npcs=None, *, areas=None):
    score = score_story_entropy(player, npcs, areas=areas)
    if score < ENTROPY_WARN:
        return ""
    return (
        f"STORY PRESSURE (entropy {score}/100 — tighten or pay off a thread this beat): "
        "Choose one open thread and advance, complicate, or close it. "
        "Do not introduce a unrelated mystery."
    )


def nudge_stale_district_tension(player, areas):
    """Light automatic pressure relief when tension maxes without progress."""
    aid = player.get("area")
    if not aid:
        return False
    area = areas.get(aid, {})
    sl = area.get("storyline")
    if not sl:
        return False
    if int(sl.get("tension") or 0) < STALE_TENSION_THRESHOLD:
        return False
    stages = sl.get("stages") or []
    stage = int(sl.get("stage") or 0)
    if stage + 1 < len(stages):
        sl["stage"] = stage + 1
        sl["current"] = stages[stage + 1]
        sl["tension"] = max(40, int(sl.get("tension", 80)) - 15)
        from simulation.story_manager import sync_starting_pipeline_from_area
        sync_starting_pipeline_from_area(player, aid, areas)
        return True
    return False
