"""Context curation — rumor ranking for narrator."""

from simulation.context_curation import rank_rumors_for_narrator, score_rumor_relevance


def test_score_rumor_boosts_focal_npc_name():
    player = {"location": "stormbridge", "area": "stormbridge:docks"}
    rumor = {"text": "Whispers say Bessa knows where the ledger went.", "spread": 10}
    npcs = {"b1": {"name": "Bessa"}}
    score = score_rumor_relevance(rumor, player=player, focal_npc_id="b1", npcs=npcs)
    assert score > 30


def test_rank_prefers_relevant_over_recent():
    player = {
        "location": "stormbridge",
        "area": "stormbridge:docks",
        "starting_pipeline": {
            "area_id": "stormbridge:docks",
            "title": "Ledger Smuggling",
            "stage": 0,
            "stages": ["hook"],
        },
    }
    rumors = [
        {"text": "Rain again in the northern hills.", "spread": 99},
        {"text": "Merchants whisper about ledger smuggling at the docks.", "spread": 20},
        {"text": "Someone saw a cat.", "spread": 50},
    ]
    ranked = rank_rumors_for_narrator(rumors, player=player, kind="explore", limit=2)
    assert len(ranked) == 2
    assert any("ledger" in (r.get("text") or "").lower() for r in ranked)
