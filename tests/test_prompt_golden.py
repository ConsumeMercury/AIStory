"""Golden snapshot of prompt assembly — catches section-order regressions."""

import re
from pathlib import Path

import pytest

from simulation.generation_guardrails import build_hard_constraints_block
from simulation.narrator import assemble_scene_prompt

FIXTURE = Path(__file__).parent / "fixtures" / "golden_talk_prompt_sections.txt"


def _npc(nid, role="priest", name="Father Hale"):
    return {"id": nid, "name": name, "role": role, "gender": "male", "status": "alive", "age": 45}


def _normalize_prompt(prompt):
    text = prompt
    text = re.sub(r"day \d+", "day N", text)
    text = re.sub(r"hour \d+", "hour N", text)
    text = re.sub(r"tick \d+", "tick N", text)
    return text.strip()


@pytest.fixture
def golden_sections():
    return [
        line.strip()
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_prompt_assembly_golden_sections(golden_sections):
    npc = _npc("p1")
    player = {
        "journal": [],
        "known_npcs": {"p1": {"name_known": True}},
        "area": "city:temple",
        "location": "city",
        "name": "Test",
        "age": 30,
        "background": "wanderer",
        "appearance": "plain coat",
    }
    world = {
        "world_name": "TestWorld",
        "day": 1,
        "time_of_day": "night",
        "season": "winter",
        "weather": "Clear",
        "hour": 20,
    }
    hard = build_hard_constraints_block("p1", npc, "Temple Row — the heavy door", {"kind": "talk"})

    prompt, token_budget, focal_id = assemble_scene_prompt(
        "Talk to the priest",
        world,
        player,
        [npc],
        memories=[],
        action_context={"kind": "talk"},
        known_ids={"p1"},
        focal_npc_id="p1",
        scene_place="Temple Row — the heavy door",
        hard_constraints=hard,
        tick=0,
    )

    assert focal_id == "p1"
    assert token_budget > 0
    normalized = _normalize_prompt(prompt)

    pos = 0
    for section in golden_sections:
        idx = normalized.find(section, pos)
        assert idx >= pos, f"missing or out-of-order section: {section!r}"
        pos = idx + len(section)

    assert normalized.strip().endswith("DO NOT REPEAT.")
