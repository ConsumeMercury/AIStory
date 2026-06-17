"""
Deterministic confirmation of AI prose-auditor nominations.

The auditor nominates; this module adjudicates against authoritative state.
"""

import re

from simulation.prose_validator import _ROLE_WORDS, _PLACE_MOVE, _PLACE_SUBPARTS

VALID_NOMINATION_TYPES = frozenset({
    "speaker_not_in_cast",
    "dialogue_attributed_absent_npc",
    "place_not_navigable",
    "item_not_in_inventory",
    "dead_npc_portrayed_alive",
    "movement_when_blocked",
})

_SPEECH_VERBS = re.compile(
    r"\b(said|asked|replied|murmured|whispered|shouted|spoke|answered|called out)\b",
    re.I,
)


def _normalize_nom(raw):
    if not raw or not isinstance(raw, dict):
        return None
    vtype = (raw.get("type") or "").strip().lower()
    if vtype not in VALID_NOMINATION_TYPES:
        return None
    return {
        "type": vtype,
        "suspected_id": (raw.get("suspected_id") or raw.get("npc_id") or None),
        "role_hint": (raw.get("role_hint") or raw.get("role") or "").strip().lower() or None,
        "item_name": (raw.get("item_name") or raw.get("item") or "").strip().lower() or None,
        "place_name": (raw.get("place_name") or raw.get("place") or "").strip().lower() or None,
        "quote": (raw.get("quote") or raw.get("evidence") or "")[:200],
        "evidence": (raw.get("evidence") or "")[:200],
    }


def _cast_ids(cast):
    return {n.get("id") for n in (cast or []) if n.get("id")}


def _role_matches_in_cast(role_hint, cast):
    if not role_hint:
        return []
    hint = role_hint.lower()
    out = []
    for n in cast or []:
        role = (n.get("role") or "").lower()
        if role == hint:
            out.append(n)
            continue
        words = _ROLE_WORDS.get(role, (role,))
        if hint in words or any(hint == w for w in words):
            out.append(n)
    return out


def _known_place_labels(player, area_id):
    labels = set()
    sub = (player.get("scene_subplace") or {}).get("label")
    if sub:
        labels.add(sub.lower())
    for rec in (player.get("narrator_places") or {}).get(area_id or "", {}).values():
        lab = (rec.get("label") or "").strip().lower()
        if lab:
            labels.add(lab)
    return labels


def _inventory_names(player):
    names = set()
    for item in player.get("inventory") or []:
        if isinstance(item, dict):
            nm = (item.get("name") or item.get("id") or "").lower()
        else:
            nm = str(item).lower()
        if nm:
            names.add(nm)
            for part in nm.split():
                if len(part) > 2:
                    names.add(part)
    eq = player.get("equipment") or {}
    for slot, item in eq.items():
        if isinstance(item, dict):
            nm = (item.get("name") or "").lower()
            if nm:
                names.add(nm)
    return names


def _confirm_speaker_not_in_cast(nom, cast, cast_ids, focal_id, npcs, action_ctx=None):
    ctx = action_ctx or {}
    left_behind = set(ctx.get("left_behind_cast") or [])
    sid = nom.get("suspected_id")
    if sid:
        if sid in left_behind:
            name = (npcs or {}).get(sid, {}).get("name") or sid
            return True, f"AUDITOR CONFIRMED: left-behind NPC {name!r} speaks but is not in this sub-place cast"
        if sid in cast_ids:
            return False, "suspected_id is in scene cast"
        npc = (npcs or {}).get(sid, {})
        if npc.get("status") == "dead":
            return False, "defer to dead_npc_portrayed_alive"
        if sid in (npcs or {}):
            return True, f"AUDITOR CONFIRMED: speaker {sid!r} not in scene cast"
    role = nom.get("role_hint")
    if role:
        matches = _role_matches_in_cast(role, cast)
        if len(matches) == 1:
            return False, "role matches sole cast member"
        if len(matches) > 1:
            return False, "ambiguous role — multiple cast matches"
        if not matches and _SPEECH_VERBS.search(nom.get("quote") or nom.get("evidence") or ""):
            return True, f"AUDITOR CONFIRMED: {role!r} speaks but no {role!r} in cast"
    return False, "unconfirmed speaker nomination"


def _confirm_dialogue_absent(nom, cast_ids, npcs, text, action_ctx=None):
    sid = nom.get("suspected_id")
    left_behind = set((action_ctx or {}).get("left_behind_cast") or [])
    if sid and sid in left_behind:
        name = (npcs or {}).get(sid, {}).get("name") or sid
        return True, f"AUDITOR CONFIRMED: left-behind NPC {name!r} has attributed dialogue"
    if not sid or sid in cast_ids:
        return False, "not absent or in cast"
    npc = (npcs or {}).get(sid, {})
    if not npc:
        return False, "unknown npc id"
    name = (npc.get("name") or "").strip()
    if not name:
        return False, "no name to match"
    first = re.escape(name.split()[0])
    if re.search(rf"\b{first}\s+(?:said|asked|replied|murmured|whispered|shouted)\b", text, re.I):
        return True, f"AUDITOR CONFIRMED: absent NPC {name!r} has attributed dialogue"
    return False, "no attributed dialogue pattern"


def _confirm_place_not_navigable(nom, player, area_id, scene_place):
    place = nom.get("place_name") or ""
    if not place or len(place) < 3:
        return False, "no place name"
    place = place.lower()
    known = _known_place_labels(player, area_id)
    if scene_place and place in scene_place.lower():
        return False, "place matches scene lock"
    if any(place in k or k in place for k in known):
        return False, "place is known/navigable"
    if place in _PLACE_SUBPARTS:
        return False, "generic subpart"
    return True, f"AUDITOR CONFIRMED: prose treats {place!r} as reachable but it is not navigable here"


def _confirm_item_not_in_inventory(nom, player, text):
    item = nom.get("item_name") or ""
    if not item or len(item) < 2:
        return False, "no item name"
    inv = _inventory_names(player)
    if item in inv or any(item in n for n in inv):
        return False, "item in inventory"
    if item not in text.lower():
        return False, "item not referenced in prose"
    return True, f"AUDITOR CONFIRMED: protagonist uses {item!r} not in inventory"


def _confirm_dead_npc_alive(nom, npcs, text):
    sid = nom.get("suspected_id")
    if not sid:
        return False, "no suspected_id"
    npc = (npcs or {}).get(sid, {})
    if npc.get("status") != "dead":
        return False, "npc not dead in sim"
    name = (npc.get("name") or sid).strip()
    first = re.escape(name.split()[0]) if name else re.escape(sid)
    if re.search(rf"\b{first}\s+(?:said|asked|replied|murmured|moves|steps|turns)\b", text, re.I):
        return True, f"AUDITOR CONFIRMED: dead NPC {name!r} portrayed as active"
    if _SPEECH_VERBS.search(text) and first.lower() in text.lower():
        return True, f"AUDITOR CONFIRMED: dead NPC {name!r} portrayed as speaking"
    return False, "dead npc not clearly active in prose"


def _confirm_movement_blocked(nom, action_ctx, text, scene_place):
    ctx = action_ctx or {}
    if not (ctx.get("approach_failed") or ctx.get("travel_failed")):
        return False, "movement not blocked this beat"
    for match in _PLACE_MOVE.finditer(text):
        dest = (match.group(1) or "").strip().lower()
        if dest and dest not in _PLACE_SUBPARTS:
            if scene_place and dest not in scene_place.lower():
                return True, f"AUDITOR CONFIRMED: prose enters {dest!r} but movement was blocked"
    return False, "no entering-movement in prose"


def confirm_nominations(
    nominations,
    text,
    *,
    player,
    npcs,
    scene_state,
    action_ctx,
    focal_npc_id,
    present_npcs,
    scene_place,
):
    """
    Confirm auditor nominations against authoritative state.
    Returns (confirmed_issue_strings, dropped_records).
    """
    cast = list(scene_state.cast) if scene_state else list(present_npcs or [])
    cast_ids = scene_state.cast_ids if scene_state else _cast_ids(cast)
    area_id = player.get("area")
    confirmed = []
    dropped = []

    for raw in nominations or []:
        nom = _normalize_nom(raw)
        if not nom:
            dropped.append({"raw": raw, "reason": "invalid_nomination"})
            continue
        vtype = nom["type"]
        ok, reason = False, "unhandled"

        if vtype == "speaker_not_in_cast":
            ok, reason = _confirm_speaker_not_in_cast(
                nom, cast, cast_ids, focal_npc_id, npcs, action_ctx,
            )
        elif vtype == "dialogue_attributed_absent_npc":
            ok, reason = _confirm_dialogue_absent(nom, cast_ids, npcs, text or "", action_ctx)
        elif vtype == "place_not_navigable":
            ok, reason = _confirm_place_not_navigable(nom, player, area_id, scene_place)
        elif vtype == "item_not_in_inventory":
            ok, reason = _confirm_item_not_in_inventory(nom, player, text or "")
        elif vtype == "dead_npc_portrayed_alive":
            ok, reason = _confirm_dead_npc_alive(nom, npcs, text or "")
        elif vtype == "movement_when_blocked":
            ok, reason = _confirm_movement_blocked(nom, action_ctx, text or "", scene_place)

        if ok:
            confirmed.append(reason)
        else:
            dropped.append({"nomination": nom, "reason": reason})

    return dedupe_confirmed(confirmed), dropped


def dedupe_confirmed(confirmed):
    seen = set()
    out = []
    for c in confirmed:
        key = c.lower()[:100]
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out
