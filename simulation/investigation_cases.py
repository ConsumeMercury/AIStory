"""
Multi-stage investigations — emergent mysteries from existing NPCs, secrets, schedules.
"""

import random
import uuid

from storage import load, save
from generation.npc_secrets import hidden_secrets

PLAYER_FILE = "player/player.json"
NPC_FILE = "characters/npcs.json"


def _pick_npcs(area_id, npcs, count, exclude=None):
    exclude = set(exclude or [])
    pool = [
        n for n in npcs.values()
        if n.get("status") == "alive" and n.get("area") == area_id and n["id"] not in exclude
    ]
    if len(pool) < count:
        return pool
    return random.sample(pool, count)


def _victim_exclusions(player, present_ids):
    """NPCs who must never be chosen as a murder victim."""
    exclude = set(present_ids or [])
    focus = player.get("scene_focus")
    if focus:
        exclude.add(focus)
    pipeline = player.get("starting_pipeline") or {}
    for nid in pipeline.get("key_npc_ids") or []:
        if nid in present_ids:
            exclude.add(nid)
    return exclude


def _pick_victim(area_id, npcs, player, present_ids):
    """
    Murder victim must be dead (or marked dead off-screen) and never someone
    the player is currently talking to or can see.
    """
    exclude = _victim_exclusions(player, present_ids)

    dead_here = [
        n for n in npcs.values()
        if n.get("status") == "dead"
        and n.get("area") == area_id
        and n["id"] not in exclude
    ]
    if dead_here:
        return random.choice(dead_here), False

    off_screen = [
        n for n in npcs.values()
        if n.get("status") == "alive"
        and n.get("area") == area_id
        and n["id"] not in exclude
    ]
    if not off_screen:
        return None, False

    victim = random.choice(off_screen)
    victim["status"] = "dead"
    return victim, True


def generate_mystery(area_id, npcs, areas, *, player=None, present_ids=None, kind="murder"):
    """Build a case from local NPCs."""
    player = player or {}
    present_ids = present_ids or []
    victim, npcs_changed = _pick_victim(area_id, npcs, player, present_ids)
    if not victim:
        return None, npcs_changed

    here = _pick_npcs(area_id, npcs, 4, exclude={victim["id"]})
    if len(here) < 1:
        return None, npcs_changed

    others = [n for n in here if n["id"] != victim["id"]]
    suspects = random.sample(others, k=min(2, len(others))) if others else []
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
        "kind": "murder",
        "area_id": area_id,
        "title": (
            f"Death in {areas.get(area_id, {}).get('name', 'the district')}"
            if kind == "murder"
            else "Local mystery"
        ),
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
    return case, npcs_changed


def is_active_case_invalid(case, player, npcs, present_ids=None):
    """True when a saved case violates murder-victim rules."""
    if not case or case.get("solved"):
        return False
    victim_id = case.get("victim_id")
    if not victim_id or victim_id not in npcs:
        return True
    victim = npcs[victim_id]
    present_ids = present_ids or []
    exclude = _victim_exclusions(player, present_ids)
    if victim_id in exclude:
        return True
    if case.get("kind", "murder") == "murder":
        if victim.get("status") == "alive" and (
            victim_id in present_ids or victim_id == player.get("scene_focus")
        ):
            return True
    return False


def sanitize_active_case(player, npcs, areas, *, present_ids=None):
    """Drop and rebuild an active case that violates victim rules."""
    case = player.get("active_case")
    if not case or case.get("solved"):
        return case, False
    if not is_active_case_invalid(case, player, npcs, present_ids):
        return case, False

    area_id = case.get("area_id") or player.get("area")
    player.pop("active_case", None)
    new_case, npcs_changed = generate_mystery(
        area_id, npcs, areas, player=player, present_ids=present_ids or [],
    )
    if new_case:
        player["active_case"] = new_case
    return new_case, npcs_changed


def ensure_case(player, area_id, npcs, areas, *, present_ids=None):
    """Return active case or generate one on first investigation."""
    _, npcs_changed = sanitize_active_case(
        player, npcs, areas, present_ids=present_ids,
    )
    case = player.get("active_case")
    if case and not case.get("solved") and case.get("area_id") == area_id:
        return case, npcs_changed
    if case and not case.get("solved"):
        return case, npcs_changed
    new_case, changed = generate_mystery(
        area_id, npcs, areas, player=player, present_ids=present_ids,
    )
    if new_case:
        player["active_case"] = new_case
    return new_case, npcs_changed or changed


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


def case_narrator_block(player, npcs, *, present_ids=None):
    case = player.get("active_case")
    if not case or case.get("solved"):
        return ""
    present_ids = set(present_ids or [])
    victim_id = case.get("victim_id")
    victim_rec = npcs.get(victim_id, {})
    victim_alive = victim_rec.get("status") == "alive"
    victim_present = victim_id in present_ids
    victim_name = case.get("victim_name") or victim_rec.get("name", "someone")

    if victim_alive and victim_present:
        victim_line = (
            "An off-screen death in this district — do NOT treat anyone present as the corpse. "
            f"The case file names {victim_name} as victim, but that person is alive here; "
            "clues must come from the environment, not from them narrating the mystery."
        )
    elif victim_alive:
        victim_line = f"victim {victim_name} (off-screen, not present)"
    else:
        victim_line = f"victim {victim_name} (dead — body or aftermath only, no dialogue from them)"

    discovered = [e for e in case.get("evidence", []) if e.get("discovered")]
    lines = [
        f"ACTIVE MYSTERY ({case.get('title', 'case')}): {victim_line}; "
        f"stage {case.get('stage', 0)+1}/4 — {case['stages'][min(case.get('stage', 0), 3)]}.",
    ]
    if discovered:
        lines.append(
            "Known clues (show as physical/overheard finds — not NPC monologue): "
            + "; ".join(e["text"][:60] for e in discovered[:3])
        )
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
