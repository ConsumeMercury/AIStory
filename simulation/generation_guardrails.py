"""
Central checklist for narration guardrails — used in prompts and offline audits.
Keeps simulation facts and Gemini prose aligned.
"""

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
    "WITHDRAW: End exchange; clear focus after — do not continue old thread next beat unless player re-engages.",
    "TARGET: Role hints pick a matching NPC; keep scene_focus when that NPC fits the hint.",
)


def guardrails_prompt_block():
    """Compact block appended to narrator context."""
    lines = ["GENERATION GUARDRAILS (simulation wins over improvisation):"]
    for rule in GUARDRAIL_RULES:
        lines.append(f"- {rule}")
    return "\n".join(lines)


def build_hard_constraints_block(focal_npc_id, focal_npc, scene_place, action_context=None):
    """
    Final pre-write constraints — location, movement, and focal identity.
    Simulation passes these explicitly; the narrator must not re-derive them.
    """
    ctx = action_context or {}
    lines = ["HARD CONSTRAINTS (override everything above):"]
    if scene_place:
        lines.append(
            f"- LOCATION LOCK: {scene_place}. "
            "The protagonist is HERE — do NOT move them to another building or district."
        )
    if ctx.get("travel_failed") or ctx.get("approach_failed"):
        lines.append(
            "- NO MOVEMENT occurred this beat. Do NOT describe entering new rooms or traveling. "
            "Do NOT invent barred gates to a place named in prior narration. "
            "Do NOT repeat the focal NPC's last line — react to the stall or stay silent."
        )
    if ctx.get("target_ambiguous"):
        lines.append(
            "- TARGET UNCLEAR — no violence or directed dialogue toward a specific person. "
            "Protagonist must choose who they mean."
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

    if ctx.get("travel_failed") and focus_ids:
        warnings.append("travel_failed but cast still has focal NPCs")

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
