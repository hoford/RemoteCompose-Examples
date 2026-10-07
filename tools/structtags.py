#!/usr/bin/env python3
"""Guarantee the three structural hashtags on every catalogued document.

    python3 tools/structtags.py --dry-run        # show what would change
    python3 tools/structtags.py                  # apply, then run `rcx catalog`
    python3 tools/structtags.py 13               # one set

Three tags carry most of the filtering weight on the site, and each answers a question a
reader actually asks before opening a document:

    #3d        is it a 3D scene
    #animated  does it move by itself
    #input     can I touch it

`vistags.py` already derives tags, but only ever fills a **blank** description, so a document
that arrived with any description at all kept whatever tags it was born with. That left 43 of
193 landed documents disagreeing with their own contents. This tool is the other half: it
does not care whether a description exists, it only ensures these three tags are right.

Everything is read from the document, never from the schedule or the title. Two corrections
to the older rule, both of which were making the filter lie:

**`#animated` means "moves by itself", which is not the same as "reads a clock".** A particle
system integrates its own state every frame from `dt`, so it moves with no clock call
anywhere in the document. Thirteen documents move visibly and were not tagged animated. A
document that only moves when touched is `#input`, not `#animated` — being touchable is a
different claim from moving on its own, and a reader scanning for something to put on a
screen wants the distinction.

**`#input` replaces `#touch`.** One name per concept. Nothing in the site hardcodes either —
facets are derived from whatever tags exist — so the rename is safe, and carrying two
synonyms for "you can touch it" would split every filter that used them.

Additive and idempotent: other tags are never removed, hand-written descriptions keep their
prose, and re-running changes nothing. Tags live both in the description text (where the
reader sees them, and where `rcx describe` harvests them) and in the entry's `tags` array
(which is what `rcx catalog` reads), so both are kept in step.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
WORK = ROOT / "work"

# Every 3D opcode, not the six the older rule happened to list. `matrix3D` and `texture3D`
# are only meaningful inside a 3D scene, so they cannot produce a false positive, and
# including them means a document is still recognised if its drawing op is ever renamed.
THREE_D = ('"camera3D"', '"drawMesh3D"', '"defineMesh3D"', '"clearDepth3D"', '"lights3D"',
           '"meshPrimitive3D"', '"matrix3D"', '"texture3D"', '"meshExpression3D"',
           '"material3D"', '"depthBias3D"')

# touchExpression is the expression-level hook; the others are modifiers. A document needs
# only one of them to be touchable.
INPUT = ('"touchExpression"', '"onClick"', '"onTouchDown"', '"onTouchUp"', '"onTouchCancel"')

# Reading any of these makes the document a function of wall-clock time.
CLOCK = ("continuousSec()", "animationTime", "timeInSec()")

# A particle system moves itself: `particlesLoop` advances each particle every frame from
# `dt`, with no clock read required anywhere.
PARTICLES = '"createParticles"'

HASHTAG_RE = re.compile(r"#([A-Za-z0-9][\w-]{1,30})")


def facts(source: str) -> set:
    """The three structural tags, each read from what the document actually contains."""
    out = set()
    if any(k in source for k in THREE_D):
        out.add("3d")
    if any(k in source for k in INPUT):
        out.add("input")
    if any(k in source for k in CLOCK) or PARTICLES in source:
        out.add("animated")
    return out


def retag_description(desc: str, required: set) -> str:
    """Add any missing hashtag, and rename #touch to #input. Prose is left alone."""
    desc = re.sub(r"#touch\b", "#input", desc)
    present = {t.lower() for t in HASHTAG_RE.findall(desc)}
    missing = sorted(required - present)
    if not missing:
        return desc
    joined = " ".join("#" + t for t in missing)
    if not desc.strip():
        return joined
    sep = " " if desc.rstrip().endswith(("#", ".")) or desc.endswith(" ") else " "
    return desc.rstrip() + sep + joined


def main() -> int:
    dry = "--dry-run" in sys.argv
    only = {int(a) for a in sys.argv[1:] if not a.startswith("--")}

    changed = untouched = nolanding = 0
    report = []
    for setdir in sorted(WORK.glob("set-*")):
        n = int(setdir.name.split("-")[1])
        if only and n not in only:
            continue
        coll = DOCS / ("vis-set-%02d" % n)
        for jp in sorted(setdir.glob("*.json")):
            ep = coll / jp.stem.lower() / "entry.json"
            if not ep.exists():
                nolanding += 1
                continue
            required = facts(jp.read_text())
            entry = json.loads(ep.read_text())
            before_desc = entry.get("description") or ""
            before_tags = sorted({t.lower() for t in entry.get("tags") or []})

            desc = retag_description(before_desc, required)
            # Only the three structural tags, plus the touch->input rename. Harvesting every
            # other hashtag out of the description into `tags` would also be a defensible
            # repair - several descriptions carry tags the array never got - but it is a
            # different change, and mixing it in here would bury 51 structural corrections
            # under a few hundred cosmetic ones in the same diff.
            tags = sorted({("input" if t == "touch" else t) for t in before_tags} | required)

            if desc == before_desc and tags == before_tags:
                untouched += 1
                continue
            added = sorted(set(tags) - set(before_tags))
            removed = sorted(set(before_tags) - set(tags))
            report.append((n, jp.stem, added, removed))
            changed += 1
            if not dry:
                entry["description"] = desc
                entry["tags"] = tags
                ep.write_text(json.dumps(entry, indent=2) + "\n")

    for n, pid, added, removed in report:
        bits = []
        if added:
            bits.append("+" + ",".join(added))
        if removed:
            bits.append("-" + ",".join(removed))
        print("  set-%02d %-20s %s" % (n, pid, " ".join(bits)))
    verb = "would change" if dry else "changed"
    print("\n  %s %d, left %d already correct, %d not landed yet"
          % (verb, changed, untouched, nolanding))
    if not dry and changed:
        print("  now run: python3 tools/rcx.py catalog")
    return 0


if __name__ == "__main__":
    sys.exit(main())
