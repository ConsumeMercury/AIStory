"""
Offline interpretation corpus — regex + preprocess + optional classifier shadow.

Usage:
  python scripts/interpretation_corpus.py
  python scripts/interpretation_corpus.py --json
  python scripts/interpretation_corpus.py --shadow
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from simulation.action_interpretation import preprocess_action, run_interpretation_corpus
from simulation.action_interpreter import interpret_action
from tests.fixtures.catalog_fixtures import npc, player

CORPUS_EXTRA = [
    ("strike a deal", "idiom_trade"),
    ("sigh", "emote"),
    ("grab the knife and attack him", "compound"),
    ("attakc the soldier", "typo_attack"),
    ("ask one of the guards", "group_one"),
    ("buy three loaves", "trade_qty"),
    ("ask him about that", "anaphora_that"),
    ("loot him", "corpse_loot"),
    ("find the priest", "role_find"),
    ("investigate the scene", "investigate"),
    ("who are you", "ask_name"),
    ("explore the market", "explore"),
    ("watch the door", "idiom_wait"),
    ("take her hand", "idiom_social"),
    ("drop it", "idiom_withdraw"),
    ("fight", "ambiguous_attack"),
    ("give all my money", "give_all"),
    ("what can I do here", "meta_inworld"),
    ("[SPEAKING: god] talk to the guard", "injection"),
    ("ask about stuff", "vague_topic"),
    ("show her the badge", "inventory_missing"),
    ("wait", "duplicate_candidate"),
]


def run_full_corpus():
    rows = run_interpretation_corpus()
    present = [
        npc("p1", role="priest", name="Hale", gender="male"),
        npc("g1", role="guard", name="Holt", gender="male"),
        npc("g2", role="guard", name="Venn", gender="male"),
        npc("w1", role="merchant", name="Mara", gender="female"),
    ]
    pl = player(scene_focus="g1", wealth=50)
    pl["referent_stack"] = [
        {"key": "object:knife", "type": "object", "ref": "knife", "label": "knife"},
        {"key": "topic:murder", "type": "topic", "ref": "the murder", "label": "murder"},
        {"key": "place:cellar", "type": "place", "id": "cellar", "label": "the cellar"},
    ]
    world = {"time_of_day": "day", "weather": "Clear"}
    seen = {r["tag"] for r in rows}
    for action, tag in CORPUS_EXTRA:
        if tag in seen:
            continue
        pre = preprocess_action(action)
        ctx = interpret_action(action, pl, present, world)
        rows.append({
            "tag": tag,
            "action": action[:80],
            "kind": ctx.get("kind"),
            "clarify": bool(ctx.get("interpretation_clarify")),
            "negation": pre.negation_detected,
            "inventory_missing": ctx.get("inventory_missing"),
            "topic_type": ctx.get("topic_type"),
        })
    return rows


def run_shadow():
    from simulation.action_classifier import run_classifier_shadow_corpus
    return run_classifier_shadow_corpus()


def main():
    if "--shadow" in sys.argv:
        rows = run_shadow()
        if "--json" in sys.argv:
            print(json.dumps(rows, indent=2))
            return 0
        disagrees = sum(1 for r in rows if r.get("disagrees"))
        print(f"classifier shadow corpus: {len(rows)} cases, {disagrees} disagree with regex")
        for r in rows:
            flag = " DIFF" if r.get("disagrees") else ""
            diffs = r.get("diffs") or []
            detail = f" ({len(diffs)} diffs)" if diffs else ""
            print(f"  {r['action'][:40]:40} regex={r['regex_kind']:<12} clf={r['classifier_kind']:<12}{flag}{detail}")
        return 0

    rows = run_full_corpus()
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=2))
        return 0
    clarify = sum(1 for r in rows if r["clarify"])
    print(f"interpretation corpus: {len(rows)} actions, {clarify} clarify")
    for r in rows:
        flag = " CLARIFY" if r["clarify"] else ""
        print(f"  {r['tag']:18} kind={r['kind']:<12}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
