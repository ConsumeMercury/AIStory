"""
Scene coherence — travel, cast, speech, and conversation continuity.
Keeps narration aligned with simulation state after each player action.
"""

import re

from generation.descriptor_generator import short_descriptor
from simulation.npc_schedule import schedule_hint, next_appearance

DIALOGUE_KINDS = frozenset({
    "talk", "personal_talk", "ask_name", "help", "give", "threaten",
    "insult", "show_respect", "withdraw", "ask_about", "find", "guild", "confess",
})

_SUBPLACE_PATTERNS = (
    (re.compile(r"\bcellar\b.*\bfishmonger|\bfishmonger\b.*\bcellar\b", re.I), "cellar_fishmonger",
     "the cellar behind the fishmonger"),
    (re.compile(r"\bcellar\b|\bbasement\b|\bunder(?:ground|croft)\b", re.I), "cellar",
     "a cellar nearby"),
)

_ASK_NAMED = re.compile(
    r"^\s*ask\s+([A-Za-z][A-Za-z'-]{1,28})\s+about\s+(.+)$", re.I,
)
_TALK_NAMED = re.compile(
    r"\b(?:talk|speak)\s+(?:to|with)\s+([A-Za-z][A-Za-z'-]{1,28})\b", re.I,
)
_ASK_FOR = re.compile(r"^\s*ask\s+(.+)$", re.I)


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


def resolve_travel_destination(action, player, current_area, dests, areas):
    """
    Pick a travel destination from the area graph, or a sub-place within the current area.
    Returns (chosen_area_id|None, subplace_dict|None, message).
    Never picks a random fallback district.
    """
    text = (action or "").lower()
    flags = player.setdefault("story_flags", {})

    for pattern, sub_id, label in _SUBPLACE_PATTERNS:
        if pattern.search(text):
            if current_area and ":docks" in current_area:
                sub = {"id": sub_id, "label": label, "area": current_area}
                player["scene_subplace"] = sub
                flags[f"subplace_{sub_id}"] = True
                return None, sub, (
                    f"You go to {label} — still within the docks, but below the street noise. "
                    "Same district; describe the enclosed space, not a new city quarter."
                )
            return None, None, (
                "There is no fishmonger's cellar here — you are not at the docks."
            )

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

    if kind in DIALOGUE_KINDS and not action_ctx.get("target_id") and present:
        focus = player.get("scene_focus")
        if focus and focus in present_ids:
            action_ctx["target_id"] = focus
        elif len(present) == 1:
            action_ctx["target_id"] = present[0]["id"]


def is_dialogue_continuation(kind, player, action_ctx, journal):
    if kind not in DIALOGUE_KINDS:
        return False
    if action_ctx.get("absent_npc"):
        return False
    if not journal:
        return False
    last = journal[-1]
    if last.get("area") != player.get("area"):
        return False
    tid = action_ctx.get("target_id")
    focus = player.get("scene_focus")
    if tid and (tid == focus or last.get("focus_npc") == tid):
        return True
    if kind in ("talk", "help", "threaten", "ask_name", "show_respect", "give", "insult"):
        return last.get("kind") in DIALOGUE_KINDS
    return False


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

    speech = (action_ctx or {}).get("player_speech")
    if speech:
        lines.append(f'- Protagonist says ONLY: "{speech}"')

    return "\n".join(lines)


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
