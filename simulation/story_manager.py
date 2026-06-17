"""
Story registry — unified view of active narrative arcs for narration, memory, and sim.

Merges district storylines, starting pipeline, investigation cases, and goals
into one authoritative structure without replacing underlying systems.
"""

from storage import load

AREAS_FILE = "world/areas.json"
INST_FILE = "world/institutions.json"


def _district_suffix(area_id):
    return area_id.split(":")[-1] if area_id else ""


def sync_starting_pipeline_from_area(player, area_id, areas):
    """Keep player.starting_pipeline aligned with live area.storyline."""
    pipe = player.get("starting_pipeline") or {}
    if not pipe or pipe.get("area_id") != area_id:
        return False
    area = (areas or {}).get(area_id, {})
    sl = area.get("storyline") or {}
    if not sl:
        return False

    changed = False
    for key in ("stage", "current", "tension", "hook", "title", "theme"):
        val = sl.get(key)
        if val is not None and pipe.get(key) != val:
            pipe[key] = val
            changed = True
    stages = sl.get("stages")
    if stages and pipe.get("stages") != stages:
        pipe["stages"] = list(stages)
        changed = True
    key_ids = list(sl.get("key_npc_ids") or [])
    if key_ids and pipe.get("key_npc_ids") != key_ids:
        pipe["key_npc_ids"] = key_ids
        changed = True
    if changed:
        player["starting_pipeline"] = pipe
    return changed


def sync_all_pipelines(player, areas=None):
    """Sync every pipeline tied to a known area."""
    areas = areas if areas is not None else load(AREAS_FILE, {})
    pipe = player.get("starting_pipeline") or {}
    aid = pipe.get("area_id") or player.get("area")
    if aid:
        return sync_starting_pipeline_from_area(player, aid, areas)
    return False


def _arc_from_case(case, npcs):
    if not case or case.get("solved"):
        return None
    suspects = case.get("suspect_ids") or []
    victim_id = case.get("victim_id")
    stages = case.get("stages") or []
    stage = case.get("stage", 0)
    return {
        "arc_id": case.get("id") or "active_case",
        "kind": "investigation",
        "status": "active",
        "title": case.get("title", "Mystery"),
        "area_id": case.get("area_id"),
        "stage": stage,
        "stage_label": stages[min(stage, len(stages) - 1)] if stages else "investigate",
        "victim_id": victim_id,
        "suspects": list(suspects),
        "clues_found": sum(1 for e in case.get("evidence", []) if e.get("discovered")),
        "key_npc_ids": list(dict.fromkeys([victim_id] + suspects))[:6],
        "threat_level": min(100, 40 + stage * 15 + len(suspects) * 5),
        "next_beat": stages[min(stage + 1, len(stages) - 1)] if stages else "follow the lead",
        "hook": case.get("summary") or case.get("title", ""),
    }


def _arc_from_pipeline(pipe, areas):
    if not pipe:
        return None
    area_id = pipe.get("area_id")
    area = (areas or {}).get(area_id, {})
    sl = area.get("storyline") or {}
    stages = pipe.get("stages") or sl.get("stages") or []
    stage = pipe.get("stage", sl.get("stage", 0))
    return {
        "arc_id": f"district_{_district_suffix(area_id) or area_id or 'local'}",
        "kind": "district",
        "status": "active",
        "title": pipe.get("title") or area.get("name", "Local trouble"),
        "area_id": area_id,
        "stage": stage,
        "stage_label": pipe.get("current") or (stages[stage] if stages else ""),
        "key_npc_ids": list(pipe.get("key_npc_ids") or sl.get("key_npc_ids") or []),
        "threat_level": int(pipe.get("tension") or sl.get("tension") or 30),
        "next_beat": pipe.get("current") or pipe.get("hook", ""),
        "hook": pipe.get("hook", ""),
        "theme": pipe.get("theme") or sl.get("theme"),
    }


def _arc_from_area(player, areas):
    aid = player.get("area")
    if not aid:
        return None
    area = (areas or {}).get(aid, {})
    sl = area.get("storyline") or {}
    if not sl:
        return None
    stages = sl.get("stages") or []
    stage = sl.get("stage", 0)
    return {
        "arc_id": f"area_{aid}",
        "kind": "district",
        "status": "active",
        "title": sl.get("title") or area.get("name", ""),
        "area_id": aid,
        "stage": stage,
        "stage_label": sl.get("current") or (stages[stage] if stages else ""),
        "key_npc_ids": list(sl.get("key_npc_ids") or []),
        "threat_level": int(sl.get("tension") or 20),
        "next_beat": sl.get("current") or sl.get("hook", ""),
        "hook": sl.get("hook", ""),
        "theme": sl.get("theme"),
    }


def get_active_arcs(player, npcs=None, *, areas=None):
    """All currently active narrative arcs, highest priority first."""
    areas = areas if areas is not None else load(AREAS_FILE, {})
    npcs = npcs or {}
    arcs = []

    case_arc = _arc_from_case(player.get("active_case"), npcs)
    if case_arc:
        arcs.append(case_arc)

    pipe = player.get("starting_pipeline") or {}
    if pipe:
        pipe_arc = _arc_from_pipeline(pipe, areas)
        if pipe_arc and not any(a.get("arc_id") == pipe_arc.get("arc_id") for a in arcs):
            arcs.append(pipe_arc)
    elif player.get("area"):
        area_arc = _arc_from_area(player, areas)
        if area_arc:
            arcs.append(area_arc)

    return arcs


def get_primary_arc(player, npcs=None, *, areas=None):
    arcs = get_active_arcs(player, npcs, areas=areas)
    return arcs[0] if arcs else None


def build_story_manager_block(player, npcs=None, *, focal_npc_id=None, kind="general", areas=None):
    """Prominent block: what story is active and what this beat must advance."""
    arcs = get_active_arcs(player, npcs, areas=areas)
    if not arcs:
        return ""

    lines = ["ACTIVE STORY (you are inside this — do not rediscover from scratch):"]
    primary = arcs[0]
    lines.append(
        f"- «{primary.get('title', 'Plot')}» ({primary.get('kind', 'arc')}) — "
        f"stage {primary.get('stage', 0) + 1}: {str(primary.get('stage_label', ''))[:90]}"
    )
    if primary.get("next_beat"):
        lines.append(f"- Next beat pressure: {str(primary['next_beat'])[:90]}")
    if primary.get("key_npc_ids"):
        names = []
        for nid in primary["key_npc_ids"][:4]:
            nm = (npcs or {}).get(nid, {}).get("name") or nid
            names.append(nm)
        lines.append(f"- Story cast: {', '.join(names)}.")

    if len(arcs) > 1:
        other = arcs[1]
        lines.append(
            f"- Secondary thread: {other.get('title', 'plot')} "
            f"({str(other.get('stage_label', ''))[:60]})"
        )

    stakes = player.get("scene_stakes") or {}
    if stakes.get("dramatic_question"):
        lines.append(f"- Dramatic question: {stakes['dramatic_question'][:100]}")
    if stakes.get("lose"):
        lines.append(f"- At stake if this fails: {stakes['lose'][:80]}")
    if stakes.get("gain"):
        lines.append(f"- Possible gain: {stakes['gain'][:80]}")

    if kind in ("talk", "ask_about", "personal_talk") and focal_npc_id:
        lines.append("- This dialogue must answer or complicate the active story — not filler.")

    return "\n".join(lines)


def npc_simulation_weights(player, npcs, *, areas=None, institutions=None):
    """Relative tick weights — story-relevant and nearby NPCs sim more often."""
    areas = areas if areas is not None else load(AREAS_FILE, {})
    institutions = institutions or load(INST_FILE, {})
    primary = get_primary_arc(player, npcs, areas=areas)
    key_ids = set(primary.get("key_npc_ids") or []) if primary else set()
    player_area = player.get("area")
    player_city = player.get("location")
    focus = player.get("scene_focus")

    weights = {}
    for nid, npc in (npcs or {}).items():
        if npc.get("status") != "alive":
            continue
        w = 1.0
        if npc.get("area") == player_area:
            w += 5.0
        elif npc.get("location") == player_city:
            w += 2.0
        if nid in key_ids:
            w += 8.0
        if nid == focus:
            w += 6.0
        inst = npc.get("institution") or {}
        if inst.get("rank") in ("leader", "master", "captain", "high priest"):
            w += 3.0
        if (npc.get("personal_objective") or {}).get("text"):
            w += 1.5
        # Regional simulation tiers — player district full weight, same city partial, far minimal
        if player_area and npc.get("area") == player_area:
            w *= 1.0
        elif player_city and npc.get("location") == player_city:
            w *= 0.55
        else:
            w *= 0.12
        weights[nid] = w
    return weights


def weighted_npc_sample(npc_ids, weights, k):
    """Sample without replacement using story/proximity weights."""
    import random

    if not npc_ids:
        return []
    k = min(k, len(npc_ids))
    pool = list(npc_ids)
    chosen = []
    for _ in range(k):
        wts = [max(0.1, weights.get(nid, 1.0)) for nid in pool]
        total = sum(wts)
        if total <= 0:
            pick = random.choice(pool)
        else:
            pick = random.choices(pool, weights=wts, k=1)[0]
        chosen.append(pick)
        pool.remove(pick)
    return chosen


def record_turn_story_progress(player, *, kind, action_ctx, areas=None):
    """Update scene stakes and nudge district tension on meaningful beats."""
    areas = areas if areas is not None else load(AREAS_FILE, {})
    sync_all_pipelines(player, areas)

    ctx = action_ctx or {}
    arc = get_primary_arc(player, areas=areas)
    question = None
    gain = None
    lose = None

    if arc:
        title = arc.get("title", "the plot")
        if kind in ("ask_about", "investigate", "find", "search"):
            question = f"What will {title} reveal next?"
            gain = "a clue or lead"
            lose = "trust or time"
        elif kind in ("talk", "personal_talk", "accuse", "blackmail"):
            question = f"Will anyone break silence about {title}?"
            gain = "information or alliance"
            lose = "goodwill or safety"
        elif kind == "attack":
            question = "Who pays for violence here?"
            lose = "life or standing"
        elif kind == "explore":
            gain = "orientation in the district"
    check = ctx.get("skill_check") or {}
    if check and not check.get("success"):
        lose = lose or "the other's patience"

    player["scene_stakes"] = {
        "dramatic_question": question,
        "gain": gain,
        "lose": lose,
        "purpose": arc.get("next_beat") if arc else None,
        "arc_id": arc.get("arc_id") if arc else None,
    }

    aid = player.get("area")
    if not aid or kind in ("wait", "rest", "meta"):
        return

    area = areas.get(aid, {})
    sl = area.get("storyline")
    if not sl:
        return

    bump = 0
    if kind in ("investigate", "ask_about", "accuse", "find", "search"):
        bump = 2 if check.get("success", True) else 1
    elif kind in ("talk", "personal_talk") and ctx.get("target_id"):
        bump = 1
    if bump:
        sl["tension"] = min(100, int(sl.get("tension", 20)) + bump)
        sync_starting_pipeline_from_area(player, aid, areas)


def nudge_area_storyline_on_advance(area_id, areas, player=None):
    """After background storyline advance, sync player pipeline."""
    if player is None:
        from storage import load as _load
        player = _load("player/player.json", {})
    if player and area_id:
        return sync_starting_pipeline_from_area(player, area_id, areas)
    return False
