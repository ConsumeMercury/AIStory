"""
World inspector — read-only summary for debug UI and /api/debug/world.
"""

from storage import load


def build_world_inspector():
    player = load("player/player.json", {})
    world = load("world/world_state.json", {})
    npcs = load("characters/npcs.json", {})
    areas = load("world/areas.json", {})
    institutions = load("world/institutions.json", {})
    rumors = load("rumors/rumors.json", [])
    events = load("events/event_log.json", [])

    area_id = player.get("area")
    area = areas.get(area_id, {})
    sl = area.get("storyline") or {}

    inst_summaries = []
    for inst in institutions.values():
        arc = inst.get("arc") or {}
        inst_summaries.append({
            "id": inst.get("id"),
            "name": inst.get("name"),
            "type": inst.get("type"),
            "city": inst.get("city"),
            "area": inst.get("area"),
            "arc_title": arc.get("title"),
            "current": arc.get("current"),
            "tension": arc.get("tension"),
            "stage": arc.get("stage"),
        })

    district_plots = []
    for aid, a in areas.items():
        if a.get("type") != "district":
            continue
        plot = a.get("storyline") or {}
        if not plot:
            continue
        district_plots.append({
            "area_id": aid,
            "name": a.get("name"),
            "title": plot.get("title"),
            "theme": plot.get("theme"),
            "current": plot.get("current"),
            "tension": plot.get("tension"),
        })

    alive = sum(1 for n in npcs.values() if n.get("status") == "alive")
    key_npcs = [
        {"id": nid, "name": n.get("name"), "area": n.get("area"), "role": n.get("role")}
        for nid, n in npcs.items()
        if n.get("key_npc")
    ][:12]

    from simulation.story_entropy import score_story_entropy
    from scripts.world_health_report import run_world_health_report

    report = run_world_health_report()
    return {
        "time": {"day": world.get("day"), "hour": world.get("hour"), "weather": world.get("weather")},
        "player": {
            "name": player.get("name"),
            "area": area_id,
            "location": player.get("location"),
            "level": player.get("level"),
        },
        "active_plot": {
            "title": sl.get("title"),
            "hook": sl.get("hook"),
            "theme": sl.get("theme"),
            "current": sl.get("current"),
            "source": sl.get("source"),
        },
        "starting_pipeline": player.get("starting_pipeline"),
        "active_case": player.get("active_case"),
        "counts": {
            "npcs_alive": alive,
            "districts": sum(1 for a in areas.values() if a.get("type") == "district"),
            "institutions": len(institutions),
            "rumors": len(rumors) if isinstance(rumors, list) else 0,
            "events": len(events) if isinstance(events, list) else 0,
            "journal": len(player.get("journal") or []),
        },
        "institutions": inst_summaries[:8],
        "district_plots": district_plots[:12],
        "key_npcs": key_npcs,
        "recent_rumors": (rumors[-5:] if isinstance(rumors, list) else []),
        "story_entropy": score_story_entropy(player, npcs, areas=areas),
        "health_score": report.get("score"),
        "health_warnings": report.get("warnings", [])[:5],
    }
