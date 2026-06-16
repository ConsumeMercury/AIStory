"""
Compact older journal beats into rolling summaries so long sessions stay bounded.
"""

JOURNAL_DETAIL_LIMIT = 50
SUMMARIZE_CHUNK = 15


def _entry_line(entry):
    action = (entry.get("action") or "")[:80]
    place = entry.get("place") or entry.get("location") or ""
    focus = entry.get("focus_npc") or ""
    day = entry.get("day")
    parts = [f"day {day}" if day else None, place, action]
    if focus:
        parts.append(f"focus={focus}")
    return " | ".join(p for p in parts if p)


def summarize_entries(entries):
    """Rule-based summary of a journal slice — no LLM."""
    if not entries:
        return ""
    lines = [_entry_line(e) for e in entries if e]
    lines = [ln for ln in lines if ln]
    if not lines:
        return ""
    first_day = entries[0].get("day")
    last_day = entries[-1].get("day")
    span = f"days {first_day}–{last_day}" if first_day and last_day and first_day != last_day else f"day {last_day or first_day or '?'}"
    return f"{span}: " + "; ".join(lines[:12]) + (f" (+{len(lines) - 12} more)" if len(lines) > 12 else "")


def maybe_compact_journal(player):
    """
    When journal exceeds JOURNAL_DETAIL_LIMIT, roll oldest SUMMARIZE_CHUNK entries
    into player['journal_summaries']. Returns True if player changed.
    """
    journal = player.get("journal") or []
    if len(journal) <= JOURNAL_DETAIL_LIMIT:
        return False

    chunk = journal[:SUMMARIZE_CHUNK]
    summary = summarize_entries(chunk)
    if summary:
        player.setdefault("journal_summaries", []).append(summary)
        player["journal_summaries"] = player["journal_summaries"][-20:]
    player["journal"] = journal[SUMMARIZE_CHUNK:]
    return True


def distant_context_block(player, *, max_summaries=3):
    """Short distant-history block for conversation ledger / continuity."""
    summaries = (player.get("journal_summaries") or [])[-max_summaries:]
    if not summaries:
        return ""
    body = "\n".join(f"- {s}" for s in summaries)
    return (
        "DISTANT HISTORY (already happened — do not replay):\n"
        f"{body}\n"
    )
