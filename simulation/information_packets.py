"""
Information packets — news travels physically between areas and cities.
"""

import random
import uuid

from storage import load, save

WORLD_FILE = "world/world_state.json"
AREAS_FILE = "world/areas.json"
MAX_PACKETS = 60


def _packets(world):
    return world.setdefault("information_packets", [])


def emit_information(world, *, origin_area, origin_city, text, credibility=0.7, speed=1, tick=0, interpretation=None):
    if not text:
        return None
    packet = {
        "id": str(uuid.uuid4())[:10],
        "text": text[:200],
        "origin_area": origin_area,
        "origin_city": origin_city,
        "credibility": max(0.1, min(1.0, float(credibility))),
        "speed": max(1, int(speed)),
        "tick": tick,
        "hops": 0,
        "max_hops": random.randint(2, 5),
        "known_areas": [origin_area] if origin_area else [],
        "known_cities": [origin_city] if origin_city else [],
        "interpretation": interpretation,
        "distortion": 0.0,
    }
    store = _packets(world)
    store.append(packet)
    world["information_packets"] = store[-MAX_PACKETS:]
    return packet


def _neighbor_areas(area_id, areas):
    if not area_id:
        return []
    area = areas.get(area_id, {})
    city = area.get("city") or (area_id.split(":")[0] if ":" in area_id else None)
    neighbors = []
    for aid, a in areas.items():
        if aid == area_id:
            continue
        if a.get("city") == city or a.get("location") == area.get("location"):
            neighbors.append(aid)
    return neighbors[:4]


def advance_information_packets(world, player=None, *, tick=0, areas=None):
    """Move packets one hop per tick; distort text slightly each hop."""
    areas = areas if areas is not None else load(AREAS_FILE, {})
    store = _packets(world)
    if not store:
        return []

    arrived = []
    remaining = []
    for packet in store:
        if packet.get("hops", 0) >= packet.get("max_hops", 3):
            continue
        origin_areas = packet.get("known_areas") or []
        frontier = origin_areas[-1] if origin_areas else packet.get("origin_area")
        neighbors = _neighbor_areas(frontier, areas)
        if not neighbors:
            remaining.append(packet)
            continue
        if random.random() > 0.45:
            remaining.append(packet)
            continue
        dest = random.choice(neighbors)
        packet["hops"] = packet.get("hops", 0) + 1
        packet.setdefault("known_areas", []).append(dest)
        packet["distortion"] = min(0.5, packet.get("distortion", 0) + 0.08)
        packet["credibility"] = max(0.15, packet.get("credibility", 0.7) - 0.06)
        arrived.append({"packet": packet, "area_id": dest})
        remaining.append(packet)

    world["information_packets"] = remaining[-MAX_PACKETS:]
    return arrived


def packets_for_area(world, area_id, city=None, *, limit=5):
    out = []
    for p in _packets(world):
        if area_id and area_id in (p.get("known_areas") or []):
            out.append(p)
        elif city and city in (p.get("known_cities") or []):
            out.append(p)
        if len(out) >= limit:
            break
    return out


def emit_from_player_beat(world, player, kind, action_ctx, *, tick=0):
    """High-importance beats spawn information that spreads slowly."""
    if kind not in ("attack", "accuse", "confess", "blackmail", "help"):
        return None
    ctx = action_ctx or {}
    check = ctx.get("skill_check") or {}
    if kind in ("help",) and not check.get("success", True):
        return None
    templates = {
        "attack": "Word of a fight involving the outsider spreads.",
        "accuse": "Someone heard a public accusation involving the outsider.",
        "confess": "A confession involving the outsider is whispered about.",
        "blackmail": "Leverage and threats involving the outsider are rumored.",
        "help": "Someone says the outsider showed unexpected kindness.",
    }
    text = templates.get(kind, "Something about the outsider is being discussed.")
    return emit_information(
        world,
        origin_area=player.get("area"),
        origin_city=player.get("location"),
        text=text,
        credibility=0.65 if kind == "help" else 0.55,
        speed=1,
        tick=tick,
        interpretation="dangerous" if kind in ("attack", "accuse", "blackmail") else "heroic",
    )


def persist_packets(world):
    save(WORLD_FILE, world)
