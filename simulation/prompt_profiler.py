"""
Prompt profiler — estimate token contribution per narrator module.
"""

import logging
import os

log = logging.getLogger(__name__)


def _estimate_tokens(text):
    if not text:
        return 0
    return max(1, len(str(text)) // 4)


def profile_prompt_sections(sections, *, label="narrator"):
    """
    sections: list of (name, text) or dict name -> text
    Returns sorted list of {name, chars, est_tokens}.
    """
    if isinstance(sections, dict):
        items = list(sections.items())
    else:
        items = list(sections)

    rows = []
    for name, text in items:
        if not text:
            continue
        s = str(text).strip()
        rows.append({
            "name": name,
            "chars": len(s),
            "est_tokens": _estimate_tokens(s),
        })
    rows.sort(key=lambda r: r["est_tokens"], reverse=True)
    total = sum(r["est_tokens"] for r in rows)

    if os.environ.get("AISTORY_DEBUG_TOKENS", "").lower() in ("1", "true", "yes"):
        parts = [f"{r['name']}={r['est_tokens']}" for r in rows[:12]]
        log.info("Prompt profile (%s): total~%s | %s", label, total, ", ".join(parts))

    return rows, total


def format_profile_summary(rows, total):
    if not rows:
        return ""
    lines = [f"Prompt modules (~{total} tokens est.):"]
    for r in rows[:10]:
        lines.append(f"- {r['name']}: ~{r['est_tokens']}")
    return "\n".join(lines)
