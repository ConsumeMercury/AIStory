"""
Compact older journal beats into rolling summaries so long sessions stay bounded.

Rule-based summaries are always available. When Gemini is configured,
compaction can optionally produce a narrative paragraph (see memory_embeddings).
"""

import logging

from simulation.memory_embeddings import (
    llm_journal_summary_enabled,
    semantic_memory_enabled,
    store_vector,
)

log = logging.getLogger(__name__)

JOURNAL_DETAIL_LIMIT = 50
SUMMARIZE_CHUNK = 15
MAX_SUMMARY_RECORDS = 20


def _entry_line(entry, npcs=None):
    action = (entry.get("action") or "")[:80]
    place = entry.get("place") or entry.get("location") or ""
    focus = entry.get("focus_npc") or ""
    if focus and npcs:
        name = (npcs.get(focus) or {}).get("name")
        if name:
            focus = name
    day = entry.get("day")
    parts = [f"day {day}" if day else None, place, action]
    if focus:
        parts.append(f"focus={focus}")
    return " | ".join(p for p in parts if p)


def _summary_text(record):
    if isinstance(record, dict):
        return record.get("text") or ""
    return str(record or "")


def _normalize_summaries(raw):
    out = []
    for item in raw or []:
        if isinstance(item, dict) and item.get("text"):
            out.append(item)
        elif isinstance(item, str) and item.strip():
            out.append({"text": item.strip(), "source": "rule"})
    return out


def summarize_entries(entries, *, npcs=None):
    """Rule-based summary of a journal slice — no LLM."""
    if not entries:
        return ""
    lines = [_entry_line(e, npcs) for e in entries if e]
    lines = [ln for ln in lines if ln]
    if not lines:
        return ""
    first_day = entries[0].get("day")
    last_day = entries[-1].get("day")
    span = (
        f"days {first_day}–{last_day}"
        if first_day and last_day and first_day != last_day
        else f"day {last_day or first_day or '?'}"
    )
    body = "; ".join(lines[:12]) + (f" (+{len(lines) - 12} more)" if len(lines) > 12 else "")
    return f"{span}: {body}"


def _beats_for_llm(entries, npcs=None):
    lines = []
    for e in entries:
        if not e:
            continue
        tick = e.get("tick", "?")
        action = (e.get("action") or "")[:100]
        excerpt = (e.get("excerpt") or e.get("scene") or "")[:180]
        focus = e.get("focus_npc")
        focus_name = ""
        if focus and npcs:
            focus_name = (npcs.get(focus) or {}).get("name") or focus
        bit = f"Tick {tick}: {action}"
        if focus_name:
            bit += f" (with {focus_name})"
        if excerpt:
            bit += f" — {excerpt}"
        lines.append(bit)
    return lines


def summarize_entries_llm(entries, player, npcs):
    """One narrative paragraph via Gemini; falls back to rule-based."""
    if not llm_journal_summary_enabled():
        return summarize_entries(entries, npcs=npcs), "rule"

    from simulation.plot_summary import build_plot_summary
    from simulation.gemini_client import generate_text

    plot_ctx = build_plot_summary(player, npcs, present_ids=[])
    beats = _beats_for_llm(entries, npcs)
    if not beats:
        return "", "rule"

    prompt = (
        "Summarize these story beats in ONE paragraph (3–5 sentences).\n"
        "Preserve: who was met, what was learned, plot threads, suspects, discoveries.\n"
        "Do NOT replay prose verbatim. Facts and meaning only.\n\n"
        f"Structured context:\n{plot_ctx or '(none)'}\n\n"
        "Beats:\n" + "\n".join(beats[:SUMMARIZE_CHUNK])
    )
    try:
        text = generate_text(prompt, temperature=0.4, top_p=0.9, max_tokens=512)
        if text and len(text.strip()) > 40:
            return text.strip(), "llm"
    except Exception as e:
        log.warning("LLM journal summary failed: %s", e)
    return summarize_entries(entries, npcs=npcs), "rule"


def maybe_compact_journal(player, npcs=None):
    """
    When journal exceeds JOURNAL_DETAIL_LIMIT, roll oldest SUMMARIZE_CHUNK entries
    into player['journal_summaries']. Returns True if player changed.
    """
    journal = player.get("journal") or []
    if len(journal) <= JOURNAL_DETAIL_LIMIT:
        return False

    chunk = journal[:SUMMARIZE_CHUNK]
    npcs = npcs or {}
    text, source = summarize_entries_llm(chunk, player, npcs)
    if not text:
        text = summarize_entries(chunk, npcs=npcs)
        source = "rule"
    if not text:
        player["journal"] = journal[SUMMARIZE_CHUNK:]
        return True

    tick_from = chunk[0].get("tick")
    tick_to = chunk[-1].get("tick")
    record = {
        "text": text,
        "source": source,
        "tick_from": tick_from,
        "tick_to": tick_to,
    }
    summaries = _normalize_summaries(player.get("journal_summaries"))
    summaries.append(record)
    player["journal_summaries"] = summaries[-MAX_SUMMARY_RECORDS:]

    if semantic_memory_enabled():
        key = f"summary:{tick_from}-{tick_to}"
        store_vector(player, key, text, meta={"kind": "journal_summary", "ticks": [tick_from, tick_to]})
        record["vector_key"] = key

    player["journal"] = journal[SUMMARIZE_CHUNK:]
    return True


def normalize_summaries(raw):
    return _normalize_summaries(raw)


def distant_context_block(player, *, max_summaries=3):
    """Short distant-history block for conversation ledger / continuity."""
    summaries = _normalize_summaries(player.get("journal_summaries"))[-max_summaries:]
    if not summaries:
        return ""
    lines = []
    for s in summaries:
        src = s.get("source", "rule")
        tag = " [narrative summary]" if src == "llm" else ""
        lines.append(f"- {_summary_text(s)}{tag}")
    body = "\n".join(lines)
    return (
        "DISTANT HISTORY (already happened — do not replay):\n"
        f"{body}\n"
    )


def recent_journal_block(player, *, max_beats=8):
    """Verbatim recent beats for prompt memory (newest last)."""
    journal = player.get("journal") or []
    if not journal:
        return ""
    lines = []
    for entry in journal[-max_beats:]:
        action = (entry.get("action") or "")[:80]
        place = entry.get("place") or entry.get("location") or "?"
        day = entry.get("day", "?")
        excerpt = (entry.get("excerpt") or "")[:160]
        line = f"- day {day} @ {place}: {action}"
        if excerpt:
            line += f" — {excerpt}"
        lines.append(line)
    return "RECENT BEATS (continuity — do not replay verbatim):\n" + "\n".join(lines)
