"""
Labeled interpretation benchmark — scored pass rate on every commit.

Run: python -m simulation.interpretation_benchmark
Or via scripts/verify_all.py test_interpretation_benchmark_offline
"""

from __future__ import annotations

from dataclasses import dataclass, field

from simulation.action_interpreter import interpret_action
from simulation.scene_state import SceneState
from tests.fixtures.catalog_fixtures import npc, player


@dataclass
class BenchmarkCase:
    action: str
    tag: str
    expect: dict = field(default_factory=dict)
    present: list | None = None
    player_extra: dict | None = None
    journal: list | None = None


def _default_present():
    return [
        npc("p1", role="priest", name="Hale", gender="male"),
        npc("g1", role="guard", name="Holt", gender="male"),
        npc("w1", role="merchant", name="Mara", gender="female"),
    ]


def _two_men():
    return [
        npc("g1", role="guard", name="Holt", gender="male"),
        npc("g2", role="guard", name="Venn", gender="male"),
    ]


def _one_man():
    return [npc("g1", role="guard", name="Holt", gender="male")]


BENCHMARK_CASES = [
    BenchmarkCase("talk to the priest", "role_match", {"kind": "talk", "has_target": True}),
    BenchmarkCase(
        "Talk to the woman", "gender_absent",
        {"kind": "talk", "target_failed": True},
        present=_two_men(),
    ),
    BenchmarkCase(
        "talk to the woman", "mislabel_single",
        {"kind": "talk", "mislabel": True, "has_target": True},
        present=_one_man(),
    ),
    BenchmarkCase("don't attack, just talk", "negation", {"kind": "talk", "negation": True}),
    BenchmarkCase("talk to myself", "self_target", {"kind": "observe", "self_target": True}),
    BenchmarkCase("examine the bird", "object", {"kind": "examine", "object_ref": True}),
    BenchmarkCase("ask about stuff", "vague_topic", {"clarify": True}),
    BenchmarkCase("give her 5 silver", "quantity", {"kind": "give", "give_amount": True}),
    BenchmarkCase("I fly away", "impossible", {"impossible_action": True, "kind": "observe"}),
    BenchmarkCase("I cast a spell", "impossible_magic", {"impossible_action": True}),
    BenchmarkCase("say nothing and watch", "silence", {"deliberate_silence": True}),
    BenchmarkCase("I want to...", "incomplete", {"clarify": True}),
    BenchmarkCase("do something interesting", "vague_intent", {"vague_player_intent": True, "kind": "explore"}),
    BenchmarkCase("lie and say I'm a merchant", "deceive", {"kind": "deceive", "declared_deception": True}),
    BenchmarkCase("demand answers", "manner_hostile", {"manner": "hostile"}),
    BenchmarkCase("gently ask about the gate", "manner_gentle", {"manner": "gentle"}),
    BenchmarkCase("skip ahead", "pacing", {"pacing_skip": True, "kind": "wait"}),
    BenchmarkCase("take that back", "in_world_undo", {"in_world_undo": True}),
    BenchmarkCase("should I trust her?", "rumination", {"rumination": True, "clarify": True}),
    BenchmarkCase("tell her to follow me", "relay", {"relay_command": True}),
    BenchmarkCase("*draws sword* back off", "stage_dir", {"stage_directions": True}),
    BenchmarkCase("ask the guard (politely) about the murder", "paren_manner", {"manner": "gentle"}),
    BenchmarkCase(
        "look around", "stale_repeat",
        {"stale_repetition": True},
        journal=[{"action": "look around", "kind": "explore", "area": "hq"},
                 {"action": "look around", "kind": "explore", "area": "hq"}],
        player_extra={"area": "hq"},
    ),
    BenchmarkCase(
        "ask about the gate", "conv_loop",
        {"conversational_loop": True},
        present=_one_man(),
        journal=[
            {"action": "talk", "kind": "talk", "focus_npc": "g1", "area": "hq"},
            {"action": "ask", "kind": "ask_about", "focus_npc": "g1", "area": "hq"},
            {"action": "ask", "kind": "ask_about", "focus_npc": "g1", "area": "hq"},
        ],
        player_extra={"area": "hq", "scene_focus": "g1"},
    ),
    BenchmarkCase(
        "show her the badge", "inventory_missing",
        {"inventory_missing": True},
        player_extra={"inventory": []},
    ),
    BenchmarkCase(
        "ask the beggar about royal succession", "topic_out_of_depth",
        {"topic_knowledge_blocked": True},
        present=[npc("b1", role="beggar", name="Rat", gender="male")],
        player_extra={"scene_focus": "b1"},
    ),
]


def _check_expect(ctx: dict, pre: dict, expect: dict) -> list[str]:
    failures = []
    for key, val in expect.items():
        if key == "kind":
            if ctx.get("kind") != val:
                failures.append(f"kind={ctx.get('kind')!r} expected {val!r}")
        elif key == "clarify":
            if bool(ctx.get("interpretation_clarify")) != val:
                failures.append(f"clarify={ctx.get('interpretation_clarify')} expected {val}")
        elif key == "has_target":
            if bool(ctx.get("target_id")) != val:
                failures.append(f"has_target={bool(ctx.get('target_id'))} expected {val}")
        elif key == "target_failed":
            if bool(ctx.get("target_constraint_failed")) != val:
                failures.append(f"target_constraint_failed={ctx.get('target_constraint_failed')} expected {val}")
        elif key == "mislabel":
            if bool(ctx.get("mislabel_resolution")) != val:
                failures.append(f"mislabel_resolution={ctx.get('mislabel_resolution')} expected {val}")
        elif key == "negation":
            got = (ctx.get("interpretation_preprocess") or {}).get("negation_detected")
            if bool(got) != val:
                failures.append(f"negation={got} expected {val}")
        elif key == "self_target":
            if bool(ctx.get("self_target")) != val:
                failures.append(f"self_target={ctx.get('self_target')} expected {val}")
        elif key == "object_ref":
            if bool(ctx.get("object_ref")) != val:
                failures.append(f"object_ref={ctx.get('object_ref')} expected {val}")
        elif key == "give_amount":
            if not ctx.get("give_amount"):
                failures.append("give_amount missing")
        elif key in ctx:
            if ctx.get(key) != val and not (val is True and ctx.get(key)):
                failures.append(f"{key}={ctx.get(key)!r} expected {val!r}")
        elif val is True:
            if not ctx.get(key):
                failures.append(f"{key} missing")
        elif ctx.get(key) != val:
            failures.append(f"{key}={ctx.get(key)!r} expected {val!r}")
    return failures


def run_benchmark(*, cases=None) -> dict:
    """Run labeled cases; return summary with pass rate and failures."""
    cases = cases or BENCHMARK_CASES
    world = {"time_of_day": "day", "weather": "Clear"}
    passed = 0
    failed_rows = []

    for case in cases:
        present = case.present or _default_present()
        pl = player(scene_focus=present[0]["id"], wealth=50)
        pl["area"] = (case.player_extra or {}).get("area", "hq")
        if case.player_extra:
            pl.update({k: v for k, v in case.player_extra.items() if k != "area"})
        if case.journal:
            pl["journal"] = list(case.journal)
        npcs = {n["id"]: n for n in present}
        cast_ids = frozenset(n["id"] for n in present)
        scene = SceneState(
            tick=1, day=1, hour=10, time_of_day="day",
            area_id=pl.get("area", "hq"), subplace_id="gate",
            place_label="Test scene",
            area_present=tuple(present), cast=tuple(present), cast_ids=cast_ids,
            scene_focus=pl.get("scene_focus"), pending_events=(),
        )
        ctx = interpret_action(case.action, pl, present, world, npcs=npcs, scene_state=scene)
        pre = ctx.get("interpretation_preprocess") or {}
        failures = _check_expect(ctx, pre, case.expect)
        if failures:
            failed_rows.append({
                "tag": case.tag,
                "action": case.action[:60],
                "failures": failures,
            })
        else:
            passed += 1

    total = len(cases)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "failures": failed_rows,
    }


def main():
    result = run_benchmark()
    print(f"interpretation benchmark: {result['passed']}/{result['total']} "
          f"({result['pass_rate'] * 100:.1f}%)")
    for row in result["failures"]:
        print(f"  FAIL [{row['tag']}] {row['action']!r}")
        for f in row["failures"]:
            print(f"       - {f}")
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
