"""
Token budget and eviction for narrator memory sections.

Approximate token count uses chars/4 (good enough for trimming).
"""

import os

CHARS_PER_TOKEN = 4

# (slot_name, max_tokens, trim_priority) — lower priority number = evict first
MEMORY_SLOTS = (
    ("retrieved_events", 300, 1),
    ("focal_npc_memory", 200, 2),
    ("distant_history", 400, 3),
    ("recent_journal", 800, 4),
    ("narrative_memory", 250, 5),
    ("plot_summary", 400, 6),
)

TOTAL_MEMORY_BUDGET = sum(s[1] for s in MEMORY_SLOTS)


def estimate_tokens(text):
    if not text:
        return 0
    return max(1, len(str(text)) // CHARS_PER_TOKEN)


def memory_budget_enabled():
    return os.environ.get("AISTORY_SKIP_MEMORY_BUDGET", "").lower() not in ("1", "true", "yes")


def apply_memory_budget(sections, *, total_cap=None, pin_slots=None):
    """
    Trim memory sections to per-slot and optional total caps.

    sections: dict slot_name -> str (may be empty)
    pin_slots: slot names that must not be dropped entirely (may still truncate last)
    Returns (trimmed_sections, evictions) where evictions is a list of human-readable notes.
    """
    if not memory_budget_enabled():
        return dict(sections), []

    pin_slots = frozenset(pin_slots or ())
    caps = {name: cap for name, cap, _ in MEMORY_SLOTS}
    total_cap = total_cap or TOTAL_MEMORY_BUDGET
    trimmed = {k: (v or "") for k, v in sections.items()}
    evictions = []

    # Per-slot hard caps (truncate from end — oldest detail usually at start of block)
    for name, cap, _prio in sorted(MEMORY_SLOTS, key=lambda x: x[2]):
        text = trimmed.get(name, "")
        if estimate_tokens(text) <= cap:
            continue
        max_chars = cap * CHARS_PER_TOKEN
        trimmed[name] = text[:max_chars].rsplit("\n", 1)[0] if "\n" in text[:max_chars] else text[:max_chars]
        if trimmed[name] != text:
            evictions.append(f"{name}: trimmed to ~{cap} tokens")

    # Total cap — evict lowest-priority slots entirely, then trim survivors
    def total_used():
        return sum(estimate_tokens(trimmed.get(n, "")) for n, _, _ in MEMORY_SLOTS)

    if total_used() <= total_cap:
        return trimmed, evictions

    for name, cap, _prio in sorted(MEMORY_SLOTS, key=lambda x: x[2]):
        if total_used() <= total_cap:
            break
        if name in pin_slots:
            continue
        if trimmed.get(name):
            evictions.append(f"{name}: dropped for total memory budget")
            trimmed[name] = ""

    for name, cap, _prio in sorted(MEMORY_SLOTS, key=lambda x: x[2], reverse=True):
        if total_used() <= total_cap:
            break
        if name in pin_slots and trimmed.get(name):
            continue
        text = trimmed.get(name, "")
        if not text:
            continue
        over = total_used() - total_cap
        if over <= 0:
            break
        drop_chars = over * CHARS_PER_TOKEN
        if len(text) <= drop_chars:
            trimmed[name] = ""
            evictions.append(f"{name}: cleared for total budget")
        else:
            trimmed[name] = text[drop_chars:].lstrip()
            evictions.append(f"{name}: shortened for total budget")

    return trimmed, evictions


def format_memory_debug(sections, evictions):
    """Debug payload for turn trace / UI."""
    used = {name: estimate_tokens(sections.get(name, "")) for name, _, _ in MEMORY_SLOTS}
    return {
        "tokens_used": used,
        "tokens_cap": {name: cap for name, cap, _ in MEMORY_SLOTS},
        "total_used": sum(used.values()),
        "total_cap": TOTAL_MEMORY_BUDGET,
        "evictions": evictions,
    }
