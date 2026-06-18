"""
Consequence propagation engine — typed effect chains from player beats.

Templates register multi-step fallout (district, institutions, hooks, delayed queue).
Replaces ad-hoc cascade logic while preserving the same public entry points.
"""

import random
import uuid

from simulation.economy_engine import VENDOR_ROLES
from simulation.consequence_queue import queue_consequence

_AUTHORITY_ROLES = frozenset({"guard", "soldier", "captain"})


def _resolve_institution_id(target_npc, institutions, *, inst_type=None):
    if not target_npc or not institutions:
        return None
    inst_ref = target_npc.get("institution") or {}
    if isinstance(inst_ref, dict) and inst_ref.get("id"):
        iid = inst_ref["id"]
        if not inst_type or (institutions.get(iid) or {}).get("type") == inst_type:
            return iid
    if inst_type:
        area = target_npc.get("area") or ""
        city = target_npc.get("location") or (area.split(":")[0] if area else None)
        for iid, inst in institutions.items():
            if inst.get("type") != inst_type:
                continue
            if city and inst.get("city") and inst.get("city") != city:
                continue
            return iid
    return None


def _effect_district_shock(ctx, *, prosperity_delta=0, crime_delta=0):
    area_id = ctx.get("area_id")
    areas = ctx.get("areas") or {}
    if not area_id or not areas:
        return False
    from simulation.economy_pressure import ripple_from_district_shock

    ok = ripple_from_district_shock(
        area_id, areas,
        prosperity_delta=prosperity_delta,
        crime_delta=crime_delta,
    )
    return bool(ok)


def _effect_queue_delayed(ctx, *, kind, summary, effects=None, delay_days=(1, 3), target_id=None):
    player = ctx.get("player")
    world = ctx.get("world") or {}
    if not player:
        return False
    lo, hi = delay_days if isinstance(delay_days, (list, tuple)) else (delay_days, delay_days)
    day = world.get("day", 1)
    entry = queue_consequence(
        player,
        fires_at_day=day + random.randint(int(lo), int(hi)),
        kind=kind,
        summary=summary,
        effects=effects or {},
        target_id=target_id or (ctx.get("target_npc") or {}).get("id"),
    )
    return bool(entry)


def _effect_institution_standing(ctx, *, inst_type=None, inst_id=None, delta=0, reason=""):
    player = ctx.get("player")
    if not player or not delta:
        return False
    from simulation.institution_membership import adjust_institution_standing

    institutions = ctx.get("institutions") or {}
    iid = inst_id or _resolve_institution_id(
        ctx.get("target_npc"), institutions, inst_type=inst_type,
    )
    if not iid:
        return False
    adjust_institution_standing(player, iid, delta, reason=reason[:120])
    return True


def _effect_area_state(ctx, *, key, value=True):
    area_id = ctx.get("area_id")
    areas = ctx.get("areas") or {}
    if not area_id or not areas:
        return False
    area = areas.get(area_id)
    if not area:
        return False
    flags = area.setdefault("state", {}).setdefault("flags", {})
    flags[str(key)] = value
    return True


def _effect_story_flag(ctx, *, key):
    player = ctx.get("player")
    if not player or not key:
        return False
    player.setdefault("story_flags", {})[str(key)] = True
    return True


def _effect_emergent_hook(ctx, *, hook_kind, label, **extra):
    player = ctx.get("player")
    if not player or not label:
        return False
    hook = {
        "id": str(uuid.uuid4())[:10],
        "kind": hook_kind,
        "label": label[:160],
        "area_id": ctx.get("area_id"),
        "tick": ctx.get("tick"),
        "memory_id": ctx.get("memory_id"),
        "target_id": (ctx.get("target_npc") or {}).get("id"),
        **{k: v for k, v in extra.items() if v is not None},
    }
    hooks = player.setdefault("emergent_hooks", [])
    hooks.append(hook)
    player["emergent_hooks"] = hooks[-24:]
    return True


_EFFECT_HANDLERS = {
    "district_shock": _effect_district_shock,
    "queue_delayed": _effect_queue_delayed,
    "institution_standing": _effect_institution_standing,
    "area_state": _effect_area_state,
    "story_flag": _effect_story_flag,
    "emergent_hook": _effect_emergent_hook,
}


def _run_steps(steps, ctx):
    trace = []
    changed = False
    for step in steps:
        name = step.get("effect")
        handler = _EFFECT_HANDLERS.get(name)
        if not handler:
            continue
        params = {k: v for k, v in step.items() if k != "effect"}
        try:
            ok = handler(ctx, **params)
        except Exception:
            ok = False
        trace.append({"effect": name, "ok": bool(ok), "params": {k: params[k] for k in list(params)[:6]}})
        changed = changed or bool(ok)
    return changed, trace


def _merchant_death_steps(ctx):
    target = ctx.get("target_npc") or {}
    name = target.get("name") or "someone"
    area_id = ctx.get("area_id") or "local"
    return [
        {"effect": "district_shock", "prosperity_delta": -10, "crime_delta": 5},
        {
            "effect": "queue_delayed",
            "kind": "trade_disruption",
            "summary": f"Trade falters after {name} died.",
            "delay_days": (1, 3),
            "effects": {
                "narrator_directive": (
                    "The market feels wrong — shuttered stalls, wary eyes, "
                    "prices creeping up. Do not invent a full economic simulation."
                ),
                "story_flag": f"trade_shock_{area_id}",
                "institution_standing_delta": -10,
                "institution_type": "guild",
            },
        },
        {
            "effect": "institution_standing",
            "inst_type": "guild",
            "delta": -12,
            "reason": f"Guild anger after {name}'s death",
        },
        {"effect": "area_state", "key": "trade_disrupted", "value": True},
        {"effect": "area_state", "key": "vendor_gap", "value": True},
        {
            "effect": "emergent_hook",
            "hook_kind": "trade_vacuum",
            "label": f"Stalls stand empty where {name} traded — prices rise and whispers spread.",
        },
        {"effect": "story_flag", "key": f"merchant_killed_{area_id}"},
    ]


def _authority_death_steps(ctx):
    target = ctx.get("target_npc") or {}
    name = target.get("name") or "someone"
    return [
        {"effect": "district_shock", "prosperity_delta": -4, "crime_delta": 5},
        {
            "effect": "queue_delayed",
            "kind": "authority_backlash",
            "summary": f"The garrison noticed what happened to {name}.",
            "delay_days": (1, 4),
            "effects": {
                "narrator_directive": (
                    "Guards are sharper, colder — less patience for strangers."
                ),
                "faction_standing_delta": -6,
                "institution_standing_delta": -8,
                "institution_type": "garrison",
            },
        },
        {
            "effect": "institution_standing",
            "inst_type": "garrison",
            "delta": -8,
            "reason": f"Garrison anger after {name}'s death",
        },
        {
            "effect": "emergent_hook",
            "hook_kind": "authority_grudge",
            "label": f"The watch remembers {name} — scrutiny on strangers tightens.",
        },
    ]


def _generic_violence_steps(ctx):
    target = ctx.get("target_npc") or {}
    name = target.get("name") or "someone"
    return [
        {"effect": "district_shock", "prosperity_delta": -4, "crime_delta": 5},
        {
            "effect": "queue_delayed",
            "kind": "violence_aftermath",
            "summary": f"Word spreads about violence involving {name}.",
            "delay_days": (2, 5),
            "effects": {
                "narrator_directive": (
                    "People speak in lowered voices; strangers are watched."
                ),
            },
        },
    ]


def _causal_ripple_steps(ctx):
    link = ctx.get("causal_link") or {}
    summary = (link.get("summary") or "")[:120]
    return [
        {
            "effect": "queue_delayed",
            "kind": "causal_ripple",
            "summary": summary or "Something you did is still moving through the district.",
            "delay_days": (2, 6),
            "effects": {
                "narrator_directive": (
                    "A prior reckoning still haunts this beat — "
                    "show social residue, not a new plot dump."
                ),
            },
        },
    ]


_TEMPLATES = {
    "fatal_kill_merchant": _merchant_death_steps,
    "fatal_kill_authority": _authority_death_steps,
    "fatal_kill_generic": _generic_violence_steps,
    "causal_ripple": _causal_ripple_steps,
}


def propagate(template_name, *, player, world=None, areas=None, target_npc=None,
              causal_link=None, memory_id=None, tick=None, institutions=None):
    """
    Run a registered propagation template. Returns (changed, trace_dict).
    """
    builder = _TEMPLATES.get(template_name)
    if not builder:
        return False, {"template": template_name, "steps": [], "error": "unknown_template"}

    ctx = {
        "player": player,
        "world": world or {},
        "areas": areas or {},
        "institutions": institutions,
        "target_npc": target_npc,
        "causal_link": causal_link,
        "memory_id": memory_id,
        "tick": tick,
        "area_id": (player or {}).get("area"),
    }
    steps = builder(ctx)
    changed, step_trace = _run_steps(steps, ctx)
    return changed, {
        "template": template_name,
        "memory_id": memory_id,
        "steps": step_trace,
        "step_count": len(step_trace),
    }


def template_for_fatal_kill(target_npc):
    """Pick propagation template from victim role."""
    if not target_npc:
        return None
    role = (target_npc.get("role") or "").lower()
    if role in VENDOR_ROLES:
        return "fatal_kill_merchant"
    if role in _AUTHORITY_ROLES:
        return "fatal_kill_authority"
    return "fatal_kill_generic"
