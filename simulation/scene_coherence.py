"""
Scene coherence — travel, cast, speech, and conversation continuity.
Keeps narration aligned with simulation state after each player action.
"""

import re

from generation.descriptor_generator import short_descriptor
from simulation.npc_schedule import schedule_hint, next_appearance
from simulation.local_places import resolve_local_movement
from simulation.target_resolution import (
    action_mentions_role_or_descriptor,
    resolve_action_target,
    find_npc_by_name_in_text,
    npc_matches_action_role_hint,
)

DIALOGUE_KINDS = frozenset({
    "talk", "personal_talk", "ask_name", "help", "give", "threaten",
    "insult", "show_respect", "withdraw", "ask_about", "find", "guild", "confess",
})

_ASK_NAMED = re.compile(
    r"^\s*ask\s+([A-Za-z][A-Za-z'-]{1,28})\s+about\s+(.+)$", re.I,
)
_TALK_NAMED = re.compile(
    r"\b(?:talk|speak)\s+(?:to|with)\s+([A-Za-z][A-Za-z'-]{1,28})\b", re.I,
)
_ASK_FOR = re.compile(r"^\s*ask\s+(.+)$", re.I)


def resolve_travel_destination(action, player, current_area, dests, areas):
    """
    Pick a travel destination from the area graph, or a sub-place within the current area.
    Returns (chosen_area_id|None, subplace_dict|None, message).
    Never picks a random fallback district.
    """
    text = (action or "").lower()

    sub, local_msg = resolve_local_movement(action, player, current_area)
    if sub:
        return None, sub, local_msg
    if local_msg and not sub:
        return None, None, local_msg

    if not dests:
        return None, None, "There is nowhere reachable from here on the map."

    scored = []
    for aid, hours in dests.items():
        area = areas.get(aid, {})
        name = (area.get("name") or "").lower()
        leaf = aid.split(":")[-1].replace("_", " ")
        score = 0
        if aid.lower() in text:
            score += 100
        if leaf in text or leaf.replace("_", " ") in text:
            score += 80
        for word in name.split():
            if len(word) > 3 and word in text:
                score += 40
        if area.get("city") and area["city"].replace("_", " ") in text:
            score += 25
        if score > 0:
            scored.append((score, hours, aid))

    if not scored:
        return None, None, (
            "That place is not on the travel map from here. "
            "Name a district you can reach, or explore where you stand."
        )

    scored.sort(key=lambda x: (-x[0], x[1]))
    chosen = scored[0][2]
    player.pop("scene_subplace", None)
    return chosen, None, None


def sync_scene_focus(player, present, npcs):
    """Drop scene focus when that NPC is not in the current area."""
    focus_id = player.get("scene_focus")
    if not focus_id:
        return
    if any(n["id"] == focus_id for n in present):
        return
    player["scene_focus"] = None


def resolve_target_and_absence(action, player, present, npcs, action_ctx, world, areas):
    """
    Set target_id when valid; populate absent_npc when player names someone not here.
    Mutates action_ctx and may update player scene_focus.
    """
    present_ids = {n["id"] for n in present}
    kind = action_ctx.get("kind", "general")

    named = find_npc_by_name_in_text(action, npcs, player)
    if named and named["id"] not in present_ids:
        action_ctx["absent_npc"] = {
            "id": named["id"],
            "name": named.get("name"),
            "descriptor": short_descriptor(named),
            "area": named.get("area"),
        }
        action_ctx["target_id"] = None
        nxt = next_appearance(named, world, areas)
        where = schedule_hint(named, world) or "elsewhere on their routine"
        if nxt:
            where = f"{nxt.get('area_name', 'elsewhere')} in ~{nxt.get('in_hours', '?')}h"
        action_ctx["story_directive"] = (
            action_ctx.get("story_directive", "")
            + f" {named.get('name', 'They')} is NOT in this scene — still at {where}. "
            "The protagonist cannot speak to them here. Show the empty result of looking or calling — "
            "no invented dialogue from the absent person."
        ).strip()
        if player.get("scene_focus") == named["id"]:
            player["scene_focus"] = None
        return

    tid = action_ctx.get("target_id")
    if tid and tid not in present_ids:
        action_ctx["target_id"] = None
        if player.get("scene_focus") == tid:
            player["scene_focus"] = None

    if kind in DIALOGUE_KINDS and present:
        has_role = action_mentions_role_or_descriptor(action, present=present)
        tid = action_ctx.get("target_id")
        if tid and tid in present_ids and has_role:
            current = next((n for n in present if n["id"] == tid), None)
            if current and not npc_matches_action_role_hint(action, current):
                action_ctx["target_id"] = None

        if not action_ctx.get("target_id") or has_role:
            resolved = resolve_action_target(
                action, player, present, npcs=npcs, kind=kind,
            )
            if resolved:
                action_ctx["target_id"] = resolved["id"]
            elif has_role:
                action_ctx["target_id"] = None
            elif not action_ctx.get("target_id"):
                focus = player.get("scene_focus")
                if focus and focus in present_ids:
                    action_ctx["target_id"] = focus
                elif len(present) == 1:
                    action_ctx["target_id"] = present[0]["id"]


def build_conversation_ledger(player, journal, npc_id, action_ctx):
    """Recent exchange + locks for the focal NPC."""
    if not npc_id or not journal:
        return ""

    from storage import load
    npcs = load("characters/npcs.json", {})
    npc = npcs.get(npc_id, {})
    name = npc.get("name", "They")
    known = player.get("known_npcs", {}).get(npc_id, {})
    name_known = known.get("name_known", False)

    lines = ["CONVERSATION LEDGER (same scene thread — obey strictly):"]
    if name_known:
        lines.append(
            f"- You ALREADY know their name is {name}. "
            "Do NOT have them introduce themselves again or repeat the name unless directly asked."
        )

    last_player = None
    last_scene = None
    for entry in reversed(journal[-6:]):
        if entry.get("focus_npc") == npc_id or (
            name_known and name.split()[0].lower() in (entry.get("action") or "").lower()
        ):
            if not last_player:
                last_player = entry.get("action", "")[:120]
            if not last_scene and entry.get("excerpt"):
                last_scene = entry.get("excerpt", "")[:200]
            if last_player and last_scene:
                break

    if last_player:
        lines.append(f"- Last player action: {last_player}")
    if last_scene:
        lines.append(f"- Last beat (do not replay): {last_scene}")

    check = (action_ctx or {}).get("skill_check")
    if check and not check.get("success"):
        lines.append(
            "- Last attempt FAILED. Same person, same voice — shorter, colder, guarded. "
            "No stammer or new personality unless their persona quirk already includes it."
        )

    if action_ctx.get("wait_no_change"):
        lines.append(
            "- WAIT produced NO state change. Do NOT repeat the prior NPC line verbatim — "
            "especially not bell, auction, or wait promises."
        )

    speech = (action_ctx or {}).get("player_speech")
    if speech:
        lines.append(f'- Protagonist says ONLY: "{speech}"')

    body = "\n".join(lines)
    return body


def stable_persona_block(npc):
    persona = npc.get("persona") or {}
    parts = []
    if persona.get("speech_style"):
        parts.append(f"speech={persona['speech_style']}")
    if persona.get("voice_quirk"):
        parts.append(f"quirk={persona['voice_quirk']}")
    if persona.get("mood"):
        parts.append(f"mood={persona['mood']}")
    if persona.get("values"):
        parts.append(f"values={persona['values']}")
    if not parts:
        return ""
    return (
        "  PERSONA (fixed for this character — never swap register between beats):\n"
        f"  {'; '.join(parts)}\n"
        "  Failed checks: same voice, less warmth — not a different person.\n"
    )


def place_label(player, area):
    """Area name plus optional sub-place (cellar, etc.)."""
    base = area.get("name", "") if area else ""
    sub = player.get("scene_subplace") or {}
    if sub.get("area") == player.get("area") and sub.get("label"):
        return f"{base} — {sub['label']}"
    return base
