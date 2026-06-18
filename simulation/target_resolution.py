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

# First names that are common English words — require explicit address, not substring luck.
_AMBIGUOUS_FIRST_NAMES = frozenset({
    "hope", "will", "grace", "joy", "faith", "mark", "rose", "art", "pat",
    "bill", "sue", "may", "spring", "summer", "dawn", "charity", "mercy",
    "honor", "glory", "sage", "storm", "rain", "snow", "river", "brook",
})


def _ambiguous_name_is_addressed(name_l, text_lower):
    """True when an ambiguous given name is clearly used as an addressee, not a common word."""
    return bool(re.search(
        rf"\b(?:talk|speak|ask|find|greet|tell|approach|nod|turn|wave|call|look)\b[^.]*\b{re.escape(name_l)}\b"
        rf"|\bto\s+{re.escape(name_l)}\b"
        rf"|\bat\s+{re.escape(name_l)}\b"
        rf"|\b{re.escape(name_l)}\s*[,!?]",
        text_lower,
    ))


def _role_tokens_in_text(action, present):
    """True if action mentions a role token from someone actually present."""
    if not action or not present:
        return False
    text = action.lower()
    for npc in present:
        role = (npc.get("role") or "").replace("_", " ")
        for token in role.split():
            if len(token) >= 4 and re.search(rf"\b{re.escape(token)}\b", text):
                return True
        occ = (npc.get("occupation") or "").replace("_", " ")
        for token in occ.split():
            if len(token) >= 4 and token != role and re.search(rf"\b{re.escape(token)}\b", text):
                return True
    return False


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
        name_l = name.lower()
        parts = name.split()
        if len(parts) == 1 and name_l in _AMBIGUOUS_FIRST_NAMES:
            if not _ambiguous_name_is_addressed(name_l, lower):
                continue
        if re.search(rf"\b{re.escape(name_l)}\b", lower):
            hits.append(npc)
            continue
        first = parts[0].lower()
        if first in _AMBIGUOUS_FIRST_NAMES:
            if not _ambiguous_name_is_addressed(first, lower):
                continue
        if len(first) > 2 and re.search(rf"\b{re.escape(first)}\b", lower):
            hits.append(npc)
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        focus = player.get("scene_focus")
        for n in hits:
            if n["id"] == focus:
                return n
        return None
    return None


def npc_matches_action_role_hint(action, npc):
    """True when this NPC fits a role/descriptor mentioned in the action."""
    if not action or not npc:
        return False
    from simulation.action_resolution import match_npc_by_description

    alone = match_npc_by_description(action, [npc])
    if alone and alone["id"] == npc.get("id"):
        return True
    text = action.lower()
    role = (npc.get("role") or "").replace("_", " ")
    for token in role.split():
        if len(token) >= 4 and re.search(rf"\b{re.escape(token)}\b", text):
            return True
    occ = (npc.get("occupation") or "").replace("_", " ")
    for token in occ.split():
        if len(token) >= 4 and token != role and re.search(rf"\b{re.escape(token)}\b", text):
            return True
    return False


def _focus_matching_role_hint(action, player, present):
    """Keep scene_focus when that NPC satisfies the role hint — don't swap strangers."""
    if not action_mentions_role_or_descriptor(action, present=present):
        return None
    focus_id = player.get("scene_focus")
    if not focus_id:
        return None
    for npc in present:
        if npc.get("id") == focus_id and npc_matches_action_role_hint(action, npc):
            return npc
    return None


def action_mentions_role_or_descriptor(action, present=None):
    if not action:
        return False
    if ROLE_HINT.search(action):
        return True
    if present and _role_tokens_in_text(action, present):
        return True
    return bool(re.search(r"\bred[\s-]?hair|\bgrey[\s-]?hair|\bauburn\b", action, re.I))


def _role_matching_npcs(action, present):
    """All present NPCs whose role fits a hint in the action text."""
    if not action or not present:
        return []
    return [n for n in present if npc_matches_action_role_hint(action, n)]


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
    has_role_hint = action_mentions_role_or_descriptor(action, present=present)

    if npcs:
        named = find_npc_by_name_in_text(action, npcs, player)
        if named:
            for n in present:
                if n["id"] == named["id"]:
                    return n
            return None

    sticky = _focus_matching_role_hint(action, player, present)
    if sticky:
        return sticky

    role_matches = _role_matching_npcs(action, present)
    if len(role_matches) == 1:
        return role_matches[0]
    if len(role_matches) > 1:
        focus_id = player.get("scene_focus")
        for n in role_matches:
            if n["id"] == focus_id:
                return n
        journal = player.get("journal") or []
        if journal:
            last_focus = journal[-1].get("focus_npc")
            for n in role_matches:
                if n["id"] == last_focus:
                    return n
        return None

    role_match = match_npc_by_description(action, present, player=player)
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
        if len(females) > 1:
            return None

    if re.search(r"\b(man|boy|he|him)\b", text) and not re.search(r"\b(woman|girl|lady|she|her)\b", text):
        males = [n for n in present if n.get("gender") == "male"]
        if len(males) == 1:
            return males[0]
        focus_id = player.get("scene_focus")
        for n in males:
            if n["id"] == focus_id:
                return n
        if len(males) > 1:
            return None

    for n in present:
        build = n.get("physique", {}).get("build", "")
        if build and build.lower() in text:
            return n

    focus_id = player.get("scene_focus")
    if focus_id and not has_role_hint:
        for n in present:
            if n["id"] == focus_id:
                return n

    if kind in TARGET_KINDS and len(present) == 1 and not has_role_hint:
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
    if not action_mentions_role_or_descriptor(action, present=present):
        return None
    return match_npc_by_description(action, present)
