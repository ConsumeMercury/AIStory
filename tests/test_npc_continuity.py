from simulation.npc_continuity import build_narration_lock, ensure_npc_continuity_locks, get_narration_lock


def _npc(nid="p1"):
    return {
        "id": nid,
        "name": "Father Hale",
        "role": "priest",
        "gender": "male",
        "age": 45,
        "physique": {
            "build": "lean",
            "height": "tall",
            "hair": "grey",
            "eyes": "pale",
            "distinguishing_mark": "a scar",
            "voice": "low gravel",
        },
        "persona": {"speech_style": "measured", "voice_quirk": "pauses before names"},
    }


def test_build_narration_lock_includes_appearance_and_voice():
    lock = build_narration_lock(_npc())
    assert lock["appearance"]
    assert lock["voice"]


def test_ensure_npc_continuity_locks_persists_on_player():
    player = {"known_npcs": {}}
    npc = _npc()
    changed = ensure_npc_continuity_locks(player, [npc])
    assert changed is True
    lock = get_narration_lock(player, "p1")
    assert lock["appearance"]
    assert ensure_npc_continuity_locks(player, [npc]) is False
