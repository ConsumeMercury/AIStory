"""
Scene objectives — purpose, emotion, and conflict derived from simulation state.

Thin planner layer: no LLM, only persisted stakes + beat kind.
"""

PURPOSE_BY_KIND = {
    "ask_about": "reveal or withhold information",
    "investigate": "surface physical evidence or contradiction",
    "accuse": "force denial, guilt, or counter-accusation",
    "blackmail": "extract compliance or backlash",
    "confess": "witness reaction to truth",
    "attack": "violence with cost",
    "help": "shift trust or obligation",
    "find": "locate a person",
    "search": "discover object or absence",
    "talk": "advance relationship or agenda",
    "explore": "orient or foreshadow",
    "wait": "time passes; something may change",
}

EMOTION_BY_STRUCTURE = {
    "tension": "pressure",
    "revelation": "unease or relief",
    "stalled": "impatience",
    "continuation": "familiar tension",
    "arrival": "wonder or wariness",
    "action": "momentum",
}


def build_scene_objectives_block(player, kind, action_context=None, *, structure_mode=None):
    stakes = player.get("scene_stakes") or {}
    ctx = action_context or {}
    purpose = stakes.get("purpose") or PURPOSE_BY_KIND.get(kind, "advance the moment")
    question = stakes.get("dramatic_question")
    gain = stakes.get("gain")
    lose = stakes.get("lose")

    emotion = EMOTION_BY_STRUCTURE.get(structure_mode or "action", "focused attention")
    if ctx.get("skill_check") and not ctx["skill_check"].get("success"):
        emotion = "friction"
    if kind in ("attack", "threaten", "accuse"):
        emotion = "pressure"

    conflict = None
    if lose and gain:
        conflict = f"{lose} vs {gain}"
    elif question:
        conflict = question[:90]

    lines = [
        "SCENE OBJECTIVES (write toward these — not filler atmosphere):",
        f"- Purpose: {purpose[:100]}",
        f"- Emotion: {emotion}",
    ]
    if conflict:
        lines.append(f"- Dramatic question: {conflict[:100]}")
    if question and question not in (conflict or ""):
        lines.append(f"- Open question: {question[:100]}")
    if lose:
        lines.append(f"- At stake if this fails: {lose[:80]}")
    if gain:
        lines.append(f"- Possible gain: {gain[:80]}")
    return "\n".join(lines)
