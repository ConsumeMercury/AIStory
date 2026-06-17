"""
Journal retention — keep high-importance beats when trimming long campaigns.
"""

JOURNAL_CAP = 300
KEEP_RECENT = 40


def trim_journal(journal, *, cap=JOURNAL_CAP, keep_recent=KEEP_RECENT, player=None):
    """
    Drop low-importance older entries while preserving the most recent beats.
    Returns chronologically ordered journal.
    """
    if not journal or len(journal) <= cap:
        return list(journal or [])

    recent = list(journal[-keep_recent:])
    older = list(journal[:-keep_recent])
    keep_count = max(0, cap - len(recent))
    if keep_count <= 0:
        return recent[-cap:]

    from simulation.importance_router import score_journal_entry

    scored = [
        (score_journal_entry(entry, player=player), idx, entry)
        for idx, entry in enumerate(older)
    ]
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    keep_indices = {idx for _, idx, _ in scored[:keep_count]}
    kept_older = [entry for idx, entry in enumerate(older) if idx in keep_indices]
    return kept_older + recent
