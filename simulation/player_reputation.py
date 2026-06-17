"""
Player reputation profile — derived archetype scores for NPC reaction bias.
"""

from storage import load

RUMOR_FILE = "rumors/rumors.json"


def build_reputation_profile(player):
    """
    Derive 0–100 trait scores from legacy, relationships, and rumor themes.
    """
    profile = {
        "violent": 15,
        "merciful": 40,
        "honorable": 50,
        "greedy": 20,
        "suspicious": 25,
        "heroic": 20,
    }

    for leg in player.get("legacy") or []:
        cat = (leg.get("category") or leg.get("kind") or "").lower()
        if cat == "violence":
            profile["violent"] = min(100, profile["violent"] + 18)
            profile["suspicious"] = min(100, profile["suspicious"] + 8)
        elif cat == "kindness":
            profile["merciful"] = min(100, profile["merciful"] + 20)
            profile["heroic"] = min(100, profile["heroic"] + 12)
        elif cat == "crime":
            profile["greedy"] = min(100, profile["greedy"] + 15)
            profile["suspicious"] = min(100, profile["suspicious"] + 14)
        elif cat == "heroism":
            profile["heroic"] = min(100, profile["heroic"] + 22)
            profile["honorable"] = min(100, profile["honorable"] + 10)

    rels = load("characters/relationships.json", {})
    toward = rels.get("toward_player") or {}
    if toward:
        avg_fear = sum(r.get("fear", 0) for r in toward.values()) / max(1, len(toward))
        avg_trust = sum(r.get("trust", 0) for r in toward.values()) / max(1, len(toward))
        profile["suspicious"] = min(100, profile["suspicious"] + int(avg_fear * 0.15))
        profile["honorable"] = min(100, profile["honorable"] + int(avg_trust * 0.12))

    rumors = load(RUMOR_FILE, [])
    for r in rumors[-20:]:
        interp = (r.get("interpretation") or "").lower()
        if interp in ("dangerous", "suspicious", "worrying"):
            profile["violent"] = min(100, profile["violent"] + 4)
            profile["suspicious"] = min(100, profile["suspicious"] + 5)
        elif interp == "heroic":
            profile["heroic"] = min(100, profile["heroic"] + 6)

    flags = player.get("story_flags") or {}
    if flags.get("murderer") or flags.get("wanted"):
        profile["violent"] = min(100, profile["violent"] + 25)
        profile["suspicious"] = min(100, profile["suspicious"] + 20)

    player["reputation_profile"] = profile
    return profile


def reputation_narrator_block(player):
    profile = player.get("reputation_profile") or build_reputation_profile(player)
    if not profile:
        return ""
    top = sorted(profile.items(), key=lambda kv: kv[1], reverse=True)[:3]
    bits = ", ".join(f"{k} {v}" for k, v in top if v >= 35)
    if not bits:
        return ""
    return (
        f"REPUTATION (locals may react accordingly — do not state scores aloud): {bits}."
    )
