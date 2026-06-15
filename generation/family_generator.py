"""
Family trees. Post-processes a generated population into households that
share a surname and have real kin relations (spouses, parents, children,
siblings). Family bonds are seeded into the relationship graph at elevated
familiarity/affection so kin don't behave like strangers — with the
occasional sibling rivalry, because families are not simple.

Not everyone gets a family; solitary people are realistic too.
"""

import random
from generation.name_generator import generate_given_name, generate_surname, CULTURES


def _rewrite_surname(npc, surname):
    given = npc["name"].split(" ")[0]
    npc["name"] = f"{given} {surname}"
    npc["surname"] = surname


def _seed(rels, a, b, **dims):
    book = rels.setdefault(a, {})
    rel = book.setdefault(b, {})
    rel.setdefault("familiarity", 0.0)
    rel.setdefault("interactions", 0)
    rel["familiarity"] = max(rel["familiarity"], dims.pop("familiarity", 60))
    for k, v in dims.items():
        rel[k] = max(rel.get(k, 0.0), v)


def build_families(npcs, relationships=None):
    relationships = relationships if relationships is not None else {}
    ids = [i for i, n in npcs.items() if n.get("status") == "alive"]
    random.shuffle(ids)
    pool = list(ids)

    # how much of the population is embedded in families
    target_in_families = int(len(pool) * random.uniform(0.55, 0.75))
    placed = 0

    while pool and placed < target_in_families:
        culture = random.choice(CULTURES)
        surname = generate_surname(culture)

        # find two adults to be a couple
        adults = [i for i in pool if npcs[i]["age"] >= 24]
        if len(adults) < 1:
            break
        p1 = adults[0]
        couple = [p1]
        # optional spouse
        spouse_candidates = [i for i in adults[1:]
                             if abs(npcs[i]["age"] - npcs[p1]["age"]) <= 12]
        if spouse_candidates and random.random() < 0.7:
            couple.append(spouse_candidates[0])

        for cid in couple:
            pool.remove(cid)
            _rewrite_surname(npcs[cid], surname)
            npcs[cid]["culture"] = culture
            npcs[cid].setdefault("family", {"surname": surname, "relations": {}})

        if len(couple) == 2:
            a, b = couple
            npcs[a]["family"]["relations"][b] = "spouse"
            npcs[b]["family"]["relations"][a] = "spouse"
            _seed(relationships, a, b, familiarity=90, trust=55, affection=50, respect=40)
            _seed(relationships, b, a, familiarity=90, trust=55, affection=50, respect=40)

        # children: younger NPCs
        parent_age = min(npcs[c]["age"] for c in couple)
        kid_candidates = [i for i in pool if npcs[i]["age"] <= parent_age - 17]
        n_kids = min(len(kid_candidates), random.randint(0, 3))
        kids = kid_candidates[:n_kids]
        for kid in kids:
            pool.remove(kid)
            _rewrite_surname(npcs[kid], surname)
            npcs[kid]["culture"] = culture
            npcs[kid].setdefault("family", {"surname": surname, "relations": {}})
            for parent in couple:
                role = "father" if npcs[parent]["gender"] == "male" else "mother"
                npcs[kid]["family"]["relations"][parent] = role
                npcs[parent]["family"]["relations"][kid] = \
                    "son" if npcs[kid]["gender"] == "male" else "daughter"
                _seed(relationships, kid, parent, familiarity=85, trust=50, affection=45)
                _seed(relationships, parent, kid, familiarity=85, trust=50, affection=55, obligation=40)

        # siblings among the kids
        for i in range(len(kids)):
            for j in range(i + 1, len(kids)):
                k1, k2 = kids[i], kids[j]
                npcs[k1]["family"]["relations"][k2] = "sibling"
                npcs[k2]["family"]["relations"][k1] = "sibling"
                rivalry = random.random() < 0.35
                _seed(relationships, k1, k2, familiarity=80, trust=40, affection=35,
                      rivalry=45 if rivalry else 5)
                _seed(relationships, k2, k1, familiarity=80, trust=40, affection=35,
                      rivalry=45 if rivalry else 5)

        placed += len(couple) + len(kids)

    # anyone left keeps their own surname & a culture tag
    for i in pool:
        npcs[i].setdefault("culture", random.choice(CULTURES))
        npcs[i].setdefault("surname", npcs[i]["name"].split(" ")[-1]
                           if " " in npcs[i]["name"] else "")
        npcs[i].setdefault("family", {"surname": npcs[i].get("surname", ""), "relations": {}})

    return npcs, relationships
