"""
Topic resolution for ask_about — what the player is asking about, not who.
"""

from __future__ import annotations

import re

_ASK_ABOUT = re.compile(
    r"\b(?:ask|asked|asking)\s+(?:(?:the|a|an)\s+[\w'-]+\s+){0,3}?about\s+(?:the\s+)?(.+?)(?:\?|$|\band\b)",
    re.I,
)
_KNOW_ABOUT = re.compile(
    r"\b(?:what do you know about|tell me about|what about|know anything about)\s+(?:the\s+)?(.+?)(?:\?|$|\band\b)",
    re.I,
)
_WHAT_THINK = re.compile(
    r"\bwhat\s+(?:do\s+)?you\s+think\s+of\s+me\b",
    re.I,
)
_ASK_IF = re.compile(
    r"\bask\s+(?:her|him|them|(?:the\s+)?[\w'-]+)\s+(?:if|whether)\s+(.+?)(?:\?|$|\band\b)",
    re.I,
)


def classify_topic(topic: str) -> str:
    """Return topic_type: npc, place, event, reflexive, vague, general."""
    t = (topic or "").strip().lower()
    if not t:
        return "vague"
    if _WHAT_THINK.search(topic):
        return "reflexive"
    if re.search(r"\b(murder|theft|kill|death|rumor|raid|fire|missing|disappearance)\b", t):
        return "event"
    if re.search(r"\b(gate|temple|market|wharf|dock|cellar|inn|archive|district|alley)\b", t):
        return "place"
    if re.search(r"\b(priest|merchant|guard|scholar|captain|woman|man|father|mother)\b", t):
        return "npc"
    if t in ("stuff", "things", "that", "this", "everything", "anything", "what's going on"):
        return "vague"
    if len(t.split()) <= 2 and not re.search(r"\b(the|a|an)\b", t):
        return "general"
    return "general"


def extract_ask_topic(action: str) -> tuple[str | None, str]:
    """Return (topic_text, topic_type) from player action."""
    text = (action or "").strip()
    if not text:
        return None, "vague"

    if _WHAT_THINK.search(text):
        return "what you think of me", "reflexive"

    m_if = _ASK_IF.search(text)
    if m_if:
        topic = m_if.group(1).strip().rstrip("?.!")
        if topic:
            return topic[:120], classify_topic(topic)

    for pat in (_ASK_ABOUT, _KNOW_ABOUT):
        m = pat.search(text)
        if m:
            topic = m.group(1).strip().rstrip("?.!")
            if topic:
                return topic[:120], classify_topic(topic)

    return None, "vague"


def _topic_tokens(topic: str) -> set[str]:
    stop = {
        "the", "a", "an", "about", "of", "and", "or", "what", "who", "how",
        "when", "where", "why", "is", "are", "was", "were", "me", "my", "you",
    }
    return {
        t for t in re.findall(r"[a-z0-9]+", (topic or "").lower())
        if len(t) > 2 and t not in stop
    }


def gate_topic_for_npc(topic: str, topic_type: str, npc: dict, player: dict | None = None) -> str:
    """
    Return knowledge level for an ask_about topic: known, partial, unknown, not_applicable.
    Heuristic — prevents authoritative lore from NPCs with no plausible access.
    """
    if topic_type in ("reflexive", "vague"):
        return "not_applicable"
    if not topic or not npc:
        return "unknown"

    tokens = _topic_tokens(topic)
    if not tokens:
        return "unknown"

    role = (npc.get("role") or "").lower()
    occ = (npc.get("occupation") or "").lower()
    area = (npc.get("area") or "").lower()

    for sec in npc.get("secrets") or []:
        blob = " ".join(
            str(sec.get(k) or "")
            for k in ("summary", "text", "label", "topic")
        ).lower()
        if any(t in blob for t in tokens):
            return "known"

    role_topics = {
        "priest": {"murder", "death", "cult", "temple", "soul", "confession", "sin"},
        "guard": {"murder", "theft", "raid", "gate", "curfew", "riot", "fire"},
        "merchant": {"trade", "market", "price", "caravan", "tax", "guild"},
        "scholar": {"archive", "history", "prophecy", "text", "ledger", "murder"},
        "sailor": {"wharf", "dock", "ship", "smuggling", "tide", "harbor"},
        "beggar": {"street", "alley", "rumor", "missing"},
    }
    aligned = role_topics.get(role, set())
    if tokens & aligned:
        return "known"

    elite = {
        "royal", "king", "queen", "court", "crown", "throne", "diplomacy",
        "succession", "palace", "noble", "duke", "emperor",
    }
    low_status = {"beggar", "thief", "criminal", "street"}
    if tokens & elite and role in low_status:
        return "unknown"

    if topic_type == "place":
        place_blob = f"{area} {occ} {role}"
        if any(t in place_blob for t in tokens):
            return "partial"
        return "partial"

    if topic_type == "event":
        if role in ("guard", "priest", "scholar", "merchant"):
            return "partial"

    if topic_type == "npc":
        return "partial"

    return "partial"


def apply_topic_gates(action_ctx: dict, player: dict, npcs: dict, present: list) -> None:
    """Set clarify flags and knowledge directives for ask_about topics."""
    if not action_ctx or action_ctx.get("interpretation_clarify"):
        return

    kind = action_ctx.get("kind", "general")
    if kind != "ask_about":
        return

    topic = action_ctx.get("ask_topic")
    topic_type = action_ctx.get("topic_type") or "vague"

    if not topic:
        action_ctx["interpretation_clarify"] = True
        action_ctx["interpretation_clarify_reason"] = "ask_about without a clear topic"
        action_ctx["story_directive"] = (
            (action_ctx.get("story_directive") or "")
            + " TOPIC UNCLEAR — ask what specifically they want to know about."
        ).strip()
        return

    if topic_type == "vague":
        action_ctx["interpretation_clarify"] = True
        action_ctx["interpretation_clarify_reason"] = "topic too vague — name what you want to know"
        action_ctx["story_directive"] = (
            (action_ctx.get("story_directive") or "")
            + " VAGUE TOPIC — protagonist must name a concrete subject (person, place, event)."
        ).strip()
        return

    tid = action_ctx.get("target_id")
    npc = None
    if tid and npcs:
        npc = npcs.get(tid)
    if not npc and len(present) == 1:
        npc = present[0]

    if not npc:
        return

    level = gate_topic_for_npc(topic, topic_type, npc, player)
    action_ctx["topic_knowledge"] = level
    if level == "unknown":
        action_ctx["topic_knowledge_blocked"] = True
        action_ctx["story_directive"] = (
            (action_ctx.get("story_directive") or "")
            + f" TOPIC OUT OF DEPTH — {npc.get('name') or 'They'} would not plausibly know {topic!r}."
            + " Deflect, guess wrong, or admit ignorance — no authoritative invented lore."
        ).strip()
    elif level == "partial":
        action_ctx["story_directive"] = (
            (action_ctx.get("story_directive") or "")
            + f" PARTIAL KNOWLEDGE — only what a {npc.get('role', 'stranger')} plausibly knows about {topic!r}."
        ).strip()
