"""
Structured narrator fact emission — simulation reads tags, not scraped prose.

Tags (stripped before player sees prose):
  [FACT: speaking | npc_id]
  [FACT: death | npc_id]
  [FACT: place | place_name]
  [SCHEDULE: ...]  (handled in scheduled_events.py)
"""

import re

from simulation.scheduled_events import parse_schedule_tags, strip_schedule_tags

_FACT_SPEAKING = re.compile(
    r"\[FACT:\s*speaking\s*\|\s*(?P<id>[\w-]+)\s*\]", re.I,
)
_FACT_DEATH = re.compile(
    r"\[FACT:\s*death\s*\|\s*(?P<id>[\w-]+)\s*\]", re.I,
)
_FACT_PLACE = re.compile(
    r"\[FACT:\s*place\s*\|\s*(?P<name>[^\]|]+?)\s*\]", re.I,
)
_ALL_FACT_TAGS = (_FACT_SPEAKING, _FACT_DEATH, _FACT_PLACE)


def parse_narrator_facts(text):
    """Extract structured fact declarations from narrator output."""
    if not text:
        return {"speaking": [], "death": [], "places": [], "schedules": []}
    speaking = []
    death = []
    places = []
    seen_s, seen_d, seen_p = set(), set(), set()
    for m in _FACT_SPEAKING.finditer(text):
        nid = m.group("id").strip()
        if nid not in seen_s:
            seen_s.add(nid)
            speaking.append(nid)
    for m in _FACT_DEATH.finditer(text):
        nid = m.group("id").strip()
        if nid not in seen_d:
            seen_d.add(nid)
            death.append(nid)
    for m in _FACT_PLACE.finditer(text):
        name = (m.group("name") or "").strip()
        if name and name.lower() not in seen_p:
            seen_p.add(name.lower())
            places.append(name)
    schedules = parse_schedule_tags(text)
    return {
        "speaking": speaking,
        "death": death,
        "places": places,
        "schedules": schedules,
    }


def strip_narrator_facts(text):
    """Remove all simulation tags from prose shown to the player."""
    if not text:
        return text
    cleaned = text
    for pat in _ALL_FACT_TAGS:
        cleaned = pat.sub("", cleaned)
    cleaned = strip_schedule_tags(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def build_fact_emission_block(scene_state=None):
    """Tell narrator which structured facts to declare."""
    lines = [
        "STRUCTURED FACTS (simulation tags — stripped from player prose; declare alongside story):",
        "- Who speaks with named dialogue: [FACT: speaking | npc_id] per speaker in cast",
        "- If prose implies an NPC died who is alive in SCENE FACTS: [FACT: death | npc_id]",
        "- If naming a specific go-to place (move target OR place named in NPC dialogue): "
        "[FACT: place | place_name]",
        "- Timed promises: [SCHEDULE: event_id | label | +Nh] (required for WHEN commitments)",
        "Use real cast ids from SCENE FACTS only — never invent ids in tags.",
    ]
    if scene_state and scene_state.cast:
        ids = ", ".join(n["id"] for n in scene_state.cast[:6])
        lines.append(f"Valid cast ids for tags: {ids}")
    return "\n".join(lines)


def validate_narrator_facts(facts, player, npcs, scene_state, action_ctx, focal_id):
    """
    Check declared facts against authoritative state.
    Returns human-readable violation strings for regeneration gate.
    """
    issues = []
    if not facts:
        return issues
    cast_ids = scene_state.cast_ids if scene_state else frozenset()
    ctx = action_ctx or {}

    for nid in facts.get("speaking") or []:
        if nid in set(ctx.get("left_behind_cast") or []):
            issues.append(
                f"FACT tag declares left-behind npc {nid!r} as speaking in relocated scene"
            )
        if cast_ids and nid not in cast_ids:
            issues.append(
                f"FACT tag declares speaking npc {nid!r} not in scene cast"
            )
        npc = (npcs or {}).get(nid, {})
        if npc.get("status") == "dead":
            issues.append(f"FACT tag declares dead npc {nid!r} as speaking")

    for nid in facts.get("death") or []:
        npc = (npcs or {}).get(nid, {})
        if not npc:
            issues.append(f"FACT death tag references unknown npc {nid!r}")
            continue
        if npc.get("status") == "alive":
            combat_ok = (
                ctx.get("kind") == "attack"
                and (ctx.get("combat_fatal") or player.get("last_combat_fatal"))
                and (ctx.get("target_id") == nid or focal_id == nid)
            )
            if not combat_ok:
                issues.append(
                    f"FACT death tag for living npc {npc.get('name') or nid!r} "
                    f"without combat authorization"
                )

    focal = focal_id or ctx.get("target_id")
    if focal and facts.get("speaking"):
        if len(facts["speaking"]) > 1:
            issues.append("multiple FACT speaking tags — one focal speaker per beat")
        elif facts["speaking"][0] != focal and ctx.get("kind") in (
            "talk", "ask_about", "ask_name", "personal_talk", "threaten", "help",
        ):
            issues.append(
                f"FACT speaking tag {facts['speaking'][0]!r} "
                f"does not match focal npc {focal!r}"
            )

    return issues


def dialogue_place_fact_gap(text, facts):
    """Flag when prose names navigable places but no [FACT: place] tags were emitted."""
    from simulation.local_places import extract_narrator_destinations

    extracted = extract_narrator_destinations(text)
    if not extracted:
        return None
    tagged = {(p or "").lower() for p in (facts or {}).get("places") or []}
    untagged = []
    for rec in extracted:
        label = (rec.get("label") or "").strip()
        key = label.lower()
        if not label:
            continue
        if key in tagged:
            continue
        if any(key in t or t in key for t in tagged):
            continue
        untagged.append(label)
    if not untagged:
        return None
    names = ", ".join(untagged[:3])
    return (
        f"prose names place(s) ({names}) "
        "but no [FACT: place | place_name] tag emitted"
    )


def build_fact_correction_block(issues):
    if not issues:
        return ""
    lines = [
        "FACT TAG CORRECTIONS (prior draft declared invalid structured facts — rewrite):",
    ]
    for issue in issues[:6]:
        lines.append(f"- {issue}")
    lines.append(
        "- Emit corrected [FACT: …] tags matching SCENE FACTS, or omit tags and obey constraints."
    )
    return "\n".join(lines)
