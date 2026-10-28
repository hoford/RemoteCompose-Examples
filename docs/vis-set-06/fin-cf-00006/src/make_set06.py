#!/usr/bin/env python3
"""Build set 6 of the visualization programme: 16 documents.

    python3 work/set-06/make_set06.py

Work order from `python3 tools/visplan.py set 6`. Three 3D slots: fusion, mutations and
revenue. Fusion and revenue both earn it - two nuclei approaching each other is a problem
about distance in space, and a revenue bridge is the one chart people genuinely draw as
blocks. Mutations is the weakest of the three and is kept honest by making the third
dimension carry the DNA helix rather than decorating a flat diagram.

Helper block carried from set 5. Two rules were added to it there and both are load-bearing
here: a 3D scene gets a canvas that fills the DOCUMENT, never a sized card (F-013), and a
translate that follows a rotate rides the rotated frame, so position a scene with the camera.
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


def oriented_box(verts, normals, uv, idx, centre, axis, half_len, hw, hh):
    """A box along an arbitrary axis: centre, unit axis, half length and two half widths.

    mesh_box only makes axis-aligned boxes, which is wrong for anything that points in a
    direction the document chose - a helix rung, a strut, a vector. Winding per F-008.
    """
    ax, ay, az = axis
    ln = math.sqrt(ax * ax + ay * ay + az * az) or 1.0
    ax, ay, az = ax / ln, ay / ln, az / ln
    up = (0.0, 1.0, 0.0) if abs(ay) < 0.9 else (1.0, 0.0, 0.0)
    sx = ay * up[2] - az * up[1]
    sy = az * up[0] - ax * up[2]
    sz = ax * up[1] - ay * up[0]
    sl = math.sqrt(sx * sx + sy * sy + sz * sz) or 1.0
    sx, sy, sz = sx / sl, sy / sl, sz / sl
    ux = sy * az - sz * ay
    uy = sz * ax - sx * az
    uz = sx * ay - sy * ax
    cx, cy, cz = centre
    corners = []
    for su in (-1, 1):
        for sv in (-1, 1):
            for sw in (-1, 1):
                corners.append((cx + ax * half_len * su + sx * hw * sv + ux * hh * sw,
                                cy + ay * half_len * su + sy * hw * sv + uy * hh * sw,
                                cz + az * half_len * su + sz * hw * sv + uz * hh * sw))
    # corners indexed by (u,v,w) bits; six faces as quads
    def q(i0, i1, i2, i3, n):
        base = len(verts) // 3
        for i in (i0, i1, i2, i3):
            verts.extend(round(c, 5) for c in corners[i])
            normals.extend(round(c, 5) for c in n)
            uv.extend((0.0, 0.0))
        idx.extend([base, base + 2, base + 1, base, base + 3, base + 2])
    q(0, 1, 3, 2, (-ax, -ay, -az))
    q(4, 6, 7, 5, (ax, ay, az))
    q(0, 4, 5, 1, (-sx, -sy, -sz))
    q(2, 3, 7, 6, (sx, sy, sz))
    q(0, 2, 6, 4, (-ux, -uy, -uz))
    q(1, 5, 7, 3, (ux, uy, uz))


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



# ── 1. PHY-NP-00019  Fusion — static-diagram / simulate / 3D ──────────────────
# Two nuclei in space, closing and separating, with the Coulomb barrier they have to climb
# drawn flat beneath them. The 3D is doing real work: the whole difficulty of fusion is how
# close two positively charged things must get, and a distance is what the top half shows.
def fusion():
    W, H = 480, 600
    # The two bands are fixed first and nothing is allowed to cross them: the nuclei live
    # above NUC_FLOOR, the barrier panel below it. The 3D projects into the document (it has
    # a full-size canvas, per F-013), so the nuclei are placed by aiming the camera.
    NUC_Y, NUC_FLOOR = 206.0, 300.0
    PAN_TOP, PAN_BOT = 332.0, 540.0

    # camera centred on the nuclei band: shifting `center` down lifts the image
    LIFT = (H / 2.0 - NUC_Y) / 146.0        # ~146 px per world unit at this distance
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.78,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [0.0, -LIFT, 5.2], "center": [0.0, -LIFT, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.4, -0.5, -0.76], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.3, 0.5], "intensity": 0.45}]}}]
    cmds.append(var("ph", "continuousSec() * 0.25 - floor(continuousSec() * 0.25)"))
    cmds.append(var("gap", "0.95 - 0.80 * @ph"))        # closes from 0.95 to 0.15
    for mid, rad, colour, sign in ((1, 0.17, ACCENT, -1.0), (2, 0.15, WARM, 1.0)):
        cmds.append({"meshPrimitive3D": {"id": mid, "primitive": "sphere", "segments": 20,
                                         "radius": rad, "center": [0, 0, 0]}})
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "translate",
                               "x": "%.1f * @gap" % sign, "y": 0.0, "z": 0.0}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mid, "mode": "software-smooth"}}]
    # labels sit just under the nuclei band, not at an arbitrary y
    cmds += text_at("deuterium", 150.0, NUC_FLOOR - 6, 10.5, ACCENT, pan_x=0.0)
    cmds += text_at("tritium", 330.0, NUC_FLOOR - 6, 10.5, WARM, pan_x=0.0)
    cmds += text_at("they have to get this close", 240.0, NUC_FLOOR + 14, 9.5, DIM,
                    pan_x=0.0)

    # the barrier, in its own band: a well at small separation, a peak to climb, a 1/r tail
    bx0, bx1 = 40.0, 440.0
    base, top = PAN_BOT - 26, PAN_TOP + 30
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": bx0, "top": PAN_TOP, "right": bx1,
                              "bottom": PAN_BOT}})
    zero_y = PAN_TOP + 34.0 + 46.0
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": bx0 + 10, "y1": zero_y, "x2": bx1 - 10, "y2": zero_y}})

    def V(r):
        tail = 0.30 / max(r, 0.30)
        well = 2.6 * math.exp(-((r - 0.14) / 0.07) ** 2)
        return tail - well

    R0, R1 = 0.08, 1.0
    SCALE = 46.0
    def px(r):
        return bx0 + 26 + (r - R0) / (R1 - R0) * (bx1 - bx0 - 52)
    def py(v):
        return zero_y - v * SCALE
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 2.4},
                      {"strokeCap": "round"}))
    prev = None
    for i in range(81):
        r = R0 + (R1 - R0) * i / 80.0
        pt = (px(r), py(V(r)))
        if prev:
            cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1],
                                      "x2": pt[0], "y2": pt[1]}})
        prev = pt
    # the peak and the well, each labelled where it actually is
    cmds.append(paint({"color": HOT}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": px(0.30), "cy": py(V(0.30)), "radius": 3.5}})
    cmds += text_at("Coulomb barrier", px(0.30) + 10, py(V(0.30)) - 4, 10.0, HOT)
    cmds.append(paint({"color": GOOD}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": px(0.14), "cy": py(V(0.14)), "radius": 3.5}})
    cmds += text_at("strong force well", px(0.14) + 12, py(V(0.14)) + 4, 10.0, GOOD)
    cmds += text_at("separation", bx1 - 14, zero_y - 8, 9.5, DIM, pan_x=1.0)

    title(cmds, W, H, "Fusion", "two nuclei, and the hill between them")
    cmds += text_at("D + T  ->  He-4 + n  +  17.6 MeV", 240.0, 572.0, 11.5, GOOD,
                    pan_x=0.0)
    return {"header": header(W, H, "Two nuclei closing in 3D above the Coulomb barrier "
                                   "they must climb to fuse"),
            "root": canvas(cmds, INK)}


# ── 2. PHY-NP-00020  Nuclear reactions — annotated-layout / analyze / 2D ──────
# Five reactions as cards, each with what goes in, what comes out, and the energy. The
# layout is the argument: the Q values are in the same place in every card, so the one that
# dwarfs the others is visible without reading a word.
def reactions():
    W, H = 460, 620
    ROWS = [("Alpha decay", "U-238", "Th-234 + He-4", "4.3 MeV", 0.04, WARM),
            ("Beta minus", "C-14", "N-14 + e- + anti-v", "0.16 MeV", 0.01, ACCENT),
            ("Gamma", "Co-60*", "Co-60 + photon", "1.3 MeV", 0.02, DIM),
            ("Fission", "U-235 + n", "Ba-141 + Kr-92 + 3n", "200 MeV", 0.52, HOT),
            ("Fusion", "D + T", "He-4 + n", "17.6 MeV", 1.00, GOOD)]

    def card(name, lhs, rhs, q, frac, colour):
        return {"type": "column",
                "modifiers": [{"width": 420}, {"padding": 11}, {"background": PANEL}],
                "children": [
                    {"type": "row", "modifiers": [{"width": 398}], "children": [
                        {"type": "text", "value": name, "modifiers": [],
                         "fontSize": 13.0, "color": colour},
                        {"type": "spacer", "modifiers": [{"width": 1}]},
                        {"type": "text", "value": q, "modifiers": [],
                         "fontSize": 12.0, "color": TEXT}]},
                    {"type": "spacer", "modifiers": [{"height": 5}]},
                    {"type": "row", "modifiers": [], "children": [
                        {"type": "text", "value": lhs, "modifiers": [],
                         "fontSize": 10.5, "color": DIM},
                        {"type": "spacer", "modifiers": [{"width": 8}]},
                        {"type": "text", "value": "->", "modifiers": [],
                         "fontSize": 10.5, "color": RULE},
                        {"type": "spacer", "modifiers": [{"width": 8}]},
                        {"type": "text", "value": rhs, "modifiers": [],
                         "fontSize": 10.5, "color": TEXT}]},
                    {"type": "spacer", "modifiers": [{"height": 7}]},
                    # the energy bar, on one scale across all five cards
                    {"type": "box", "modifiers": [{"width": 398}, {"height": 7},
                                                  {"background": RULE}],
                     "children": [
                        {"type": "box",
                         "modifiers": [{"width": max(3, int(398 * frac))}, {"height": 7},
                                       {"background": colour}], "children": []}]}]}

    kids = [{"type": "text", "value": "Nuclear reactions", "modifiers": [],
             "fontSize": 19.0, "color": TEXT},
            {"type": "spacer", "modifiers": [{"height": 3}]},
            {"type": "text", "value": "same scale on every bar, which is the point",
             "modifiers": [], "fontSize": 11.0, "color": DIM},
            {"type": "spacer", "modifiers": [{"height": 12}]}]
    for r in ROWS:
        kids.append(card(*r))
        kids.append({"type": "spacer", "modifiers": [{"height": 8}]})
    kids.append({"type": "text",
                 "value": "fusion releases more per nucleon than fission, but needs the "
                          "hill in the previous document climbed first",
                 "modifiers": [], "fontSize": 9.5, "color": DIM})
    return {"header": header(W, H, "Five nuclear reactions as cards, their energies on one "
                                   "shared scale"),
            "root": {"type": "column",
                     "modifiers": ["fillMaxSize", {"padding": 18}, {"background": INK}],
                     "children": kids}}


# ── 3. BIO-BIOC-00018  Photosynthesis — data-plot / explain / 2D ──────────────
# Chlorophyll a and b absorb at the ends of the visible range and not in the middle, which
# is exactly why leaves are green: the green is what is left over. Plotting the action
# spectrum on top of the two absorptions is what turns that from a claim into a reading.
def photosynthesis():
    W, H = 560, 420
    def band(c, w0, s0, a0, w1, s1, a1):
        return [a0 * math.exp(-((c - w0) / s0) ** 2) + a1 * math.exp(-((c - w1) / s1) ** 2)]
    N = 48
    lo, hi = 400.0, 700.0
    chl_a, chl_b, action = [], [], []
    for i in range(N):
        w = lo + (hi - lo) * i / (N - 1)
        chl_a.append(0.95 * math.exp(-((w - 430) / 17) ** 2)
                     + 0.72 * math.exp(-((w - 662) / 14) ** 2))
        chl_b.append(0.68 * math.exp(-((w - 453) / 18) ** 2)
                     + 0.44 * math.exp(-((w - 642) / 15) ** 2))
        action.append(min(1.0, 0.86 * (chl_a[-1] + 0.55 * chl_b[-1]) + 0.05))
    cmds = []
    px0, px1, py0, py1 = 60.0, 530.0, 110.0, 340.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    # the visible spectrum itself along the axis - the band the data is about
    for i in range(60):
        w = lo + (hi - lo) * i / 59.0
        x = px0 + (px1 - px0) * i / 60.0
        cmds.append(paint({"color": spectral(w)}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x, "top": py1 + 4, "right": x + (px1 - px0) / 60.0 + 1,
                                  "bottom": py1 + 20}})
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    for f in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = py1 - f * (py1 - py0)
        cmds.append({"drawLine": {"x1": px0, "y1": y, "x2": px1, "y2": y}})
        cmds += text_at("%.0f%%" % (f * 100), px0 - 6, y + 4, 9.0, DIM, pan_x=1.0)
    for w in (400, 500, 600, 700):
        x = px0 + (px1 - px0) * (w - lo) / (hi - lo)
        cmds += text_at("%d" % w, x, py1 + 34, 9.5, DIM, pan_x=0.0)
    cmds += text_at("nm", px1, py1 + 34, 9.5, DIM, pan_x=1.0)

    for series, colour, width in ((action, DIM, 5.0), (chl_a, GOOD, 2.6),
                                  (chl_b, ACCENT, 2.6)):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": width},
                          {"strokeCap": "round"}))
        prev = None
        for i, v in enumerate(series):
            x = px0 + (px1 - px0) * i / (N - 1.0)
            y = py1 - v * (py1 - py0)
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": x, "y2": y}})
            prev = (x, y)
    # the green gap, named where it happens
    cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 1.2}))
    gx = px0 + (px1 - px0) * (550 - lo) / (hi - lo)
    cmds.append({"drawLine": {"x1": gx, "y1": py0 + 6, "x2": gx, "y2": py1}})
    cmds += text_at("neither pigment absorbs here,", gx + 8, py0 + 36, 10.0, WARM)
    cmds += text_at("so this is the light a leaf throws back", gx + 8, py0 + 52, 10.0, WARM)

    for i, (lbl, colour) in enumerate((("chlorophyll a", GOOD), ("chlorophyll b", ACCENT),
                                       ("rate of photosynthesis", DIM))):
        y = 372.0 + 0.0
        x = 60.0 + i * 168.0
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 3.0}))
        cmds.append({"drawLine": {"x1": x, "y1": y - 4, "x2": x + 18, "y2": y - 4}})
        cmds += text_at(lbl, x + 24, y, 10.0, DIM)
    title(cmds, W, H, "Photosynthesis", "what chlorophyll takes, and what it leaves")
    return {"header": header(W, H, "Absorption spectra of chlorophyll a and b against the "
                                   "rate of photosynthesis, over the visible band"),
            "root": canvas(cmds, INK)}


def spectral(nm):
    """Approximate sRGB for a wavelength, as a document colour. Only used for the strip
    under the photosynthesis axis, where the band being real matters to the reading."""
    if nm < 440:
        r, g, b = -(nm - 440) / 60.0, 0.0, 1.0
    elif nm < 490:
        r, g, b = 0.0, (nm - 440) / 50.0, 1.0
    elif nm < 510:
        r, g, b = 0.0, 1.0, -(nm - 510) / 20.0
    elif nm < 580:
        r, g, b = (nm - 510) / 70.0, 1.0, 0.0
    elif nm < 645:
        r, g, b = 1.0, -(nm - 645) / 65.0, 0.0
    else:
        r, g, b = 1.0, 0.0, 0.0
    return "#FF%02X%02X%02X" % tuple(int(255 * max(0.0, min(1.0, c)) * 0.92) for c in (r, g, b))


# ── 4. BIO-GENE-00019  Mendelian inheritance — path-form / explore / 2D ──────
# A Punnett square built entirely from paths, with the four outcomes drawn as closed
# polygons rather than rectangles so the 3:1 ratio can be shaded as one shape per genotype.
def mendel():
    W, H = 480, 560
    cmds = []
    gx, gy, cell = 150.0, 150.0, 92.0
    cmds += text_at("Aa  x  Aa", 240.0, 112.0, 13.0, TEXT, pan_x=0.0)
    for i, g in enumerate(("A", "a")):
        cmds += text_at(g, gx + cell * (i + 0.5), gy - 14, 14.0, ACCENT, pan_x=0.0)
        cmds += text_at(g, gx - 20, gy + cell * (i + 0.5) + 5, 14.0, WARM, pan_x=1.0)
    OUT = [("AA", GOOD, "homozygous dominant"), ("Aa", GOOD, "heterozygous"),
           ("Aa", GOOD, "heterozygous"), ("aa", HOT, "homozygous recessive")]
    pid = "cell0"
    pids = iter(["c%d" % i for i in range(4)])
    for r in range(2):
        for c in range(2):
            geno, colour, _ = OUT[r * 2 + c]
            x0, y0 = gx + c * cell, gy + r * cell
            cmds.append({"pathCreate": {"id": pid, "x": x0 + 4, "y": y0 + 4}})
            for (px, py) in ((x0 + cell - 4, y0 + 4), (x0 + cell - 4, y0 + cell - 4),
                             (x0 + 4, y0 + cell - 4)):
                cmds.append({"pathAppendLineTo": {"path": pid, "x": px, "y": py}})
            cmds.append({"pathAppendClose": {"path": pid}})
            cmds.append(paint({"color": colour if geno != "Aa" else PANEL},
                              {"style": "fill"}))
            cmds.append({"drawPath": {"path": pid}})
            cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.4}))
            cmds.append({"drawPath": {"path": pid}})
            cmds += text_at(geno, x0 + cell / 2, y0 + cell / 2 + 6, 17.0,
                            INK if geno != "Aa" else TEXT, pan_x=0.0)
            pid = next(pids, "cx")
    # Everything that is not the bar is drawn first - the bar's clip is permanent for the
    # rest of this canvas (F-021), and on the first attempt it swallowed the title.
    title(cmds, W, H, "A monohybrid cross",
          "one gene, two alleles, four equally likely ways")
    cmds += text_at("the ratio is of appearance, not of genotype: two of the three "
                    "look alike", 60.0, 454.0, 10.0, DIM)
    cmds += text_at("and carry a copy of the recessive allele they do not show",
                    60.0, 470.0, 10.0, DIM)
    # the ratio bar, clipped so the three-quarters reads as a quantity not a label
    bx0, bx1, by = 60.0, 420.0, 400.0
    # Order matters and only in one direction: the clip below cannot be undone, so the red
    # quarter and both labels are laid down FIRST and the green three-quarters is clipped
    # over the top of them.
    cmds.append(paint({"color": HOT}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": bx0, "top": by, "right": bx1, "bottom": by + 26}})
    cmds += text_at("1", bx1 - 14, by + 18, 11.0, INK, pan_x=1.0)
    cmds.append({"clipRect": {"left": bx0, "top": by, "right": bx0 + (bx1 - bx0) * 0.75,
                              "bottom": by + 26}})
    cmds.append(paint({"color": GOOD}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": bx0, "top": by, "right": bx1, "bottom": by + 26}})
    cmds += text_at("3 show the dominant trait", bx0 + 10, by + 18, 11.0, INK)
    return {"header": header(W, H, "A Punnett square drawn as paths, with the 3:1 ratio of "
                                   "appearance shown as a clipped bar"),
            "root": canvas(cmds, INK)}


# ── 5. BIO-GENE-00020  Chromosomes — expression-animation / compare / 2D ─────
# Mitosis and meiosis on the same clock, side by side. Running them together is the only
# way to make the difference legible: meiosis is mitosis with one extra division and no
# second round of copying, and a reader can watch the chromosome count halve.
def chromosomes():
    W, H = 580, 440
    cmds = [var("t", "continuousSec() * 0.22 - floor(continuousSec() * 0.22)")]
    for col, (name, divisions, note) in enumerate(
            (("Mitosis", 1, "two cells, each a full copy"),
             ("Meiosis", 2, "four cells, each with half"))):
        cx = 150.0 + col * 290.0
        cmds += text_at(name, cx, 110.0, 15.0, TEXT if col == 0 else ACCENT, pan_x=0.0)
        cmds += text_at(note, cx, 128.0, 10.0, DIM, pan_x=0.0)
        # the parent cell, which splits once or twice depending on the column
        for stage in range(divisions + 1):
            n_cells = 2 ** stage
            y = 180.0 + stage * 92.0
            # how far this split has progressed, as a fraction of the whole cycle
            frac = "clamp(0.0, 1.0, (@t - %.3f) * %.2f)" % (
                stage * 0.33, 1.0 / 0.33)
            for k in range(n_cells):
                spread = (k - (n_cells - 1) / 2.0) * 58.0
                cmds.append(var("s%d%d%d" % (col, stage, k),
                                "%.1f * %s" % (spread, frac) if stage else "0.0"))
                cmds.append(paint({"color": PANEL}, {"style": "fill"}))
                cmds.append({"drawCircle": {"cx": "%.1f + @s%d%d%d" % (cx, col, stage, k),
                                            "cy": y, "radius": 26.0}})
                cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.2}))
                cmds.append({"drawCircle": {"cx": "%.1f + @s%d%d%d" % (cx, col, stage, k),
                                            "cy": y, "radius": 26.0}})
                # chromosomes inside: 4 in the parent, halving only in meiosis
                n_chrom = 4 if stage == 0 else (4 if col == 0 else max(2, 4 // (2 ** stage)))
                for c in range(n_chrom):
                    a = c * 2 * math.pi / n_chrom + 0.4
                    colour = (GOOD, WARM, ACCENT, HOT)[c % 4]
                    cmds.append(paint({"color": colour}, {"style": "stroke"},
                                      {"width": 3.4}, {"strokeCap": "round"}))
                    cmds.append({"drawLine": {
                        "x1": "%.1f + @s%d%d%d" % (cx + 11 * math.cos(a), col, stage, k),
                        "y1": y + 11 * math.sin(a),
                        "x2": "%.1f + @s%d%d%d" % (cx + 11 * math.cos(a) + 7 * math.cos(a + 1.5),
                                                   col, stage, k),
                        "y2": y + 11 * math.sin(a) + 7 * math.sin(a + 1.5)}})
            if stage < divisions:
                cmds += text_at("divide", cx, y + 48, 9.5, DIM, pan_x=0.0)
        cmds += text_at("%d chromosomes each" % (4 if col == 0 else 2),
                        cx, 180.0 + divisions * 92.0 + 54.0, 11.0,
                        GOOD if col == 0 else ACCENT, pan_x=0.0)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": 290.0, "y1": 100.0, "x2": 290.0, "y2": 400.0}})
    title(cmds, W, H, "Two ways to divide", "same clock, so the extra division is visible")
    return {"header": header(W, H, "Mitosis and meiosis animated side by side on one clock, "
                                   "so the halving of chromosome number is visible"),
            "root": canvas(cmds, INK)}


# ── 6. BIO-GENE-00021  Mutations — particle-system / demonstrate / 3D ────────
# A helix in 3D with bases riding it, and a stream of mutagen particles crossing the frame.
# The particles are the point: most pass through and nothing happens, and the few that land
# leave a mark that stays. That ratio is the honest picture of mutation rate.
def mutations():
    W, H = 500, 580
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.85,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [2.2, 0.9, 3.0], "center": [0, 0.15, 0], "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.45, -0.5, -0.74], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.3, 0.45], "intensity": 0.45}]}}]
    cmds.append(var("spin", "continuousSec() * 0.5"))
    # the two backbones, as boxes stepped along a helix
    RUNGS = 16
    verts, normals, uv, idx = [], [], [], []
    for i in range(RUNGS):
        t = i / (RUNGS - 1.0)
        a = t * 3.6 * math.pi
        y = (t - 0.5) * 2.0
        for sgn in (1, -1):
            x, z = 0.42 * math.cos(a) * sgn, 0.42 * math.sin(a) * sgn
            mesh_box(verts, normals, uv, idx,
                     (x - 0.055, y - 0.062, z - 0.055), (x + 0.055, y + 0.062, z + 0.055))
    cmds.append({"defineMesh3D": {"id": 1, "verts": [round(v, 5) for v in verts],
                                  "normals": normals, "uv": uv, "indices": idx}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": DIM}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]
    # the rungs, split into healthy and the three that got hit
    HIT = (4, 9, 13)
    for group, colour, mid in ((tuple(i for i in range(RUNGS) if i not in HIT), GOOD, 2),
                               (HIT, HOT, 3)):
        v2, n2, u2, i2 = [], [], [], []
        for i in group:
            t = i / (RUNGS - 1.0)
            a = t * 3.6 * math.pi
            y = (t - 0.5) * 2.0
            # An axis-aligned box cannot be a diagonal rung - the first version spanned the
            # full x and z extent and read as a stack of slabs rather than a ladder. This
            # one is built on the rung's own axis.
            dx, dz = math.cos(a), math.sin(a)
            oriented_box(v2, n2, u2, i2, (0.0, y, 0.0),
                         (dx, 0.0, dz), 0.42, 0.030, 0.030)
        cmds.append({"defineMesh3D": {"id": mid, "verts": [round(v, 5) for v in v2],
                                      "normals": n2, "uv": u2, "indices": i2}})
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mid, "mode": "software-smooth"}}]

    # the mutagen stream, flat over the top: many cross, three landed
    cmds.append({"createParticles": {
        "id": "mutagen", "count": 90,
        "variables": ["px", "py", "pv", "pw"],
        "initialValues": ["20 + rand() * 460", "120 + rand() * 350",
                          "34 + rand() * 62", "0.6 + rand() * 1.8"]}})
    cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 1.6},
                      {"strokeCap": "round"}))
    # The motion lives in `equations`, one per declared variable, not in the draw call:
    # a particle's state is advanced by the system and only then drawn.
    cmds.append({"particlesLoop": {
        "system": "@mutagen",
        "equations": ["(px + pv * 0.02) % 500", "py", "pv", "pw"],
        "commands": [
            {"drawLine": {"x1": "@px", "y1": "@py",
                          "x2": "@px + @pw * 5", "y2": "@py + @pw * 2"}}]}})
    title(cmds, W, H, "Mutation", "most of what crosses a cell does nothing at all")
    cmds += text_at("three bases altered", 250.0, 538.0, 11.0, HOT, pan_x=0.0)
    cmds += text_at("out of ninety strikes", 250.0, 556.0, 10.0, DIM, pan_x=0.0)
    return {"header": header(W, H, "A rotating DNA helix in 3D with three damaged bases, "
                                   "under a stream of mutagen particles"),
            "root": canvas(cmds, INK)}


# ── 7. MTH-ALGE-00006  Equations — interactive / simulate / 2D ───────────────
# Drag c and watch the roots of x^2 + bx + c meet and vanish. The discriminant is the whole
# story and it is drawn as a quantity, so the moment the parabola lifts off the axis is the
# same moment the bar crosses zero.
def equations():
    W, H = 520, 560
    B = 1.4
    cmds = [{"touchExpression": {"name": "drag", "defaultValue": 260.0, "min": 60.0,
                                 "max": 460.0, "expression": "touchX()"}},
            var("c", "(@drag - 60.0) / 400.0 * 3.0 - 1.2"),      # c from -1.2 to 1.8
            var("disc", "%.2f - 4.0 * @c" % (B * B)),
            var("real", "@disc * 1000.0")]
    px0, px1, py0, py1 = 60.0, 460.0, 130.0, 370.0
    cx, cy = (px0 + px1) / 2, (py0 + py1) / 2 + 40
    sx, sy = (px1 - px0) / 6.0, 46.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": px0, "y1": cy, "x2": px1, "y2": cy}})
    cmds.append({"drawLine": {"x1": cx, "y1": py0, "x2": cx, "y2": py1}})
    for k in (-2, -1, 1, 2):
        cmds += text_at("%d" % k, cx + k * sx, cy + 15, 9.0, DIM, pan_x=0.0)
    # the parabola, as 40 segments whose heights follow @c
    # No clipRect here. A clip cannot be widened again (F-021), so clipping the curve
    # would confine the discriminant bar, the labels and the title drawn after it. The
    # curve is kept inside the panel by clamping its y instead.
    cmds.append(paint({"color": ACCENT}, {"style": "stroke"}, {"width": 2.6},
                      {"strokeCap": "round"}))
    for i in range(40):
        u0 = -3.0 + 6.0 * i / 40.0
        u1 = -3.0 + 6.0 * (i + 1) / 40.0
        cmds.append({"drawLine": {
            "x1": cx + u0 * sx,
            "y1": "clamp(%.1f, %.1f, %.4f - (%.4f + @c) * %.2f)"
                  % (py0, py1, cy, u0 * u0 + B * u0, sy),
            "x2": cx + u1 * sx,
            "y2": "clamp(%.1f, %.1f, %.4f - (%.4f + @c) * %.2f)"
                  % (py0, py1, cy, u1 * u1 + B * u1, sy)}})
    # the roots exist only while the discriminant is positive
    cmds.append({"conditionalOperations": {
        "condition": "gt", "v1": "@disc", "v2": 0.0,
        "commands": [
            paint({"color": GOOD}, {"style": "fill"}),
            {"drawCircle": {"cx": "%.2f + (-%.2f - sqrt(@disc)) / 2.0 * %.2f" % (cx, B, sx),
                            "cy": cy, "radius": 6.0}},
            {"drawCircle": {"cx": "%.2f + (-%.2f + sqrt(@disc)) / 2.0 * %.2f" % (cx, B, sx),
                            "cy": cy, "radius": 6.0}},
            paint({"color": GOOD}, {"style": "fill"}, {"textSize": 11.0}),
            {"drawTextAnchored": {"text": "two real roots", "x": 260.0, "y": 398.0,
                                  "panX": 0.0, "panY": 0.0, "flags": 0}}]}})
    cmds.append({"conditionalOperations": {
        "condition": "lt", "v1": "@disc", "v2": 0.0,
        "commands": [
            paint({"color": HOT}, {"style": "fill"}, {"textSize": 11.0}),
            {"drawTextAnchored": {"text": "no real roots - the curve has left the axis",
                                  "x": 260.0, "y": 398.0, "panX": 0.0, "panY": 0.0,
                                  "flags": 0}}]}})
    # the discriminant as a signed bar about its own zero
    zx, zy = 260.0, 446.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": 60.0, "top": zy - 13, "right": 460.0,
                              "bottom": zy + 13}})
    cmds.append(paint({"color": GOOD}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": zx, "top": zy - 11,
                              "right": "clamp(%.1f, 458.0, %.1f + @disc * 46.0)" % (zx, zx),
                              "bottom": zy + 11}})
    cmds.append(paint({"color": HOT}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": "clamp(62.0, %.1f, %.1f + @disc * 46.0)" % (zx, zx),
                              "top": zy - 11, "right": zx, "bottom": zy + 11}})
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.4}))
    cmds.append({"drawLine": {"x1": zx, "y1": zy - 15, "x2": zx, "y2": zy + 15}})
    cmds += text_at("b² - 4c", 60.0, zy - 22, 10.5, DIM)
    cmds += text_at("c =", 60.0, 500.0, 11.0, DIM)
    cmds += [{"variable": {"name": "clabel", "commit": True,
                           "value": {"type": "textFromFloat", "value": "@c",
                                     "whole": 1, "decimal": 2}}},
             paint({"color": TEXT}, {"style": "fill"}, {"textSize": 11.0}),
             {"drawTextAnchored": {"text": "@clabel", "x": 92.0, "y": 500.0,
                                   "panX": -1.0, "panY": 0.0, "flags": 0}}]
    title(cmds, W, H, "x² + 1.4x + c", "drag left and right to move c")
    return {"header": header(W, H, "Drag to vary c in a quadratic and watch its two roots "
                                   "meet and disappear as the discriminant crosses zero"),
            "root": canvas(cmds, INK)}


# ── 8. CSC-DS-00006  Arrays — raster-and-text / analyze / 2D ─────────────────
# An array is an address and a stride, and everything else follows. Showing the arithmetic
# next to the cells it lands on is the one thing that makes random access obvious rather
# than magical.
def arrays():
    W, H = 580, 430
    cmds = []
    BASE, STRIDE, N = 4096, 4, 10
    x0, y, cw = 48.0, 190.0, 48.0
    cmds += text_at("base address", 48.0, 128.0, 10.0, DIM)
    cmds += text_at("0x1000", 48.0, 148.0, 13.0, ACCENT)
    cmds += text_at("stride", 190.0, 128.0, 10.0, DIM)
    cmds += text_at("4 bytes", 190.0, 148.0, 13.0, WARM)
    for i in range(N):
        x = x0 + i * cw
        hot = (i == 6)
        cmds.append(paint({"color": HOT if hot else PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x, "top": y, "right": x + cw - 4,
                                  "bottom": y + 56}})
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawRect": {"left": x, "top": y, "right": x + cw - 4,
                                  "bottom": y + 56}})
        cmds += text_at("%d" % i, x + (cw - 4) / 2, y - 10, 10.0, DIM, pan_x=0.0)
        cmds += text_at("%d" % ((i * 37 + 11) % 90), x + (cw - 4) / 2, y + 34, 15.0,
                        INK if hot else TEXT, pan_x=0.0)
        cmds += text_at("%04X" % (BASE + i * STRIDE), x + (cw - 4) / 2, y + 74, 8.5,
                        DIM, pan_x=0.0)
    cmds += text_at("addresses, four apart", 48.0, y + 96, 10.0, DIM)
    # the arithmetic, lined up under the cell it produces
    ax = x0 + 6 * cw + (cw - 4) / 2
    cmds.append(paint({"color": HOT}, {"style": "stroke"}, {"width": 1.6}))
    cmds.append({"drawLine": {"x1": ax, "y1": y + 86, "x2": ax, "y2": y + 126}})
    cmds += text_at("0x1000 + 6 x 4  =  0x1018", ax, y + 146, 13.0, HOT, pan_x=0.0)
    cmds += text_at("one multiply and one add, whatever the index -", 48.0, 376.0, 11.0, TEXT)
    cmds += text_at("which is the whole reason an array is fast, and the whole reason "
                    "it cannot grow", 48.0, 394.0, 11.0, DIM)
    title(cmds, W, H, "An array in memory", "index arithmetic, drawn where it lands")
    return {"header": header(W, H, "Ten array cells with their addresses, and the index "
                                   "arithmetic drawn beneath the element it selects"),
            "root": canvas(cmds, INK)}


# ── 9. CHM-MS-00006  Molecular orbitals — static-diagram / analyze / 2D ──────
# The O2 diagram, which is worth drawing because it predicts something a Lewis structure
# gets wrong: two unpaired electrons, so oxygen is magnetic. The two atomic columns and the
# molecular column in the middle are the standard reading order.
def orbitals():
    W, H = 520, 620
    cmds = []
    cxl, cxr, cxm = 90.0, 430.0, 260.0
    LEVELS = [("sigma*2p", 150.0, 0, HOT), ("pi*2p", 196.0, 2, HOT),
              ("pi 2p", 268.0, 4, GOOD), ("sigma 2p", 314.0, 2, GOOD),
              ("sigma*2s", 386.0, 2, HOT), ("sigma 2s", 432.0, 2, GOOD)]
    ATOMIC = [("2p", 232.0, 4), ("2s", 409.0, 2)]
    for cx in (cxl, cxr):
        for name, y, e in ATOMIC:
            cmds.append(paint({"color": DIM}, {"style": "stroke"}, {"width": 2.0}))
            for k in range(3 if name == "2p" else 1):
                lx = cx - 34 + k * 24
                cmds.append({"drawLine": {"x1": lx, "y1": y, "x2": lx + 18, "y2": y}})
            cmds += text_at(name, cx - 44, y + 4, 10.0, DIM, pan_x=1.0)
    for name, y, e, colour in LEVELS:
        wide = name.startswith("pi")
        for k in range(2 if wide else 1):
            lx = cxm - (26 if wide else 0) + k * 52 - 22
            cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.4}))
            cmds.append({"drawLine": {"x1": lx, "y1": y, "x2": lx + 44, "y2": y}})
            # electrons as arrows; the two in pi*2p stay unpaired, which is the point
            n_here = (e // 2) if wide else e
            for s in range(n_here):
                ex = lx + 14 + s * 16
                up = (s == 0)
                cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.6},
                                  {"strokeCap": "round"}))
                cmds.append({"drawLine": {"x1": ex, "y1": y - 9, "x2": ex, "y2": y + 9}})
                cmds.append({"drawLine": {"x1": ex, "y1": y - 9 if up else y + 9,
                                          "x2": ex - 4,
                                          "y2": y - 3 if up else y + 3}})
        cmds += text_at(name, cxm + 86, y + 4, 10.0, colour)
    # the tie lines from atomic to molecular
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 0.8}))
    for cx in (cxl, cxr):
        for _, ay, _ in ATOMIC:
            for name, my, _, _ in LEVELS:
                if (name.endswith("2p") and ay < 300) or (name.endswith("2s") and ay > 300):
                    cmds.append({"drawLine": {"x1": cx + (28 if cx == cxl else -28),
                                              "y1": ay, "x2": cxm + (-50 if cx == cxl else 90),
                                              "y2": my}})
    cmds += text_at("O", cxl, 128.0, 15.0, TEXT, pan_x=0.0)
    cmds += text_at("O", cxr, 128.0, 15.0, TEXT, pan_x=0.0)
    cmds += text_at("O₂", cxm, 118.0, 15.0, ACCENT, pan_x=0.0)
    # the conclusion, drawn rather than asserted
    cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 1.4}))
    cmds.append({"drawOval": {"left": cxm - 76, "top": 180.0, "right": cxm + 76,
                              "bottom": 212.0}})
    cmds += text_at("two electrons, unpaired", cxm, 170.0, 10.5, WARM, pan_x=0.0)
    cmds += text_at("bond order  =  (8 - 4) / 2  =  2", 60.0, 500.0, 12.5, GOOD)
    cmds += text_at("and because those two stay unpaired, liquid oxygen sticks to a magnet",
                    60.0, 524.0, 10.5, TEXT)
    cmds += text_at("- which the dot structure everyone is taught first does not predict",
                    60.0, 542.0, 10.5, DIM)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawArc": {"left": 60.0, "top": 556.0, "right": 110.0, "bottom": 586.0,
                             "startAngle": 180.0, "sweepAngle": 180.0}})
    cmds.append(paint({"color": GOOD}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": 85.0, "cy": 571.0, "radius": 3.5}})
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": 0.0, "top": 596.0, "right": W, "bottom": H}})
    title(cmds, W, H, "Molecular orbitals of O₂", "atomic on the outside, molecular between")
    return {"header": header(W, H, "The molecular orbital diagram of dioxygen, showing the "
                                   "two unpaired electrons that make it paramagnetic"),
            "root": canvas(cmds, INK)}


# ── 10. EAR-GEOL-00006  Mountain formation — annotated-layout / explain / 2D ─
# Four ways to build a mountain, each with a cross-section drawn in its own card. The cards
# are a flow so the sections stay the same size and can be compared edge to edge.
def mountains():
    W, H = 560, 600
    KINDS = [("Collision", "two continents meet and neither sinks",
              "Himalaya", GOOD),
             ("Volcanic", "one plate dives, melts, and comes back up",
              "Andes", HOT),
             ("Fault-block", "the crust pulls apart and blocks tilt",
              "Sierra Nevada", ACCENT),
             ("Dome", "magma lifts the layers without breaking out",
              "Black Hills", WARM)]

    def section(colour, kind):
        """The cross-section lives in its own canvas, sized, and clipped - a canvas does
        not clip its own drawing (F-012), so without this the strata run over the card."""
        c = [{"clipRect": {"left": 0, "top": 0, "right": 230, "bottom": 96}}]
        c.append(paint({"color": RULE}, {"style": "fill"}))
        c.append({"drawRect": {"left": 0, "top": 0, "right": 230, "bottom": 96}})
        if kind == 0:
            for s in range(4):
                c.append(paint({"color": colour if s % 2 == 0 else PANEL}, {"style": "fill"}))
                c.append({"drawPathFromPoints": {"points": []}} if False else
                         {"drawRect": {"left": 0, "top": 60 - s * 7, "right": 230,
                                       "bottom": 96}})
            c.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.4}))
            for k in range(5):
                c.append({"drawLine": {"x1": 20 + k * 8, "y1": 90 - k * 4,
                                       "x2": 115, "y2": 24}})
                c.append({"drawLine": {"x1": 210 - k * 8, "y1": 90 - k * 4,
                                       "x2": 115, "y2": 24}})
        elif kind == 1:
            c.append(paint({"color": PANEL}, {"style": "fill"}))
            c.append({"drawRect": {"left": 0, "top": 56, "right": 230, "bottom": 96}})
            c.append(paint({"color": colour}, {"style": "fill"}))
            for k in range(3):
                c.append({"drawCircle": {"cx": 70 + k * 46, "cy": 30 + k * 6, "radius": 16 - k * 3}})
            c.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.0}))
            c.append({"drawLine": {"x1": 0, "y1": 60, "x2": 230, "y2": 92}})
        elif kind == 2:
            for k in range(4):
                c.append(paint({"color": colour if k % 2 else PANEL}, {"style": "fill"}))
                c.append({"drawRect": {"left": k * 58, "top": 30 + k * 12,
                                       "right": k * 58 + 54, "bottom": 96}})
        else:
            c.append(paint({"color": PANEL}, {"style": "fill"}))
            c.append({"drawRect": {"left": 0, "top": 40, "right": 230, "bottom": 96}})
            for k in range(3):
                c.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.0}))
                c.append({"drawArc": {"left": 50 - k * 14, "top": 26 + k * 10,
                                      "right": 180 + k * 14, "bottom": 120 + k * 10,
                                      "startAngle": 180.0, "sweepAngle": 180.0}})
        return {"type": "canvas", "modifiers": [{"width": 230}, {"height": 96}],
                "commands": c}

    cards = []
    for i, (name, how, where, colour) in enumerate(KINDS):
        cards.append({"type": "column",
                      "modifiers": [{"width": 248}, {"padding": 9}, {"background": PANEL}],
                      "children": [
                          section(colour, i),
                          {"type": "spacer", "modifiers": [{"height": 7}]},
                          {"type": "text", "value": name, "modifiers": [],
                           "fontSize": 13.0, "color": colour},
                          {"type": "spacer", "modifiers": [{"height": 3}]},
                          {"type": "text", "value": how, "modifiers": [],
                           "fontSize": 9.5, "color": DIM},
                          {"type": "text", "value": where, "modifiers": [],
                           "fontSize": 10.0, "color": TEXT}]})
    return {"header": header(W, H, "Four ways mountains form, each with its own cross-"
                                   "section drawn at the same size"),
            "root": {"type": "column",
                     "modifiers": ["fillMaxSize", {"padding": 16}, {"background": INK}],
                     "children": [
                         {"type": "text", "value": "How mountains are made", "modifiers": [],
                          "fontSize": 19.0, "color": TEXT},
                         {"type": "spacer", "modifiers": [{"height": 3}]},
                         {"type": "text",
                          "value": "sections at one scale, so the shapes can be compared",
                          "modifiers": [], "fontSize": 11.0, "color": DIM},
                         {"type": "spacer", "modifiers": [{"height": 12}]},
                         {"type": "flow", "modifiers": [{"width": 520}],
                          "children": cards}]}}


# ── 11. ENG-ME-00006  Robotics — data-plot / explore / 2D ───────────────────
# A two-link arm's joint angles over one pick-and-place cycle, with the hand's path in
# cartesian space beside them. Putting both views on one page is the point: smooth joints
# do not mean a smooth path, and the corner in the trace is where that bites.
def robotics():
    W, H = 600, 440
    N = 40
    T = [i / (N - 1.0) for i in range(N)]
    def j1(t):
        return 0.5 + 0.85 * (3 * t * t - 2 * t * t * t)
    def j2(t):
        return 1.5 - 1.1 * math.sin(math.pi * min(1.0, t * 1.25))
    cmds = []
    px0, px1, py0, py1 = 50.0, 310.0, 120.0, 330.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    for f in (0.0, 0.5, 1.0):
        y = py1 - f * (py1 - py0)
        cmds.append({"drawLine": {"x1": px0, "y1": y, "x2": px1, "y2": y}})
        cmds += text_at("%.1f" % (f * 2.5), px0 - 6, y + 4, 9.0, DIM, pan_x=1.0)
    for series, colour, lbl in ((j1, GOOD, "shoulder"), (j2, ACCENT, "elbow")):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6},
                          {"strokeCap": "round"}))
        prev = None
        for i, t in enumerate(T):
            x = px0 + (px1 - px0) * t
            y = py1 - (series(t) / 2.5) * (py1 - py0)
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": x, "y2": y}})
            prev = (x, y)
        cmds += text_at(lbl, prev[0] - 4, prev[1] - 8, 10.0, colour, pan_x=1.0)
    cmds += text_at("joint angle, radians", px0, py0 - 12, 10.5, DIM)
    cmds += text_at("time through the cycle", px0, py1 + 20, 10.0, DIM)

    # the same motion in cartesian space
    qx0, qx1, qy0, qy1 = 340.0, 560.0, 120.0, 330.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": qx0, "top": qy0, "right": qx1, "bottom": qy1}})
    L1, L2, S = 1.0, 0.8, 62.0
    ox, oy = qx0 + 36, qy1 - 30
    pts = []
    for t in T:
        a, b = j1(t), j2(t)
        x = ox + (L1 * math.cos(a) + L2 * math.cos(a + b - 1.6)) * S
        y = oy - (L1 * math.sin(a) + L2 * math.sin(a + b - 1.6)) * S
        pts.append((x, y))
    cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 2.2}))
    for i in range(1, len(pts)):
        cmds.append({"drawLine": {"x1": pts[i - 1][0], "y1": pts[i - 1][1],
                                  "x2": pts[i][0], "y2": pts[i][1]}})
    # the arm itself at three instants, so the trace has something generating it
    for t, alpha in ((0.0, DIM), (0.5, RULE), (1.0, TEXT)):
        a, b = j1(t), j2(t)
        ex = ox + L1 * math.cos(a) * S
        ey = oy - L1 * math.sin(a) * S
        hx = ex + L2 * math.cos(a + b - 1.6) * S
        hy = ey - L2 * math.sin(a + b - 1.6) * S
        cmds.append(paint({"color": alpha}, {"style": "stroke"}, {"width": 3.0},
                          {"strokeCap": "round"}))
        cmds.append({"drawLine": {"x1": ox, "y1": oy, "x2": ex, "y2": ey}})
        cmds.append({"drawLine": {"x1": ex, "y1": ey, "x2": hx, "y2": hy}})
        cmds.append(paint({"color": alpha}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": ex, "cy": ey, "radius": 3.5}})
    cmds += text_at("where the hand actually goes", qx0 + 8, qy0 - 12, 10.5, WARM)
    cmds += text_at("both joints move smoothly, and the hand still does not travel in a "
                    "straight line", 50.0, 372.0, 11.0, TEXT)
    cmds += text_at("- which is why a robot that must follow a line plans in the right "
                    "space and solves backwards", 50.0, 392.0, 10.5, DIM)
    title(cmds, W, H, "A two-link arm", "joint space on the left, the world on the right")
    return {"header": header(W, H, "Two joint angles over a pick-and-place cycle beside the "
                                   "curved path the hand traces"),
            "root": canvas(cmds, INK)}


# ── 12. FIN-MARK-00004  Foreign exchange — path-form / compare / 2D ─────────
# Three currencies against one base, each as a closed path filled from its own baseline, so
# a year where one strengthened while another fell is a shape rather than a legend entry.
def forex():
    W, H = 580, 460
    SERIES = [("EUR", GOOD, [0.0, 1.2, 2.1, 1.4, 2.8, 3.9, 3.2, 4.6, 5.8, 5.1, 6.4, 7.2]),
              ("JPY", HOT, [0.0, -1.8, -3.4, -2.9, -5.1, -6.8, -8.2, -7.4, -9.6, -11.2,
                            -10.4, -12.1]),
              ("GBP", ACCENT, [0.0, 0.6, -0.4, 1.1, 0.8, 1.9, 1.2, 2.4, 1.8, 3.1, 2.6, 3.4])]
    cmds = []
    # Everything that must not be clipped goes first: a clipRect later in this list can
    # never be widened again (F-021), and the series fills below each need one.
    px0, px1, cy, scale = 60.0, 540.0, 270.0, 8.4
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": 120.0, "right": px1, "bottom": 400.0}})
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.2}))
    cmds.append({"drawLine": {"x1": px0, "y1": cy, "x2": px1, "y2": cy}})
    for pct in (-10, -5, 5, 10):
        y = cy - pct * scale
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 0.8}))
        cmds.append({"drawLine": {"x1": px0, "y1": y, "x2": px1, "y2": y}})
        cmds += text_at("%+d%%" % pct, px0 - 6, y + 4, 9.0, DIM, pan_x=1.0)
    for i, m in enumerate(("Jan", "Apr", "Jul", "Oct")):
        cmds += text_at(m, px0 + 14 + (px1 - px0 - 28) * (i * 3) / 11.0, 420.0, 9.5,
                        DIM, pan_x=0.0)
    cmds += text_at("against the dollar", px0, 112.0, 10.5, DIM)
    cmds += text_at("the same dollar did all three of these at once", 60.0, 440.0, 10.5, TEXT)
    for name, colour, vals in SERIES:
        n = len(vals)
        cmds += text_at(name, px1 - 20, cy - vals[-1] * scale + 4, 11.0, colour, pan_x=1.0)
    title(cmds, W, H, "One year, three currencies",
          "each filled from zero, so direction is a shape")
    pid = "fx0"
    for si, (name, colour, vals) in enumerate(SERIES):
        pid = "fx%d" % si
        n = len(vals)
        xs = [px0 + 14 + (px1 - px0 - 28) * i / (n - 1.0) for i in range(n)]
        ys = [cy - v * scale for v in vals]
        cmds.append({"pathCreate": {"id": pid, "x": xs[0], "y": cy}})
        for x, y in zip(xs, ys):
            cmds.append({"pathAppendLineTo": {"path": pid, "x": x, "y": y}})
        cmds.append({"pathAppendLineTo": {"path": pid, "x": xs[-1], "y": cy}})
        cmds.append({"pathAppendClose": {"path": pid}})
        cmds.append({"clipRect": {"left": px0, "top": 120.0, "right": px1, "bottom": 400.0}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawPath": {"path": pid}})
        cmds.append({"clipRect": {"left": 0, "top": 0, "right": W, "bottom": H}})
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.0}))
        cmds.append({"drawPath": {"path": pid}})

    return {"header": header(W, H, "Three currencies against the dollar over a year, each "
                                   "as a filled path from its own zero line"),
            "root": canvas(cmds, INK)}


# ── 13. FIN-CF-00005  Revenue — expression-animation / demonstrate / 3D ─────
# A revenue bridge as blocks in space, growing from zero on a shared clock. A bridge is the
# one finance chart people already draw as stacked blocks, so the third dimension is not
# decoration here - it lets the positive and negative steps sit on separate faces.
def revenue():
    W, H = 520, 580
    STEPS = [("Opening", 100.0, DIM), ("New", 34.0, GOOD), ("Upsell", 18.0, GOOD),
             ("Churn", -22.0, HOT), ("Discount", -9.0, HOT), ("Closing", 121.0, ACCENT)]
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.72,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [1.5, 1.35, 5.6], "center": [0, 0.42, 0], "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.45, -0.62, -0.65], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.2, 0.5], "intensity": 0.42}]}}]
    # A fly-in reads as an empty frame for most of its cycle, and `continuousSec()` cannot
    # be pinned (F-019), so a still of this document would usually catch it mid-arrival with
    # the bridge half absent. A slow turn instead: assembled at every instant, including the
    # one a thumbnail happens to land on.
    cmds.append(var("turn", "sin(continuousSec() * 0.35) * 0.42"))
    SC = 0.009
    run = 0.0
    for i, (name, val, colour) in enumerate(STEPS):
        x = -1.45 + i * 0.58
        if name in ("Opening", "Closing"):
            lo_y, hi_y = 0.0, abs(val) * SC
        else:
            lo_y = run * SC if val > 0 else (run + val) * SC
            hi_y = (run + val) * SC if val > 0 else run * SC
        verts, normals, uv, idx = [], [], [], []
        # Geometry carries the block's FINAL position. The animation is a translate that
        # decays to zero, never a scale: scale acts about the world origin, so scaling a
        # block that floats above the floor moves it as well as resizing it - which is
        # what scattered the bridge across the frame on the first attempt.
        mesh_box(verts, normals, uv, idx,
                 (x - 0.20, lo_y, -0.20), (x + 0.20, hi_y, 0.20))
        cmds.append({"defineMesh3D": {"id": 10 + i, "verts": [round(v, 5) for v in verts],
                                      "normals": normals, "uv": uv, "indices": idx}})
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@turn", "axis": [0, 1, 0]}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": 10 + i, "mode": "software-smooth"}}]
        if name not in ("Opening", "Closing"):
            run += val
        elif name == "Opening":
            run = val
    # labels in 2D, under the blocks they belong to - 3D text would ride the camera
    for i, (name, val, colour) in enumerate(STEPS):
        x = 72.0 + i * 76.0
        cmds += text_at(name, x, 476.0, 10.0, colour, pan_x=0.0)
        cmds += text_at("%+.0f" % val if name not in ("Opening", "Closing") else "%.0f" % val,
                        x, 494.0, 11.5, TEXT, pan_x=0.0)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": 40.0, "y1": 452.0, "x2": 480.0, "y2": 452.0}})
    title(cmds, W, H, "Where the year's revenue went",
          "opening, what was won, what was lost, closing")
    cmds += text_at("the two red blocks are the whole reason 152 became 121",
                    40.0, 532.0, 10.5, DIM)
    return {"header": header(W, H, "A revenue bridge as 3D blocks growing from zero, with "
                                   "gains and losses on separate faces"),
            "root": canvas(cmds, INK)}


# ── 14. FIN-CF-00006  Costs — particle-system / simulate / 2D ───────────────
# Cost as a flow of units falling into two buckets. Fixed costs fill at the same rate no
# matter what; variable costs track the stream. Running them as particles rather than bars
# makes the rate the visible quantity, which is what distinguishes the two.
def costs():
    W, H = 500, 560
    cmds = []
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": 40.0, "top": 110.0, "right": 460.0, "bottom": 300.0}})
    # the stream: units falling from the top, drifting toward one bucket or the other
    cmds.append({"createParticles": {
        "id": "units", "count": 70,
        "variables": ["sx", "sy", "drift", "speed"],
        "initialValues": ["60 + rand() * 380", "118 + rand() * 176",
                          "-0.4 + rand() * 0.8", "0.6 + rand() * 1.5"]}})
    cmds.append(paint({"color": WARM}, {"style": "fill"}))
    cmds.append({"particlesLoop": {
        "system": "@units",
        "equations": ["sx + drift", "118 + ((sy - 118 + speed) % 176)", "drift", "speed"],
        "commands": [{"drawCircle": {"cx": "@sx", "cy": "@sy", "radius": 2.6}}]}})
    cmds += text_at("every unit sold", 250.0, 136.0, 11.0, DIM, pan_x=0.0)
    # two buckets, one of which does not care about the stream
    for i, (name, note, frac, colour) in enumerate(
            (("Fixed", "rent, salaries, the lease on the machine", 0.62, ACCENT),
             ("Variable", "materials, shipping, the hour someone worked", 0.78, HOT))):
        x0 = 56.0 + i * 212.0
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 2.0}))
        cmds.append({"drawLine": {"x1": x0, "y1": 320.0, "x2": x0, "y2": 440.0}})
        cmds.append({"drawLine": {"x1": x0 + 188, "y1": 320.0, "x2": x0 + 188, "y2": 440.0}})
        cmds.append({"drawLine": {"x1": x0, "y1": 440.0, "x2": x0 + 188, "y2": 440.0}})
        if i == 0:
            fill = 0.62
            cmds.append(paint({"color": colour}, {"style": "fill"}))
            cmds.append({"drawRect": {"left": x0 + 3, "top": 440.0 - 118 * fill,
                                      "right": x0 + 185, "bottom": 438.0}})
        else:
            # this one rises and falls with the stream, on the same clock the particles use
            cmds.append(var("vol", "0.45 + 0.33 * sin(continuousSec() * 0.6)"))
            cmds.append(paint({"color": colour}, {"style": "fill"}))
            cmds.append({"drawRect": {"left": x0 + 3, "top": "438.0 - 118.0 * @vol",
                                      "right": x0 + 185, "bottom": 438.0}})
        cmds += text_at(name, x0 + 94, 466.0, 13.0, colour, pan_x=0.0)
        cmds += text_at(note, x0 + 94, 484.0, 9.0, DIM, pan_x=0.0)
    cmds += text_at("the left bucket is the same height whether you sell nothing or "
                    "everything", 40.0, 520.0, 10.5, TEXT)
    cmds += text_at("- which is why volume is survival when fixed costs are high",
                    40.0, 538.0, 10.5, DIM)
    title(cmds, W, H, "Two kinds of cost", "one tracks the stream, one does not")
    return {"header": header(W, H, "Units of sale falling as particles into a fixed cost "
                                   "bucket that never moves and a variable one that does"),
            "root": canvas(cmds, INK)}


# ── 15. FIN-CF-00007  Cash flow — interactive / analyze / 2D ────────────────
# Drag through a year of cash. Profit and cash are not the same thing and the gap between
# them is where companies die, so the running balance is drawn as the thing that can go
# below zero while the monthly profit bars stay cheerfully positive.
def cashflow():
    W, H = 560, 520
    PROFIT = [12, 14, 11, 16, 18, 15, 19, 17, 21, 18, 22, 24]
    # paid late: cash arrives two months after the profit is booked
    CASH = [-38, -31, -24, -17, -9, -2, 4, 9, 15, 22, 31, 42]
    MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    cmds = [{"touchExpression": {"name": "drag", "defaultValue": 300.0, "min": 60.0,
                                 "max": 520.0, "expression": "touchX()"}},
            var("sel", "clamp(0.0, 11.0, floor((@drag - 60.0) / 460.0 * 12.0))")]
    px0, px1, cy = 60.0, 520.0, 300.0
    bw = (px1 - px0) / 12.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": 120.0, "right": px1, "bottom": 400.0}})
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.2}))
    cmds.append({"drawLine": {"x1": px0, "y1": cy, "x2": px1, "y2": cy}})
    for i in range(12):
        x = px0 + i * bw
        cmds.append(paint({"color": GOOD}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x + 5, "top": cy - PROFIT[i] * 2.4,
                                  "right": x + bw - 5, "bottom": cy}})
        cmds += text_at(MON[i], x + bw / 2, 418.0, 8.5, DIM, pan_x=0.0)
    # the running cash balance, which spends half the year underwater
    cmds.append(paint({"color": HOT}, {"style": "stroke"}, {"width": 2.8},
                      {"strokeCap": "round"}))
    prev = None
    for i, v in enumerate(CASH):
        x = px0 + i * bw + bw / 2
        y = cy - v * 2.4
        if prev:
            cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": x, "y2": y}})
        prev = (x, y)
    # the selected month, picked out by the drag
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.6}))
    cmds.append({"drawLine": {"x1": "%.1f + @sel * %.3f + %.2f" % (px0, bw, bw / 2),
                              "y1": 126.0,
                              "x2": "%.1f + @sel * %.3f + %.2f" % (px0, bw, bw / 2),
                              "y2": 396.0}})
    cmds += text_at("profit, every month", px0 + 6, 142.0, 10.5, GOOD)
    cmds += text_at("cash in the bank", px0 + 6, 160.0, 10.5, HOT)
    cmds += text_at("month", 60.0, 452.0, 10.0, DIM)
    cmds += [{"variable": {"name": "mlabel", "commit": True,
                           "value": {"type": "textFromFloat", "value": "@sel + 1.0",
                                     "whole": 2, "decimal": 0}}},
             paint({"color": TEXT}, {"style": "fill"}, {"textSize": 12.0}),
             {"drawTextAnchored": {"text": "@mlabel", "x": 112.0, "y": 452.0,
                                   "panX": -1.0, "panY": 0.0, "flags": 0}}]
    cmds.append({"conditionalOperations": {
        "condition": "lt", "v1": "@sel", "v2": 6.0,
        "commands": [
            paint({"color": HOT}, {"style": "fill"}, {"textSize": 11.0}),
            {"drawTextAnchored": {
                "text": "profitable, and out of money", "x": 160.0, "y": 452.0,
                "panX": -1.0, "panY": 0.0, "flags": 0}}]}})
    cmds.append({"conditionalOperations": {
        "condition": "ge", "v1": "@sel", "v2": 6.0,
        "commands": [
            paint({"color": GOOD}, {"style": "fill"}, {"textSize": 11.0}),
            {"drawTextAnchored": {
                "text": "the receipts have finally caught up", "x": 160.0, "y": 452.0,
                "panX": -1.0, "panY": 0.0, "flags": 0}}]}})
    cmds += text_at("every month on this page made a profit", 60.0, 482.0, 10.5, TEXT)
    cmds += text_at("- the company was still nearly out of cash in March",
                    60.0, 500.0, 10.5, DIM)
    title(cmds, W, H, "Profit is not cash", "drag to move through the year")
    return {"header": header(W, H, "Drag through a year of monthly profit against the "
                                   "running cash balance, which stays negative until July"),
            "root": canvas(cmds, INK)}


# ── 16. SOC-PSYC-00005  Cognition — raster-and-text / explain / 2D ──────────
# The memory pipeline, with the losses named at each step. The numbers are the argument:
# almost everything that reaches the senses is gone within seconds, and saying so next to
# the arrow that drops it is more honest than three equal boxes.
def cognition():
    W, H = 520, 580
    STAGES = [("Sensory", "everything the senses take in", "~0.5 s", 1.00, DIM),
              ("Attention", "the narrow part, and the only part you steer", "", 0.22, WARM),
              ("Working", "about four things, for about twenty seconds", "~20 s", 0.09,
               ACCENT),
              ("Long-term", "what rehearsal and meaning manage to keep", "years", 0.04,
               GOOD)]
    cmds = []
    y = 130.0
    for i, (name, note, dur, frac, colour) in enumerate(STAGES):
        wpx = 60.0 + 360.0 * frac
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 60.0, "top": y, "right": 60.0 + wpx,
                                  "bottom": y + 52}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 60.0, "top": y, "right": 64.0,
                                  "bottom": y + 52}})
        cmds += text_at(name, 76.0, y + 22, 13.0, colour)
        cmds += text_at(note, 76.0, y + 40, 9.5, DIM)
        if dur:
            cmds += text_at(dur, 460.0, y + 22, 11.0, TEXT, pan_x=1.0)
        if i < len(STAGES) - 1:
            nxt = STAGES[i + 1][3]
            cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.6}))
            cmds.append({"drawLine": {"x1": 92.0, "y1": y + 52, "x2": 92.0, "y2": y + 92}})
            cmds.append({"drawLine": {"x1": 92.0, "y1": y + 92, "x2": 86.0, "y2": y + 84}})
            cmds.append({"drawLine": {"x1": 92.0, "y1": y + 92, "x2": 98.0, "y2": y + 84}})
            lost = 100.0 * (1.0 - nxt / frac)
            cmds += [{"variable": {"name": "lost%d" % i, "commit": True,
                                   # as a STRING: a numeric literal here renders as 0
                                   # with no error at all (F-020)
                                   "value": {"type": "textFromFloat",
                                             "value": "%.1f" % lost,
                                             "whole": 2, "decimal": 0}}},
                     paint({"color": HOT}, {"style": "fill"}, {"textSize": 10.0}),
                     {"drawTextAnchored": {"text": "@lost%d" % i, "x": 108.0, "y": y + 78,
                                           "panX": -1.0, "panY": 0.0, "flags": 0}}]
            cmds += text_at("% of it does not make the next step", 136.0, y + 78, 10.0, HOT)
        y += 108.0
    cmds += text_at("the width of each bar is how much survives", 60.0, 548.0, 10.5, TEXT)
    title(cmds, W, H, "What gets remembered",
          "four stages, and what each one throws away")
    return {"header": header(W, H, "The memory pipeline as four bars whose widths are what "
                                   "survives each stage, with the losses named"),
            "root": canvas(cmds, INK)}


# ── build ──────────────────────────────────────────────────────────────────────
BUILD = [("PHY-NP-00019", fusion), ("PHY-NP-00020", reactions),
         ("BIO-BIOC-00018", photosynthesis), ("BIO-GENE-00019", mendel),
         ("BIO-GENE-00020", chromosomes), ("BIO-GENE-00021", mutations),
         ("MTH-ALGE-00006", equations), ("CSC-DS-00006", arrays),
         ("CHM-MS-00006", orbitals), ("EAR-GEOL-00006", mountains),
         ("ENG-ME-00006", robotics), ("FIN-MARK-00004", forex),
         ("FIN-CF-00005", revenue), ("FIN-CF-00006", costs),
         ("FIN-CF-00007", cashflow), ("SOC-PSYC-00005", cognition)]

if __name__ == "__main__":
    for doc_id, fn in BUILD:
        name = use(doc_id)
        d = fn()
        (OUT / ("%s.json" % doc_id)).write_text(json.dumps(d, indent=1) + "\n")
        print("  %-16s %-9s %s" % (doc_id, name, d["header"]["contentDescription"][:52]))
    print("  %d documents" % len(BUILD))
