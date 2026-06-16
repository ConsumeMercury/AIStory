"""
Authoritative plot summary from simulation state — not reconstructed from prose.
"""


def _goal_lines(player):
    lines = []
    for g in player.get("goals") or []:
        if g.get("complete"):
            continue
        prog = g.get("progress", 0)
        target = g.get("target", "?")
        text = (g.get("text") or "")[:120]
        if text:
            lines.append(f"- Goal: {text} ({prog}/{target})")
    return lines


def _pipeline_lines(player):
    pipe = player.get("starting_pipeline") or {}
    if not pipe:
        return []
    lines = [
        f"- Opening thread ({pipe.get('title', 'local plot')}): "
        f"{(pipe.get('hook') or '')[:100]}",
    ]
    current = pipe.get("current")
    if current:
        lines.append(f"- Current stage: {current[:100]}")
    return lines


def _case_lines(player, npcs, present_ids):
    case = player.get("active_case")
    if not case or case.get("solved"):
        return []
    present_ids = set(present_ids or [])
    victim_id = case.get("victim_id")
    victim = (npcs or {}).get(victim_id, {})
    victim_name = case.get("victim_name") or victim.get("name", "unknown")
    stage = case.get("stage", 0)
    stages = case.get("stages") or []
    stage_label = stages[min(stage, len(stages) - 1)] if stages else "investigating"

    if victim.get("status") == "alive" and victim_id in present_ids:
        victim_line = (
            f"- Active case ({case.get('title', 'mystery')}): stage {stage + 1} — {stage_label}. "
            f"Case file names {victim_name} as victim, but they are alive and present — "
            "treat death as off-screen; do not narrate them as a corpse."
        )
    else:
        victim_line = (
            f"- Active case ({case.get('title', 'mystery')}): victim {victim_name}; "
            f"stage {stage + 1} — {stage_label}."
        )
    lines = [victim_line]

    discovered = [e for e in case.get("evidence", []) if e.get("discovered")]
    for ev in discovered[:4]:
        lines.append(f"- Clue: {ev.get('text', '')[:90]}")

    suspects = case.get("suspect_ids") or []
    if suspects:
        names = [
            (npcs or {}).get(sid, {}).get("name", sid)
            for sid in suspects[:3]
        ]
        lines.append(f"- Suspects: {', '.join(names)}.")
    return lines


def _discovery_lines(player, npcs):
    lines = []
    item = player.get("last_acquired_item")
    if item:
        lines.append(
            f"- Recently acquired: {item.get('name', 'item')} ({item.get('rarity', '?')})."
        )
    known = player.get("known_npcs") or {}
    named = [
        (npcs or {}).get(nid, {}).get("name", nid)
        for nid, rec in known.items()
        if rec.get("name_known")
    ]
    if named:
        lines.append(f"- Names learned: {', '.join(named[-6:])}.")
    areas = player.get("discovered_areas") or {}
    if areas:
        recent = list(areas.values())[-3:]
        labels = [a.get("name") or a.get("subtitle") or "?" for a in recent]
        lines.append(f"- Places visited: {', '.join(labels)}.")
    return lines


def _focal_lines(player, npcs, focal_npc_id):
    if not focal_npc_id:
        return []
    npc = (npcs or {}).get(focal_npc_id, {})
    if not npc:
        return []
    known = (player.get("known_npcs") or {}).get(focal_npc_id, {})
    name = npc.get("name") if known.get("name_known") else "unnamed"
    imp = known.get("impression") or {}
    hint = imp.get("hint")
    lines = [f"- Current conversation focus: {name} ({npc.get('role', 'stranger')})."]
    if hint:
        lines.append(f"- Their read of you: {hint}.")
    return lines


def build_plot_summary(player, npcs=None, *, focal_npc_id=None, present_ids=None):
    """Deterministic plot state block for the narrator prompt."""
    npcs = npcs or {}
    parts = ["PLOT SUMMARY (simulation truth — obey over prose memory):"]
    parts.extend(_pipeline_lines(player))
    parts.extend(_goal_lines(player))
    parts.extend(_case_lines(player, npcs, present_ids))
    parts.extend(_discovery_lines(player, npcs))
    parts.extend(_focal_lines(player, npcs, focal_npc_id))
    if len(parts) <= 1:
        return ""
    return "\n".join(parts)
