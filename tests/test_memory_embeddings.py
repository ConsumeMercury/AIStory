"""Semantic memory embedding model and circuit breaker."""

import simulation.memory_embeddings as mem


def test_default_embed_model_is_gemini_embedding():
    assert mem.EMBED_MODEL == "gemini-embedding-001"


def test_semantic_memory_disabled_after_not_found():
    mem._embed_disabled_reason = "404 NOT_FOUND"
    try:
        assert mem.semantic_memory_enabled() is False
    finally:
        mem._embed_disabled_reason = None


def test_wrong_speaker_skips_focal_name_duplicate():
    from simulation.prose_validator import wrong_speaker_dialogue

    npcs = {
        "f1": {"id": "f1", "name": "Aevex Vaelith"},
        "ghost": {"id": "ghost", "name": "Aevex Vaelith", "status": "dead"},
    }
    present = [{"id": "f1", "name": "Aevex Vaelith"}]
    text = '"What is your name?" Aevex Vaelith said quietly.'
    issue = wrong_speaker_dialogue(text, "f1", present, npcs)
    assert issue is None
