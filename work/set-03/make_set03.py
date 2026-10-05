#!/usr/bin/env python3
"""Build set 3 of the visualization programme: 16 documents.

    python3 work/set-03/make_set03.py

Work order from `python3 tools/visplan.py set 3`. No curation swap this time - the schedule
dealt a workable hand. The one pairing that looked wrong, Higgs field as annotated-layout in
3D, is fine once you notice a layout card can CONTAIN a 3D canvas (set 2's Feynman cards
proved the nesting), and the Mexican-hat potential is exactly the 3D object that subject
wants.

Carried forward from sets 1 and 2, all of it paid for once already:

  * text components key on `value`; `resources` sits at document top level
  * paint uses the `ops` array; panX -1 is left-aligned, 0 centres
  * mesh triangles wind [a, a+N+1, a+N] or the mesh is invisible with no error (F-008)
  * a containing wireframe is drawn LAST; it writes depth across whole faces (F-009)
  * a texture needs a FILLED mesh; wireframe shows edges only (F-010)
  * particle equations must not accumulate - immutable base, wobble at draw time - and
    position or size has to encode something or the document means nothing (set 1 and 2
    both needed rebuilding for this)
"""

import hashlib
import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent


# ── shared helpers (in-file so each document's src/ copy runs standalone) ───────
def header(w, h, desc):
    return {"apiLevel": 7, "width": w, "height": h, "profiles": 513,
            "contentDescription": desc}


def paint(*ops):
    return {"paint": {"ops": list(ops)}}


def canvas(commands, bg=None):
    mods = ["fillMaxSize"]
    if bg:
        mods.append({"background": bg})
    return {"canvas": {"modifiers": mods, "commands": commands}}


def text_at(s, x, y, size, colour, pan_x=-1.0, pan_y=0.0):
    """panX: -1 left edge at x, 0 centred on x, +1 right edge at x."""
    return [paint({"color": colour}, {"style": "fill"}, {"textSize": size}),
            {"drawTextAnchored": {"text": s, "x": x, "y": y,
                                  "panX": pan_x, "panY": pan_y, "flags": 0}}]


def var(name, value, commit=True):
    return {"variable": {"name": name, "value": value, "commit": commit}}


def title(cmds, W, H, head, sub):
    cmds[:0] = [paint({"color": INK}, {"style": "fill"}),
                {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}}]
    cmds += text_at(head, 20.0, 32.0, 19.0, TEXT)
    if sub:
        cmds += text_at(sub, 20.0, 52.0, 11.0, DIM)
    return cmds


def mesh_box(verts, normals, uv, idx, lo, hi):
    """An axis-aligned box as 12 triangles. Winding per F-008."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    faces = [((0, 0, 1),  [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]),
             ((0, 0, -1), [(x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)]),
             ((1, 0, 0),  [(x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)]),
             ((-1, 0, 0), [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)]),
             ((0, 1, 0),  [(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)]),
             ((0, -1, 0), [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)])]
    for n, quad in faces:
        base = len(verts) // 3
        for (px, py, pz) in quad:
            verts += [px, py, pz]
            normals += list(n)
            uv += [0.0, 0.0]
        idx += [base, base + 2, base + 1, base, base + 3, base + 2]


def surface_mesh(mesh_id, f, N, half=1.0, yscale=1.0, yoff=0.0):
    """A height-field surface y = f(u, v) over [-half, half]^2, with analytic-ish normals
    from finite differences. Winding per F-008."""
    verts, normals, uv, idx = [], [], [], []
    h = 1.0 / (N - 1)
    for i in range(N):
        for j in range(N):
            u, v = i / (N - 1), j / (N - 1)
            x, z = (u * 2 - 1) * half, (v * 2 - 1) * half
            y = f(u, v) * yscale + yoff
            verts += [round(x, 5), round(y, 5), round(z, 5)]
            du = (f(min(1.0, u + h), v) - f(max(0.0, u - h), v)) * yscale
            dv = (f(u, min(1.0, v + h)) - f(u, max(0.0, v - h))) * yscale
            nx, ny, nz = -du, 2.0 * h * half * 2, -dv
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            normals += [round(nx / ln, 5), round(ny / ln, 5), round(nz / ln, 5)]
            uv += [u, v]
    for i in range(N - 1):
        for j in range(N - 1):
            a = i * N + j
            idx += [a, a + N + 1, a + N, a, a + 1, a + N + 1]
    return {"defineMesh3D": {"id": mesh_id, "verts": verts, "normals": normals,
                             "uv": uv, "indices": idx}}


# ── palettes ───────────────────────────────────────────────────────────────────
# Three sets in, every document looked like the same document: one navy ground and one blue
# accent, 48 times. For a corpus whose job is to be a source of EXAMPLES that is a real
# weakness - a reader wants to see what the format can look like, not what one author's
# taste looks like.
#
# Six palettes with genuinely different grounds, including a light one, because a light
# document differs from a dark one far more than two dark documents differ from each other.
# Each supplies the same nine roles so no document needs to know which palette it got.
#
# The pick is a hash of the document id, NOT a random number. Generators here must be
# deterministic: the corpus stores compiled bytes and re-running a generator has to
# reproduce them, so `random` or a clock would make every rebuild a false diff.
PALETTES = {
    "midnight": ("#FF0C1220", "#FF141E33", "#FF2B3A5C", "#FFDCE4F2", "#FF8A99BC",
                 "#FF5B8CEE", "#FFE8A33D", "#FF4FD6C9", "#FFE8564F"),
    "carbon":   ("#FF131313", "#FF1E1E1E", "#FF343434", "#FFEDEDED", "#FF9A9A9A",
                 "#FFFF8A3D", "#FFFFD166", "#FF8BD450", "#FFFF5E5B"),
    "paper":    ("#FFEDEFF2", "#FFFFFFFF", "#FFC6CDD8", "#FF16203A", "#FF5B6880",
                 "#FF2F6BD8", "#FFB5651D", "#FF0E8F80", "#FFC0322C"),
    "plum":     ("#FF1A0F20", "#FF271634", "#FF43295A", "#FFF0E4F7", "#FFA98BBE",
                 "#FFC77DFF", "#FFFFC857", "#FF5BE8B5", "#FFFF6B9D"),
    "forest":   ("#FF0B1410", "#FF14241C", "#FF27402F", "#FFE4F0E6", "#FF8FA894",
                 "#FF6FD08C", "#FFE0B354", "#FF4FC3D6", "#FFE07A5F"),
    "ember":    ("#FF1A1310", "#FF28201C", "#FF463630", "#FFF5E9E2", "#FFB49C91",
                 "#FFE07A5F", "#FFF2CC8F", "#FF81B29A", "#FFD64545"),
}
PALETTE_ORDER = sorted(PALETTES)

def axis_rod(mesh_id, p0, p1, ticks, tick_dir, rod=0.028, tick_len=0.1):
    """One axis rod with ticks, as a single mesh.

    `p0`/`p1` are the rod's ends; `ticks` are positions along the varying coordinate, and
    `tick_dir` says which coordinate that is ("x", "y" or "z"). One mesh per axis because a
    mesh takes a single paint and each axis wants its own colour.

    Third time this has been needed, so it lives here as a helper rather than being written
    out again - sets 1 and 2 each grew their own copy.
    """
    verts, normals, uv, idx = [], [], [], []
    lo = tuple(min(a, b) - (rod if a == b else 0) for a, b in zip(p0, p1))
    hi = tuple(max(a, b) + (rod if a == b else 0) for a, b in zip(p0, p1))
    mesh_box(verts, normals, uv, idx, lo, hi)
    for t in ticks:
        if tick_dir == "x":
            mesh_box(verts, normals, uv, idx,
                     (t - rod, lo[1] - tick_len, lo[2] - rod),
                     (t + rod, lo[1] + rod, lo[2] + rod))
        elif tick_dir == "z":
            mesh_box(verts, normals, uv, idx,
                     (lo[0] - tick_len, lo[1] - rod, t - rod),
                     (lo[0] + rod, lo[1] + rod, t + rod))
        else:
            mesh_box(verts, normals, uv, idx,
                     (lo[0] - tick_len, t - rod, lo[2] - rod),
                     (lo[0] + rod, t + rod, lo[2] + rod))
    return {"defineMesh3D": {"id": mesh_id, "verts": [round(v, 5) for v in verts],
                             "normals": normals, "uv": uv, "indices": idx}}


def draw_axes(cmds, rods, spin_var, colours):
    """Define and draw a set of axis rods under one rotation."""
    for (mesh_id, rod), colour in zip(rods, colours):
        cmds.append(rod)
    for (mesh_id, _), colour in zip(rods, colours):
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": spin_var, "axis": [0, 1, 0]}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mesh_id, "mode": "software-flat"}}]


INK = PANEL = RULE = TEXT = DIM = ACCENT = WARM = GOOD = HOT = ""
PALETTE_USED = {}


def use(doc_id):
    """Pick this document's palette, deterministically from its id."""
    global INK, PANEL, RULE, TEXT, DIM, ACCENT, WARM, GOOD, HOT
    h = int(hashlib.md5(doc_id.encode()).hexdigest(), 16)
    name = PALETTE_ORDER[h % len(PALETTE_ORDER)]
    PALETTE_USED[doc_id] = name
    (INK, PANEL, RULE, TEXT, DIM, ACCENT, WARM, GOOD, HOT) = PALETTES[name]
    return name


docs = {}


# ── 1. PHY-FPP-00008  Neutrinos — static-diagram / simulate / 2D ──────────────
# Oscillation: the three flavour probabilities as a function of distance over energy. A
# frozen plot rather than an animation, because the thing to see is that the three curves
# always sum to one, and that is easier to check when nothing is moving.
def neutrinos():
    W, H = 560, 360
    left, right, top, bottom = 60.0, 520.0, 90.0, 280.0
    cmds = []
    for p in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = bottom - p * (bottom - top)
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": left, "y1": y, "x2": right, "y2": y}})
        cmds += text_at("%.2f" % p, left - 8.0, y + 4.0, 9.0, DIM, pan_x=1.0)

    N = 150

    def probs(t):
        """A two-flavour-style oscillation, scaled so the three always sum to 1."""
        pm = math.sin(2.6 * t) ** 2 * 0.62
        pt = math.sin(1.7 * t + 0.6) ** 2 * 0.30
        return max(0.0, 1.0 - pm - pt), pm, pt

    for fi, (name, colour) in enumerate([("electron", ACCENT), ("muon", WARM),
                                         ("tau", GOOD)]):
        pid = "f%d" % fi
        pts = []
        for k in range(N):
            t = k / (N - 1) * 6.0
            y = probs(t)[fi]
            pts.append((round(left + k / (N - 1) * (right - left), 2),
                        round(bottom - y * (bottom - top), 2)))
        cmds.append({"pathCreate": {"id": pid, "x": pts[0][0], "y": pts[0][1]}})
        for px, py in pts[1:]:
            cmds.append({"pathAppendLineTo": {"path": pid, "x": px, "y": py}})
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.4}))
        cmds.append({"drawPath": {"path": pid}})
        cmds += text_at(name, left + 8.0 + fi * 96.0, 306.0, 11.5, colour)

    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.3}))
    cmds.append({"drawLine": {"x1": left, "y1": bottom, "x2": right, "y2": bottom}})
    cmds += text_at("distance / energy", left, 298.0, 10.0, DIM)
    cmds += text_at("probability of detecting each flavour", left, 332.0, 10.5, TEXT)
    cmds += text_at("the three always sum to one: a neutrino is never lost, only changed",
                    left, 348.0, 10.0, DIM)
    return {"header": header(W, H, "Neutrino flavour probabilities oscillating with distance "
                                   "over energy, always summing to one"),
            "root": canvas(title(cmds, W, H, "Neutrino oscillation",
                                 "three flavours, one particle"))}


use("PHY-FPP-00008")
docs["PHY-FPP-00008"] = neutrinos()


# ── 2. PHY-FPP-00009  Higgs field — annotated-layout / analyze / 3D ───────────
# The slot looked contradictory - layout containers are 2D - until you notice a card can
# hold a 3D canvas. So the layout carries the argument and one card carries the Mexican-hat
# potential, which is the only honest way to draw why the field has a non-zero value
# everywhere.
def higgs():
    W, H = 460, 520

    def potential(u, v):
        """V = -a r^2 + b r^4, the brim-and-dimple shape."""
        x, y = (u * 2 - 1), (v * 2 - 1)
        r2 = x * x + y * y
        return (-0.95 * r2 + 0.62 * r2 * r2) * 0.9

    hat = [{"clearDepth3D": {}},
           {"camera3D": {"projection": "perspective", "fovY": 0.95, "aspect": 1.6,
                         "near": 0.1, "far": 60.0,
                         "eye": [2.0, 2.0, 2.9], "center": [0, -0.05, 0], "up": [0, 1, 0]}},
           {"lights3D": {"lights": [
               {"type": "directional", "color": "#FFFFFFFF",
                "dir": [-0.4, -0.7, -0.6], "intensity": 1.0},
               {"type": "directional", "color": "#FF5B8CEE",
                "dir": [0.5, 0.2, 0.4], "intensity": 0.3}]}},
           surface_mesh(1, potential, 23, half=0.92, yscale=1.5, yoff=0.18)]
    hat.append(var("spin", "sin(continuousSec() * 0.28) * 0.6"))
    hat += [{"matrix3D": {"op": "identity"}},
            {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
            paint({"color": "#FF3E6FC4"}, {"style": "fill"}),
            {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}},
            paint({"color": "#FF9FC2F5"}, {"style": "stroke"}, {"width": 1.0}),
            {"drawMesh3D": {"mesh": 1, "mode": "software-smooth", "wireframe": True}}]

    # The two horizontal axes are the field's own components, and the vertical is the
    # potential. Without them "the brim is lower than the centre" is a claim about an
    # unlabelled surface.
    HB, HE = 0.52, 1.22
    draw_axes(hat, [
        (2, axis_rod(2, (-HE, HB, -HE), (HE, HB, -HE), [-0.5, 0.0, 0.5], "x")),
        (3, axis_rod(3, (-HE, HB, -HE), (-HE, HB, HE), [-0.5, 0.0, 0.5], "z")),
        (4, axis_rod(4, (-HE, HB - 0.95, -HE), (-HE, HB, -HE),
                     [HB - 0.3, HB - 0.6], "y")),
    ], "@spin", [WARM, GOOD, "#FFBFCBE4"])


    def note(head, body, colour):
        return {"type": "column",
                "modifiers": [{"width": 410}, {"padding": 12}, {"background": PANEL}],
                "children": [
                    {"type": "text", "value": head, "modifiers": [],
                     "fontSize": 13.5, "color": colour},
                    {"type": "spacer", "modifiers": [{"height": 5}]},
                    {"type": "text", "value": body, "modifiers": [],
                     "fontSize": 10.5, "color": DIM}]}

    return {
        "header": header(W, H, "The Higgs potential as a 3D surface inside a card layout, "
                               "with notes on why the field sits in the brim"),
        "root": {"type": "column",
                 "modifiers": ["fillMaxSize", {"background": INK}, {"padding": 18}],
                 "children": [
                     {"type": "text", "value": "The Higgs field", "modifiers": [],
                      "fontSize": 20.0, "color": TEXT},
                     {"type": "spacer", "modifiers": [{"height": 4}]},
                     {"type": "text", "value": "why its value is not zero",
                      "modifiers": [], "fontSize": 11.0, "color": DIM},
                     {"type": "spacer", "modifiers": [{"height": 12}]},
                     {"type": "canvas", "modifiers": [{"width": 410}, {"height": 250}],
                      "commands": hat},
                     {"type": "spacer", "modifiers": [{"height": 6}]},
                     {"type": "row", "modifiers": [{"width": 410}], "children": [
                         {"type": "text", "value": "field component 1", "modifiers": [],
                          "fontSize": 9.5, "color": WARM},
                         {"type": "spacer", "modifiers": [{"width": 16}]},
                         {"type": "text", "value": "component 2", "modifiers": [],
                          "fontSize": 9.5, "color": GOOD},
                         {"type": "spacer", "modifiers": [{"width": 16}]},
                         {"type": "text", "value": "potential V", "modifiers": [],
                          "fontSize": 9.5, "color": "#FFBFCBE4"}]},
                     {"type": "spacer", "modifiers": [{"height": 10}]},
                     note("The centre is a hill, not a valley",
                          "At zero field the potential is a local maximum. Nothing rests "
                          "there, so the field rolls off it.", WARM),
                     {"type": "spacer", "modifiers": [{"height": 8}]},
                     note("The brim is the ground state",
                          "Every point around the circle is equally low. The field takes one "
                          "of them, and that choice breaks the symmetry.", GOOD),
                     {"type": "spacer", "modifiers": [{"height": 8}]},
                     note("Mass is the cost of moving through it",
                          "Particles that interact strongly with the occupied field are the "
                          "heavy ones. The photon does not interact, and has no mass.",
                          ACCENT),
                 ]},
    }


use("PHY-FPP-00009")
docs["PHY-FPP-00009"] = higgs()


# ── 3. PHY-AP-00010  Atomic structure — data-plot / explain / 2D ──────────────
# Ionization energy against atomic number. The sawtooth is the explanation: every drop is a
# new shell starting, every peak is a full one.
IONIZATION = [13.6, 24.6, 5.4, 9.3, 8.3, 11.3, 14.5, 13.6, 17.4, 21.6,
              5.1, 7.6, 6.0, 8.2, 10.5, 10.4, 13.0, 15.8, 4.3, 6.1]
NOBLE = {2, 10, 18}
ALKALI = {3, 11, 19}


def ionization():
    W, H = 580, 360
    left, right, top, bottom = 56.0, 548.0, 86.0, 286.0
    cmds = []
    for e in (0, 5, 10, 15, 20, 25):
        y = bottom - e / 25.0 * (bottom - top)
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": left, "y1": y, "x2": right, "y2": y}})
        cmds += text_at(str(e), left - 8.0, y + 4.0, 9.0, DIM, pan_x=1.0)

    n = len(IONIZATION)
    cmds.append(var("step", "%.4f" % ((right - left) / (n - 1))))
    cmds.append({"loop": {"index": "i", "from": 0.0, "until": float(n), "step": 1.0,
                          "commands": [
        var("e", "arrayGet(@ion, @i)"),
        var("px", "%.1f + @i * @step" % left),
        var("py", "%.1f - @e / 25.0 * %.1f" % (bottom, bottom - top)),
        paint({"color": ACCENT}, {"style": "stroke"}, {"width": 1.5}),
        {"drawLine": {"x1": "@px", "y1": bottom, "x2": "@px", "y2": "@py"}},
        paint({"color": ACCENT}, {"style": "fill"}),
        {"drawCircle": {"cx": "@px", "cy": "@py", "radius": 3.6}},
    ]}})

    for z in range(1, n + 1):
        px = left + (z - 1) * (right - left) / (n - 1)
        py = bottom - IONIZATION[z - 1] / 25.0 * (bottom - top)
        if z in NOBLE:
            cmds.append(paint({"color": GOOD}, {"style": "fill"}))
            cmds.append({"drawCircle": {"cx": px, "cy": py, "radius": 5.5}})
            cmds += text_at("full shell", px, py - 14.0, 9.0, GOOD, pan_x=0.0)
        if z in ALKALI:
            cmds.append(paint({"color": WARM}, {"style": "fill"}))
            cmds.append({"drawCircle": {"cx": px, "cy": py, "radius": 5.5}})
            cmds += text_at("new shell", px, py + 20.0, 9.0, WARM, pan_x=0.0)
        if z % 2 == 1:
            cmds += text_at(str(z), px, bottom + 16.0, 8.5, DIM, pan_x=0.0)

    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.3}))
    cmds.append({"drawLine": {"x1": left, "y1": bottom, "x2": right, "y2": bottom}})
    cmds += text_at("atomic number", left, bottom + 36.0, 10.0, DIM)
    cmds += text_at("first ionization energy, eV", left, 328.0, 10.5, TEXT)
    cmds += text_at("peaks are full shells, troughs are the next shell starting",
                    left, 346.0, 10.0, DIM)
    return {"header": header(W, H, "First ionization energy against atomic number, with the "
                                   "shell structure marked on the sawtooth"),
            "resources": {"floatArrays": [{"ion": IONIZATION}]},
            "root": canvas(title(cmds, W, H, "Ionization energy",
                                 "the sawtooth is the shell structure"))}


use("PHY-AP-00010")
docs["PHY-AP-00010"] = ionization()


# ── 4. PHY-AP-00011  Electron orbitals — path-form / explore / 2D ─────────────
# Orbital cross-sections as closed paths. The shapes are the content, so they are real
# outlines rather than circles standing in for them.
def orbitals():
    W, H = 540, 380
    cmds = []
    panels = [("s", 90.0, 200.0, ACCENT), ("p", 250.0, 200.0, WARM),
              ("d", 420.0, 200.0, GOOD)]

    def lobe_path(pid, cx, cy, fn, n=90, scale=58.0):
        pts = []
        for k in range(n + 1):
            th = k / n * 2 * math.pi
            r = fn(th) * scale
            pts.append((round(cx + r * math.cos(th), 2), round(cy + r * math.sin(th), 2)))
        out = [{"pathCreate": {"id": pid, "x": pts[0][0], "y": pts[0][1]}}]
        for px, py in pts[1:]:
            out.append({"pathAppendLineTo": {"path": pid, "x": px, "y": py}})
        out.append({"pathAppendClose": {"path": pid}})
        return out

    shapes = {
        "s": lambda th: 1.0,
        "p": lambda th: abs(math.cos(th)) ** 0.7,
        "d": lambda th: abs(math.cos(2 * th)) ** 0.6,
    }
    for name, cx, cy, colour in panels:
        cmds += lobe_path("orb%s" % name, cx, cy, shapes[name])
        cmds.append(paint({"color": colour}, {"style": "fill"}, {"alpha": 0.28}))
        cmds.append({"drawPath": {"path": "orb%s" % name}})
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.2}))
        cmds.append({"drawPath": {"path": "orb%s" % name}})
        cmds.append(paint({"color": TEXT}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": cx, "cy": cy, "radius": 3.5}})
        cmds += text_at("%s orbital" % name, cx, 300.0, 14.0, colour, pan_x=0.0)
        lobes = {"s": "1 lobe", "p": "2 lobes", "d": "4 lobes"}[name]
        cmds += text_at(lobes, cx, 318.0, 10.0, DIM, pan_x=0.0)

    cmds += text_at("cross-sections through the nucleus; the dot is the nucleus",
                    24.0, 348.0, 10.5, TEXT)
    cmds += text_at("each outline is a closed path, not an approximation by circles",
                    24.0, 366.0, 10.0, DIM)
    return {"header": header(W, H, "s, p and d orbital cross-sections drawn as closed paths"),
            "root": canvas(title(cmds, W, H, "Electron orbitals", "shape, not position"))}


use("PHY-AP-00011")
docs["PHY-AP-00011"] = orbitals()


# ── 5. BIO-CB-00009  Cell membrane — expression-animation / compare / 2D ──────
# Two panels on one clock: passive transport drifts down the gradient, active transport is
# pumped against it. Running both from the same time makes the comparison exact.
def membrane():
    W, H = 540, 400
    cmds = []
    cmds.append(var("t", "continuousSec()"))
    for pi, (name, colour, x0, uphill) in enumerate(
            [("Passive", GOOD, 40.0, False), ("Active", WARM, 290.0, True)]):
        w = 210.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": 92.0,
                                  "right": x0 + w, "bottom": 316.0}})
        # the bilayer, two rows of heads
        for row, yy in ((0, 186.0), (1, 214.0)):
            for k in range(int(w // 12)):
                cmds.append(paint({"color": "#FF46608E"}, {"style": "fill"}))
                cmds.append({"drawCircle": {"cx": x0 + 7 + k * 12, "cy": yy,
                                            "radius": 4.6}})
        cmds.append(paint({"color": "#FF2A3C60"}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": 190.0,
                                  "right": x0 + w, "bottom": 210.0}})

        # molecules: passive ones fall, active ones are pushed up and reset
        for k in range(7):
            ph = k * 0.9
            if uphill:
                ypos = "316 - ((@t * 34 + %.1f) %% 224)" % (k * 32)
            else:
                ypos = "92 + ((@t * 30 + %.1f) %% 224)" % (k * 32)
            cmds.append(paint({"color": colour}, {"style": "fill"}))
            cmds.append({"drawCircle": {
                "cx": "%.1f + sin(@t * 1.3 + %.2f) * 14" % (x0 + 30 + k * 25, ph),
                "cy": ypos, "radius": 6.0}})

        cmds += text_at(name, x0 + w / 2, 84.0, 13.0, colour, pan_x=0.0)
        cmds += text_at("high concentration" if not uphill else "low concentration",
                        x0 + w / 2, 110.0, 9.0, DIM, pan_x=0.0)
        cmds += text_at("low" if not uphill else "high",
                        x0 + w / 2, 306.0, 9.0, DIM, pan_x=0.0)
        cmds += text_at("down the gradient, free" if not uphill
                        else "against it, costs ATP", x0 + w / 2, 336.0, 10.0,
                        colour, pan_x=0.0)
        if uphill:
            cmds.append(paint({"color": HOT}, {"style": "fill"}))
            cmds.append({"drawRoundRect": {"left": x0 + w / 2 - 22, "top": 184.0,
                                           "right": x0 + w / 2 + 22, "bottom": 216.0,
                                           "rx": 6.0, "ry": 6.0}})
            cmds += text_at("pump", x0 + w / 2, 204.0, 9.5, INK, pan_x=0.0)
    cmds += text_at("both panels run from the same clock, so the rates are comparable",
                    40.0, 376.0, 10.0, DIM)
    return {"header": header(W, H, "Passive and active transport across a membrane, side by "
                                   "side on one clock"),
            "root": canvas(title(cmds, W, H, "Crossing the membrane",
                                 "with the gradient, and against it"))}


use("BIO-CB-00009")
docs["BIO-CB-00009"] = membrane()


# ── 6. BIO-CB-00010  Mitosis — particle-system / demonstrate / 2D ─────────────
# Chromosomes as particles, and the phase is the clock. Position encodes the stage: they
# line up at the plate, then separate to the poles, which is the whole of mitosis.
def mitosis():
    W, H = 520, 380
    cx, cy = 260.0, 210.0
    cmds = []
    cmds.append(var("ph", "(continuousSec() * 0.35) % 4"))
    # 0-1 prophase, 1-2 metaphase, 2-3 anaphase, 3-4 telophase
    cmds.append(var("align", "clamp(0.0, 1.0, @ph)"))
    cmds.append(var("sep", "clamp(0.0, 1.0, @ph - 2)"))

    cmds.append(paint({"color": "#FF1A2540"}, {"style": "fill"}))
    cmds.append({"drawOval": {"left": cx - 190.0, "top": cy - 116.0,
                              "right": cx + 190.0, "bottom": cy + 116.0}})
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.2}))
    cmds.append({"drawLine": {"x1": cx, "y1": cy - 104.0, "x2": cx, "y2": cy + 104.0}})
    cmds += text_at("metaphase plate", cx, cy - 116.0, 9.5, DIM, pan_x=0.0)

    cmds.append({"createParticles": {
        "id": "chr",
        "variables": ["sx", "sy", "side", "ph"],
        "initialValues": ["%.1f + rand() * 300" % (cx - 150), "%.1f + rand() * 180" % (cy - 90),
                          "ifElse(-1, 1, rand() - 0.5)", "rand() * 6.283"],
        "count": 16}})
    cmds.append({"particlesLoop": {
        "system": "@chr",
        "equations": ["sx", "sy", "side", "ph"],
        "commands": [
            paint({"color": ACCENT}, {"style": "fill"}),
            {"drawRoundRect": {
                # scattered -> aligned on the plate -> pulled to the poles
                "left": "sx * (1 - @align) + (%.1f + side * @sep * 150) * @align - 5" % cx,
                "top": "sy * (1 - @align) + (%.1f + (ph - 3.14) * 26) * @align - 14" % cy,
                "right": "sx * (1 - @align) + (%.1f + side * @sep * 150) * @align + 5" % cx,
                "bottom": "sy * (1 - @align) + (%.1f + (ph - 3.14) * 26) * @align + 14" % cy,
                "rx": 4.0, "ry": 4.0}}]}})

    labels = [("prophase", 0), ("metaphase", 1), ("anaphase", 2), ("telophase", 3)]
    for name, k in labels:
        x = 60.0 + k * 118.0
        cmds += text_at(name, x, 344.0, 11.0, DIM)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 2.0}))
    cmds.append({"drawLine": {"x1": 56.0, "y1": 354.0, "x2": 470.0, "y2": 354.0}})
    cmds.append(paint({"color": WARM}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": "56 + @ph / 4 * 414", "cy": 354.0, "radius": 6.0}})
    cmds += text_at("16 chromosomes, one clock, four phases", 56.0, 374.0, 10.0, DIM)
    return {"header": header(W, H, "Chromosomes aligning on the metaphase plate then "
                                   "separating to the poles, as a particle system"),
            "root": canvas(title(cmds, W, H, "Mitosis", "line up, then pull apart"))}


use("BIO-CB-00010")
docs["BIO-CB-00010"] = mitosis()


# ── 7. BIO-CB-00011  Meiosis — interactive / simulate / 3D ────────────────────
# Drag to step through the divisions. 3D because the two divisions are easier to keep
# straight when the daughter cells occupy space rather than overlapping on a plane.
def meiosis():
    W, H = 480, 480
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.95, "aspect": 1.0,
                          "near": 0.1, "far": 60.0,
                          "eye": [0.5, 1.5, 3.6], "center": [0, 0, 0], "up": [0, 1, 0]}},
            {"lights3D": {"lights": [{"type": "directional", "color": "#FFFFFFFF",
                                      "dir": [-0.35, -0.6, -0.72], "intensity": 1.0}]}}]
    # Default mid-way through the first division rather than at zero: at stage 0 all four
    # cells are concentric and the still preview shows a single ball, which is the wrong
    # first impression for a document whose subject is dividing.
    cmds.append({"touchExpression": {"name": "stage", "defaultValue": 0.42,
                                     "min": 0.0, "max": 1.0, "stopMode": "gently",
                                     "expression": "touchX() / 480"}})
    cmds.append(var("s", "clamp(0.0, 1.0, @stage)"))
    # first division splits left/right, second splits each up/down
    cmds.append(var("d1", "clamp(0.0, 1.0, @s * 2)"))
    cmds.append(var("d2", "clamp(0.0, 1.0, @s * 2 - 1)"))

    for i, (sx, sy) in enumerate([(-1, -1), (-1, 1), (1, -1), (1, 1)]):
        cmds += [{"meshPrimitive3D": {"id": 10 + i, "primitive": "sphere", "segments": 20,
                                      "radius": 0.44, "center": [0, 0, 0]}},
                 {"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "translate",
                               "x": "%d * @d1 * 0.72" % sx,
                               "y": "%d * @d2 * 0.66" % sy,
                               "z": 0}},
                 paint({"color": [ACCENT, GOOD, WARM, HOT][i]}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": 10 + i, "mode": "software-smooth"}}]

    cmds += text_at("drag across to run the two divisions", 24.0, 372.0, 11.0, TEXT)
    cmds += text_at("meiosis I separates homologues", 24.0, 392.0, 10.0, ACCENT)
    cmds += text_at("meiosis II separates sister chromatids", 24.0, 408.0, 10.0, GOOD)
    cmds += text_at("one diploid cell becomes four haploid ones", 24.0, 424.0, 10.0, DIM)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 2.0}))
    cmds.append({"drawLine": {"x1": 24.0, "y1": 448.0, "x2": 456.0, "y2": 448.0}})
    cmds.append(paint({"color": TEXT}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": "24 + @s * 432", "cy": 448.0, "radius": 7.0}})
    cmds += text_at("I", 240.0, 466.0, 10.0, ACCENT, pan_x=1.0)
    cmds += text_at("II", 456.0, 466.0, 10.0, GOOD, pan_x=1.0)
    return {"header": header(W, H, "Drag to run meiosis: one cell dividing twice into four "
                                   "haploid daughters, in 3D"),
            "root": canvas(title(cmds, W, H, "Meiosis", "two divisions, four cells"))}


use("BIO-CB-00011")
docs["BIO-CB-00011"] = meiosis()


# ── 8. BIO-CB-00012  Cell signaling — raster-and-text / analyze / 2D ──────────
# A cascade is a numbers argument: each step multiplies. Set as a table so the
# amplification is readable rather than implied by arrow thickness.
CASCADE = [("Hormone binds receptor", 1, "1 molecule"),
           ("G protein activated", 10, "10"),
           ("Adenylyl cyclase", 100, "100"),
           ("cAMP produced", 10000, "10 thousand"),
           ("Protein kinase A", 100000, "100 thousand"),
           ("Target enzymes", 10000000, "10 million")]


def signaling():
    W, H = 560, 400
    cmds = []
    cmds += text_at("STEP", 26.0, 96.0, 9.5, DIM)
    cmds += text_at("MOLECULES", 420.0, 96.0, 9.5, DIM, pan_x=1.0)
    cmds += text_at("AMPLIFICATION", 544.0, 96.0, 9.5, DIM, pan_x=1.0)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": 26.0, "y1": 104.0, "x2": 544.0, "y2": 104.0}})

    prev = 1
    for i, (name, count, label) in enumerate(CASCADE):
        y = 134.0 + i * 42.0
        size = 11.0 + math.log10(max(count, 1)) * 1.3
        cmds += text_at(name, 26.0, y, size, TEXT)
        cmds += text_at(label, 420.0, y, 12.5, WARM, pan_x=1.0)
        if i:
            cmds += text_at("x%d" % (count // prev), 544.0, y, 12.0, GOOD, pan_x=1.0)
        prev = count
        # a bar whose length is log of the count, so the growth is visible as well as stated
        cmds.append(paint({"color": ACCENT}, {"style": "fill"}, {"alpha": 0.55}))
        cmds.append({"drawRect": {"left": 26.0, "top": y + 6.0,
                                  "right": 26.0 + math.log10(max(count, 1)) * 56.0 + 3.0,
                                  "bottom": y + 10.0}})
        if i < len(CASCADE) - 1:
            cmds.append(paint({"color": "#FF1B2740"}, {"style": "stroke"}, {"width": 1.0}))
            cmds.append({"drawLine": {"x1": 26.0, "y1": y + 20.0,
                                      "x2": 544.0, "y2": y + 20.0}})
    cmds += text_at("one hormone molecule ends up moving ten million enzymes",
                    26.0, 380.0, 11.0, TEXT)
    return {"header": header(W, H, "A signalling cascade as a table, with the amplification "
                                   "at each step stated as a multiplier"),
            "root": canvas(title(cmds, W, H, "Signal amplification",
                                 "one molecule in, ten million out"))}


use("BIO-CB-00012")
docs["BIO-CB-00012"] = signaling()


# ── 9. MTH-AN-00003  Prime numbers — static-diagram / analyze / 3D ────────────
# Primes laid on a grid and raised into towers. Flat, the pattern is a scatter of dots; as
# height over the grid the diagonal striping that an Ulam spiral is famous for shows up as
# ridges you can look along.
def primes():
    W, H = 500, 460
    N = 24

    def is_prime(k):
        if k < 2:
            return False
        for d in range(2, int(k ** 0.5) + 1):
            if k % d == 0:
                return False
        return True

    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.9, "aspect": 1.0,
                          "near": 0.1, "far": 80.0,
                          "eye": [2.4, 2.6, 2.8], "center": [0, -0.2, 0], "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.4, -0.75, -0.5], "intensity": 1.0},
                {"type": "directional", "color": "#FF4FD6C9",
                 "dir": [0.55, 0.2, 0.45], "intensity": 0.28}]}}]

    verts, normals, uv, idx = [], [], [], []
    count = 0
    for r in range(N):
        for c in range(N):
            k = r * N + c + 1
            if not is_prime(k):
                continue
            count += 1
            x = -1.0 + c / (N - 1) * 2.0
            z = -1.0 + r / (N - 1) * 2.0
            hgt = 0.10 + 0.14 * (k / (N * N)) ** 0.4
            s = 0.028
            mesh_box(verts, normals, uv, idx,
                     (x - s, -0.62, z - s), (x + s, -0.62 + hgt, z + s))
    cmds.append({"defineMesh3D": {"id": 1, "verts": [round(v, 5) for v in verts],
                                  "normals": normals, "uv": uv, "indices": idx}})
    cmds.append(var("spin", "sin(continuousSec() * 0.22) * 0.55"))
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": "#FF6FB2F0"}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]

    # Column and row are the axes that carry the pattern; the tower height is just the
    # number itself, so it gets a rod too rather than being left unexplained.
    BASE, EDGE = -0.62, 1.12
    col_ticks = [-1.0 + (c - 1) / (N - 1) * 2.0 for c in (1, 6, 12, 18, 24)]
    row_ticks = [-1.0 + (r - 1) / (N - 1) * 2.0 for r in (1, 6, 12, 18, 24)]
    draw_axes(cmds, [
        (2, axis_rod(2, (-EDGE, BASE, -EDGE), (EDGE, BASE, -EDGE), col_ticks, "x")),
        (3, axis_rod(3, (-EDGE, BASE, -EDGE), (-EDGE, BASE, EDGE), row_ticks, "z")),
        (4, axis_rod(4, (-EDGE, BASE, -EDGE), (-EDGE, BASE + 0.34, -EDGE),
                     [BASE + 0.12, BASE + 0.24], "y")),
    ], "@spin", [WARM, GOOD, "#FFBFCBE4"])

    cmds += text_at("column", 20.0, 362.0, 11.0, WARM)
    cmds += text_at("row", 96.0, 362.0, 11.0, GOOD)
    cmds += text_at("n", 148.0, 362.0, 11.0, "#FFBFCBE4")
    cmds += text_at("%d primes below %d, on a %d by %d grid" % (count, N * N, N, N),
                    20.0, 384.0, 11.0, TEXT)
    cmds += text_at("rows of 24, so the gaps fall into diagonal lanes",
                    20.0, 402.0, 10.0, DIM)
    cmds += text_at("every even column after 2 is empty, and so is every third",
                    20.0, 418.0, 10.0, DIM)
    cmds += text_at("one mesh, %d towers" % count, 20.0, 436.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "Primes below 576 as towers on a 24 by 24 grid, where the "
                                   "gaps form diagonal lanes"),
            "root": canvas(title(cmds, W, H, "Primes on a grid", "where the gaps line up"))}


use("MTH-AN-00003")
docs["MTH-AN-00003"] = primes()


# ── 10. CSC-ALGO-00003  Recursion — annotated-layout / explain / 2D ───────────
# The containers ARE the recursion: each call is a box holding the next call, nested as
# deeply as the recursion goes. The layout engine does the drawing that a tree diagram
# would otherwise have to fake.
def recursion():
    W, H = 520, 440

    def frame(n, depth):
        colour = ["#FF1E2C4A", "#FF24355A", "#FF2A3F6A", "#FF31497A",
                  "#FF385380"][min(depth, 4)]
        inner = ([{"type": "text", "value": "return 1", "modifiers": [],
                   "fontSize": 11.0, "color": GOOD}] if n <= 1 else
                 [{"type": "text", "value": "%d x factorial(%d)" % (n, n - 1),
                   "modifiers": [], "fontSize": 10.5, "color": DIM},
                  {"type": "spacer", "modifiers": [{"height": 6}]},
                  frame(n - 1, depth + 1)])
        return {"type": "column",
                "modifiers": [{"padding": 10}, {"background": colour}],
                "children": [
                    {"type": "text", "value": "factorial(%d)" % n, "modifiers": [],
                     "fontSize": 12.5, "color": TEXT},
                    {"type": "spacer", "modifiers": [{"height": 5}]},
                ] + inner}

    return {
        "header": header(W, H, "A recursive factorial drawn as nested layout boxes, one box "
                               "per call frame"),
        "root": {"type": "column",
                 "modifiers": ["fillMaxSize", {"background": INK}, {"padding": 18}],
                 "children": [
                     {"type": "text", "value": "Recursion", "modifiers": [],
                      "fontSize": 20.0, "color": TEXT},
                     {"type": "spacer", "modifiers": [{"height": 4}]},
                     {"type": "text",
                      "value": "each box is a call waiting for the one inside it",
                      "modifiers": [], "fontSize": 11.0, "color": DIM},
                     {"type": "spacer", "modifiers": [{"height": 14}]},
                     frame(5, 0),
                     {"type": "spacer", "modifiers": [{"height": 12}]},
                     {"type": "text",
                      "value": "the innermost box returns first; every box outside it is "
                               "still on the stack",
                      "modifiers": [], "fontSize": 10.0, "color": "#FF5E6E95"},
                 ]},
    }


use("CSC-ALGO-00003")
docs["CSC-ALGO-00003"] = recursion()


# ── 11. CHM-AC-00003  Electron configuration — data-plot / explore / 2D ───────
# Subshell energies in filling order, from an array. The crossings are the interesting part:
# 4s fills before 3d, which is why the transition metals sit where they do.
SUBSHELLS = [("1s", 2, 1.0), ("2s", 2, 2.0), ("2p", 6, 2.3), ("3s", 2, 3.0),
             ("3p", 6, 3.3), ("4s", 2, 3.7), ("3d", 10, 4.0), ("4p", 6, 4.3),
             ("5s", 2, 4.7), ("4d", 10, 5.0), ("5p", 6, 5.3), ("6s", 2, 5.7)]


def configuration():
    W, H = 560, 380
    caps = [float(c) for _, c, _ in SUBSHELLS]
    energies = [e for _, _, e in SUBSHELLS]
    left, right, top, bottom = 60.0, 530.0, 90.0, 290.0
    cmds = []
    for e in (1, 2, 3, 4, 5, 6):
        y = bottom - (e - 1) / 5.0 * (bottom - top)
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": left, "y1": y, "x2": right, "y2": y}})
        cmds += text_at("n=%d" % e, left - 8.0, y + 4.0, 9.0, DIM, pan_x=1.0)

    n = len(SUBSHELLS)
    cmds.append(var("step", "%.4f" % ((right - left) / n)))
    cmds.append({"loop": {"index": "i", "from": 0.0, "until": float(n), "step": 1.0,
                          "commands": [
        var("cap", "arrayGet(@caps, @i)"),
        var("en", "arrayGet(@energy, @i)"),
        var("px", "%.1f + (@i + 0.5) * @step" % left),
        var("py", "%.1f - (@en - 1) / 5.0 * %.1f" % (bottom, bottom - top)),
        paint({"color": ACCENT}, {"style": "fill"}, {"alpha": "0.35 + @cap / 14"}),
        {"drawRoundRect": {"left": "@px - @cap * 1.6", "top": "@py - 9",
                           "right": "@px + @cap * 1.6", "bottom": "@py + 9",
                           "rx": 5.0, "ry": 5.0}},
    ]}})

    for i, (name, cap, en) in enumerate(SUBSHELLS):
        px = left + (i + 0.5) * (right - left) / n
        py = bottom - (en - 1) / 5.0 * (bottom - top)
        cmds += text_at(name, px, py + 4.0, 10.0, TEXT, pan_x=0.0)
        cmds += text_at(str(cap), px, bottom + 18.0, 9.5, DIM, pan_x=0.0)
        if name in ("4s", "3d"):
            cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 1.6}))
            cmds.append({"drawCircle": {"cx": px, "cy": py, "radius": 19.0}})
    cmds += text_at("filling order, left to right", left, bottom + 40.0, 10.0, DIM)
    cmds += text_at("electrons each", left, bottom + 18.0, 9.5, DIM, pan_x=1.0)
    cmds += text_at("4s fills before 3d even though its shell number is higher",
                    left, 342.0, 11.0, WARM)
    cmds += text_at("that crossing is why the transition metals start at scandium",
                    left, 360.0, 10.0, DIM)
    return {"header": header(W, H, "Subshells in filling order against energy level, with the "
                                   "4s and 3d crossing marked"),
            "resources": {"floatArrays": [{"caps": caps}, {"energy": energies}]},
            "root": canvas(title(cmds, W, H, "Electron configuration",
                                 "why 4s comes before 3d"))}


use("CHM-AC-00003")
docs["CHM-AC-00003"] = configuration()


# ── 12. EAR-GEOL-00003  Volcanoes — path-form / compare / 2D ──────────────────
# Three profiles at one scale, as paths. Volcano shape is the comparison - a shield is
# nothing like a cinder cone - and it only reads if they share a baseline and a scale bar.
def volcanoes():
    W, H = 560, 380
    base = 290.0
    cmds = []
    kinds = [("Shield", 230.0, 44.0, 0.9, GOOD, 70.0),
             ("Stratovolcano", 150.0, 120.0, 2.1, WARM, 290.0),
             ("Cinder cone", 70.0, 76.0, 3.4, HOT, 470.0)]
    for name, halfw, hgt, steep, colour, cx in kinds:
        pid = "v%s" % name[:3]
        pts = []
        n = 60
        for k in range(n + 1):
            u = -1.0 + 2.0 * k / n
            y = base - hgt * (1.0 - abs(u) ** steep)
            pts.append((round(cx + u * halfw, 2), round(y, 2)))
        cmds.append({"pathCreate": {"id": pid, "x": pts[0][0], "y": pts[0][1]}})
        for px, py in pts[1:]:
            cmds.append({"pathAppendLineTo": {"path": pid, "x": px, "y": py}})
        cmds.append({"pathAppendClose": {"path": pid}})
        cmds.append(paint({"color": colour}, {"style": "fill"}, {"alpha": 0.5}))
        cmds.append({"drawPath": {"path": pid}})
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.0}))
        cmds.append({"drawPath": {"path": pid}})
        cmds += text_at(name, cx, base + 22.0, 12.0, colour, pan_x=0.0)
        cmds += text_at("%.0f km across" % (halfw / 10.0), cx, base + 38.0, 9.5,
                        DIM, pan_x=0.0)

    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.4}))
    cmds.append({"drawLine": {"x1": 24.0, "y1": base, "x2": 540.0, "y2": base}})
    # a shared scale bar, without which the three outlines mean nothing
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 2.0}))
    cmds.append({"drawLine": {"x1": 24.0, "y1": 338.0, "x2": 124.0, "y2": 338.0}})
    for x in (24.0, 124.0):
        cmds.append({"drawLine": {"x1": x, "y1": 332.0, "x2": x, "y2": 344.0}})
    cmds += text_at("10 km", 74.0, 356.0, 10.0, TEXT, pan_x=0.0)
    cmds += text_at("same scale, same baseline: the shapes are the comparison",
                    150.0, 356.0, 10.5, DIM)
    return {"header": header(W, H, "Shield, strato and cinder cone profiles as filled paths "
                                   "at one shared scale"),
            "root": canvas(title(cmds, W, H, "Volcano profiles", "three shapes, one scale"))}


use("EAR-GEOL-00003")
docs["EAR-GEOL-00003"] = volcanoes()


# ── 13. ENG-ME-00003  Linkages — expression-animation / demonstrate / 2D ──────
# A slider-crank: rotation in, straight-line motion out. The whole demonstration is that the
# slider's travel is NOT sinusoidal, so the piston position is computed exactly rather than
# faked with a sine.
def linkage():
    W, H = 540, 340
    ox, oy = 150.0, 190.0
    crank, rod = 56.0, 150.0
    cmds = []
    cmds.append(var("a", "continuousSec() * 1.5"))
    cmds.append(var("px", "%.1f + cos(@a) * %.1f" % (ox, crank)))
    cmds.append(var("py", "%.1f + sin(@a) * %.1f" % (oy, crank)))
    # exact slider position: x = r cos + sqrt(l^2 - (r sin)^2)
    cmds.append(var("sx", "@px + sqrt(%.1f - (@py - %.1f) * (@py - %.1f))"
                    % (rod * rod, oy, oy)))

    cmds.append(paint({"color": "#FF1A2540"}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": 300.0, "top": oy - 34.0,
                              "right": 500.0, "bottom": oy + 34.0}})
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": ox, "y1": oy, "x2": 500.0, "y2": oy}})

    cmds.append(paint({"color": GOOD}, {"style": "stroke"}, {"width": 5.0},
                      {"strokeCap": "round"}))
    cmds.append({"drawLine": {"x1": ox, "y1": oy, "x2": "@px", "y2": "@py"}})
    cmds.append(paint({"color": ACCENT}, {"style": "stroke"}, {"width": 4.0},
                      {"strokeCap": "round"}))
    cmds.append({"drawLine": {"x1": "@px", "y1": "@py", "x2": "@sx", "y2": oy}})

    cmds.append(paint({"color": WARM}, {"style": "fill"}))
    cmds.append({"drawRoundRect": {"left": "@sx - 26", "top": oy - 22.0,
                                   "right": "@sx + 26", "bottom": oy + 22.0,
                                   "rx": 5.0, "ry": 5.0}})
    for x, y, r, col in ((ox, oy, 7.0, TEXT),):
        cmds.append(paint({"color": col}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": x, "cy": y, "radius": r}})
    cmds.append(paint({"color": GOOD}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": "@px", "cy": "@py", "radius": 6.0}})

    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawCircle": {"cx": ox, "cy": oy, "radius": crank}})
    cmds += text_at("crank", ox, oy + crank + 22.0, 10.5, GOOD, pan_x=0.0)
    cmds += text_at("connecting rod", 250.0, 136.0, 10.5, ACCENT)
    cmds += text_at("slider", 400.0, oy + 46.0, 10.5, WARM, pan_x=0.0)
    cmds += text_at("rotation in, straight-line motion out", 24.0, 290.0, 11.0, TEXT)
    cmds += text_at("the slider's travel is not a sine wave: it is computed exactly from "
                    "the rod length", 24.0, 308.0, 10.0, DIM)
    cmds += text_at("which is why a piston spends longer at the far end than the near one",
                    24.0, 324.0, 10.0, "#FF5E6E95")
    return {"header": header(W, H, "A slider-crank linkage turning rotation into "
                                   "straight-line motion, computed exactly"),
            "root": canvas(title(cmds, W, H, "Slider-crank", "the piston mechanism"))}


use("ENG-ME-00003")
docs["ENG-ME-00003"] = linkage()


# ── 14. FIN-MARK-00001  Stocks — particle-system / simulate / 3D ──────────────
# Particles draw with 2D commands, so a 3D scatter means projecting inside the draw
# expression: each particle holds its own x, y, z and the projection is arithmetic on them.
#
# Dragging rotates the view, which means rotating every point about the vertical axis BEFORE
# projecting it. Expanding that inline per particle would blow the 32-token budget, so the
# four trigonometric combinations are computed once as document variables and the particle
# expressions just multiply by them - the same trick as hoisting a loop invariant.
#
#   x' = (x-c)cos + (z-c)sin        screen x = CX + K[(x-c)(cos+sin) + (z-c)(sin-cos)]
#   z' = (z-c)cos - (x-c)sin        screen y = CY - KY(y-c) + KZ[(x-c)(cos-sin) + (z-c)(sin+cos)]
#
# The wireframe box is rotated by the same angle through matrix3D, so box and points turn
# together. They are not pixel-exact - the box goes through the engine's perspective camera
# while the points use this flat projection - but they agree closely enough to read as one
# scene, and making them exact would need a perspective divide per particle.
def stocks():
    W, H = 500, 480
    CX, CY, K, KY, KZ = 250.0, 250.0, 120.0, 150.0, 46.0
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.9, "aspect": 1.0,
                          "near": 0.1, "far": 60.0,
                          "eye": [2.3, 1.9, 2.6], "center": [0, 0, 0], "up": [0, 1, 0]}},
            {"lights3D": {"lights": [{"type": "directional", "color": "#FFFFFFFF",
                                      "dir": [-0.4, -0.6, -0.7], "intensity": 1.0}]}}]

    # `min` omitted so the scatter keeps turning instead of stopping at +-6 radians. The
    # max becomes exactly one turn: the value wraps there, and here the value IS the angle
    # in radians, so 6.0 would have wrapped 16 degrees short of a full turn and shown it.
    cmds.append({"touchExpression": {"name": "drag", "defaultValue": 0.6,
                                     "max": 2 * math.pi, "stopMode": "gently",
                                     "expression": "touchX() / 90"}})
    cmds.append(var("rot", "@drag"))
    cmds.append(var("ca", "cos(@rot)"))
    cmds.append(var("sa", "sin(@rot)"))
    cmds.append(var("cp", "@ca + @sa"))
    cmds.append(var("cm", "@sa - @ca"))
    cmds.append(var("dp", "@ca - @sa"))
    cmds.append(var("dm", "@sa + @ca"))

    cmds.append({"createParticles": {
        "id": "px",
        "variables": ["rx", "ry", "rz", "sz"],
        "initialValues": ["rand()", "rand()", "rand()", "2.5 + rand() * 6.0"],
        "count": 90}})
    cmds.append({"particlesLoop": {
        "system": "@px",
        "equations": ["rx", "ry", "rz", "sz"],
        "commands": [
            paint({"color": GOOD}, {"style": "fill"},
                  {"alpha": "clamp(0.25, 0.95, ry)"}),
            {"drawCircle": {
                "cx": "%.1f + ((rx - 0.5) * @cp + (rz - 0.5) * @cm) * %.1f" % (CX, K),
                "cy": "%.1f - (ry - 0.5) * %.1f + ((rx - 0.5) * @dp + (rz - 0.5) * @dm) * %.1f"
                      % (CY, KY, KZ),
                "radius": "sz"}}]}})

    verts, normals, uv, idx = [], [], [], []
    mesh_box(verts, normals, uv, idx, (-1.0, -1.0, -1.0), (1.0, 1.0, 1.0))
    cmds.append({"defineMesh3D": {"id": 1, "verts": verts, "normals": normals,
                                  "uv": uv, "indices": idx}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@rot", "axis": [0, 1, 0]}},
             paint({"color": "#FF27385C"}, {"style": "stroke"}, {"width": 1.0}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth", "wireframe": True}}]

    cmds += text_at("drag left and right to turn the scatter", 24.0, 382.0, 11.5, TEXT)
    cmds += text_at("90 holdings", 24.0, 404.0, 11.0, DIM)
    cmds += text_at("across: risk    up: return    depth: sector", 24.0, 420.0, 10.5, DIM)
    cmds += text_at("dot size is position size; brighter is higher return",
                    24.0, 436.0, 10.0, GOOD)
    cmds += text_at("the rotation is applied to each point before projecting it, so the "
                    "cloud turns with the box", 24.0, 458.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "Ninety holdings as a particle scatter in three axes, "
                                   "turned by dragging"),
            "root": canvas(title(cmds, W, H, "A portfolio in three axes",
                                 "drag to turn: risk, return and sector"))}


use("FIN-MARK-00001")
docs["FIN-MARK-00001"] = stocks()


# ── 15. FIN-MARK-00002  Bonds — interactive / analyze / 2D ────────────────────
# Drag the yield and watch the price move the other way. The inverse relationship is the
# single fact worth carrying away, and it is much more convincing under your own finger.
def bonds():
    W, H = 520, 400
    cmds = []
    cmds.append({"touchExpression": {"name": "y", "defaultValue": 4.0, "min": 1.0,
                                     "max": 10.0, "stopMode": "gently",
                                     "expression": "touchY() / 400 * 11"}})
    cmds.append(var("yl", "clamp(1.0, 10.0, @y)"))
    # price of a 5% coupon, 10-year bond, approximated by duration around par
    cmds.append(var("price", "100 + (5.0 - @yl) * 7.8"))

    left, right, top, bottom = 70.0, 480.0, 110.0, 300.0
    for p in (60, 80, 100, 120, 140):
        yy = bottom - (p - 60) / 80.0 * (bottom - top)
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": left, "y1": yy, "x2": right, "y2": yy}})
        cmds += text_at(str(p), left - 8.0, yy + 4.0, 9.0, DIM, pan_x=1.0)

    # the price-yield curve, drawn once as a path
    pts = []
    for k in range(61):
        yv = 1.0 + k / 60.0 * 9.0
        pr = 100 + (5.0 - yv) * 7.8
        pts.append((round(left + (yv - 1.0) / 9.0 * (right - left), 2),
                    round(bottom - (pr - 60) / 80.0 * (bottom - top), 2)))
    cmds.append({"pathCreate": {"id": "py", "x": pts[0][0], "y": pts[0][1]}})
    for px, py in pts[1:]:
        cmds.append({"pathAppendLineTo": {"path": "py", "x": px, "y": py}})
    cmds.append(paint({"color": "#FF3E5A8C"}, {"style": "stroke"}, {"width": 2.0}))
    cmds.append({"drawPath": {"path": "py"}})

    cmds.append(var("mx", "%.1f + (@yl - 1) / 9 * %.1f" % (left, right - left)))
    cmds.append(var("my", "%.1f - (@price - 60) / 80 * %.1f" % (bottom, bottom - top)))
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": "@mx", "y1": top, "x2": "@mx", "y2": bottom}})
    cmds.append(paint({"color": WARM}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": "@mx", "cy": "@my", "radius": 8.0}})
    cmds.append(paint({"color": "#FF2A4A86"}, {"style": "stroke"}, {"width": 1.2}))
    cmds.append({"drawLine": {"x1": left, "y1": "%.1f - (100 - 60) / 80 * %.1f"
                              % (bottom, bottom - top),
                              "x2": right, "y2": "%.1f - (100 - 60) / 80 * %.1f"
                              % (bottom, bottom - top)}})
    cmds += text_at("par", right + 6.0, bottom - (100 - 60) / 80.0 * (bottom - top) + 4.0,
                    9.5, "#FF7E9AC6")

    for v in (1, 3, 5, 7, 10):
        x = left + (v - 1) / 9.0 * (right - left)
        cmds += text_at("%d%%" % v, x, bottom + 18.0, 9.5, DIM, pan_x=0.0)
    cmds += text_at("yield", left, bottom + 38.0, 10.0, DIM)
    cmds += text_at("price", left, 100.0, 10.0, DIM)

    for name, val, whole, dec, colour, x in (("yield", "@yl", 2, 2, GOOD, 70.0),
                                             ("price", "@price", 3, 2, WARM, 270.0)):
        cmds.append({"variable": {"name": "t" + name,
                                  "value": {"type": "textFromFloat", "value": val,
                                            "whole": whole, "decimal": dec}}})
        cmds.append(paint({"color": colour}, {"style": "fill"}, {"textSize": 26.0}))
        cmds.append({"drawTextAnchored": {"text": "@t" + name, "x": x, "y": 352.0,
                                          "panX": -1.0, "panY": 0.0, "flags": 0}})
        cmds += text_at(name, x, 372.0, 10.0, DIM)
    cmds += text_at("drag up and down; a 5% coupon pays par only when yields are 5%",
                    24.0, 392.0, 10.0, DIM)
    return {"header": header(W, H, "Drag the yield and watch a bond's price move inversely "
                                   "along the price-yield curve"),
            "root": canvas(title(cmds, W, H, "Price and yield", "one goes up, the other down"))}


use("FIN-MARK-00002")
docs["FIN-MARK-00002"] = bonds()


# ── 16. FIN-MARK-00003  Commodities — raster-and-text / explain / 2D ──────────
# A reference table. Commodities are traded in units nobody outside the pit knows, so the
# unit column is the document and everything else supports it.
COMMODITIES = [("Crude oil", "WTI", "1,000 barrels", "USD / barrel", HOT),
               ("Natural gas", "Henry Hub", "10,000 MMBtu", "USD / MMBtu", WARM),
               ("Gold", "COMEX", "100 troy ounces", "USD / ounce", "#FFD9B44A"),
               ("Copper", "COMEX", "25,000 pounds", "USD / pound", "#FFC07A4A"),
               ("Corn", "CBOT", "5,000 bushels", "USD cents / bushel", GOOD),
               ("Wheat", "CBOT", "5,000 bushels", "USD cents / bushel", "#FFBFCBE4")]


def commodities():
    W, H = 580, 380
    cmds = []
    heads = [("COMMODITY", 26.0, -1.0), ("VENUE", 210.0, -1.0),
             ("CONTRACT", 310.0, -1.0), ("QUOTED IN", 554.0, 1.0)]
    for name, x, pan in heads:
        cmds += text_at(name, x, 96.0, 9.5, DIM, pan_x=pan)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": 26.0, "y1": 104.0, "x2": 554.0, "y2": 104.0}})

    for i, (name, venue, size, quote, colour) in enumerate(COMMODITIES):
        y = 134.0 + i * 40.0
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 26.0, "top": y - 13.0,
                                  "right": 30.0, "bottom": y + 5.0}})
        cmds += text_at(name, 40.0, y, 14.0, TEXT)
        cmds += text_at(venue, 210.0, y, 11.0, DIM)
        cmds += text_at(size, 310.0, y, 12.5, colour)
        cmds += text_at(quote, 554.0, y, 11.5, "#FFB9C6E0", pan_x=1.0)
        if i < len(COMMODITIES) - 1:
            cmds.append(paint({"color": "#FF1B2740"}, {"style": "stroke"}, {"width": 1.0}))
            cmds.append({"drawLine": {"x1": 26.0, "y1": y + 14.0,
                                      "x2": 554.0, "y2": y + 14.0}})
    cmds += text_at("one contract is a fixed quantity, so a price move means a different "
                    "amount of money in each row", 26.0, 356.0, 10.5, TEXT)
    return {"header": header(W, H, "Six commodity futures contracts, their venues, contract "
                                   "sizes and quoting units"),
            "root": canvas(title(cmds, W, H, "Commodity contracts", "what one contract is"))}


use("FIN-MARK-00003")
docs["FIN-MARK-00003"] = commodities()


# ── write ───────────────────────────────────────────────────────────────────────
def main():
    for doc_id, doc in docs.items():
        (OUT / ("%s.json" % doc_id)).write_text(json.dumps(doc, indent=1) + "\n")
    print("  wrote %d documents to %s" % (len(docs), OUT.name))
    import collections
    tally = collections.Counter(PALETTE_USED.values())
    print("  palettes: %s" % dict(sorted(tally.items())))


if __name__ == "__main__":
    main()
