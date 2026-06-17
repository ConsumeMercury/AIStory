"""
Detect contradictory narrator directives before the prompt is sent.
"""

_CONFLICTS = (
    (
        ("continue conversation", "same conversation", "mid-exchange", "mid-scene"),
        ("fresh chapter", "re-describe setting", "first arrival", "weather opener"),
    ),
    (
        ("do not repeat", "forbidden verbatim", "do not replay", "new wording only"),
        ("match rhythm", "voice anchor", "spoken like this"),
    ),
    (
        ("no protagonist dialogue", "does not speak", "no invented lines"),
        ("protagonist says only", "quote that line", "says aloud"),
    ),
    (
        ("stay in same place", "location lock", "did not move", "stalled"),
        ("travel to", "arrives at", "new district"),
    ),
)


def _contains_any(text, phrases):
    lower = text.lower()
    return any(p in lower for p in phrases)


def find_directive_conflicts(prompt_text):
    """Return list of human-readable conflict descriptions."""
    if not prompt_text:
        return []
    issues = []
    for group_a, group_b in _CONFLICTS:
        if _contains_any(prompt_text, group_a) and _contains_any(prompt_text, group_b):
            issues.append(
                f"Conflicting directives: {group_a[0]!r} vs {group_b[0]!r}"
            )
    return issues


def arbitrate_prompt(prompt_text, conflicts):
    """Prepend priority order when contradictory directives were detected."""
    if not conflicts or not prompt_text:
        return prompt_text
    header = (
        "ARBITRATION — conflicting instructions detected; obey in this order:\n"
        "1. HARD CONSTRAINTS and SCENE FACTS\n"
        "2. PLACE LOCK and THIS BEAT\n"
        "3. CONVERSATION LEDGER / continuity / DO NOT REPEAT\n"
        "4. Atmosphere, craft, and story tier hints\n\n"
    )
    return header + prompt_text


def validate_directives(prompt_text):
    """Log conflicts at warning level; return issues for telemetry."""
    issues = find_directive_conflicts(prompt_text)
    if issues:
        import logging
        log = logging.getLogger(__name__)
        for issue in issues[:4]:
            log.warning("Directive conflict: %s", issue)
    return issues
