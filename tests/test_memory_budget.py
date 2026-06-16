"""Memory budget trimming."""

from simulation.memory_budget import apply_memory_budget, estimate_tokens, format_memory_debug


def test_estimate_tokens():
    assert estimate_tokens("abcd") >= 1
    assert estimate_tokens("") == 0


def test_apply_memory_budget_trims_low_priority_first(monkeypatch):
    monkeypatch.delenv("AISTORY_SKIP_MEMORY_BUDGET", raising=False)
    sections = {
        "plot_summary": "PLOT " + ("x" * 2000),
        "recent_journal": "RECENT " + ("y" * 4000),
        "distant_history": "DISTANT " + ("z" * 2000),
        "retrieved_events": "EVENTS " + ("w" * 2000),
    }
    trimmed, evictions = apply_memory_budget(sections, total_cap=400)
    assert estimate_tokens(trimmed.get("plot_summary", "")) <= 400 or trimmed.get("plot_summary", "") == ""
    assert evictions


def test_format_memory_debug():
    debug = format_memory_debug({"plot_summary": "hello"}, ["plot_summary: trimmed"])
    assert debug["tokens_used"]["plot_summary"] >= 1
    assert debug["evictions"]
