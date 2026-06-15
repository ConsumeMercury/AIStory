import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def log_player_event(action, outcome, location, tick):
    player_path = os.path.join(BASE_DIR, "player", "player.json")
    with open(player_path) as f:
        player = json.load(f)

    player.setdefault("journal", [])
    player["journal"].append({
        "tick": tick,
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "outcome": outcome,
        "location": location,
    })

    # Keep last 100 journal entries to avoid unbounded growth
    player["journal"] = player["journal"][-100:]

    with open(player_path, "w") as f:
        json.dump(player, f, indent=2)

def get_player_memories(limit=10):
    player_path = os.path.join(BASE_DIR, "player", "player.json")
    with open(player_path) as f:
        player = json.load(f)
    return player.get("journal", [])[-limit:]