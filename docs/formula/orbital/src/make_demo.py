#!/usr/bin/env python3
"""Author the 3D demo documents and emit a self-contained web page that plays them live.

    python3 d3/make_demo.py        # -> d3/demo/index.html

Documents are inlined as base64 so the page opens straight from disk: fetching a local .rc over
file:// is blocked by CORS, and a demo that needs a server running is a demo nobody opens. The
player bundle stays external — it is 700 KB and a <script src> to a sibling file is not blocked.

Everything animates at once. These are procedural 3D documents; a grid of frozen thumbnails
would hide the only thing worth looking at.
"""

import base64
import json
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import rcj  # noqa: E402

OUT = HERE / "demo"
BUNDLE = pathlib.Path("/Users/john/code/github/rcExperiments/players/typescript/"
                      "web-player/bundle.js")

W, H = 320, 320
BG = "#FF0E1420"


def doc(commands, w=W, h=H, description=""):
    """The shared frame: a canvas filling the card, cleared to the same dark background."""
    body = [
        {"paint": {"ops": [{"color": BG}, {"style": "fill"}]}},
        {"drawRect": {"left": 0, "top": 0, "right": w, "bottom": h}},
        {"clearDepth3D": {}},
    ] + commands
    return {
        "header": {"apiLevel": 7, "width": w, "height": h, "profiles": 513,
                   "contentDescription": description, "orderedResources": True},
        "root": [{"box": {"modifiers": ["fillMaxSize"], "children": [{
            "type": "canvas", "modifiers": ["fillMaxSize"], "commands": body}]}}],
    }


def camera(eye=(0, 1.2, 5.2), center=(0, 0, 0), fov=0.85, aspect=1.0):
    return {"camera3D": {"projection": "perspective", "fovY": fov, "aspect": aspect,
                         "near": 0.1, "far": 100.0,
                         "eye": list(eye), "center": list(center), "up": [0, 1, 0]}}


def lights(key=(-0.4, -0.6, -0.7), fill=(-3.0, 2.0, 2.5)):
    return {"lights3D": {"lights": [
        {"type": "directional", "color": "#FFFFF4E4", "dir": list(key), "intensity": 1.0},
        {"type": "point", "color": "#FF5588FF", "pos": list(fill), "intensity": 1.0}]}}


def place(mesh, at, colour, spin=None, mode="software-smooth", tilt=None):
    """Position a mesh and draw it; `spin` turns it about its own Y axis."""
    out = [{"matrix3D": {"op": "identity"}},
           {"matrix3D": {"op": "translate", "x": at[0], "y": at[1], "z": at[2]}}]
    if spin is not None:
        out.append({"matrix3D": {"op": "rotate", "angle": spin, "axis": [0, 1, 0]}})
    if tilt is not None:
        out.append({"matrix3D": {"op": "rotate", "angle": tilt, "axis": [1, 0, 0]}})
    out.append({"paint": {"ops": [{"color": colour}]}})
    out.append({"drawMesh3D": {"mesh": mesh, "mode": mode}})
    return out


SPIN = "continuousSec() * 0.5"
DEMOS = []


def demo(slug, title, blurb, document, note=""):
    DEMOS.append({"slug": slug, "title": title, "blurb": blurb, "note": note, "doc": document})


# ── 1. the primitive gallery ────────────────────────────────────────────────
shapes = [
    ("sphere", {"radius": 0.42, "center": [0, 0, 0]}, 24, [-1.15, 0.75, 0], "#FFE8944A"),
    ("torus", {"majorRadius": 0.38, "minorRadius": 0.15, "center": [0, 0, 0]}, 22,
     [0, 0.75, 0], "#FF7FE0C0"),
    ("roundedCube", {"dimX": 0.75, "dimY": 0.75, "dimZ": 0.75, "center": [0, 0, 0],
                     "cornerRadius": 0.17}, 5, [1.15, 0.75, 0], "#FFE06A8A"),
    ("cone", {"radius": 0.38, "height": 0.8, "center": [0, -0.4, 0]}, 20,
     [-1.15, -0.55, 0], "#FF8AA8F0"),
    ("icosphere", {"radius": 0.42, "center": [0, 0, 0]}, 2, [0, -0.55, 0], "#FFB0E060"),
    ("extrudeSquircle", {"radius": 0.42, "exponent": 4.0, "depth": 0.26,
                         "center": [0, 0, 0]}, 32, [1.15, -0.55, 0], "#FFF0C860"),
]
cmds = [camera(eye=(0, 0.35, 4.4)), lights(), {"material3D": {"specular": 0.35, "shininess": 36}}]
for i, (kind, params, seg, _, _) in enumerate(shapes):
    cmds.append({"meshPrimitive3D": dict({"id": i + 1, "primitive": kind, "segments": seg},
                                         **params)})
for i, (_, _, _, at, colour) in enumerate(shapes):
    cmds += place(i + 1, at, colour, spin=SPIN)
demo("primitives", "Parametric primitives",
     "Six shapes named rather than shipped. No vertex data crosses the wire at all — the "
     "player builds the geometry from a type and a handful of numbers.",
     doc(cmds, description="3D primitive gallery"))

# ── 2. reactive geometry ────────────────────────────────────────────────────
breathe = "0.30 + sin(continuousSec() * 1.2) * 0.16"
pitch = "0.40 + sin(continuousSec() * 0.9) * 0.22"
cmds = [camera(eye=(0, 0.3, 4.6)), lights(), {"material3D": {"specular": 0.3, "shininess": 32}},
        {"meshPrimitive3D": {"id": 1, "primitive": "torus", "segments": 26,
                             "majorRadius": 0.62, "minorRadius": breathe,
                             "center": [0, 0, 0]}},
        {"meshPrimitive3D": {"id": 2, "primitive": "helix", "segments": 10,
                             "coilRadius": 0.42, "tubeRadius": 0.10,
                             "pitch": pitch, "turns": 2.6}}]
cmds += place(1, [-0.95, 0, 0], "#FF7FE0C0", spin=SPIN)
cmds += place(2, [0.95, 0, 0], "#FFE06A8A", spin=SPIN)
demo("reactive", "Geometry driven by expressions",
     "The torus tube radius and the coil pitch are expressions, not constants. Each frame the "
     "mesh is <em>rebuilt</em> on the player — this is not a transform on fixed geometry.",
     doc(cmds, description="reactive 3D geometry"))

# ── 3. expression surfaces ──────────────────────────────────────────────────
cmds = [camera(eye=(0, 2.1, 4.2), center=(0, -0.15, 0)), lights(),
        {"material3D": {"specular": 0.28, "shininess": 30}},
        {"meshExpression3D": {
            "id": 1, "surface": "heightField",
            "xRange": [-1.5, 1.5], "uCount": 40, "zRange": [-1.5, 1.5], "vCount": 40,
            "yRange": [-1.2, 1.2],
            "height": "sin(sqrt(u*u + v*v) * 3.6 - continuousSec() * 2.2) * 0.30"}}]
cmds += place(1, [0, -0.35, 0], "#FF7FE0C0")
demo("surface", "A surface from a formula",
     "A 40&times;40 grid whose height is one RPN expression evaluated per vertex per frame. "
     "The ripple travels because the formula reads the clock.",
     doc(cmds, description="expression height field"))

# ── 4. sweeps and extrusions ────────────────────────────────────────────────
cmds = [camera(eye=(0, 0.6, 4.6)), lights(), {"material3D": {"specular": 0.3, "shininess": 32}},
        {"meshPrimitive3D": {"id": 1, "primitive": "captube", "segments": 14, "radius": 0.11,
                             "points": [[-0.62, -0.30, 0.12], [-0.20, 0.32, -0.18],
                                        [0.22, -0.30, 0.18], [0.64, 0.28, 0.0]]}},
        {"meshPrimitive3D": {"id": 2, "primitive": "sweep",
                             "closed": True, "capStart": True, "capEnd": True,
                             "section": [[0.18, 0.0], [0.09, 0.155], [-0.09, 0.155],
                                         [-0.18, 0.0], [-0.09, -0.155], [0.09, -0.155]],
                             "path": [[-0.62, -0.22, 0.0], [-0.31, 0.14, 0.18],
                                      [0.0, 0.28, 0.0], [0.31, 0.14, -0.18],
                                      [0.62, -0.22, 0.0]],
                             "scales": [0.6, 1.0, 1.4, 1.0, 0.6],
                             "twists": [0.0, 0.4, 0.8, 1.2, 1.6]}},
        {"meshPrimitive3D": {"id": 3, "primitive": "extrudePath", "depth": 0.30, "bevel": 0.055,
                             "contours": [[[-0.45, -0.45], [0.45, -0.45], [0.45, 0.45],
                                           [-0.45, 0.45]],
                                          [[-0.18, -0.18], [-0.18, 0.18], [0.18, 0.18],
                                           [0.18, -0.18]]]}}]
cmds += place(1, [-1.15, 0.55, 0], "#FFF0C860", spin=SPIN)
cmds += place(2, [1.15, 0.55, 0], "#FF8AA8F0", spin=SPIN)
cmds += place(3, [0, -0.75, 0], "#FFE8944A", spin=SPIN)
demo("sweeps", "Swept and extruded solids",
     "A splined tube through four control points, a hexagonal section swept along a path with "
     "per-station scale and twist, and an arbitrary outline extruded with a bevel — including "
     "its hole.",
     doc(cmds, description="swept and extruded 3D solids"))

# ── 5. wireframe ────────────────────────────────────────────────────────────
cmds = [camera(eye=(0, 0.4, 4.3)), lights(),
        {"meshPrimitive3D": {"id": 1, "primitive": "sphere", "segments": 18,
                             "radius": 0.62, "center": [0, 0, 0]}},
        {"meshPrimitive3D": {"id": 2, "primitive": "torus", "segments": 20,
                             "majorRadius": 0.55, "minorRadius": 0.2, "center": [0, 0, 0]}}]
# Shaded pass then a wireframe pass of the same mesh: the depth buffer is shared within a 3D
# pass, so the second draw's hidden lines are removed against the first.
cmds += place(1, [-0.95, 0, 0], "#FF25405C", spin=SPIN)
cmds += place(1, [-0.95, 0, 0], "#FF7FE0C0", spin=SPIN, mode="software-flat")
cmds[-1]["drawMesh3D"]["wireframe"] = True
cmds += place(2, [0.95, 0, 0], "#FF3A2A46", spin=SPIN, tilt=0.5)
cmds += place(2, [0.95, 0, 0], "#FFE06A8A", spin=SPIN, tilt=0.5, mode="software-flat")
cmds[-1]["drawMesh3D"]["wireframe"] = True
demo("wireframe", "Hidden-line wireframe",
     "Each solid is drawn twice: shaded, then as a depth-tested wireframe over the top. Edges "
     "behind nearer surface are removed, which needs a real depth buffer — so this style is "
     "software-only by construction.",
     doc(cmds, description="hidden-line wireframe"))

# ── 6. vector expression ────────────────────────────────────────────────────
sweep = ("normalize(vec3(cos(continuousSec()*0.6)*2.0, 0.9, "
         "sin(continuousSec()*0.6)*2.0))")
cmds = [
    {"vectorExpression": {"name": "dir", "dimension": 3, "expression": sweep}},
    camera(eye=(0, 1.0, 4.4)),
    {"lights3D": {"lights": [
        {"type": "directional", "color": "#FFFFF0E0",
         "dir": ["0 - @dir.x", "0 - @dir.y", "0 - @dir.z"], "intensity": 1.0},
        {"type": "point", "color": "#FF4477FF", "pos": [-2.5, 1.5, 2.0], "intensity": 0.6}]}},
    {"material3D": {"specular": 0.4, "shininess": 40}},
    {"meshPrimitive3D": {"id": 1, "primitive": "sphere", "segments": 26, "radius": 0.8,
                         "center": [0, 0, 0]}},
    {"meshPrimitive3D": {"id": 2, "primitive": "cylinder", "segments": 12, "radius": 0.07,
                         "from": [0, 0, 0],
                         "to": ["@dir.x * 1.7", "@dir.y * 1.7", "@dir.z * 1.7"]}},
    {"meshPrimitive3D": {"id": 3, "primitive": "sphere", "segments": 14, "radius": 0.15,
                         "center": ["@dir.x * 1.7", "@dir.y * 1.7", "@dir.z * 1.7"]}},
    {"matrix3D": {"op": "identity"}},
]
cmds += [{"paint": {"ops": [{"color": "#FFB0BCCF"}]}},
         {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}},
         {"paint": {"ops": [{"color": "#FFE8944A"}]}},
         {"drawMesh3D": {"mesh": 2, "mode": "software-smooth"}},
         {"paint": {"ops": [{"color": "#FFFFD066"}]}},
         {"drawMesh3D": {"mesh": 3, "mode": "software-smooth"}}]
demo("vector", "One vector, two consumers",
     "A single <code>normalize(vec3(&hellip;))</code> produces three scalars. The light "
     "direction and the rod's endpoint both read them, so they cannot drift apart.",
     doc(cmds, description="vector expression driving light and geometry"),
     note="This is the document that exposed an upstream bug: on the unpatched Android player "
          "the vector opcodes are overwritten during variable resolution, the rod collapses to "
          "zero length and the key light goes dark. Reported to the team.")


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RemoteCompose 3D</title>
<style>
  :root {
    --bg: #0b0d12; --panel: #141821; --line: #232936;
    --ink: #e9edf5; --dim: #8b95a8; --accent: #7f9cf5;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font: 15px/1.6 ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  header { padding: 40px 24px 8px; max-width: 1180px; margin: 0 auto; }
  h1 { font-size: 26px; margin: 0 0 6px; letter-spacing: -0.2px; }
  header p { color: var(--dim); margin: 0; max-width: 60ch; }
  main {
    max-width: 1180px; margin: 0 auto; padding: 24px;
    display: grid; gap: 22px; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  }
  figure {
    margin: 0; background: var(--panel); border: 1px solid var(--line);
    border-radius: 14px; overflow: hidden; display: flex; flex-direction: column;
  }
  canvas { display: block; width: 100%; height: auto; background: #0e1420; cursor: zoom-in; }
  figcaption { padding: 14px 16px 16px; }
  .title { font-weight: 600; margin-bottom: 4px; }
  .blurb { color: var(--dim); font-size: 13.5px; }
  .note {
    margin-top: 10px; padding: 9px 11px; border-radius: 8px; font-size: 12.5px;
    background: #1d1a12; border: 1px solid #4a3f22; color: #e8cf9a;
  }
  .meta {
    margin-top: 10px; font-size: 12px; color: var(--dim);
    display: flex; gap: 12px; flex-wrap: wrap; align-items: center;
  }
  .size { font-variant-numeric: tabular-nums; color: var(--accent); }
  code { background: #1b202b; padding: 1px 5px; border-radius: 4px; font-size: 12.5px; }
  footer {
    max-width: 1180px; margin: 0 auto; padding: 8px 24px 56px;
    color: var(--dim); font-size: 13px;
  }
  footer b { color: var(--ink); font-weight: 600; }
  dialog {
    border: 1px solid var(--line); background: var(--panel); color: var(--ink);
    border-radius: 16px; padding: 0; max-width: 94vw;
  }
  dialog::backdrop { background: rgba(0,0,0,.78); }
  dialog canvas { width: 560px; max-width: 90vw; cursor: default; }
  dialog .bar {
    display: flex; gap: 10px; align-items: center; padding: 12px 16px;
    border-top: 1px solid var(--line); font-size: 13px;
  }
  dialog .bar .grow { flex: 1; }
  button {
    background: #1b202b; border: 1px solid var(--line); color: var(--ink);
    border-radius: 8px; padding: 6px 12px; font: inherit; font-size: 13px; cursor: pointer;
  }
</style>
</head>
<body>
<header>
  <h1>RemoteCompose 3D</h1>
  <p>Procedural 3D documents, playing live in this page. Every one is a few hundred bytes of
  JSON compiled to a binary document &mdash; no meshes, no textures, no shader source. Click a
  panel to enlarge.</p>
</header>
<main id="grid"></main>
<footer id="foot"></footer>

<dialog id="zoom">
  <canvas id="zoomCanvas"></canvas>
  <div class="bar"><span class="grow" id="zoomName"></span>
    <button id="prev">&larr;</button><button id="next">&rarr;</button>
    <button id="close">close</button></div>
</dialog>

<script src="./bundle.js"></script>
<script>
const DEMOS = __DEMOS__;
const grid = document.getElementById('grid');
const zoom = document.getElementById('zoom');
const zoomCanvas = document.getElementById('zoomCanvas');
const zoomName = document.getElementById('zoomName');
let current = -1;
let zoomPlayer = null;

function bytesOf(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out.buffer;
}

DEMOS.forEach((d, i) => {
  const fig = document.createElement('figure');
  const c = document.createElement('canvas');
  c.width = d.w; c.height = d.h;
  c.addEventListener('click', () => open(i));
  const cap = document.createElement('figcaption');
  cap.innerHTML =
    '<div class="title">' + d.title + '</div>' +
    '<div class="blurb">' + d.blurb + '</div>' +
    (d.note ? '<div class="note">' + d.note + '</div>' : '') +
    '<div class="meta"><span class="size">' + d.size + ' bytes</span>' +
    '<span>' + d.w + '&times;' + d.h + '</span></div>';
  fig.append(c, cap);
  grid.appendChild(fig);
  try {
    const p = new window.RC.RcdPlayer(c);
    p.loadFromArrayBuffer(bytesOf(d.b64));
  } catch (e) {
    cap.innerHTML += '<div class="note">failed: ' + e.message + '</div>';
  }
});

function open(i) {
  current = i;
  const d = DEMOS[i];
  zoomCanvas.width = d.w; zoomCanvas.height = d.h;
  zoomName.textContent = d.title + ' \\u2014 ' + d.size + ' bytes';
  // A fresh player each time: reusing one across documents leaves the previous document's
  // state behind, which shows up as a panel that never repaints.
  zoomPlayer = new window.RC.RcdPlayer(zoomCanvas);
  zoomPlayer.loadFromArrayBuffer(bytesOf(d.b64));
  if (!zoom.open) zoom.showModal();
}
function step(n) { open((current + n + DEMOS.length) % DEMOS.length); }
document.getElementById('next').onclick = () => step(1);
document.getElementById('prev').onclick = () => step(-1);
document.getElementById('close').onclick = () => { zoom.close(); zoomPlayer = null; };
zoom.addEventListener('close', () => { zoomPlayer = null; });
document.addEventListener('keydown', e => {
  if (!zoom.open) return;
  if (e.key === 'ArrowRight') step(1);
  if (e.key === 'ArrowLeft') step(-1);
});

const total = DEMOS.reduce((a, d) => a + d.size, 0);
document.getElementById('foot').innerHTML =
  '<b>' + DEMOS.length + ' documents, ' + total + ' bytes in total</b> &mdash; less than a ' +
  'single uncompressed screenshot of this page. The geometry is generated on the player from ' +
  'parameters, and anything that moves is an expression re-evaluated per frame rather than ' +
  'baked animation.';
</script>
</body>
</html>
"""


def main():
    OUT.mkdir(exist_ok=True)
    entries = []
    for d in DEMOS:
        data = rcj.convert_doc(d["doc"])
        (HERE / f"demo_{d['slug']}.json").write_text(json.dumps(d["doc"], indent=1))
        (HERE / f"demo_{d['slug']}.rc").write_bytes(data)
        entries.append({
            "slug": d["slug"], "title": d["title"], "blurb": d["blurb"], "note": d["note"],
            "w": d["doc"]["header"]["width"], "h": d["doc"]["header"]["height"],
            "size": len(data), "b64": base64.b64encode(data).decode(),
        })
        print(f"  {d['slug']:12} {len(data):5} B")
    page = PAGE.replace("__DEMOS__", json.dumps(entries))
    (OUT / "index.html").write_text(page)
    if BUNDLE.exists():
        shutil.copy(BUNDLE, OUT / "bundle.js")
    else:
        print(f"  WARNING: player bundle not found at {BUNDLE}")
    print(f"\n  {len(entries)} documents -> {OUT / 'index.html'} ({len(page) / 1024:.0f} KB)")

    # A single-file build for phones. A sibling <script src> works fine over file:// on desktop,
    # but Android's Downloads directory is not a normal filesystem to Chrome and the sibling
    # fetch is refused, so the bundle has to be inlined for the page to work on a device.
    if BUNDLE.exists():
        js = BUNDLE.read_text()
        standalone = page.replace('<script src="./bundle.js"></script>',
                                  "<script>\n" + js + "\n</script>")
        target = OUT / "standalone.html"
        target.write_text(standalone)
        print(f"  standalone (bundle inlined) -> {target} "
              f"({len(standalone) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
