"""
Central checklist for narration guardrails — used in prompts and offline audits.
Keeps simulation facts and Gemini prose aligned.
"""

import re

from generation.descriptor_generator import short_descriptor

GUARDRAIL_RULES = (
    "FOCUS: Only the focal person in SCENE FACTS may speak with named dialogue.",
    "ABSENCE: If someone is absent, show empty result — no invented dialogue from them.",
    "LOCATION: Obey LOCATION LOCK — no teleporting to new buildings or districts.",
    "PLACES: Do not name specific go-to destinations (yards, cisterns, buildings) unless NAVIGABLE PLACES lists them.",
    "MOVEMENT: travel_failed or approach_failed means NO movement occurred.",
    "LOOT: Items and documents only if SCENE FACTS or inventory facts list them.",
    "CAST: NO FOCAL CHARACTER means no new named strangers with speeches.",
    "IDENTITY: Same NPC — same gender, role, and persona register every beat.",
    "PLAYER: Quote protagonist speech exactly once when given; never invent their lines.",
    "TIME: Do not promise specific bell tolls, auctions, or timed meetings unless SCHEDULED EVENTS lists them; when you commit to WHEN something happens, emit [SCHEDULE: id | label | +Nh] on its own line — vague deflection without a tag is not enough.",
    "FACTS: Declare simulation facts with stripped tags — [FACT: speaking | npc_id], [FACT: death | npc_id], [FACT: place | name] — using cast ids from SCENE FACTS only.",
    "WAIT: wait until/for targets advance simulation time — do not narrate time passing if WAIT REFUSED.",
    "WITHDRAW: End exchange; clear focus after — do not continue old thread next beat unless player re-engages.",
    "TARGET: Role hints pick a matching NPC; keep scene_focus when that NPC fits the hint.",
    "MISNAME: If the player uses the wrong name, the focal NPC corrects them — do not invent a third person.",
)


def guardrails_prompt_block():
    """Compact block appended to narrator context."""
    lines = ["GENERATION GUARDRAILS (simulation wins over improvisation):"]
    for rule in GUARDRAIL_RULES:
        lines.append(f"- {rule}")
    return "\n".join(lines)


def build_misname_directive(action, target_npc, npcs, target_id):
    """
    When player text names someone other than the resolved focal NPC,
    tell the narrator to have them push back — not invent reconciling characters.
    """
    if not action or not target_npc or not target_id:
        return ""
    focal_name = (target_npc.get("name") or "").strip()
    focal_first = focal_name.split()[0].lower() if focal_name else ""
    text_l = action.lower()
    wrong_names = []
    for nid, npc in (npcs or {}).items():
        if nid == target_id or npc.get("status") != "alive":
            continue
        name = (npc.get("name") or "").strip()
        if not name:
            continue
        first = name.split()[0].lower()
        if len(first) < 3 or first == focal_first:
            continue
        if re.search(rf"\b{re.escape(first)}\b", text_l):
            wrong_names.append(name)
    for token in re.findall(r"\bask\s+(?:the\s+)?([a-z]{3,})\b", text_l):
        if token in ("the", "her", "him", "why", "what", "how", "about"):
            continue
        role_l = (target_npc.get("role") or "").lower()
        occ_l = (target_npc.get("occupation") or "").lower()
        if focal_first and token != focal_first and token not in {role_l, *occ_l.split()}:
            if token.title() not in wrong_names:
                wrong_names.append(token.title())
    if not wrong_names:
        return ""
    label = focal_name or short_descriptor(target_npc)
    wrong = wrong_names[0]
    return (
        f"MISNAME GUARD: The player said \"{wrong}\" but the focal person is {label}. "
        f"They are NOT {wrong}. The focal NPC must correct the mistake or deflect — "
        f"do NOT invent a third character named {wrong} to reconcile the error."
    )


def build_hard_constraints_block(
    focal_npc_id, focal_npc, scene_place, action_context=None, present=None, npcs=None,
    world=None,
):
    """
    Final pre-write constraints — location, movement, and focal identity.
    Simulation passes these explicitly; the narrator must not re-derive them.
    """
    ctx = action_context or {}
    lines = ["HARD CONSTRAINTS (override everything above):"]
    if world:
        from simulation.world_integrity import expected_time_of_day
        hour = world.get("hour", 0)
        tod = expected_time_of_day(world)
        weather = world.get("weather") or "Clear"
        day = world.get("day", 1)
        lines.append(
            f"- TEMPORAL LOCK: Day {day}, hour {hour} ({tod}), weather {weather}. "
            "Atmosphere and lighting MUST match this — do NOT describe a different "
            "time of day (no dawn sun at deep night; no midnight hush at noon)."
        )
    if scene_place:
        lines.append(
            f"- LOCATION LOCK: {scene_place}. "
            "The protagonist is HERE — do NOT move them to another building or district."
        )
    if ctx.get("travel_failed") or ctx.get("approach_failed"):
        lines.append(
            "- NO MOVEMENT occurred this beat. Do NOT describe entering new rooms or traveling. "
            "Do NOT invent barred gates to a place named in prior narration. "
            "Do NOT swap in new named characters — same people as last beat."
        )
        if present:
            labels = [
                short_descriptor(n) for n in present[:8]
                if n.get("status") == "alive"
            ]
            if labels:
                lines.append(
                    "- STILL PRESENT (only these may be named): " + "; ".join(labels) + "."
                )
    if ctx.get("target_ambiguous"):
        lines.append(
            "- TARGET UNCLEAR — no violence or directed dialogue toward a specific person. "
            "Protagonist must choose who they mean."
        )
    if ctx.get("trade_refused"):
        lines.append(
            "- TRADE REFUSED — no coin spent, no goods acquired. "
            "Do NOT invent a vendor, price, or transaction."
        )
    if ctx.get("give_refused"):
        lines.append("- GIVE REFUSED — wealth unchanged.")
    if ctx.get("search_refused"):
        lines.append("- ACQUIRE REFUSED — nothing added to inventory.")
    if ctx.get("accuse_refused"):
        lines.append(
            "- ACCUSE REFUSED — no case verdict, no guilt confirmed. "
            "Resolve this beat only; do NOT continue prior accusation threads."
        )
    if ctx.get("wait_no_change"):
        lines.append(
            "- WAIT REFUSED — no time passed. Do NOT narrate dawn, bell tolls, or events firing. "
            "Do NOT repeat the prior NPC line verbatim."
        )
    if ctx.get("relocated"):
        lines.append(
            "- RELOCATION — prior conversation partner does NOT follow into this sub-place."
        )
        left = list(ctx.get("left_behind_cast") or [])
        if left:
            names = []
            for nid in left[:6]:
                npc = (npcs or {}).get(nid, {})
                names.append(npc.get("name") or nid)
            lines.append(
                "- LEFT BEHIND (must NOT speak or dominate this beat): "
                + ", ".join(names)
                + "."
            )
    if focal_npc_id and focal_npc:
        known_name = focal_npc.get("name")
        label = known_name or short_descriptor(focal_npc)
        role = (focal_npc.get("role") or "stranger").replace("_", " ")
        lines.append(
            f"- FOCAL PERSON THIS BEAT: id={focal_npc_id} | {label} ({role}) — "
            "the ONLY character who may speak with dialogue. "
            "The conversation ledger below applies to this same id."
        )
    else:
        lines.append(
            "- NO FOCAL PERSON this beat — no named NPC dialogue. "
            "Background crowd is faceless."
        )
    return "\n".join(lines)


def audit_capture_anomalies(capture, player, npcs):
    """
    Return list of human-readable warnings for a mocked generate_scene capture.
    Used by scripts/simulation_audit.py and generation_report.py.
    """
    warnings = []
    ctx = capture or {}
    kind = ctx.get("kind")
    target_id = ctx.get("target_id")
    focus_ids = ctx.get("focus_ids") or []
    focal_npc_id = ctx.get("focal_npc_id")
    ledger_focal_id = ctx.get("ledger_focal_id")
    action = (ctx.get("action") or "").lower()

    if focal_npc_id and focus_ids and focal_npc_id != focus_ids[0]:
        warnings.append(
            f"focal_npc_id {focal_npc_id!r} != present_npcs[0] {focus_ids[0]!r}"
        )

    if focal_npc_id and ledger_focal_id and focal_npc_id != ledger_focal_id:
        warnings.append(
            f"ledger built for {ledger_focal_id!r} but focal_npc_id is {focal_npc_id!r}"
        )

    if kind == "investigate" and (focus_ids or focal_npc_id or target_id):
        warnings.append("investigate must have empty cast and no target")

    if "priest" in action or "cleric" in action:
        if target_id and npcs:
            role = npcs.get(target_id, {}).get("role")
            if role and role != "priest" and "talk" in (kind or ""):
                warnings.append(f"player asked for priest but target role is {role!r}")

    if kind == "withdraw" and player.get("scene_focus"):
        warnings.append("withdraw should clear scene_focus")

    if kind == "ask_about" and "about" in action and "ask " in action:
        parts = action.split()
        if len(parts) >= 3 and parts[0] == "ask" and parts[2] == "about":
            if kind == "talk":
                warnings.append("named ask X about Y should be ask_about not talk")

    return warnings
