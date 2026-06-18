"""
Action interpretation boundary — preprocess, dimension status, and trace.

Principle: every interpretation dimension can be MATCHED / ABSENT / AMBIGUOUS.
When unsure, clarify or abstain — never silently substitute wrong intent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class InterpretationStatus(str, Enum):
    MATCHED = "matched"
    ABSENT = "absent"
    AMBIGUOUS = "ambiguous"


@dataclass
class DimensionResult:
    status: InterpretationStatus
    value: object = None
    reason: str = ""
    source: str = "regex"
    candidates: list = field(default_factory=list)

    def to_dict(self):
        return {
            "status": self.status.value,
            "value": self.value,
            "reason": self.reason,
            "source": self.source,
            "candidates": self.candidates,
        }


@dataclass
class PreprocessResult:
    action: str
    original: str
    primary_clause: str
    blocked_kinds: list[str] = field(default_factory=list)
    kind_override: str | None = None
    self_target: bool = False
    object_ref: str | None = None
    place_ref: str | None = None
    emote: bool = False
    permission_question: bool = False
    narrated_outcome: bool = False
    conditional: bool = False
    compound_dropped: str | None = None
    negation_detected: bool = False
    negated_kinds: list[str] = field(default_factory=list)
    meta_inworld: bool = False
    empty_input: bool = False
    injection_stripped: bool = False
    clarify_reason: str | None = None
    idiom_resolved: str | None = None
    typo_normalized: bool = False
    group_address: bool = False
    group_one_role: str | None = None

    def needs_clarify(self) -> bool:
        if self.permission_question or self.meta_inworld:
            return True
        if self.clarify_reason and not self.narrated_outcome:
            return True
        return False


_INJECTION = re.compile(
    r"\[(?:SPEAKING|SYSTEM|NARRATOR|OOC|META)[^\]]*\]|\(OOC\s*:[^)]*\)",
    re.I,
)
_EMPTY = re.compile(r"^\s*[^\w\s]*\s*$")
_SELF_TARGET = re.compile(
    r"\b(?:talk|speak|ask|look|examine|inspect|check|watch)\s+(?:to|at|on)?\s*"
    r"(?:myself|me|my\s+(?:self|hands|face|reflection|pockets|gear|inventory))\b"
    r"|\b(?:talk|speak)\s+to\s+myself\b"
    r"|\bintrospect\b|\bcheck\s+myself\b",
    re.I,
)
_OBJECT_VERBS = re.compile(
    r"\b(?:examine|inspect|look\s+at|study|pick\s+up|take|grab|open|search\s+for|"
    r"loot|collect|use)\s+(?:the\s+|a\s+|an\s+)?"
    r"(bird|knife|door|key|coin|sword|blade|dagger|weapon|letter|note|book|"
    r"crate|barrel|box|chest|lock|chain|rope|lamp|candle|food|bread|potion|"
    r"artifact|relic|statue|painting|map|scroll|gem|ring|amulet|corpse|body)\b",
    re.I,
)
_PLACE_AS_PERSON = re.compile(
    r"\b(?:ask|talk|speak)\s+(?:(?:to|with)\s+)?(?:the\s+)?"
    r"(temple|shrine|chapel|church|sanctuary|altar|guild\s+hall|market|"
    r"castle|palace|inn|tavern|forge|library|archive)\b",
    re.I,
)
_IDIOMS = [
    (re.compile(r"\bhit\s+the\s+road\b", re.I), "travel", "idiom: hit the road → travel"),
    (re.compile(r"\bstrike\s+a\s+deal\b", re.I), "trade", "idiom: strike a deal → trade"),
    (re.compile(r"\btake\s+her\s+hand\b", re.I), "talk", "idiom: take her hand → social"),
    (re.compile(r"\btake\s+his\s+hand\b", re.I), "talk", "idiom: take his hand → social"),
    (re.compile(r"\bwatch\s+the\s+door\b", re.I), "wait", "idiom: watch the door → wait"),
    (re.compile(r"\bdrop\s+it\b(?!\s+(?:off|down))", re.I), "withdraw", "idiom: drop it → let go"),
]
_NEGATED_KIND = [
    (re.compile(r"\b(?:don'?t|do not|won't|will not|never)\s+attack\b", re.I), "attack"),
    (re.compile(r"\b(?:don'?t|do not|won't|will not|never)\s+(?:pay|give|hand\s+over)\b", re.I), "give"),
    (re.compile(r"\b(?:don'?t|do not|won't|will not|never)\s+(?:steal|pickpocket)\b", re.I), "steal"),
    (re.compile(r"\b(?:don'?t|do not|won't|will not|never)\s+kill\b", re.I), "attack"),
    (re.compile(r"\b(?:don'?t|do not|won't|will not|never)\s+threaten\b", re.I), "threaten"),
]
_AFFIRMED_AFTER_NEG = re.compile(
    r"\b(?:don'?t|do not|won't|will not|never)\s+\w+(?:\s+\w+){0,4}\s*"
    r"(?:,\s*(?:just\s+)?|\bbut\s+|\bjust\s+|\binstead\s+)"
    r"(talk|speak|ask|leave|wait|rest|explore|withdraw)\b",
    re.I,
)
_CONDITIONAL = re.compile(
    r"\b(?:if\s+.+\s*,\s*(?:then\s+)?(?:attack|kill|pay|steal|give|threaten)|"
    r"i(?:'ll|\s+will)\s+(?:only\s+)?(?:pay|attack|kill)\s+if\b)",
    re.I,
)
_NARRATED_OUTCOME = re.compile(
    r"\b(?:i|we)\s+(?:kill|killed|murder|murdered|slay|slayed|slain|stab|stabbed|"
    r"defeat|defeated|take|took)\s+(?:him|her|them|the\s+\w+)"
    r"(?:\s+and\s+(?:take|grab|loot|get)\b)?",
    re.I,
)
_PERMISSION = re.compile(
    r"^\s*(?:can|could|may|am\s+i\s+allowed\s+to|is\s+it\s+ok(?:ay)?\s+to)\s+"
    r"(?:i\s+)?(?:attack|kill|steal|pay|give|take|leave|rest)\b",
    re.I,
)
_EMOTE = re.compile(
    r"^\s*(?:sigh|smile|laugh|chuckle|grimace|shrug|nod|bow|curtsy|"
    r"wait\s+nervously|fidget|pace)\b",
    re.I,
)
_COMPOUND = re.compile(
    r"\s+(?:,\s*|\band\s+then\s+|\band\s+|\bthen\s+)"
    r"(?:attack|kill|leave|go|travel|rest|wait|steal|give)\b",
    re.I,
)
_META_INWORLD = re.compile(
    r"^\s*(?:what\s+can\s+i\s+do\s+here|what\s+are\s+my\s+options|"
    r"what\s+commands|how\s+do\s+i\s+play)\??\s*$",
    re.I,
)
_META_FRUSTRATION = re.compile(
    r"^\s*(?:this\s+isn'?t\s+working|that'?s\s+not\s+what\s+i\s+meant|ugh|wtf|"
    r"wrong\s+person|you\s+misunderstood)\b",
    re.I,
)
_CONTINUATION = re.compile(
    r"^\s*(?:and\s+then\??|go\s+on|what\s+else\??|continue|keep\s+going|"
    r"what\s+happened\s+next)\s*[.!?]?\s*$",
    re.I,
)
_BACKCHANNEL = re.compile(
    r"^\s*(?:okay|ok|i\s+see|hmm+|yes|yeah|yep|right|sure|understood|"
    r"got\s+it|alright)\s*[.!?]?\s*$",
    re.I,
)
_VERBLESS_NAME = re.compile(
    r"^\s*([A-Z][a-z'-]{2,24})\s*[.!?]?\s*$",
)
_VERBLESS_NOUN = re.compile(
    r"^\s*(?:the\s+)?(door|gate|north|south|east|west|knife|bird|key|corpse|body)\s*[.!?]?\s*$",
    re.I,
)
_SLANG = {
    r"\bgonna\b": "going to",
    r"\bwanna\b": "want to",
    r"\blemme\b": "let me",
    r"\bgimme\b": "give me",
    r"\bain't\b": "is not",
}


def normalize_input_text(text: str) -> str:
    """Whitespace, smart quotes, common slang — before parse."""
    if not text:
        return text
    t = text.strip()
    t = re.sub(r"\s+", " ", t)
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2018", "'").replace("\u2019", "'")
    for pat, rep in _SLANG.items():
        t = re.sub(pat, rep, t, flags=re.I)
    return t
_GROUP_EVERYONE = re.compile(
    r"\b(?:tell|ask|speak\s+to|address|say\s+to)\s+"
    r"(?:everyone|everybody|the\s+crowd|them\s+all|all\s+of\s+them|the\s+people\s+here)\b",
    re.I,
)
_GROUP_ONE = re.compile(
    r"\bone\s+of\s+the\s+(guards|soldiers|merchants|priests|sailors|scholars|women|men)\b",
    re.I,
)
_TYPO_VERBS = {
    "tlak": "talk", "takl": "talk", "tak": "talk", "tlk": "talk",
    "attakc": "attack", "attac": "attack", "attak": "attack", "attck": "attack",
    "examin": "examine", "explor": "explore", "investigte": "investigate",
    "travl": "travel", "trvel": "travel", "apprach": "approach",
    "giv": "give", "hel": "help",
}


def normalize_typo_verbs(text: str) -> tuple[str, bool]:
    """Fix common verb typos at word boundaries."""
    if not text:
        return text, False
    changed = False

    def _repl(m):
        nonlocal changed
        word = m.group(0)
        low = word.lower()
        if low in _TYPO_VERBS:
            changed = True
            rep = _TYPO_VERBS[low]
            if word[0].isupper():
                return rep.capitalize()
            return rep
        return word

    out = re.sub(r"\b[a-zA-Z]{2,12}\b", _repl, text)
    return out, changed


def preprocess_action(action: str) -> PreprocessResult:
    original = (action or "").strip()
    original = normalize_input_text(original)
    if not original or _EMPTY.match(original):
        return PreprocessResult(
            action=original,
            original=original,
            primary_clause=original,
            empty_input=True,
            clarify_reason="empty input",
        )

    cleaned = original
    injection_stripped = False
    if _INJECTION.search(cleaned):
        cleaned = _INJECTION.sub("", cleaned).strip()
        injection_stripped = True

    cleaned, typo_normalized = normalize_typo_verbs(cleaned)

    primary = cleaned
    compound_dropped = None
    m_comp = _COMPOUND.search(cleaned)
    if m_comp:
        primary = cleaned[: m_comp.start()].strip()
        compound_dropped = cleaned[m_comp.start() :].strip()

    result = PreprocessResult(
        action=cleaned,
        original=original,
        primary_clause=primary or cleaned,
        injection_stripped=injection_stripped,
        typo_normalized=typo_normalized,
    )
    if compound_dropped:
        result.compound_dropped = compound_dropped

    scan = result.primary_clause

    if _META_INWORLD.match(cleaned):
        result.meta_inworld = True
        result.clarify_reason = "meta question — use /help or hints"
        return result

    if _META_FRUSTRATION.search(cleaned):
        result.clarify_reason = "meta frustration — rephrase your in-world action plainly"
        return result

    if _CONTINUATION.match(cleaned):
        result.kind_override = "talk"
        result.clarify_reason = None
        return result

    if _BACKCHANNEL.match(cleaned):
        result.emote = True
        result.kind_override = "observe"
        return result

    m_vn = _VERBLESS_NAME.match(scan)
    if m_vn and len(scan.split()) <= 2:
        result.kind_override = "talk"
        result.clarify_reason = None
        return result

    m_vo = _VERBLESS_NOUN.match(scan)
    if m_vo:
        noun = m_vo.group(1).lower()
        if noun in ("north", "south", "east", "west"):
            result.kind_override = "travel"
        else:
            result.object_ref = noun
            result.kind_override = "examine"
        return result

    if _PERMISSION.search(cleaned):
        result.permission_question = True
        result.clarify_reason = "permission question — clarify intent before acting"
        return result

    if _SELF_TARGET.search(scan):
        result.self_target = True
        result.kind_override = "observe"
        return result

    if _GROUP_EVERYONE.search(scan):
        result.group_address = True
        if re.search(r"\b(?:leave|go|get\s+out|disperse)\b", scan, re.I):
            result.kind_override = "withdraw"
        else:
            result.kind_override = "talk"
        return result

    m_one = _GROUP_ONE.search(scan)
    if m_one:
        result.group_one_role = m_one.group(1).lower().rstrip("s")
        if result.group_one_role == "women":
            result.group_one_role = "woman"
        elif result.group_one_role == "men":
            result.group_one_role = "man"
        return result

    mobj = _OBJECT_VERBS.search(scan)
    if mobj:
        result.object_ref = mobj.group(1).lower()
        if re.search(r"\b(?:pick\s+up|take|grab|loot|collect)\b", scan, re.I):
            result.kind_override = "search"
        else:
            result.kind_override = "examine"
        return result

    mplace = _PLACE_AS_PERSON.search(scan)
    if mplace:
        result.place_ref = mplace.group(1).lower()
        result.clarify_reason = f"no one to ask at the {result.place_ref} — name a person or investigate the place"
        return result

    for pat, kind, note in _IDIOMS:
        if pat.search(cleaned):
            result.kind_override = kind
            result.idiom_resolved = note
            break

    negated = []
    for pat, kind in _NEGATED_KIND:
        if pat.search(cleaned):
            negated.append(kind)
    if negated:
        result.negation_detected = True
        result.negated_kinds = negated
        result.blocked_kinds = list(negated)

    m_aff = _AFFIRMED_AFTER_NEG.search(cleaned)
    if m_aff:
        verb = m_aff.group(1).lower()
        kind_map = {
            "talk": "talk", "speak": "talk", "ask": "ask_about",
            "leave": "withdraw", "wait": "wait", "rest": "rest",
            "explore": "explore", "withdraw": "withdraw",
        }
        result.kind_override = kind_map.get(verb, "talk")
        result.negation_detected = True

    if _CONDITIONAL.search(cleaned) and not re.search(
        r"^\s*ask\s+(?:her|him|them|the\s+\w+)\s+if\b", cleaned, re.I,
    ):
        result.conditional = True
        result.clarify_reason = "conditional action — state what you do now, not if-then"
        primary_match = re.search(
            r"\b(ask|talk|speak|investigate|examine|wait|rest|explore|approach)\b",
            primary,
            re.I,
        )
        if primary_match and not result.kind_override:
            verb = primary_match.group(1).lower()
            result.kind_override = "ask_about" if verb == "ask" else ("talk" if verb in ("talk", "speak") else verb)

    if _NARRATED_OUTCOME.search(cleaned) and not result.negation_detected:
        result.narrated_outcome = True
        if not result.kind_override:
            result.kind_override = "attack"
        result.clarify_reason = "attempt only — outcomes belong to simulation, not narration"

    if _EMOTE.match(cleaned) and len(cleaned.split()) <= 6:
        result.emote = True
        result.kind_override = "observe"

    return result


def kind_blocked(kind: str, preprocess: PreprocessResult) -> bool:
    return kind in preprocess.blocked_kinds


def apply_preinterpretation_to_ctx(preprocess: PreprocessResult, ctx: dict):
    trace = {
        "negation_detected": preprocess.negation_detected,
        "negated_kinds": preprocess.negated_kinds,
        "self_target": preprocess.self_target,
        "object_ref": preprocess.object_ref,
        "place_ref": preprocess.place_ref,
        "emote": preprocess.emote,
        "permission_question": preprocess.permission_question,
        "narrated_outcome": preprocess.narrated_outcome,
        "conditional": preprocess.conditional,
        "compound_dropped": preprocess.compound_dropped,
        "kind_override": preprocess.kind_override,
        "idiom_resolved": preprocess.idiom_resolved,
        "primary_clause": preprocess.primary_clause[:120],
        "clarify_reason": preprocess.clarify_reason,
        "typo_normalized": preprocess.typo_normalized,
        "group_address": preprocess.group_address,
        "group_one_role": preprocess.group_one_role,
    }
    ctx["interpretation_preprocess"] = trace

    if preprocess.empty_input:
        ctx["interpretation_clarify"] = True
        ctx["interpretation_clarify_reason"] = "empty input"
        ctx["kind"] = "general"
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " EMPTY INPUT — one short beat of stillness; no invented action."
        ).strip()
        return

    if preprocess.needs_clarify():
        ctx["interpretation_clarify"] = True
        ctx["interpretation_clarify_reason"] = preprocess.clarify_reason
        if preprocess.permission_question:
            ctx["story_directive"] = (
                (ctx.get("story_directive") or "")
                + " PERMISSION QUESTION — the protagonist hesitates; do NOT execute violence or payment yet."
            ).strip()
        elif preprocess.place_ref:
            ctx["target_id"] = None
            ctx["story_directive"] = (
                (ctx.get("story_directive") or "")
                + f" NO PERSON TO ASK — the {preprocess.place_ref} is a place, not a speaker. "
                "Show looking for someone to address, or investigating the place instead."
            ).strip()
        return

    if preprocess.self_target:
        ctx["self_target"] = True
        ctx["target_id"] = None
        ctx["kind"] = preprocess.kind_override or "observe"
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " SELF-TARGET — inward beat: hands, breath, gear, reflection. No NPC dialogue."
        ).strip()
        return

    if preprocess.group_address:
        ctx["group_address"] = True
        ctx["target_id"] = None
        ctx["kind"] = preprocess.kind_override or "talk"
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " GROUP ADDRESS — crowd reaction or general call; no single focal NPC dialogue unless one steps forward."
        ).strip()
        return

    if preprocess.group_one_role:
        ctx["group_one_role"] = preprocess.group_one_role
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + f" ONE OF GROUP — pick one {preprocess.group_one_role} present; arbitrary if several match."
        ).strip()
        return

    if preprocess.object_ref:
        ctx["object_ref"] = preprocess.object_ref
        ctx["target_id"] = None
        ctx["kind"] = preprocess.kind_override or "examine"
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + f" OBJECT TARGET — focus on the {preprocess.object_ref}, not a person. "
            "No invented NPC dialogue unless someone reacts unprompted."
        ).strip()
        return

    if preprocess.narrated_outcome:
        ctx["narrated_outcome_reframed"] = True
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + " ATTEMPT ONLY — describe the try, not success. Simulation decides outcome."
        ).strip()

    if preprocess.compound_dropped:
        ctx["compound_dropped"] = preprocess.compound_dropped
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + f" COMPOUND TRUNCATED — only the first action this beat: {preprocess.primary_clause[:80]!r}."
        ).strip()


def build_kind_dimension(ctx: dict, *, source: str = "regex") -> DimensionResult:
    kind = ctx.get("kind", "general")
    if ctx.get("interpretation_clarify"):
        return DimensionResult(
            InterpretationStatus.AMBIGUOUS,
            value=kind,
            reason=ctx.get("interpretation_clarify_reason") or "clarify",
            source=source,
        )
    if kind == "general":
        return DimensionResult(
            InterpretationStatus.AMBIGUOUS,
            value=kind,
            reason="no specific verb matched",
            source=source,
        )
    return DimensionResult(InterpretationStatus.MATCHED, value=kind, source=source)


def build_speech_dimension(ctx: dict) -> DimensionResult:
    speech = ctx.get("player_speech")
    if speech:
        return DimensionResult(InterpretationStatus.MATCHED, value=speech[:120], source="regex")
    if ctx.get("compound_dropped") and ctx.get("kind") in ("talk", "ask_about"):
        return DimensionResult(
            InterpretationStatus.AMBIGUOUS,
            value=None,
            reason="compound action — speech unsafe",
        )
    kind = ctx.get("kind", "general")
    if kind in ("talk", "ask_about", "ask_name", "personal_talk") and not speech:
        return DimensionResult(
            InterpretationStatus.ABSENT,
            value=None,
            reason="dialogue kind but no safe quote reconstructed",
        )
    return DimensionResult(InterpretationStatus.ABSENT, value=None, reason="no speech expected")


def build_target_dimension(ctx: dict) -> DimensionResult:
    tr = ctx.get("target_resolution") or {}
    status = tr.get("status")
    if status:
        return DimensionResult(
            InterpretationStatus(status),
            value=tr.get("npc_id"),
            reason=tr.get("reason") or "",
            source="constraint",
            candidates=tr.get("candidate_ids") or [],
        )
    if ctx.get("self_target"):
        return DimensionResult(
            InterpretationStatus.MATCHED,
            value="player",
            reason="self-target",
            source="preprocess",
        )
    if ctx.get("object_ref"):
        return DimensionResult(
            InterpretationStatus.MATCHED,
            value=ctx["object_ref"],
            reason="object target",
            source="preprocess",
        )
    tid = ctx.get("target_id")
    if tid:
        return DimensionResult(InterpretationStatus.MATCHED, value=tid, source="regex")
    if ctx.get("target_constraint_failed"):
        return DimensionResult(
            InterpretationStatus.ABSENT,
            value=None,
            reason="constraint unsatisfied",
            source="constraint",
        )
    return DimensionResult(InterpretationStatus.ABSENT, value=None, reason="no npc target")


def build_topic_dimension(ctx: dict) -> DimensionResult:
    topic = ctx.get("ask_topic")
    ttype = ctx.get("topic_type")
    if ctx.get("topic_knowledge_blocked"):
        return DimensionResult(
            InterpretationStatus.ABSENT,
            value=topic,
            reason=f"topic_knowledge:{ctx.get('topic_knowledge', 'unknown')}",
            source="topic_resolution",
        )
    if topic and ttype == "vague":
        return DimensionResult(
            InterpretationStatus.AMBIGUOUS,
            value=topic,
            reason="vague topic",
            source="topic_resolution",
        )
    if topic:
        return DimensionResult(
            InterpretationStatus.MATCHED,
            value=topic,
            reason=ttype or "general",
            source="topic_resolution",
        )
    kind = ctx.get("kind", "general")
    if kind == "ask_about":
        return DimensionResult(
            InterpretationStatus.ABSENT,
            value=None,
            reason="ask_about without resolved topic",
        )
    return DimensionResult(InterpretationStatus.ABSENT, value=None, reason="no topic slot")


def build_interpretation_trace(ctx: dict) -> dict:
    bc = ctx.get("boundary_classifier") or {}
    source = "classifier" if ctx.get("classifier_applied") else "regex"
    if ctx.get("interpretation_clarify"):
        source = "preprocess"

    trace = {
        "kind": build_kind_dimension(ctx, source=source).to_dict(),
        "target": build_target_dimension(ctx).to_dict(),
        "speech": build_speech_dimension(ctx).to_dict(),
        "topic": build_topic_dimension(ctx).to_dict(),
        "preprocess": ctx.get("interpretation_preprocess") or {},
        "negation_detected": bool((ctx.get("interpretation_preprocess") or {}).get("negation_detected")),
        "classifier_abstain": bool(ctx.get("classifier_abstain")),
        "classifier_confidence": ctx.get("classifier_confidence"),
        "clarify": bool(ctx.get("interpretation_clarify")),
        "clarify_reason": ctx.get("interpretation_clarify_reason"),
        "referents_resolved": ctx.get("referents_resolved"),
        "give_amount": ctx.get("give_amount"),
        "trade_quantity": ctx.get("trade_quantity"),
        "inventory_missing": ctx.get("inventory_missing"),
        "topic_knowledge": ctx.get("topic_knowledge"),
        "duplicate_action": bool(ctx.get("duplicate_action")),
        "manner": ctx.get("manner"),
        "intent_echo": ctx.get("intent_echo"),
        "mislabel_resolution": ctx.get("mislabel_resolution"),
        "impossible_action": ctx.get("impossible_action"),
        "conversational_loop": ctx.get("conversational_loop"),
        "stale_repetition": ctx.get("stale_repetition"),
        "declared_deception": ctx.get("declared_deception"),
    }
    if ctx.get("target_resolution"):
        trace["target_resolution"] = ctx["target_resolution"]
    if bc:
        trace["classifier"] = {
            "mode": bc.get("mode"),
            "invoked": bc.get("invoked"),
            "disagrees": bc.get("disagrees"),
            "skip_reason": bc.get("skip_reason"),
        }
    return trace


def resolve_stale_or_dead_referent(action, player, present, npcs, ctx: dict) -> bool:
    from simulation.target_resolution import find_npc_by_name_in_text

    present_ids = {n["id"] for n in present}
    text = (action or "").lower()

    named = find_npc_by_name_in_text(action, npcs or {}, player) if npcs else None
    if named:
        return False

    focus = player.get("scene_focus")
    if not re.search(r"\b(her|him|she|he)\b", text) or not focus:
        return False
    if focus in present_ids:
        return False

    dead = (npcs or {}).get(focus, {})
    label = dead.get("name") or "They"
    ctx["target_id"] = None
    ctx["dead_referent"] = focus if dead.get("status") != "alive" else None
    ctx["stale_referent"] = focus
    ctx["target_constraint_failed"] = True
    reason = "DEAD REFERENT" if dead.get("status") != "alive" else "STALE REFERENT"
    ctx["story_directive"] = (
        (ctx.get("story_directive") or "")
        + f" {reason} — {label} is not here to address. No ghost dialogue."
    ).strip()
    ctx.setdefault("interpretation_preprocess", {})["stale_referent"] = focus
    return True


def build_interpretation_clarify_scene(ctx: dict) -> str:
    reason = ctx.get("interpretation_clarify_reason") or "unclear intent"
    lines = [
        f"You hesitate — {reason}.",
        "",
        "Say what you mean plainly, or type /help for commands.",
    ]
    pre = ctx.get("interpretation_preprocess") or {}
    if pre.get("conditional"):
        lines.insert(1, "State what you do now — conditions can't be evaluated in one beat.")
    return "\n".join(lines)


def attach_economy_quantities(action, player, ctx: dict, *, npcs=None, present=None):
    """Parse give/trade quantities into action_ctx for mechanics + trace."""
    text = action or ""
    kind = ctx.get("kind", "general")
    if kind in ("give", "trade") or re.search(r"\b(?:give|pay|offer|buy|purchase)\b", text, re.I):
        from simulation.economy_engine import parse_give_amount
        amount = parse_give_amount(text, player)
        if amount > 0:
            ctx["give_amount"] = amount

    from simulation.topic_resolution import extract_ask_topic
    topic, ttype = extract_ask_topic(text)
    if topic:
        ctx["ask_topic"] = topic
        ctx["topic_type"] = ttype
    m_qty = re.search(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
        r"(?:loaves|loaf|loaves of bread|bread|coins?|silver|copper|gold|potions?)\b",
        text,
        re.I,
    )
    if m_qty:
        word = m_qty.group(1).lower()
        nums = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }
        qty = nums.get(word, int(word) if word.isdigit() else 1)
        ctx["trade_quantity"] = qty

    attach_inventory_checks(action, player, ctx)


_ITEM_QUERY = re.compile(
    r"\b(?:show|present|read|use|display|equip|drink|consume|eat|flash|produce|"
    r"hand\s+(?:her|him|them|the\s+\w+)\s+(?:the\s+)?|"
    r"give\s+(?:her|him|them)\s+(?:the\s+)?)\s*"
    r"(?:the\s+|a\s+|an\s+|my\s+)?(?P<item>[\w'-]+(?:\s+[\w'-]+){0,3})\b",
    re.I,
)
_UNLOCK = re.compile(
    r"\bunlock\s+(?:the\s+)?(?P<target>door|gate|chest|lock|box|cell|wardrobe)\b",
    re.I,
)
_UNLOCK_WITH = re.compile(
    r"\b(?:with|using)\s+(?:the\s+|a\s+|an\s+|my\s+)?(?P<item>[\w'-]+(?:\s+[\w'-]+){0,2})\b",
    re.I,
)
_ITEM_STOP = frozenset({
    "her", "him", "them", "me", "you", "it", "that", "this", "room", "around",
    "door", "gate", "way", "north", "south", "east", "west", "something", "anything",
})


def _inventory_name_tokens(player, area_id=None):
    tokens = set()
    for item in player.get("inventory") or []:
        if not isinstance(item, dict):
            continue
        for field in ("name", "label", "id"):
            val = item.get(field)
            if val:
                for t in re.findall(r"[a-z0-9]+", str(val).lower()):
                    if len(t) > 1:
                        tokens.add(t)
    for iid in (player.get("equipment") or {}).values():
        if not iid:
            continue
        for item in player.get("inventory") or []:
            if isinstance(item, dict) and item.get("id") == iid:
                for field in ("name", "label"):
                    val = item.get(field)
                    if val:
                        for t in re.findall(r"[a-z0-9]+", str(val).lower()):
                            if len(t) > 1:
                                tokens.add(t)
    if area_id:
        for rec in ((player.get("narrator_items") or {}).get(area_id) or {}).values():
            for t in rec.get("tokens") or []:
                tokens.add(t.lower())
            label = rec.get("label") or ""
            for t in re.findall(r"[a-z0-9]+", label.lower()):
                if len(t) > 1:
                    tokens.add(t)
    return tokens


def _item_query_matches_inventory(query, tokens):
    q_tokens = {
        t for t in re.findall(r"[a-z0-9]+", (query or "").lower())
        if len(t) > 1 and t not in _ITEM_STOP
    }
    if not q_tokens:
        return True
    if q_tokens <= tokens:
        return True
    return bool(q_tokens & tokens)


def attach_inventory_checks(action, player, ctx: dict):
    """Flag actions referencing items the protagonist does not possess."""
    text = action or ""
    if not text.strip():
        return

    area_id = player.get("area")
    tokens = _inventory_name_tokens(player, area_id)
    missing = []

    for m in _ITEM_QUERY.finditer(text):
        item = (m.group("item") or "").strip()
        if not item or item.lower() in _ITEM_STOP:
            continue
        if not _item_query_matches_inventory(item, tokens):
            missing.append(item)

    um = _UNLOCK.search(text)
    if um:
        key_m = _UNLOCK_WITH.search(text)
        if key_m:
            key = key_m.group("item")
            if key and not _item_query_matches_inventory(key, tokens):
                missing.append(key)
        elif not any(t in tokens for t in ("key", "keys")):
            ctx["inventory_missing"] = list(dict.fromkeys(missing or [um.group("target") + " key"]))
            ctx["story_directive"] = (
                (ctx.get("story_directive") or "")
                + " NO KEY — protagonist lacks a key for that lock; show failed attempt, no phantom unlock."
            ).strip()
            return

    if missing:
        unique = list(dict.fromkeys(missing))
        ctx["inventory_missing"] = unique
        labels = ", ".join(unique[:3])
        ctx["story_directive"] = (
            (ctx.get("story_directive") or "")
            + f" MISSING ITEM — protagonist does not have {labels!r} in pack or pockets."
            + " Show empty hands or refusal — do NOT invent the item."
        ).strip()


def detect_duplicate_action(action, player) -> bool:
    """True when player repeats the same input as the prior journal beat."""
    journal = player.get("journal") or []
    if not journal:
        return False
    last = journal[-1]
    if last.get("target_ambiguous") or last.get("interpretation_clarify"):
        return False

    def _norm(text):
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    return _norm(action) == _norm(last.get("action")) and bool(_norm(action))


def apply_duplicate_action_guard(action, player, ctx: dict) -> bool:
    """Set clarify on repeated identical input. Returns True if duplicate."""
    if not detect_duplicate_action(action, player):
        return False
    ctx["duplicate_action"] = True
    ctx["interpretation_clarify"] = True
    ctx["interpretation_clarify_reason"] = "same action as last beat — nothing new happened"
    ctx["story_directive"] = (
        (ctx.get("story_directive") or "")
        + " DUPLICATE INPUT — protagonist already tried that; show impatience or no change, not a fresh outcome."
    ).strip()
    return True


def run_interpretation_corpus(present=None, pl=None):
    """Run built-in action corpus for shadow/offline regression. Returns list of result dicts."""
    from simulation.action_interpreter import interpret_action
    from tests.fixtures.catalog_fixtures import npc, player

    corpus = [
        ("talk to the priest", "role_single"),
        ("Talk to the woman", "gender_constraint"),
        ("don't attack, just talk", "negation"),
        ("talk to myself", "self_target"),
        ("examine the bird", "object"),
        ("ask the temple about the relic", "place_as_person"),
        ("hit the road", "idiom_travel"),
        ("I kill him and take his keys", "narrated_outcome"),
        ("can I attack him?", "permission"),
        ("tlak to the guard", "typo"),
        ("tell everyone to leave", "group"),
        ("give her 5 silver", "quantity"),
        ("if she lies, attack her", "conditional"),
        ("examine it", "anaphora_it"),
        ("go there", "anaphora_there"),
        ("", "empty"),
    ]
    present = present or [
        npc("p1", role="priest", name="Hale", gender="male"),
        npc("g1", role="guard", name="Holt", gender="male"),
        npc("w1", role="merchant", name="Mara", gender="female"),
    ]
    pl = pl or player(scene_focus="g1", wealth=50)
    pl["referent_stack"] = [
        {"key": "object:knife", "type": "object", "ref": "knife", "label": "knife"},
        {"key": "place:cellar", "type": "place", "id": "cellar", "label": "cellar"},
    ]
    world = {"time_of_day": "day", "weather": "Clear"}
    rows = []
    for action, tag in corpus:
        pre = preprocess_action(action)
        ctx = interpret_action(action, pl, present, world)
        rows.append({
            "tag": tag,
            "action": action[:80],
            "kind": ctx.get("kind"),
            "clarify": bool(ctx.get("interpretation_clarify")),
            "negation": pre.negation_detected,
        })
    return rows
