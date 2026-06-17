"""Tests for build-time LLM content validators (no API calls)."""

from generation.llm_content import (
    ai_worldgen_enabled,
    npc_batch_size,
    npc_enrich_limit,
    worldgen_parallel_workers,
    parse_json_response,
    unwrap_npc_batch_payload,
    validate_background_spec,
    validate_history_events,
    validate_npc_profile,
    validate_objective_spec,
    validate_persona_spec,
    validate_secrets_list,
    validate_storyline_spec,
)


def test_ai_worldgen_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AISTORY_AI_WORLDGEN", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert ai_worldgen_enabled() is False


def test_ai_worldgen_requires_api_key(monkeypatch):
    monkeypatch.setenv("AISTORY_AI_WORLDGEN", "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert ai_worldgen_enabled() is False


def test_worldgen_speed_defaults(monkeypatch):
    monkeypatch.delenv("AISTORY_AI_WORLDGEN_NPC_BATCH", raising=False)
    monkeypatch.delenv("AISTORY_AI_WORLDGEN_NPC_LIMIT", raising=False)
    monkeypatch.delenv("AISTORY_AI_WORLDGEN_WORKERS", raising=False)
    assert npc_batch_size() == 6
    assert npc_enrich_limit() == 20
    assert worldgen_parallel_workers() == 4


def test_select_npcs_for_enrichment_prioritizes_leaders():
    from generation.ai_worldgen import select_npcs_for_enrichment

    npcs = {
        f"n{i}": {"id": f"n{i}", "status": "alive", "name": f"Npc {i}"}
        for i in range(10)
    }
    institutions = {
        "guild": {"leader": "n1", "members": {"n1": "leader", "n2": "member"}},
    }
    picked = select_npcs_for_enrichment(npcs, institutions, limit=3)
    ids = {n["id"] for n in picked}
    assert "n1" in ids
    assert "n2" in ids
    assert len(picked) == 3


def test_parse_json_response_strips_fences():
    raw = '```json\n{"title": "Test", "theme": "intrigue", "hooks": ["a hook here"], "stages": ["a", "b", "c", "d", "e"]}\n```'
    data = parse_json_response(raw)
    assert data["title"] == "Test"


def test_validate_storyline_spec_accepts_good_payload():
    payload = {
        "title": "The Rotten Scale",
        "theme": "corruption",
        "hooks": ["Someone fixes the weights at dawn."],
        "stages": ["rumour", "accusation", "bribe", "witness", "reckoning"],
    }
    ok, cleaned, errors = validate_storyline_spec(payload)
    assert ok is True
    assert errors == []
    assert len(cleaned["stages"]) == 5
    assert cleaned["hook"] == payload["hooks"][0]


def test_validate_storyline_spec_accepts_institution_hook_field():
    payload = {
        "title": "The Rigged Examination",
        "theme": "academic",
        "hook": "Whispers say the coming examinations were sold before the questions were written.",
        "stages": ["rumours spread", "accusation at the steps", "guards look away", "ledgers clash", "reckoning"],
    }
    ok, cleaned, errors = validate_storyline_spec(payload)
    assert ok is True
    assert cleaned["hooks"] == [payload["hook"]]


def test_validate_storyline_spec_rejects_short_stages():
    payload = {
        "title": "Bad",
        "theme": "crime",
        "hooks": ["hook one"],
        "stages": ["only one"],
    }
    ok, cleaned, errors = validate_storyline_spec(payload)
    assert ok is False
    assert cleaned is None


def test_validate_history_events():
    events = [
        {"when": "Year 12", "official": "The guild charter was rewritten.", "folk": "They sold the city.", "rumor": "Coin changed hands."},
        {"when": "Year 11", "official": "A bridge collapsed.", "folk": "Saboteurs.", "rumor": "The captain knew."},
        {"when": "Year 10", "official": "Famine ended.", "folk": "Ships came late.", "rumor": "Grain was hoarded."},
    ]
    ok, cleaned, _ = validate_history_events(events)
    assert ok is True
    assert len(cleaned) == 3

    ok, cleaned, _ = validate_history_events({"events": events})
    assert ok is True
    assert len(cleaned) == 3


def test_validate_wrapped_payloads():
    ok, cleaned, _ = validate_secrets_list({"secrets": [{"text": "forged a partner's signature", "severity": "major"}]})
    assert ok is True

    ok, cleaned, _ = validate_objective_spec({"objective": {"text": "Find who shaved the caravan silver before the guild counts it."}})
    assert ok is True

    ok, _, _ = validate_persona_spec({"persona": {
        "speech_style": "clipped merchant cant",
        "voice_quirk": "counts coin while speaking",
        "core_value": "debts must be paid",
        "mood": "wary",
        "example_lines": ["Price is the price.", "Don't touch the scale."],
    }})
    assert ok is True

    batch = unwrap_npc_batch_payload({"profiles": [{"persona": {}, "background": {}}]})
    assert isinstance(batch, list)
    assert len(batch) == 1


def test_validate_persona_and_background():
    persona = {
        "speech_style": "clipped merchant cant",
        "voice_quirk": "counts coin while speaking",
        "core_value": "debts must be paid",
        "mood": "wary",
        "example_lines": ["Price is the price.", "Don't touch the scale."],
    }
    ok, _, _ = validate_persona_spec(persona)
    assert ok is True

    background = {
        "summary": "A dockside clerk who learned ledgers before letters and never forgot either.",
        "childhood": "Raised on pilings.",
        "formative_event": "Lost a brother to press-gangs.",
        "current_situation": "Keeps two sets of books.",
        "belief": "Coin is honest.",
        "secret": "Reports to the syndicate.",
        "mannerism": "Watches hands not faces.",
        "hope": "Leave before winter.",
    }
    ok, _, _ = validate_background_spec(background)
    assert ok is True


def test_validate_npc_profile_requires_appearance_lock():
    profile = {
        "persona": {
            "speech_style": "formal temple speech",
            "voice_quirk": "quotes scripture under breath",
            "core_value": " mercy is debt",
            "mood": "solemn",
            "example_lines": ["The dawn sees all.", "Kneel if you must speak."],
        },
        "background": {
            "summary": "An acolyte who survived a purge by naming the wrong priest and has not slept well since.",
            "childhood": "Orphaned at the steps.",
            "formative_event": "Survived a purge.",
            "current_situation": "Sweeps the nave.",
            "belief": "Silence saves.",
            "secret": "Shelters a deserter.",
            "mannerism": "Counts prayer beads.",
            "hope": "Absolution.",
        },
        "appearance_lock": "Pale, close-cropped hair, ash-grey eyes, a burn scar along the jaw.",
    }
    ok, cleaned, errors = validate_npc_profile(profile)
    assert ok is True
    assert cleaned["appearance_lock"].startswith("Pale")


def test_validate_objective_and_secrets():
    ok, cleaned, _ = validate_objective_spec({"text": "Find who shaved the caravan silver before the guild counts it."})
    assert ok is True
    assert cleaned["text"]

    ok, cleaned, _ = validate_secrets_list([{"text": "forged a partner's signature", "severity": "major"}])
    assert ok is True
    assert cleaned[0]["severity"] == "major"


def test_json_truncation_allows_brace_endings():
    from simulation.gemini_client import _looks_truncated_json

    assert _looks_truncated_json('{"title": "Test", "hooks": ["a"]}', None) is False
    assert _looks_truncated_json('[{"persona": {}}]', None) is False
    assert _looks_truncated_json('{"title": "Test"', None) is True


def test_json_truncation_accepts_complete_payload_on_max_tokens():
    from simulation.gemini_client import _looks_truncated_json

    class _Resp:
        candidates = [type("C", (), {"finish_reason": "MAX_TOKENS"})()]

    payload = (
        '{"kind":"talk","target_id":"g1","player_speech":"When?","time_target":null}'
    )
    assert _looks_truncated_json(payload, _Resp()) is False


def test_prose_truncation_ignores_trailing_fact_tags():
    from simulation.gemini_client import _looks_truncated

    raw = (
        "Rain slickens the greasy cobblestones of the market square, turning the discarded "
        "cabbage leaves into a slick paste that smells of wet wool and charred fat. "
        "She keeps her shoulder slightly turned, her posture alert to the silence of the empty market.\n"
        "[FACT: speaking | g1]"
    )
    assert _looks_truncated(raw, None) is False


def test_max_tokens_finish_with_clean_prose_not_truncated():
    from simulation.gemini_client import _looks_truncated

    class _Cand:
        finish_reason = "MAX_TOKENS"

    class _Resp:
        candidates = [_Cand()]

    visible = (
        "Rain slickens the greasy cobblestones of the market square, turning the discarded "
        "cabbage leaves into a slick paste that smells of wet wool and charred fat under the "
        "dripping eaves. She keeps her shoulder slightly turned, her posture alert to the "
        "silence of the empty market."
    )
    assert len(visible) >= 200
    assert _looks_truncated(visible, _Resp()) is False


def test_prose_truncation_still_flags_mid_sentence():
    from simulation.gemini_client import _looks_truncated

    assert _looks_truncated("The rain fell on the", None) is True
