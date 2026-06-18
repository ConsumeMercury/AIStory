"""
Interpretation signals beyond bare kind/target — manner, impossibility, loops, intent echo.

These extend preprocess/action_ctx without letting the LLM own truth.
"""

from __future__ import annotations

import re

_IMPOSSIBLE = re.compile(
    r"\b(?:"
    r"(?:i\s+)?(?:fly|teleport|levitate|cast\s+(?:a\s+)?(?:spell|magic)|"
    r"use\s+magic|summon|telekinesis)"
    r"|(?:pull\s+out|draw|aim)\s+(?:my\s+)?(?:gun|pistol|rifle|firearm)"
    r"|(?:shoot|fire)\s+(?:him|her|them)\s+with\s+(?:a\s+)?gun"
    r")\b",
    re.I,
)
_DELIBERATE_SILENCE = re.compile(
    r"\b(?:"
    r"say\s+nothing|stay\s+silent|remain\s+silent|hold\s+(?:my|your)\s+tongue|"
    r"do\s+nothing|i\s+(?:do\s+)?nothing|keep\s+quiet|hold\s+back"
    r"|i\s+wait\s+and\s+watch|watch\s+and\s+wait|just\s+watch(?:ing)?"
    r")\b",
    re.I,
)
_INCOMPLETE = re.compile(
    r"^(?:i\s+want\s+to|tell\s+(?:her|him|them)\s+that)[\s,.\-]*$"
    r"|(?:^|\s)(?:\.\.\.|…)\s*$"
    r"|—\s*$"
    r"|tell\s+(?:her|him|them)\s+that\s*[-—]\s*$",
    re.I,
)
_VAGUE_INTENT = re.compile(
    r"\b(?:"
    r"do\s+something\s+interesting|surprise\s+me|"
    r"i\s+don'?t\s+know\s+what\s+to\s+do|what\s+should\s+i\s+do\s+now|"
    r"anything\s+(?:interesting\s+)?happen"
    r")\b",
    re.I,
)
_PACING_SKIP = re.compile(
    r"\b(?:"
    r"skip\s+ahead|fast\s+forward|later\s+that\s+(?:night|evening|day)|"
    r"after\s+i\s+rest|let'?s\s+move\s+on|jump\s+ahead"
    r")\b",
    re.I,
)
_IN_WORLD_UNDO = re.compile(
    r"\b(?:"
    r"take\s+that\s+back|didn'?t\s+mean\s+(?:to|that)|"
    r"wait,?\s*i\s+(?:take|didn'?t\s+mean)|put\s+(?:it|that|the\s+\w+)\s+away|"
    r"i\s+(?:sheath|sheathe|lower|holster)\s+(?:my\s+)?(?:sword|blade|weapon)"
    r")\b",
    re.I,
)
_DECEIVE = re.compile(
    r"\b(?:"
    r"(?:lie|lying)\s+(?:and\s+)?(?:say|tell|claim)|"
    r"pretend\s+(?:to\s+be|i'?m|that\s+i)|"
    r"pass\s+(?:myself|me)\s+off\s+as|"
    r"deceive|bluff\s+(?:and\s+)?(?:say|tell)|"
    r"claim\s+(?:to\s+be|i'?m\s+a)\s+(?:merchant|guard|noble|priest|scholar)"
    r")\b",
    re.I,
)
_RELAY_COMMAND = re.compile(
    r"\btell\s+(?:her|him|them|(?:the\s+)?\w+)\s+to\s+",
    re.I,
)
_COERCE = re.compile(
    r"\b(?:"
    r"(?:talk|tell|make)\s+(?:or\s+)?(?:i'?ll|i\s+will)\s+(?:kill|hurt|break)|"
    r"if\s+you\s+don'?t\s+(?:talk|tell|open|give)|"
    r"unless\s+you\s+(?:talk|tell|open)"
    r")\b",
    re.I,
)
_RUMINATION = re.compile(
    r"^\s*(?:should\s+i|do\s+i|would\s+it\s+be\s+wise\s+to|what\s+if\s+i)\s+",
    re.I,
)
_PLAYER_MOOD = re.compile(
    r"\b(?:i'?m\s+(?:scared|afraid|nervous|anxious|worried)|i\s+trust\s+(?:her|him|them))\b",
    re.I,
)
_STAGE_DIR = re.compile(r"\*([^*]{2,120})\*")
_MANNER_PAREN = re.compile(
    r"\((politely|gently|softly|angrily|hostilely|sarcastically|firmly|"
    r"desperately|coldly|warmly|hesitantly)\)",
    re.I,
)
_HOSTILE = re.compile(
    r"\b(?:demand|snarl|snap|shout\s+at|yell\s+at|grab\s+(?:him|her)|"
    r"in\s+(?:his|her|their)\s+face)\b",
    re.I,
)
_GENTLE = re.compile(
    r"\b(?:gently|softly|kindly|politely|carefully|humbly)\b",
    re.I,
)
_SARCASM = re.compile(
    r"\b(?:oh\s+great|wonderful|just\s+perfect|lovely|fantastic)\b|!\s*$",
    re.I,
)
_BARE_IMPERATIVE = re.compile(
    r"^(?:kneel|stop|wait|go|leave|run|help|listen|follow|open|move)\s*[!?.]*\s*$",
    re.I,
)
_RETURN_ITEM = re.compile(
    r"\b(?:give\s+back|return|hand\s+back)\s+(?:the\s+|a\s+|my\s+)?([\w\s'-]{2,30})\b",
    re.I,
)


def extract_manner(text: str) -> str:
    """Return manner slot: hostile, gentle, sarcastic, coercive, polite, neutral."""
    t = text or ""
    if _COERCE.search(t):
        return "coercive"
    if _HOSTILE.search(t):
        return "hostile"
    if _GENTLE.search(t):
        return "gentle"
    if _SARCASM.search(t):
        return "sarcastic"
    m = _MANNER_PAREN.search(t)
    if m:
        word = m.group(1).lower()
        if word in ("angrily", "hostilely", "firmly", "coldly"):
            return "hostile"
        if word in ("gently", "softly", "politely", "warmly", "hesitantly"):
            return "gentle"
        if word == "sarcastically":
            return "sarcastic"
    return "neutral"


def strip_manner_parentheticals(text: str) -> tuple[str, str | None]:
    manner = None
    m = _MANNER_PAREN.search(text or "")
    if m:
        manner = extract_manner(m.group(0))
        text = _MANNER_PAREN.sub("", text).strip()
    return text, manner


def parse_stage_directions(text: str) -> tuple[str, list[str]]:
    dirs = _STAGE_DIR.findall(text or "")
    cleaned = _STAGE_DIR.sub("", text or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, [d.strip() for d in dirs if d.strip()]


def detect_impossible_action(text: str) -> str | None:
    if _IMPOSSIBLE.search(text or ""):
        return "impossible_in_setting"
    return None


def detect_stale_repetition(player: dict, action: str, kind: str) -> bool:
    """Same explore/observe in unchanged scene — over-literal loop."""
    if kind not in ("explore", "observe", "examine", "general"):
        return False
    journal = player.get("journal") or []
    area = player.get("area")
    if not journal:
        return False

    def _norm(s):
        return re.sub(r"\s+", " ", (s or "").strip().lower())

    norm = _norm(action)
    recent = [e for e in journal[-8:] if e.get("area") == area]
    if not recent:
        return False
    same_action = sum(1 for e in recent if _norm(e.get("action")) == norm)
    if same_action >= 2:
        return True
    passive = [e for e in recent if e.get("kind") in ("explore", "observe", "examine", "general")]
    return len(passive) >= 4 and kind in ("explore", "observe", "examine")


def detect_conversation_loop(player: dict, kind: str, target_id: str | None) -> bool:
    if kind not in ("talk", "ask_about", "personal_talk") or not target_id:
        return False
    window = (player.get("journal") or [])[-6:]
    hits = sum(
        1 for e in window
        if e.get("focus_npc") == target_id
        and e.get("kind") in ("talk", "ask_about", "personal_talk")
        and not e.get("interpretation_clarify")
    )
    return hits >= 3


def build_intent_echo(ctx: dict) -> str:
    """Human-readable parsed intent for debug / player echo."""
    if not ctx:
        return ""
    parts = [f"kind={ctx.get('kind', '?')}"]
    tid = ctx.get("target_id")
    if tid:
        parts.append(f"target={tid}")
    elif ctx.get("target_resolution", {}).get("status"):
        parts.append(f"target={ctx['target_resolution']['status']}")
    if ctx.get("ask_topic"):
        parts.append(f"topic={ctx['ask_topic'][:40]!r}")
    if ctx.get("manner") and ctx.get("manner") != "neutral":
        parts.append(f"manner={ctx['manner']}")
    if ctx.get("player_speech"):
        parts.append(f'speech="{ctx["player_speech"][:60]}"')
    if ctx.get("interpretation_clarify"):
        parts.append(f"CLARIFY: {ctx.get('interpretation_clarify_reason') or '?'}")
    if ctx.get("inventory_missing"):
        parts.append(f"missing={ctx['inventory_missing'][:2]}")
    if ctx.get("mislabel_resolution"):
        parts.append("mislabel=resolved")
    if ctx.get("impossible_action"):
        parts.append("impossible=reframed")
    if ctx.get("conversational_loop"):
        parts.append("loop=detected")
    if ctx.get("stale_repetition"):
        parts.append("stale=repeat")
    return " · ".join(parts)


def log_rephrase_pair(player: dict, action: str, action_ctx: dict, *, tick=None) -> bool:
    """
    When player rephrases after clarify/ambiguous beat, log A→B for corpus mining.
    """
    journal = player.get("journal") or []
    if not journal:
        return False
    last = journal[-1]
    if not (last.get("interpretation_clarify") or last.get("target_ambiguous")):
        return False

    def _norm(s):
        return re.sub(r"\s+", " ", (s or "").strip().lower())

    if _norm(action) == _norm(last.get("action")):
        return False

    pairs = player.setdefault("interpretation_rephrase_log", [])
    pairs.append({
        "tick": tick,
        "first": (last.get("action") or "")[:160],
        "second": (action or "")[:160],
        "first_kind": last.get("kind"),
        "second_kind": action_ctx.get("kind"),
        "clarify_reason": last.get("interpretation_clarify_reason")
        or (last.get("boundary") or {}).get("tagged_shapes"),
    })
    player["interpretation_rephrase_log"] = pairs[-80:]
    return True


def apply_interpretation_signals(action: str, player: dict, ctx: dict) -> None:
    """Apply tonal, temporal, and experience-layer signals to action_ctx."""
    text = action or ""
    if not text.strip():
        return

    cleaned, stage_dirs = parse_stage_directions(text)
    cleaned, paren_manner = strip_manner_parentheticals(cleaned)
    if stage_dirs:
        ctx["stage_directions"] = stage_dirs
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " STAGE DIRECTION — physical beat: "
            + "; ".join(stage_dirs[:2])
            + "."
        ).strip()

    manner = paren_manner or extract_manner(cleaned)
    if manner != "neutral":
        ctx["manner"] = manner
        if manner == "coercive" and ctx.get("kind") in ("talk", "ask_about", "general"):
            ctx["kind"] = "threaten"
        if manner == "hostile" and ctx.get("kind") == "talk":
            ctx["relationship"] = ctx.get("relationship") or ("insult", 0.4)

    imp = detect_impossible_action(cleaned)
    if imp:
        ctx["impossible_action"] = imp
        ctx["kind"] = "observe"
        ctx["target_id"] = None
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " IMPOSSIBLE ACTION — no magic, guns, or flight in this world."
            + " Reframe in-world: effort, failure, or awkward pause — never solemn compliance."
        ).strip()

    if _DELIBERATE_SILENCE.search(cleaned):
        ctx["deliberate_silence"] = True
        ctx["kind"] = "wait" if "watch" in cleaned.lower() else "observe"
        ctx["target_id"] = None
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " DELIBERATE NON-ACTION — passing the moment; watch, silence, or stillness."
        ).strip()

    if _INCOMPLETE.search(cleaned) and not ctx.get("interpretation_clarify"):
        ctx["interpretation_clarify"] = True
        ctx["interpretation_clarify_reason"] = "incomplete intent — finish what you mean to do or say"
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " INCOMPLETE — protagonist trails off; prompt them to finish the thought."
        ).strip()

    if _VAGUE_INTENT.search(cleaned) and not ctx.get("interpretation_clarify"):
        ctx["kind"] = "explore"
        ctx["vague_player_intent"] = True
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " VAGUE INTENT — nudge toward one concrete hook in the scene (person, object, exit, rumor)."
            + " Do not invent a quest; surface what is already here."
        ).strip()

    if _PACING_SKIP.search(cleaned):
        ctx["kind"] = "rest" if "rest" in cleaned.lower() else "wait"
        ctx["pacing_skip"] = True
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " PACING SKIP — player requests time to pass; compress to next beat without inventing events."
        ).strip()

    if _IN_WORLD_UNDO.search(cleaned):
        ctx["in_world_undo"] = True
        ctx["kind"] = "withdraw"
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " IN-WORLD RETRACTION — protagonist takes back the last gesture; no combat from the aborted action."
        ).strip()

    if _DECEIVE.search(cleaned):
        ctx["kind"] = "deceive"
        ctx["declared_deception"] = True
        ctx["skill_xp"] = ("deception", 10)
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " DECLARED DECEPTION — protagonist intends a lie; NPC may believe, doubt, or call it."
            + " Outcome depends on deception, not plain speech."
        ).strip()

    if _RELAY_COMMAND.search(cleaned):
        ctx["relay_command"] = True
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " RELAY/COMMAND — protagonist asks an NPC to act; compliance is not guaranteed."
            + " Show assent, refusal, or deflection based on relationship."
        ).strip()

    if _RUMINATION.match(cleaned):
        ctx["rumination"] = True
        ctx["interpretation_clarify"] = True
        ctx["interpretation_clarify_reason"] = "internal question — decide what you do, not whether you should"
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " RUMINATION — inward beat; no NPC dialogue unless they overhear muttering."
        ).strip()

    m_mood = _PLAYER_MOOD.search(cleaned)
    if m_mood:
        ctx["player_mood"] = m_mood.group(0).lower()[:40]
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + f" PLAYER MOOD — {ctx['player_mood']}; color prose, no stat change unless earned."
        ).strip()

    if _BARE_IMPERATIVE.match(cleaned.strip()):
        words = cleaned.strip().split()
        verb = words[0].lower().rstrip("!?")
        if ctx.get("target_id"):
            ctx["relay_command"] = True
            ctx["kind"] = "talk"
        elif verb in ("wait", "kneel", "stop"):
            ctx["kind"] = "observe" if verb == "kneel" else "wait"
        else:
            ctx["interpretation_clarify"] = True
            ctx["interpretation_clarify_reason"] = (
                f"ambiguous imperative {verb!r} — command someone present or act yourself?"
            )

    m_ret = _RETURN_ITEM.search(cleaned)
    if m_ret:
        ctx["return_item_query"] = m_ret.group(1).strip()
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + f" RETURN ITEM — verify protagonist has {m_ret.group(1)!r} before prose shows giving it back."
        ).strip()

    kind = ctx.get("kind", "general")
    if detect_stale_repetition(player, action, kind):
        ctx["stale_repetition"] = True
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " STALE REPETITION — little has changed; say so briefly or nudge one new detail, not a full re-description."
        ).strip()

    if detect_conversation_loop(player, kind, ctx.get("target_id")):
        ctx["conversational_loop"] = True
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " CONVERSATION LOOP — same exchange repeating; NPC shows impatience, new info, or closes the topic."
        ).strip()
