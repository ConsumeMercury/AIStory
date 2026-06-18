"""
Validator chain registry — who checks what, and boundary trace summary.
"""

VALIDATOR_REGISTRY = (
    {"name": "prose_validator", "module": "prose_validator", "mode": "hard", "gates_regen": True},
    {"name": "narrator_facts", "module": "narrator_facts", "mode": "hard", "gates_regen": True},
    {"name": "prose_assertion_guard", "module": "prose_assertion_guard", "mode": "hard", "gates_regen": True},
    {"name": "fact_gate", "module": "fact_gate", "mode": "hard", "gates_regen": True},
    {"name": "prose_auditor", "module": "prose_auditor", "mode": "shadow|on", "gates_regen": True},
    {"name": "narrative_trace", "module": "narrative_trace", "mode": "soft", "gates_regen": True},
    {"name": "directive_validator", "module": "directive_validator", "mode": "arbitrate", "gates_regen": False},
    {"name": "regen_governor", "module": "regen_governor", "mode": "budget", "gates_regen": False},
)


def build_validator_chain_trace(
    *,
    prose_issues=None,
    fact_issues=None,
    auditor_issues=None,
    narrative_issues=None,
    action_ctx=None,
):
    """Compact per-turn validator output for boundary trace."""
    ctx = action_ctx or {}
    auditor = ctx.get("boundary_auditor") or {}
    regen = ctx.get("regen_governor") or {}
    chain = [
        {
            "name": "prose_validator",
            "issues": len(prose_issues or []),
            "mode": "hard",
        },
        {
            "name": "narrator_facts",
            "issues": len(fact_issues or []),
            "mode": "hard",
        },
        {
            "name": "prose_auditor",
            "issues": len(auditor_issues or []),
            "mode": auditor.get("mode", "off"),
            "invoked": bool(auditor.get("invoked")),
            "confirmed": auditor.get("confirmed", 0),
        },
        {
            "name": "narrative_trace",
            "issues": len(narrative_issues or []),
            "mode": ctx.get("narrative_regen_mode", "soft"),
        },
        {
            "name": "regen_governor",
            "attempt": regen.get("attempt", 0),
            "exhausted": bool(regen.get("exhausted")),
            "top_priority": regen.get("top_priority", 0),
        },
    ]
    if ctx.get("directive_conflicts"):
        chain.append({
            "name": "directive_validator",
            "issues": len(ctx["directive_conflicts"]),
            "mode": "arbitrate",
        })
    return chain
