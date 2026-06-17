"""
Narrative causality — lightweight cause → effect chains for major beats.
"""

MAX_LINKS = 40

CAUSE_MAP = {
    "attack": ("violence", "standing and fear shift"),
    "accuse": ("accusation", "trust fractures"),
    "confess": ("confession", "secrets surface"),
    "help": ("kindness", "obligation or gratitude"),
    "steal": ("theft", "suspicion spreads"),
    "investigate": ("inquiry", "clues accumulate"),
    "blackmail": ("leverage", "compliance or revenge"),
}


def record_causal_link(player, *, cause, effect, summary, importance=60, tick=None, arc_id=None):
    if not summary:
        return False
    link = {
        "cause": cause[:80],
        "effect": effect[:80],
        "summary": summary[:200],
        "importance": max(1, min(100, int(importance))),
        "tick": tick,
        "arc_id": arc_id,
    }
    links = player.setdefault("causal_links", [])
    if any(l.get("summary") == link["summary"] for l in links[-8:]):
        return False
    links.append(link)
    player["causal_links"] = sorted(
        links, key=lambda l: l.get("importance", 0), reverse=True,
    )[:MAX_LINKS]
    return True


def record_from_beat(player, kind, action_ctx, world, *, tick=None):
    """Record causal chain snippet from a resolved player beat."""
    ctx = action_ctx or {}
    cause_key, default_effect = CAUSE_MAP.get(kind, (kind, "consequences ripple"))
    stakes = player.get("scene_stakes") or {}
    arc_id = stakes.get("arc_id")
    action = (ctx.get("action_summary") or kind)[:80]
    check = ctx.get("skill_check") or {}
    success = check.get("success", True)

    if kind == "attack":
        effect = "someone hurt or humiliated" if success else "violence failed or backfired"
    elif kind in ("accuse", "blackmail"):
        effect = "silence breaks or hardens" if success else "accusation rejected"
    elif kind == "help":
        effect = "goodwill earned" if success else "help refused or wasted"
    elif kind == "investigate":
        effect = "evidence found" if success else "trail goes cold"
    else:
        effect = default_effect

    imp = 55
    if kind in ("attack", "accuse", "confess", "blackmail"):
        imp = 72
    if not success:
        imp = max(imp - 8, 45)

    summary = f"Because the outsider {cause_key}: {action[:60]} → {effect}."
    return record_causal_link(
        player,
        cause=cause_key,
        effect=effect,
        summary=summary,
        importance=imp,
        tick=tick,
        arc_id=arc_id,
    )


def propagate_causal_pressure(player, kind, action_ctx, *, npcs=None, areas=None, tick=None):
    """
    After a beat, nudge district tension and focal beliefs from latest causal links.
    Lightweight consequence propagation — not a full sim rewrite.
    """
    from storage import load

    links = player.get("causal_links") or []
    if not links:
        return False
    latest = links[0]
    imp = int(latest.get("importance") or 0)
    if imp < 50:
        return False

    changed = False
    areas = areas if areas is not None else load("world/areas.json", {})
    aid = player.get("area")
    if aid and kind in ("investigate", "ask_about", "accuse", "confess", "attack", "blackmail"):
        sl = (areas.get(aid, {}) or {}).get("storyline") or {}
        if sl and imp >= 65:
            sl["tension"] = min(100, int(sl.get("tension", 20)) + 1)
            changed = True

    ctx = action_ctx or {}
    target_id = ctx.get("target_id")
    if target_id and npcs and kind in ("accuse", "blackmail", "confess", "attack"):
        npc = npcs.get(target_id)
        if npc and npc.get("status") == "alive":
            from simulation.belief_model import upsert_belief
            upsert_belief(
                npc, "outsider_is_notable", 0.08,
                source="witnessed", tick=tick, grounding="witnessed",
            )
            changed = True

    links = player.get("causal_links") or []
    if links:
        from simulation.consequence_cascade import register_from_causal_link
        from storage import load as _load
        world_state = _load("world/world_state.json", {})
        if register_from_causal_link(player, links[0], world=world_state, areas=areas):
            changed = True
    return changed


def causality_narrator_block(player, *, limit=3):
    links = player.get("causal_links") or []
    if not links:
        return ""
    lines = ["RECENT CAUSALITY (the world remembers why — not just what):"]
    for link in links[:limit]:
        lines.append(f"- {link.get('summary', '')[:140]}")
    return "\n".join(lines)
