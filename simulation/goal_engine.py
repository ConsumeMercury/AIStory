def check_goal_progress(npc, action, wealth_gain=0):
    completed = []

    for goal in list(npc.get("goals", [])):

        if goal == "accumulate wealth" and npc.get("wealth", 0) >= 500:
            completed.append(goal)
            npc["goals"].remove(goal)
            npc["goals"].append("maintain wealth")

        elif goal == "gain power" and action == "plan":
            npc.setdefault("goals_progress", {})
            npc["goals_progress"]["gain power"] = npc["goals_progress"].get("gain power", 0) + 1

        elif goal == "help others" and action == "help":
            npc.setdefault("goals_progress", {})
            npc["goals_progress"]["help others"] = npc["goals_progress"].get("help others", 0) + 1

    return completed