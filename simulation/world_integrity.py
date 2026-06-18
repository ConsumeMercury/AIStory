"""
Deep referential-integrity audit across JSON stores.

Detects dangling IDs, out-of-bounds values, clock drift, and cross-store mismatches
that world_health_report surfaces as issues/warnings.
"""

from __future__ import annotations

from simulation.relationship_engine import DIMS
from simulation.world_clock import clock_coherence_issue, time_of_day_from_hour

_REL_DIMS = set(DIMS) | {"familiarity", "interactions"}
_COMMAND_LIKE = (
    "talk to", "ask ", "go to", "wait ", "attack ", "find ", "search ",
    "look around", "give ", "help ",
)


def run_integrity_audit(
    *,
    player,
    npcs,
    areas,
    institutions,
    rumors,
    events,
    world,
    relationships=None,
    npc_memories=None,
    memories=None,
):
    """
    Scan stores for referential integrity and quiet data divergence.
    Returns (issues, warnings) — issues fail health score; warnings reduce it.
    """
    issues = []
    warnings = []
    npc_ids = set(npcs.keys())
    area_ids = set(areas.keys())

    clock_issue = clock_coherence_issue(world)
    if clock_issue:
        issues.append(clock_issue)

    hc = world.get("hour_count")
    hour = world.get("hour")
    if hc is not None and hour is not None and hc % 24 != hour:
        issues.append(
            f"hour_count {hc} and hour {hour} disagree (expected hour={hc % 24})"
        )

    for nid, npc in npcs.items():
        if npc.get("status") != "alive":
            continue
        if not (npc.get("name") or "").strip():
            issues.append(f"alive NPC {nid!r} has no name")
        if not npc.get("role"):
            warnings.append(f"alive NPC {nid!r} missing role")
        if not npc.get("gender"):
            warnings.append(f"alive NPC {nid!r} missing gender")
        aid = npc.get("area")
        if aid and aid not in area_ids:
            warnings.append(f"NPC {nid!r} references unknown area {aid!r}")

    focus = player.get("scene_focus")
    if focus:
        if focus not in npc_ids:
            issues.append(f"scene_focus {focus!r} not in npcs.json")
        elif npcs.get(focus, {}).get("status") != "alive":
            issues.append(f"scene_focus {focus!r} points to non-alive NPC")

    cast = player.get("scene_cast") or {}
    cast_ids = cast.get("ids") or []
    cast_area = cast.get("area")
    player_area = player.get("area")
    if cast_area and player_area and cast_area != player_area:
        warnings.append(
            f"scene_cast area {cast_area!r} != player area {player_area!r}"
        )
    dead_cast = [
        cid for cid in cast_ids
        if cid not in npc_ids or npcs[cid].get("status") != "alive"
    ]
    if dead_cast:
        warnings.append(f"scene_cast lists {len(dead_cast)} absent/dead NPC id(s)")

    pending = player.get("pending_target_clarification")
    if pending:
        opts = pending.get("options") or []
        stale = [o.get("id") for o in opts if o.get("id") and o.get("id") not in npc_ids]
        if stale:
            issues.append(
                f"pending_target_clarification references missing NPCs: {stale[:3]}"
            )

    known = player.get("known_npcs") or {}
    stale_known = [nid for nid in known if nid not in npc_ids][:5]
    if stale_known:
        warnings.append(
            f"known_npcs references {len(stale_known)} missing NPC id(s): {stale_known[:3]}"
        )

    met = player.get("met_npcs") or []
    stale_met = [nid for nid in met if nid not in npc_ids][:5]
    if stale_met:
        warnings.append(f"met_npcs lists missing NPC id(s): {stale_met[:3]}")

    case = player.get("active_case") or {}
    if case and not case.get("solved"):
        victim = case.get("victim_id")
        if victim and victim in npcs and npcs[victim].get("status") == "alive":
            if case.get("stage", 0) > 0:
                warnings.append("active case victim still alive after investigation started")
        for sid in case.get("suspect_ids") or []:
            if sid not in npc_ids:
                issues.append(f"case suspect {sid!r} missing from npcs")

    pipe = player.get("starting_pipeline") or {}
    pipe_area = pipe.get("area_id")
    if pipe_area and pipe_area not in area_ids:
        warnings.append(f"starting_pipeline area {pipe_area!r} missing from areas")

    if relationships:
        missing_edges = 0
        missing_sources = 0
        oob_edges = []
        for src, edges in relationships.items():
            if src != "player" and src not in npc_ids:
                missing_sources += 1
            if not isinstance(edges, dict):
                continue
            for tgt, rel in edges.items():
                if tgt != "player" and tgt not in npc_ids:
                    missing_edges += 1
                if not isinstance(rel, dict):
                    continue
                for dim, val in rel.items():
                    if dim not in _REL_DIMS:
                        continue
                    if isinstance(val, (int, float)) and (val < 0 or val > 100):
                        oob_edges.append(f"{src!r}->{tgt!r} {dim}={val}")
        if missing_sources:
            warnings.append(
                f"{missing_sources} relationship graph source id(s) missing from npcs"
            )
        if missing_edges:
            warnings.append(
                f"{missing_edges} relationship edge(s) target missing NPCs"
            )
        for msg in oob_edges[:3]:
            issues.append(f"relationship {msg} out of bounds")
        if len(oob_edges) > 3:
            warnings.append(f"{len(oob_edges)} relationship values out of bounds")

    if institutions:
        dead_inst = 0
        for inst in institutions.values():
            members = inst.get("members") or []
            if isinstance(members, dict):
                members = list(members.keys())
            for mid in list(members)[:50]:
                if mid not in npc_ids:
                    dead_inst += 1
            loc = inst.get("area") or inst.get("location")
            if isinstance(loc, str) and loc not in area_ids and loc not in npc_ids:
                if ":" in loc or loc.startswith("city"):
                    warnings.append(f"institution references unknown area {loc!r}")
        if dead_inst:
            warnings.append(f"{dead_inst} institution member refs point to missing NPCs")

    if npc_memories:
        missing_buckets = 0
        missing_participants = 0
        raw_command_memories = 0
        for owner_id, mems in npc_memories.items():
            if owner_id not in npc_ids:
                missing_buckets += 1
            for mem in mems or []:
                summary = (mem.get("summary") or "").lower()
                if "outsider" in summary:
                    tail = summary.split("outsider", 1)[-1].strip()
                    if any(tail.startswith(cmd) for cmd in _COMMAND_LIKE):
                        raw_command_memories += 1
                for pid in mem.get("participants") or []:
                    if pid not in ("player",) and pid not in npc_ids:
                        missing_participants += 1
        if missing_buckets:
            warnings.append(
                f"{missing_buckets} npc_memories bucket(s) for removed NPC ids"
            )
        if missing_participants:
            warnings.append(
                f"{missing_participants} memory participant ref(s) point to missing NPCs"
            )
        if raw_command_memories:
            warnings.append(
                f"{raw_command_memories} memory summar(ies) look like raw player commands"
            )

    if isinstance(rumors, list):
        for rumor in rumors[:200]:
            text = (rumor.get("text") or rumor.get("summary") or "").lower()
            for nid in npc_ids:
                name = (npcs[nid].get("name") or "").split()[0].lower()
                if len(name) > 3 and name in text and npcs[nid].get("status") == "dead":
                    pass  # dead NPC rumors are ok
            subj = rumor.get("subject_id") or rumor.get("about_id")
            if subj and subj not in npc_ids and subj != "player":
                warnings.append(f"rumor subject {subj!r} missing from npcs")

    display_names = {}
    for aid, area in areas.items():
        label = (area.get("name") or area.get("label") or "").strip().lower()
        if not label:
            continue
        city = aid.split(":", 1)[0] if ":" in aid else ""
        key = (city, label)
        if key in display_names:
            warnings.append(
                f"duplicate area name {label!r} in city {city!r}: "
                f"{display_names[key]!r} and {aid!r}"
            )
        else:
            display_names[key] = aid

    if player_area and player_area not in area_ids:
        issues.append(f"player area {player_area!r} missing from areas.json")

    return issues, warnings


def expected_time_of_day(world):
    """Return authoritative time_of_day for a world dict (recomputed if needed)."""
    if not world:
        return "day"
    hour = world.get("hour")
    if hour is not None:
        return time_of_day_from_hour(hour)
    return world.get("time_of_day") or "day"
