#!/usr/bin/env python3
"""Render one 3D document under several cameras and tile the results.

    python3 tools/camsweep.py work/set-10/PHY-CM-00033.json

Framing a 3D scene by editing the generator and rebuilding is a slow loop, and the thing
being judged - whether the surface reads - is only visible in the picture. This patches the
camera in the compiled JSON, renders each variant at a pinned time, and lays them out side
by side with their parameters printed on them.

The time is pinned to 0 so any spin variable sits at its starting value; otherwise each
variant is rendered at a different rotation and the comparison is between rotations rather
than between cameras.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RCJ = Path.home() / "code/github/rcJson"
RC2IMAGE = (Path.home() /
            "code/github/rcExperiments/players/cpp/build/tools/rc2image/rc2image")
TMP = Path("/Users/john/.claude/jobs/168469d6/tmp")

# eye, centre, fovY
VARIANTS = [
    ([2.6, 2.1, 3.5], [0.0, -0.05, 0.0], 0.74),
    ([2.6, 3.2, 3.5], [0.0, -0.05, 0.0], 0.74),
    ([2.2, 3.6, 2.8], [0.0, -0.10, 0.0], 0.70),
    ([3.0, 4.2, 3.6], [0.0, -0.10, 0.0], 0.62),
]


def find_camera(node):
    """The camera can be anywhere in the command tree, so walk it rather than assuming a
    position. Returns the dict itself, so patching it patches the document."""
    if isinstance(node, dict):
        if "camera3D" in node:
            return node["camera3D"]
        for v in node.values():
            r = find_camera(v)
            if r:
                return r
    elif isinstance(node, list):
        for v in node:
            r = find_camera(v)
            if r:
                return r
    return None


def main():
    src = Path(sys.argv[1])
    # argv[2] is an optional JSON list of [eye, centre, fovY], so a second sweep does not
    # mean editing this file between runs
    variants = json.loads(sys.argv[2]) if len(sys.argv) > 2 else VARIANTS
    sys.path.insert(0, str(RCJ))
    from rcj import convert
    from PIL import Image, ImageDraw

    shots = []
    for n, (eye, centre, fov) in enumerate(variants):
        doc = json.loads(src.read_text())
        cam = find_camera(doc)
        if cam is None:
            sys.exit("no camera3D in %s" % src)
        cam["eye"], cam["center"], cam["fovY"] = eye, centre, fov
        jp = TMP / ("cam%d.json" % n)
        jp.write_text(json.dumps(doc))
        rc = TMP / ("cam%d.rc" % n)
        rc.write_bytes(convert(jp.read_text(), base_dir=str(src.parent)))
        png = TMP / ("cam%d.png" % n)
        p = subprocess.run([str(RC2IMAGE), str(rc), str(png), "--time", "0", "--seed", "7"],
                           capture_output=True, text=True)
        if p.returncode:
            print("  FAIL %d: %s" % (n, (p.stderr or p.stdout)[:80]))
            continue
        im = Image.open(png).convert("RGB")
        ImageDraw.Draw(im).text((6, 6), "eye %s  ctr %s  fov %.2f" % (eye, centre, fov),
                                fill=(255, 220, 80))
        shots.append(im)
        print("  %d  eye %s centre %s fov %.2f" % (n, eye, centre, fov))

    if not shots:
        return 1
    w, h = shots[0].size
    sheet = Image.new("RGB", (w * len(shots), h), (12, 12, 14))
    for i, im in enumerate(shots):
        sheet.paste(im, (i * w, 0))
    out = TMP / "camsweep.png"
    sheet.save(out)
    print("  -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
