"""
AI prose auditor — nominates suspected violations; never decides alone.

Modes (AISTORY_PROSE_AUDITOR):
  off    — skip auditor (default)
  shadow — run auditor, log nominations + confirm/drop, do not add to gate
  on     — confirmed nominations feed deterministic fact_gate
"""

import json
import logging
import os
import re

from simulation.auditor_confirm import VALID_NOMINATION_TYPES

log = logging.getLogger(__name__)

_AUDITOR_MODES = frozenset({"off", "shadow", "on"})

_AUDIT_KINDS = frozenset({
    "talk", "ask_about", "ask_name", "personal_talk", "threaten", "help",
    "give", "trade", "insult", "show_respect", "accuse", "blackmail", "confess",
    "attack", "search", "find",
})


def auditor_mode():
    raw = (os.environ.get("AISTORY_PROSE_AUDITOR") or "off").strip().lower()
    return raw if raw in _AUDITOR_MODES else "off"


def _mock_auditor_json():
    return os.environ.get("AISTORY_MOCK_PROSE_AUDITOR_JSON", "").strip()


def should_audit_prose(action_ctx, scene_state, text, *, focal_npc_id=None):
    if auditor_mode() == "off":
        return False, "mode_off"
    if not text or len(text) < 80:
        return False, "prose_too_short"
    if (action_ctx or {}).get("target_ambiguous"):
        return False, "target_ambiguous"
    kind = (action_ctx or {}).get("kind", "general")
    if kind == "investigate":
        return True, "investigate_beat"
    if kind in _AUDIT_KINDS:
        return True, "dialogue_or_stakes"
    if focal_npc_id or (scene_state and scene_state.cast):
        return True, "focal_scene"
    return False, "low_stakes_beat"


def _build_audit_prompt(text, player, npcs, scene_state, action_ctx, focal_npc_id, scene_place, present_npcs):
    cast = list(scene_state.cast) if scene_state else list(present_npcs or [])
    cast_lines = []
    for n in cast[:8]:
        cast_lines.append(
            f"- id={n.get('id')} name={n.get('name')!r} role={n.get('role')!r} "
            f"status={(npcs or {}).get(n.get('id'), {}).get('status', 'alive')}"
        )
    cast_block = "\n".join(cast_lines) if cast_lines else "- (empty cast — no named speakers allowed)"

    inv = []
    for item in (player.get("inventory") or [])[:12]:
        if isinstance(item, dict):
            inv.append(item.get("name") or item.get("id"))
        else:
            inv.append(str(item))
    eq = player.get("equipment") or {}
    for slot, item in eq.items():
        if isinstance(item, dict) and item.get("name"):
            inv.append(item["name"])

    dead = [
        f"{nid}: {npc.get('name') or nid}"
        for nid, npc in (npcs or {}).items()
        if npc.get("status") == "dead" and npc.get("area") == player.get("area")
    ][:6]

    places = list((player.get("narrator_places") or {}).get(player.get("area") or "", {}).values())
    place_names = [p.get("label") for p in places[:8] if p.get("label")]
    sub = (player.get("scene_subplace") or {}).get("label")

    types_list = ", ".join(sorted(VALID_NOMINATION_TYPES))
    ctx = action_ctx or {}
    movement_blocked = bool(ctx.get("approach_failed") or ctx.get("travel_failed"))
    left_behind = ctx.get("left_behind_cast") or []
    left_lines = []
    for nid in left_behind[:6]:
        npc = (npcs or {}).get(nid, {})
        left_lines.append(f"- id={nid} name={npc.get('name')!r} (LEFT BEHIND — must not speak here)")
    left_block = "\n".join(left_lines) if left_lines else "- none"

    return (
        "Audit this narrator prose for simulation violations. "
        "Return ONLY JSON: {\"violations\": [{type, suspected_id, role_hint, item_name, place_name, quote, evidence}, ...]}\n"
        "Rules:\n"
        f"- type MUST be one of: {types_list}\n"
        "- Nominate ONLY clear violations — do not decide final truth; cite evidence.\n"
        "- speaker_not_in_cast: quoted/named dialogue from someone not in cast list\n"
        "- dialogue_attributed_absent_npc: named NPC speaks but id not in cast\n"
        "- After RELOCATION, NPCs left behind at the prior sub-place must NOT speak — nominate them as speaker_not_in_cast\n"
        "- place_not_navigable: protagonist enters/reaches a specific place not in known list\n"
        "- item_not_in_inventory: protagonist uses/holds item not in inventory\n"
        "- dead_npc_portrayed_alive: dead NPC speaks or acts\n"
        "- movement_when_blocked: prose enters new place but movement was blocked\n"
        f"- LOCATION LOCK: {scene_place}\n"
        f"- Sub-place: {sub or 'none'}\n"
        f"- Known navigable places: {', '.join(place_names) or 'none'}\n"
        f"- Movement blocked this beat: {movement_blocked}\n"
        f"- Relocated this beat: {bool(ctx.get('relocated'))}\n"
        f"- NPCs left behind (must NOT speak):\n{left_block}\n"
        f"- Focal NPC id: {focal_npc_id or 'none'}\n"
        f"- Inventory: {', '.join(inv) or 'empty'}\n"
        f"- Dead NPCs in area: {', '.join(dead) or 'none'}\n"
        "Scene cast (only these may speak with named dialogue):\n"
        f"{cast_block}\n"
        "Prose to audit:\n"
        f"{text[:3500]}\n"
        "JSON:"
    )


def _parse_auditor_json(text):
    if not text:
        return []
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    violations = data.get("violations") if isinstance(data, dict) else None
    if not isinstance(violations, list):
        return []
    out = []
    for v in violations[:12]:
        if isinstance(v, dict) and v.get("type"):
            out.append(v)
    return out


def audit_prose_llm(
    text,
    *,
    player,
    npcs,
    scene_state,
    action_ctx,
    focal_npc_id,
    scene_place,
    present_npcs,
):
    """Return list of raw violation nominations (may be empty)."""
    mock = _mock_auditor_json()
    if mock:
        return _parse_auditor_json(mock)
    try:
        from simulation.gemini_client import generate_text, structured_json_max_tokens
        prompt = _build_audit_prompt(
            text, player, npcs, scene_state, action_ctx,
            focal_npc_id, scene_place, present_npcs,
        )
        raw = generate_text(
            prompt,
            temperature=0.1,
            top_p=0.85,
            max_tokens=structured_json_max_tokens(),
            json_output=True,
        )
        return _parse_auditor_json(raw)
    except Exception as e:
        log.debug("Prose auditor failed: %s", e)
        return None


def run_prose_audit(
    text,
    *,
    player,
    npcs,
    scene_state,
    action_ctx,
    focal_npc_id,
    scene_place,
    present_npcs,
):
    """
    Run auditor + deterministic confirm.
    Returns (confirmed_issues, meta) where meta tracks shadow/on stats.
    """
    mode = auditor_mode()
    should, skip_reason = should_audit_prose(
        action_ctx, scene_state, text, focal_npc_id=focal_npc_id,
    )
    meta = {
        "mode": mode,
        "invoked": False,
        "skip_reason": skip_reason,
        "nominations": 0,
        "confirmed": 0,
        "dropped": 0,
        "error": None,
    }
    if mode == "off" or not should:
        return [], meta

    meta["invoked"] = True
    nominations = audit_prose_llm(
        text,
        player=player,
        npcs=npcs,
        scene_state=scene_state,
        action_ctx=action_ctx,
        focal_npc_id=focal_npc_id,
        scene_place=scene_place,
        present_npcs=present_npcs,
    )
    if nominations is None:
        meta["error"] = "auditor_failed"
        meta["skip_reason"] = "auditor_failed"
        return [], meta

    meta["nominations"] = len(nominations)

    from simulation.auditor_confirm import confirm_nominations
    confirmed, dropped = confirm_nominations(
        nominations,
        text,
        player=player,
        npcs=npcs,
        scene_state=scene_state,
        action_ctx=action_ctx,
        focal_npc_id=focal_npc_id,
        present_npcs=present_npcs,
        scene_place=scene_place,
    )
    meta["confirmed"] = len(confirmed)
    meta["dropped"] = len(dropped)
    meta["dropped_samples"] = dropped[:3]

    if mode == "shadow":
        if confirmed or nominations:
            log.info(
                "Prose auditor shadow: nominations=%s confirmed=%s dropped=%s",
                len(nominations), len(confirmed), len(dropped),
            )
        return [], meta

    return confirmed, meta
