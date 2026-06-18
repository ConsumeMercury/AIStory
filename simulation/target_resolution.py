"""
Unified NPC target resolution — who the player is addressing or acting on.

Backward-compatible facade over simulation.target_constraints (filter-then-decide).
"""

import re

from simulation.target_constraints import (
    ResolvedTarget,
    TargetStatus,
    extract_constraints,
    npc_satisfies_constraints,
    resolve_target,
)

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

_AMBIGUOUS_FIRST_NAMES = frozenset({
    "hope", "will", "grace", "joy", "faith", "mark", "rose", "art", "pat",
    "bill", "sue", "may", "spring", "summer", "dawn", "charity", "mercy",
    "honor", "glory", "sage", "storm", "rain", "snow", "river", "brook",
})


def _ambiguous_name_is_addressed(name_l, text_lower):
    return bool(re.search(
        rf"\b(?:talk|speak|ask|find|greet|tell|approach|nod|turn|wave|call|look)\b[^.]*\b{re.escape(name_l)}\b"
        rf"|\bto\s+{re.escape(name_l)}\b"
        rf"|\bat\s+{re.escape(name_l)}\b"
        rf"|\b{re.escape(name_l)}\s*[,!?]",
        text_lower,
    ))


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
            continue
        # Fuzzy: single-token misspelling close to first name
        for word in re.findall(r"\b[a-z]{3,18}\b", lower):
            if _name_fuzzy_match(word, first):
                hits.append(npc)
                break
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        focus = player.get("scene_focus")
        for n in hits:
            if n["id"] == focus:
                return n
        return None
    return None


def _name_fuzzy_match(word, name_part):
    if not word or not name_part or len(name_part) < 4:
        return False
    if abs(len(word) - len(name_part)) > 2:
        return False
    if word == name_part:
        return True
    # Allow one edit distance for names >= 5 chars
    if len(name_part) >= 5 and len(word) >= 4:
        diff = sum(1 for a, b in zip(word, name_part) if a != b)
        diff += abs(len(word) - len(name_part))
        return diff <= 2 and word[:3] == name_part[:3]
    return False


def action_mentions_role_or_descriptor(action, present=None):
    if not action:
        return False
    if ROLE_HINT.search(action):
        return True
    if present and _role_tokens_in_text(action, present):
        return True
    return bool(re.search(r"\bred[\s-]?hair|\bgrey[\s-]?hair|\bauburn\b", action, re.I))


def action_mentions_target_constraint(action, present=None):
    """True when the action binds who the player means."""
    constraints = extract_constraints(action, {}, present or [], {})
    return not constraints.is_empty()


def npc_matches_action_role_hint(action, npc):
    """True when this NPC satisfies every verifiable constraint in the action."""
    return npc_satisfies_constraints(action, npc, player={}, present=[npc])


def target_constraint_unsatisfied(action, present, player=None, npcs=None):
    """True when constraints bind but no present NPC qualifies."""
    result = resolve_target(action, player or {}, present, npcs=npcs, kind="talk")
    return result.status == TargetStatus.ABSENT and bool(result.constraint_violated)


def resolve_action_target(action, player, present, npcs=None, kind="general"):
    """Return the present NPC targeted, or None (absent / ambiguous)."""
    result = resolve_target(action, player, present, npcs=npcs, kind=kind)
    if result.status == TargetStatus.MATCHED:
        return result.npc
    return None


def resolve_investigate_target(action, player, present):
    """Prefer a role-matching NPC for investigation beats when one is named in text."""
    if not present or not action:
        return None
    if not action_mentions_target_constraint(action, present=present):
        return None
    result = resolve_target(action, player, present, kind="investigate")
    return result.npc if result.status == TargetStatus.MATCHED else None


def _role_tokens_in_text(action, present):
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


def apply_resolved_target_to_ctx(action_ctx, result: ResolvedTarget):
    """Write resolution outcome into action_ctx for story_loop / trace."""
    action_ctx["target_resolution"] = {
        "status": result.status.value,
        "npc_id": result.npc_id,
        "reason": result.reason,
        "constraint_violated": result.constraint_violated,
        "candidate_ids": [n["id"] for n in result.candidates],
        "mislabel": bool(getattr(result, "mislabel", False)),
    }

    if getattr(result, "mislabel", False):
        action_ctx["mislabel_resolution"] = True
        action_ctx["story_directive"] = (
            action_ctx.get("story_directive", "")
            + " MISLABEL — player used wrong descriptor for the only person present;"
            + " treat as them but NPC may correct the mistake in dialogue."
        ).strip()

    if result.status == TargetStatus.MATCHED:
        action_ctx["target_id"] = result.npc_id
        action_ctx.pop("target_constraint_failed", None)
        return

    action_ctx["target_id"] = None
    if result.status == TargetStatus.ABSENT and result.constraint_violated:
        action_ctx["target_constraint_failed"] = True
        action_ctx["story_directive"] = (
            action_ctx.get("story_directive", "")
            + " NO MATCH — "
            + (result.reason or "no one here fits that description")
            + ". Do NOT substitute a different person or give them dialogue."
        ).strip()
