"""
Post-generation prose checks — run on live turns (log-only) and offline audits.
"""

import logging
import os
import re

log = logging.getLogger(__name__)

_DEATH_PROSE = re.compile(
    r"\b("
    r"corpse|lifeless body|slain|murdered (?:him|her)|"
    r"killed (?:him|her)|he is dead|she is dead|"
    r"fatal wound|bled out|stopped breathing|"
    r"body (?:went|falls?) still|death rattle"
    r")\b",
    re.I,
)

_ROLE_WORDS = {
    "scholar": ("scholar", "scribe", "academic"),
    "priest": ("priest", "cleric", "monk", "chaplain"),
    "blacksmith": ("blacksmith", "smith", "forge"),
    "merchant": ("merchant", "trader", "stall"),
    "sailor": ("sailor", "dockhand", "crewman"),
    "guard": ("guard", "watchman", "soldier"),
}

_FOCAL_DIALOGUE_KINDS = frozenset({
    "talk", "personal_talk", "attack", "confess", "search", "ask_name",
    "show_respect", "insult", "threaten", "help", "give", "trade", "guild", "find",
})

_AMBIENT_GUARD = re.compile(
    r"\b(?:border|gate|city|harbor|harbour|dock|customs|night|warehouse|patrol)\s+guards?\b"
    r"|\bguards?\s+(?:at|on|by|near|from|under|posted|patrol)\b"
    r"|\b(?:two|three|several|many|a pair of)\s+guards?\b"
    r"|\b(?:like|as)\s+(?:a\s+)?(?:guard|watchman)\b"
    r"|\b(?:a|the|another|some)\s+(?:watchman|watchmen|patrol(?:man|men)?|customs officer)\b"
    r"|\b(?:watchman|patrol)\s+(?:in|with|wearing|rounds?|rounds the)\b",
    re.I,
)

_FOCAL_ROLE_MISLABEL = re.compile(
    r"\b(?:he|she|him|her)\s*,?\s*(?:the|a|an)\s+(?:guard|watchman|soldier|priest|scholar|blacksmith)\b"
    r"|\b(?:the|a|an)\s+(?:guard|watchman|soldier|priest|scholar|blacksmith)\s*,?\s*(?:he|she)\b",
    re.I,
)

_PLACE_MOVE = re.compile(
    r"\b(?:enter(?:ing)?|step(?:ping)? into|walk(?:ing)? into|arriv(?:e|ing|ed) at|"
    r"inside the|within the|reach(?:es|ed|ing)? the)\s+(?:the\s+)?([a-z][a-z\s\-']{2,28})",
    re.I,
)

_PLACE_SUBPARTS = frozenset({
    "room", "door", "hall", "corridor", "sanctuary", "office", "chapel", "nave",
    "cellar", "alcove", "threshold", "counter", "desk", "pew", "yard", "court",
    "street", "lane", "corner", "shadow", "light", "silence", "dark", "crowd",
})


def _focal_pronoun_pattern(gender):
    if gender == "female":
        return re.compile(r"\b(she|her)\b", re.I)
    if gender == "male":
        return re.compile(r"\b(he|him|his)\b", re.I)
    return re.compile(r"\b(she|her|he|him|his)\b", re.I)


def focal_referenced(text, npc):
    """True when prose likely describes the simulation focal NPC."""
    if not npc or not text:
        return False
    lower = text.lower()
    name = (npc.get("name") or "").lower()
    if name:
        for part in name.split():
            if len(part) > 2 and part in lower:
                return True
    gender = npc.get("gender")
    if gender == "female" and re.search(r"\b(she|her)\b", lower):
        return True
    if gender == "male" and re.search(r"\b(he|him|his)\b", lower):
        return True
    role = (npc.get("role") or "").lower()
    if role and role in lower:
        return True
    return False


def gender_mismatch(text, gender):
    """Flag when the focal NPC is mislabeled — not when another NPC is mentioned nearby."""
    if not gender:
        return None
    pron = _focal_pronoun_pattern(gender)
    if gender == "female":
        mislabel = re.compile(
            r"\b(?:she|her)\s*,?\s*(?:the|a|an)\s+(?:priest|blacksmith|guard|sailor)\b"
            r"|\b(?:the|a|an)\s+(?:priest|blacksmith|guard|sailor)\s*,?\s*she\b"
            r"|\b(?:he|him|his)\s+(?:said|voice|hand|arm|shoulder)\b.*\b(?:her name|her face)\b",
            re.I,
        )
        third_party = re.compile(
            r"\b(?:watch(?:es|ed|ing)?|glanc(?:e|es|ed|ing)|see(?:s|ing)?|spot(?:s|ted)?|"
            r"toward|past|at|near|from|behind|beside|by)\s+(?:the|a|an)\s+"
            r"(?:priest|blacksmith|guard|sailor|man|merchant)\b",
            re.I,
        )
    else:
        mislabel = re.compile(
            r"\b(?:he|him|his)\s*,?\s*(?:the|a|an)\s+(?:priest|blacksmith|scholar|woman)\b"
            r"|\b(?:the|a|an)\s+(?:woman|priest|scholar)\s*,?\s*he\b"
            r"|\b(?:she|her)\s+(?:said|voice)\b.*\b(?:his name|his face)\b",
            re.I,
        )
        third_party = re.compile(
            r"\b(?:watch(?:es|ed|ing)?|glanc(?:e|es|ed|ing)|see(?:s|ing)?|"
            r"toward|past|at|near|from|behind|beside|by)\s+(?:the|a|an)\s+"
            r"(?:woman|priest|scholar|merchant|girl)\b",
            re.I,
        )
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if not pron.search(sent):
            continue
        if third_party.search(sent):
            continue
        if mislabel.search(sent):
            return (
                "female focal but male-role/male-pronoun narration"
                if gender == "female"
                else "male focal but female-pronoun narration"
            )
    return None


def role_mismatch(text, role, gender, *, allow_roles=()):
    if not role:
        return None
    allowed = set(allow_roles or ())
    focal_words = _ROLE_WORDS.get(role, (role,))
    pron = _focal_pronoun_pattern(gender)
    for sent in re.split(r"(?<=[.!?])\s+", text):
        lower = sent.lower()
        if not pron.search(sent):
            continue
        if role in lower or any(w in lower for w in focal_words):
            continue
        if re.match(r"^\s*You\b", sent) and re.search(r"\bguards?\b", lower):
            continue
        for wrong_role, words in _ROLE_WORDS.items():
            if wrong_role == role or wrong_role in allowed:
                continue
            if wrong_role == "guard" and _AMBIENT_GUARD.search(sent):
                if not _FOCAL_ROLE_MISLABEL.search(sent):
                    continue
            if any(re.search(rf"\b{re.escape(w)}\b", lower) for w in words):
                return f"focal role is {role} but prose uses {wrong_role} imagery"
    return None


def place_drift(text, scene_place):
    """Flag when prose describes entering a place unlike the locked scene."""
    if not text or not scene_place:
        return None
    place_lower = scene_place.lower()
    place_tokens = {w for w in re.split(r"[\W_]+", place_lower) if len(w) > 3}
    for match in _PLACE_MOVE.finditer(text):
        dest = match.group(1).strip().lower()
        dest = re.sub(r"\s+(and|where|before|after|again)\b.*$", "", dest).strip()
        if not dest or dest in _PLACE_SUBPARTS:
            continue
        if dest in place_lower or any(tok in dest for tok in place_tokens):
            continue
        if any(tok in place_lower for tok in dest.split() if len(tok) > 3):
            continue
        return f"prose moves toward {dest!r} but LOCATION LOCK is {scene_place!r}"
    return None


def wrong_speaker_dialogue(text, focal_npc_id, present_npcs, npcs, known_ids=None):
    """Flag dialogue attributed to a non-focal or absent NPC."""
    if not text:
        return None
    present_ids = {n.get("id") for n in (present_npcs or [])}
    known_ids = set(known_ids or [])
    for nid, npc in (npcs or {}).items():
        if nid == focal_npc_id:
            continue
        name = (npc.get("name") or "").strip()
        if not name or len(name) < 3:
            continue
        if nid not in present_ids:
            scope = "absent"
        elif nid != focal_npc_id:
            scope = "non-focal"
        else:
            continue
        first = re.escape(name.split()[0])
        full = re.escape(name)
        patterns = (
            rf"\b{first}\s+(?:said|asked|replied|murmured|whispered|shouted)\b",
            r'"[^"]{4,}"\s*,?\s*(?:' + first + r"|" + full + r")\b",
        )
        for pat in patterns:
            if re.search(pat, text, re.I):
                return f"{scope} NPC {name!r} has attributed dialogue"
    return None


def analyze_prose(text, ctx, player, npcs):
    issues = []
    if not text or len(text) < 40:
        issues.append("scene too short or empty")
        return issues

    lower = text.lower()
    focus_id = ctx.get("target_id") or ctx.get("focal_npc_id") or player.get("scene_focus")
    npc = npcs.get(focus_id, {}) if focus_id else {}
    gender = npc.get("gender", "")
    role = npc.get("role", "")
    kind = ctx.get("kind")
    focal_ref = focal_referenced(text, npc)

    if kind in _FOCAL_DIALOGUE_KINDS and kind != "find" and focus_id and not focal_ref:
        issues.append("focal NPC not clearly referenced in scene prose")

    if focal_ref and kind in _FOCAL_DIALOGUE_KINDS:
        gm = gender_mismatch(text, gender)
        if gm:
            issues.append(gm)

        mismatch = role_mismatch(
            text, role, gender,
            allow_roles=ctx.get("allow_roles") or (),
        )
        if mismatch and kind in ("confess", "talk", "attack", "search", "find", "show_respect", "insult"):
            issues.append(mismatch)

    fatal = ctx.get("combat_fatal")
    if fatal is False and kind in ("attack", "confess", "search"):
        if _DEATH_PROSE.search(text):
            issues.append("non-fatal combat but prose describes death")

    if ctx.get("acquired_item") and kind == "search":
        name = (ctx["acquired_item"].get("name") or "").lower()
        if name and not any(w in lower for w in ("sword", "blade", "iron", "hilt", "notched")):
            issues.append(f"acquired {ctx['acquired_item'].get('name')} but prose omits weapon")

    if kind == "confess" and not re.search(r'"[^"]{4,}"', text):
        issues.append("confession beat but no quoted speech detected")

    scene_place = ctx.get("scene_place")
    drift = place_drift(text, scene_place)
    if drift:
        issues.append(drift)

    speaker = wrong_speaker_dialogue(
        text,
        focus_id,
        ctx.get("present_npcs") or [],
        npcs,
        known_ids=ctx.get("known_ids"),
    )
    if speaker:
        issues.append(speaker)

    if not focus_id and kind in _FOCAL_DIALOGUE_KINDS and re.search(r'"[^"]{8,}"', text):
        issues.append("no focal NPC but scene contains extended quoted dialogue")

    return issues


def build_beat_context(last, player, npcs):
    ctx = {
        "kind": last.get("kind"),
        "target_id": last.get("focus_npc"),
        "combat_fatal": (
            last.get("combat_fatal")
            if last.get("kind") == "attack"
            else player.get("last_combat_fatal")
        ),
        "acquired_item": player.get("last_acquired_item"),
    }
    if last.get("kind") == "confess" and not player.get("last_combat_fatal"):
        ctx["combat_fatal"] = False
    if last.get("kind") == "confess":
        victim = npcs.get(player.get("last_combat_target") or "", {})
        v_role = victim.get("role")
        if v_role:
            ctx["allow_roles"] = (v_role,)
    return ctx


def focus_role_switch_issue(player, action_ctx, journal, npcs):
    """Flag when a role address resolves to a different NPC than the last dialogue partner."""
    from simulation.target_resolution import action_mentions_role_or_descriptor

    if not journal:
        return None
    last = journal[-1]
    last_focus = last.get("focus_npc")
    new_focus = (action_ctx or {}).get("target_id") or (action_ctx or {}).get("focal_npc_id")
    if not last_focus or not new_focus or last_focus == new_focus:
        return None
    if last.get("kind") not in _FOCAL_DIALOGUE_KINDS:
        return None
    kind = (action_ctx or {}).get("kind")
    if kind not in _FOCAL_DIALOGUE_KINDS:
        return None
    action = (action_ctx or {}).get("action_summary") or ""
    present = (action_ctx or {}).get("present_npcs") or []
    if not action_mentions_role_or_descriptor(action, present=present):
        return None
    last_npc = (npcs or {}).get(last_focus, {})
    new_npc = (npcs or {}).get(new_focus, {})
    last_name = last_npc.get("name") or last_focus
    new_name = new_npc.get("name") or new_focus
    role = last_npc.get("role") or new_npc.get("role") or "role"
    return (
        f"role address switched focal NPC from {last_name!r} to {new_name!r} "
        f"(same {role!r} thread — likely wrong person)"
    )


def validate_scene_prose(text, *, player, npcs, action_ctx, focal_npc_id,
                         scene_place, present_npcs, known_ids=None):
    """Return human-readable prose validation issues for a live turn."""
    ctx = dict(action_ctx or {})
    ctx["focal_npc_id"] = focal_npc_id
    ctx["scene_place"] = scene_place
    ctx["present_npcs"] = present_npcs or []
    ctx["known_ids"] = known_ids or set()
    if focal_npc_id and not ctx.get("target_id"):
        ctx["target_id"] = focal_npc_id
    issues = analyze_prose(text, ctx, player, npcs)
    switch = focus_role_switch_issue(
        player, ctx, player.get("journal") or [], npcs,
    )
    if switch:
        issues.append(switch)
    return issues


def log_scene_prose_issues(text, *, player, npcs, action_ctx, focal_npc_id,
                           scene_place, present_npcs, known_ids=None):
    """Log prose anomalies; returns issue list. Never raises."""
    if not text or len(text) < 40:
        return []
    if os.environ.get("AISTORY_SKIP_PROSE_VALIDATION", "").lower() in ("1", "true", "yes"):
        return []
    issues = validate_scene_prose(
        text,
        player=player,
        npcs=npcs,
        action_ctx=action_ctx,
        focal_npc_id=focal_npc_id,
        scene_place=scene_place,
        present_npcs=present_npcs,
        known_ids=known_ids,
    )
    if not issues:
        return issues
    kind = (action_ctx or {}).get("kind", "?")
    action = (action_ctx or {}).get("action_summary") or ""
    log.warning(
        "Scene prose validation (%s %r focal=%s): %s",
        kind,
        action[:60],
        focal_npc_id,
        "; ".join(issues),
    )
    return issues
