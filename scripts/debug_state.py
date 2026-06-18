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
    bstats = player.get("boundary_stats") or {}
    if bstats.get("turns"):
        print(f"Boundary: {bstats.get('turns')} turns | "
              f"clf disagree {bstats.get('classifier_disagrees', 0)} | "
              f"facts miss {bstats.get('facts_missing', 0)}/{bstats.get('facts_expected', 0)} | "
              f"audit confirm {bstats.get('auditor_confirmed', 0)}/{bstats.get('auditor_nominations', 0)} | "
              f"gate {bstats.get('gate_violations', 0)}")


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


def cmd_boundary():
    from simulation.turn_trace import get_last_turn, get_boundary_history, get_boundary_summary
    from simulation.boundary_metrics import summarize_player_boundary_history
    player = load("player/player.json", {})
    saved_hist = player.get("boundary_history") or []
    mem_hist = get_boundary_history()
    history = saved_hist if saved_hist else mem_hist
    last_trace = player.get("last_boundary_trace") or get_last_turn()
    summary = (
        summarize_player_boundary_history(saved_hist)
        if saved_hist
        else get_boundary_summary()
    )
    payload = {
        "session_stats": player.get("boundary_stats") or {},
        "last_turn_trace": last_trace,
        "history_summary": summary,
        "recent_history": history[-10:],
    }
    narrative = (last_trace or {}).get("narrative") or {}
    if narrative:
        payload["narrative_summary"] = {
            "dramatic_question": narrative.get("dramatic_question"),
            "structure_mode": narrative.get("structure_mode"),
            "promises_open": narrative.get("promises_open"),
            "narrator_block_count": narrative.get("narrator_block_count"),
            "arc_stage": narrative.get("arc_stage") or narrative.get("beat_plan_arc_stage"),
            "regen_mode": narrative.get("regen_mode"),
            "last_issues": (last_trace or {}).get("narrative_issues") or [],
        }
    beat_plan = (last_trace or {}).get("beat_plan") or {}
    if beat_plan:
        payload["beat_plan"] = beat_plan
    orchestrator = (last_trace or {}).get("orchestrator") or {}
    if orchestrator:
        payload["orchestrator"] = orchestrator
    prompt_profile = (last_trace or {}).get("prompt_profile") or {}
    if prompt_profile:
        payload["prompt_profile"] = {
            "est_tokens": prompt_profile.get("est_tokens"),
            "top_modules": [
                {"name": m.get("name"), "est_tokens": m.get("est_tokens")}
                for m in (prompt_profile.get("modules") or [])[:8]
            ],
        }
    validator_chain = (last_trace or {}).get("validator_chain") or []
    if validator_chain:
        payload["validator_chain"] = validator_chain
    clarification = (last_trace or {}).get("clarification") or {}
    if clarification:
        payload["clarification"] = {
            "target_ambiguous": clarification.get("target_ambiguous"),
            "interpretation_clarify": clarification.get("interpretation_clarify"),
            "clarify_reason": clarification.get("clarify_reason"),
            "reprompt": clarification.get("reprompt"),
            "pending_reason": (clarification.get("pending") or {}).get("reason"),
            "pending_fail_count": (clarification.get("pending") or {}).get("fail_count"),
        }
    interp = (last_trace or {}).get("interpretation") or {}
    if interp:
        payload["interpretation_summary"] = {
            "kind": (interp.get("kind") or {}).get("value"),
            "target": (interp.get("target") or {}).get("value"),
            "topic": (interp.get("topic") or {}).get("value"),
            "clarify": interp.get("clarify"),
            "inventory_missing": interp.get("inventory_missing"),
            "duplicate_action": interp.get("duplicate_action"),
        }
    _print_json(payload)


def cmd_scheduled():
    from simulation.scheduled_events import list_pending_events
    player = load("player/player.json", {})
    world = load("world/world_state.json", {})
    area = player.get("area")
    if not player:
        print("No player save.")
        return
    pending = list_pending_events(player, area)
    store = (player.get("scheduled_events") or {}).get(area or "", {})
    hc = world.get("hour_count", 0)
    payload = {
        "area": area,
        "hour_count": hc,
        "pending": [
            {
                "id": e.get("id"),
                "label": e.get("label"),
                "fires_at_hour": e.get("fires_at_hour"),
                "hours_until": max(0, (e.get("fires_at_hour") or hc) - hc),
                "source": e.get("source"),
            }
            for e in pending
        ],
        "all_in_area": {
            eid: {
                "label": rec.get("label"),
                "fires_at_hour": rec.get("fires_at_hour"),
                "fired": rec.get("fired"),
                "source": rec.get("source"),
            }
            for eid, rec in store.items()
        },
    }
    _print_json(payload)


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
        "boundary": cmd_boundary,
        "scheduled": cmd_scheduled,
        "events": cmd_scheduled,
        "travel": cmd_travel,
        "map": cmd_travel,
    }
    fn = handlers.get(cmd)
    if not fn:
        print(f"Unknown command: {cmd}")
        print("Usage: python scripts/debug_state.py [summary|player|last-turn|boundary|scheduled|travel]")
        sys.exit(1)
    fn()


if __name__ == "__main__":
    main()
