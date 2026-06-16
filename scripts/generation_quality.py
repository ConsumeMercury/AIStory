"""
Generation quality runner — multi-action scenarios with optional live Gemini prose.

Quick checks:
  python scripts/generation_quality.py
  python scripts/generation_quality.py --live

Thorough audit (time, stats, NPCs, travel, full report file):
  python scripts/generation_report.py --live
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.generation_checks import (  # noqa: E402
    SCENARIOS,
    analyze_prose,
    build_beat_context,
    mechanical_checks,
    reset_baseline,
)


def run_scenario(name, actions, live=False):
    from storage import load
    from simulation import simulation_runner
    from simulation.story_loop import process_player_action
    from scripts.generation_checks import capture_state

    reset_baseline()
    report = {"scenario": name, "beats": [], "issues": []}

    for action in actions:
        player = load("player/player.json", {})
        world = load("world/world_state.json", {})
        npcs = load("characters/npcs.json", {})
        before = capture_state(player, world, npcs, simulation_runner.get_current_tick())
        before_inv = before["inv_count"]

        scene = process_player_action(action)

        player = load("player/player.json", {})
        npcs = load("characters/npcs.json", {})
        world = load("world/world_state.json", {})
        after = capture_state(player, world, npcs, simulation_runner.get_current_tick())
        journal = player.get("journal") or []
        last = journal[-1] if journal else {}
        beat = {
            "action": action,
            "kind": last.get("kind"),
            "focus_npc": last.get("focus_npc"),
            "scene_focus": player.get("scene_focus"),
            "inventory_delta": after["inv_count"] - before_inv,
            "last_combat_fatal": player.get("last_combat_fatal"),
            "scene_preview": (scene or "")[:280],
        }
        ctx = build_beat_context(last, player, npcs)
        if live:
            issues = analyze_prose(scene or "", ctx, player, npcs)
        else:
            issues = mechanical_checks(action, last.get("kind"), before, after, last, npcs)
        beat["issues"] = issues
        report["issues"].extend(issues)
        report["beats"].append(beat)

    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Call Gemini (requires GEMINI_API_KEY)")
    parser.add_argument("--scenario", default="all", help="Scenario name or 'all'")
    args = parser.parse_args()

    if args.live:
        from simulation.gemini_client import require_api_key
        require_api_key()
    else:
        from unittest.mock import patch
        patcher = patch(
            "simulation.story_loop.generate_scene",
            return_value="You stand at the docks. She watches you. (offline mock scene)",
        )
        patcher.start()

    try:
        names = list(SCENARIOS.keys()) if args.scenario == "all" else [args.scenario]
        total_issues = 0
        for name in names:
            if name not in SCENARIOS:
                print(f"Unknown scenario: {name}")
                sys.exit(1)
            rep = run_scenario(name, SCENARIOS[name], live=args.live)
            print(f"\n=== {name} ({'live' if args.live else 'offline'}) ===")
            for b in rep["beats"]:
                flag = f" ISSUES:{b['issues']}" if b["issues"] else ""
                print(
                    f"  {b['action']!r} kind={b['kind']} focus={b['focus_npc']} "
                    f"inv+={b['inventory_delta']} fatal={b['last_combat_fatal']}{flag}"
                )
                if args.live and b.get("scene_preview"):
                    print(f"    {b['scene_preview'][:200]}...")
            if rep["issues"]:
                total_issues += len(rep["issues"])
                print(f"  >> {len(rep['issues'])} issue(s): {rep['issues']}")
            else:
                print("  >> OK")

        if total_issues:
            print(f"\n{total_issues} quality issue(s) flagged.")
            sys.exit(1)
        print("\nAll scenarios passed quality checks.")
    finally:
        if not args.live:
            patcher.stop()


if __name__ == "__main__":
    main()
