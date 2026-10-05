#!/usr/bin/env python3
"""Write descriptions with hashtags into entry.json for the visualization sets.

    python3 tools/vistags.py 9 10 11 12          # fill sets 9-12
    python3 tools/vistags.py --dry-run 9         # show what it would write

Hashtags live inside the description text, not in a separate field - see the "Descriptions
and hashtags" section of rcx.py. `rcx catalog` lifts them into the `tag` facet, so a
document with no description has no tags and is invisible to every tag filter on the site.
That was true of all 193 documents in vis-set-01..12: sets 1-4 had hashtags, sets 5-12 had
no description at all.

Nothing here is invented. Every part is read from something the document or the schedule
already asserts:

  the sentence   the document's own `contentDescription`, written by its generator
  domain tag     the schedule's `domain`, through DOMAIN_TAG below
  topic tag      the schedule's `topic`, through TOPIC_TAG, and only when it has an entry
  #3d            the document actually contains 3D opcodes
  #touch         the document actually contains touchExpression or an onClick modifier
  #animated      the document actually reads a clock
  #particles     the document actually creates a particle system
  #interactive   the schedule's `how` is "interactive"

An unrecognised domain or topic contributes no tag rather than a guessed one. A wrong tag is
worse than a missing one, because it makes the filter quietly lie - the same reasoning
rcx.py gives for keeping COLLECTION_TAGS a small explicit table.

Only ever fills a blank description. Re-running is idempotent and hand edits survive.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
WORK = ROOT / "work"

DOMAIN_TAG = {
    "Physics": "physics",
    "Biology": "biology",
    "Chemistry": "chemistry",
    "Mathematics": "maths",
    "Computer Science": "computing",
    "Earth Science": "earth",
    "Engineering": "engineering",
    "Finance / Business": "finance",
    "Economics": "economics",
    "Medicine / Health Sciences": "medicine",
    "Social Sciences": "society",
    "Geography": "geography",
    "History": "history",
}

# Only topics whose short form is worth a facet of its own. Anything absent contributes
# nothing; the domain tag still applies.
TOPIC_TAG = {
    "Graphs": "graphs", "Hash tables": "algorithms", "CPU": "computing",
    "Forces": "forces", "Pendulums": "mechanics",
    "Collisions": "mechanics", "Energy": "mechanics", "Rotational mechanics": "mechanics",
    "Momentum": "mechanics", "Motion": "mechanics",
    "Microbiomes": "cells", "Viruses": "cells", "Bacteria": "cells", "Fungi": "cells",
    "Protozoa": "cells", "Anatomy": "anatomy",
    "Reaction pathways": "chemistry", "Reaction mechanisms": "mechanism",
    "Catalysis": "mechanism", "Tessellations": "geometry", "Solids": "geometry",
    "Transformations": "geometry", "Trigonometry": "geometry",
    "Mountains": "geology", "Mantle convection": "geology", "Rivers": "geology",
    "Deserts": "climate", "Biomes": "climate", "Meteorology": "climate",
    "Human migration": "demography", "Behavior": "society",
    "Development": "society", "Bridges": "engineering", "Signal processing": "signals",
    "Digital logic": "signals",
    "Capital structure": "finance", "Accounting": "finance", "Markets": "economics",
    # filled in after a pass that showed these topics leaving a document with its domain
    # tag and nothing else
    "Balance sheet": "accounting", "Euclidean geometry": "geometry",
    "Quantum fields": "quantum", "Cultures": "anthropology",
    "Skeletal system": "anatomy", "Muscular system": "anatomy",
    "RF systems": "signals", "Surgery": "surgery", "Imaging": "imaging",
    "Drug mechanisms": "pharmacology", "Drug metabolism": "pharmacology",
    "Laminar flow": "fluids", "Turbulence": "fluids", "Vortices": "fluids",
    "Equilibrium": "mechanism", "GPU": "computing", "Clouds": "climate",
}

HASHTAG_RE = re.compile(r"#([A-Za-z0-9][\w-]{1,30})")


def facts(json_path: Path) -> set:
    """Structural tags, each read from what the document actually contains."""
    s = json_path.read_text()
    out = set()
    if any(k in s for k in ('"camera3D"', '"drawMesh3D"', '"defineMesh3D"',
                            '"clearDepth3D"', '"lights3D"', '"meshPrimitive3D"')):
        out.add("3d")
    if '"touchExpression"' in s or '"onClick"' in s or '"onTouchDown"' in s:
        out.add("touch")
    if "continuousSec()" in s or "animationTime" in s or "timeInSec()" in s:
        out.add("animated")
    if '"createParticles"' in s:
        out.add("particles")
    return out


def main() -> int:
    dry = "--dry-run" in sys.argv
    sets = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not sets:
        sys.exit(__doc__)
    sched = json.loads((ROOT / "catalog/vis-schedule.json").read_text())
    plan = {}
    for s in sched["sets"]:
        for d in s.get("documents", []):
            plan[d["id"]] = d

    wrote = skipped = missing = 0
    for n in sets:
        setdir = WORK / ("set-%02d" % int(n))
        coll = DOCS / ("vis-set-%02d" % int(n))
        for jp in sorted(setdir.glob("*.json")):
            pid = jp.stem
            ep = coll / pid.lower() / "entry.json"
            if not ep.exists():
                missing += 1
                continue
            entry = json.loads(ep.read_text())
            if (entry.get("description") or "").strip():
                skipped += 1
                continue
            sentence = (json.loads(jp.read_text()).get("header", {})
                        .get("contentDescription") or "").strip().rstrip(".")
            meta = plan.get(pid, {})
            tags = set(facts(jp))
            if meta.get("domain") in DOMAIN_TAG:
                tags.add(DOMAIN_TAG[meta["domain"]])
            if meta.get("topic") in TOPIC_TAG:
                tags.add(TOPIC_TAG[meta["topic"]])
            if meta.get("how") == "interactive":
                tags.add("interactive")
            if not sentence:
                missing += 1
                continue
            desc = sentence + ". " + " ".join("#" + t for t in sorted(tags))
            if dry:
                print("  %-16s %s" % (pid, " ".join(sorted(tags))))
            else:
                entry["description"] = desc
                entry["descriptionSource"] = "generator"
                entry["tags"] = sorted(set(entry.get("tags") or [])
                                       | {t.lower() for t in HASHTAG_RE.findall(desc)})
                ep.write_text(json.dumps(entry, indent=2) + "\n")
            wrote += 1
    verb = "would write" if dry else "wrote"
    print("  %s %d, skipped %d already described, %d without a source sentence"
          % (verb, wrote, skipped, missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
