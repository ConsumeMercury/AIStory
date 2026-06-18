"""
Detect ambiguous NPC targeting before mechanics run.
Simulation asks for clarification instead of guessing present[0].
"""

import logging
import re

from generation.descriptor_generator import short_descriptor
from simulation.target_constraints import TargetStatus, resolve_target
from simulation.target_resolution import (
    TARGET_KINDS,
    action_mentions_target_constraint,
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
    male_hint = bool(re.search(r"\b(him|he|man|boy|fellow|bloke)\b", text)) and not re.search(
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
    Constraint survivors only — never offer NPCs that violate what the player said.
    """
    if kind not in _CLARIFY_KINDS or not present or len(present) < 2:
        return None
    if target_id:
        return None

    result = resolve_target(action, player, present, npcs=npcs, kind=kind)
    if result.status == TargetStatus.AMBIGUOUS and len(result.candidates) >= 2:
        return {
            "kind": kind,
            "reason": result.reason or "target unclear",
            "options": [_clarification_option(n, kind) for n in result.candidates[:6]],
            "original_action": (action or "").strip()[:200],
        }

    if result.status in (TargetStatus.MATCHED, TargetStatus.ABSENT):
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

    if not candidates and action_mentions_target_constraint(action, present=present):
        desc_hits = collect_description_matches(action, present)
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
            or action_mentions_target_constraint(action, present=present)
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
    options = pending.get("options") or []

    opt_ids = {o["id"] for o in options}

    # Exact chip match first
    for opt in options:
        chip = (opt.get("chip") or "").lower()
        if chip and lower == chip:
            return pending.get("kind"), opt["id"]

    for opt in options:
        chip = (opt.get("chip") or "").lower()
        if chip and chip in lower and len(lower) <= len(chip) + 8:
            return pending.get("kind"), opt["id"]

    # Name / label match — options are authoritative; do not require scene cast membership
    for opt in options:
        oid = opt.get("id")
        if not oid or oid not in opt_ids:
            continue
        npc = npcs.get(oid, {})
        if npc.get("status") == "dead":
            continue
        label = (opt.get("label") or "").strip()
        if label and re.search(rf"\b{re.escape(label.lower())}\b", lower):
            return pending.get("kind"), oid
        name = (npc.get("name") or "").strip()
        if name and re.search(rf"\b{re.escape(name.lower())}\b", lower):
            return pending.get("kind"), oid
        first = name.split()[0].lower() if name else ""
        if first and len(first) > 2 and re.search(rf"\b{re.escape(first)}\b", lower):
            return pending.get("kind"), oid

    m = re.match(r"^\s*(\d+)\s*$", text)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(options):
            opt = options[idx]
            oid = opt.get("id")
            if oid in opt_ids and npcs.get(oid, {}).get("status") != "dead":
                return pending.get("kind"), oid

    # Constraint answer: "the woman", "the guard", "him" — not generic unrelated text
    has_target_signal = bool(
        re.search(
            r"\b(him|her|he|she|the\s+\w+|man|woman|boy|girl|first|second|last|middle)\b",
            lower,
        )
    )
    if has_target_signal:
        from simulation.target_constraints import resolve_target
        result = resolve_target(
            text, player, present, npcs=npcs, kind=pending.get("kind", "talk"),
        )
        if result.matched and result.npc_id in opt_ids:
            return pending.get("kind"), result.npc_id

    note_pending_pick_failed(player)
    return None, None


def should_abandon_clarification(action, player):
    """True when pending clarification should clear for a new unrelated action."""
    pending = player.get("pending_target_clarification")
    if not pending:
        return False
    text = (action or "").strip().lower()
    if not text:
        return False
    if re.match(r"^\d+$", text):
        return False
    for opt in pending.get("options") or []:
        chip = (opt.get("chip") or "").lower()
        if chip and chip in text:
            return False
    # New verb-heavy action unrelated to picking among options
    if re.search(
        r"\b(?:explore|travel|rest|wait|investigate|attack|steal|give|buy|leave|help)\b",
        text,
    ):
        return True
    if len(text.split()) >= 4 and not re.search(r"\b(?:him|her|the\s+\w+)\b", text):
        return True
    return False


def set_pending_clarification(player, pending):
    pending = dict(pending or {})
    existing = player.get("pending_target_clarification") or {}
    same_question = (
        existing.get("original_action") == pending.get("original_action")
        and existing.get("kind") == pending.get("kind")
    )
    pending["fail_count"] = existing.get("fail_count", 0) if same_question else 0
    player["pending_target_clarification"] = pending


def note_pending_pick_failed(player):
    pending = player.get("pending_target_clarification")
    if not pending:
        return
    pending["fail_count"] = int(pending.get("fail_count") or 0) + 1
    player["pending_target_clarification"] = pending


def pending_clarification_exhausted(player, *, max_failures=3) -> bool:
    pending = player.get("pending_target_clarification") or {}
    return int(pending.get("fail_count") or 0) >= max_failures


def clear_pending_clarification(player):
    player.pop("pending_target_clarification", None)
