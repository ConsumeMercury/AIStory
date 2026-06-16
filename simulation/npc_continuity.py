"""
Pin NPC appearance and voice across scenes so narration does not drift.
"""

from generation.descriptor_generator import appearance_notes
from simulation.narrator_variety import speech_hint


def build_narration_lock(npc):
    """Canonical appearance + voice strings for prompt reuse."""
    persona = npc.get("persona") or {}
    return {
        "appearance": appearance_notes(npc, "face"),
        "voice": speech_hint(persona, "default"),
    }


def get_narration_lock(player, npc_id):
    rec = (player.get("known_npcs") or {}).get(npc_id) or {}
    return rec.get("narration_lock")


def ensure_npc_continuity_locks(player, npcs):
    """Create narration locks for present NPCs missing one. Returns True if player changed."""
    changed = False
    for npc in npcs or []:
        nid = npc.get("id")
        if not nid:
            continue
        rec = player.setdefault("known_npcs", {}).setdefault(nid, {})
        if rec.get("narration_lock"):
            continue
        rec["narration_lock"] = build_narration_lock(npc)
        changed = True
    return changed
