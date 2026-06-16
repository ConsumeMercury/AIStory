"""
Choose who is actually in the scene — one focal person, not a crowd of strangers.
"""

import random
import re

from generation.descriptor_generator import short_descriptor
from storage import load

INST_FILE = "world/institutions.json"


def _institution_boost(npc, player_area, institutions):
    inst_ref = npc.get("institution")
    if not inst_ref or not player_area:
        return 0
    inst = institutions.get(inst_ref.get("id"), {})
    if inst.get("area") == player_area:
        return 25
    return 0


ROLE_GOAL_THEMES = {
    "scholar": "discovery",
    "scribe": "discovery",
    "priest": "discovery",
    "merchant": "wealth",
    "innkeeper": "wealth",
    "guard": "renown",
    "soldier": "renown",
    "hunter": "renown",
    "mercenary": "conflict",
}


def _goal_npc_boost(npc, player, action_kind):
    """Prefer NPCs who might advance the player's stated aim."""
    themes = set(player.get("goal_themes") or [])
    if not themes or action_kind not in ("explore", "find", "investigate", "ask_about", "talk"):
        return 0
    role_theme = ROLE_GOAL_THEMES.get(npc.get("role", ""))
    if role_theme and role_theme in themes:
        return 22
    obj_raw = npc.get("personal_objective") or ""
    if isinstance(obj_raw, dict):
        obj = (obj_raw.get("text") or "").lower()
    else:
        obj = str(obj_raw).lower()
    motivation = (player.get("motivation") or "").lower()
    if motivation and len(motivation) > 8:
        for word in motivation.split():
            if len(word) > 4 and word in obj:
                return 18
    return 0


def _score_npc(npc, player, action_ctx, known, institutions=None):
    """Higher = more likely to be the scene's focus."""
    score = 0.0
    nid = npc["id"]
    tid = action_ctx.get("target_id")
    if tid == nid:
        score += 100
    elif not tid and player.get("scene_focus") == nid:
        score += 80
    if npc.get("key_npc"):
        score += 45
    if known.get(nid, {}).get("name_known"):
        score += 60
    if known.get(nid, {}).get("seen_before"):
        score += 20
    score += _institution_boost(npc, player.get("area"), institutions or {})
    # age proximity for social actions
    if action_ctx.get("kind") in (
        "talk", "ask_name", "personal_talk", "help", "give",
        "threaten", "insult", "show_respect", "find", "confess", "attack",
    ):
        age_diff = abs(npc.get("age", 30) - player.get("age", 30))
        if age_diff <= 6:
            score += 15
        if age_diff <= 12:
            score += 8
        score += npc.get("physique", {}).get("presentation", 50) * 0.1
    score += _goal_npc_boost(npc, player, action_ctx.get("kind", ""))
    return score


def select_scene_cast(present, player, action_ctx, max_focus=1):
    """
    Returns (focus_list, crowd_note, focal_id).
    focus_list: NPCs the narrator may describe in detail (usually one).
    focal_id: authoritative simulation decision for who is focal — pass to narrator verbatim.
    """
    absent = action_ctx.get("absent_npc")
    if absent:
        label = absent.get("name") or absent.get("descriptor") or "They"
        return [], (
            f"{label} is NOT in this scene. "
            "Do NOT invent their dialogue or presence — show the protagonist looking, "
            "calling out, or finding no answer."
        ), None

    if not present:
        return [], "You are alone here.", None

    kind = action_ctx.get("kind", "general")
    present_ids = {n["id"] for n in present}
    tid = action_ctx.get("target_id")
    if tid and tid not in present_ids:
        keep_dead_combat = (
            kind == "attack"
            and (
                action_ctx.get("combat_snapshot")
                or action_ctx.get("combat_fatal") is not None
            )
        )
        if not keep_dead_combat:
            action_ctx["target_id"] = None
            if player.get("scene_focus") == tid:
                player["scene_focus"] = None

    known = player.get("known_npcs", {})
    institutions = load(INST_FILE, {})

    if action_ctx.get("travel_failed") or action_ctx.get("approach_failed"):
        return [], (
            "NO MOVEMENT — the protagonist stays where they were. "
            "Do NOT describe entering new buildings, crossing districts, or meeting strangers. "
            "One short beat of frustration or re-orientation only."
        ), None

    if kind == "investigate":
        action_ctx["target_id"] = None
        return [], (
            "Environment-only investigation. Describe place, objects, sounds, contradictions. "
            "Do NOT invent new named NPCs (no priests, clerks, or strangers with dialogue). "
            "Do NOT give dialogue to anyone the protagonist was just talking to — clues are physical, "
            "overheard, or written, not speeches from a conversation partner. "
            "Background crowd is faceless — no speeches."
        ), None

    if kind in ("explore", "rest", "travel", "observe", "approach") and not action_ctx.get("target_id"):
        if kind == "find":
            pass  # find always wants a person
        elif len(present) == 1 and kind not in ("travel", "approach"):
            fid = present[0]["id"]
            return present[:1], "No one else of note.", fid
        elif kind == "approach" and player.get("scene_subplace"):
            return [], (
                f"Local movement to {(player.get('scene_subplace') or {}).get('label', 'a nearby spot')}. "
                "Place and atmosphere only — no focal NPC unless already in conversation."
            ), None
        return [], (
            f"The {kind} action is about place and atmosphere. "
            f"Do NOT introduce or describe individual strangers. "
            f"There are people in the distance — indistinct, unnamed, unimportant."
        ), None

    ranked = sorted(present, key=lambda n: _score_npc(n, player, action_ctx, known, institutions), reverse=True)
    focus = ranked[:max_focus]
    focal_id = focus[0]["id"] if focus else None

    others = len(present) - len(focus)
    if others <= 0:
        crowd = "No other individuals worth distinguishing this scene."
    else:
        crowd = (
            f"{others} other people are nearby as background only — "
            f"do NOT describe them, name them, or give them gestures or dialogue. "
            f"They are faceless crowd noise."
        )
    return focus, crowd, focal_id


def pick_name_target(player, present, action):
    """Who the player is asking for a name — prefer scene focus or hinted person."""
    known = player.setdefault("known_npcs", {})
    candidates = [n for n in present if not known.get(n["id"], {}).get("name_known")]
    if not candidates:
        return None
    focus_id = player.get("scene_focus")
    for n in candidates:
        if n["id"] == focus_id:
            return n
    text = action.lower()
    if re.search(r"\b(woman|girl|lady|she|her)\b", text):
        for n in candidates:
            if n.get("gender") == "female":
                return n
    if re.search(r"\b(man|boy|he|him)\b", text) and not re.search(r"\bwoman\b", text):
        for n in candidates:
            if n.get("gender") == "male":
                return n
    for n in candidates:
        build = n.get("physique", {}).get("build", "").lower()
        if build and build in text:
            return n
    if len(candidates) == 1:
        return candidates[0]
    return candidates[0]
