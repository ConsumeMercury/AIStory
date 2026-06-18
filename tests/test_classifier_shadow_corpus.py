"""Classifier shadow corpus — offline constraint diff regression."""

from simulation.action_classifier import run_classifier_shadow_corpus, CLASSIFIER_SHADOW_CORPUS
from simulation.beat_structure import classify_beat_structure


def test_shadow_corpus_runs_without_api():
    rows = run_classifier_shadow_corpus()
    assert len(rows) == len(CLASSIFIER_SHADOW_CORPUS)
    assert all("action" in r for r in rows)


def test_woman_case_has_gender_constraint_diff_or_match():
    rows = run_classifier_shadow_corpus()
    woman = next(r for r in rows if "woman" in r["action"])
    assert woman["classifier_constraints"].get("gender") == "female"


def test_beat_structure_stalled_on_clarify():
    mode = classify_beat_structure(
        "talk",
        {"interpretation_clarify": True},
        {},
        [],
        "hq",
        None,
    )
    assert mode == "stalled"
