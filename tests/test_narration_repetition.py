"""Regressions for recycled NPC dialogue across consecutive beats."""

from simulation.narrative_continuity import find_repeated_prior_content
from simulation.narrator_variety import build_avoid_repeating
from simulation.prose_validator import validate_scene_prose


def test_find_repeated_prior_content_flags_verbatim_quote():
    player = {
        "known_npcs": {
            "m1": {
                "prior_lines": [
                    '"The watch does not come to this corner after midnight," she says.',
                ],
            },
        },
    }
    text = (
        'She leans in. "The watch does not come to this corner after midnight," '
        "she says, smiling."
    )
    issue = find_repeated_prior_content(text, player, "m1")
    assert issue
    assert "prior" in issue.lower()


def test_build_avoid_repeating_bans_dialogue_from_full_scene():
    journal = [{
        "action": "look around",
        "excerpt": "Your fingers brush cold iron.",
        "scene": (
            "Your fingers brush cold iron. "
            '"The watch does not come to this corner after midnight," she says. '
            '"A useful thing to remember, hum?"'
        ),
    }]
    block = build_avoid_repeating(journal)
    assert "FORBIDDEN VERBATIM LINES" in block
    assert "useful thing to remember" in block.lower()


def test_validate_scene_prose_flags_repeated_prior_line():
    player = {
        "known_npcs": {
            "m1": {
                "prior_lines": ['"A useful thing to remember, hum?"'],
            },
        },
        "journal": [],
        "scene_focus": "m1",
    }
    npcs = {"m1": {"id": "m1", "role": "merchant", "gender": "female", "name": "Sera"}}
    text = (
        "She watches the lane. "
        '"A useful thing to remember, hum?" she murmurs, unchanged.'
    )
    issues = validate_scene_prose(
        text,
        player=player,
        npcs=npcs,
        action_ctx={"kind": "ask_about", "target_id": "m1"},
        focal_npc_id="m1",
        scene_place="High Quarter",
        present_npcs=[npcs["m1"]],
    )
    assert any("repeated prior" in i.lower() or "echoed prior" in i.lower() for i in issues)
