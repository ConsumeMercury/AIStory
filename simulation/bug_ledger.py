"""
Bug shape taxonomy — tag issues A/B/C/D for instrumentation and postmortems.

A — Narrator asserts state sim doesn't own (phantom facts)
B — Regex/prose scraping misses phrasing (interpretation boundary)
C — Directive-and-hope (model didn't obey inline instruction)
D — State recomputed per beat instead of persisted (coherence)
"""

from enum import Enum


class BugShape(str, Enum):
    PHANTOM_STATE = "A"       # narrator/fabrication
    SCRAPE_MISS = "B"         # regex / prose reverse-engineering
    DIRECTIVE_HOPE = "C"      # instruction not obeyed
    STATE_RECOMPUTE = "D"     # cast/place/focus instability


SHAPE_DESCRIPTIONS = {
    BugShape.PHANTOM_STATE: "Narrator asserted state the simulation does not own",
    BugShape.SCRAPE_MISS: "Code regex-scanned prose/ input and missed phrasing",
    BugShape.DIRECTIVE_HOPE: "Fix relied on model obeying a prose directive",
    BugShape.STATE_RECOMPUTE: "State that should persist was recomputed each beat",
}

OVERHAUL_FOR_SHAPE = {
    BugShape.PHANTOM_STATE: "Overhaul 2 (structured fact emission) + Overhaul 4 (validate-and-act)",
    BugShape.SCRAPE_MISS: "Overhaul 1 (structured action classifier)",
    BugShape.DIRECTIVE_HOPE: "Overhaul 2 + Overhaul 4",
    BugShape.STATE_RECOMPUTE: "Overhaul 3 (SceneState)",
}


def tag_bug(shape, summary, *, overhaul=None):
    """Return a structured bug record for logging or tests."""
    return {
        "shape": shape.value if isinstance(shape, BugShape) else str(shape),
        "summary": summary,
        "overhaul": overhaul or OVERHAUL_FOR_SHAPE.get(shape, ""),
    }
