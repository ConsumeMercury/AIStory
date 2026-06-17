"""
Regeneration budget governor — prioritize violations, dedupe, circuit breaker.
"""

import os
import re

# Higher = worth spending a regen attempt on.
VIOLATION_PRIORITY = {
    "death": 100,
    "corpse": 100,
    "fact death": 95,
    "auditor confirmed: dead": 95,
    "living npc": 90,
    "speaker": 85,
    "auditor confirmed: speaker": 85,
    "dialogue": 80,
    "absent npc": 80,
    "location lock": 75,
    "prose moves toward": 75,
    "auditor confirmed: place": 70,
    "inventory": 65,
    "auditor confirmed: item": 65,
    "movement": 60,
    "focal npc not": 50,
    "investigate beat": 40,
    "too short": 10,
}


def max_regen_attempts():
    raw = os.environ.get("AISTORY_PROSE_RETRIES", "1")
    try:
        return max(0, min(3, int(raw)))
    except ValueError:
        return 1


def min_priority_for_regen():
    raw = os.environ.get("AISTORY_REGEN_MIN_PRIORITY", "40")
    try:
        return max(0, min(100, int(raw)))
    except ValueError:
        return 40


def _issue_priority(issue_text):
    text = (issue_text or "").lower()
    best = 0
    for key, score in VIOLATION_PRIORITY.items():
        if key in text:
            best = max(best, score)
    if text.startswith("auditor confirmed"):
        best = max(best, 70)
    return best or 30


def dedupe_issues(issues):
    """Remove near-duplicate violation strings."""
    seen = set()
    out = []
    for issue in issues or []:
        if not issue:
            continue
        key = re.sub(r"\s+", " ", issue.lower().strip())[:120]
        if key in seen:
            continue
        seen.add(key)
        out.append(issue)
    return out


def prioritize_issues(issues):
    return sorted(
        dedupe_issues(issues),
        key=_issue_priority,
        reverse=True,
    )


def issues_warrant_regen(issues, attempt):
    """
    True if remaining issues are severe enough to spend another regen attempt.
    attempt is 0-based count of regens already performed.
    """
    if not issues:
        return False
    if attempt >= max_regen_attempts():
        return False
    ranked = prioritize_issues(issues)
    top = _issue_priority(ranked[0])
    return top >= min_priority_for_regen()


def apply_regen_governor(issues, attempt):
    """
    Returns (issues_for_display, should_retry, governor_meta).
    """
    ranked = prioritize_issues(issues)
    meta = {
        "attempt": attempt,
        "max_attempts": max_regen_attempts(),
        "top_priority": _issue_priority(ranked[0]) if ranked else 0,
        "issue_count": len(ranked),
        "exhausted": False,
    }
    should_retry = issues_warrant_regen(ranked, attempt)
    if ranked and not should_retry and attempt < max_regen_attempts():
        meta["exhausted"] = True
        meta["skip_reason"] = "below_min_priority"
    if attempt >= max_regen_attempts() and ranked:
        meta["exhausted"] = True
        meta["skip_reason"] = "max_attempts"
    return ranked[:8], should_retry, meta


def build_regen_exhausted_directive(issues):
    """Queue correction next beat when regen budget exhausted with remaining issues."""
    if not issues:
        return ""
    lines = [
        "PRIOR BEAT HAD UNRESOLVED SIM VIOLATIONS (regen budget exhausted — obey now):",
    ]
    for issue in issues[:5]:
        lines.append(f"- {issue}")
    return "\n".join(lines)
