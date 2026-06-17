"""
NPC planning — personal objectives decomposed into subgoals that bias actions.
"""

SUBGOAL_ACTIONS = {
    "recover": ("plan", "study"),
    "prove": ("study", "plan"),
    "expose": ("plan", "study"),
    "steal": ("plan", "hide"),
    "sell": ("trade", "plan"),
    "marry": ("socialise", "plan"),
    "avenge": ("plan", "fight"),
    "catch": ("plan", "study"),
    "protect": ("help", "hide"),
    "find": ("study", "travel"),
    "escape": ("hide", "travel"),
    "publish": ("study", "socialise"),
    "decode": ("study", "craft"),
    "earn": ("plan", "socialise"),
}


def derive_subgoals(npc):
    obj = npc.get("personal_objective")
    text = obj.get("text", "") if isinstance(obj, dict) else (obj or "")
    if not text:
        return []
    lower = text.lower()
    goals = npc.setdefault("subgoals", [])
    if goals and goals[0].get("source") == text[:80]:
        return goals
    found = []
    for keyword, actions in SUBGOAL_ACTIONS.items():
        if keyword in lower:
            found.append({
                "text": keyword,
                "actions": list(actions),
                "source": text[:80],
                "progress": 0,
            })
    if not found:
        found.append({"text": "pursue objective", "actions": ["plan", "socialise"], "source": text[:80], "progress": 0})
    npc["subgoals"] = found[:4]
    return npc["subgoals"]


def apply_plan_weights(npc, weights):
    subgoals = derive_subgoals(npc)
    if not subgoals:
        return
    primary = subgoals[0]
    for act in primary.get("actions") or []:
        weights[act] = weights.get(act, 5) + 16


def advance_subgoal(npc, action):
    subgoals = npc.get("subgoals") or []
    if not subgoals:
        return
    sg = subgoals[0]
    if action in (sg.get("actions") or []):
        sg["progress"] = sg.get("progress", 0) + 1
        if sg["progress"] >= 5 and len(subgoals) > 1:
            npc["subgoals"] = subgoals[1:]
