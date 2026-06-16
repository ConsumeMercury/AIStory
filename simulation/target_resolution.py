"""
Unified NPC target resolution — who the player is addressing or acting on.
Simulation picks the focal person; the narrator must not swap them.
"""

import re

ROLE_HINT = re.compile(
    r"\b(priest|cleric|monk|guard|soldier|merchant|sailor|captain|"
    r"blacksmith|scholar|scribe|innkeeper|clerk|clerks|beggar|"
    r"hunter|mercenary|woman|man|girl|boy|lady|fellow)\b",
    re.I,
)

TARGET_KINDS = frozenset({
    "talk", "personal_talk", "ask_name", "help", "give", "threaten",
    "insult", "show_respect", "find", "confess", "attack", "trade",
    "steal", "ask_about", "investigate", "accuse", "blackmail", "guild",
})


def find_npc_by_name_in_text(text, npcs, player):
    """Match a known NPC name mentioned in player text."""
    if not text:
        return None
    lower = text.lower()
    known = player.get("known_npcs", {})
    hits = []
    for nid, npc in npcs.items():
        if npc.get("status") != "alive":
            continue
        name = (npc.get("name") or "").strip()
        if not name or not known.get(nid, {}).get("name_known"):
            continue
        if name.lower() in lower:
            hits.append(npc)
        else:
            first = name.split()[0].lower()
            if len(first) > 2 and re.search(rf"\b{re.escape(first)}\b", lower):
                hits.append(npc)
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        focus = player.get("scene_focus")
        for n in hits:
            if n["id"] == focus:
                return n
        return hits[0]
    return None


def action_mentions_role_or_descriptor(action):
    if not action:
        return False
    if ROLE_HINT.search(action):
        return True
    return bool(re.search(r"\bred[\s-]?hair|\bgrey[\s-]?hair|\bauburn\b", action, re.I))


def resolve_action_target(action, player, present, npcs=None, kind="general"):
    """
    Return the present NPC the player is targeting, or None.
    Absent named NPCs are handled separately in resolve_target_and_absence.
    """
    from simulation.action_resolution import match_npc_by_description, resolve_pronoun_target

    if not present:
        return None

    npcs = npcs or {}
    text = (action or "").lower()

    if npcs:
        named = find_npc_by_name_in_text(action, npcs, player)
        if named:
            for n in present:
                if n["id"] == named["id"]:
                    return n
            return None

    role_match = match_npc_by_description(action, present)
    if role_match:
        return role_match

    pron = resolve_pronoun_target(action, player, present)
    if pron:
        return pron

    if re.search(r"\b(woman|girl|lady|she|her)\b", text):
        females = [n for n in present if n.get("gender") == "female"]
        if len(females) == 1:
            return females[0]
        focus_id = player.get("scene_focus")
        for n in females:
            if n["id"] == focus_id:
                return n
        if females:
            return females[0]

    if re.search(r"\b(man|boy|he|him)\b", text) and not re.search(r"\b(woman|girl|lady|she|her)\b", text):
        males = [n for n in present if n.get("gender") == "male"]
        if len(males) == 1:
            return males[0]
        focus_id = player.get("scene_focus")
        for n in males:
            if n["id"] == focus_id:
                return n
        if males:
            return males[0]

    for n in present:
        build = n.get("physique", {}).get("build", "")
        if build and build.lower() in text:
            return n

    focus_id = player.get("scene_focus")
    has_role_hint = action_mentions_role_or_descriptor(action)
    if focus_id and not has_role_hint:
        for n in present:
            if n["id"] == focus_id:
                return n

    if kind in TARGET_KINDS and len(present) == 1:
        return present[0]

    if not has_role_hint:
        known = player.get("known_npcs", {})
        known_present = [n for n in present if known.get(n["id"], {}).get("name_known")]
        if len(known_present) == 1:
            return known_present[0]

    return None


def resolve_investigate_target(action, player, present):
    """Prefer a role-matching NPC for investigation beats when one is named in text."""
    from simulation.action_resolution import match_npc_by_description

    if not present or not action:
        return None
    if not action_mentions_role_or_descriptor(action):
        return None
    return match_npc_by_description(action, present)
