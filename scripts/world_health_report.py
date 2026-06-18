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
    world = load("world/world_state.json", {})
    relationships = load("characters/relationships.json", {})
    npc_memories = load("characters/npc_memories.json", {})
    memories = load("characters/memories.json", {})

    from simulation.world_clock import ensure_clock_coherent
    from simulation.world_integrity import run_integrity_audit

    world, clock_fixed = ensure_clock_coherent(world, persist=False)
    if clock_fixed:
        warnings.append(
            "world clock was stale (time_of_day/hour drift) — recomputed in-memory for audit"
        )

    audit_issues, audit_warnings = run_integrity_audit(
        player=player,
        npcs=npcs,
        areas=areas,
        institutions=institutions,
        rumors=rumors,
        events=events,
        world=world,
        relationships=relationships,
        npc_memories=npc_memories,
        memories=memories,
    )
    issues.extend(audit_issues)
    warnings.extend(audit_warnings)

    if not player.get("area"):
        warnings.append("player has no area set")

    stats = player.get("stats") or {}
    if player and not stats.get("max_health"):
        warnings.append("player stats missing max_health")

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
