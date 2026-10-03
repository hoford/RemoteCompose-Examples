#!/usr/bin/env python3
"""Generate and audit the visualization build schedule.

    python3 tools/visplan.py build      # (re)generate catalog/vis-schedule.json + state
    python3 tools/visplan.py audit      # prove the schedule is balanced
    python3 tools/visplan.py status     # where we are, and what the next set is
    python3 tools/visplan.py set N      # print set N as a work order

Three axes, from catalog/vis-taxonomy.md and the program document:

  WHAT   507 leaf nodes over 21 domains - the knowledge domain
  HOW    8 techniques, each bound to a distinct ENGINE SUBSYSTEM
  WHY    6 communication purposes

The HOW axis is deliberately not a list of visual styles. Each value names a part of the
engine, so "evenly distributed across HOW" is the same statement as "even pressure on every
subsystem" - which is what makes this exercise find bugs instead of producing 500 more static
diagrams of the kind the corpus already has 900 of.

The schedule is a PROPOSAL, not a contract. Some (WHAT, HOW) pairs are absurd - a particle
system for an income statement - and are meant to be swapped at build time. The rule is that
a swap preserves the set's HOW and WHY tallies, so balance survives curation.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAXONOMY = ROOT / "catalog" / "vis-taxonomy.md"
SCHEDULE = ROOT / "catalog" / "vis-schedule.json"
STATE = ROOT / "catalog" / "program-state.json"

SET_SIZE = 16

# Each HOW value names an engine subsystem, with the commands that define it. The commands
# are listed so a builder knows what the assignment actually obliges them to use, and so
# `audit` can later check whether built documents honoured it.
HOW = {
    "static-diagram":       ["paint", "drawRect", "drawCircle", "drawLine", "drawArc",
                             "drawOval", "drawRoundRect", "drawSector", "drawTextAnchored"],
    "annotated-layout":     ["box", "row", "column", "flow", "fitBox", "spacer", "text",
                             "collapsiblecolumn", "collapsiblerow"],
    "data-plot":            ["resources", "loop", "variable", "arrayGet", "arrayMax",
                             "arraySpline", "textFromFloat"],
    "path-form":            ["pathCreate", "pathAppendLineTo", "pathAppendClose", "drawPath",
                             "pathExpression", "clipRect"],
    "expression-animation": ["variable", "continuousSec", "anim", "rotate", "scale",
                             "translate", "save", "restore"],
    "particle-system":      ["createParticles", "particlesLoop", "particlescomparison",
                             "impulse", "impulseProcess"],
    "interactive":          ["touchExpression", "conditionalOperations", "impulse",
                             "collapsiblecolumn", "collapsiblerow"],
    "raster-and-text":      ["resources", "texture3D", "drawTextAnchored", "text",
                             "textFromFloat", "soundexpression"],
}
HOW_ORDER = list(HOW)

WHY = ["explain", "explore", "compare", "demonstrate", "simulate", "analyze"]

# 2D and 3D are a delivery constraint, not a style. A watch face will never run the 3D
# pipeline, and 3D costs more everywhere, so 2D carries the programme and 3D is spent where
# the extra dimension is the point. The corpus already has 16 documents exercising all 11
# 3D commands, so this is about keeping 2D strong rather than filling a 3D hole.
#
# THREE_D_IN is the denominator: one document in this many is 3D. Tunable - raise it to make
# the programme cheaper to run, lower it to push the mesh pipeline harder. It must stay
# COPRIME WITH 6 (the purpose count) for the reason given in assign_axes; 4 and 6 share a
# factor and cost a quarter of the joint space.
THREE_D_IN = 5

DIM_COMMANDS = {
    "2D": [],   # nothing from the 3D pipeline: runs on constrained devices
    "3D": ["defineMesh3D", "drawMesh3D", "meshPrimitive3D", "camera3D", "lights3D",
           "material3D", "matrix3D", "texture3D", "meshExpression3D", "clearDepth3D",
           "depthBias3D"],
}

# Short codes for document ids: PHY-PART-00023, as the taxonomy's own metadata block uses.
DOMAIN_CODE = {
    "Physics": "PHY", "Chemistry": "CHM", "Biology": "BIO", "Earth Science": "EAR",
    "Mathematics": "MTH", "Computer Science": "CSC", "Engineering": "ENG",
    "Medicine / Health Sciences": "MED", "Economics": "ECO", "Finance / Business": "FIN",
    "Social Sciences": "SOC", "History": "HIS", "Geography": "GEO",
    "Political Science / Civics": "POL", "Environmental Science": "ENV",
    "Technology": "TEC", "Transportation": "TRA",
    "Architecture / Built Environment": "ARC", "Agriculture / Food": "AGR",
    "Astronomy": "AST", "Education / Conceptual": "EDU",
}


def slug(s, n=4):
    """A short uppercase code for a subdomain, for the middle field of an id."""
    words = re.findall(r"[A-Za-z0-9]+", s)
    if len(words) == 1:
        return words[0][:n].upper()
    return "".join(w[0] for w in words)[:n].upper()


def parse_taxonomy():
    """-> [ (domain, subdomain, leaf) ].

    A subdomain with no leaves of its own IS a leaf: the taxonomy uses two depths in some
    domains and three in others, and both are addressable. Treating only three-deep entries
    as targets would silently drop 84 nodes - every one of Astronomy, Technology,
    Transportation and five other domains.
    """
    text = TAXONOMY.read_text()
    body = text.split("## Typical Meta data")[0]
    nodes, domain, sub = [], None, None
    pending_sub = None

    for line in body.split("\n"):
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("  - "):
            if pending_sub:
                pending_sub = None          # this subdomain has leaves; it is not itself one
            nodes.append((domain, sub, line[4:].strip()))
        elif line.startswith("- "):
            if pending_sub:
                nodes.append((domain, pending_sub, pending_sub))
            sub = line[2:].strip()
            pending_sub = sub
        else:
            if pending_sub:
                nodes.append((domain, pending_sub, pending_sub))
                pending_sub = None
            domain = line.strip()
            sub = None
    if pending_sub:
        nodes.append((domain, pending_sub, pending_sub))
    return nodes


def assign_axes(g):
    """(how, why, dimension) for the g-th document of the programme.

    Write g = 8q + r, so r indexes HOW and a set of 16 gets each subsystem exactly twice.

    WHY needs a multiplier on q that is COPRIME WITH 6, or q cannot walk it through every
    purpose. The obvious `(g + q) % 6` fails: g + q = 9q + r and 9 mod 6 = 3, so q shifts WHY
    by only 0 or 3 and each technique meets two purposes - 16 joint cells of 48. `(r + q)`
    puts a coefficient of 1 on q and fills all of them.

    DIMENSION reuses the same s = r + q, which sounds like the mistake above and is not,
    because 5 and 6 are coprime: by the Chinese remainder theorem s mod 30 determines the
    pair independently, so every (purpose, dimension) combination occurs. A "one in four"
    rule does NOT work here however it is phrased - gcd(4, 6) = 2 means the 3D documents of
    any one technique can only ever reach three of the six purposes, which measured 72 of 96
    joint cells. One in five measures 96 of 96, and costs less to run besides.
    """
    r = g % len(HOW_ORDER)
    q = g // len(HOW_ORDER)
    s = r + q
    how = HOW_ORDER[r]
    why = WHY[s % len(WHY)]
    dim = "3D" if s % THREE_D_IN == 0 else "2D"
    return how, why, dim


def allocate_domains(remaining, cap=4):
    """Pick 16 nodes' worth of domain slots for one set, proportional to work remaining.

    Largest-remainder over the remaining node counts, capped so no single domain dominates a
    set. Physics has 99 nodes against Political Science's 7; a flat rotation would exhaust the
    small domains in the first few sets and then spend twenty sets on Physics alone, so no
    individual set would be a spectrum probe any more.
    """
    total = sum(remaining.values())
    take = min(SET_SIZE, total)
    quota = {d: remaining[d] * take / total for d in remaining if remaining[d] > 0}
    alloc = {d: min(int(q), cap, remaining[d]) for d, q in quota.items()}

    # hand out what rounding left over, by largest fractional part
    while sum(alloc.values()) < take:
        best, best_frac = None, -1.0
        for d, q in quota.items():
            if alloc[d] >= min(cap, remaining[d]):
                continue
            frac = q - int(q)
            if frac > best_frac:
                best, best_frac = d, frac
        if best is None:                          # every domain at cap: relax it
            for d in sorted(quota, key=lambda x: -remaining[x]):
                if alloc[d] < remaining[d]:
                    alloc[d] += 1
                    break
            else:
                break
        else:
            alloc[best] += 1
    return {d: n for d, n in alloc.items() if n > 0}


def build():
    nodes = parse_taxonomy()
    by_domain = {}
    for d, s, leaf in nodes:
        by_domain.setdefault(d, []).append((s, leaf))

    remaining = {d: len(v) for d, v in by_domain.items()}
    cursor = {d: 0 for d in by_domain}
    seq = {d: 0 for d in by_domain}               # per-domain running id number

    sets, g = [], 0
    while sum(remaining.values()) > 0:
        alloc = allocate_domains(remaining)
        docs = []

        # `g` is the programme-wide document counter, carried across set boundaries so the
        # axis cycles stay even when a set is short (the final one) or when we pause.
        for d in sorted(alloc, key=lambda x: -remaining[x]):
            for _ in range(alloc[d]):
                sub, leaf = by_domain[d][cursor[d]]
                cursor[d] += 1
                remaining[d] -= 1
                seq[d] += 1
                how, why, dim = assign_axes(g)
                g += 1
                docs.append({
                    "id": "%s-%s-%05d" % (DOMAIN_CODE.get(d, slug(d, 3)), slug(sub), seq[d]),
                    "domain": d, "subdomain": sub, "topic": leaf,
                    "how": how, "why": why, "dimension": dim,
                    "subsystem_commands": HOW[how] + DIM_COMMANDS[dim],
                    "twin": None,
                })

        sets.append({
            "set": len(sets) + 1,
            "size": len(docs),
            "status": "planned",
            "documents": docs,
        })

    schedule = {
        "note": "Generated by tools/visplan.py. A proposal: swap any (topic, how) pair that "
                "does not make sense, keeping the set's how/why tallies intact.",
        "setSize": SET_SIZE,
        "how": HOW,
        "why": WHY,
        "dimension": DIM_COMMANDS,
        "threeDOneIn": THREE_D_IN,
        "totals": {
            "documents": sum(s["size"] for s in sets),
            "sets": len(sets),
            "domains": len(by_domain),
        },
        "sets": sets,
    }
    SCHEDULE.write_text(json.dumps(schedule, indent=1) + "\n")

    if not STATE.exists():
        STATE.write_text(json.dumps({
            "note": "The only source of truth for where the programme is. Read this first "
                    "after any pause.",
            "currentSet": 1,
            "setsLanded": 0,
            "documentsLanded": 0,
            "lastTouched": None,
            "pausedFor": None,
            "setStatus": {},
            "findings": [],
        }, indent=1) + "\n")

    print("  %s" % SCHEDULE.relative_to(ROOT))
    print("    %d documents, %d sets of %d, %d domains"
          % (schedule["totals"]["documents"], len(sets), SET_SIZE, len(by_domain)))
    return schedule


def audit():
    """Prove the balance claims rather than stating them."""
    sch = json.loads(SCHEDULE.read_text())
    docs = [d for s in sch["sets"] for d in s["documents"]]
    import collections
    how = collections.Counter(d["how"] for d in docs)
    why = collections.Counter(d["why"] for d in docs)
    dom = collections.Counter(d["domain"] for d in docs)
    pair = collections.Counter((d["how"], d["why"]) for d in docs)

    print("  documents: %d in %d sets" % (len(docs), len(sch["sets"])))
    print("  unique topics: %d  (duplicates: %d)"
          % (len({(d["domain"], d["subdomain"], d["topic"]) for d in docs}),
             len(docs) - len({(d["domain"], d["subdomain"], d["topic"]) for d in docs})))
    print()
    print("  HOW   min %d  max %d  spread %d" % (min(how.values()), max(how.values()),
                                                 max(how.values()) - min(how.values())))
    for k in HOW_ORDER:
        print("     %-22s %3d" % (k, how[k]))
    print("  WHY   min %d  max %d  spread %d" % (min(why.values()), max(why.values()),
                                                 max(why.values()) - min(why.values())))
    for k in WHY:
        print("     %-22s %3d" % (k, why[k]))
    print()
    print("  HOW x WHY cells filled: %d of %d   min %d  max %d"
          % (len(pair), len(HOW_ORDER) * len(WHY), min(pair.values()), max(pair.values())))
    dim = collections.Counter(d["dimension"] for d in docs)
    print("  dimension: 2D %d (%.0f%%)  3D %d (%.0f%%)"
          % (dim["2D"], 100 * dim["2D"] / len(docs), dim["3D"], 100 * dim["3D"] / len(docs)))
    wd = collections.Counter((d["why"], d["dimension"]) for d in docs)
    print("  WHY x DIM cells filled: %d of %d" % (len(wd), len(WHY) * 2))
    tri = collections.Counter((d["how"], d["why"], d["dimension"]) for d in docs)
    print("  HOW x WHY x DIM cells filled: %d of %d   min %d  max %d"
          % (len(tri), len(HOW_ORDER) * len(WHY) * 2,
             min(tri.values()), max(tri.values())))
    hd = collections.Counter((d["how"], d["dimension"]) for d in docs)
    print("  every technique has 2D and 3D instances: %s"
          % all((h, "2D") in hd and (h, "3D") in hd for h in HOW_ORDER))
    print("  domains covered: %d" % len(dom))

    # per-set spectrum: every set should touch every subsystem
    bad = [s["set"] for s in sch["sets"]
           if s["size"] == SET_SIZE and len({d["how"] for d in s["documents"]}) < len(HOW_ORDER)]
    print("  sets of %d that do NOT touch all %d subsystems: %s"
          % (SET_SIZE, len(HOW_ORDER), bad if bad else "none"))
    percap = [max(collections.Counter(d["domain"] for d in s["documents"]).values())
              for s in sch["sets"]]
    print("  most documents from one domain in any set: %d" % max(percap))
    spread = [len({d["why"] for d in s["documents"]}) for s in sch["sets"]]
    print("  purposes per set: min %d of %d  (a set should span most of them)"
          % (min(spread), len(WHY)))


def status():
    st = json.loads(STATE.read_text())
    sch = json.loads(SCHEDULE.read_text())
    n = st["currentSet"]
    print("  sets landed      : %d of %d" % (st["setsLanded"], len(sch["sets"])))
    print("  documents landed : %d of %d" % (st["documentsLanded"], sch["totals"]["documents"]))
    print("  current set      : %d" % n)
    if st.get("pausedFor"):
        print("  PAUSED FOR       : %s" % st["pausedFor"])
    if st.get("lastTouched"):
        print("  last touched     : %s" % st["lastTouched"])
    done = sum(1 for v in st.get("setStatus", {}).values() if v == "landed")
    print("  findings logged  : %d" % len(st.get("findings", [])))
    if n <= len(sch["sets"]):
        print()
        print("  next set %d:" % n)
        docs = sch["sets"][n - 1]["documents"]
        n3d = sum(1 for d in docs if d["dimension"] == "3D")
        print("    %d documents, %d of them 3D" % (len(docs), n3d))
        for d in docs:
            print("    %-18s %-24s %-21s %-12s %s"
                  % (d["id"], d["topic"][:24], d["how"], d["why"], d["dimension"]))


def show_set(n):
    sch = json.loads(SCHEDULE.read_text())
    if not (1 <= n <= len(sch["sets"])):
        sys.exit("  no set %d (1..%d)" % (n, len(sch["sets"])))
    s = sch["sets"][n - 1]
    print("  SET %d  —  %d documents  —  status: %s" % (s["set"], s["size"], s["status"]))
    print()
    for d in s["documents"]:
        print("  %s" % d["id"])
        print("     %s / %s / %s" % (d["domain"], d["subdomain"], d["topic"]))
        print("     how: %-22s why: %-12s dimension: %s"
              % (d["how"], d["why"], d["dimension"]))
        print("     must use: %s" % ", ".join(d["subsystem_commands"][:6]))
        print()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "build":
        build(); print(); audit()
    elif cmd == "audit":
        audit()
    elif cmd == "status":
        status()
    elif cmd == "set":
        show_set(int(sys.argv[2]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
