"""Generation settings and narrative continuity."""

from simulation.gemini_client import effective_sampling_params, model_family
from simulation.novel_craft import (
    TEMPERATURE_BY_KIND,
    frequency_penalty_for_kind,
    temperature_for_kind,
)
from simulation.narrative_continuity import (
    build_narrative_continuity_block,
    extract_dialogue_lines,
    extract_descriptor_sentences,
    update_npc_narrative_cache,
)


def test_temperature_lower_for_fact_sensitive_beats():
    assert temperature_for_kind("attack") < temperature_for_kind("explore")
    assert temperature_for_kind("ask_name") < temperature_for_kind("travel")
    assert temperature_for_kind("confess") <= 0.65


def test_frequency_penalty_higher_for_atmosphere_beats():
    assert frequency_penalty_for_kind("explore") > frequency_penalty_for_kind("attack")
    assert frequency_penalty_for_kind("ask_name") < frequency_penalty_for_kind("talk")


def test_model_family_detection():
    assert model_family("gemini-3.5-flash") == "3"
    assert model_family("gemini-2.5-flash") == "2.5"
    assert model_family("gemini-2.0-flash") == "2.0"


def test_frequency_penalty_gated_off_25_and_3():
    for model in ("gemini-3.5-flash", "gemini-2.5-flash", "gemini-3-flash-preview"):
        eff = effective_sampling_params(model, temperature=0.8, top_p=0.9, frequency_penalty=0.35)
        assert eff["temperature"] == 0.8
        assert eff["frequency_penalty"] is None


def test_frequency_penalty_sent_on_20():
    eff = effective_sampling_params("gemini-2.0-flash", temperature=0.8, frequency_penalty=0.35)
    assert eff["frequency_penalty"] == 0.35


def test_extract_dialogue_lines_skips_player_speech():
    scene = '"What is your name?"\n\nShe paused. "Fahir al-Zahir," she said.'
    lines = extract_dialogue_lines(scene, skip_lines=["What is your name?"], limit=2)
    assert any("Fahir" in ln for ln in lines)


def test_extract_descriptor_sentences_finds_physical_claims():
    scene = (
        "Fahir al-Zahir shifts her weight. Her fingers, scarred from old bowstring bites, "
        "twitch toward her belt."
    )
    found = extract_descriptor_sentences(scene, "Fahir al-Zahir", limit=2)
    assert found
    assert any("bowstring" in f or "finger" in f.lower() for f in found)


def test_update_npc_narrative_cache_stores_lines_and_details():
    player = {"known_npcs": {}}
    npcs = {"f1": {"id": "f1", "name": "Fahir al-Zahir"}}
    scene = (
        'Fahir al-Zahir\'s fingers, scarred from old bowstring bites, still. '
        '"The market is full of meat that never ran on four legs," she says.'
    )
    changed = update_npc_narrative_cache(
        player, "f1", scene, npcs, player_speech=None,
    )
    assert changed
    rec = player["known_npcs"]["f1"]
    assert rec.get("prior_lines")
    assert rec.get("established_details")


def test_narrative_block_includes_no_reestablishment():
    from simulation.narrative_continuity import build_narrative_continuity_block

    player = {
        "discovered_areas": {"ashmoor:market": {"visits": 3}},
        "known_npcs": {"f1": {"name_known": True, "prior_lines": ['"Flat and measured."']}},
        "journal": [{"kind": "talk", "focus_npc": "f1", "area": "ashmoor:market"}] * 4,
    }
    block = build_narrative_continuity_block(
        player, player["journal"], "f1", {"f1": {"name": "Fahir al-Zahir"}},
        known_ids={"f1"}, area_id="ashmoor:market", action_kind="talk",
    )
    assert "NO RE-ESTABLISHMENT" in block
    assert "ESTABLISHED PLACE" in block
    assert "HARD BAN" in block
    assert "PRIOR DIALOGUE" in block
    assert "ESTABLISHED PERSON" in block
