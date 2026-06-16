"""
Quick offline state inspector — no server required.

  python scripts/debug_state.py              # summary
  python scripts/debug_state.py player       # player JSON highlights
  python scripts/debug_state.py last-turn    # last journal entry
  python scripts/debug_state.py travel       # destinations from current area
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from storage import load
from simulation.travel_engine import list_destinations
from simulation.ui_state import _format_destination, get_full_state


def _print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_summary():
    player = load("player/player.json", {})
    world = load("world/world_state.json", {})
    if not player:
        print("No player save. Create a character first.")
        return
    print(f"Name:     {player.get('name', '?')}")
    print(f"Place:    {player.get('area')} ({player.get('location')})")
    print(f"Day:      {world.get('day')} · {world.get('time_of_day')} · {world.get('weather')}")
    stats = player.get("stats") or {}
    print(f"Health:   {stats.get('health')}/{stats.get('max_health')}")
    print(f"Wealth:   {player.get('wealth', 0)}c")
    journal = player.get("journal") or []
    print(f"Journal:  {len(journal)} entries")
    if journal:
        last = journal[-1]
        print(f"Last:     [{last.get('kind')}] {last.get('action', '')[:60]}")


def cmd_player():
    state = get_full_state()
    if not state:
        print("No player save.")
        return
    _print_json(state["player"])


def cmd_last_turn():
    player = load("player/player.json", {})
    journal = player.get("journal") or []
    if not journal:
        print("No journal entries yet.")
        return
    _print_json(journal[-1])


def cmd_travel():
    player = load("player/player.json", {})
    areas = load("world/areas.json", {})
    locs = load("world/locations.json", {})
    area = player.get("area")
    dests = list_destinations(area)
    if not dests:
        print(f"No destinations from {area}")
        return
    print(f"From {area}:")
    for aid, hours in sorted(dests.items(), key=lambda x: x[1]):
        d = _format_destination(aid, hours, areas, locs)
        print(f"  {d['hours']:>3}h  {d['label']}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "summary").lower()
    handlers = {
        "summary": cmd_summary,
        "player": cmd_player,
        "last-turn": cmd_last_turn,
        "last": cmd_last_turn,
        "travel": cmd_travel,
        "map": cmd_travel,
    }
    fn = handlers.get(cmd)
    if not fn:
        print(f"Unknown command: {cmd}")
        print("Usage: python scripts/debug_state.py [summary|player|last-turn|travel]")
        sys.exit(1)
    fn()


if __name__ == "__main__":
    main()
