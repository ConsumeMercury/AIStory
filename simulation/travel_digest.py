"""
What changed in the world while the player was on the road.
"""

from storage import load

EVENT_FILE = "events/event_log.json"
RUMOR_FILE = "rumors/rumors.json"
INST_FILE = "world/institutions.json"
NPC_FILE = "characters/npcs.json"


def snapshot_before_travel():
    events = load(EVENT_FILE, [])
    return {
        "event_ids": {e.get("id") for e in events if e.get("id")},
        "rumor_texts": {r.get("text") for r in load(RUMOR_FILE, []) if r.get("text")},
        "arc_stages": {
            i.get("id"): (i.get("arc") or {}).get("stage")
            for i in load(INST_FILE, {}).values()
        },
        "dead_npcs": {
            nid for nid, n in load(NPC_FILE, {}).items()
            if n.get("status") != "alive"
        },
    }


def build_arrival_digest(before, destination_area_id=None):
    """Prose directive for the narrator — not a bullet list in output."""
    if not before:
        return ""

    events = load(EVENT_FILE, [])
    new_events = [e for e in events if e.get("id") and e.get("id") not in before["event_ids"]]
    rumors = load(RUMOR_FILE, [])
    new_rumors = [
        r for r in rumors
        if r.get("text") and r.get("text") not in before["rumor_texts"]
    ]

    beats = []
    for e in new_events[-8:]:
        etype = e.get("type", "")
        action = e.get("action", "")
        if etype in ("combat", "death", "institution_event") or action in ("fight", "hide", "plan"):
            actor = e.get("actor", "someone")
            beats.append(f"{actor} {action or etype}")

    institutions = load(INST_FILE, {})
    for inst in institutions.values():
        iid = inst.get("id")
        old_stage = before["arc_stages"].get(iid)
        new_stage = (inst.get("arc") or {}).get("stage")
        if old_stage is not None and new_stage != old_stage:
            name = inst.get("name", "somewhere")
            current = (inst.get("arc") or {}).get("current", "")
            beats.append(f"at {name}: {current[:80]}")

    npcs = load(NPC_FILE, {})
    for nid, n in npcs.items():
        if nid not in before["dead_npcs"] and n.get("status") != "alive":
            beats.append(f"{n.get('name', 'someone')} is gone")

    if new_rumors:
        beats.append(f"new gossip: {new_rumors[-1].get('text', '')[:90]}")

    if not beats:
        return (
            "TRAVEL DIGEST: Time passed. The world kept turning — "
            "show arrival through small differences (light, faces, mood), not a report."
        )

    summary = "; ".join(beats[:5])
    dest = destination_area_id or "here"
    return (
        f"TRAVEL DIGEST: While you were away from {dest.replace('_', ' ')}, "
        f"the world moved on ({summary}). "
        f"Let arrival feel like re-entering a living place — weave one or two of these "
        f"as sensory detail, not exposition."
    )
