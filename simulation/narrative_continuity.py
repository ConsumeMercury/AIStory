"""
Long-horizon narrative continuity — voice anchors, established details, no re-establishment.
"""

import re

_QUOTED = re.compile(r'"([^"]{12,240})"')
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_DESCRIPTOR_WORDS = re.compile(
    r"\b(scar|scars|finger|fingers|wrist|wrists|eye|eyes|hair|voice|throat|"
    r"knuckle|knuckles|cheek|nose|freckle|freckles|tattoo|brand|callous|"
    r"bowstring|ink|stain|stained|fringe|brow|lip|lips|jaw|shoulder|hand|hands)\b",
    re.I,
)


def extract_dialogue_lines(scene, *, skip_lines=None, limit=2):
    """Quoted lines from prose — likely NPC speech."""
    skip = {s.strip().lower() for s in (skip_lines or []) if s}
    found = []
    for match in _QUOTED.finditer(scene or ""):
        line = match.group(1).strip()
        if len(line) < 12 or line.lower() in skip:
            continue
        found.append(line)
    return found[-limit:]


def extract_descriptor_sentences(scene, npc_name, *, limit=4):
    """Concrete physical claims about an NPC from prior prose."""
    if not scene or not npc_name:
        return []
    first = npc_name.split()[0]
    if len(first) < 2:
        return []
    name_pat = re.compile(rf"\b{re.escape(first)}\b", re.I)
    pron_pat = re.compile(r"\b(she|her|he|him|his)\b", re.I)
    out = []
    for sent in _SENTENCE.split(scene.strip()):
        sent = sent.strip()
        if not sent:
            continue
        if not (name_pat.search(sent) or pron_pat.search(sent)):
            continue
        if not _DESCRIPTOR_WORDS.search(sent):
            continue
        if len(sent) > 180:
            sent = sent[:177] + "..."
        if sent not in out:
            out.append(sent)
        if len(out) >= limit:
            break
    return out


def _seed_cache_from_journal(player, focal_npc_id, npcs, journal):
    """Backfill voice/details from journal when cache is empty."""
    rec = player.setdefault("known_npcs", {}).setdefault(focal_npc_id, {})
    if rec.get("prior_lines") and rec.get("established_details"):
        return
    npc = (npcs or {}).get(focal_npc_id, {})
    name = npc.get("name", "")
    for entry in reversed(journal[-10:]):
        if entry.get("focus_npc") != focal_npc_id:
            continue
        scene = entry.get("scene") or entry.get("excerpt") or ""
        if not rec.get("prior_lines"):
            speech = (entry.get("action") or "")
            if speech.startswith('"') or 'ask "' in speech.lower():
                skip = [speech.strip('"')]
            else:
                skip = []
            lines = extract_dialogue_lines(scene, skip_lines=skip, limit=2)
            if lines:
                rec["prior_lines"] = lines
        if not rec.get("established_details") and name:
            details = extract_descriptor_sentences(scene, name, limit=4)
            lock = (rec.get("narration_lock") or {}).get("appearance", "")
            filtered = [d for d in details if d not in lock]
            if filtered:
                rec["established_details"] = filtered[:6]


def update_npc_narrative_cache(player, focal_npc_id, scene, npcs, *, player_speech=None):
    """Persist dialogue lines and invented descriptors after each scene."""
    if not focal_npc_id or not scene:
        return False
    rec = player.setdefault("known_npcs", {}).setdefault(focal_npc_id, {})
    npc = (npcs or {}).get(focal_npc_id, {})
    name = npc.get("name", "")
    skip = [player_speech] if player_speech else []
    changed = False

    lines = extract_dialogue_lines(scene, skip_lines=skip, limit=2)
    if lines:
        prior = list(rec.get("prior_lines") or [])
        for ln in lines:
            if ln not in prior:
                prior.append(ln)
        rec["prior_lines"] = prior[-2:]
        changed = True

    if name:
        desc = extract_descriptor_sentences(scene, name, limit=3)
        lock = (rec.get("narration_lock") or {}).get("appearance", "")
        details = list(rec.get("established_details") or [])
        for d in desc:
            if d not in details and d not in lock:
                details.append(d)
        if details:
            rec["established_details"] = details[-6:]
            changed = True
    return changed


def build_no_reestablishment_note(player, journal, focal_npc_id, known_ids, area_id, action_kind):
    """Skip full re-introduction when place and person are already established."""
    if not journal:
        return ""
    lines = []
    visits = (player.get("discovered_areas") or {}).get(area_id, {}).get("visits", 0)
    if area_id and (visits > 1 or len(journal) >= 3):
        lines.append(
            "ESTABLISHED PLACE: the protagonist already knows this location — "
            "do NOT write a second arrival paragraph (no fresh weather/atmosphere opener). "
            "Continue from the last moment."
        )
    if focal_npc_id and focal_npc_id in (known_ids or set()):
        lines.append(
            "ESTABLISHED PERSON: they are already known — "
            "do NOT re-describe face, hair, eyes, or voice register from scratch. "
            "At most one small gesture; build on prior beats."
        )
    if not lines:
        return ""
    return "CONTINUITY — NO RE-ESTABLISHMENT:\n" + "\n".join(f"- {ln}" for ln in lines)


def build_narrative_continuity_block(
    player, journal, focal_npc_id, npcs, *, known_ids, area_id, action_kind,
):
    """Voice anchors, established invented details, and anti-reestablishment."""
    _seed_cache_from_journal(player, focal_npc_id, npcs, journal)

    parts = [build_no_reestablishment_note(
        player, journal, focal_npc_id, known_ids, area_id, action_kind,
    )]

    if focal_npc_id:
        rec = (player.get("known_npcs") or {}).get(focal_npc_id, {})
        details = rec.get("established_details") or []
        if details:
            body = "\n".join(f"- {d}" for d in details[:6])
            parts.append(
                "ESTABLISHED DETAILS (already true in prior beats — stay consistent, do not contradict):\n"
                f"{body}"
            )
        prior = rec.get("prior_lines") or []
        if prior:
            body = "\n".join(f'- "{ln}"' for ln in prior[-2:])
            parts.append(
                "VOICE ANCHOR (this person has spoken like this — match rhythm and register):\n"
                f"{body}"
            )

    return "\n\n".join(p for p in parts if p)
