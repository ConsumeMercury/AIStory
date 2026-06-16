"""
Multi-stage investigations — emergent mysteries from existing NPCs, secrets, schedules.
"""

import random
import uuid

from storage import load, save
from generation.npc_secrets import hidden_secrets

PLAYER_FILE = "player/player.json"


def _pick_npcs(area_id, npcs, count, exclude=None):
    exclude = set(exclude or [])
    pool = [
        n for n in npcs.values()
        if n.get("status") == "alive" and n.get("area") == area_id and n["id"] not in exclude
    ]
    if len(pool) < count:
        return pool
    return random.sample(pool, count)


def generate_mystery(area_id, npcs, areas, kind="murder"):
    """Build a case from local NPCs."""
    here = _pick_npcs(area_id, npcs, 4)
    if len(here) < 2:
        return None

    victim = random.choice(here)
    others = [n for n in here if n["id"] != victim["id"]]
    suspects = random.sample(others, k=min(2, len(others)))
    witnesses = [n for n in others if n not in suspects][:2]

    evidence = []
    for s in suspects:
        sched = s.get("schedule_label") or s.get("schedule_activity") or "somewhere"
        evidence.append({
            "id": str(uuid.uuid4())[:6],
            "type": "routine",
            "text": f"{s['name']} was {sched} near the time in question.",
            "points_to": s["id"],
            "discovered": False,
        })
        sec = hidden_secrets(s)
        if sec:
            evidence.append({
                "id": str(uuid.uuid4())[:6],
                "type": "secret",
                "text": f"Someone saw {s['name']} behaving as if they had something to hide.",
                "points_to": s["id"],
                "discovered": False,
            })

    case = {
        "id": str(uuid.uuid4())[:8],
        "kind": kind,
        "area_id": area_id,
        "title": f"Death in {areas.get(area_id, {}).get('name', 'the district')}" if kind == "murder" else "Local mystery",
        "stage": 0,
        "stages": ["learn what happened", "identify suspects", "find proof", "accuse or expose"],
        "victim_id": victim["id"],
        "victim_name": victim["name"],
        "suspect_ids": [s["id"] for s in suspects],
        "witness_ids": [w["id"] for w in witnesses],
        "evidence": evidence,
        "solved": False,
        "accused_id": None,
    }
    return case


def ensure_case(player, area_id, npcs, areas):
    """Return active case or generate one on first investigation."""
    case = player.get("active_case")
    if case and not case.get("solved") and case.get("area_id") == area_id:
        return case
    if case and not case.get("solved"):
        return case
    new_case = generate_mystery(area_id, npcs, areas)
    if new_case:
        player["active_case"] = new_case
    return new_case


def advance_case(player, action_kind, action_ctx, npcs):
    """Progress investigation stages from player actions."""
    case = player.get("active_case")
    if not case or case.get("solved"):
        return ""

    check = action_ctx.get("skill_check") or {}
    success = check.get("success", True)
    margin = check.get("margin", 0)
    tid = action_ctx.get("target_id")
    notes = []

    if action_kind in ("investigate", "observe", "examine") and success:
        for ev in case.get("evidence", []):
            if not ev.get("discovered") and random.random() < 0.45 + margin * 0.03:
                ev["discovered"] = True
                notes.append(f"Evidence: {ev['text']}")
                case["stage"] = max(case.get("stage", 0), 1)
                break

    if action_kind == "ask_about" and success and tid:
        if tid in case.get("witness_ids", []):
            notes.append(f"A witness ({npcs.get(tid, {}).get('name', '?')}) contradicts themselves under pressure.")
            case["stage"] = max(case.get("stage", 0), 2)
        elif tid in case.get("suspect_ids", []):
            notes.append(f"A suspect ({npcs.get(tid, {}).get('name', '?')}) grows defensive.")
            case["stage"] = max(case.get("stage", 0), 2)

    if action_kind == "accuse" and tid and success:
        if tid in case.get("suspect_ids", []):
            case["accused_id"] = tid
            case["solved"] = True
            case["stage"] = 3
            notes.append(
                f"Accusation lands on {npcs.get(tid, {}).get('name', 'the suspect')} — "
                f"the mystery may close, rightly or wrongly."
            )
        else:
            notes.append("Wrong accusation — trust burned, truth harder to find.")

    player["active_case"] = case
    return " ".join(notes)


def case_narrator_block(player, npcs):
    case = player.get("active_case")
    if not case or case.get("solved"):
        return ""
    victim = npcs.get(case.get("victim_id"), {}).get("name", "someone")
    discovered = [e for e in case.get("evidence", []) if e.get("discovered")]
    lines = [
        f"ACTIVE MYSTERY ({case.get('title', 'case')}): victim {victim}; "
        f"stage {case.get('stage', 0)+1}/4 — {case['stages'][min(case.get('stage', 0), 3)]}.",
    ]
    if discovered:
        lines.append("Known clues: " + "; ".join(e["text"][:60] for e in discovered[:3]))
    suspect_names = [npcs.get(s, {}).get("name", "?") for s in case.get("suspect_ids", [])[:3]]
    if suspect_names:
        lines.append(f"Suspects (do not invent others): {', '.join(suspect_names)}.")
    return "INVESTIGATION:\n" + "\n".join(lines)


def format_case_status(player, npcs):
    case = player.get("active_case")
    if not case:
        return "  No active investigation."
    if case.get("solved"):
        acc = npcs.get(case.get("accused_id"), {}).get("name", "?")
        return f"  Solved case: accused {acc}."
    lines = [f"  {case.get('title', 'Mystery')} — stage {case.get('stage', 0)+1}/4"]
    for ev in case.get("evidence", []):
        if ev.get("discovered"):
            lines.append(f"    • {ev['text'][:70]}")
    return "\n".join(lines)
