"""
Lightweight story graph — causal links between arcs, NPCs, and factions.

Reads from existing case/storyline/relationship data; does not replace them.
"""

from storage import load

AREAS_FILE = "world/areas.json"
INST_FILE = "world/institutions.json"


def build_story_graph(player, npcs=None, *, areas=None, institutions=None):
    """Return nodes and edges describing active narrative relationships."""
    npcs = npcs or {}
    areas = areas if areas is not None else load(AREAS_FILE, {})
    institutions = institutions or load(INST_FILE, {})

    nodes = []
    edges = []

    case = player.get("active_case") or {}
    if case and not case.get("solved"):
        cid = case.get("id") or "active_case"
        nodes.append({"id": cid, "kind": "case", "label": case.get("title", "Case")})
        victim = case.get("victim_id")
        if victim:
            nodes.append({"id": victim, "kind": "npc", "label": (npcs.get(victim) or {}).get("name", victim)})
            edges.append({"from": cid, "to": victim, "rel": "victim"})
        for sid in (case.get("suspect_ids") or [])[:6]:
            nodes.append({"id": sid, "kind": "npc", "label": (npcs.get(sid) or {}).get("name", sid)})
            edges.append({"from": cid, "to": sid, "rel": "suspect"})

    pipe = player.get("starting_pipeline") or {}
    if pipe.get("area_id"):
        aid = pipe["area_id"]
        arc_id = f"district_{aid.split(':')[-1]}"
        nodes.append({"id": arc_id, "kind": "district_arc", "label": pipe.get("title", "District plot")})
        area = areas.get(aid, {})
        sl = area.get("storyline") or {}
        for nid in (sl.get("key_npc_ids") or pipe.get("key_npc_ids") or [])[:5]:
            nodes.append({"id": nid, "kind": "npc", "label": (npcs.get(nid) or {}).get("name", nid)})
            edges.append({"from": arc_id, "to": nid, "rel": "story_cast"})

    focus = player.get("scene_focus")
    if focus and npcs.get(focus):
        nodes.append({"id": "player", "kind": "player", "label": player.get("name") or "Outsider"})
        nodes.append({"id": focus, "kind": "npc", "label": npcs[focus].get("name", focus)})
        edges.append({"from": "player", "to": focus, "rel": "scene_focus"})

    rels = load("characters/relationships.json", {})
    toward = rels.get("toward_player") or {}
    for nid, rel in list(toward.items())[:8]:
        if rel.get("trust", 0) >= 55 or rel.get("fear", 0) >= 55:
            if not any(n["id"] == nid for n in nodes):
                nodes.append({"id": nid, "kind": "npc", "label": (npcs.get(nid) or {}).get("name", nid)})
            edges.append({
                "from": "player",
                "to": nid,
                "rel": "trust" if rel.get("trust", 0) >= rel.get("fear", 0) else "fear",
            })

    return {"nodes": nodes, "edges": edges}


def story_graph_narrator_block(player, npcs=None, *, areas=None, limit=6):
    graph = build_story_graph(player, npcs, areas=areas)
    if not graph["edges"]:
        return ""
    lines = ["STORY LINKS (who connects to what — do not re-explain from scratch):"]
    seen = set()
    for edge in graph["edges"][:limit]:
        key = (edge.get("from"), edge.get("to"), edge.get("rel"))
        if key in seen:
            continue
        seen.add(key)
        labels = {n["id"]: n.get("label", n["id"]) for n in graph["nodes"]}
        fr = labels.get(edge["from"], edge["from"])
        to = labels.get(edge["to"], edge["to"])
        lines.append(f"- {fr} → {to} ({edge.get('rel', 'linked')})")
    return "\n".join(lines)
