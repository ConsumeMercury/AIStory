"""
Uniform post-generation gate — prose validation + declared fact validation.
"""

from simulation.narrator_facts import parse_narrator_facts, validate_narrator_facts
from simulation.prose_validator import (
    build_prose_correction_block,
    validate_scene_prose,
)


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
    Returns (issues, parsed_facts).
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
    fact_issues = validate_narrator_facts(
        facts, player, npcs, scene_state, action_ctx, focal_npc_id,
    )
    all_issues = list(prose_issues) + list(fact_issues)
    return all_issues, facts, prose_issues, fact_issues


def build_combined_correction_block(prose_issues, fact_issues):
    blocks = []
    if prose_issues:
        blocks.append(build_prose_correction_block(prose_issues))
    if fact_issues:
        from simulation.narrator_facts import build_fact_correction_block
        blocks.append(build_fact_correction_block(fact_issues))
    return "\n\n".join(b for b in blocks if b).strip()
