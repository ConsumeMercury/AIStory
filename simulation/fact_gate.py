"""
Uniform post-generation gate — regex prose + structured facts + AI auditor nominations.
"""

from simulation.narrator_facts import (
    dialogue_place_fact_gap,
    parse_narrator_facts,
    validate_narrator_facts,
)
from simulation.prose_validator import (
    build_prose_correction_block,
    validate_scene_prose,
)
from simulation.prose_auditor import run_prose_audit
from simulation.regen_governor import dedupe_issues
from simulation.boundary_metrics import (
    MISSING_FACTS_ISSUE,
    facts_missing_for_beat,
    summarize_fact_emission,
)
from simulation.scheduled_events import extract_event_promises, parse_schedule_tags


def validate_schedule_emission(text):
    """Flag WHEN commitments captured by regex but missing structured [SCHEDULE] tag."""
    if not text:
        return None
    promises = extract_event_promises(text)
    tags = parse_schedule_tags(text)
    if promises and not tags:
        labels = ", ".join(p.get("label", p.get("id", "?")) for p in promises[:3])
        return (
            f"timed event promised in prose ({labels}) "
            "but no [SCHEDULE: event_id | label | +Nh] tag emitted"
        )
    return None


def validate_turn_output(
    text,
    *,
    player,
    npcs,
    action_ctx,
    focal_npc_id,
    scene_place,
    present_npcs,
    known_ids=None,
    scene_state=None,
):
    """
    Combined validation for narrator output.
    Returns (all_issues, facts, prose_issues, fact_issues, auditor_issues, auditor_meta).
    """
    prose_issues = validate_scene_prose(
        text,
        player=player,
        npcs=npcs,
        action_ctx=action_ctx,
        focal_npc_id=focal_npc_id,
        scene_place=scene_place,
        present_npcs=present_npcs,
        known_ids=known_ids,
    )
    facts = parse_narrator_facts(text)
    emission = summarize_fact_emission(facts)
    fact_issues = validate_narrator_facts(
        facts, player, npcs, scene_state, action_ctx, focal_npc_id,
    )
    if facts_missing_for_beat((action_ctx or {}).get("kind"), action_ctx, facts, emission):
        fact_issues = list(fact_issues) + [MISSING_FACTS_ISSUE]
    schedule_issue = validate_schedule_emission(text)
    if schedule_issue:
        fact_issues = list(fact_issues) + [schedule_issue]
    place_gap = dialogue_place_fact_gap(text, facts)
    if place_gap:
        fact_issues = list(fact_issues) + [place_gap]

    from simulation.prose_assertion_guard import validate_prose_assertions
    assertion_issues = validate_prose_assertions(
        text,
        player=player,
        npcs=npcs,
        action_ctx=action_ctx,
        focal_npc_id=focal_npc_id,
        present_npcs=present_npcs,
        known_ids=known_ids,
        facts=facts,
        scene_state=scene_state,
        world=(scene_state and {
            "hour": scene_state.hour,
            "day": scene_state.day,
            "time_of_day": scene_state.time_of_day,
        }) or None,
    )
    if action_ctx and action_ctx.get("inventory_missing"):
        labels = ", ".join(action_ctx["inventory_missing"][:3])
        assertion_issues = list(assertion_issues) + [
            f"action references missing inventory ({labels}) — prose must not show protagonist holding it"
        ]
    if assertion_issues:
        prose_issues = list(prose_issues) + assertion_issues

    auditor_confirmed, auditor_meta = run_prose_audit(
        text,
        player=player,
        npcs=npcs,
        scene_state=scene_state,
        action_ctx=action_ctx,
        focal_npc_id=focal_npc_id,
        scene_place=scene_place,
        present_npcs=present_npcs,
    )

    if action_ctx is not None:
        action_ctx["boundary_auditor"] = auditor_meta

    all_issues = dedupe_issues(
        list(prose_issues) + list(fact_issues) + list(auditor_confirmed),
    )
    return all_issues, facts, prose_issues, fact_issues, auditor_confirmed, auditor_meta


def build_auditor_correction_block(auditor_issues):
    if not auditor_issues:
        return ""
    lines = [
        "AUDITOR CONFIRMED VIOLATIONS (rewrite — do not invent speakers, places, or items):",
    ]
    for issue in auditor_issues[:6]:
        lines.append(f"- {issue}")
    return "\n".join(lines)


def build_combined_correction_block(prose_issues, fact_issues, auditor_issues=None):
    blocks = []
    if prose_issues:
        blocks.append(build_prose_correction_block(prose_issues))
    if fact_issues:
        from simulation.narrator_facts import build_fact_correction_block
        blocks.append(build_fact_correction_block(fact_issues))
    if auditor_issues:
        blocks.append(build_auditor_correction_block(auditor_issues))
    return "\n\n".join(b for b in blocks if b).strip()
