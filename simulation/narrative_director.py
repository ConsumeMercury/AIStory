"""
Narrative Director — pacing, callback scheduling, dialogue intents.

Unifies story-facing beat decisions before Gemini runs. story_orchestrator
executes the director plan; this module owns pacing and pre-prose intent.
"""

from simulation.scene_coherence import DIALOGUE_KINDS

_BREATHE_KINDS = frozenset({"wait", "rest", "withdraw", "observe"})
_TENSION_KINDS = frozenset({"accuse", "attack", "blackmail", "confess"})
_REVELATION_KINDS = frozenset({"investigate", "search", "find", "ask_about"})

_STANCE_BY_VALENCE = (
    (-0.55, "hostile", "resist"),
    (-0.2, "guarded", "deflect"),
    (0.35, "warm", "cooperate"),
    (999, "cautious", "neutral"),
)


def _director_state(player):
    return player.setdefault("narrative_director", {
        "beats_since_callback": 0,
        "last_callback_tick": 0,
        "last_pacing": "advance",
    })


def _pacing_mode(kind, scene_plan, *, journal_len=0):
    hint = (scene_plan or {}).get("structure_hint") or "continuation"
    if kind in _BREATHE_KINDS:
        return "breathe"
    if hint == "arrival" and journal_len < 2:
        return "orient"
    if kind in _TENSION_KINDS or hint == "tension":
        return "complicate"
    if kind in _REVELATION_KINDS or hint == "revelation":
        return "revelation"
    if hint == "continuation":
        return "continuation"
    return "advance"


def _should_schedule_callback(player, kind, pacing, scene_plan, tick):
    """Callbacks land sparingly — not every eligible beat."""
    state = _director_state(player)
    beats = int(state.get("beats_since_callback") or 0)
    if kind in _TENSION_KINDS:
        return True
    if pacing in ("complicate", "revelation"):
        return beats >= 1
    if pacing in ("continuation", "advance"):
        return beats >= 2
    if pacing == "breathe":
        return False
    must = scene_plan.get("must_surface") or []
    if len(must) >= 2 and beats >= 1:
        return True
    last = state.get("last_callback_tick") or 0
    if tick and last and (tick - last) >= 8:
        return True
    return beats >= 3


def build_dialogue_intents(focal_id, npcs, *, kind, action_ctx, player):
    """
    Pre-Gemini dialogue intent for the focal NPC — goal and stance, not prose.
    """
    if not focal_id or kind not in DIALOGUE_KINDS:
        return []
    npc = (npcs or {}).get(focal_id)
    if not npc or npc.get("status") != "alive":
        return []

    from simulation.npc_memory_engine import player_memories
    from simulation.memory_immersion import effective_salience

    mems = player_memories(focal_id, n=2)
    valence = 0.0
    tick = player.get("last_tick") or 0
    if mems:
        valence = float(mems[0].get("valence") or 0)
        if effective_salience(mems[0], tick) < 10:
            valence *= 0.5

    stance, goal = "cautious", "neutral"
    for threshold, st, gl in _STANCE_BY_VALENCE:
        if valence <= threshold:
            stance, goal = st, gl
            break

    ctx = action_ctx or {}
    check = ctx.get("skill_check") or {}
    if check and not check.get("success") and kind in ("threaten", "accuse", "blackmail"):
        stance, goal = "guarded", "deflect"

    if kind in ("accuse", "blackmail"):
        goal = "resist" if valence < 0 else "deflect"
    elif kind in ("help", "give", "show_respect"):
        goal = "cooperate"
    elif kind == "ask_about":
        goal = "deflect" if valence < -0.15 else "cooperate"

    intent = {
        "npc_id": focal_id,
        "name": npc.get("name") or focal_id,
        "goal": goal,
        "stance": stance,
    }
    secrets = npc.get("secrets") or []
    if secrets and kind in ("ask_about", "investigate", "accuse"):
        intent["withhold"] = (secrets[0].get("summary") or secrets[0].get("text") or "a secret")[:80]
        intent["reveal_if_pressed"] = check.get("success", True) and kind == "accuse"
    return [intent]


def build_dialogue_intents_block(intents):
    if not intents:
        return ""
    lines = ["DIALOGUE INTENT (execute in prose — do not state these labels):"]
    for intent in intents[:2]:
        parts = [
            f"{intent.get('name', 'NPC')}: goal={intent.get('goal')}",
            f"stance={intent.get('stance')}",
        ]
        if intent.get("withhold"):
            parts.append(f"withhold={intent['withhold'][:60]}")
        if intent.get("reveal_if_pressed"):
            parts.append("may crack if pressed hard")
        lines.append("- " + "; ".join(parts))
    return "\n".join(lines)


def plan_director_beat(player, *, kind, action_ctx, scene_plan, npcs=None, tick=None):
    """
    Build director plan merged into beat_plan.scene_plan.
    Returns director_plan dict and mutates player narrative_director state.
    """
    ctx = action_ctx or {}
    plan = dict(scene_plan or {})
    state = _director_state(player)
    journal_len = len(player.get("journal") or [])
    pacing = _pacing_mode(kind, plan, journal_len=journal_len)

    focal = ctx.get("target_id") or ctx.get("focal_npc_id")
    dialogue_intents = build_dialogue_intents(
        focal, npcs, kind=kind, action_ctx=ctx, player=player,
    )

    callback = plan.pop("memory_callback", None)
    schedule_cb = bool(callback) and _should_schedule_callback(
        player, kind, pacing, plan, tick or player.get("last_tick"),
    )
    if callback and not schedule_cb:
        callback = None
    elif callback and schedule_cb:
        state["beats_since_callback"] = 0
        state["last_callback_tick"] = tick or player.get("last_tick") or 0
    else:
        state["beats_since_callback"] = int(state.get("beats_since_callback") or 0) + 1

    state["last_pacing"] = pacing
    player["narrative_director"] = state

    must_surface = list(plan.get("must_surface") or [])
    if pacing == "breathe" and len(must_surface) > 1:
        must_surface = must_surface[:1]

    director_plan = {
        "pacing_mode": pacing,
        "dialogue_intents": dialogue_intents,
        "memory_callback": callback,
        "must_surface": must_surface,
        "callback_scheduled": bool(callback),
    }
    return director_plan
