"""
Output-interpretation guard — prose asserting state the simulation did not author.

Closes the gap between narrator prose and authoritative sim state:
acquisition, gifts, time passage, invented entities, off-screen facts.
"""

from __future__ import annotations

import re

# Prose implies receiving an item
_PHANTOM_RECEIVE = re.compile(
    r"\b(?:"
    r"(?:he|she|they)\s+(?:hands?|gives?|passes?|slips?|offers?)\s+(?:you|him|her)\s+(?:a|the|some)\s+\w+"
    r"|you\s+(?:take|receive|accept|pocket|pick\s+up)\s+(?:a|the)\s+\w+"
    r"|(?:key|coin|letter|blade|dagger|pouch|map|scroll|ring|amulet)\s+(?:lands?|rests?)\s+in\s+your\s+(?:hand|palm|pocket)"
    r")\b",
    re.I,
)

# Protagonist gives away something not authorized
_PHANTOM_GIVE = re.compile(
    r"\b(?:you\s+(?:hand|give|offer|pay|slip)\s+(?:him|her|them|the\s+\w+)\s+(?:a|the|some|\d+))"
    r"|(?:coins?|silver|gold)\s+(?:change\s+hands|pass(?:es)?\s+(?:to|from))\b",
    re.I,
)

_TIME_SKIP = re.compile(
    r"\b(?:"
    r"hours?\s+later|much\s+later|a\s+while\s+later|time\s+passes|time\s+passed"
    r"|by\s+(?:morning|evening|nightfall|dawn|noon|midnight)"
    r"|the\s+next\s+(?:day|morning|evening)"
    r"|(?:sun|daylight|darkness)\s+(?:rises|falls|deepens)"
    r"|eventually,?\s+(?:after|hours|the\s+day)"
    r")\b",
    re.I,
)

_OFFSCREEN_FACT = re.compile(
    r"\b(?:"
    r"(?:already|have\s+already|has\s+already)\s+(?:sealed|locked|left|gone|fled|closed|barred)"
    r"|(?:the\s+)?(?:gate|door|path|road)\s+(?:is|are|was|were)\s+(?:sealed|locked|barred|closed)"
    r"|(?:guards?|soldiers?)\s+have\s+(?:already|since)\s+"
    r")\b",
    re.I,
)

# "the merchant Tomas", "a blacksmith named Doran", "Doran the smith"
_INVENTED_NPC = re.compile(
    r"\b(?:"
    r"(?:the|a|an)\s+(?:[\w-]+\s+){0,2}?(?:man|woman|merchant|blacksmith|priest|guard|stranger|smith|sailor|scholar)"
    r"\s+(?:named|called)\s+([A-Z][a-z]{2,18})"
    r"|([A-Z][a-z]{2,18})\s+(?:the|said|stepped|turned|muttered|replied|asked|nodded)"
    r")\b",
)

_COMMON_WORD_NAMES = frozenset({
    "The", "You", "Your", "They", "Their", "She", "Her", "His", "He", "It",
    "Gate", "Door", "Market", "Temple", "City", "Street", "Night", "Morning",
    "Leave", "Wait", "Yes", "No", "What", "When", "Where", "Why", "How",
})

_NIGHT_ATMOSPHERE = re.compile(
    r"\b(?:deep night|midnight|starless|moonless|predawn hush|dead of night)\b"
    r"|\b(?:pitch dark|black sky|no sun|before dawn)\b",
    re.I,
)
_DAY_ATMOSPHERE = re.compile(
    r"\b(?:bright (?:sun|daylight|morning)|high noon|midday sun|"
    r"afternoon glare|sun(?:'s| is) (?:high|up)|golden morning)\b",
    re.I,
)
_DAWN_ATMOSPHERE = re.compile(
    r"\b(?:first light|sunrise|rosy dawn|grey dawn|pale dawn)\b",
    re.I,
)
_EVENING_ATMOSPHERE = re.compile(
    r"\b(?:sunset|dusk|twilight|gloaming|evening glow)\b",
    re.I,
)

_PHANTOM_INJURY = re.compile(
    r"\b(?:(?:you(?:'re| are)|your)\s+(?:bleeding|bloodied|wounded|injured|hurt))"
    r"|(?:blood\s+(?:runs|streams|trickles)\s+(?:from|down)\s+your)"
    r"|(?:you\s+(?:notice|feel)\s+(?:you(?:'re| are)\s+)?(?:bleeding|hurt|injured))"
    r"\b",
    re.I,
)

_DRAW_WEAPON = re.compile(
    r"\b(?:you\s+(?:draw|unsheathe|pull|wield)\s+(?:your\s+)?(?:sword|blade|dagger|knife|axe))\b",
    re.I,
)

_DOOR_OPEN = re.compile(
    r"\b(?:the\s+)?(?:door|gate|portal)\s+(?:is|swings?|stands?\s+)?(?:now\s+)?(?:open|unlocked|ajar)\b"
    r"|\b(?:you\s+(?:open|unlock|push open)\s+(?:the\s+)?(?:door|gate))\b",
    re.I,
)


def _cast_names(present_npcs, npcs, known_ids=None):
    names = set()
    known_ids = known_ids or set()
    for n in present_npcs or []:
        name = (n.get("name") or "").strip()
        if name:
            names.add(name.lower())
            names.add(name.split()[0].lower())
    for nid, npc in (npcs or {}).items():
        if nid in known_ids or any(n.get("id") == nid for n in (present_npcs or [])):
            name = (npc.get("name") or "").strip()
            if name:
                names.add(name.lower())
                names.add(name.split()[0].lower())
    return names


def _sim_authorized_item_change(action_ctx):
    if not action_ctx:
        return False
    if action_ctx.get("acquired_item"):
        return True
    if action_ctx.get("give_refused") is False and action_ctx.get("give_amount"):
        return True
    kind = action_ctx.get("kind")
    if kind in ("give", "trade", "search") and not action_ctx.get("trade_refused"):
        if action_ctx.get("give_amount") or action_ctx.get("acquired_item"):
            return True
    return False


def _sim_authorized_time_pass(action_ctx, facts):
    if not action_ctx:
        return False
    if action_ctx.get("wait_hours"):
        return True
    if action_ctx.get("wait_event"):
        return True
    if action_ctx.get("travel_arrival"):
        return True
    if (facts or {}).get("schedules"):
        return True
    if action_ctx.get("kind") in ("wait", "travel", "rest"):
        return True
    return False


def _time_of_day_from_context(action_ctx, scene_state, world):
    if scene_state:
        return scene_state.time_of_day, scene_state.hour
    if world:
        from simulation.world_integrity import expected_time_of_day
        return expected_time_of_day(world), world.get("hour", 0)
    return (action_ctx or {}).get("time_of_day"), (action_ctx or {}).get("hour")


def _atmosphere_conflicts_time(text, time_of_day):
    """Return issue fragment when prose atmosphere contradicts clock time_of_day."""
    if not text or not time_of_day:
        return None
    tod = time_of_day.lower()
    if tod in ("deep night", "night"):
        if _DAY_ATMOSPHERE.search(text) or _DAWN_ATMOSPHERE.search(text):
            return f"prose describes daylight/dawn but clock is {time_of_day!r}"
        if re.search(r"\b(?:noon|midday|morning sun|afternoon heat)\b", text, re.I):
            return f"prose describes daytime heat/light but clock is {time_of_day!r}"
    elif tod in ("morning", "afternoon", "noon"):
        if _NIGHT_ATMOSPHERE.search(text):
            return f"prose describes deep night but clock is {time_of_day!r}"
    elif tod == "dawn":
        if _NIGHT_ATMOSPHERE.search(text) and not _DAWN_ATMOSPHERE.search(text):
            return f"prose describes deep night but clock is dawn"
    elif tod in ("evening",):
        if _DAY_ATMOSPHERE.search(text) and not _EVENING_ATMOSPHERE.search(text):
            return f"prose describes bright daytime but clock is evening"
    return None


def _player_has_weapon(player):
    eq = (player or {}).get("equipment") or {}
    if eq.get("weapon"):
        return True
    inv = (player or {}).get("inventory") or []
    for item in inv:
        name = (item.get("name") or item if isinstance(item, str) else "").lower()
        if any(w in name for w in ("sword", "blade", "dagger", "knife", "axe")):
            return True
    return False


def _sim_authorized_injury(action_ctx, player):
    if not action_ctx:
        return bool((player or {}).get("injuries"))
    if action_ctx.get("combat_snapshot") or action_ctx.get("kind") == "attack":
        return True
    injuries = (player or {}).get("injuries") or []
    return bool(injuries)


def validate_prose_assertions(
    text,
    *,
    player,
    npcs,
    action_ctx,
    focal_npc_id,
    present_npcs,
    known_ids=None,
    facts=None,
    scene_state=None,
    world=None,
):
    """
    Return list of issue strings for unauthorized prose-asserted state changes.
    """
    if not text or len(text) < 20:
        return []

    issues = []
    ctx = action_ctx or {}
    kind = ctx.get("kind", "general")
    facts = facts or {}
    cast_names = _cast_names(present_npcs, npcs, known_ids)

    if _PHANTOM_RECEIVE.search(text) and not _sim_authorized_item_change(ctx):
        if kind not in ("give", "trade", "search") or ctx.get("search_refused"):
            issues.append(
                "prose asserts receiving an item but simulation did not grant acquisition"
            )

    if _PHANTOM_GIVE.search(text) and kind == "give" and ctx.get("give_refused"):
        issues.append("prose describes giving/paying but GIVE was refused by simulation")

    if _PHANTOM_GIVE.search(text) and kind not in ("give", "trade") and not ctx.get("give_amount"):
        if not re.search(r"\b(?:would|could|might|try to|attempt)\b", text, re.I):
            issues.append(
                "prose asserts giving/payment but action was not a give/trade beat"
            )

    if _TIME_SKIP.search(text) and not _sim_authorized_time_pass(ctx, facts):
        issues.append(
            "prose advances time (hours later / by morning) without wait, travel, or [SCHEDULE] tag"
        )

    tod, _hour = _time_of_day_from_context(ctx, scene_state, world)
    atm = _atmosphere_conflicts_time(text, tod)
    if atm:
        issues.append(atm)

    if _PHANTOM_INJURY.search(text) and not _sim_authorized_injury(ctx, player):
        if not (player or {}).get("injuries"):
            issues.append(
                "prose asserts protagonist injury/bleeding but simulation did not authorize it"
            )

    if _DRAW_WEAPON.search(text) and not _player_has_weapon(player):
        if not ctx.get("acquired_item"):
            issues.append(
                "prose describes drawing a weapon but protagonist has none equipped or carried"
            )

    if _DOOR_OPEN.search(text) and kind not in ("travel", "approach", "explore", "search"):
        if not ctx.get("relocated") and not ctx.get("travel_arrival"):
            issues.append(
                "prose asserts door/gate opened without travel, approach, or relocation beat"
            )

    if _OFFSCREEN_FACT.search(text) and kind not in ("wait", "travel", "investigate", "observe"):
        if not ctx.get("events_fired"):
            issues.append(
                "prose asserts off-screen world change (already sealed/gone) sim did not author"
            )

    for m in _INVENTED_NPC.finditer(text):
        for g in m.groups():
            if not g or g in _COMMON_WORD_NAMES:
                continue
            if g.lower() not in cast_names:
                if g.lower() not in {"i", "we"}:
                    issues.append(
                        f"prose introduces named character {g!r} not in present cast"
                    )
                    break

    # Cross-check interpretation: object target beat should not have focal NPC dialogue
    if ctx.get("object_ref") and focal_npc_id and re.search(r'"[^"]{6,}"', text):
        if ctx.get("self_target") or ctx.get("group_address"):
            pass
        elif kind in ("examine", "search", "investigate", "observe"):
            issues.append(
                "object-focused beat but prose contains extended NPC dialogue"
            )

    # Speaking tag vs focal mismatch already in narrator_facts; add unattributed long dialogue
    if kind in ("talk", "ask_about", "personal_talk") and focal_npc_id:
        speaking = facts.get("speaking") or []
        if re.search(r'"[^"]{10,}"', text) and not speaking:
            if not ctx.get("interpretation_clarify") and not ctx.get("target_ambiguous"):
                issues.append(
                    "dialogue beat with quoted speech but no [FACT: speaking | npc_id] tag"
                )

    return issues


_ASSERTION_BLOCK_PATTERNS = (
    "acquisition",
    "grant acquisition",
    "introduces named character",
    "not in present cast",
    "advances time",
    "off-screen world change",
    "asserts giving/payment",
    "injury/bleeding",
    "drawing a weapon",
    "door/gate opened",
    "daylight/dawn but clock",
    "deep night but clock",
    "daytime heat/light but clock",
)


def issues_block_narrator_registration(issues) -> bool:
    """
    True when prose still asserts unauthorized state — do not register phantom
    narrator items/places from that text.
    """
    if not issues:
        return False
    for issue in issues:
        low = (issue or "").lower()
        if any(p in low for p in _ASSERTION_BLOCK_PATTERNS):
            return True
    return False
