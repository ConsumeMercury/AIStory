"""
Institutional memory — organizations remember player deeds across member turnover.
"""

MAX_MEMORIES = 12


def record_institution_memory(institutions, inst_id, *, summary, valence=0, tick=None):
    if not inst_id or not summary:
        return False
    inst = (institutions or {}).get(inst_id)
    if not inst:
        return False
    mems = inst.setdefault("institutional_memory", [])
    rec = {"summary": summary[:160], "valence": valence, "tick": tick}
    if any(m.get("summary") == rec["summary"] for m in mems[-4:]):
        return False
    mems.append(rec)
    inst["institutional_memory"] = mems[-MAX_MEMORIES:]
    return True


def record_from_player_action(institutions, player, kind, action_ctx, target_npc, *, tick=None):
    if not target_npc:
        return False
    inst_ref = (target_npc.get("institution") or {})
    inst_id = inst_ref.get("id")
    if not inst_id:
        return False
    check = (action_ctx or {}).get("skill_check") or {}
    success = check.get("success", True)
    valence = 0
    summary = None
    if kind in ("help", "give", "show_respect") and success:
        summary = f"The outsider showed goodwill toward a member ({target_npc.get('role', 'member')})."
        valence = 0.6
    elif kind in ("attack", "insult", "accuse", "blackmail"):
        summary = f"The outsider clashed with a member ({kind})."
        valence = -0.7
    elif kind == "guild" and success:
        summary = "The outsider completed guild business without scandal."
        valence = 0.3
    if summary:
        return record_institution_memory(
            institutions, inst_id, summary=summary, valence=valence, tick=tick,
        )
    return False


def institution_memory_block(player, institutions, target_npc=None):
    inst_id = None
    if target_npc:
        inst_id = (target_npc.get("institution") or {}).get("id")
    if not inst_id:
        return ""
    inst = (institutions or {}).get(inst_id, {})
    mems = inst.get("institutional_memory") or []
    if not mems:
        return ""
    name = inst.get("name", inst_id)
    lines = [f"INSTITUTION MEMORY ({name} — may color member reactions):"]
    for m in mems[-3:]:
        lines.append(f"- {m.get('summary', '')[:120]}")
    return "\n".join(lines)
