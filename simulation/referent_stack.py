"""
Referent stack — resolve it/that/there from prior beats.

Stores recent npc, object, and place referents on the player save.
"""

from __future__ import annotations

import re

_STACK_CAP = 8

_PRONOUN_IT = re.compile(
    r"\b(?:examine|inspect|look\s+at|pick\s+up|pick|take|grab|use|drop|search\s+for)\s+it\b"
    r"|\bpick\s+it\s+up\b"
    r"|\b(?:examine|inspect|search\s+for)\s+it\b",
    re.I,
)
_ABOUT_THAT = re.compile(r"\b(?:about|on|regarding)\s+that\b", re.I)
_GO_THERE = re.compile(r"\b(?:go|head|travel|walk|move)\s+(?:to\s+)?there\b", re.I)
_LOOT_HIM = re.compile(r"\b(?:loot|search|pick\s+through|rifle\s+through)\s+(?:him|her|the\s+(?:body|corpse))\b", re.I)


def _stack(player) -> list[dict]:
    return list(player.get("referent_stack") or [])


def _push(player, entry: dict):
    stack = [e for e in _stack(player) if e.get("key") != entry.get("key")]
    stack.insert(0, entry)
    player["referent_stack"] = stack[:_STACK_CAP]


def build_stack_from_journal(player, npcs=None):
    """Bootstrap stack from scene focus and recent journal when empty."""
    if _stack(player):
        return
    npcs = npcs or {}
    focus = player.get("scene_focus")
    if focus:
        npc = npcs.get(focus, {})
        _push(player, {
            "key": f"npc:{focus}",
            "type": "npc",
            "id": focus,
            "label": npc.get("name") or npc.get("role") or focus,
        })
    journal = player.get("journal") or []
    for entry in reversed(journal[-4:]):
        fid = entry.get("focus_npc")
        if fid and fid != focus:
            npc = npcs.get(fid, {})
            _push(player, {
                "key": f"npc:{fid}",
                "type": "npc",
                "id": fid,
                "label": npc.get("name") or entry.get("action", "")[:40] or fid,
            })
            break
    sub = player.get("scene_subplace") or {}
    if sub.get("id"):
        _push(player, {
            "key": f"place:{sub['id']}",
            "type": "place",
            "id": sub["id"],
            "label": sub.get("label") or sub["id"],
        })


def update_referent_stack(player, action_ctx, present, npcs=None):
    """Record referents from this beat for the next turn."""
    npcs = npcs or {}
    tid = action_ctx.get("target_id")
    if tid:
        npc = next((n for n in present if n["id"] == tid), None) or npcs.get(tid, {})
        _push(player, {
            "key": f"npc:{tid}",
            "type": "npc",
            "id": tid,
            "label": npc.get("name") or npc.get("role") or tid,
        })

    obj = action_ctx.get("object_ref")
    if obj:
        _push(player, {
            "key": f"object:{obj}",
            "type": "object",
            "ref": obj,
            "label": obj,
        })

    sub = player.get("scene_subplace") or {}
    if sub.get("id"):
        _push(player, {
            "key": f"place:{sub['id']}",
            "type": "place",
            "id": sub["id"],
            "label": sub.get("label") or sub["id"],
        })

    topic = action_ctx.get("ask_topic") or action_ctx.get("investigation_topic")
    if topic:
        _push(player, {
            "key": f"topic:{topic[:40]}",
            "type": "topic",
            "ref": topic[:80],
            "label": topic[:40],
        })


def _find_referent(player, ref_type: str):
    for entry in _stack(player):
        if entry.get("type") == ref_type:
            return entry
    return None


def resolve_anaphora(action, player, present, npcs, ctx: dict) -> bool:
    """
    Resolve it/that/there/corpse pronouns from referent stack.
    Mutates ctx; returns True when anaphora was resolved or failed explicitly.
    """
    text = (action or "").strip()
    if not text:
        return False

    build_stack_from_journal(player, npcs)
    stack = _stack(player)
    if not stack:
        if _PRONOUN_IT.search(text) or _ABOUT_THAT.search(text) or _GO_THERE.search(text):
            ctx["interpretation_clarify"] = True
            ctx["interpretation_clarify_reason"] = "unclear referent — what do you mean by it/that/there?"
            ctx.setdefault("interpretation_preprocess", {})["anaphora_unresolved"] = True
            return True
        return False

    present_ids = {n["id"] for n in present}
    resolved = {}

    if _PRONOUN_IT.search(text):
        obj = _find_referent(player, "object") or _find_referent(player, "topic")
        if obj and obj.get("type") == "object":
            ctx["object_ref"] = obj.get("ref")
            ctx["target_id"] = None
            if not ctx.get("kind") or ctx.get("kind") == "general":
                ctx["kind"] = "search" if re.search(r"\b(?:take|grab|pick)\b", text, re.I) else "examine"
            resolved["it"] = obj.get("ref")
        elif obj and obj.get("type") == "topic":
            ctx["ask_topic"] = obj.get("ref")
            if ctx.get("kind") == "general":
                ctx["kind"] = "ask_about"
            resolved["it"] = obj.get("ref")
        else:
            ctx["interpretation_clarify"] = True
            ctx["interpretation_clarify_reason"] = "unclear referent — what is 'it'?"
            ctx.setdefault("interpretation_preprocess", {})["anaphora_unresolved"] = "it"
            return True

    if _ABOUT_THAT.search(text):
        topic = _find_referent(player, "topic") or _find_referent(player, "object")
        if topic:
            ctx["ask_topic"] = topic.get("ref") or topic.get("label")
            if ctx.get("kind") in ("general", "talk"):
                ctx["kind"] = "ask_about"
            resolved["that"] = ctx["ask_topic"]
        else:
            ctx["interpretation_clarify"] = True
            ctx["interpretation_clarify_reason"] = "unclear referent — what is 'that'?"
            return True

    if _GO_THERE.search(text):
        place = _find_referent(player, "place")
        if place:
            ctx["referent_place"] = place.get("id")
            ctx["kind"] = "approach"
            resolved["there"] = place.get("label")
        else:
            ctx["interpretation_clarify"] = True
            ctx["interpretation_clarify_reason"] = "unclear referent — where is 'there'?"
            return True

    if _LOOT_HIM.search(text):
        corpse = player.get("last_combat_target")
        fatality = player.get("last_combat_fatal")
        if corpse and fatality:
            npc = (npcs or {}).get(corpse, {})
            if npc.get("status") != "alive" or fatality:
                ctx["object_ref"] = "corpse"
                ctx["target_id"] = corpse if corpse in present_ids else None
                ctx["kind"] = "search"
                ctx["story_directive"] = (
                    (ctx.get("story_directive") or "")
                    + " CORPSE SEARCH — loot the dead, not a living speaker."
                ).strip()
                resolved["corpse"] = corpse
        elif corpse and corpse in present_ids:
            ctx["target_id"] = corpse
            ctx["kind"] = "search"
            ctx["object_ref"] = "corpse"
            resolved["corpse"] = corpse
        else:
            ctx["target_constraint_failed"] = True
            ctx["target_id"] = None
            ctx["story_directive"] = (
                (ctx.get("story_directive") or "")
                + " NO CORPSE — nothing here to loot."
            ).strip()
            resolved["corpse"] = None

    if resolved:
        pre = ctx.setdefault("interpretation_preprocess", {})
        pre["anaphora_resolved"] = resolved
        ctx["referents_resolved"] = resolved
        return True
    return False
