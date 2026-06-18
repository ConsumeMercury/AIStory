"""
Structured narrator fact emission — simulation reads tags, not scraped prose.

Tags (stripped before player sees prose):
  [FACT: speaking | npc_id]
  [FACT: death | npc_id]
  [FACT: place | place_name]
  [FACT: item | item_label]
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
_FACT_ITEM = re.compile(
    r"\[FACT:\s*item\s*\|\s*(?P<label>[^\]|]+?)\s*\]", re.I,
)
_ALL_FACT_TAGS = (_FACT_SPEAKING, _FACT_DEATH, _FACT_PLACE, _FACT_ITEM)


def parse_narrator_facts(text):
    """Extract structured fact declarations from narrator output."""
    if not text:
        return {"speaking": [], "death": [], "places": [], "items": [], "schedules": []}
    speaking = []
    death = []
    places = []
    items = []
    seen_s, seen_d, seen_p, seen_i = set(), set(), set(), set()
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
    for m in _FACT_ITEM.finditer(text):
        label = (m.group("label") or "").strip()
        if label and label.lower() not in seen_i:
            seen_i.add(label.lower())
            items.append(label)
    schedules = parse_schedule_tags(text)
    return {
        "speaking": speaking,
        "death": death,
        "places": places,
        "items": items,
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
    cleaned = re.sub(r"\[(?:FACT|SCHEDULE):[^\]]*$", "", cleaned, flags=re.I | re.M)
    cleaned = re.sub(r"\[(?:FACT|SCHEDULE):[^\]]*\]", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def build_fact_emission_block(scene_state=None, action_ctx=None):
    """Tell narrator which structured facts to declare."""
    lines = [
        "STRUCTURED FACTS (simulation tags — stripped from player prose; declare alongside story):",
        "- Who speaks with named dialogue: [FACT: speaking | npc_id] per speaker in cast",
        "- If prose implies an NPC died who is alive in SCENE FACTS: [FACT: death | npc_id]",
        "- If an NPC names a specific go-to place in quoted dialogue: "
        "[FACT: place | place_name]",
        "- Timed promises: [SCHEDULE: event_id | label | +Nh] (required for WHEN commitments)",
        "- If protagonist acquires an item this beat (search/give/trade authorized): "
        "[FACT: item | item_label]",
        "Use real cast ids from SCENE FACTS only — never invent ids in tags.",
        "Every dialogue beat with quoted speech MUST include [FACT: speaking | focal_npc_id].",
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
        from simulation.boundary_metrics import _DIALOGUE_KINDS

        if len(facts["speaking"]) > 1:
            issues.append("multiple FACT speaking tags — one focal speaker per beat")
        elif facts["speaking"][0] != focal and ctx.get("kind") in _DIALOGUE_KINDS:
            issues.append(
                f"FACT speaking tag {facts['speaking'][0]!r} "
                f"does not match focal npc {focal!r}"
            )

    if facts.get("items") and ctx.get("inventory_missing"):
        issues.append(
            "FACT item tag emitted but action referenced items protagonist lacks"
        )
    if facts.get("items") and not _sim_item_change_ok(ctx):
        for label in facts["items"]:
            issues.append(
                f"FACT item tag {label!r} without authorized acquisition this beat"
            )

    return issues


def _sim_item_change_ok(ctx):
    if not ctx:
        return False
    if ctx.get("acquired_item"):
        return True
    if ctx.get("give_amount") and ctx.get("kind") in ("give", "trade"):
        return True
    if ctx.get("kind") in ("search", "trade") and not ctx.get("search_refused"):
        return True
    return False


_DIALOGUE_AT_PLACE = re.compile(
    r"\b(?:meet(?:\s+me)?|go|find|wait|head|walk|come|sent|send(?:\s+\w+){0,3})\b"
    r"(?:\s+\w+){0,5}\s+(?:at|in|to|by|behind|inside|down|into|near)\s+"
    r"(?:the\s+)?(?P<place>[\w\s'-]{3,40}?)"
    r"(?:\s+before|\s+when|\s+after|\s+if\b|[.,\"']|$)",
    re.I,
)
_DIALOGUE_NAMED_PLACE = re.compile(
    r"\b(?P<place>(?:the\s+)?(?:"
    r"customs\s+house|back\s+room|cellars?|market(?:\s+square)?|"
    r"gate(?:house)?|warehouse|sanctuary|chapel|temple|"
    r"records?\s+office|clerk'?s?\s+office|"
    r"inn|tavern|wharf|harbor|harbour|dock(?:s)?|"
    r"[\w'-]+\s+(?:house|hall|yard|room|office|cellar|gate|court|tower|"
    r"bridge|quarter|district|wharf|market|dock|cellars?)"
    r"))\b",
    re.I,
)
_PLACE_REJECT = re.compile(
    r"\b(?:your|my|his|her|their|our|you|boots|collar|sleeve|grit|pavers|"
    r"shoulder|hand|finger|voice|name|question|look|breadth|chest|wall from|"
    r"stop a yard|wet grit)\b",
    re.I,
)
_LOCATION_WORDS = frozenset({
    "cellar", "cellars", "house", "hall", "room", "office", "gate", "market",
    "wharf", "dock", "docks", "temple", "chapel", "inn", "tavern", "warehouse",
    "quarter", "district", "yard", "bridge", "tower", "customs", "sanctuary",
    "harbor", "harbour", "alley", "lane", "gatehouse", "cistern", "barracks",
})


def _normalize_place_label(raw):
    label = (raw or "").strip(" .,\"'")
    label = re.sub(r"^(?:the|a|an)\s+", "", label, flags=re.I).strip()
    return label


def _valid_dialogue_place(name):
    name = _normalize_place_label(name)
    if len(name) < 4 or len(name) > 48:
        return False
    if _PLACE_REJECT.search(name):
        return False
    tokens = {t for t in re.split(r"[\W_]+", name.lower()) if t}
    if not tokens & _LOCATION_WORDS:
        return False
    if re.search(r"\b(?:you|your|stop|yard from)\b", name, re.I):
        return False
    return True


def extract_dialogue_place_names(text):
    """Conservative: navigable place names explicitly spoken in quoted dialogue."""
    if not text:
        return []
    found = []
    seen = set()
    for quote in re.findall(r'"([^"]{6,})"', text):
        for pat in (_DIALOGUE_AT_PLACE, _DIALOGUE_NAMED_PLACE):
            for m in pat.finditer(quote):
                place = _normalize_place_label(m.group("place"))
                key = place.lower()
                if not _valid_dialogue_place(place) or key in seen:
                    continue
                seen.add(key)
                found.append(place)
    return found


def _place_tag_covers(label, tagged):
    """True when a declared [FACT: place] tag already covers this name."""
    key = _normalize_place_label(label).lower()
    if not key:
        return True
    for tag in tagged:
        t = _normalize_place_label(tag).lower()
        if not t:
            continue
        if key == t or key in t or t in key:
            return True
        key_tokens = {w for w in re.split(r"[\W_]+", key) if len(w) > 3}
        tag_tokens = {w for w in re.split(r"[\W_]+", t) if len(w) > 3}
        if key_tokens & tag_tokens & _LOCATION_WORDS:
            return True
    return False


def dialogue_place_fact_gap(text, facts):
    """Flag when quoted dialogue names a go-to place but no [FACT: place] tag covers it."""
    spoken_places = extract_dialogue_place_names(text)
    if not spoken_places:
        return None
    tagged = (facts or {}).get("places") or []
    untagged = [p for p in spoken_places if not _place_tag_covers(p, tagged)]
    if not untagged:
        return None
    names = ", ".join(untagged[:3])
    return (
        f"dialogue names place(s) ({names}) "
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
    lines.append(
        "- On dialogue beats, include [FACT: speaking | focal_npc_id] AND any [SCHEDULE: …] "
        "tags in the same draft — regen must not drop structured tags."
    )
    return "\n".join(lines)
