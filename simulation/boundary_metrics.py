"""
Boundary instrumentation — measure classifier and fact-emission contract compliance.

Feeds turn_trace, journal, session stats, and bug_ledger shape tagging.
"""

import logging
import re

from simulation.bug_ledger import BugShape, tag_bug
from simulation.narrator_facts import parse_narrator_facts
from simulation.scheduled_events import extract_event_promises, list_pending_events, parse_schedule_tags

log = logging.getLogger(__name__)

_DIALOGUE_KINDS = frozenset({
    "talk", "ask_about", "ask_name", "personal_talk", "threaten", "help",
    "give", "trade", "insult", "show_respect", "accuse", "blackmail", "confess",
})

_WHEN_PATTERN = re.compile(r"\b(when|wait for|until)\b", re.I)


def facts_expected_for_beat(kind, action_ctx=None):
    """True when structured fact tags should appear in narrator output."""
    ctx = action_ctx or {}
    kind = kind or ctx.get("kind") or "general"
    if kind in _DIALOGUE_KINDS and (ctx.get("target_id") or ctx.get("focal_npc_id")):
        return True
    if kind == "wait" and ctx.get("wait_target"):
        return True
    action = (ctx.get("action_summary") or "")
    if _WHEN_PATTERN.search(action) and kind in ("ask_about", "talk", "wait", "general"):
        return True
    if ctx.get("time_target_hint"):
        return True
    return False


def summarize_fact_emission(facts):
    """Compact summary of parsed narrator fact tags."""
    facts = facts or {}
    speaking = facts.get("speaking") or []
    death = facts.get("death") or []
    places = facts.get("places") or []
    schedules = facts.get("schedules") or []
    tag_count = len(speaking) + len(death) + len(places) + len(schedules)
    return {
        "tag_count": tag_count,
        "has_facts": tag_count > 0,
        "speaking": list(speaking),
        "death": list(death),
        "places": list(places),
        "schedule_count": len(schedules),
        "schedules": [
            {"id": s.get("id"), "label": s.get("label"), "hours": s.get("hours_from_now")}
            for s in schedules[:4]
        ],
    }


def schedule_emission_metrics(raw_scene):
    """Detect prose-only schedule promises missing structured tags."""
    promises = extract_event_promises(raw_scene or "")
    tags = parse_schedule_tags(raw_scene or "")
    regex_caps = [p for p in promises if p.get("source") == "regex"]
    return {
        "schedule_promised": bool(promises),
        "schedule_tagged": bool(tags),
        "schedule_untagged": bool(regex_caps) and not tags,
        "schedule_regex_captures": [
            {"id": p.get("id"), "label": p.get("label")} for p in regex_caps[:4]
        ],
    }


def build_classifier_diff(regex_ctx, validated):
    """Structured diff between regex and validated classifier output."""
    if not validated:
        return {}
    diffs = []
    if validated.get("kind") != regex_ctx.get("kind"):
        diffs.append({
            "field": "kind",
            "regex": regex_ctx.get("kind"),
            "classifier": validated.get("kind"),
        })
    if validated.get("target_id") != regex_ctx.get("target_id"):
        diffs.append({
            "field": "target_id",
            "regex": regex_ctx.get("target_id"),
            "classifier": validated.get("target_id"),
        })
    rs = regex_ctx.get("player_speech")
    cs = validated.get("player_speech")
    if cs and cs != rs:
        diffs.append({
            "field": "player_speech",
            "regex": (rs or "")[:80],
            "classifier": cs[:80],
        })
    return {
        "regex_kind": regex_ctx.get("kind"),
        "regex_target": regex_ctx.get("target_id"),
        "classifier_kind": validated.get("kind"),
        "classifier_target": validated.get("target_id"),
        "diffs": diffs,
        "disagrees": bool(diffs),
    }


def classifier_metrics_from_ctx(action_ctx):
    """Extract classifier boundary metrics already stored on action_ctx."""
    ctx = action_ctx or {}
    bc = ctx.get("boundary_classifier") or {}
    shadow = ctx.get("classifier_shadow")
    if shadow and not bc.get("validated"):
        bc = dict(bc)
        bc["validated"] = shadow
    return bc


def build_output_boundary(
    *,
    kind,
    action_ctx,
    raw_scene,
    prose_issues,
    fact_issues,
    prose_retry=0,
    focal_id=None,
    auditor_issues=None,
    auditor_meta=None,
    regen_meta=None,
):
    """Metrics from narrator output validation."""
    facts = parse_narrator_facts(raw_scene or "")
    emission = summarize_fact_emission(facts)
    expected = facts_expected_for_beat(kind, action_ctx)
    missing = expected and not emission["has_facts"]
    am = auditor_meta or {}
    rg = regen_meta or {}
    auditor_count = len(auditor_issues or [])
    schedule = schedule_emission_metrics(raw_scene)
    return {
        "facts": emission,
        "facts_expected": expected,
        "facts_missing": missing,
        "schedule_promised": schedule.get("schedule_promised"),
        "schedule_tagged": schedule.get("schedule_tagged"),
        "schedule_untagged": schedule.get("schedule_untagged"),
        "schedule_regex_captures": schedule.get("schedule_regex_captures") or [],
        "prose_issue_count": len(prose_issues or []),
        "fact_issue_count": len(fact_issues or []),
        "auditor_issue_count": auditor_count,
        "auditor_invoked": bool(am.get("invoked")),
        "auditor_nominations": am.get("nominations", 0),
        "auditor_confirmed": am.get("confirmed", 0),
        "auditor_dropped": am.get("dropped", 0),
        "auditor_mode": am.get("mode", "off"),
        "prose_retry": prose_retry or 0,
        "regenerated": bool(prose_retry),
        "regen_exhausted": bool(rg.get("exhausted")),
        "gate_active": bool(prose_issues or fact_issues or auditor_count),
        "focal_id": focal_id,
    }


def classify_issue_shape(issue_text):
    """Map a validation issue string to bug shape A/B/C/D."""
    text = (issue_text or "").lower()
    if not text:
        return None
    if text.startswith("auditor confirmed"):
        return BugShape.PHANTOM_STATE
    if text.startswith("fact ") or "fact tag" in text or "fact death" in text:
        return BugShape.PHANTOM_STATE
    if "death" in text or "corpse" in text or "living npc" in text:
        return BugShape.PHANTOM_STATE
    if "speaking" in text and ("cast" in text or "focal" in text):
        return BugShape.PHANTOM_STATE
    if "role address switched" in text or "wrong speaker" in text or "focal npc" in text:
        return BugShape.STATE_RECOMPUTE
    if "location lock" in text or "place drift" in text:
        return BugShape.PHANTOM_STATE
    if "investigate beat has" in text:
        return BugShape.STATE_RECOMPUTE
    return BugShape.PHANTOM_STATE


def tag_turn_issues(prose_issues, fact_issues, action_ctx, boundary, auditor_issues=None):
    """Tag all turn issues with bug shapes for ledger / debug."""
    tagged = []
    for issue in prose_issues or []:
        shape = classify_issue_shape(issue)
        if shape:
            tagged.append(tag_bug(shape, issue))
    for issue in fact_issues or []:
        tagged.append(tag_bug(BugShape.PHANTOM_STATE, issue))
    for issue in auditor_issues or []:
        tagged.append(tag_bug(BugShape.PHANTOM_STATE, issue))
    ba = (action_ctx or {}).get("boundary_auditor") or {}
    if ba.get("invoked") and ba.get("mode") == "shadow" and ba.get("confirmed", 0) > 0:
        tagged.append(tag_bug(
            BugShape.SCRAPE_MISS,
            f"auditor shadow would confirm {ba.get('confirmed')} nomination(s)",
        ))
    bc = (action_ctx or {}).get("boundary_classifier") or {}
    if bc.get("disagrees"):
        summary = "; ".join(
            f"{d.get('field')}:{d.get('regex')!r}→{d.get('classifier')!r}"
            for d in (bc.get("diffs") or [])
        )
        tagged.append(tag_bug(
            BugShape.SCRAPE_MISS,
            f"classifier shadow disagrees with regex: {summary}",
        ))
    if boundary.get("facts_missing"):
        tagged.append(tag_bug(
            BugShape.DIRECTIVE_HOPE,
            "structured fact tags expected for this beat but none emitted",
        ))
    if boundary.get("schedule_untagged"):
        caps = boundary.get("schedule_regex_captures") or []
        label = caps[0].get("label") if caps else "timed event"
        tagged.append(tag_bug(
            BugShape.DIRECTIVE_HOPE,
            f"schedule promise in prose ({label}) without [SCHEDULE] tag",
        ))
    return tagged


def build_turn_boundary(action_ctx, output_boundary):
    """Merge input (classifier) and output (facts) boundary metrics for one turn."""
    classifier = classifier_metrics_from_ctx(action_ctx)
    merged = {
        "classifier_mode": classifier.get("mode", "off"),
        "classifier_invoked": bool(classifier.get("invoked")),
        "classifier_applied": bool((action_ctx or {}).get("classifier_applied")),
        "classifier_disagrees": bool(classifier.get("disagrees")),
        "classifier_diffs": classifier.get("diffs") or [],
        "classifier_skip_reason": classifier.get("skip_reason"),
        "classifier_error": classifier.get("error"),
    }
    if output_boundary:
        merged.update(output_boundary)
    return merged


def update_session_boundary_stats(player, turn_boundary, tagged_issues=None):
    """Rolling session counters on player save for shadow-mode review."""
    if player is None or not turn_boundary:
        return
    stats = player.setdefault("boundary_stats", {})
    stats["turns"] = stats.get("turns", 0) + 1
    if turn_boundary.get("classifier_invoked"):
        stats["classifier_invoked"] = stats.get("classifier_invoked", 0) + 1
    if turn_boundary.get("classifier_disagrees"):
        stats["classifier_disagrees"] = stats.get("classifier_disagrees", 0) + 1
    if turn_boundary.get("classifier_applied"):
        stats["classifier_applied"] = stats.get("classifier_applied", 0) + 1
    if turn_boundary.get("facts", {}).get("has_facts"):
        stats["facts_emitted"] = stats.get("facts_emitted", 0) + 1
    if turn_boundary.get("facts_expected"):
        stats["facts_expected"] = stats.get("facts_expected", 0) + 1
    if turn_boundary.get("facts_missing"):
        stats["facts_missing"] = stats.get("facts_missing", 0) + 1
    if turn_boundary.get("gate_active"):
        stats["gate_violations"] = stats.get("gate_violations", 0) + 1
    if turn_boundary.get("regenerated"):
        stats["regenerations"] = stats.get("regenerations", 0) + 1
    if turn_boundary.get("auditor_invoked"):
        stats["auditor_invoked"] = stats.get("auditor_invoked", 0) + 1
    if turn_boundary.get("auditor_confirmed"):
        stats["auditor_confirmed"] = stats.get("auditor_confirmed", 0) + turn_boundary.get("auditor_confirmed", 0)
    if turn_boundary.get("auditor_nominations"):
        stats["auditor_nominations"] = stats.get("auditor_nominations", 0) + turn_boundary.get("auditor_nominations", 0)
    if turn_boundary.get("regen_exhausted"):
        stats["regen_exhausted"] = stats.get("regen_exhausted", 0) + 1
    if turn_boundary.get("classifier_mode"):
        stats["classifier_mode"] = turn_boundary["classifier_mode"]
    if turn_boundary.get("auditor_mode"):
        stats["auditor_mode"] = turn_boundary["auditor_mode"]
    if turn_boundary.get("schedule_untagged"):
        stats["schedule_untagged"] = stats.get("schedule_untagged", 0) + 1
    if tagged_issues:
        shapes = stats.setdefault("issue_shapes", {})
        for t in tagged_issues:
            sh = t.get("shape", "?")
            shapes[sh] = shapes.get(sh, 0) + 1
    player["boundary_stats"] = stats


def log_boundary_turn(tick, turn_boundary, tagged_issues=None):
    """Python log line for shadow-mode sessions without debug API."""
    if not turn_boundary:
        return
    parts = [
        f"mode={turn_boundary.get('classifier_mode', 'off')}",
    ]
    if turn_boundary.get("classifier_invoked"):
        parts.append(f"clf_disagree={turn_boundary.get('classifier_disagrees')}")
    parts.append(f"facts={turn_boundary.get('facts', {}).get('tag_count', 0)}")
    if turn_boundary.get("facts_missing"):
        parts.append("facts_missing")
    if turn_boundary.get("gate_active"):
        parts.append(
            f"violations={turn_boundary.get('prose_issue_count', 0)}+"
            f"{turn_boundary.get('fact_issue_count', 0)}+"
            f"{turn_boundary.get('auditor_issue_count', 0)}"
        )
    if turn_boundary.get("auditor_invoked"):
        parts.append(
            f"audit={turn_boundary.get('auditor_confirmed', 0)}/"
            f"{turn_boundary.get('auditor_nominations', 0)}"
        )
    if tagged_issues:
        shapes = sorted({t.get("shape") for t in tagged_issues})
        parts.append(f"shapes={','.join(shapes)}")
    log.info("boundary tick=%s %s", tick, " ".join(parts))


def _boundary_history_cap():
    import os
    raw = os.environ.get("AISTORY_BOUNDARY_HISTORY", "20")
    try:
        return max(0, min(100, int(raw)))
    except ValueError:
        return 20


def summarize_player_boundary_history(history):
    """Aggregate counters from persisted player boundary_history."""
    hist = history or []
    if not hist:
        return {}
    n = len(hist)
    invoked = sum(
        1 for h in hist
        if (h.get("boundary") or {}).get("classifier_invoked")
    )
    disagrees = sum(
        1 for h in hist
        if (h.get("boundary") or {}).get("classifier_disagrees")
    )
    facts_emitted = sum(
        1 for h in hist
        if (h.get("boundary") or {}).get("facts", {}).get("has_facts")
    )
    facts_expected = sum(
        1 for h in hist if (h.get("boundary") or {}).get("facts_expected")
    )
    facts_missing = sum(
        1 for h in hist if (h.get("boundary") or {}).get("facts_missing")
    )
    gate = sum(1 for h in hist if (h.get("boundary") or {}).get("gate_active"))
    auditor_invoked = sum(
        1 for h in hist if (h.get("boundary") or {}).get("auditor_invoked")
    )
    auditor_confirmed = sum(
        (h.get("boundary") or {}).get("auditor_confirmed", 0) for h in hist
    )
    return {
        "turns_in_history": n,
        "classifier_invoked": invoked,
        "classifier_disagrees": disagrees,
        "facts_emitted": facts_emitted,
        "facts_expected": facts_expected,
        "facts_missing": facts_missing,
        "gate_violations": gate,
        "classifier_invoked_rate": round(invoked / n, 3) if n else 0,
        "facts_emission_rate": round(facts_emitted / n, 3) if n else 0,
        "auditor_invoked": auditor_invoked,
        "auditor_confirmed_total": auditor_confirmed,
        "facts_miss_rate": round(facts_missing / facts_expected, 3) if facts_expected else 0,
    }


def persist_boundary_trace(
    player,
    *,
    tick,
    action,
    kind,
    turn_boundary,
    tagged_issues=None,
    action_ctx=None,
    scene_cast_ids=None,
):
    """Persist per-turn boundary detail on player save for offline debug_state."""
    if player is None or not turn_boundary:
        return
    ctx = action_ctx or {}
    bc = ctx.get("boundary_classifier") or {}
    ba = ctx.get("boundary_auditor") or {}
    detail = {
        "tick": tick,
        "action": (action or "")[:120],
        "kind": kind,
        "subplace": (player.get("scene_subplace") or {}).get("id"),
        "scene_cast_ids": list(scene_cast_ids or []),
        "boundary": turn_boundary,
        "classifier": {
            "mode": turn_boundary.get("classifier_mode") or bc.get("mode"),
            "invoked": turn_boundary.get("classifier_invoked"),
            "disagrees": turn_boundary.get("classifier_disagrees"),
            "applied": turn_boundary.get("classifier_applied"),
            "diffs": turn_boundary.get("classifier_diffs") or bc.get("diffs") or [],
            "skip_reason": turn_boundary.get("classifier_skip_reason") or bc.get("skip_reason"),
            "error": turn_boundary.get("classifier_error") or bc.get("error"),
        },
        "auditor": {
            "mode": turn_boundary.get("auditor_mode") or ba.get("mode"),
            "invoked": turn_boundary.get("auditor_invoked"),
            "nominations": turn_boundary.get("auditor_nominations"),
            "confirmed": turn_boundary.get("auditor_confirmed"),
            "dropped": turn_boundary.get("auditor_dropped"),
            "dropped_samples": ba.get("dropped_samples") or [],
        },
        "facts": turn_boundary.get("facts") or {},
        "facts_expected": turn_boundary.get("facts_expected"),
        "facts_missing": turn_boundary.get("facts_missing"),
        "gate_active": turn_boundary.get("gate_active"),
        "prose_retry": turn_boundary.get("prose_retry"),
        "regen_exhausted": turn_boundary.get("regen_exhausted"),
        "tagged_issues": (tagged_issues or [])[:12],
        "reloc": {
            "relocated": bool(ctx.get("relocated")),
            "left_behind_cast": list(ctx.get("left_behind_cast") or []),
        },
        "scheduled_events_pending": len(list_pending_events(player, player.get("area"))),
    }
    player["last_boundary_trace"] = detail
    hist = player.setdefault("boundary_history", [])
    hist.append(detail)
    cap = _boundary_history_cap()
    if cap > 0:
        player["boundary_history"] = hist[-cap:]
    else:
        player["boundary_history"] = []
