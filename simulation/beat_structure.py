"""
Beat-type prose structure — vary scene shape by what the beat is for.

Simulation knows kind and what changed; the narrator prompt must translate that
into opening structure, not just temperature.
"""

HIGH_TENSION_KINDS = frozenset({
    "attack", "threaten", "confess", "accuse", "blackmail", "steal",
})
REVELATION_KINDS = frozenset({
    "search", "investigate", "find", "ask_about", "examine", "observe",
})


def recent_same_area(journal, area_id, window=12):
    if not area_id or not journal:
        return []
    return [e for e in journal[-window:] if e.get("area") == area_id]


def beats_with_same_focus(journal, area_id, focal_npc_id, window=8):
    if not focal_npc_id or not area_id:
        return 0
    return sum(
        1 for e in journal[-window:]
        if e.get("area") == area_id and e.get("focus_npc") == focal_npc_id
    )


def _nothing_changed(action_context):
    ctx = action_context or {}
    return bool(
        ctx.get("approach_failed")
        or ctx.get("travel_failed")
        or ctx.get("target_ambiguous")
        or ctx.get("interpretation_clarify")
        or ctx.get("duplicate_action")
        or ctx.get("clarification_reprompt")
        or ctx.get("wait_no_change")
    )


def _has_revelation(action_context, kind):
    ctx = action_context or {}
    if kind == "search" and ctx.get("acquired_item"):
        return True
    if kind == "find" and ctx.get("target_id") and not ctx.get("find_failed"):
        return True
    if kind == "investigate" and (ctx.get("story_directive") or "").strip():
        return True
    check = ctx.get("skill_check") or {}
    if check.get("success") and kind in ("ask_about", "examine", "investigate", "observe"):
        return True
    if ctx.get("name_reveal") or ctx.get("confession_facts"):
        return True
    return False


def classify_beat_structure(kind, action_context, player, journal, area_id, focal_npc_id):
    """Return structure mode: revelation, stalled, tension, continuation, arrival, action."""
    if _nothing_changed(action_context):
        return "stalled"
    if kind in HIGH_TENSION_KINDS or (action_context or {}).get("combat_fatal"):
        return "tension"
    if _has_revelation(action_context, kind):
        return "revelation"
    same_spot = len(recent_same_area(journal, area_id))
    if same_spot >= 3 and kind in (
        "talk", "personal_talk", "show_respect", "guild", "help", "give", "insult",
    ):
        return "continuation"
    if kind == "explore" and not journal:
        return "arrival"
    if same_spot >= 4 and kind in ("explore", "observe", "rest", "approach"):
        return "continuation"
    if beats_with_same_focus(journal, area_id, focal_npc_id) >= 2:
        return "continuation"
    return "action"


STRUCTURE_DIRECTIVES = {
    "revelation": (
        "PROSE STRUCTURE — REVELATION:\n"
        "Open on what is NEW — the discovery, answer, object found, or clue understood. "
        "At most one short clause of place before the reveal. "
        "Do NOT open with weather, heat, stall layout, or NPC appearance."
    ),
    "stalled": (
        "PROSE STRUCTURE — STALLED / NO CHANGE:\n"
        "Nothing moved. One short paragraph (2–4 sentences). "
        "Do NOT re-paint the room, weather, or the NPC's face. "
        "Open on friction — repetition, silence, impatience, or one small new detail. "
        "Do NOT repeat the prior NPC line verbatim — especially not bell/auction/wait promises."
    ),
    "tension": (
        "PROSE STRUCTURE — HIGH TENSION:\n"
        "Drop sensory throat-clearing. Open in the middle of motion, threat, or consequence. "
        "No weather opener. No arrival paragraph. Body and breath first."
    ),
    "continuation": (
        "PROSE STRUCTURE — CONTINUATION:\n"
        "Mid-scene, not chapter one. The player has been here — do NOT re-describe setting, weather, "
        "the stall, or the focal person's appearance. Open on dialogue or the next beat of action."
    ),
    "arrival": (
        "PROSE STRUCTURE — OPENING ARRIVAL:\n"
        "Use the full 3–4 paragraph length. Teach the player the environment: spatial layout, "
        "who belongs here, what this place is for, one live tension, and one implicit hook "
        "for what they might do next. Spread at least two senses beyond sight across the scene. "
        "No dialogue exchange yet."
    ),
    "action": (
        "PROSE STRUCTURE — ACTION:\n"
        "Open on what the player did this beat, not atmosphere. "
        "Weather only if it changes the beat — never as the first line by habit."
    ),
}


def build_opening_variation_note(journal, kind):
    """Explicit ban on the weather/atmosphere opening tic."""
    if not journal:
        return ""
    last = journal[-1]
    last_excerpt = (last.get("excerpt") or last.get("scene") or "")[:200].lower()
    weather_tic = any(
        w in last_excerpt
        for w in ("heat", "sun", "weather", "fog", "cold", "wind", "rain", "humid", "stall")
    )
    lines = [
        "OPENING VARIATION: Do NOT begin with weather, heat, fog, or generic sensory atmosphere.",
        "Vary your first sentence — dialogue, action, thought, or object — not another room description.",
    ]
    if weather_tic and kind not in ("explore", "travel"):
        lines.append(
            "The last beat already opened on atmosphere — this beat MUST use a different opening shape."
        )
    return "\n".join(lines)


def build_beat_structure_block(kind, action_context, player, journal, area_id, focal_npc_id):
    mode = classify_beat_structure(
        kind, action_context, player, journal, area_id, focal_npc_id,
    )
    parts = [STRUCTURE_DIRECTIVES[mode]]
    opening = build_opening_variation_note(journal, kind)
    if opening:
        parts.append(opening)
    same = len(recent_same_area(journal, area_id))
    if same >= 3 and area_id:
        parts.append(
            f"SAME SPOT ({same + 1} beats in this place): prose is continuous — "
            "no second arrival, no re-establishing the district or stall."
        )
    return "\n\n".join(parts)


def build_narrative_thread_directive(
    player, npcs, *, focal_npc_id=None, present_ids=None, kind="general", action_context=None,
):
    """
    Prominent arc/stakes block — what the player is pursuing and what this beat should do.
    Includes deterministic plot summary from simulation state.
    """
    from simulation.plot_summary import build_plot_summary

    plot = build_plot_summary(
        player, npcs, focal_npc_id=focal_npc_id, present_ids=present_ids,
    )
    ctx = action_context or {}
    lines = [
        "NARRATIVE THREAD (this beat must serve the story — not atmospheric filler):",
    ]

    case = player.get("active_case") or {}
    if case and not case.get("solved"):
        title = case.get("title", "the case")
        stage = case.get("stage", 0)
        stages = case.get("stages") or []
        stage_label = stages[min(stage, len(stages) - 1)] if stages else "investigate"
        lines.append(
            f"- Pursuit: {title} — stage «{stage_label}». "
            "Move this thread (clue, reaction, setback, or lead); do not drift."
        )

    goals = [g for g in (player.get("goals") or []) if not g.get("complete")]
    if goals:
        g = goals[0]
        text = (g.get("text") or "")[:100]
        prog = g.get("progress", 0)
        target = g.get("target", "?")
        lines.append(f"- Goal ({prog}/{target}): {text}")

    stakes = player.get("scene_stakes") or {}
    if stakes.get("dramatic_question"):
        lines.append(f"- Dramatic question: {stakes['dramatic_question'][:100]}")
    if stakes.get("lose"):
        lines.append(f"- At stake: {stakes['lose'][:80]}")

    pipe = player.get("starting_pipeline") or {}
    if pipe.get("hook") and not (case and case.get("title")):
        lines.append(
            f"- Local thread ({pipe.get('title', 'district')}): "
            f"{(pipe.get('current') or pipe.get('hook') or '')[:90]}"
        )

    if kind in ("talk", "ask_about", "personal_talk") and focal_npc_id:
        npc = (npcs or {}).get(focal_npc_id, {})
        role = npc.get("role", "stranger")
        lines.append(
            f"- This {kind} beat with the {role}: advance information, trust, or obstacle — not padding."
        )
    elif kind == "investigate":
        lines.append("- Investigation: evidence or contradiction tied to the pursuit above.")
    elif kind == "search" and ctx.get("acquired_item"):
        item = ctx["acquired_item"].get("name", "item")
        lines.append(f"- Item taken ({item}): state that early; hint what it enables.")
    elif kind == "find" and ctx.get("target_id") and not ctx.get("find_failed"):
        lines.append("- Person found: open on locating them — not on re-describing the district.")

    if not plot and len(lines) <= 1:
        lines.append(
            "- No active case yet: still advance character, place, or tension — not static description."
        )
    elif plot:
        lines.append("")
        lines.append(plot)

    return "\n".join(lines)
