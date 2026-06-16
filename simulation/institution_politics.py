"""
Internal institution politics — members disagree; player navigates factions within orgs.
"""

import random

STANCE_AGENDAS = {
    "hardline": ("push for crackdown and examples", "fight", "plan"),
    "reform": ("seek compromise and transparency", "help", "study"),
    "pragmatic": ("protect the institution's coin and reputation", "trade", "plan"),
    "secretive": ("keep scandal buried at any cost", "hide", "plan"),
    "pious": ("answer to faith before politics", "help", "study"),
    "ambitious": ("climb by any alliance", "socialise", "plan"),
}


def attach_politics(institutions, npcs):
    """Seed internal factions for each institution."""
    for inst in institutions.values():
        if inst.get("politics"):
            continue
        members = list((inst.get("members") or {}).keys())
        if len(members) < 2:
            continue
        stances = random.sample(list(STANCE_AGENDAS.keys()), k=min(3, len(members)))
        inst["politics"] = []
        for i, mid in enumerate(members[:4]):
            stance = stances[i % len(stances)]
            agenda, *acts = STANCE_AGENDAS[stance]
            npcs.get(mid, {})["institution_stance"] = stance
            inst["politics"].append({
                "member_id": mid,
                "stance": stance,
                "agenda": agenda,
                "preferred_actions": list(acts),
            })
        if inst.get("leader") and len(inst["politics"]) >= 2:
            inst["politics"][0]["stance"] = random.choice(["hardline", "ambitious"])
    return institutions


def politics_action_bias(npc, institution):
    """Bias NPC action toward their internal stance."""
    if not institution:
        return {}
    stance = npc.get("institution_stance")
    if not stance:
        for p in institution.get("politics") or []:
            if p.get("member_id") == npc.get("id"):
                stance = p.get("stance")
                break
    if not stance or stance not in STANCE_AGENDAS:
        return {}
    _, a, b = STANCE_AGENDAS[stance]
    return {a: 1.35, b: 1.2}


def politics_narrator_block(area_id, institutions, npcs):
    """Lines about schisms in institutions in this district."""
    lines = []
    for inst in institutions.values():
        if inst.get("area") != area_id:
            continue
        pol = inst.get("politics") or []
        if len(pol) < 2:
            continue
        a, b = pol[0], pol[1]
        na = npcs.get(a["member_id"], {}).get("name", "one faction")
        nb = npcs.get(b["member_id"], {}).get("name", "another")
        lines.append(
            f"At {inst.get('name', 'the institution')}, {na} ({a['stance']}) "
            f"and {nb} ({b['stance']}) pull against each other — {a['agenda']} vs {b['agenda']}."
        )
    if not lines:
        return ""
    return "INSTitution POLITICS:\n" + "\n".join(f"- {l}" for l in lines[:2])
