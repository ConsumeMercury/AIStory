"""
Long-horizon narrative continuity — voice anchors, established details, no re-establishment.
"""

import re

from simulation.beat_structure import beats_with_same_focus

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
    same_area_beats = sum(1 for e in journal[-8:] if e.get("area") == area_id) if area_id else 0
    same_focus_beats = beats_with_same_focus(journal, area_id, focal_npc_id) if focal_npc_id else 0

    if area_id and (visits > 1 or same_area_beats >= 2):
        ban = "HARD BAN —" if same_area_beats >= 3 else "Do NOT"
        lines.append(
            f"ESTABLISHED PLACE ({same_area_beats + 1} beats in this exact spot): {ban} "
            "re-describe setting, weather, heat, stall layout, or district atmosphere. "
            "The player has NOT left — continue from the last moment; open on motion or change."
        )
    if focal_npc_id and focal_npc_id in (known_ids or set()):
        if same_focus_beats >= 2:
            lines.append(
                f"ESTABLISHED PERSON ({same_focus_beats + 1} exchanges with them here): "
                "do NOT re-describe face, hair, eyes, robes, or voice register. "
                "One small gesture at most; match VOICE ANCHOR and prior lines."
            )
        else:
            lines.append(
                "ESTABLISHED PERSON: they are already known — "
                "do NOT re-describe face, hair, eyes, or voice from scratch. "
                "At most one small gesture; build on prior beats."
            )
    if not lines:
        return ""
    return "CONTINUITY — NO RE-ESTABLISHMENT:\n" + "\n".join(f"- {ln}" for ln in lines)


def build_stalled_beat_note(player, journal, action_context, focal_npc_id, area_id):
    """When movement fails repeatedly at the same spot, forbid line recycling."""
    if not journal:
        return ""
    last = journal[-1]
    ctx = action_context or {}
    same_place = last.get("area") == area_id
    same_focus = focal_npc_id and last.get("focus_npc") == focal_npc_id
    stalled = ctx.get("approach_failed") or ctx.get("travel_failed")
    last_stalled = last.get("approach_failed") or last.get("travel_failed")

    if not same_place or not stalled:
        return ""
    if not (same_focus or last_stalled):
        return ""

    prior = (last.get("excerpt") or "")[:160]
    lines = [
        "STALLED BEAT — the protagonist did not move; state is unchanged from last beat.",
        "Do NOT repeat the focal NPC's prior line verbatim.",
        "React to the stall: impatience, silence, a new concrete detail, or let them go quiet.",
        "Do NOT name new navigable destinations the player cannot reach.",
    ]
    if prior:
        lines.append(f"Last beat (do not replay): {prior}")
    return "CONTINUITY — STALL:\n" + "\n".join(f"- {ln}" for ln in lines)


def find_repeated_prior_content(text, player, focal_npc_id, *, min_quote_len=28):
    """Flag when new prose reuses stored NPC dialogue or gesture sentences."""
    if not text or not focal_npc_id:
        return None
    rec = (player.get("known_npcs") or {}).get(focal_npc_id, {})
    lower = text.lower()

    for line in rec.get("prior_lines") or []:
        clean = line.strip().strip('"').strip()
        if len(clean) < min_quote_len:
            continue
        if clean.lower() in lower:
            return f"focal NPC repeated prior line verbatim: {clean[:72]!r}"
        if len(clean) >= 48 and clean[:36].lower() in lower:
            return f"focal NPC echoed prior speech: {clean[:72]!r}"

    for detail in rec.get("established_details") or []:
        d = (detail or "").strip()
        if len(d) >= 48 and d.lower() in lower:
            return "prose repeated established gesture/description verbatim"
    return None


def build_narrative_continuity_block(
    player, journal, focal_npc_id, npcs, *, known_ids, area_id, action_kind,
    action_context=None,
):
    """Voice anchors, established invented details, and anti-reestablishment."""
    _seed_cache_from_journal(player, focal_npc_id, npcs, journal)

    parts = [build_no_reestablishment_note(
        player, journal, focal_npc_id, known_ids, area_id, action_kind,
    )]

    stall = build_stalled_beat_note(
        player, journal, action_context, focal_npc_id, area_id,
    )
    if stall:
        parts.append(stall)

    if focal_npc_id:
        rec = (player.get("known_npcs") or {}).get(focal_npc_id, {})
        details = rec.get("established_details") or []
        if details:
            body = "\n".join(f"- {d}" for d in details[:6])
            parts.append(
                "ESTABLISHED DETAILS (stay consistent — do NOT repeat these sentences verbatim each beat):\n"
                f"{body}"
            )
        prior = rec.get("prior_lines") or []
        if prior:
            body = "\n".join(f'- "{ln}"' for ln in prior[-2:])
            parts.append(
                "PRIOR DIALOGUE (register only — do NOT quote these lines again; answer the new question):\n"
                f"{body}"
            )

    return "\n\n".join(p for p in parts if p)
