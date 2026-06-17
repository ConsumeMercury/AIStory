def check_goal_progress(npc, action, wealth_gain=0):
    completed = []

    goals = npc.setdefault("goals", list(npc.get("goals") or []))
    for goal in list(goals):

        if goal == "accumulate wealth" and npc.get("wealth", 0) >= 500:
            completed.append(goal)
            goals.remove(goal)
            goals.append("maintain wealth")

        elif goal == "gain power" and action == "plan":
            npc.setdefault("goals_progress", {})
            npc["goals_progress"]["gain power"] = npc["goals_progress"].get("gain power", 0) + 1

        elif goal == "help others" and action == "help":
            npc.setdefault("goals_progress", {})
            npc["goals_progress"]["help others"] = npc["goals_progress"].get("help others", 0) + 1

    return completed