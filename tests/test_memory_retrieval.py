"""Memory retrieval — keyword and journal candidates."""

from simulation.memory_retrieval import (
    get_relevant_memories,
    player_relevant_events,
)


def test_player_relevant_events_filters_tick_noise():
    events = [
        {"type": "player_action", "actor": "player", "action": "investigate seals", "id": "e1"},
        {"type": "npc_tick", "actor": "npc_x", "action": "walked", "id": "e2"},
    ]
    assert len(player_relevant_events(events)) == 1


def test_keyword_retrieval_matches_shared_words():
    events = [
        {"type": "player_action", "actor": "player", "action": "ask about forgery", "id": "e1"},
        {"type": "player_action", "actor": "player", "action": "look around market", "id": "e2"},
    ]
    hits = get_relevant_memories(events, "investigate the forgery ring", limit=2)
    assert hits
    assert hits[0].get("action", "").find("forgery") >= 0 or "forgery" in hits[0].get("action", "")


def test_journal_summary_candidate_retrieval():
    player = {
        "journal_summaries": [
            {"text": "Andrew learned about counterfeit lodge seals in the market.", "source": "rule"},
        ],
        "journal": [],
    }
    events = []
    hits = get_relevant_memories(events, "ask about the counterfeit seal", limit=3, player=player)
    assert hits
    assert "counterfeit" in hits[0].get("action", "").lower()
