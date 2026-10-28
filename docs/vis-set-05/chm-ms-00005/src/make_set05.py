#!/usr/bin/env python3
"""Build set 5 of the visualization programme: 16 documents.

    python3 work/set-05/make_set05.py

Work order from `python3 tools/visplan.py set 5`. No curation swap: all four 3D slots suit
their topics. The chart of nuclides really is a three-dimensional object, a molecule is a
volume, a turbine is a volume, and a body is the most obviously volumetric subject here.

Helper block carried from set 4, which carried it from set 3. It holds the six palettes,
axis_rod/draw_axes, mesh_box, surface_mesh, and every rule the earlier sets paid for -
including the two set 4 added: text placed relative to a table's own extent rather than a
fixed y, and palette role PAIRS chosen for contrast across all six palettes rather than the
one in front of you.
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


# ── 1. PHY-AP-00015  Quantum transitions — static-diagram / compare / 2D ─────
# Four transitions on four identical two-level diagrams. Keeping the levels in the same
# place in every panel is the whole trick: the only thing that varies is the arrow, so the
# comparison is forced rather than asserted.
def transitions():
    W, H = 600, 380
    panels = [("Absorption", "up", 1, "a photon arrives and is taken in", GOOD),
              ("Spontaneous", "down", 1, "the atom drops on its own, any time", WARM),
              ("Stimulated", "down", 2, "a photon arrives and two leave, in step", HOT),
              ("Non-radiative", "down", 0, "the energy goes to heat, not light", DIM)]
    cmds = []
    pw = 136.0
    for i, (name, direction, photons, note, colour) in enumerate(panels):
        x0 = 26.0 + i * (pw + 10.0)
        cx = x0 + pw / 2
        yhi, ylo = 150.0, 250.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": 110.0,
                                  "right": x0 + pw, "bottom": 300.0}})
        for y, lbl in ((yhi, "E2"), (ylo, "E1")):
            cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 2.0}))
            cmds.append({"drawLine": {"x1": x0 + 18.0, "y1": y,
                                      "x2": x0 + pw - 18.0, "y2": y}})
            cmds += text_at(lbl, x0 + 12.0, y + 4.0, 9.0, DIM, pan_x=1.0)
        # the electron, before and after
        cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": cx - 26.0,
                                    "cy": ylo if direction == "up" else yhi,
                                    "radius": 5.5}})
        cmds.append(paint({"color": ACCENT}, {"style": "fill"}, {"alpha": 0.45}))
        cmds.append({"drawCircle": {"cx": cx + 26.0,
                                    "cy": yhi if direction == "up" else ylo,
                                    "radius": 5.5}})
        # the transition arrow
        y0, y1 = (ylo, yhi) if direction == "up" else (yhi, ylo)
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6}))
        cmds.append({"drawLine": {"x1": cx, "y1": y0, "x2": cx, "y2": y1}})
        for sgn in (-1, 1):
            cmds.append({"drawLine": {"x1": cx, "y1": y1, "x2": cx + sgn * 5.0,
                                      "y2": y1 + (9.0 if direction == "up" else -9.0)}})
        # photons in or out, as little wave bundles
        for k in range(photons):
            py = 130.0 + k * 14.0 if direction == "down" else 282.0
            for seg in range(4):
                sx = x0 + 22.0 + seg * 9.0 + k * 2.0
                cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.8}))
                cmds.append({"drawArc": {"left": sx, "top": py - 4.0,
                                         "right": sx + 9.0, "bottom": py + 4.0,
                                         "startAngle": 0.0 if seg % 2 else 180.0,
                                         "sweepAngle": 180.0}})
        cmds += text_at(name, cx, 100.0, 11.5, colour, pan_x=0.0)
        cmds += text_at(note, x0 + 6.0, 318.0, 8.5, DIM)
        cmds += text_at("%d photon%s" % (photons, "" if photons == 1 else "s"),
                        cx, 336.0, 9.5, TEXT, pan_x=0.0)
    cmds += text_at("same two levels in every panel, so only the transition differs",
                    26.0, 362.0, 10.5, TEXT)
    return {"header": header(W, H, "Four transitions between the same two energy levels, "
                                   "differing only in direction and photon count"),
            "root": canvas(title(cmds, W, H, "Quantum transitions",
                                 "four ways between two levels"))}


use("PHY-AP-00015")
docs["PHY-AP-00015"] = transitions()


# ── 2. PHY-NP-00016  Nuclear structure — annotated-layout / demonstrate / 2D ─
# Isotope cards, each drawing its own nucleus. The demonstration is that the proton count
# fixes the element and the neutron count does not, which only lands if you see three
# nuclei that are all carbon.
ISOTOPES = [("Carbon-12", 6, 6, "stable, 98.9% of carbon", GOOD),
            ("Carbon-13", 6, 7, "stable, 1.1%", ACCENT),
            ("Carbon-14", 6, 8, "decays, half-life 5,730 years", HOT),
            ("Nitrogen-14", 7, 7, "what carbon-14 becomes", WARM)]


def nuclear_structure():
    W, H = 500, 580

    def nucleus(z, n, colour):
        c = [paint({"color": "#FF0F1830"}, {"style": "fill"}),
             {"drawRect": {"left": 0, "top": 0, "right": 130, "bottom": 104}}]
        total = z + n
        for k in range(total):
            ang = k * 2.399963                      # golden angle, so they pack evenly
            r = 5.0 + 3.6 * math.sqrt(k)
            px = 65.0 + r * math.cos(ang)
            py = 52.0 + r * math.sin(ang)
            is_proton = k < z
            c.append(paint({"color": colour if is_proton else "#FF6E89B4"},
                           {"style": "fill"}))
            c.append({"drawCircle": {"cx": round(px, 1), "cy": round(py, 1),
                                     "radius": 6.5}})
        return {"type": "canvas", "modifiers": [{"width": 130}, {"height": 104}],
                "commands": c}

    cards = []
    for name, z, n, note, colour in ISOTOPES:
        cards.append({"type": "row",
                      "modifiers": [{"width": 460}, {"padding": 8},
                                    {"background": PANEL}],
                      "children": [
                          nucleus(z, n, colour),
                          {"type": "spacer", "modifiers": [{"width": 12}]},
                          {"type": "column", "modifiers": [{"width": 290}], "children": [
                              {"type": "text", "value": name, "modifiers": [],
                               "fontSize": 15.0, "color": colour},
                              {"type": "spacer", "modifiers": [{"height": 6}]},
                              {"type": "text", "value": "%d protons, %d neutrons" % (z, n),
                               "modifiers": [], "fontSize": 12.5, "color": TEXT},
                              {"type": "spacer", "modifiers": [{"height": 4}]},
                              {"type": "text", "value": note, "modifiers": [],
                               "fontSize": 10.0, "color": DIM}]}]})
        cards.append({"type": "spacer", "modifiers": [{"height": 8}]})

    return {
        "header": header(W, H, "Three carbon isotopes and a nitrogen nucleus as cards, each "
                               "drawing its own protons and neutrons"),
        "root": {"type": "column",
                 "modifiers": ["fillMaxSize", {"background": INK}, {"padding": 16}],
                 "children": [
                     {"type": "text", "value": "Nuclear structure", "modifiers": [],
                      "fontSize": 20.0, "color": TEXT},
                     {"type": "spacer", "modifiers": [{"height": 4}]},
                     {"type": "text",
                      "value": "protons decide the element; neutrons decide the isotope",
                      "modifiers": [], "fontSize": 11.0, "color": DIM},
                     {"type": "spacer", "modifiers": [{"height": 12}]},
                 ] + cards + [
                     {"type": "text",
                      "value": "the first three are all carbon; add one proton and it is "
                               "nitrogen instead",
                      "modifiers": [], "fontSize": 9.5, "color": "#FF5E6E95"}]},
    }


use("PHY-NP-00016")
docs["PHY-NP-00016"] = nuclear_structure()


# ── 3. PHY-NP-00017  Radioactive decay — data-plot / simulate / 3D ───────────
# The chart of nuclides is genuinely three-dimensional: protons one way, neutrons the other,
# and stability as height. The valley of stability is a valley, and saying so in 2D with
# colour never reads as well as a floor you can see dipping.
def nuclides():
    W, H = 520, 500
    ZMAX, NMAX = 28, 34
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.95, "aspect": 1.0,
                          "near": 0.1, "far": 80.0,
                          "eye": [2.3, 2.5, 2.9], "center": [0, -0.15, 0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.4, -0.72, -0.52], "intensity": 1.0},
                {"type": "directional", "color": "#FF5B8CEE",
                 "dir": [0.55, 0.25, 0.4], "intensity": 0.3}]}}]
    cmds.append(var("spin", "sin(continuousSec() * 0.22) * 0.5"))

    # distance from the empirical line of stability, N ~ Z + Z^2/60
    verts, normals, uv, idx = [], [], [], []
    towers = 0
    for z in range(1, ZMAX + 1):
        for n in range(0, NMAX + 1):
            stable_n = z + z * z / 60.0
            off = abs(n - stable_n)
            if off > 5.5 or n < z * 0.6:
                continue
            towers += 1
            hgt = 0.06 + 0.42 * math.exp(-off * off / 5.0)
            x = -1.0 + z / ZMAX * 2.0
            zz = -1.0 + n / NMAX * 2.0
            s = 0.026
            mesh_box(verts, normals, uv, idx,
                     (x - s, -0.62, zz - s), (x + s, -0.62 + hgt, zz + s))
    cmds.append({"defineMesh3D": {"id": 1, "verts": [round(v, 5) for v in verts],
                                  "normals": normals, "uv": uv, "indices": idx}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": "#FF5FA8E8"}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]

    BASE, EDGE = -0.62, 1.1
    draw_axes(cmds, [
        (2, axis_rod(2, (-EDGE, BASE, -EDGE), (EDGE, BASE, -EDGE),
                     [-1.0 + z / ZMAX * 2.0 for z in (8, 16, 24)], "x")),
        (3, axis_rod(3, (-EDGE, BASE, -EDGE), (-EDGE, BASE, EDGE),
                     [-1.0 + n / NMAX * 2.0 for n in (10, 20, 30)], "z")),
        (4, axis_rod(4, (-EDGE, BASE, -EDGE), (-EDGE, BASE + 0.5, -EDGE),
                     [BASE + 0.2, BASE + 0.4], "y")),
    ], "@spin", [WARM, GOOD, "#FFBFCBE4"])

    cmds += text_at("protons", 24.0, 392.0, 11.0, WARM)
    cmds += text_at("neutrons", 104.0, 392.0, 11.0, GOOD)
    cmds += text_at("stability", 196.0, 392.0, 11.0, "#FFBFCBE4")
    cmds += text_at("%d nuclides, tallest where the nucleus is most tightly bound"
                    % towers, 24.0, 418.0, 11.0, TEXT)
    cmds += text_at("the ridge bends away from the diagonal: heavy nuclei need extra "
                    "neutrons", 24.0, 438.0, 10.0, DIM)
    cmds += text_at("either side of the ridge, a nucleus decays back towards it",
                    24.0, 456.0, 10.0, DIM)
    cmds += text_at("ticks: protons 8 16 24, neutrons 10 20 30", 24.0, 478.0, 9.0,
                    "#FF5E6E95")
    return {"header": header(W, H, "The chart of nuclides as 3D towers, with the valley of "
                                   "stability as a visible ridge"),
            "root": canvas(title(cmds, W, H, "The valley of stability",
                                 "protons against neutrons"))}


use("PHY-NP-00017")
docs["PHY-NP-00017"] = nuclides()


# ── 4. PHY-NP-00018  Fission — path-form / analyze / 2D ──────────────────────
# Fission does not split a nucleus in half, and the yield curve is the evidence: two humps,
# not one peak in the middle. The fragment paths above it are the picture people carry; the
# curve below is the thing that corrects it.
def fission():
    W, H = 580, 460
    cmds = []
    # fragment tracks, as real paths from the split point
    sx, sy = 160.0, 170.0
    cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 3.0},
                      {"strokeCap": "round"}))
    cmds.append({"drawLine": {"x1": 40.0, "y1": 170.0, "x2": sx - 26.0, "y2": 170.0}})
    cmds += text_at("neutron", 40.0, 160.0, 9.5, WARM)

    for fi, (ang, mass, colour, label) in enumerate(
            [(-0.42, 95, ACCENT, "lighter fragment"), (0.36, 139, HOT, "heavier fragment")]):
        pid = "frag%d" % fi
        pts = []
        for k in range(30):
            t = k / 29.0
            # the heavier fragment carries less speed, so its track is shorter and straighter
            reach = 230.0 * (1.25 - mass / 200.0)
            px = sx + t * reach
            py = sy + math.sin(ang) * t * reach * 0.8 + math.sin(t * 2.2) * 5.0
            pts.append((round(px, 2), round(py, 2)))
        cmds.append({"pathCreate": {"id": pid, "x": pts[0][0], "y": pts[0][1]}})
        for a, b in pts[1:]:
            cmds.append({"pathAppendLineTo": {"path": pid, "x": a, "y": b}})
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6},
                          {"strokeCap": "round"}))
        cmds.append({"drawPath": {"path": pid}})
        ex, ey = pts[-1]
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": ex, "cy": ey,
                                    "radius": 9.0 + mass / 26.0}})
        cmds += text_at("A = %d" % mass, ex + 16.0, ey + 4.0, 11.0, colour)
        cmds += text_at(label, ex + 16.0, ey + 18.0, 9.0, DIM)
    # loose neutrons
    for k, ang in enumerate((-0.05, 0.14, -0.22)):
        cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 1.6}))
        cmds.append({"drawLine": {"x1": sx, "y1": sy,
                                  "x2": round(sx + math.cos(ang) * 92, 1),
                                  "y2": round(sy + math.sin(ang) * 92 - 44, 1)}})
    cmds += text_at("2 to 3 free neutrons", sx + 96.0, 108.0, 9.5, WARM)
    cmds.append(paint({"color": TEXT}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": sx, "cy": sy, "radius": 13.0}})
    cmds += text_at("U-235", sx, sy + 32.0, 10.0, TEXT, pan_x=0.0)

    # the yield curve, as a path: two humps
    gx0, gx1, gy0, gy1 = 70.0, 540.0, 268.0, 384.0
    def yld(a):
        return (math.exp(-((a - 95) ** 2) / 320.0) + math.exp(-((a - 139) ** 2) / 420.0))
    pts = []
    for k in range(101):
        a = 70 + k / 100.0 * 90
        pts.append((round(gx0 + (a - 70) / 90.0 * (gx1 - gx0), 2),
                    round(gy1 - yld(a) / 1.05 * (gy1 - gy0), 2)))
    cmds.append({"pathCreate": {"id": "yield", "x": pts[0][0], "y": pts[0][1]}})
    for a, b in pts[1:]:
        cmds.append({"pathAppendLineTo": {"path": "yield", "x": a, "y": b}})
    cmds.append(paint({"color": GOOD}, {"style": "stroke"}, {"width": 2.4}))
    cmds.append({"drawPath": {"path": "yield"}})
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.3}))
    cmds.append({"drawLine": {"x1": gx0, "y1": gy1, "x2": gx1, "y2": gy1}})
    for a in (80, 95, 117, 139, 155):
        x = gx0 + (a - 70) / 90.0 * (gx1 - gx0)
        cmds += text_at(str(a), x, gy1 + 16.0, 9.5, DIM, pan_x=0.0)
        if a == 117:
            cmds.append(paint({"color": HOT}, {"style": "stroke"}, {"width": 1.4}))
            cmds.append({"drawLine": {"x1": x, "y1": gy0 - 6.0, "x2": x, "y2": gy1}})
            cmds += text_at("an even split would peak here", x + 8.0, gy0 + 6.0, 9.5, HOT)
    cmds += text_at("fission yield by fragment mass", gx0, gy0 - 14.0, 10.5, GOOD)
    cmds += text_at("mass number", gx0, gy1 + 34.0, 10.0, DIM)
    cmds += text_at("uranium does not split down the middle", 24.0, 424.0, 11.5, TEXT)
    cmds += text_at("two humps, around A=95 and A=139 - the symmetric split is the rare one",
                    24.0, 442.0, 10.0, DIM)
    return {"header": header(W, H, "Fission fragment tracks above the yield curve, showing "
                                   "the asymmetric double hump"),
            "root": canvas(title(cmds, W, H, "Fission", "why it splits unevenly"))}


use("PHY-NP-00018")
docs["PHY-NP-00018"] = fission()


# ── 5. BIO-BIOC-00017  ATP — expression-animation / explain / 2D ─────────────
# The cycle, on one clock: the third phosphate leaves, energy is released, and it comes
# back. Showing it as a loop rather than two states is the point - ATP is not consumed, it
# is recharged.
def atp():
    W, H = 540, 400
    cx, cy, R = 270.0, 220.0, 112.0
    cmds = []
    cmds.append(var("t", "(continuousSec() * 0.42) % 1"))
    cmds.append(var("ang", "@t * 6.28318 - 1.5708"))

    cmds.append(paint({"color": "#FF22304E"}, {"style": "stroke"}, {"width": 20.0}))
    cmds.append({"drawCircle": {"cx": cx, "cy": cy, "radius": R}})

    for label, frac, colour in (("ATP", 0.0, GOOD), ("ADP + P", 0.5, WARM)):
        a = frac * 2 * math.pi - math.pi / 2
        x, y = cx + R * math.cos(a), cy + R * math.sin(a)
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": round(x, 1), "cy": round(y, 1), "radius": 34.0}})
        cmds.append(paint({"color": INK}, {"style": "fill"}, {"textSize": 12.0}))
        cmds.append({"drawTextAnchored": {"text": label, "x": round(x, 1),
                                          "y": round(y, 1) + 4.0, "panX": 0.0,
                                          "panY": 0.0, "flags": 0}})

    # the travelling marker: a phosphate leaving on one half, returning on the other
    cmds.append(paint({"color": HOT}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": "%.1f + cos(@ang) * %.1f" % (cx, R),
                                "cy": "%.1f + sin(@ang) * %.1f" % (cy, R),
                                "radius": 10.0}})
    cmds.append(paint({"color": INK}, {"style": "fill"}, {"textSize": 9.0}))
    cmds.append({"drawTextAnchored": {"text": "P", "x": "%.1f + cos(@ang) * %.1f" % (cx, R),
                                      "y": "%.1f + sin(@ang) * %.1f + 3" % (cy, R),
                                      "panX": 0.0, "panY": 0.0, "flags": 0}})

    # energy released on the way down, absorbed on the way back
    cmds.append(var("release", "clamp(0.0, 1.0, 1 - abs(@t - 0.25) * 6)"))
    cmds.append(var("recharge", "clamp(0.0, 1.0, 1 - abs(@t - 0.75) * 6)"))
    cmds.append(paint({"color": HOT}, {"style": "fill"}, {"alpha": "@release"}))
    cmds.append({"drawRoundRect": {"left": cx + R - 24.0, "top": cy - 18.0,
                                   "right": cx + R + 112.0, "bottom": cy + 18.0,
                                   "rx": 8.0, "ry": 8.0}})
    cmds.append(paint({"color": INK}, {"style": "fill"}, {"textSize": 11.5},
                      {"alpha": "@release"}))
    cmds.append({"drawTextAnchored": {"text": "energy out", "x": cx + R + 44.0,
                                      "y": cy + 4.0, "panX": 0.0, "panY": 0.0,
                                      "flags": 0}})
    cmds.append(paint({"color": GOOD}, {"style": "fill"}, {"alpha": "@recharge"}))
    cmds.append({"drawRoundRect": {"left": cx - R - 112.0, "top": cy - 18.0,
                                   "right": cx - R + 24.0, "bottom": cy + 18.0,
                                   "rx": 8.0, "ry": 8.0}})
    cmds.append(paint({"color": INK}, {"style": "fill"}, {"textSize": 11.5},
                      {"alpha": "@recharge"}))
    cmds.append({"drawTextAnchored": {"text": "energy in", "x": cx - R - 44.0,
                                      "y": cy + 4.0, "panX": 0.0, "panY": 0.0,
                                      "flags": 0}})

    cmds += text_at("hydrolysis releases about 30 kJ per mole", 24.0, 350.0, 11.0, TEXT)
    cmds += text_at("respiration puts the phosphate back; a cell turns over its own weight "
                    "in ATP daily", 24.0, 368.0, 10.0, DIM)
    cmds += text_at("one clock drives the whole loop", 24.0, 386.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "The ATP cycle as a loop, with a phosphate leaving and "
                                   "returning and energy released and absorbed"),
            "root": canvas(title(cmds, W, H, "ATP", "charged, spent, recharged"))}


use("BIO-BIOC-00017")
docs["BIO-BIOC-00017"] = atp()


# ── 6. MTH-ALGE-00005  Functions — particle-system / explore / 2D ────────────
# A function is a mapping, so the particles ARE the mapping: each one sits at its input on
# the bottom axis and at its output on the left, joined by its own position. Spread the
# inputs evenly and the shape of f falls out of where the dots land.
def functions():
    W, H = 520, 460
    x0, x1 = 90.0, 470.0
    y0, y1 = 110.0, 340.0
    cmds = []
    cmds.append(var("m", "0.5 + sin(continuousSec() * 0.3) * 0.45"))

    for g in (0.0, 0.25, 0.5, 0.75, 1.0):
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": x0 + g * (x1 - x0), "y1": y0,
                                  "x2": x0 + g * (x1 - x0), "y2": y1}})
        cmds.append({"drawLine": {"x1": x0, "y1": y1 - g * (y1 - y0),
                                  "x2": x1, "y2": y1 - g * (y1 - y0)}})

    cmds.append({"createParticles": {
        "id": "pt",
        "variables": ["u", "jx", "ph"],
        "initialValues": ["rand()", "rand()", "rand() * 6.283"],
        "count": 150}})
    # f(x) = x^m, with m under a slow oscillation: at m=1 the dots lie on the diagonal,
    # below it they bow up, above it they bow down. Position IS the function.
    cmds.append({"particlesLoop": {
        "system": "@pt",
        "equations": ["u", "jx", "ph"],
        "commands": [
            paint({"color": ACCENT}, {"style": "fill"}, {"alpha": 0.8}),
            {"drawCircle": {
                "cx": "%.1f + u * %.1f" % (x0, x1 - x0),
                "cy": "%.1f - pow(u, @m * 2.4 + 0.3) * %.1f" % (y1, y1 - y0),
                "radius": 3.4}}]}})

    # the diagonal, for reference
    cmds.append(paint({"color": "#FF55658A"}, {"style": "stroke"}, {"width": 1.4}))
    cmds.append({"drawLine": {"x1": x0, "y1": y1, "x2": x1, "y2": y0}})
    cmds += text_at("f(x) = x", x1 - 70.0, y0 + 18.0, 10.0, "#FF7E9AC6")

    cmds.append({"variable": {"name": "mt", "value": {"type": "textFromFloat",
                                                      "value": "@m * 2.4 + 0.3",
                                                      "whole": 1, "decimal": 2}}})
    cmds.append(paint({"color": WARM}, {"style": "fill"}, {"textSize": 28.0}))
    cmds.append({"drawTextAnchored": {"text": "@mt", "x": x1, "y": 384.0,
                                      "panX": 1.0, "panY": 0.0, "flags": 0}})
    cmds += text_at("the exponent", x0, 384.0, 11.5, DIM)
    cmds += text_at("x", x1, y1 + 20.0, 11.0, DIM, pan_x=1.0)
    cmds += text_at("f(x)", x0 - 10.0, y0 + 4.0, 11.0, DIM, pan_x=1.0)
    cmds += text_at("150 inputs spread evenly along x, each drawn at its own output",
                    24.0, 412.0, 11.0, TEXT)
    cmds += text_at("below 1 the curve bows above the diagonal; above 1 it sags below",
                    24.0, 430.0, 10.0, DIM)
    cmds += text_at("the dots are the function, not a sample of it", 24.0, 448.0, 9.5,
                    "#FF5E6E95")
    return {"header": header(W, H, "150 particles placed at their own input and output, "
                                   "tracing a power function as its exponent changes"),
            "root": canvas(title(cmds, W, H, "A function is a mapping",
                                 "every dot is one input and its output"))}


use("MTH-ALGE-00005")
docs["MTH-ALGE-00005"] = functions()


# ── 7. CSC-ALGO-00005  Optimization — interactive / compare / 2D ─────────────
# Two searches on the same landscape, under your finger. Gradient descent is fast and finds
# whichever basin it started in; random search is slow and does not care. Drag the start
# point and the comparison makes itself.
def optimization():
    W, H = 560, 470
    gx0, gx1, gy0, gy1 = 50.0, 510.0, 110.0, 310.0

    def raw(u):
        """Two basins, the right one deeper, so a start on the left gets stuck in the
        shallow one. The first version of this had a single interior minimum and therefore
        could not demonstrate the thing it claimed - the document said "1 basins" and was
        right to."""
        return 1.3 * (u - 0.62) ** 2 + 0.18 * math.sin(u * 15.0)

    _lo = min(raw(k / 400.0) for k in range(401))
    _hi = max(raw(k / 400.0) for k in range(401))

    def cost(u):
        return (raw(u) - _lo) / (_hi - _lo)

    cmds = []
    cmds.append({"touchExpression": {"name": "start", "defaultValue": 0.22,
                                     "min": 0.02, "max": 0.98, "stopMode": "gently",
                                     "expression": "touchX() / 560"}})
    cmds.append(var("s", "clamp(0.02, 0.98, @start)"))

    pts = []
    for k in range(121):
        u = k / 120.0
        pts.append((round(gx0 + u * (gx1 - gx0), 2),
                    round(gy1 - cost(u) * (gy1 - gy0), 2)))
    cmds.append({"pathCreate": {"id": "land", "x": pts[0][0], "y": pts[0][1]}})
    for a, b in pts[1:]:
        cmds.append({"pathAppendLineTo": {"path": "land", "x": a, "y": b}})
    cmds.append(paint({"color": "#FF46608E"}, {"style": "stroke"}, {"width": 2.2}))
    cmds.append({"drawPath": {"path": "land"}})

    # gradient descent, traced at build time from the same cost function: wherever the
    # user starts, the walk is computed here and drawn as a path with the start under @s
    for marker in range(1):
        cmds.append(paint({"color": GOOD}, {"style": "stroke"}, {"width": 1.4}))
        cmds.append({"drawLine": {"x1": "%.1f + @s * %.1f" % (gx0, gx1 - gx0),
                                  "y1": gy0 - 8.0,
                                  "x2": "%.1f + @s * %.1f" % (gx0, gx1 - gx0),
                                  "y2": gy1 + 8.0}})
    # every basin floor, so the reader can see which one a start falls into
    minima = []
    for k in range(1, 120):
        u = k / 120.0
        if cost(u) < cost((k - 1) / 120.0) and cost(u) < cost((k + 1) / 120.0):
            minima.append(u)
    for mi, u in enumerate(minima):
        x = gx0 + u * (gx1 - gx0)
        y = gy1 - cost(u) * (gy1 - gy0)
        deepest = abs(cost(u) - min(cost(v) for v in minima)) < 1e-9
        cmds.append(paint({"color": HOT if deepest else WARM}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": round(x, 1), "cy": round(y, 1), "radius": 7.0}})
        cmds += text_at("global" if deepest else "local", round(x, 1), round(y, 1) + 24.0,
                        9.5, HOT if deepest else WARM, pan_x=0.0)

    # random search: scattered probes, indifferent to where you start
    cmds.append({"createParticles": {
        "id": "rs",
        "variables": ["ru", "ph"],
        "initialValues": ["rand()", "rand() * 6.283"],
        "count": 40}})
    cmds.append({"particlesLoop": {
        "system": "@rs",
        "equations": ["ru", "ph"],
        "commands": [
            paint({"color": ACCENT}, {"style": "fill"}, {"alpha": 0.55}),
            {"drawCircle": {"cx": "%.1f + ru * %.1f" % (gx0, gx1 - gx0),
                            "cy": "%.1f + sin(ph + animationTime) * 5" % (gy1 + 30.0),
                            "radius": 3.2}}]}})
    cmds += text_at("random search samples everywhere, ignoring where you started",
                    gx0, gy1 + 52.0, 10.0, ACCENT)

    cmds += text_at("drag to move the starting point", 24.0, 388.0, 11.5, TEXT)
    cmds += text_at("gradient descent walks downhill from wherever you put it, so it finds "
                    "the nearest floor", 24.0, 408.0, 10.0, GOOD)
    cmds += text_at("that is the local minimum unless you happened to start in the right "
                    "basin", 24.0, 426.0, 10.0, WARM)
    cmds += text_at("%d basins on this landscape, and only the deeper one is the answer"
                    % len(minima), 24.0, 448.0, 10.0, DIM)
    return {"header": header(W, H, "A cost landscape with the starting point under your "
                                   "finger, comparing gradient descent against random search"),
            "root": canvas(title(cmds, W, H, "Local or global",
                                 "where you start decides what you find"))}


use("CSC-ALGO-00005")
docs["CSC-ALGO-00005"] = optimization()


# ── 8. CHM-MS-00005  Chemical bonds — raster-and-text / demonstrate / 3D ─────
# A textured 3D molecule. The texture goes on a FILLED mesh, because a wireframe draws only
# its edges and shows no texture at all (F-010) - which is the mistake set 2 shipped before
# it was caught.
def bonds():
    W, H = 480, 500
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.9, "aspect": 1.0,
                          "near": 0.1, "far": 60.0,
                          "eye": [0.6, 0.8, 3.2], "center": [0, 0, 0], "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.35, -0.55, -0.75], "intensity": 1.0},
                {"type": "directional", "color": "#FF4FD6C9",
                 "dir": [0.5, 0.25, 0.4], "intensity": 0.28}]}}]
    cmds.append(var("spin", "continuousSec() * 0.3"))

    # methane: a textured carbon with four hydrogens at the tetrahedral angle
    tet = [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]
    for i, (hx, hy, hz) in enumerate(tet):
        d = math.sqrt(3)
        bx, by, bz = hx / d * 0.78, hy / d * 0.78, hz / d * 0.78
        # the bond, as a run of small spheres - there is no cylinder-between-two-points op
        for k in range(1, 7):
            t = k / 7.0
            cmds += [{"meshPrimitive3D": {"id": 40 + i * 8 + k, "primitive": "sphere",
                                          "segments": 8, "radius": 0.045,
                                          "center": [0, 0, 0]}},
                     {"matrix3D": {"op": "identity"}},
                     {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                     {"matrix3D": {"op": "translate", "x": round(bx * t, 4),
                                   "y": round(by * t, 4), "z": round(bz * t, 4)}},
                     paint({"color": "#FF9FB0D4"}, {"style": "fill"}),
                     {"drawMesh3D": {"mesh": 40 + i * 8 + k, "mode": "software-smooth"}}]
        cmds += [{"meshPrimitive3D": {"id": 10 + i, "primitive": "sphere", "segments": 16,
                                      "radius": 0.21, "center": [0, 0, 0]}},
                 {"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 {"matrix3D": {"op": "translate", "x": round(bx, 4), "y": round(by, 4),
                               "z": round(bz, 4)}},
                 paint({"color": "#FFE4ECFA"}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": 10 + i, "mode": "software-smooth"}}]

    cmds += [{"texture3D": {"bitmap": "@shell"}},
             {"meshPrimitive3D": {"id": 1, "primitive": "sphere", "segments": 26,
                                  "radius": 0.40, "center": [0, 0, 0], "uv": "uv"}},
             {"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": "#FFFFFFFF"}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]

    rows = [("Covalent", "electrons shared", "methane, diamond, water", GOOD),
            ("Ionic", "electrons transferred", "table salt, most minerals", WARM),
            ("Metallic", "electrons pooled and free", "copper, iron, every wire", ACCENT)]
    for i, (kind, how, egs, colour) in enumerate(rows):
        y = 374.0 + i * 36.0
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 24.0, "top": y - 12.0,
                                  "right": 28.0, "bottom": y + 6.0}})
        cmds += text_at(kind, 38.0, y, 13.5, colour)
        cmds += text_at(how, 140.0, y, 11.0, TEXT)
        cmds += text_at(egs, 300.0, y, 10.0, DIM)
    cmds += text_at("the carbon's shell is a bitmap texture on a filled mesh",
                    24.0, 484.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "A methane molecule with a bitmap-textured carbon, over a "
                                   "table of the three bond types"),
            "resources": {"bitmaps": [{"shell": {"file": "textures/shell.png"}}]},
            "root": canvas(title(cmds, W, H, "Chemical bonds",
                                 "shared, transferred, or pooled"))}


use("CHM-MS-00005")
docs["CHM-MS-00005"] = bonds()


# ── 9. EAR-GEOL-00005  Faults — static-diagram / demonstrate / 2D ────────────
# Three faults, three block pairs, one shared stratigraphy. Drawing the same layers in every
# panel is what makes the offset readable: you can trace a band across the break and see
# where it went.
def faults():
    W, H = 600, 420
    kinds = [("Normal", "pulled apart", -1, 0.0, GOOD),
             ("Reverse", "pushed together", 1, 0.0, HOT),
             ("Strike-slip", "slid past", 0, 1.0, WARM)]
    layers = [("#FF8A6A4A", 0), ("#FFB79A6E", 1), ("#FF6E89B4", 2), ("#FF4D6E8A", 3)]
    pw, ph = 170.0, 150.0
    cmds = []
    for i, (name, motion, dip, lateral, colour) in enumerate(kinds):
        x0 = 26.0 + i * (pw + 16.0)
        y0 = 120.0
        for side in (0, 1):
            dx = side * (pw / 2)
            # vertical throw for dip-slip faults, horizontal offset for strike-slip
            off_y = dip * (12.0 if side else -12.0)
            off_x = lateral * (10.0 if side else -10.0)
            for colour_l, li in layers:
                ly = y0 + li * (ph / len(layers))
                cmds.append(paint({"color": colour_l}, {"style": "fill"}))
                cmds.append({"drawRect": {
                    "left": x0 + dx + off_x, "top": ly + off_y,
                    "right": x0 + dx + pw / 2 + off_x,
                    "bottom": ly + ph / len(layers) + off_y}})
        # the fault plane itself
        cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 2.4}))
        if lateral:
            cmds.append({"drawLine": {"x1": x0 + pw / 2, "y1": y0 - 10.0,
                                      "x2": x0 + pw / 2, "y2": y0 + ph + 10.0}})
            for sgn, yy in ((-1, y0 + 20.0), (1, y0 + ph - 20.0)):
                cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.0}))
                cmds.append({"drawLine": {"x1": x0 + pw / 2 + sgn * 34.0, "y1": yy,
                                          "x2": x0 + pw / 2 + sgn * 6.0, "y2": yy}})
        else:
            cmds.append({"drawLine": {"x1": x0 + pw / 2 - 22.0, "y1": y0 - 10.0,
                                      "x2": x0 + pw / 2 + 22.0, "y2": y0 + ph + 10.0}})
            for side, sgn in ((0, -1), (1, 1)):
                ax = x0 + pw / 4 + side * (pw / 2)
                cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.0}))
                cmds.append({"drawLine": {"x1": ax, "y1": y0 + ph + 26.0,
                                          "x2": ax, "y2": y0 + ph + 26.0 - dip * sgn * 18.0}})
        cmds += text_at(name, x0 + pw / 2, 108.0, 13.0, colour, pan_x=0.0)
        cmds += text_at(motion, x0 + pw / 2, 312.0, 10.0, DIM, pan_x=0.0)

    cmds += text_at("the same four layers in every panel, so the offset is traceable",
                    26.0, 356.0, 11.0, TEXT)
    cmds += text_at("normal faults stretch the crust, reverse faults shorten it, and "
                    "strike-slip moves it sideways", 26.0, 376.0, 10.0, DIM)
    cmds += text_at("arrows show the direction each block moved", 26.0, 394.0, 9.5,
                    "#FF5E6E95")
    return {"header": header(W, H, "Normal, reverse and strike-slip faults drawn on the same "
                                   "four-layer stratigraphy"),
            "root": canvas(title(cmds, W, H, "Three kinds of fault",
                                 "same layers, different break"))}


use("EAR-GEOL-00005")
docs["EAR-GEOL-00005"] = faults()


# ── 10. ENG-ME-00005  Turbines — annotated-layout / simulate / 3D ────────────
# Layout carries the stage breakdown; one card holds a 3D rotor that actually turns. Putting
# the 3D inside a card rather than filling the document is the pattern set 3's Higgs
# established, and it keeps the numbers beside the picture.
def quad(verts, normals, uv, idx, a, b, c, d, n):
    """One flat quad as two triangles, winding per F-008."""
    base = len(verts) // 3
    for pt in (a, b, c, d):
        verts += [round(pt[0], 5), round(pt[1], 5), round(pt[2], 5)]
        normals += [round(n[0], 5), round(n[1], 5), round(n[2], 5)]
        uv += [0.0, 0.0]
    idx += [base, base + 2, base + 1, base, base + 3, base + 2]


def turbines():
    W, H = 460, 560

    # The 3D goes in a canvas that FILLS the document, not in a card. A scene nested in a
    # sized component projects into the document's viewport offset by that component, so it
    # lands mostly outside its own card (finding F-013) - which is why the first version of
    # this document showed half a rotor and no hub. Stacking a full-size canvas and the
    # layout column inside a box gives the 3D a predictable centre and keeps the cards.
    rotor = [{"clearDepth3D": {}},
             {"camera3D": {"projection": "perspective", "fovY": 0.80,
                           "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                           "eye": [1.74, 0.54, 4.70], "center": [0, -0.60, 0],
                           "up": [0, 1, 0]}},
             {"lights3D": {"lights": [
                 {"type": "directional", "color": "#FFFFFFFF",
                  "dir": [-0.42, -0.55, -0.72], "intensity": 1.0},
                 {"type": "directional", "color": "#FF7FA6F2",
                  "dir": [0.62, 0.22, 0.48], "intensity": 0.55},
                 {"type": "directional", "color": "#FF9FB4DC",
                  "dir": [0.05, 0.85, -0.52], "intensity": 0.30}]}}]
    rotor.append(var("rpm", "continuousSec() * 1.9"))

    # Blades built as twisted, tapered strips rather than beads on a line: a turbine blade
    # is an aerofoil whose chord shrinks and whose angle unwinds towards the tip, and that
    # shape is the only reason the thing works.
    NB, SEG = 14, 7
    R0, R1 = 0.26, 0.95
    verts, normals, uv, idx = [], [], [], []
    for k in range(NB):
        a = k * 2 * math.pi / NB
        ux, uy = math.cos(a), math.sin(a)
        for seg in range(SEG):
            t0, t1 = seg / SEG, (seg + 1) / SEG
            pts = []
            for t in (t0, t1):
                r = R0 + (R1 - R0) * t
                chord = 0.30 * (1.0 - 0.52 * t)          # tapers towards the tip
                tw = 0.95 * (1.0 - t) ** 1.3             # unwinds towards the tip
                ct, st = math.cos(tw), math.sin(tw)
                # chord direction: tangential, tilted out of plane by the twist
                cx_, cy_, cz_ = -uy * ct, ux * ct, st
                base = (ux * r, uy * r, 0.0)
                pts.append(((base[0] - cx_ * chord / 2, base[1] - cy_ * chord / 2,
                             base[2] - cz_ * chord / 2),
                            (base[0] + cx_ * chord / 2, base[1] + cy_ * chord / 2,
                             base[2] + cz_ * chord / 2)))
            (p00, p01), (p10, p11) = pts
            # face normal from the strip's own edges
            e1 = (p01[0] - p00[0], p01[1] - p00[1], p01[2] - p00[2])
            e2 = (p10[0] - p00[0], p10[1] - p00[1], p10[2] - p00[2])
            n = (e1[1] * e2[2] - e1[2] * e2[1],
                 e1[2] * e2[0] - e1[0] * e2[2],
                 e1[0] * e2[1] - e1[1] * e2[0])
            ln = math.sqrt(sum(c * c for c in n)) or 1.0
            n = (n[0] / ln, n[1] / ln, n[2] / ln)
            quad(verts, normals, uv, idx, p00, p01, p11, p10, n)
            quad(verts, normals, uv, idx, p00, p10, p11, p01,
                 (-n[0], -n[1], -n[2]))          # the other face, so it is solid from behind
    rotor.append({"defineMesh3D": {"id": 2, "verts": verts, "normals": normals,
                                   "uv": uv, "indices": idx}})
    rotor += [{"matrix3D": {"op": "identity"}},
              {"matrix3D": {"op": "rotate", "angle": "@rpm", "axis": [0, 0, 1]}},
              paint({"color": ACCENT}, {"style": "fill"}),
              {"drawMesh3D": {"mesh": 2, "mode": "software-smooth"}}]
    # hub and spinner, after the blades so the blade roots disappear into them
    for mid, rad, cz, colour in ((1, 0.21, 0.0, "#FF8A99BC"),
                                (3, 0.10, 0.19, "#FFC8D4EC")):
        rotor += [{"meshPrimitive3D": {"id": mid, "primitive": "sphere", "segments": 20,
                                       "radius": rad, "center": [0, 0, cz]}},
                  {"matrix3D": {"op": "identity"}},
                  paint({"color": colour}, {"style": "fill"}),
                  {"drawMesh3D": {"mesh": mid, "mode": "software-smooth"}}]

    rotor += text_at("Gas turbine", 20.0, 32.0, 20.0, TEXT)
    rotor += text_at("fourteen blades, tapered and twisted", 20.0, 52.0, 11.0, DIM)

    STAGES = [("Compressor", "squeezes incoming air to 40 times atmospheric", GOOD),
              ("Combustor", "fuel burns at constant pressure, 1500 C", HOT),
              ("Turbine", "hot gas spins the shaft that drives the compressor", ACCENT),
              ("Exhaust", "what is left provides thrust, or turns a generator", WARM)]

    def stage(name, body, colour):
        return {"type": "row",
                "modifiers": [{"width": 410}, {"padding": 9}, {"background": PANEL}],
                "children": [
                    {"type": "box", "modifiers": [{"width": 5}, {"height": 34},
                                                  {"background": colour}],
                     "children": []},
                    {"type": "spacer", "modifiers": [{"width": 10}]},
                    {"type": "column", "modifiers": [{"width": 370}], "children": [
                        {"type": "text", "value": name, "modifiers": [],
                         "fontSize": 12.5, "color": colour},
                        {"type": "spacer", "modifiers": [{"height": 3}]},
                        {"type": "text", "value": body, "modifiers": [],
                         "fontSize": 10.0, "color": DIM}]}]}

    column = [{"type": "spacer", "modifiers": [{"height": 300}]}]
    for name, body, colour in STAGES:
        column.append(stage(name, body, colour))
        column.append({"type": "spacer", "modifiers": [{"height": 7}]})
    column.append({"type": "text",
                   "value": "the turbine drives the compressor it depends on, which is why "
                            "starting one needs an outside motor",
                   "modifiers": [], "fontSize": 9.5, "color": "#FF5E6E95"})

    return {"header": header(W, H, "A turning fourteen-blade rotor above the four stages of "
                                   "a gas turbine"),
            "root": {"type": "box",
                     "modifiers": ["fillMaxSize", {"background": INK}],
                     "children": [
                         {"type": "canvas", "modifiers": ["fillMaxSize"],
                          "commands": rotor},
                         {"type": "column",
                          "modifiers": ["fillMaxSize", {"padding": 18}],
                          "children": column}]}}


use("ENG-ME-00005")
docs["ENG-ME-00005"] = turbines()


# ── 11. ECO-MACR-00008  Interest rates — data-plot / analyze / 2D ────────────
# Three yield curves on one pair of axes. The analysis is the shape, not the level, so all
# three share a scale and the inversion is visible as a crossing rather than described.
CURVES = [("Normal", [1.9, 2.3, 2.7, 3.0, 3.3, 3.5, 3.7, 3.9], GOOD,
           "long money costs more - the usual state"),
          ("Flat", [3.4, 3.4, 3.5, 3.5, 3.5, 3.5, 3.4, 3.4], WARM,
           "the market cannot tell which way rates go next"),
          ("Inverted", [4.8, 4.5, 4.1, 3.8, 3.6, 3.4, 3.3, 3.2], HOT,
           "short money costs more - it has preceded most recessions")]
TENORS = ["3m", "1y", "2y", "3y", "5y", "7y", "10y", "30y"]


def yield_curves():
    W, H = 580, 440
    left, right, top, bottom = 70.0, 540.0, 110.0, 290.0
    cmds = []
    for r in (2, 3, 4, 5):
        y = bottom - (r - 1.5) / 3.8 * (bottom - top)
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": left, "y1": y, "x2": right, "y2": y}})
        cmds += text_at("%d%%" % r, left - 8.0, y + 4.0, 9.5, DIM, pan_x=1.0)

    n = len(TENORS)
    for ci, (name, rates, colour, note) in enumerate(CURVES):
        pid = "yc%d" % ci
        pts = [(round(left + i / (n - 1) * (right - left), 2),
                round(bottom - (v - 1.5) / 3.8 * (bottom - top), 2))
               for i, v in enumerate(rates)]
        cmds.append({"pathCreate": {"id": pid, "x": pts[0][0], "y": pts[0][1]}})
        for a, b in pts[1:]:
            cmds.append({"pathAppendLineTo": {"path": pid, "x": a, "y": b}})
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6}))
        cmds.append({"drawPath": {"path": pid}})
        for a, b in pts:
            cmds.append(paint({"color": colour}, {"style": "fill"}))
            cmds.append({"drawCircle": {"cx": a, "cy": b, "radius": 3.4}})

    for i, t in enumerate(TENORS):
        cmds += text_at(t, left + i / (n - 1) * (right - left), bottom + 18.0, 9.5,
                        DIM, pan_x=0.0)
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.3}))
    cmds.append({"drawLine": {"x1": left, "y1": bottom, "x2": right, "y2": bottom}})
    cmds += text_at("time to maturity", left, bottom + 38.0, 10.0, DIM)

    for ci, (name, rates, colour, note) in enumerate(CURVES):
        y = 332.0 + ci * 30.0
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 24.0, "top": y - 11.0,
                                  "right": 44.0, "bottom": y - 7.0}})
        cmds += text_at(name, 54.0, y, 12.5, colour)
        cmds += text_at(note, 150.0, y, 10.0, DIM)
    cmds += text_at("the shape is the signal; the level is just where rates happen to be",
                    24.0, 424.0, 10.0, "#FF5E6E95")
    return {"header": header(W, H, "Normal, flat and inverted yield curves on one pair of "
                                   "axes"),
            "root": canvas(title(cmds, W, H, "The yield curve",
                                 "what the shape is saying"))}


use("ECO-MACR-00008")
docs["ECO-MACR-00008"] = yield_curves()


# ── 12. ECO-MACR-00009  Unemployment — path-form / explain / 2D ──────────────
# The Beveridge curve, as a path with the years marked along it. Unemployment and vacancies
# normally trade off along one curve; a shift OFF the curve is the interesting event, so the
# path is drawn once and the outliers are called out.
BEVERIDGE = [(2001, 4.7, 3.3), (2003, 6.0, 2.5), (2005, 5.1, 3.0), (2007, 4.6, 3.3),
             (2009, 9.3, 1.9), (2011, 8.9, 2.3), (2013, 7.4, 2.8), (2015, 5.3, 3.6),
             (2017, 4.4, 4.0), (2019, 3.7, 4.5), (2021, 5.4, 6.6), (2023, 3.6, 5.8)]


def beveridge():
    W, H = 560, 460
    left, right, top, bottom = 80.0, 520.0, 110.0, 330.0

    def px(u):
        return left + (u - 3.0) / 7.0 * (right - left)

    def py(v):
        return bottom - (v - 1.5) / 5.6 * (bottom - top)

    cmds = []
    for u in (4, 6, 8, 10):
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": px(u), "y1": top, "x2": px(u), "y2": bottom}})
        cmds += text_at("%d%%" % u, px(u), bottom + 18.0, 9.5, DIM, pan_x=0.0)
    for v in (2, 4, 6):
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": left, "y1": py(v), "x2": right, "y2": py(v)}})
        cmds += text_at("%d%%" % v, left - 8.0, py(v) + 4.0, 9.5, DIM, pan_x=1.0)

    pts = [(round(px(u), 2), round(py(v), 2)) for _, u, v in BEVERIDGE]
    cmds.append({"pathCreate": {"id": "bev", "x": pts[0][0], "y": pts[0][1]}})
    for a, b in pts[1:]:
        cmds.append({"pathAppendLineTo": {"path": "bev", "x": a, "y": b}})
    cmds.append(paint({"color": "#FF5A7099"}, {"style": "stroke"}, {"width": 2.2}))
    cmds.append({"drawPath": {"path": "bev"}})

    for (year, u, v), (a, b) in zip(BEVERIDGE, pts):
        odd = year >= 2021
        cmds.append(paint({"color": HOT if odd else ACCENT}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": a, "cy": b, "radius": 6.0 if odd else 4.5}})
        if year % 4 == 1 or odd:
            cmds += text_at(str(year), a + 8.0, b + 4.0, 9.0,
                            HOT if odd else DIM)

    cmds += text_at("vacancies", left - 8.0, top - 6.0, 10.5, DIM, pan_x=1.0)
    cmds += text_at("unemployment", right, bottom + 38.0, 10.5, DIM, pan_x=1.0)
    cmds += text_at("normally the two trade off: fewer jobs going, more people looking",
                    24.0, 372.0, 11.0, TEXT)
    cmds += text_at("2021 sits far off the curve - many vacancies AND high unemployment, "
                    "which is a matching problem", 24.0, 392.0, 10.0, HOT)
    cmds += text_at("the path is drawn once in year order; the outliers are what it is for",
                    24.0, 412.0, 10.0, DIM)
    cmds += text_at("illustrative figures", 24.0, 436.0, 9.0, "#FF5E6E95")
    return {"header": header(W, H, "The Beveridge curve traced in year order, with the "
                                   "post-2021 outliers marked"),
            "root": canvas(title(cmds, W, H, "Jobs and job-seekers",
                                 "the Beveridge curve"))}


use("ECO-MACR-00009")
docs["ECO-MACR-00009"] = beveridge()


# ── 13. ECO-MACR-00010  Monetary policy — expression-animation / explore / 2D ─
# The lag is the subject. A rate change now reaches output in about four quarters and prices
# in about eight, so the three traces run from one clock with different delays and you can
# watch the policy arrive late.
def monetary():
    W, H = 580, 440
    left, right = 70.0, 540.0
    cmds = []
    cmds.append(var("t", "(continuousSec() * 0.22) % 1"))

    rows = [("Policy rate", 0.0, ACCENT, "changed today"),
            ("Output", 0.18, GOOD, "responds in about 4 quarters"),
            ("Inflation", 0.36, HOT, "responds in about 8 quarters")]
    for ri, (name, lag, colour, note) in enumerate(rows):
        y0 = 120.0 + ri * 96.0
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": left, "y1": y0 + 30.0,
                                  "x2": right, "y2": y0 + 30.0}})
        # a step that has travelled a fraction of the width, delayed by this row's lag
        cmds.append(var("p%d" % ri, "clamp(0.0, 1.0, @t - %.3f)" % lag))
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6}))
        # before the step: flat. after: raised. drawn as two segments meeting at the front
        cmds.append({"drawLine": {
            "x1": left, "y1": y0 + 30.0,
            "x2": "%.1f + @p%d * %.1f" % (left, ri, right - left), "y2": y0 + 30.0}})
        cmds.append({"drawLine": {
            "x1": "%.1f + @p%d * %.1f" % (left, ri, right - left), "y1": y0 + 30.0,
            "x2": "%.1f + @p%d * %.1f" % (left, ri, right - left), "y2": y0 + 4.0}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": "%.1f + @p%d * %.1f" % (left, ri, right - left),
                                    "cy": y0 + 4.0, "radius": 5.0}})
        cmds += text_at(name, left, y0 - 8.0, 12.5, colour)
        cmds += text_at(note, left + 130.0, y0 - 8.0, 10.0, DIM)

    for q in range(0, 13, 2):
        x = left + q / 12.0 * (right - left)
        cmds.append(paint({"color": "#FF22304E"}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": x, "y1": 112.0, "x2": x, "y2": 400.0}})
        cmds += text_at("Q%d" % q, x, 416.0, 9.0, DIM, pan_x=0.0)
    cmds += text_at("one clock, three delays: the policy arrives long after the decision",
                    24.0, 390.0, 11.0, TEXT)
    return {"header": header(W, H, "A policy rate change propagating to output and inflation "
                                   "with their respective lags"),
            "root": canvas(title(cmds, W, H, "Policy lags",
                                 "the decision now, the effect later"))}


use("ECO-MACR-00010")
docs["ECO-MACR-00010"] = monetary()


# ── 14. ECO-MACR-00011  Fiscal policy — particle-system / compare / 2D ───────
# The multiplier, as money that gets spent again. Two economies, same injection: where more
# of each pound is re-spent the particles keep moving through more hands, and the total is
# counted beside them.
def fiscal():
    W, H = 560, 440
    cmds = []
    panels = [("High multiplier", 0.8, GOOD, 30.0, "80p of each pound re-spent"),
              ("Low multiplier", 0.4, WARM, 290.0, "40p of each pound re-spent")]
    for pi, (name, mpc, colour, x0, note) in enumerate(panels):
        pw = 240.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": 120.0,
                                  "right": x0 + pw, "bottom": 320.0}})
        # rounds of spending, each a band; height is what survives to that round
        total = 0.0
        for r in range(6):
            share = mpc ** r
            total += share
            bw = pw * 0.86 * share
            y = 132.0 + r * 30.0
            cmds.append(paint({"color": colour}, {"style": "fill"},
                              {"alpha": 0.35 + 0.65 * share}))
            cmds.append({"drawRoundRect": {"left": x0 + 12.0, "top": y,
                                           "right": x0 + 12.0 + max(bw, 3.0),
                                           "bottom": y + 22.0, "rx": 3.0, "ry": 3.0}})
            cmds += text_at("round %d" % (r + 1), x0 + 16.0, y + 15.0, 9.0,
                            INK if share > 0.4 else DIM)
        # the people doing the spending, as particles - count scales with the multiplier
        sysid = "f%d" % pi
        cmds.append({"createParticles": {
            "id": sysid,
            "variables": ["bx", "by", "ph"],
            "initialValues": ["%.1f + rand() * %.1f" % (x0 + 14, pw - 28),
                              "%.1f + rand() * %.1f" % (326.0, 34.0),
                              "rand() * 6.283"],
            "count": int(round(total * 18))}})
        cmds.append({"particlesLoop": {
            "system": "@" + sysid,
            "equations": ["bx", "by", "ph"],
            "commands": [
                paint({"color": colour}, {"style": "fill"}, {"alpha": 0.85}),
                {"drawCircle": {"cx": "bx + sin(ph + animationTime * 1.6) * 4",
                                "cy": "by + cos(ph + animationTime * 1.4) * 3",
                                "radius": 4.0}}]}})
        cmds += text_at(name, x0 + pw / 2, 110.0, 12.5, colour, pan_x=0.0)
        cmds += text_at(note, x0 + pw / 2, 374.0, 9.5, DIM, pan_x=0.0)
        cmds += text_at("%.1fx" % total, x0 + pw / 2, 400.0, 24.0, TEXT, pan_x=0.0)
        cmds += text_at("total effect of 1 spent", x0 + pw / 2, 418.0, 9.0, DIM,
                        pan_x=0.0)
    cmds += text_at("the same injection; what differs is how much gets passed on",
                    24.0, 352.0, 11.0, TEXT)
    return {"header": header(W, H, "Two economies receiving the same fiscal injection, with "
                                   "different shares of each pound re-spent"),
            "root": canvas(title(cmds, W, H, "The multiplier",
                                 "one pound, spent again and again"))}


use("ECO-MACR-00011")
docs["ECO-MACR-00011"] = fiscal()


# ── 15. MED-HA-00001  Human Anatomy — interactive / demonstrate / 3D ─────────
# Drag to peel the layers. Nesting them as 3D shells is the only honest way to show that
# skin, muscle and skeleton occupy the same space rather than sitting side by side - and
# fading the outer ones is how you get to look inside without cutting.
def anatomy():
    W, H = 460, 520
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.95, "aspect": 1.0,
                          "near": 0.1, "far": 60.0,
                          "eye": [0.9, 0.5, 3.4], "center": [0, -0.05, 0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.35, -0.5, -0.78], "intensity": 1.0},
                {"type": "directional", "color": "#FF8FB4F2",
                 "dir": [0.5, 0.25, 0.42], "intensity": 0.3}]}}]
    cmds.append({"touchExpression": {"name": "peel", "defaultValue": 0.45,
                                     "min": 0.0, "max": 1.0, "stopMode": "gently",
                                     "expression": "touchX() / 460"}})
    cmds.append(var("p", "clamp(0.0, 1.0, @peel)"))
    cmds.append(var("spin", "continuousSec() * 0.25"))

    # torso proportions: a stack of shells, innermost drawn first
    LAYERS = [("skeleton", 0.30, "#FFE8E4D8", "0"),
              ("organs", 0.40, "#FFE8564F", "clamp(0.0, 1.0, 1.6 - @p * 2.2)"),
              ("muscle", 0.50, "#FFC25B4E", "clamp(0.0, 1.0, 1.3 - @p * 2.0)"),
              ("skin", 0.60, "#FFD9A878", "clamp(0.0, 1.0, 1.0 - @p * 1.8)")]
    for li, (name, rad, colour, alpha) in enumerate(LAYERS):
        for si, (sy, sr) in enumerate(((0.52, 0.52), (0.0, 1.0), (-0.56, 0.78))):
            mid = 10 + li * 4 + si
            cmds += [{"meshPrimitive3D": {"id": mid, "primitive": "sphere",
                                          "segments": 18,
                                          "radius": round(rad * sr, 4),
                                          "center": [0, 0, 0]}},
                     {"matrix3D": {"op": "identity"}},
                     {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                     {"matrix3D": {"op": "translate", "x": 0, "y": sy * 0.62, "z": 0}}]
            if alpha == "0":
                cmds.append(paint({"color": colour}, {"style": "fill"}))
                cmds.append({"drawMesh3D": {"mesh": mid, "mode": "software-smooth"}})
            else:
                # outer shells are wireframe, because a filled one would hide everything
                # inside it - mesh alpha does not blend (F-004)
                cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.0},
                                  {"alpha": alpha}))
                cmds.append({"drawMesh3D": {"mesh": mid, "mode": "software-smooth",
                                            "wireframe": True}})

    for li, (name, rad, colour, alpha) in enumerate(reversed(LAYERS)):
        y = 372.0 + li * 20.0
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": 30.0, "cy": y - 4.0, "radius": 6.0}})
        cmds += text_at(name, 46.0, y, 11.0, DIM)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 2.0}))
    cmds.append({"drawLine": {"x1": 200.0, "y1": 400.0, "x2": 436.0, "y2": 400.0}})
    cmds.append(paint({"color": TEXT}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": "200 + @p * 236", "cy": 400.0, "radius": 7.0}})
    cmds += text_at("skin on", 200.0, 420.0, 9.5, DIM)
    cmds += text_at("bone only", 436.0, 420.0, 9.5, DIM, pan_x=1.0)
    cmds += text_at("drag right to peel the layers away", 24.0, 462.0, 11.5, TEXT)
    cmds += text_at("the shells occupy the same space - they are not stacked side by side",
                    24.0, 482.0, 10.0, DIM)
    cmds += text_at("outer layers are wireframe, since a filled shell would hide what is "
                    "inside it", 24.0, 500.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "Drag to peel skin, muscle and organs away from the "
                                   "skeleton, as nested 3D shells"),
            "root": canvas(title(cmds, W, H, "Layers of the body",
                                 "skin, muscle, organs, bone"))}


use("MED-HA-00001")
docs["MED-HA-00001"] = anatomy()


# ── 16. MED-PHYS-00002  Physiology — raster-and-text / simulate / 2D ─────────
# A monitor. The numbers are the document, so they are set large and in a fixed column, and
# the traces behind them are deliberately secondary - which is how a real bedside monitor is
# read, and the opposite of how a chart is.
def physiology():
    W, H = 580, 420
    cmds = []
    cmds.append(var("t", "continuousSec()"))
    # one cardiac cycle per 0.85 s; the beat phase drives both the trace and the numbers
    cmds.append(var("beat", "(@t / 0.85) % 1"))

    rows = [("HR", "72", "bpm", GOOD, 0),
            ("SpO2", "98", "%", ACCENT, 1),
            ("BP", "118/76", "mmHg", WARM, 2),
            ("RR", "14", "/min", "#FFBFCBE4", 3)]
    for label, value, unit, colour, i in rows:
        y = 118.0 + i * 68.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 24.0, "top": y - 26.0,
                                  "right": 556.0, "bottom": y + 32.0}})
        cmds += text_at(label, 40.0, y - 6.0, 11.0, DIM)
        cmds.append(paint({"color": colour}, {"style": "fill"}, {"textSize": 34.0}))
        cmds.append({"drawTextAnchored": {"text": value, "x": 40.0, "y": y + 24.0,
                                          "panX": -1.0, "panY": 0.0, "flags": 0}})
        cmds += text_at(unit, 176.0, y + 22.0, 11.0, DIM)

        # the trace, secondary: a repeating waveform scrolling behind the number
        if i == 0:
            for k in range(58):
                u = k / 57.0
                ph = (u * 3.0) % 1.0
                # a crude QRS: small p, tall spike, small t
                v = (0.12 * math.sin(ph * 6.28)
                     + (0.95 if 0.30 < ph < 0.34 else 0.0)
                     - (0.35 if 0.34 <= ph < 0.38 else 0.0))
                x = 250.0 + u * 290.0
                yy = y + 4.0 - v * 26.0
                if k:
                    cmds.append(paint({"color": colour}, {"style": "stroke"},
                                      {"width": 1.8}))
                    cmds.append({"drawLine": {"x1": round(px_, 1), "y1": round(py_, 1),
                                              "x2": round(x, 1), "y2": round(yy, 1)}})
                px_, py_ = x, yy
        else:
            for k in range(58):
                u = k / 57.0
                v = math.sin(u * 9.0 + i * 1.3) * (0.4 if i == 3 else 0.22)
                x = 250.0 + u * 290.0
                yy = y + 4.0 - v * 26.0
                if k:
                    cmds.append(paint({"color": colour}, {"style": "stroke"},
                                      {"width": 1.4}, {"alpha": 0.6}))
                    cmds.append({"drawLine": {"x1": round(px_, 1), "y1": round(py_, 1),
                                              "x2": round(x, 1), "y2": round(yy, 1)}})
                px_, py_ = x, yy

    # the beat marker, the one live element
    cmds.append(paint({"color": HOT}, {"style": "fill"},
                      {"alpha": "clamp(0.0, 1.0, 1 - @beat * 5)"}))
    cmds.append({"drawCircle": {"cx": 540.0, "cy": 92.0, "radius": 9.0}})
    cmds += text_at("a resting adult at rest, in the normal range on every line",
                    24.0, 388.0, 11.0, TEXT)
    cmds += text_at("numbers first, traces second - which is how a monitor is read",
                    24.0, 406.0, 10.0, DIM)
    return {"header": header(W, H, "A bedside monitor with four vital signs set large and "
                                   "their traces behind them"),
            "root": canvas(title(cmds, W, H, "Vital signs", "what a monitor shows"))}


use("MED-PHYS-00002")
docs["MED-PHYS-00002"] = physiology()


# ── write ───────────────────────────────────────────────────────────────────────
def main():
    for doc_id, doc in docs.items():
        (OUT / ("%s.json" % doc_id)).write_text(json.dumps(doc, indent=1) + "\n")
    print("  wrote %d documents to %s" % (len(docs), OUT.name))
    import collections
    print("  palettes: %s" % dict(sorted(collections.Counter(PALETTE_USED.values()).items())))


if __name__ == "__main__":
    main()
