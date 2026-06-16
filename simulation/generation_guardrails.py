"""
Central checklist for narration guardrails — used in prompts and offline audits.
Keeps simulation facts and Gemini prose aligned.
"""

GUARDRAIL_RULES = (
    "FOCUS: Only the focal person in SCENE FACTS may speak with named dialogue.",
    "ABSENCE: If someone is absent, show empty result — no invented dialogue from them.",
    "LOCATION: Obey LOCATION LOCK — no teleporting to new buildings or districts.",
    "MOVEMENT: travel_failed or approach_failed means NO movement occurred.",
    "LOOT: Items and documents only if SCENE FACTS or inventory facts list them.",
    "CAST: NO FOCAL CHARACTER means no new named strangers with speeches.",
    "IDENTITY: Same NPC — same gender, role, and persona register every beat.",
    "PLAYER: Quote protagonist speech exactly once when given; never invent their lines.",
    "WITHDRAW: End exchange; clear focus after — do not continue old thread next beat unless player re-engages.",
    "TARGET: Role hints (priest, clerk, guard) override stale scene_focus.",
)


def guardrails_prompt_block():
    """Compact block appended to narrator context."""
    lines = ["GENERATION GUARDRAILS (simulation wins over improvisation):"]
    for rule in GUARDRAIL_RULES:
        lines.append(f"- {rule}")
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
    action = (ctx.get("action") or "").lower()

    if ctx.get("travel_failed") and focus_ids:
        warnings.append("travel_failed but cast still has focal NPCs")

    if kind == "investigate" and not target_id and focus_ids:
        warnings.append("investigate without target should have empty cast")

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
