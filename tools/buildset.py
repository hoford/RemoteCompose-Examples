#!/usr/bin/env python3
"""Compile and render a set, or just the documents named.

    python3 tools/buildset.py 9                 # the whole set
    python3 tools/buildset.py 9 CSC-DS-00009    # one document, after an edit

`make_setNN.py` only writes JSON. Getting from there to something you can look at takes
two more steps - rcj to compile the wire format, rc2image to paint it - and during a review
pass those are run over and over on one document at a time. Doing them by hand is how a
stale `.rc` ends up next to a fresh `.json`, which is a confusing thing to debug: the
generator reports success and the render does not change.

Renders are pinned with --clock AND --seed. The clock alone does not pin rand() (F-023),
and an unpinned render cannot be compared against anything, including its own previous run.
"""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
RCJ = Path.home() / "code/github/rcJson"
RC2IMAGE = (Path.home() /
            "code/github/rcExperiments/players/cpp/build/tools/rc2image/rc2image")

# Any fixed instant will do; it only has to be the same one every time, so that two renders
# of an unchanged document are byte-identical and a diff means a real change.
CLOCK = "2026-03-04T10:17:00"
SEED = "7"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    setdir = ROOT / "work" / ("set-%02d" % int(sys.argv[1]))
    wanted = set(sys.argv[2:])
    maker = setdir / ("make_set%02d.py" % int(sys.argv[1]))
    if not maker.exists():
        sys.exit("no %s" % maker)

    r = subprocess.run([sys.executable, str(maker)], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stdout + r.stderr)

    sys.path.insert(0, str(RCJ))
    from rcj import convert

    render = setdir / "render"
    render.mkdir(exist_ok=True)
    ok = bad = 0
    for jp in sorted(setdir.glob("*.json")):
        if wanted and jp.stem not in wanted:
            continue
        try:
            data = convert(jp.read_text(), base_dir=str(setdir))
        except Exception as e:
            print("  FAIL  %-16s %s: %s" % (jp.stem, type(e).__name__, str(e)[:70]))
            bad += 1
            continue
        rc = setdir / (jp.stem + ".rc")
        rc.write_bytes(data)
        png = render / (jp.stem + ".png")
        p = subprocess.run([str(RC2IMAGE), str(rc), str(png),
                            "--clock", CLOCK, "--seed", SEED],
                           capture_output=True, text=True)
        if p.returncode:
            print("  FAIL  %-16s render: %s" % (jp.stem, (p.stderr or p.stdout)[:70]))
            bad += 1
            continue
        hdr = json.loads(jp.read_text())["header"]
        relinked = relink(int(sys.argv[1]), jp, rc)
        print("  ok    %-16s %6d B   %dx%d%s" % (jp.stem, len(data), hdr["width"],
                                                 hdr["height"],
                                                 "  -> docs" if relinked else ""))
        ok += 1
    print("  %d built, %d failed" % (ok, bad))
    contact_sheet(setdir, render)
    return 1 if bad else 0


def relink(setno: int, json_path: Path, rc_path: Path) -> bool:
    """Push a rebuilt document into its landed copy under docs/.

    The site serves `docs/<collection>/<slug>/doc.rc`, not `work/`. Rebuilding a landed
    document used to change only the work/ copy, so the page went on serving the old bytes
    and nothing said so - `rcx verify` passes either way, because docs/ stays internally
    consistent with its own stale file. That cost a wrong conclusion: a browser test of a
    "fixed" document was really exercising the version before the fix.

    `rcx add` is not the tool for this; it dedupes on content hash and would mint a second
    entry rather than update the first.
    """
    dest = DOCS / ("vis-set-%02d" % setno) / json_path.stem.lower()
    if not dest.is_dir():
        return False
    shutil.copy2(rc_path, dest / "doc.rc")
    shutil.copy2(json_path, dest / "doc.json")
    entry = dest / "entry.json"
    if entry.exists():
        e = json.loads(entry.read_text())
        e["sha256"] = hashlib.sha256(rc_path.read_bytes()).hexdigest()
        entry.write_text(json.dumps(e, indent=2) + "\n")
    return True


def contact_sheet(setdir, render, cols=4, cell=300):
    """One image of the whole set. Rebuilt on every run, including partial ones, because a
    sheet that is older than the renders beside it is worse than no sheet - it is the view
    most likely to be glanced at and believed."""
    try:
        from PIL import Image
    except ImportError:
        return
    shots = sorted(render.glob("*.png"))
    if not shots:
        return
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), (16, 16, 18))
    for i, p in enumerate(shots):
        im = Image.open(p).convert("RGB")
        im.thumbnail((cell - 12, cell - 12), Image.LANCZOS)
        x = (i % cols) * cell + (cell - im.width) // 2
        y = (i // cols) * cell + (cell - im.height) // 2
        sheet.paste(im, (x, y))
    sheet.save(setdir / "contact-sheet.png")
    print("  contact sheet: %d documents" % len(shots))


if __name__ == "__main__":
    sys.exit(main())
