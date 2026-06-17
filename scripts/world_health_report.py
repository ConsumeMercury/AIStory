"""
World health report — automated checks for save integrity and narrative drift.

Run manually or from verify_all:
  python scripts/world_health_report.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from storage import load


def _file_size(path):
    full = os.path.join(ROOT, path.replace("/", os.sep))
    if not os.path.isfile(full):
        return 0
    return os.path.getsize(full)


def run_world_health_report(*, strict=False):
    issues = []
    warnings = []

    player = load("player/player.json", {})
    npcs = load("characters/npcs.json", {})
    areas = load("world/areas.json", {})
    institutions = load("world/institutions.json", {})
    rumors = load("rumors/rumors.json", [])
    events = load("events/event_log.json", [])

    if not player.get("area"):
        warnings.append("player has no area set")

    focus = player.get("scene_focus")
    if focus and focus not in npcs:
        issues.append(f"scene_focus {focus!r} not in npcs.json")
    elif focus and npcs.get(focus, {}).get("status") != "alive":
        issues.append(f"scene_focus {focus!r} points to non-alive NPC")
    elif focus:
        focus_npc = npcs.get(focus, {})
        player_area = player.get("area")
        if player_area and focus_npc.get("area") and focus_npc.get("area") != player_area:
            warnings.append(
                f"scene_focus {focus!r} is in {focus_npc.get('area')!r}, player in {player_area!r}"
            )

    pending = player.get("pending_target_clarification")
    if pending:
        opts = pending.get("options") or []
        stale = [o.get("id") for o in opts if o.get("id") and o.get("id") not in npcs]
        if stale:
            issues.append(f"pending_target_clarification references missing NPCs: {stale[:3]}")

    cast = player.get("scene_cast") or {}
    cast_ids = cast.get("ids") or []
    dead_cast = [
        cid for cid in cast_ids
        if cid not in npcs or npcs[cid].get("status") != "alive"
    ]
    if dead_cast:
        warnings.append(f"scene_cast lists {len(dead_cast)} absent/dead NPC id(s)")

    stats = player.get("stats") or {}
    if player and not stats.get("max_health"):
        warnings.append("player stats missing max_health")

    pipe = player.get("starting_pipeline") or {}
    pipe_area = pipe.get("area_id")
    if pipe_area and pipe_area not in areas:
        warnings.append(f"starting_pipeline area {pipe_area!r} missing from areas")

    case = player.get("active_case") or {}
    if case and not case.get("solved"):
        victim = case.get("victim_id")
        if victim and victim in npcs and npcs[victim].get("status") == "alive":
            if case.get("stage", 0) > 0:
                warnings.append("active case victim still alive after investigation started")
        for sid in case.get("suspect_ids") or []:
            if sid not in npcs:
                issues.append(f"case suspect {sid!r} missing from npcs")

    orphan_areas = []
    for nid, npc in npcs.items():
        if npc.get("status") != "alive":
            continue
        aid = npc.get("area")
        if aid and aid not in areas:
            orphan_areas.append(nid)
    if orphan_areas:
        warnings.append(f"{len(orphan_areas)} NPC(s) reference unknown areas")

    dead_inst_refs = 0
    for inst in institutions.values():
        members = inst.get("members") or []
        if isinstance(members, dict):
            members = list(members.keys())
        for mid in list(members)[:50]:
            if mid not in npcs:
                dead_inst_refs += 1
    if dead_inst_refs:
        warnings.append(f"{dead_inst_refs} institution member refs point to missing NPCs")

    if isinstance(rumors, list) and len(rumors) > 180:
        warnings.append(f"rumor list large ({len(rumors)} entries)")

    if isinstance(events, list) and len(events) > 5000:
        warnings.append(f"event log large ({len(events)} entries)")

    try:
        from simulation.event_archiver import archive_stats
        estats = archive_stats()
        if estats.get("hot_events", 0) > estats.get("hot_cap", 2500):
            warnings.append(
                f"event log over hot cap ({estats['hot_events']}/{estats['hot_cap']})"
            )
        if estats.get("archived_events_total", 0):
            pass  # archival active — informational only
    except Exception:
        estats = {}

    journal = player.get("journal") or []
    if len(journal) > 280:
        warnings.append(f"journal near cap ({len(journal)} entries)")

    save_bytes = sum(
        _file_size(p)
        for p in (
            "player/player.json",
            "characters/npcs.json",
            "events/event_log.json",
            "characters/npc_memories.json",
        )
    )
    if save_bytes > 2_000_000:
        warnings.append(f"core save files ~{save_bytes // 1024}KB — consider compaction")

    from simulation.story_entropy import score_story_entropy
    entropy = score_story_entropy(player, npcs, areas=areas)
    if entropy >= 70:
        warnings.append(f"high story entropy ({entropy}/100) — many unresolved threads")

    score = 100
    score -= len(issues) * 15
    score -= len(warnings) * 5
    score = max(0, min(100, score))

    return {
        "score": score,
        "entropy": entropy,
        "issues": issues,
        "warnings": warnings,
        "counts": {
            "npcs": len(npcs),
            "areas": len(areas),
            "rumors": len(rumors) if isinstance(rumors, list) else 0,
            "events": len(events) if isinstance(events, list) else 0,
            "journal": len(journal),
            **({f"events_{k}": v for k, v in (estats or {}).items()} if estats else {}),
        },
    }


def main():
    report = run_world_health_report()
    print(json.dumps(report, indent=2))
    if report["issues"]:
        print(f"\nHealth score: {report['score']}/100 — FAILED ({len(report['issues'])} issues)")
        sys.exit(1)
    print(f"\nHealth score: {report['score']}/100 — OK")
    if report["warnings"]:
        print(f"({len(report['warnings'])} warnings)")
    sys.exit(0)


if __name__ == "__main__":
    main()
