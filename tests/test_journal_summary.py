from simulation.journal_summary import (
    JOURNAL_DETAIL_LIMIT,
    distant_context_block,
    maybe_compact_journal,
    summarize_entries,
)


def _entry(day, action, place="Dock", focus="n1"):
    return {"day": day, "action": action, "place": place, "focus_npc": focus}


def test_summarize_entries_joins_actions():
    summary = summarize_entries([_entry(1, "look around"), _entry(1, "talk to priest")])
    assert "look around" in summary
    assert "talk to priest" in summary


def test_maybe_compact_journal_rolls_old_beats():
    player = {
        "journal": [_entry(i, f"action {i}") for i in range(JOURNAL_DETAIL_LIMIT + 5)],
        "journal_summaries": [],
    }
    changed = maybe_compact_journal(player)
    assert changed is True
    assert len(player["journal"]) < JOURNAL_DETAIL_LIMIT + 5
    assert player["journal_summaries"]


def test_distant_context_block_includes_summaries():
    player = {"journal_summaries": ["days 1–3: look around; talk"]}
    block = distant_context_block(player)
    assert "DISTANT HISTORY" in block
    assert "look around" in block
