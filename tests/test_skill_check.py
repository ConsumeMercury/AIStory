"""Skill check math — pure logic, no Gemini."""

from unittest.mock import patch

from simulation.skill_check import resolve_check


def test_resolve_check_success_on_high_roll():
    player = {
        "skills": {"persuasion": {"level": 8, "xp": 200}},
        "stats": {"attributes": {"presence": 14}, "stress": 0},
    }
    with patch("simulation.skill_check.random.randint", return_value=18):
        check = resolve_check(player, "persuasion", 5)
    assert check["success"] is True
    assert check["margin"] >= 0


def test_resolve_check_failure_on_low_roll():
    player = {
        "skills": {"persuasion": {"level": 1, "xp": 25}},
        "stats": {"attributes": {"presence": 8}, "stress": 0},
    }
    with patch("simulation.skill_check.random.randint", return_value=3):
        check = resolve_check(player, "persuasion", 18)
    assert check["success"] is False
