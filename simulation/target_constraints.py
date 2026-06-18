"""
Constraint-based target resolution.

If the player names any identifying constraint, the resolved target MUST satisfy it.
If nothing satisfies it → absent or clarify — never substitute a violating NPC.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

# Role keywords → acceptable npc.role values
ROLE_ALIASES = {
    "priest": frozenset({"priest"}),
    "cleric": frozenset({"priest"}),
    "monk": frozenset({"priest"}),
    "guard": frozenset({"guard", "soldier"}),
    "soldier": frozenset({"guard", "soldier"}),
    "merchant": frozenset({"merchant", "innkeeper"}),
    "trader": frozenset({"merchant", "innkeeper"}),
    "sailor": frozenset({"sailor", "merchant", "guard"}),
    "captain": frozenset({"sailor", "merchant", "guard"}),
    "scholar": frozenset({"scholar", "scribe"}),
    "scribe": frozenset({"scribe", "scholar"}),
    "blacksmith": frozenset({"blacksmith"}),
    "smith": frozenset({"blacksmith"}),
    "hunter": frozenset({"hunter"}),
    "innkeeper": frozenset({"innkeeper", "merchant"}),
    "beggar": frozenset({"beggar"}),
    "mercenary": frozenset({"mercenary", "soldier", "guard"}),
}

ROLE_PATTERNS = [
    (re.compile(r"\b(priest|cleric|monk|chaplain)\b", re.I), "priest"),
    (re.compile(r"\b(guard|watchman|soldier|levy|mercenary)\b", re.I), "guard"),
    (re.compile(r"\b(merchant|trader|stall(?:holder)?|innkeeper)\b", re.I), "merchant"),
    (re.compile(r"\b(sailor|dockhand|crewman|captain)\b", re.I), "sailor"),
    (re.compile(r"\b(blacksmith|smith|forge(?:hand)?)\b", re.I), "blacksmith"),
    (re.compile(r"\b(scholar|academic|scribe)\b", re.I), "scholar"),
    (re.compile(r"\b(hunter|hunters)\b", re.I), "hunter"),
    (re.compile(r"\b(beggar)\b", re.I), "beggar"),
]

FEMALE_WORDS = re.compile(r"\b(woman|girl|lady)\b", re.I)
FEMALE_PRON = re.compile(r"\b(she|her)\b", re.I)
MALE_WORDS = re.compile(r"\b(man|boy|fellow|bloke|sir)\b", re.I)
MALE_PRON = re.compile(r"\b(he|him|his)\b", re.I)

GROUP_PATTERNS = re.compile(
    r"\b(guards|soldiers|knights|merchants|priests|sailors|scholars)\b", re.I,
)

STRICT_KINDS = frozenset({"attack", "steal", "give"})


class TargetStatus(str, Enum):
    MATCHED = "matched"
    ABSENT = "absent"
    AMBIGUOUS = "ambiguous"


@dataclass
class TargetConstraints:
    name_query: str | None = None
    role: str | None = None
    gender: str | None = None
    physical: list[str] = field(default_factory=list)
    pronoun: str | None = None
    relational: str | None = None
    group: bool = False
    conflicting: bool = False

    def is_empty(self) -> bool:
        return not any([
            self.name_query,
            self.role,
            self.gender,
            self.physical,
            self.pronoun,
            self.relational,
            self.group,
            self.conflicting,
        ])

    def primary_violation(self) -> str | None:
        if self.conflicting:
            return "conflicting constraints"
        if self.name_query:
            return f"name:{self.name_query}"
        if self.role:
            return f"role:{self.role}"
        if self.gender:
            return f"gender:{self.gender}"
        if self.physical:
            return f"trait:{self.physical[0]}"
        if self.pronoun:
            return f"pronoun:{self.pronoun}"
        if self.relational:
            return f"relational:{self.relational}"
        return None

    def describe_unmet(self) -> str:
        if self.conflicting:
            return "contradictory description — clarify who you mean"
        if self.gender == "female":
            return "no woman here"
        if self.gender == "male":
            return "no man here"
        if self.role:
            return f"no {self.role} here"
        if self.physical:
            return f"no one here matches {self.physical[0]}"
        if self.name_query:
            return f"no one matching {self.name_query!r} is here"
        return "no one here matches that description"


@dataclass
class ResolvedTarget:
    status: TargetStatus
    npc: dict | None = None
    npc_id: str | None = None
    reason: str = ""
    candidates: list[dict] = field(default_factory=list)
    constraint_violated: str | None = None
    mislabel: bool = False

    @property
    def matched(self) -> bool:
        return self.status == TargetStatus.MATCHED


def _hair_match(npc, colors):
    hair = (npc.get("appearance") or {}).get("hair", "").lower()
    return any(c in hair for c in colors)


TRAIT_CHECKS = {
    "red_hair": (
        re.compile(r"\bred[\s-]?hair(?:ed)?|\bauburn\b", re.I),
        lambda n: _hair_match(n, ("red", "auburn", "copper")),
    ),
    "grey_hair": (
        re.compile(r"\b(grey|gray)[\s-]?hair|\bsilver[\s-]?hair\b", re.I),
        lambda n: _hair_match(n, ("grey", "gray", "silver", "white")),
    ),
}


def extract_constraints(action, player, present, npcs):
    """Parse binding signals from player text into a constraint set."""
    text = (action or "").strip()
    lower = text.lower()
    c = TargetConstraints()

    female_word = bool(FEMALE_WORDS.search(lower))
    female_pron = bool(FEMALE_PRON.search(lower))
    male_word = bool(MALE_WORDS.search(lower))
    male_pron = bool(MALE_PRON.search(lower))

    if female_word or female_pron:
        c.gender = "female"
    if male_word or (male_pron and not female_word):
        if c.gender == "female" and (male_word or male_pron):
            c.conflicting = True
        elif not c.gender:
            c.gender = "male"

    if female_pron and not female_word:
        c.pronoun = "female"
    elif male_pron and not male_word and c.gender != "female":
        c.pronoun = "male"

    for pattern, role_key in ROLE_PATTERNS:
        if pattern.search(lower):
            c.role = role_key
            break

    if GROUP_PATTERNS.search(lower):
        c.group = True

    for trait_key, (pattern, _matcher) in TRAIT_CHECKS.items():
        if pattern.search(lower):
            c.physical.append(trait_key)

    build_hint = re.search(
        r"\b(tall|wiry|barrel-chested|stocky|slight|lean|broad|hunched|limping|one-eyed|scarred)\b",
        lower,
    )
    if build_hint:
        c.physical.append(build_hint.group(1).lower())

    if re.search(r"\bthe other one\b|\bthe other\b", lower):
        c.relational = "other"
    if re.search(r"\b(one i (?:just )?spoke to|one we spoke to|same one|the one from before)\b", lower):
        c.relational = "prior_conversation"

    m = re.search(
        r"\b(?:talk|speak)\s+(?:to|with)\s+(?:the\s+)?([a-z][a-z'-]{2,28})\b",
        lower,
    )
    if m and m.group(1) not in {
        "priest", "merchant", "guard", "soldier", "woman", "man", "girl", "boy", "lady", "him", "her",
    }:
        c.name_query = m.group(1)

    return c


def _role_matches(npc, role_key):
    roles = ROLE_ALIASES.get(role_key, frozenset({role_key}))
    npc_role = (npc.get("role") or "").lower()
    if npc_role in roles:
        return True
    occ = (npc.get("occupation") or "").lower()
    return occ in roles


def _npc_satisfies_trait(npc, trait_key):
    if trait_key in TRAIT_CHECKS:
        _, matcher = TRAIT_CHECKS[trait_key]
        try:
            return bool(matcher(npc))
        except Exception:
            return False
    build = (npc.get("physique") or {}).get("build", "").lower()
    if build and build == trait_key:
        return True
    app = " ".join(str(v).lower() for v in (npc.get("appearance") or {}).values())
    return trait_key in app


def filter_by_constraints(candidates, constraints, player, present):
    """Progressive filter — tie-breakers only run on survivors."""
    if constraints.conflicting:
        return [], "conflicting constraints"

    pool = list(candidates)

    if constraints.role:
        pool = [n for n in pool if _role_matches(n, constraints.role)]

    if constraints.gender:
        pool = [n for n in pool if n.get("gender") == constraints.gender]

    for trait in constraints.physical:
        if trait in TRAIT_CHECKS:
            pool = [n for n in pool if _npc_satisfies_trait(n, trait)]
            continue
        with_build = [n for n in pool if (n.get("physique") or {}).get("build")]
        matching = [n for n in pool if _npc_satisfies_trait(n, trait)]
        if matching:
            pool = matching
        elif with_build and len(with_build) == len(pool):
            pool = []
        # else: unspecified physique on some/all — keep pool for clarify

    if constraints.relational == "other":
        focus = player.get("scene_focus")
        if focus:
            pool = [n for n in pool if n["id"] != focus]

    if constraints.relational == "prior_conversation":
        partner = _prior_conversation_partner(player, present)
        if partner:
            pool = [n for n in pool if n["id"] == partner]
        else:
            return [], "prior conversation partner not here"

    if constraints.pronoun and not constraints.gender:
        pool = [n for n in pool if n.get("gender") == constraints.pronoun]

    return pool, None


def _prior_conversation_partner(player, present):
    present_ids = {n["id"] for n in present}
    area = player.get("area")
    journal = player.get("journal") or []
    for entry in reversed(journal):
        if entry.get("area") != area:
            continue
        fid = entry.get("focus_npc")
        if fid and fid in present_ids:
            return fid
    focus = player.get("scene_focus")
    if focus and focus in present_ids:
        return focus
    return None


def _tiebreak(candidates, player, kind):
    """Pick one survivor — never reaches NPCs that failed constraints."""
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    ids = {n["id"] for n in candidates}
    focus = player.get("scene_focus")
    if focus and focus in ids:
        return next(n for n in candidates if n["id"] == focus)

    journal = player.get("journal") or []
    if journal:
        last_focus = journal[-1].get("focus_npc")
        if last_focus and last_focus in ids:
            return next(n for n in candidates if n["id"] == last_focus)

    if kind == "attack":
        last = player.get("last_combat_target")
        if last and last in ids:
            return next(n for n in candidates if n["id"] == last)

    keyed = [n for n in candidates if n.get("key_npc")]
    if len(keyed) == 1:
        return keyed[0]

    return None


def _resolve_unconstrained(player, present, kind):
    """Safe fallbacks — only when the player gave no binding constraint."""
    if not present:
        return ResolvedTarget(TargetStatus.ABSENT, reason="no one here")

    if len(present) == 1:
        if kind in STRICT_KINDS:
            return ResolvedTarget(
                TargetStatus.MATCHED,
                npc=present[0],
                npc_id=present[0]["id"],
            )
        return ResolvedTarget(
            TargetStatus.MATCHED,
            npc=present[0],
            npc_id=present[0]["id"],
        )

    focus_id = player.get("scene_focus")
    if focus_id:
        for n in present:
            if n["id"] == focus_id:
                return ResolvedTarget(TargetStatus.MATCHED, npc=n, npc_id=n["id"])

    known = player.get("known_npcs") or {}
    known_present = [n for n in present if known.get(n["id"], {}).get("name_known")]
    if len(known_present) == 1:
        n = known_present[0]
        return ResolvedTarget(TargetStatus.MATCHED, npc=n, npc_id=n["id"])

    if kind in STRICT_KINDS:
        return ResolvedTarget(
            TargetStatus.AMBIGUOUS,
            candidates=list(present),
            reason="several people are here — name who you mean",
        )

    return ResolvedTarget(
        TargetStatus.AMBIGUOUS,
        candidates=list(present),
        reason="several people are here — who do you mean",
    )


def resolve_target(action, player, present, npcs=None, kind="general"):
    """
    Resolve who the player is targeting among present NPCs.

    Returns ResolvedTarget with explicit status — never a silent wrong pick.
    """
    from simulation.target_resolution import find_npc_by_name_in_text

    if not present:
        return ResolvedTarget(TargetStatus.ABSENT, reason="no one here")

    npcs = npcs or {}
    constraints = extract_constraints(action, player, present, npcs)

    if npcs:
        named = find_npc_by_name_in_text(action, npcs, player)
        if named:
            for n in present:
                if n["id"] == named["id"]:
                    return ResolvedTarget(
                        TargetStatus.MATCHED,
                        npc=n,
                        npc_id=n["id"],
                        reason="named target present",
                    )
            return ResolvedTarget(
                TargetStatus.ABSENT,
                reason=f"{named.get('name', 'they')} is not here",
                constraint_violated=f"name:{named.get('name')}",
            )

    if constraints.is_empty():
        return _resolve_unconstrained(player, present, kind)

    pool, filter_err = filter_by_constraints(list(present), constraints, player, present)
    if filter_err == "conflicting constraints":
        return ResolvedTarget(
            TargetStatus.AMBIGUOUS,
            candidates=list(present),
            reason=filter_err,
            constraint_violated=constraints.primary_violation(),
        )

    if len(pool) == 0:
        if (
            len(present) == 1
            and kind not in STRICT_KINDS
            and constraints.gender
            and not constraints.role
        ):
            sole = present[0]
            return ResolvedTarget(
                TargetStatus.MATCHED,
                npc=sole,
                npc_id=sole["id"],
                reason=f"mislabel: only one person present; player said {constraints.gender!r}",
                constraint_violated=constraints.primary_violation(),
                mislabel=True,
            )
        return ResolvedTarget(
            TargetStatus.ABSENT,
            reason=constraints.describe_unmet(),
            constraint_violated=constraints.primary_violation(),
        )

    if len(pool) == 1:
        n = pool[0]
        return ResolvedTarget(TargetStatus.MATCHED, npc=n, npc_id=n["id"])

    if constraints.group:
        return ResolvedTarget(
            TargetStatus.AMBIGUOUS,
            candidates=pool,
            reason=f"several {constraints.role or 'people'} here",
        )

    picked = _tiebreak(pool, player, kind)
    if picked:
        return ResolvedTarget(
            TargetStatus.MATCHED,
            npc=picked,
            npc_id=picked["id"],
            reason="tie-break among constraint matches",
        )

    return ResolvedTarget(
        TargetStatus.AMBIGUOUS,
        candidates=pool,
        reason=constraints.describe_unmet() if len(pool) > 1 else "target unclear",
    )


def npc_satisfies_constraints(action, npc, player=None, present=None):
    """True when npc satisfies every verifiable constraint in the action."""
    if not npc:
        return False
    present = present or [npc]
    player = player or {}
    constraints = extract_constraints(action, player, present, {})
    if constraints.is_empty():
        return True
    pool, err = filter_by_constraints([npc], constraints, player, present)
    if err == "conflicting constraints":
        return False
    return len(pool) == 1 and pool[0]["id"] == npc.get("id")


def target_resolution_trace(action, player, present, npcs=None, kind="general"):
    """Debug payload for boundary trace."""
    result = resolve_target(action, player, present, npcs=npcs, kind=kind)
    constraints = extract_constraints(action, player, present, npcs or {})
    return {
        "status": result.status.value,
        "npc_id": result.npc_id,
        "reason": result.reason,
        "constraint_violated": result.constraint_violated,
        "candidate_ids": [n["id"] for n in result.candidates],
        "constraints_empty": constraints.is_empty(),
        "constraints": {
            "role": constraints.role,
            "gender": constraints.gender,
            "physical": constraints.physical,
            "pronoun": constraints.pronoun,
            "relational": constraints.relational,
            "group": constraints.group,
            "conflicting": constraints.conflicting,
        },
    }
