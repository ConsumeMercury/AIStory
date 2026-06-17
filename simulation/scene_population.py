"""
Scene population — who is actually in the social scene this beat.

The area may contain dozens of NPCs; the scene cast is the small persistent
set the player can see and address. Focus stickiness requires cast persistence.
"""

from simulation.scene_cast import _score_npc

MAX_SCENE_CAST = 6
CONTINUATION_KINDS = frozenset({
    "wait", "talk", "ask_about", "ask_name", "personal_talk", "help", "give",
    "threaten", "insult", "show_respect", "accuse", "blackmail", "confess",
    "examine", "observe", "general",
})


def _place_key(player):
    sub = (player.get("scene_subplace") or {}) or {}
    return player.get("area"), sub.get("id")


def _stored_cast_ids(player):
    stored = player.get("scene_cast") or {}
    area, sub = _place_key(player)
    if stored.get("area") == area and stored.get("subplace") == sub:
        ids = stored.get("ids") or []
        if ids:
            return list(ids)
    journal = player.get("journal") or []
    if not journal:
        return []
    last = journal[-1]
    if last.get("area") != player.get("area"):
        return []
    if last.get("subplace") != (player.get("scene_subplace") or {}).get("id"):
        return []
    return list(last.get("scene_cast_ids") or last.get("focus_cast") or [])


def should_reset_scene_cast(action_ctx, player):
    if action_ctx.get("relocated"):
        return True
    if action_ctx.get("travel_arrival"):
        return True
    stored = player.get("scene_cast") or {}
    area, sub = _place_key(player)
    if stored.get("area") and stored.get("area") != area:
        return True
    if stored.get("subplace") != sub:
        return True
    return False


def _journal_prior_cast_ids(player):
    """Last beat's cast at this area — used when scene_cast is stale after subplace change."""
    journal = player.get("journal") or []
    if not journal:
        return []
    last = journal[-1]
    if last.get("area") != player.get("area"):
        return []
    ids = list(last.get("scene_cast_ids") or last.get("focus_cast") or [])
    focus = last.get("focus_npc")
    if focus and focus not in ids:
        ids.append(focus)
    return ids


def _exclude_cast_ids(action_ctx, player):
    """NPC ids that must not carry over after relocation or place-key change."""
    exclude = set(action_ctx.get("left_behind_cast") or [])
    stored = player.get("scene_cast") or {}
    area, sub = _place_key(player)
    if action_ctx.get("relocated") or action_ctx.get("travel_arrival"):
        exclude.update(stored.get("ids") or [])
        if not exclude:
            exclude.update(_journal_prior_cast_ids(player))
    elif stored.get("area") and (stored.get("area") != area or stored.get("subplace") != sub):
        exclude.update(stored.get("ids") or [])
        if not exclude:
            exclude.update(_journal_prior_cast_ids(player))
    return exclude


def bootstrap_scene_cast(all_present, player, action_ctx, npcs, *, max_cast=MAX_SCENE_CAST):
    """Pick a bounded cast for a new scene — not the entire district population."""
    if not all_present:
        return []
    known = player.get("known_npcs", {})
    institutions = {}
    ranked = sorted(
        all_present,
        key=lambda n: _score_npc(n, player, action_ctx, known, institutions),
        reverse=True,
    )
    ids = []
    exclude = _exclude_cast_ids(action_ctx, player)
    for prefer in (
        action_ctx.get("target_id"),
        player.get("scene_focus"),
    ):
        if prefer and prefer not in ids and prefer not in exclude:
            if any(n["id"] == prefer for n in all_present):
                ids.append(prefer)
    for n in ranked:
        if n["id"] in exclude:
            continue
        if n["id"] not in ids:
            ids.append(n["id"])
        if len(ids) >= max_cast:
            break
    by_id = {n["id"]: n for n in all_present}
    return [by_id[i] for i in ids if i in by_id]


def resolve_scene_present(all_present, player, action_ctx, npcs):
    """
    Filter area NPCs to the persistent scene cast for this beat.
    Same area/subplace keeps the same people unless schedules remove them.
    """
    if not all_present:
        return []

    if should_reset_scene_cast(action_ctx, player):
        return bootstrap_scene_cast(all_present, player, action_ctx, npcs)

    id_set = {n["id"] for n in all_present}
    cast_ids = [i for i in _stored_cast_ids(player) if i in id_set]
    by_id = {n["id"]: n for n in all_present}
    filtered = [by_id[i] for i in cast_ids if i in by_id]

    for prefer in (action_ctx.get("target_id"), player.get("scene_focus")):
        if prefer and prefer in by_id and prefer not in {n["id"] for n in filtered}:
            if prefer in _exclude_cast_ids(action_ctx, player):
                continue
            filtered.append(by_id[prefer])

    if action_ctx.get("clarification_resolved") and action_ctx.get("target_id"):
        tid = action_ctx["target_id"]
        if tid in by_id and tid not in {n["id"] for n in filtered}:
            filtered.append(by_id[tid])

    if not filtered:
        return bootstrap_scene_cast(all_present, player, action_ctx, npcs)

    if len(filtered) > MAX_SCENE_CAST:
        focus = action_ctx.get("target_id") or player.get("scene_focus")
        if focus and focus in {n["id"] for n in filtered}:
            focal = by_id[focus]
            rest = [n for n in filtered if n["id"] != focus]
            filtered = [focal] + rest[: MAX_SCENE_CAST - 1]
        else:
            filtered = filtered[:MAX_SCENE_CAST]

    return filtered


def persist_scene_cast(player, scene_present, action_ctx):
    """Save the bounded cast for the next beat at this place."""
    area, sub = _place_key(player)
    left = set(action_ctx.get("left_behind_cast") or [])
    ids = [n["id"] for n in scene_present if n["id"] not in left]
    tid = action_ctx.get("target_id")
    if tid and tid not in ids and tid not in left:
        ids.append(tid)
    player["scene_cast"] = {
        "area": area,
        "subplace": sub,
        "ids": ids[:MAX_SCENE_CAST],
    }


def build_clarification_identity_directive(npc):
    """After the player picks a name, bind narrator to that exact NPC."""
    if not npc:
        return ""
    from generation.descriptor_generator import short_descriptor

    label = npc.get("name") or short_descriptor(npc)
    role = (npc.get("role") or "stranger").replace("_", " ")
    return (
        f"CLARIFICATION RESOLVED — the protagonist addressed {label} "
        f"(id={npc.get('id')}, role={role}). "
        f"YOU ARE this person — respond in character as them. "
        f"Do NOT speak as a different NPC talking about {label} in third person. "
        f"Do NOT say they are elsewhere or that you are looking for them. "
        f"Answer the protagonist's question directly; do NOT repeat prior speech verbatim."
    )
