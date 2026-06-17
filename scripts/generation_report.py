"""
Thorough live simulation + generation audit.

Runs many varied actions, checks mechanical state updates (time, stats, NPCs,
inventory, combat, travel, journal), optionally calls Gemini for prose quality,
and writes a detailed report to generation_report.txt.

  python scripts/generation_report.py --live
  python scripts/generation_report.py --live --no-restore   # keep mutated save

Stop api/server.py first — it locks player.json on Windows.
"""

import argparse
import datetime
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.generation_checks import (  # noqa: E402
    FULL_SCENARIOS,
    SCENARIOS,
    analyze_prose,
    backup_saves,
    build_beat_context,
    capture_state,
    format_delta,
    mechanical_checks,
    reset_baseline,
    restore_saves,
)

DEFAULT_REPORT = os.path.join(ROOT, "generation_report.txt")


def _pause_background_sim():
    """Stop api/server background ticks so JSON saves are not contested."""
    from simulation import simulation_runner
    worker = getattr(simulation_runner, "_worker", None)
    if worker is not None and worker.is_alive():
        simulation_runner.stop()
        return True
    return False


def _resume_background_sim(was_running):
    if was_running:
        from simulation import simulation_runner
        simulation_runner.start()


def _header_lines(live, scenarios, backups):
    from simulation.gemini_client import api_key

    player = backups["player"]
    lines = [
        "=" * 78,
        "AIStory Live Simulation Report",
        f"Generated: {datetime.datetime.now().isoformat(timespec='seconds')}",
        f"Mode: {'LIVE (Gemini)' if live else 'OFFLINE (mock prose)'}",
        f"GEMINI_API_KEY: {'set' if api_key() else 'MISSING'}",
        f"Player: {player.get('name', '?')} @ {player.get('area')} ({player.get('location')})",
        f"Scenarios: {len(scenarios)}",
        "=" * 78,
        "",
    ]
    return lines


def _format_beat_report(scenario, beat_num, beat, lines_out):
    lines_out.append(f"--- [{scenario}] beat {beat_num}: {beat['action']!r} ---")
    lines_out.append(
        f"  kind={beat['kind']} | sim_tick {beat['sim_tick_before']}->{beat['sim_tick_after']} | "
        f"hour {beat['hour_before']}->{beat['hour_after']} (day {beat['day_after']}) | "
        f"area={beat['area_after']}"
    )
    lines_out.append(
        f"  health {beat['health_before']}->{beat['health_after']} | "
        f"stamina {beat['stamina_before']}->{beat['stamina_after']} | "
        f"wealth {beat['wealth_before']}->{beat['wealth_after']} | "
        f"inv {beat['inv_before']}->{beat['inv_after']}"
    )
    lines_out.append(
        f"  focus={beat['focus_npc']} | combat_target={beat['combat_target']} | "
        f"fatal={beat['combat_fatal']} | journal+={beat['journal_delta']}"
    )
    if beat.get("skill_check"):
        sc = beat["skill_check"]
        lines_out.append(
            f"  skill_check: {sc.get('skill')} roll={sc.get('roll')} total={sc.get('total')} "
            f"vs {sc.get('difficulty')} success={sc.get('success')}"
        )
    lines_out.append(f"  delta: {beat['delta_summary']}")
    mech = beat.get("mech_issues") or []
    prose = beat.get("prose_issues") or []
    api_err = beat.get("api_error")
    lines_out.append(f"  MECH: {'OK' if not mech else 'ISSUES: ' + repr(mech)}")
    lines_out.append(f"  PROSE: {'OK' if not prose else 'ISSUES: ' + repr(prose)}")
    if api_err:
        lines_out.append(f"  API: FAILED — {api_err[:200]}")
    lines_out.append(f"  scene_len={beat.get('scene_len', 0)}")
    if beat.get("scene_preview"):
        preview = beat["scene_preview"].replace("\n", " ")
        lines_out.append(f"  preview: {preview[:400]}")
    lines_out.append("")


def run_scenario(name, actions, live):
    from storage import load
    from simulation import simulation_runner
    from simulation.story_loop import process_player_action

    reset_baseline()
    beats = []
    all_mech = []
    all_prose = []
    all_api = []

    for action in actions:
        player = load("player/player.json", {})
        world = load("world/world_state.json", {})
        npcs = load("characters/npcs.json", {})
        sim_before = simulation_runner.get_current_tick()
        before = capture_state(player, world, npcs, sim_before)

        try:
            scene = process_player_action(action)
        except Exception as e:
            err = str(e)
            all_api.append(f"[{name}] {action!r}: {err}")
            beats.append({
                "action": action,
                "kind": None,
                "sim_tick_before": before["sim_tick"],
                "sim_tick_after": before["sim_tick"],
                "hour_before": before["hour_count"],
                "hour_after": before["hour_count"],
                "day_after": before["day"],
                "area_after": before["area"],
                "health_before": before["health"],
                "health_after": before["health"],
                "stamina_before": before["stamina"],
                "stamina_after": before["stamina"],
                "wealth_before": before["wealth"],
                "wealth_after": before["wealth"],
                "inv_before": before["inv_count"],
                "inv_after": before["inv_count"],
                "focus_npc": None,
                "combat_target": before.get("last_combat_target"),
                "combat_fatal": before.get("last_combat_fatal"),
                "journal_delta": 0,
                "skill_check": None,
                "delta_summary": "(action failed — state may be partial)",
                "mech_issues": [],
                "prose_issues": [],
                "api_error": err,
                "scene_len": 0,
                "scene_preview": "",
            })
            break

        player = load("player/player.json", {})
        world = load("world/world_state.json", {})
        npcs = load("characters/npcs.json", {})
        sim_after = simulation_runner.get_current_tick()
        after = capture_state(player, world, npcs, sim_after)

        journal = player.get("journal") or []
        last = journal[-1] if journal else {}
        kind = last.get("kind")

        mech = mechanical_checks(action, kind, before, after, last, npcs)
        ctx = build_beat_context(last, player, npcs)
        prose = analyze_prose(scene or "", ctx, player, npcs) if live else []

        beat = {
            "action": action,
            "kind": kind,
            "sim_tick_before": before["sim_tick"],
            "sim_tick_after": after["sim_tick"],
            "hour_before": before["hour_count"],
            "hour_after": after["hour_count"],
            "day_after": after["day"],
            "area_after": after["area"],
            "health_before": before["health"],
            "health_after": after["health"],
            "stamina_before": before["stamina"],
            "stamina_after": after["stamina"],
            "wealth_before": before["wealth"],
            "wealth_after": after["wealth"],
            "inv_before": before["inv_count"],
            "inv_after": after["inv_count"],
            "focus_npc": last.get("focus_npc"),
            "combat_target": after.get("last_combat_target"),
            "combat_fatal": last.get("combat_fatal") if kind == "attack" else after.get("last_combat_fatal"),
            "journal_delta": after["journal_len"] - before["journal_len"],
            "skill_check": player.get("last_check"),
            "delta_summary": format_delta(before, after),
            "mech_issues": mech,
            "prose_issues": prose,
            "scene_len": len(scene or ""),
            "scene_preview": (scene or "")[:500],
        }
        beats.append(beat)
        all_mech.extend(f"[{name}] {action!r}: {m}" for m in mech)
        all_prose.extend(f"[{name}] {action!r}: {p}" for p in prose)

    return {
        "scenario": name,
        "beats": beats,
        "mech_issues": all_mech,
        "prose_issues": all_prose,
        "api_issues": all_api,
    }


def write_report(path, live, scenario_map, results, backups):
    lines = _header_lines(live, scenario_map, backups)

    total_beats = sum(len(r["beats"]) for r in results)
    mech_all = [i for r in results for i in r["mech_issues"]]
    prose_all = [i for r in results for i in r["prose_issues"]]
    api_all = [i for r in results for i in r.get("api_issues", [])]

    lines.extend([
        "SUMMARY",
        f"  Total beats: {total_beats}",
        f"  Mechanical issues: {len(mech_all)}",
        f"  Prose issues: {len(prose_all)}",
        f"  API errors: {len(api_all)}",
        "",
    ])
    for r in results:
        n_m = len(r["mech_issues"])
        n_p = len(r["prose_issues"])
        n_a = len(r.get("api_issues", []))
        if n_a:
            status = f"api={n_a}" + (f" mech={n_m}" if n_m else "") + (f" prose={n_p}" if n_p else "")
        elif not n_m and not n_p:
            status = "OK"
        else:
            status = f"mech={n_m} prose={n_p}"
        lines.append(f"  {r['scenario']}: {status}")
    lines.append("")
    lines.append("=" * 78)
    lines.append("DETAILED BEATS")
    lines.append("=" * 78)
    lines.append("")

    for r in results:
        lines.append(f"### Scenario: {r['scenario']} ({len(r['beats'])} beats)")
        lines.append("")
        for i, beat in enumerate(r["beats"], 1):
            _format_beat_report(r["scenario"], i, beat, lines)

    if mech_all or prose_all or api_all:
        lines.append("=" * 78)
        lines.append("ALL ISSUES")
        lines.append("=" * 78)
        idx = 1
        for msg in api_all:
            lines.append(f"  {idx}. [API] {msg}")
            idx += 1
        for msg in mech_all:
            lines.append(f"  {idx}. [MECH] {msg}")
            idx += 1
        for msg in prose_all:
            lines.append(f"  {idx}. [PROSE] {msg}")
            idx += 1
        lines.append("")

    total_issues = len(mech_all) + len(prose_all) + len(api_all)
    lines.append("=" * 78)
    if total_issues:
        lines.append(f"FAILED - {total_issues} issue(s)")
    else:
        lines.append("PASSED - no issues flagged")
    lines.append("=" * 78)

    text = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text, total_issues


def main():
    parser = argparse.ArgumentParser(description="Thorough live simulation + generation audit")
    parser.add_argument("--live", action="store_true", help="Call Gemini (requires GEMINI_API_KEY)")
    parser.add_argument(
        "--report", default=DEFAULT_REPORT,
        help=f"Report output path (default: {DEFAULT_REPORT})",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Run only dock_fight + social (fast smoke)",
    )
    parser.add_argument(
        "--no-restore", action="store_true",
        help="Do not restore player/world/npcs after the run",
    )
    parser.add_argument(
        "--scenario", default="",
        help="Run a single scenario name from the full pack",
    )
    args = parser.parse_args()

    if args.quick:
        scenario_map = dict(SCENARIOS)
    elif args.scenario:
        scenario_map = {args.scenario: FULL_SCENARIOS.get(args.scenario) or SCENARIOS.get(args.scenario)}
        if not scenario_map.get(args.scenario):
            names = sorted(set(FULL_SCENARIOS) | set(SCENARIOS))
            print(f"Unknown scenario {args.scenario!r}. Available: {', '.join(names)}")
            sys.exit(1)
    else:
        scenario_map = FULL_SCENARIOS

    if args.live:
        from simulation.gemini_client import require_api_key
        require_api_key()
    else:
        from unittest.mock import MagicMock, patch
        mock_narr = MagicMock()
        mock_narr.generate_scene.return_value = (
            "You stand at the docks. Rain on the pilings. She watches you, "
            "in grey wool. (offline mock scene)"
        )
        mock = patch("simulation.story_loop.get_narrator", return_value=mock_narr)
        mock.start()

    backups = backup_saves()
    results = []
    exit_code = 0
    sim_was_running = _pause_background_sim()
    if sim_was_running:
        print("Paused background simulation (stop api/server.py during runs if saves still lock).\n")

    try:
        print(f"Running {len(scenario_map)} scenario(s) ({'live' if args.live else 'offline'})...")
        print(f"Report -> {args.report}")
        print("(Stop api/server.py if player.json is locked.)\n")

        for name, actions in scenario_map.items():
            print(f"  {name}...", flush=True)
            try:
                results.append(run_scenario(name, actions, args.live))
            except Exception as e:
                results.append({
                    "scenario": name,
                    "beats": [],
                    "mech_issues": [],
                    "prose_issues": [],
                    "api_issues": [f"scenario crashed: {e}"],
                })
                traceback.print_exc()

        report_text, issue_count = write_report(
            args.report, args.live, scenario_map, results, backups,
        )
        print(report_text[-1200:])
        print(f"\nFull report written to: {os.path.abspath(args.report)}")
        exit_code = 1 if issue_count else 0
    finally:
        if not args.live:
            mock.stop()
        if not args.no_restore:
            restore_saves(backups)
            print("\nSave files restored to pre-run state.")
        else:
            print("\nSave files left as-is (--no-restore).")
        _resume_background_sim(sim_was_running)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
