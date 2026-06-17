"""
Authoritative action vocabulary — every interpreter/classifier output is validated here.
"""

VALID_ACTION_KINDS = frozenset({
    "ask_name", "talk", "personal_talk", "threaten", "show_respect", "blackmail",
    "accuse", "ask_about", "wait", "hunt", "approach", "guild", "investigate",
    "confess", "search", "find", "attack", "travel", "explore", "give", "help",
    "examine", "observe", "rest", "insult", "steal", "trade", "withdraw", "general",
})

# Regex fast-path — skip LLM when kind is unambiguous and target/speech are resolved.
FAST_PATH_KINDS = frozenset({
    "attack", "wait", "travel", "explore", "investigate", "withdraw", "confess",
    "rest", "hunt", "guild", "search", "steal", "blackmail", "accuse", "find",
})

HIGH_STAKES_KINDS = frozenset({"attack", "trade", "give", "steal"})

SPEECH_KINDS = frozenset({
    "talk", "ask_about", "ask_name", "personal_talk", "confess", "threaten",
    "insult", "show_respect", "accuse", "blackmail", "help", "give", "trade",
})


def normalize_kind(kind):
    k = (kind or "general").strip().lower()
    return k if k in VALID_ACTION_KINDS else None


def kind_valid(kind):
    return normalize_kind(kind) is not None
