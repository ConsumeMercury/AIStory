"""
Consequence cascades — mechanical fallout from high-impact beats.

Links player violence and causal pressure to district economy and delayed hooks.
"""

import random

from simulation.economy_engine import VENDOR_ROLES
from simulation.consequence_queue import queue_consequence

_AUTHORITY_ROLES = frozenset({"guard", "soldier", "captain"})


def register_combat_consequences(player, target_npc, *, world, areas, fatal=False, tick=None):
    """
    Propagate immediate + delayed consequences when the player fatally kills an NPC.
    """
    if not fatal or not target_npc:
        return False
    if target_npc.get("status") != "dead":
        return False

    changed = False
    area_id = player.get("area")
    role = (target_npc.get("role") or "").lower()
    name = target_npc.get("name") or "someone"
    day = (world or {}).get("day", 1)

    if area_id and areas:
        from simulation.economy_pressure import ripple_from_district_shock

        prosperity_delta = -10 if role in VENDOR_ROLES else -4
        ripple_from_district_shock(
            area_id, areas,
            prosperity_delta=prosperity_delta,
            crime_delta=5,
        )
        changed = True

    if role in VENDOR_ROLES:
        queue_consequence(
            player,
            fires_at_day=day + random.randint(1, 3),
            kind="trade_disruption",
            summary=f"Trade falters after {name} died.",
            effects={
                "narrator_directive": (
                    "The market feels wrong — shuttered stalls, wary eyes, "
                    "prices creeping up. Do not invent a full economic simulation."
                ),
                "story_flag": f"trade_shock_{area_id or 'local'}",
            },
            target_id=target_npc.get("id"),
        )
        changed = True
    elif role in _AUTHORITY_ROLES:
        queue_consequence(
            player,
            fires_at_day=day + random.randint(1, 4),
            kind="authority_backlash",
            summary=f"The garrison noticed what happened to {name}.",
            effects={
                "narrator_directive": (
                    "Guards are sharper, colder — less patience for strangers."
                ),
                "faction_standing_delta": -6,
            },
            target_id=target_npc.get("id"),
        )
        changed = True
    else:
        queue_consequence(
            player,
            fires_at_day=day + random.randint(2, 5),
            kind="violence_aftermath",
            summary=f"Word spreads about violence involving {name}.",
            effects={
                "narrator_directive": (
                    "People speak in lowered voices; strangers are watched."
                ),
            },
            target_id=target_npc.get("id"),
        )
        changed = True

    return changed


def register_from_causal_link(player, link, *, world, areas=None):
    """Enqueue delayed fallout when a high-importance causal link forms."""
    if not link:
        return False
    imp = int(link.get("importance") or 0)
    if imp < 65:
        return False

    cause = (link.get("cause") or "").lower()
    day = (world or {}).get("day", 1)
    summary = (link.get("summary") or "")[:120]

    if cause in ("violence", "accusation", "blackmail", "theft"):
        queue_consequence(
            player,
            fires_at_day=day + random.randint(2, 6),
            kind="causal_ripple",
            summary=summary or "Something you did is still moving through the district.",
            effects={
                "narrator_directive": (
                    "A prior reckoning still haunts this beat — "
                    "show social residue, not a new plot dump."
                ),
            },
        )
        return True
    return False
