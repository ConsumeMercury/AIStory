"""
Detect ambiguous NPC targeting before mechanics run.
Simulation asks for clarification instead of guessing present[0].
"""

import logging
import re

from generation.descriptor_generator import short_descriptor
from simulation.target_resolution import (
    TARGET_KINDS,
    action_mentions_role_or_descriptor,
    find_npc_by_name_in_text,
)

log = logging.getLogger(__name__)

_CLARIFY_KINDS = frozenset(TARGET_KINDS) | frozenset({"find"})


def collect_description_matches(action, present):
    from simulation.action_resolution import _DESC_HINTS

    hits = []
    seen = set()
    if not action or not present:
        return hits
    for pattern, matcher in _DESC_HINTS:
        if not pattern.search(action):
            continue
        for npc in present:
            try:
                if matcher(npc) and npc["id"] not in seen:
                    hits.append(npc)
                    seen.add(npc["id"])
            except Exception:
                log.debug("description match failed for npc %s", npc.get("id"), exc_info=True)
    return hits


def collect_name_matches(action, npcs, player, present_ids):
    """Multiple known names mentioned in text that are present."""
    if not action or not npcs:
        return []
    lower = action.lower()
    known = player.get("known_npcs", {})
    hits = []
    seen = set()
    for nid, npc in npcs.items():
        if npc.get("status") != "alive" or nid not in present_ids:
            continue
        name = (npc.get("name") or "").strip()
        if not name or not known.get(nid, {}).get("name_known"):
            continue
        if re.search(rf"\b{re.escape(name.lower())}\b", lower):
            if nid not in seen:
                hits.append(npc)
                seen.add(nid)
    if len(hits) <= 1:
        return hits
    focus = player.get("scene_focus")
    if focus:
        focused = [n for n in hits if n["id"] == focus]
        if len(focused) == 1:
            return focused
    return hits


def collect_gender_matches(action, present):
    text = (action or "").lower()
    female_hint = bool(re.search(r"\b(her|she|woman|girl|lady)\b", text))
    male_hint = bool(re.search(r"\b(him|he|man|boy)\b", text)) and not re.search(
        r"\b(her|she|woman|girl|lady)\b", text,
    )
    if female_hint:
        return [n for n in present if n.get("gender") == "female"]
    if male_hint:
        return [n for n in present if n.get("gender") == "male"]
    return []


def detect_target_ambiguity(action, player, present, npcs, kind, *, target_id=None):
    """
    Return ambiguity payload when the player must pick among present NPCs.
    None when targeting is clear enough to proceed (or no candidates).
    """
    if kind not in _CLARIFY_KINDS or not present or len(present) < 2:
        return None
    if target_id:
        return None

    present_ids = {n["id"] for n in present}
    reason = None
    candidates = []

    name_hits = collect_name_matches(action, npcs, player, present_ids)
    if len(name_hits) > 1:
        candidates = name_hits
        reason = "more than one person you named is here"

    if not candidates:
        desc_hits = collect_description_matches(action, present)
        if len(desc_hits) > 1:
            focus = player.get("scene_focus")
            focused = [n for n in desc_hits if n["id"] == focus]
            if len(focused) == 1:
                return None
            candidates = desc_hits
            reason = "more than one person matches that description"

    if not candidates and action_mentions_role_or_descriptor(action, present=present):
        desc_hits = collect_description_matches(action, present)
        if len(desc_hits) == 0 and kind in ("attack", "find"):
            return None
        if len(desc_hits) > 1:
            candidates = desc_hits
            reason = "more than one person matches that role"

    if not candidates:
        gender_hits = collect_gender_matches(action, present)
        if len(gender_hits) > 1:
            focus = player.get("scene_focus")
            focused = [n for n in gender_hits if n["id"] == focus]
            if len(focused) == 1:
                return None
            candidates = gender_hits
            reason = "more than one person matches that pronoun"

    if not candidates and kind == "attack":
        text = (action or "").lower()
        specific = bool(
            re.search(r"\b(knight|knights|guard|guards|soldier|soldiers|monster|beast)\b", text)
            or find_npc_by_name_in_text(action, npcs, player)
            or re.search(r"\b(her|him|she|he)\b", text)
            or action_mentions_role_or_descriptor(action, present=present)
            or player.get("scene_focus")
            or (
                player.get("last_combat_target")
                and re.search(r"\b(again|anyway|still|finish|keep fighting)\b", text)
            )
        )
        if not specific:
            candidates = list(present)
            reason = "several people are here — no clear target for violence"

    if not candidates or len(candidates) < 2:
        return None

    return {
        "kind": kind,
        "reason": reason or "target unclear",
        "options": [_clarification_option(n, kind) for n in candidates[:6]],
        "original_action": (action or "").strip()[:200],
    }


def _clarification_option(npc, kind):
    desc = short_descriptor(npc)
    role = (npc.get("role") or "stranger").replace("_", " ")
    name = npc.get("name")
    label = f"{name} ({role})" if name else f"{desc}, {role}"
    verb = {
        "attack": "attack",
        "find": "find",
        "talk": "talk to",
        "personal_talk": "talk to",
        "ask_name": "ask",
        "help": "help",
        "give": "give to",
        "threaten": "threaten",
        "insult": "insult",
        "show_respect": "show respect to",
        "trade": "trade with",
        "steal": "steal from",
        "ask_about": "ask",
        "accuse": "accuse",
        "blackmail": "blackmail",
        "guild": "ask",
        "confess": "confess to",
        "investigate": "investigate",
    }.get(kind, "approach")
    chip_name = name.split()[0] if name else desc.split(",")[0].strip()
    return {
        "id": npc["id"],
        "label": label,
        "chip": f"{verb} {chip_name}".strip(),
    }


def build_clarification_scene(pending):
    reason = pending.get("reason", "target unclear")
    lines = [f"You hesitate — {reason}:", ""]
    for i, opt in enumerate(pending.get("options") or [], 1):
        lines.append(f"  {i}. {opt['label']}")
    lines.append("")
    lines.append("Choose one (tap a chip or name them clearly).")
    return "\n".join(lines)


def resolve_clarification_pick(action, player, present, npcs):
    """
    If player is answering a pending clarification, return (kind, npc_id) or (None, None).
    """
    pending = player.get("pending_target_clarification")
    if not pending:
        return None, None

    text = (action or "").strip()
    lower = text.lower()
    present_ids = {n["id"] for n in present}
    options = pending.get("options") or []

    for opt in options:
        chip = (opt.get("chip") or "").lower()
        if chip and lower == chip:
            return pending.get("kind"), opt["id"]
        if chip and chip in lower:
            return pending.get("kind"), opt["id"]

    for opt in options:
        if opt["id"] not in present_ids:
            continue
        npc = next((n for n in present if n["id"] == opt["id"]), None) or npcs.get(opt["id"], {})
        name = (npc.get("name") or "").strip()
        if name and re.search(rf"\b{re.escape(name.lower())}\b", lower):
            return pending.get("kind"), opt["id"]
        first = name.split()[0].lower() if name else ""
        if first and len(first) > 2 and re.search(rf"\b{re.escape(first)}\b", lower):
            return pending.get("kind"), opt["id"]

    m = re.match(r"^\s*(\d+)\s*$", text)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(options):
            opt = options[idx]
            if opt["id"] in present_ids:
                return pending.get("kind"), opt["id"]

    return None, None


def set_pending_clarification(player, pending):
    player["pending_target_clarification"] = pending


def clear_pending_clarification(player):
    player.pop("pending_target_clarification", None)
