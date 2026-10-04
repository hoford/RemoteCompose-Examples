#!/usr/bin/env python3
"""Build set 7 of the visualization programme: 16 documents.

    python3 work/set-07/make_set07.py

Work order from `python3 tools/visplan.py set 7`. Three 3D slots: the double slit, tumour
growth and depth perception. All three earn it - interference is a pattern on a screen some
distance from the slits, growth over time is a surface, and depth perception is about the
one dimension a flat image throws away.

Helper block carried from set 6, which added oriented_box. The rules this set was written
against, each paid for by an earlier one:

  clipRect is permanent         it intersects and can never be widened (F-021), so anything
                                clipped goes last or into its own nested canvas
  textFromFloat wants a string  a numeric literal renders as 0, silently (F-020)
  3D fills the document         a scene in a sized card projects outside it (F-013)
  translate after rotate        rides the rotated frame; aim the camera instead
  scale is about the origin     so it moves anything not sitting on the origin
  clamp(min, max, value)        the value goes last
  pin the clock                 and pick an instant where the document looks like itself
"""

import hashlib
import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent


# ────────────────────────────────────────────────────────────────────────────
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


# ── 1. PHY-QM-00021  Wave functions — static-diagram / explain / 2D ──────────
# A particle in a box, four states. Drawing psi above and |psi|^2 below in the same column is
# the whole explanation: the wave is the thing that has a sign, the square is the thing you
# can measure, and the nodes survive the squaring while the sign does not.
def wavefunctions():
    W, H = 620, 460
    cmds = []
    bw, gap = 128.0, 14.0
    for n in range(1, 5):
        x0 = 30.0 + (n - 1) * (bw + gap)
        cy_psi, cy_prob = 180.0, 330.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": 120.0, "right": x0 + bw,
                                  "bottom": 240.0}})
        cmds.append({"drawRect": {"left": x0, "top": 270.0, "right": x0 + bw,
                                  "bottom": 390.0}})
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": x0, "y1": cy_psi, "x2": x0 + bw, "y2": cy_psi}})
        cmds.append({"drawLine": {"x1": x0, "y1": 390.0, "x2": x0 + bw, "y2": 390.0}})
        STEP = 44
        prev_p = prev_q = None
        for i in range(STEP + 1):
            u = i / float(STEP)
            psi = math.sin(n * math.pi * u)
            x = x0 + u * bw
            yp = cy_psi - psi * 48.0
            yq = 390.0 - (psi * psi) * 110.0
            if prev_p:
                cmds.append(paint({"color": ACCENT}, {"style": "stroke"}, {"width": 2.2},
                                  {"strokeCap": "round"}))
                cmds.append({"drawLine": {"x1": prev_p[0], "y1": prev_p[1],
                                          "x2": x, "y2": yp}})
                cmds.append(paint({"color": GOOD}, {"style": "stroke"}, {"width": 2.2},
                                  {"strokeCap": "round"}))
                cmds.append({"drawLine": {"x1": prev_q[0], "y1": prev_q[1],
                                          "x2": x, "y2": yq}})
            prev_p, prev_q = (x, yp), (x, yq)
        # the nodes, which are what the two rows have in common
        for k in range(1, n):
            xn = x0 + bw * k / float(n)
            cmds.append(paint({"color": HOT}, {"style": "fill"}))
            cmds.append({"drawCircle": {"cx": xn, "cy": cy_psi, "radius": 3.0}})
            cmds.append({"drawCircle": {"cx": xn, "cy": 390.0, "radius": 3.0}})
        cmds += text_at("n = %d" % n, x0 + bw / 2, 112.0, 12.0, TEXT, pan_x=0.0)
        cmds += text_at("E = %d E1" % (n * n), x0 + bw / 2, 414.0, 10.0, DIM, pan_x=0.0)
    cmds += text_at("psi", 24.0, 180.0, 11.0, ACCENT, pan_x=1.0)
    cmds += text_at("|psi|²", 24.0, 334.0, 11.0, GOOD, pan_x=1.0)
    cmds += text_at("the sign disappears when you square it; the nodes do not",
                    30.0, 438.0, 10.5, DIM)
    title(cmds, W, H, "A particle in a box", "the wave above, what you can measure below")
    return {"header": header(W, H, "Four standing-wave states of a particle in a box, each "
                                   "with its probability density beneath it"),
            "root": canvas(cmds, INK)}


# ── 2. PHY-QM-00022  Probability distributions — annotated-layout / explore ──
# Four distributions as cards, each with the question it answers. Layout rather than a plot
# because the point is taxonomic: which distribution, and when.
def distributions():
    W, H = 500, 640
    KINDS = [("Uniform", "every outcome equally likely",
              "a fair die, a photon's phase", GOOD, [1, 1, 1, 1, 1, 1, 1, 1]),
             ("Gaussian", "many small independent effects added up",
              "measurement error, thermal noise", ACCENT,
              [1, 2, 4, 7, 9, 7, 4, 2]),
             ("Poisson", "rare events in a fixed window",
              "clicks on a Geiger counter", WARM, [2, 5, 8, 8, 6, 3, 2, 1]),
             ("Exponential", "time until the next event",
              "how long a nucleus survives", HOT, [9, 6, 4, 3, 2, 1, 1, 1])]

    def spark(bars, colour):
        """Its own canvas, clipped as its first command: a clip cannot be widened later
        (F-021), so scoping it to a child is the only way to clip one panel safely."""
        m = float(max(bars))
        c = [{"clipRect": {"left": 0, "top": 0, "right": 150, "bottom": 56}},
             paint({"color": RULE}, {"style": "fill"}),
             {"drawRect": {"left": 0, "top": 0, "right": 150, "bottom": 56}}]
        bw = 150.0 / len(bars)
        for i, b in enumerate(bars):
            c.append(paint({"color": colour}, {"style": "fill"}))
            c.append({"drawRect": {"left": i * bw + 1.5, "top": 54 - (b / m) * 48,
                                   "right": (i + 1) * bw - 1.5, "bottom": 54}})
        return {"type": "canvas", "modifiers": [{"width": 150}, {"height": 56}],
                "commands": c}

    cards = []
    for name, when, eg, colour, bars in KINDS:
        cards.append({"type": "row",
                      "modifiers": [{"width": 456}, {"padding": 11},
                                    {"background": PANEL}],
                      "children": [
                          spark(bars, colour),
                          {"type": "spacer", "modifiers": [{"width": 14}]},
                          {"type": "column", "modifiers": [{"width": 268}], "children": [
                              {"type": "text", "value": name, "modifiers": [],
                               "fontSize": 14.0, "color": colour},
                              {"type": "spacer", "modifiers": [{"height": 4}]},
                              {"type": "text", "value": when, "modifiers": [],
                               "fontSize": 10.0, "color": TEXT},
                              {"type": "spacer", "modifiers": [{"height": 3}]},
                              {"type": "text", "value": eg, "modifiers": [],
                               "fontSize": 9.5, "color": DIM}]}]})
    kids = [{"type": "text", "value": "Four distributions", "modifiers": [],
             "fontSize": 19.0, "color": TEXT},
            {"type": "spacer", "modifiers": [{"height": 3}]},
            {"type": "text", "value": "not what they look like, but what question each answers",
             "modifiers": [], "fontSize": 11.0, "color": DIM},
            {"type": "spacer", "modifiers": [{"height": 14}]}]
    for c in cards:
        kids.append(c)
        kids.append({"type": "spacer", "modifiers": [{"height": 10}]})
    kids.append({"type": "text",
                 "value": "the Gaussian turns up everywhere because almost anything made of "
                          "many small independent parts ends up looking like it, whatever "
                          "the parts were",
                 "modifiers": [], "fontSize": 9.5, "color": DIM})
    return {"header": header(W, H, "Four probability distributions as cards, each with the "
                                   "kind of question it answers"),
            "root": {"type": "column",
                     "modifiers": ["fillMaxSize", {"padding": 18}, {"background": INK}],
                     "children": kids}}


# ── 3. PHY-QM-00023  Quantum tunneling — data-plot / compare / 2D ───────────
# Transmission against barrier width, for three particle masses. The log-scale fall is the
# content: tunnelling is not rare so much as exponentially punished, and an electron and a
# proton differ by orders of magnitude at the same barrier.
def tunneling():
    W, H = 580, 470
    SPECIES = [("electron", 1.0, GOOD), ("proton", 42.8, ACCENT), ("alpha", 85.6, HOT)]
    px0, px1, py0, py1 = 70.0, 540.0, 120.0, 340.0
    cmds = [paint({"color": PANEL}, {"style": "fill"}),
            {"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}}]
    # a decade grid, because the whole story is on a log axis
    DEC = 8
    for d in range(DEC + 1):
        y = py0 + (py1 - py0) * d / DEC
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 0.8}))
        cmds.append({"drawLine": {"x1": px0, "y1": y, "x2": px1, "y2": y}})
        if d % 2 == 0:
            cmds += text_at("1e-%d" % d, px0 - 6, y + 4, 9.0, DIM, pan_x=1.0)
    for name, kappa, colour in SPECIES:
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6},
                          {"strokeCap": "round"}))
        prev = None
        for i in range(49):
            a = i / 48.0 * 1.0                      # barrier width, nm
            decades = kappa * a * 2.0 / 2.302585
            if decades > DEC:
                break
            x = px0 + (px1 - px0) * a
            y = py0 + (py1 - py0) * decades / DEC
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": x, "y2": y}})
            prev = (x, y)
        if prev:
            cmds += text_at(name, min(prev[0] + 8, px1 - 6), prev[1] + 4, 10.5, colour)
    for k in range(5):
        x = px0 + (px1 - px0) * k / 4.0
        cmds += text_at("%.2f" % (k / 4.0), x, py1 + 20, 9.5, DIM, pan_x=0.0)
    cmds += text_at("barrier width, nm", (px0 + px1) / 2, py1 + 40, 10.5, DIM, pan_x=0.0)
    cmds += text_at("transmission", px0, py0 - 12, 10.5, DIM)
    # one concrete reading, marked on the plot
    mx = px0 + (px1 - px0) * 0.30
    cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 1.2}))
    cmds.append({"drawLine": {"x1": mx, "y1": py0, "x2": mx, "y2": py1}})
    cmds += text_at("at 0.3 nm an electron gets through about once in a thousand tries",
                    70.0, 414.0, 10.5, TEXT)
    cmds += text_at("a proton, about once in 10^11 - same barrier, same energy",
                    70.0, 434.0, 10.5, DIM)
    title(cmds, W, H, "Tunnelling", "why a heavier particle simply does not")
    return {"header": header(W, H, "Transmission probability against barrier width on a log "
                                   "axis, for an electron, a proton and an alpha particle"),
            "root": canvas(cmds, INK)}


# ── 4. PHY-QM-00024  Double-slit — path-form / demonstrate / 3D ─────────────
# The slits and the screen in space, with the fringe pattern drawn as a path on the screen
# and again flat below it. 3D earns its place here: the pattern only means anything in
# relation to the distance it formed over, and that distance is the thing a flat diagram
# cannot show.
def double_slit():
    W, H = 520, 620
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.72,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [4.0, 3.6, 5.0], "center": [0.0, 0.05, -1.25],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.4, -0.55, -0.73], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.25, 0.5], "intensity": 0.45}]}}]
    # The drag turns the whole scene. Declared here because every mesh below references
    # @spin, and a variable has to exist before the command that reads it.
    cmds.append({"touchExpression": {"name": "drag", "defaultValue": 260.0,
                                     "min": 0.0, "max": 520.0,
                                     "expression": "touchX()"}})
    # centred on the composed view, so an untouched document shows the arrangement the
    # caption describes rather than an arbitrary angle
    cmds.append(var("spin", "(@drag - 260.0) / 170.0"))
    # Seen from the side, because the claim is about the distance behind the slits. Head-on
    # the barrier and the screen overlap into one ambiguous slab, which is what the first
    # version did.
    verts, normals, uv, idx = [], [], [], []
    for lo, hi in (((-1.10, 0.0, -0.03), (-0.20, 1.15, 0.03)),      # left of both slits
                   ((-0.08, 0.0, -0.03), (0.08, 1.15, 0.03)),       # the bar between them
                   ((0.20, 0.0, -0.03), (1.10, 1.15, 0.03))):       # right of both
        mesh_box(verts, normals, uv, idx, lo, hi)
    cmds.append({"defineMesh3D": {"id": 1, "verts": [round(v, 5) for v in verts],
                                  "normals": normals, "uv": uv, "indices": idx}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": TEXT}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]
    # the screen, behind and larger, so it frames the barrier rather than hiding behind it
    v2, n2, u2, i2 = [], [], [], []
    mesh_box(v2, n2, u2, i2, (-2.05, -0.05, -2.60), (2.05, 2.05, -2.54))
    cmds.append({"defineMesh3D": {"id": 2, "verts": [round(v, 5) for v in v2],
                                  "normals": n2, "uv": u2, "indices": i2}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": ACCENT}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 2, "mode": "software-flat"}}]
    # a floor running from the barrier back to the screen, so the gap between them reads as
    # a distance rather than as empty page
    v3, n3, u3, i3 = [], [], [], []
    mesh_box(v3, n3, u3, i3, (-2.05, -0.06, -2.60), (2.05, -0.02, 0.35))
    cmds.append({"defineMesh3D": {"id": 3, "verts": [round(v, 5) for v in v3],
                                  "normals": n3, "uv": u3, "indices": i3}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": RULE}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 3, "mode": "software-flat"}}]
    # Two streams, one per slit. Each particle runs a single parameter pt from 0 to 1: up to
    # the barrier it travels straight at its slit, and only past the halfway point does the
    # fan term switch on, so the change of direction happens AT the slit rather than before
    # it. The translate follows the rotate deliberately here - that puts the particle at a
    # scene-space position and then turns the whole scene with it, which is what the drag
    # should do. (It is the same ordering that made the turbine hub orbit in set 5, wanted
    # this time.)
    cmds.append({"meshPrimitive3D": {"id": 4, "primitive": "sphere", "segments": 8,
                                     "radius": 0.035, "center": [0, 0, 0]}})
    cmds.append({"createParticles": {
        "id": "beam", "count": 120,
        "variables": ["pt", "ps", "pd", "py"],
        "initialValues": ["rand()",
                          "floor(rand() * 2.0) * 0.28 - 0.14",
                          "(rand() - 0.5) * 1.7",
                          "0.34 + rand() * 0.48"]}})
    cmds.append(paint({"color": GOOD}, {"style": "fill"}))
    cmds.append({"particlesLoop": {
        "system": "@beam",
        "equations": ["(pt + 0.004) % 1.0", "ps", "pd", "py"],
        "commands": [
            {"matrix3D": {"op": "identity"}},
            {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
            {"matrix3D": {"op": "translate",
                          # The barrier sits at z = 0, which the path reaches at
                          # pt = 1.2 / 3.75 = 0.32 - NOT at the halfway point. Bending at
                          # 0.5 had the streams changing direction in open space well
                          # behind the slits, which is the one thing this document must
                          # not show.
                          "x": "@ps + clamp(0.0, 0.68, @pt - 0.32) * @pd",
                          "y": "@py",
                          "z": "1.2 - @pt * 3.75"}},
            {"drawMesh3D": {"mesh": 4, "mode": "software-smooth"}}]}})
    cmds += text_at("the barrier, with two slits in it", 470.0, 364.0, 10.0, TEXT,
                    pan_x=1.0)
    cmds += text_at("drag to turn the scene", 60.0, 578.0, 10.0, DIM)
    cmds += text_at("the screen", 60.0, 126.0, 10.0, ACCENT)
    cmds += text_at("two and a half times further back", 60.0, 142.0, 9.0, DIM)

    # the fringes, flat, under the scene: intensity as a closed path
    fx0, fx1, fy = 40.0, 480.0, 500.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": fx0, "top": fy - 86, "right": fx1,
                              "bottom": fy + 10}})
    N = 90
    cmds.append({"pathCreate": {"id": "fringe", "x": fx0, "y": fy}})
    for i in range(N + 1):
        u = i / float(N)
        th = (u - 0.5) * 9.0
        env = math.cos(th * 0.42) ** 2 if abs(th * 0.42) < math.pi / 2 else 0.0
        inten = env * math.cos(th * 2.1) ** 2
        cmds.append({"pathAppendLineTo": {"path": "fringe",
                                          "x": fx0 + u * (fx1 - fx0),
                                          "y": fy - inten * 80.0}})
    cmds.append({"pathAppendLineTo": {"path": "fringe", "x": fx1, "y": fy}})
    cmds.append({"pathAppendClose": {"path": "fringe"}})
    cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
    cmds.append({"drawPath": {"path": "fringe"}})
    cmds += text_at("bright where the two paths arrive in step", 40.0, fy + 32, 10.5, TEXT)
    cmds += text_at("dark where they arrive exactly out of step - and this happens even "
                    "when the particles go one at a time", 40.0, fy + 50, 10.0, DIM)
    title(cmds, W, H, "Two slits", "the pattern needs the distance behind them")
    return {"header": header(W, H, "Two slits and a screen in 3D, with the interference "
                                   "pattern drawn as a filled path beneath"),
            "root": canvas(cmds, INK)}


# ── 5. BIO-GENE-00022  Gene expression — expression-animation / simulate ────
# A polymerase crossing a gene, mRNA accumulating behind it, ribosomes turning that into
# protein. The clock is shared, so the lag between transcript and protein is visible rather
# than stated - which is the thing that makes regulation hard to reason about.
def gene_expression():
    W, H = 580, 480
    cmds = [var("t", "continuousSec() * 0.18 - floor(continuousSec() * 0.18)")]
    gx0, gx1, gy = 60.0, 520.0, 170.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": gx0, "top": gy - 14, "right": gx1,
                              "bottom": gy + 14}})
    for i in range(24):
        cmds.append(paint({"color": RULE if i % 2 else ACCENT}, {"style": "fill"}))
        x = gx0 + i * (gx1 - gx0) / 24.0
        cmds.append({"drawRect": {"left": x + 1, "top": gy - 11,
                                  "right": x + (gx1 - gx0) / 24.0 - 1, "bottom": gy + 11}})
    cmds += text_at("the gene", gx0, gy - 24, 10.5, DIM)
    # the polymerase, crossing once per cycle
    cmds.append(paint({"color": WARM}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": "%.1f + @t * %.1f" % (gx0, gx1 - gx0),
                                "cy": gy, "radius": 13.0}})
    cmds += text_at("polymerase", 60.0, 128.0, 10.5, WARM)
    # the transcript trailing behind it, drawn as a bar that grows with the same clock
    cmds.append(paint({"color": GOOD}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": gx0, "top": 226.0,
                              "right": "%.1f + @t * %.1f" % (gx0, gx1 - gx0),
                              "bottom": 250.0}})
    cmds += text_at("mRNA, as it is written", gx0, 218.0, 10.5, GOOD)
    # protein lags: it only starts once enough transcript exists, and keeps rising after
    cmds.append(var("prot", "clamp(0.0, 1.0, (@t - 0.28) * 1.55)"))
    cmds.append(paint({"color": HOT}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": gx0, "top": 300.0,
                              "right": "%.1f + @prot * %.1f" % (gx0, gx1 - gx0),
                              "bottom": 324.0}})
    cmds += text_at("protein, once there is something to translate", gx0, 292.0, 10.5, HOT)
    # ribosomes riding the transcript
    for k in range(4):
        cmds.append(paint({"color": TEXT}, {"style": "fill"}))
        cmds.append({"drawCircle": {
            "cx": "%.1f + @prot * %.1f" % (gx0 + 18 + k * 26, (gx1 - gx0) * 0.82),
            "cy": 268.0, "radius": 6.0}})
    cmds += text_at("ribosomes", gx0, 262.0, 9.5, DIM, pan_x=1.0)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": gx0, "y1": 348.0, "x2": gx1, "y2": 348.0}})
    cmds += text_at("the protein is still rising when transcription has already stopped",
                    60.0, 380.0, 11.0, TEXT)
    cmds += text_at("- a cell that switched this gene off a minute ago is still making it",
                    60.0, 400.0, 10.5, DIM)
    title(cmds, W, H, "From gene to protein", "one clock, so the lag is visible")
    return {"header": header(W, H, "A polymerase crossing a gene with mRNA and protein "
                                   "accumulating behind it on a shared clock"),
            "root": canvas(cmds, INK)}


# ── 6. MTH-ALGE-00007  Polynomials — particle-system / analyze / 2D ─────────
# Particles dropped onto a quintic and allowed to run downhill. Where they pile up is where
# the minima are, and the roots are marked separately - two different questions about the
# same curve that beginners routinely conflate.
def polynomials():
    W, H = 560, 460
    px0, px1, cy = 60.0, 520.0, 300.0
    SX, SY = (px1 - px0) / 4.4, 30.0
    def f(u):
        return 0.14 * (u ** 5) - 0.9 * (u ** 3) + 1.1 * u
    cmds = [paint({"color": PANEL}, {"style": "fill"}),
            {"drawRect": {"left": px0, "top": 130.0, "right": px1, "bottom": 400.0}}]
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": px0, "y1": cy, "x2": px1, "y2": cy}})
    cx = (px0 + px1) / 2
    cmds.append({"drawLine": {"x1": cx, "y1": 130.0, "x2": cx, "y2": 400.0}})
    cmds.append(paint({"color": ACCENT}, {"style": "stroke"}, {"width": 2.6},
                      {"strokeCap": "round"}))
    prev = None
    for i in range(89):
        u = -2.2 + 4.4 * i / 88.0
        v = max(-4.4, min(4.4, f(u)))
        pt = (cx + u * SX, cy - v * SY)
        if prev:
            cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1],
                                      "x2": pt[0], "y2": pt[1]}})
        prev = pt
    # the roots, where it crosses
    for r in (-2.42, -1.09, 0.0, 1.09, 2.42):
        if abs(r) <= 2.2:
            cmds.append(paint({"color": GOOD}, {"style": "fill"}))
            cmds.append({"drawCircle": {"cx": cx + r * SX, "cy": cy, "radius": 5.0}})
    cmds += text_at("roots: where it crosses zero", 70.0, 150.0, 10.5, GOOD)
    cmds += text_at("minima: where the particles settle", 70.0, 168.0, 10.5, WARM)
    # Particles resting in the two wells, jittering.
    #
    # The first version evaluated the quintic inside the per-particle draw call. That
    # expression came to about 36 RPN tokens against a cap of 32: rcj wrote it without
    # complaint, the C++ renderer drew it, and the Java writer refused it outright with
    # "to long" - which is the only reason this was caught before a device saw it (F-022).
    # Each well's position is computed in Python instead, so the expression stays short.
    WELLS = []
    for guess in (-1.55, 1.55):
        u = guess
        for _ in range(40):                     # Newton on f'(u) to land in the well
            d1 = 0.7 * u ** 4 - 2.7 * u * u + 1.1
            d2 = 2.8 * u ** 3 - 5.4 * u
            if abs(d2) < 1e-9:
                break
            u -= d1 / d2
        WELLS.append(u)
    for wi, wu in enumerate(WELLS):
        wx = cx + wu * SX
        wy = cy - max(-4.4, min(4.4, f(wu))) * SY
        cmds.append({"createParticles": {
            "id": "well%d" % wi, "count": 40,
            "variables": ["bx", "by", "amp", "ph"],
            "initialValues": ["%.1f + (rand() - 0.5) * 46.0" % wx,
                              "%.1f - rand() * 16.0" % wy,
                              "1.5 + rand() * 3.5", "rand() * 6.28"]}})
        cmds.append(paint({"color": WARM}, {"style": "fill"}))
        cmds.append({"particlesLoop": {
            "system": "@well%d" % wi,
            "equations": ["bx", "by", "amp", "ph + 0.06"],
            "commands": [{"drawCircle": {
                "cx": "@bx", "cy": "@by + sin(@ph) * @amp", "radius": 2.4}}]}})
        cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": wx, "y1": wy + 16, "x2": wx, "y2": cy}})
    cmds += text_at("the particles find the minima; the green dots are the roots",
                    60.0, 426.0, 11.0, TEXT)
    cmds += text_at("- a quintic can have five roots and still only two places to rest",
                    60.0, 444.0, 10.0, DIM)
    title(cmds, W, H, "A quintic", "roots and minima are different questions")
    return {"header": header(W, H, "Particles settling into the minima of a quintic, with "
                                   "its roots marked separately on the axis"),
            "root": canvas(cmds, INK)}


# ── 7. CSC-DS-00007  Linked lists — interactive / explain / 2D ──────────────
# Drag to walk the list. The cost is the lesson: reaching element k means following k
# pointers, and the counter rising as you drag is a more honest account of O(n) than the
# notation is.
def linked_lists():
    W, H = 600, 440
    N = 7
    cmds = [{"touchExpression": {"name": "drag", "defaultValue": 120.0, "min": 50.0,
                                 "max": 550.0, "expression": "touchX()"}},
            var("k", "clamp(0.0, %.1f, floor((@drag - 50.0) / 500.0 * %.1f))"
                     % (N - 1, float(N)))]
    nx0, ny, nw, ngap = 48.0, 200.0, 62.0, 18.0
    for i in range(N):
        x = nx0 + i * (nw + ngap)
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x, "top": ny, "right": x + nw,
                                  "bottom": ny + 54}})
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.2}))
        cmds.append({"drawRect": {"left": x, "top": ny, "right": x + nw,
                                  "bottom": ny + 54}})
        cmds.append({"drawLine": {"x1": x + nw - 20, "y1": ny, "x2": x + nw - 20,
                                  "y2": ny + 54}})
        cmds += text_at("%d" % ((i * 17 + 5) % 90), x + (nw - 20) / 2, ny + 34, 15.0,
                        TEXT, pan_x=0.0)
        if i < N - 1:
            cmds.append(paint({"color": ACCENT}, {"style": "stroke"}, {"width": 2.0},
                              {"strokeCap": "round"}))
            cmds.append({"drawLine": {"x1": x + nw - 10, "y1": ny + 27,
                                      "x2": x + nw + ngap, "y2": ny + 27}})
            cmds.append({"drawLine": {"x1": x + nw + ngap, "y1": ny + 27,
                                      "x2": x + nw + ngap - 7, "y2": ny + 22}})
            cmds.append({"drawLine": {"x1": x + nw + ngap, "y1": ny + 27,
                                      "x2": x + nw + ngap - 7, "y2": ny + 32}})
        else:
            cmds += text_at("null", x + nw - 10, ny + 33, 9.0, DIM)
    # the cursor, which is the only thing that moves
    cmds.append(paint({"color": HOT}, {"style": "stroke"}, {"width": 2.6}))
    cmds.append({"drawRect": {"left": "%.1f + @k * %.1f" % (nx0 - 4, nw + ngap),
                              "top": ny - 4,
                              "right": "%.1f + @k * %.1f" % (nx0 + nw + 4, nw + ngap),
                              "bottom": ny + 58}})
    cmds += text_at("head", nx0, ny - 16, 10.0, DIM)
    cmds += [{"variable": {"name": "klabel", "commit": True,
                           "value": {"type": "textFromFloat", "value": "@k",
                                     "whole": 1, "decimal": 0}}},
             paint({"color": HOT}, {"style": "fill"}, {"textSize": 13.0}),
             {"drawTextAnchored": {"text": "@klabel", "x": 188.0, "y": 318.0,
                                   "panX": -1.0, "panY": 0.0, "flags": 0}}]
    cmds += text_at("pointers followed:", 60.0, 318.0, 13.0, TEXT)
    cmds.append({"conditionalOperations": {
        "condition": "lt", "v1": "@k", "v2": 1.0,
        "commands": [paint({"color": GOOD}, {"style": "fill"}, {"textSize": 11.0}),
                     {"drawTextAnchored": {
                         "text": "the head is free - you already have it",
                         "x": 230.0, "y": 318.0, "panX": -1.0, "panY": 0.0, "flags": 0}}]}})
    cmds.append({"conditionalOperations": {
        "condition": "ge", "v1": "@k", "v2": 1.0,
        "commands": [paint({"color": WARM}, {"style": "fill"}, {"textSize": 11.0}),
                     {"drawTextAnchored": {
                         "text": "every one of them a jump to somewhere else in memory",
                         "x": 230.0, "y": 318.0, "panX": -1.0, "panY": 0.0, "flags": 0}}]}})
    cmds += text_at("an array would have computed the address and gone straight there",
                    60.0, 366.0, 11.0, TEXT)
    cmds += text_at("- what a list buys instead is inserting in the middle without "
                    "moving anything", 60.0, 386.0, 10.5, DIM)
    title(cmds, W, H, "Walking a linked list", "drag to move along it")
    return {"header": header(W, H, "Drag along a seven-node linked list, counting the "
                                   "pointers that must be followed to reach each node"),
            "root": canvas(cmds, INK)}


# ── 8. CHM-MS-00007  Molecular geometry — raster-and-text / explore / 2D ────
# Five VSEPR shapes with their angles. Electron pairs repel, and every one of these shapes
# is the answer to "where do N things sit on a sphere so as to be as far apart as possible" -
# so the angles are printed, because they are the evidence.
def geometry():
    W, H = 600, 470
    SHAPES = [("Linear", 2, 0, "180", "CO2", GOOD),
              ("Trigonal planar", 3, 0, "120", "BF3", ACCENT),
              ("Tetrahedral", 4, 0, "109.5", "CH4", WARM),
              ("Trigonal pyramidal", 3, 1, "107", "NH3", HOT),
              ("Bent", 2, 2, "104.5", "H2O", TEXT)]
    cmds = []
    cw = 112.0
    for i, (name, bonds, lone, angle, eg, colour) in enumerate(SHAPES):
        cx = 72.0 + i * cw
        cy = 220.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": cx - 50, "top": 140.0, "right": cx + 50,
                                  "bottom": 300.0}})
        # bonds laid out at the real angle, which is the whole point of the card
        total = bonds + lone
        spread = {2: 180.0, 3: 120.0, 4: 109.5}.get(total, 120.0)
        start = -90.0 - spread * (total - 1) / 2.0
        for b in range(total):
            a = math.radians(start + b * spread)
            ex, ey = cx + 40 * math.cos(a), cy + 40 * math.sin(a)
            is_lone = b >= bonds
            cmds.append(paint({"color": RULE if is_lone else colour}, {"style": "stroke"},
                              {"width": 1.6 if is_lone else 3.0}, {"strokeCap": "round"}))
            cmds.append({"drawLine": {"x1": cx, "y1": cy, "x2": ex, "y2": ey}})
            cmds.append(paint({"color": RULE if is_lone else colour}, {"style": "fill"}))
            cmds.append({"drawCircle": {"cx": ex, "cy": ey, "radius": 8.0 if not is_lone
                                        else 5.0}})
        cmds.append(paint({"color": TEXT}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": cx, "cy": cy, "radius": 12.0}})
        # the angle, as an arc between the first two arms
        cmds.append(paint({"color": DIM}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawArc": {"left": cx - 24, "top": cy - 24, "right": cx + 24,
                                 "bottom": cy + 24, "startAngle": start,
                                 "sweepAngle": spread}})
        cmds += text_at(angle + "°", cx, cy + 46, 11.0, colour, pan_x=0.0)
        cmds += text_at(name, cx, 322.0, 10.0, TEXT, pan_x=0.0)
        cmds += text_at(eg, cx, 340.0, 11.5, colour, pan_x=0.0)
        if lone:
            cmds += text_at("%d lone pair%s" % (lone, "s" if lone > 1 else ""),
                            cx, 358.0, 9.0, DIM, pan_x=0.0)
    cmds += text_at("a lone pair takes more room than a bond, which is why the last two "
                    "are squeezed", 60.0, 404.0, 11.0, TEXT)
    cmds += text_at("below the angle the same number of arms would otherwise give",
                    60.0, 422.0, 10.5, DIM)
    title(cmds, W, H, "Where the atoms sit", "five shapes, and the angles that prove them")
    return {"header": header(W, H, "Five VSEPR geometries drawn at their true bond angles, "
                                   "with lone pairs shown"),
            "root": canvas(cmds, INK)}


# ── 9. EAR-GEOP-00007  Earth interior — static-diagram / explore / 2D ───────
# The layers at true relative thickness, which is the one thing textbook cutaways get wrong:
# the crust is a skin. Drawing it to scale and then naming the number is the argument.
def earth_interior():
    W, H = 520, 600
    LAYERS = [("Inner core", 0, 1221, "solid iron, under so much pressure it cannot melt",
               HOT),
              ("Outer core", 1221, 3480, "liquid iron - this is what makes the magnetic field",
               WARM),
              ("Mantle", 3480, 6371 - 35, "rock that flows, given a few million years", ACCENT),
              ("Crust", 6371 - 35, 6371, "5 to 70 km. Everything anyone has ever seen.", GOOD)]
    R, cx, cy = 158.0, 260.0, 248.0
    cmds = []
    for name, r0, r1, note, colour in reversed(LAYERS):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": cx, "cy": cy, "radius": R * r1 / 6371.0}})
    cmds.append(paint({"color": INK}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawCircle": {"cx": cx, "cy": cy, "radius": R}})

    # The legend sits BELOW the globe rather than beside it. Leader lines into a disc this
    # size cross each other and land on colours the text cannot be read against, which is
    # what the first version did.
    y = 430.0
    for name, r0, r1, note, colour in LAYERS:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 44.0, "top": y - 10, "right": 58.0,
                                  "bottom": y + 4}})
        cmds += text_at(name, 68.0, y, 12.0, colour)
        cmds += text_at("%d km" % (r1 - r0), 212.0, y, 10.5, TEXT, pan_x=1.0)
        cmds += text_at(note, 224.0, y, 9.5, DIM)
        y += 30.0

    # the crust, called out on the globe itself, because at this scale it is one line
    ax = cx + R * 0.72
    ay = cy - R * 0.70
    cmds.append(paint({"color": GOOD}, {"style": "stroke"}, {"width": 1.2}))
    cmds.append({"drawLine": {"x1": ax, "y1": ay, "x2": 384.0, "y2": 104.0}})
    cmds.append(paint({"color": GOOD}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": ax, "cy": ay, "radius": 3.0}})
    cmds += text_at("the crust is this line", 500.0, 100.0, 10.5, GOOD, pan_x=1.0)
    cmds += text_at("1 px here is about 40 km", 500.0, 116.0, 9.0, DIM, pan_x=1.0)
    # a scale bar, so "to scale" is checkable rather than asserted
    cmds.append(paint({"color": DIM}, {"style": "stroke"}, {"width": 1.4}))
    cmds.append({"drawLine": {"x1": 44.0, "y1": 396.0,
                              "x2": 44.0 + R * 2000.0 / 6371.0, "y2": 396.0}})
    cmds += text_at("2000 km", 44.0, 390.0, 9.0, DIM)
    title(cmds, W, H, "Inside the Earth", "drawn to scale, which is the surprise")
    return {"header": header(W, H, "The Earth's internal layers at true relative thickness, "
                                   "with the crust called out as a single line"),
            "root": canvas(cmds, INK)}


# ── 10. ENG-EE-00007  Circuits — annotated-layout / compare / 2D ────────────
# Series against parallel, each with its own schematic and the arithmetic underneath. The
# two cards are identical in structure so the only thing that differs is the thing being
# compared, which is what makes a comparison honest.
def circuits():
    W, H = 560, 560

    def schematic(series, colour):
        c = [{"clipRect": {"left": 0, "top": 0, "right": 230, "bottom": 120}},
             paint({"color": RULE}, {"style": "fill"}),
             {"drawRect": {"left": 0, "top": 0, "right": 230, "bottom": 120}}]
        c.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.8}))
        # battery
        c.append({"drawLine": {"x1": 20, "y1": 40, "x2": 20, "y2": 80}})
        c.append({"drawLine": {"x1": 28, "y1": 50, "x2": 28, "y2": 70}})
        if series:
            c.append({"drawLine": {"x1": 20, "y1": 40, "x2": 20, "y2": 24}})
            c.append({"drawLine": {"x1": 20, "y1": 24, "x2": 210, "y2": 24}})
            c.append({"drawLine": {"x1": 210, "y1": 24, "x2": 210, "y2": 96}})
            c.append({"drawLine": {"x1": 210, "y1": 96, "x2": 20, "y2": 96}})
            c.append({"drawLine": {"x1": 20, "y1": 96, "x2": 20, "y2": 80}})
            for k in range(2):
                x = 80 + k * 68
                c.append(paint({"color": colour}, {"style": "fill"}))
                c.append({"drawRect": {"left": x, "top": 16, "right": x + 40,
                                       "bottom": 32}})
                c.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.8}))
        else:
            c.append({"drawLine": {"x1": 20, "y1": 40, "x2": 20, "y2": 24}})
            c.append({"drawLine": {"x1": 20, "y1": 24, "x2": 210, "y2": 24}})
            c.append({"drawLine": {"x1": 210, "y1": 24, "x2": 210, "y2": 96}})
            c.append({"drawLine": {"x1": 210, "y1": 96, "x2": 20, "y2": 96}})
            c.append({"drawLine": {"x1": 20, "y1": 96, "x2": 20, "y2": 80}})
            for k in range(2):
                y = 44 + k * 32
                c.append({"drawLine": {"x1": 96, "y1": 24, "x2": 96, "y2": y}})
                c.append({"drawLine": {"x1": 96, "y1": y, "x2": 124, "y2": y}})
                c.append({"drawLine": {"x1": 164, "y1": y, "x2": 164, "y2": y}})
                c.append({"drawLine": {"x1": 164, "y1": y, "x2": 164, "y2": 96}})
                c.append(paint({"color": colour}, {"style": "fill"}))
                c.append({"drawRect": {"left": 124, "top": y - 7, "right": 164,
                                       "bottom": y + 7}})
                c.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.8}))
        return {"type": "canvas", "modifiers": [{"width": 230}, {"height": 120}],
                "commands": c}

    def card(title_s, series, colour, formula, total, current, note):
        return {"type": "column",
                "modifiers": [{"width": 250}, {"padding": 10}, {"background": PANEL}],
                "children": [
                    {"type": "text", "value": title_s, "modifiers": [],
                     "fontSize": 14.0, "color": colour},
                    {"type": "spacer", "modifiers": [{"height": 8}]},
                    schematic(series, colour),
                    {"type": "spacer", "modifiers": [{"height": 9}]},
                    {"type": "text", "value": formula, "modifiers": [],
                     "fontSize": 11.0, "color": TEXT},
                    {"type": "spacer", "modifiers": [{"height": 4}]},
                    {"type": "text", "value": total, "modifiers": [],
                     "fontSize": 13.0, "color": colour},
                    {"type": "text", "value": current, "modifiers": [],
                     "fontSize": 11.0, "color": TEXT},
                    {"type": "spacer", "modifiers": [{"height": 6}]},
                    {"type": "text", "value": note, "modifiers": [],
                     "fontSize": 9.5, "color": DIM}]}

    return {"header": header(W, H, "Two 100 ohm resistors in series and in parallel, with "
                                   "the same battery and the arithmetic for each"),
            "root": {"type": "column",
                     "modifiers": ["fillMaxSize", {"padding": 18}, {"background": INK}],
                     "children": [
                         {"type": "text", "value": "Two resistors, two ways",
                          "modifiers": [], "fontSize": 19.0, "color": TEXT},
                         {"type": "spacer", "modifiers": [{"height": 3}]},
                         {"type": "text",
                          "value": "same two 100 ohm parts, same 12 V battery",
                          "modifiers": [], "fontSize": 11.0, "color": DIM},
                         {"type": "spacer", "modifiers": [{"height": 14}]},
                         {"type": "row", "modifiers": [{"width": 520}], "children": [
                             card("In series", True, ACCENT, "R = R1 + R2",
                                  "200 ohms", "I = 12 / 200 = 60 mA",
                                  "one path, so the same current goes through both"),
                             {"type": "spacer", "modifiers": [{"width": 16}]},
                             card("In parallel", False, GOOD, "1/R = 1/R1 + 1/R2",
                                  "50 ohms", "I = 12 / 50 = 240 mA",
                                  "two paths, so each gets the full voltage")]},
                         {"type": "spacer", "modifiers": [{"height": 16}]},
                         {"type": "text",
                          "value": "Adding a resistor in parallel LOWERS the resistance, "
                                   "which reads as wrong until you notice you have added a "
                                   "road, not a narrowing.",
                          "modifiers": [], "fontSize": 11.0, "color": TEXT},
                         {"type": "spacer", "modifiers": [{"height": 6}]},
                         {"type": "text",
                          "value": "The parallel circuit draws four times the current from "
                                   "the same battery, which is how a wall socket ends up "
                                   "overloaded.",
                          "modifiers": [], "fontSize": 10.0, "color": DIM}]}}


# ── 11. MED-DP-00003  Cancer — data-plot / demonstrate / 3D ─────────────────
# Tumour burden as a surface over treatment time and resistance fraction. A surface because
# the clinically important feature is a saddle: the same treatment that collapses a sensitive
# tumour selects for the resistant cells that come back.
def cancer():
    W, H = 540, 620
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.78,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [2.7, 1.9, 4.3], "center": [0.0, 0.02, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.42, -0.6, -0.68], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.25, 0.5], "intensity": 0.42}]}}]
    cmds.append(var("spin", "sin(continuousSec() * 0.22) * 0.5"))

    def burden(u, v):
        """u: time under treatment. v: fraction of cells already resistant."""
        kill = math.exp(-3.4 * u) * (1.0 - v)
        regrow = v * (1.0 - math.exp(-2.6 * u)) * 1.25
        return kill + regrow

    # Axis rods first, so the surface has something to sit in. Floating in black it read as
    # a sail rather than a landscape, and neither axis meant anything.
    draw_axes(cmds, [(5, axis_rod(5, (-1.0, -0.42, 1.0), (1.0, -0.42, 1.0), 
                                  [-0.5, 0.0, 0.5], "x")),
                     (6, axis_rod(6, (-1.0, -0.42, -1.0), (-1.0, -0.42, 1.0),
                                  [-0.5, 0.0, 0.5], "z")),
                     (7, axis_rod(7, (-1.0, -0.42, 1.0), (-1.0, 0.62, 1.0),
                                  [0.0, 0.3], "y"))],
              "@spin", [DIM, DIM, DIM])
    cmds.append(surface_mesh(1, burden, 26, half=1.0, yscale=0.82, yoff=-0.40))
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": ACCENT}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]
    cmds += text_at("time under treatment", 310.0, 452.0, 10.0, DIM, pan_x=0.0)
    cmds += text_at("fraction already resistant", 110.0, 452.0, 10.0, DIM, pan_x=0.0)
    cmds += text_at("tumour burden", 46.0, 150.0, 10.5, TEXT)

    ROWS = [("A tumour with no resistant cells", "collapses, and stays collapsed", GOOD),
            ("One per cent resistant", "falls, then returns from the survivors", WARM),
            ("Ten per cent resistant", "barely dips - you are treating the wrong cells",
             HOT)]
    y = 486.0
    for name, what, colour in ROWS:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 40.0, "top": y - 10, "right": 45.0,
                                  "bottom": y + 6}})
        cmds += text_at(name, 56.0, y, 11.0, colour)
        cmds += text_at(what, 56.0, y + 15, 9.5, DIM)
        y += 36.0
    title(cmds, W, H, "Why it comes back", "the same treatment, three starting mixtures")
    return {"header": header(W, H, "Tumour burden as a 3D surface over treatment time and "
                                   "the fraction of resistant cells"),
            "root": canvas(cmds, INK)}


# ── 12. MED-DP-00004  Cardiovascular disease — path-form / simulate / 2D ────
# A vessel narrowing, drawn as two paths with the lumen between them, and the flow that
# results. Flow falls as the fourth power of the radius, so a vessel can lose half its
# diameter and most of its flow while the person feels nothing until they climb stairs.
def cardiovascular():
    W, H = 580, 500
    cmds = [{"touchExpression": {"name": "drag", "defaultValue": 160.0, "min": 60.0,
                                 "max": 520.0, "expression": "touchX()"}},
            var("narrow", "clamp(0.0, 0.82, (@drag - 60.0) / 460.0 * 0.82)")]
    vx0, vx1, vcy, vr = 60.0, 520.0, 220.0, 54.0
    # the vessel wall: two static paths
    for sign, pid in ((-1.0, "wallTop"), (1.0, "wallBot")):
        cmds.append({"pathCreate": {"id": pid, "x": vx0, "y": vcy + sign * vr}})
        for i in range(1, 41):
            u = i / 40.0
            cmds.append({"pathAppendLineTo": {"path": pid, "x": vx0 + u * (vx1 - vx0),
                                              "y": vcy + sign * vr}})
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 3.0}))
        cmds.append({"drawPath": {"path": pid}})
    # the lumen, as a filled band whose half-height follows the drag
    cmds.append(paint({"color": HOT}, {"style": "fill"}))
    for i in range(40):
        u0, u1 = i / 40.0, (i + 1) / 40.0
        bump0 = math.exp(-((u0 - 0.5) / 0.14) ** 2)
        bump1 = math.exp(-((u1 - 0.5) / 0.14) ** 2)
        x0 = vx0 + u0 * (vx1 - vx0)
        x1 = vx0 + u1 * (vx1 - vx0)
        cmds.append({"drawRect": {
            "left": x0, "right": x1 + 1,
            "top": "%.2f - %.2f * (1.0 - @narrow * %.4f)" % (vcy, vr - 4, bump0),
            "bottom": "%.2f + %.2f * (1.0 - @narrow * %.4f)" % (vcy, vr - 4, bump1)}})
    cmds += text_at("plaque", 290.0, vcy - vr - 14, 10.5, WARM, pan_x=0.0)
    cmds += text_at("blood", 90.0, vcy + 5, 10.5, INK)
    # flow, as the fourth power of what is left
    cmds.append(var("open", "1.0 - @narrow"))
    cmds.append(var("flow", "@open * @open * @open * @open"))
    bx0, bw2 = 60.0, 460.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": bx0, "top": 336.0, "right": bx0 + bw2,
                              "bottom": 364.0}})
    cmds.append(paint({"color": GOOD}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": bx0, "top": 336.0,
                              "right": "%.1f + @flow * %.1f" % (bx0, bw2),
                              "bottom": 364.0}})
    cmds += text_at("flow, relative to a clear vessel", bx0, 328.0, 10.5, DIM)
    cmds += [{"variable": {"name": "pct", "commit": True,
                           "value": {"type": "textFromFloat", "value": "@flow * 100.0",
                                     "whole": 3, "decimal": 0}}},
             paint({"color": TEXT}, {"style": "fill"}, {"textSize": 15.0}),
             {"drawTextAnchored": {"text": "@pct", "x": bx0, "y": 394.0,
                                   "panX": -1.0, "panY": 0.0, "flags": 0}}]
    cmds += text_at("per cent", bx0 + 44, 394.0, 11.0, DIM)
    cmds.append({"conditionalOperations": {
        "condition": "lt", "v1": "@flow", "v2": 0.35,
        "commands": [paint({"color": HOT}, {"style": "fill"}, {"textSize": 11.0}),
                     {"drawTextAnchored": {
                         "text": "this is where climbing stairs starts to hurt",
                         "x": 160.0, "y": 394.0, "panX": -1.0, "panY": 0.0, "flags": 0}}]}})
    cmds += text_at("halve the radius and you lose fifteen sixteenths of the flow",
                    60.0, 436.0, 11.0, TEXT)
    cmds += text_at("- which is why a narrowing can be severe long before it is felt",
                    60.0, 456.0, 10.5, DIM)
    title(cmds, W, H, "A narrowing artery", "drag to close it")
    return {"header": header(W, H, "Drag to narrow an artery and watch flow fall as the "
                                   "fourth power of the remaining radius"),
            "root": canvas(cmds, INK)}


# ── 13. MED-DP-00005  Infection — expression-animation / analyze / 2D ───────
# Two epidemics on one clock, differing only in how fast people meet. The areas are equal in
# neither height nor time, and the flat line across the middle is the thing the whole shape
# is being compared against.
def infection():
    W, H = 580, 470
    N = 72
    def curve(beta):
        s, i, r = 0.995, 0.005, 0.0
        out = []
        for _ in range(N):
            ns = s - beta * s * i * 0.42
            ni = i + beta * s * i * 0.42 - i * 0.14
            s, i, r = max(0.0, ns), max(0.0, ni), r
            out.append(i)
        return out
    FAST, SLOW = curve(2.6), curve(1.35)
    peak = max(max(FAST), max(SLOW))
    px0, px1, py0, py1 = 60.0, 530.0, 140.0, 330.0
    cmds = [var("t", "continuousSec() * 0.1 - floor(continuousSec() * 0.1)")]
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    # the capacity line, which is what "flatten the curve" is about
    cap_y = py1 - (py1 - py0) * 0.34
    cmds.append(paint({"color": HOT}, {"style": "stroke"}, {"width": 1.6}))
    cmds.append({"drawLine": {"x1": px0, "y1": cap_y, "x2": px1, "y2": cap_y}})
    cmds += text_at("what the hospitals can take", px1 - 8, cap_y - 8, 10.0, HOT, pan_x=1.0)
    for series, colour, name in ((FAST, WARM, "people meeting freely"),
                                 (SLOW, GOOD, "meeting half as often")):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6},
                          {"strokeCap": "round"}))
        prev = None
        for i, v in enumerate(series):
            x = px0 + (px1 - px0) * i / (N - 1.0)
            y = py1 - (v / peak) * (py1 - py0) * 0.92
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": x, "y2": y}})
            prev = (x, y)
        pk = series.index(max(series))
        cmds += text_at(name, px0 + (px1 - px0) * pk / (N - 1.0) + 8,
                        py1 - (max(series) / peak) * (py1 - py0) * 0.92 - 8, 10.0, colour)
    # a marker sweeping both curves on the shared clock
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.4}))
    cmds.append({"drawLine": {"x1": "%.1f + @t * %.1f" % (px0, px1 - px0), "y1": py0,
                              "x2": "%.1f + @t * %.1f" % (px0, px1 - px0), "y2": py1}})
    cmds += text_at("days", (px0 + px1) / 2, py1 + 22, 10.0, DIM, pan_x=0.0)
    cmds += text_at("people sick at once", px0, py0 - 12, 10.5, DIM)
    cmds += text_at("the slower epidemic infects almost as many people in total",
                    60.0, 372.0, 11.0, TEXT)
    cmds += text_at("- it just never asks for more beds than exist on any one day",
                    60.0, 392.0, 10.5, DIM)
    title(cmds, W, H, "Flattening a curve", "the same disease, met at two speeds")
    return {"header": header(W, H, "Two epidemic curves on one clock, differing only in "
                                   "contact rate, against a fixed hospital capacity"),
            "root": canvas(cmds, INK)}


# ── 14. MED-DP-00006  Neurological disease — particle-system / explain / 2D ─
# A signal crossing a synapse, and the same synapse with fewer vesicles. Particles because
# transmission is stochastic: it is not that the signal weakens, it is that fewer packets
# arrive, and below a threshold the next cell simply does not fire.
def neuro():
    W, H = 560, 520
    cmds = []
    for col, (label, count, colour, fires) in enumerate(
            (("Healthy", 60, GOOD, True), ("Degenerating", 14, HOT, False))):
        x0 = 50.0 + col * 258.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": 140.0, "right": x0 + 222,
                                  "bottom": 360.0}})
        cmds += text_at(label, x0 + 111, 132.0, 13.0, colour, pan_x=0.0)
        # the two cells
        cmds.append(paint({"color": RULE}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0 + 12, "top": 160.0, "right": x0 + 210,
                                  "bottom": 198.0}})
        cmds.append({"drawRect": {"left": x0 + 12, "top": 302.0, "right": x0 + 210,
                                  "bottom": 340.0}})
        cmds += text_at("sending", x0 + 20, 184.0, 9.5, DIM)
        cmds += text_at("receiving", x0 + 20, 326.0, 9.5, DIM)
        cmds.append({"createParticles": {
            "id": "ves%d" % col, "count": count,
            "variables": ["vx", "vy", "vs", "ph"],
            "initialValues": ["%.1f + rand() * 186.0" % (x0 + 18),
                              "200 + rand() * 96",
                              "0.4 + rand() * 1.1", "rand() * 6.28"]}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"particlesLoop": {
            "system": "@ves%d" % col,
            "equations": ["vx", "200 + ((vy - 200 + vs) % 96)", "vs", "ph"],
            "commands": [{"drawCircle": {"cx": "@vx", "cy": "@vy", "radius": 2.6}}]}})
        # whether the receiving cell fires
        cmds.append(paint({"color": colour if fires else RULE}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0 + 12, "top": 302.0,
                                  "right": x0 + 210 if fires else x0 + 54,
                                  "bottom": 340.0}})
        cmds += text_at("fires" if fires else "does not reach threshold",
                        x0 + 111, 326.0, 10.5, INK if fires else DIM, pan_x=0.0)
        cmds += text_at("%d vesicles" % count, x0 + 111, 378.0, 10.5, colour, pan_x=0.0)
    cmds += text_at("the surviving neurons are working normally", 50.0, 428.0, 11.0, TEXT)
    cmds += text_at("- there are simply not enough of them left to carry the signal, which "
                    "is why symptoms appear suddenly", 50.0, 448.0, 10.5, DIM)
    cmds += text_at("after years of quiet loss", 50.0, 466.0, 10.5, DIM)
    title(cmds, W, H, "A synapse, twice", "same machinery, fewer packets")
    return {"header": header(W, H, "A healthy synapse and a degenerating one as particle "
                                   "systems, with only the receiving cell's response differing"),
            "root": canvas(cmds, INK)}


# ── 15. SOC-PSYC-00006  Memory — interactive / explore / 2D ────────────────
# The forgetting curve, with a second curve showing what one review does to it. Dragging
# through time rather than reading a chart is the point: the gap between the two curves is
# small on day one and enormous on day thirty.
def memory():
    W, H = 580, 500
    cmds = [{"touchExpression": {"name": "drag", "defaultValue": 120.0, "min": 60.0,
                                 "max": 530.0, "expression": "touchX()"}},
            var("day", "clamp(0.0, 30.0, (@drag - 60.0) / 470.0 * 30.0)")]
    px0, px1, py0, py1 = 60.0, 530.0, 140.0, 340.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 0.8}))
    for f in (0.25, 0.5, 0.75):
        y = py1 - f * (py1 - py0)
        cmds.append({"drawLine": {"x1": px0, "y1": y, "x2": px1, "y2": y}})
        cmds += text_at("%d%%" % int(f * 100), px0 - 6, y + 4, 9.0, DIM, pan_x=1.0)
    def plain(d):
        return math.exp(-d / 4.2)
    def reviewed(d):
        return plain(d) if d < 7 else min(1.0, 0.92 * math.exp(-(d - 7) / 19.0))
    for fn, colour, name in ((plain, HOT, "read once"),
                             (reviewed, GOOD, "reviewed on day seven")):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6},
                          {"strokeCap": "round"}))
        prev = None
        for i in range(61):
            d = i / 60.0 * 30.0
            pt = (px0 + (px1 - px0) * d / 30.0, py1 - fn(d) * (py1 - py0))
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1],
                                          "x2": pt[0], "y2": pt[1]}})
            prev = pt
        cmds += text_at(name, px1 - 8, py1 - fn(30.0) * (py1 - py0) - 8, 10.0,
                        colour, pan_x=1.0)
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.4}))
    cmds.append({"drawLine": {"x1": "%.1f + @day / 30.0 * %.1f" % (px0, px1 - px0),
                              "y1": py0,
                              "x2": "%.1f + @day / 30.0 * %.1f" % (px0, px1 - px0),
                              "y2": py1}})
    for d in (0, 10, 20, 30):
        cmds += text_at("%d" % d, px0 + (px1 - px0) * d / 30.0, py1 + 22, 9.5,
                        DIM, pan_x=0.0)
    cmds += text_at("days since learning", (px0 + px1) / 2, py1 + 42, 10.0, DIM, pan_x=0.0)
    cmds += text_at("still remembered", px0, py0 - 12, 10.5, DIM)
    cmds += text_at("day", 60.0, 408.0, 12.0, DIM)
    cmds += [{"variable": {"name": "dlabel", "commit": True,
                           "value": {"type": "textFromFloat", "value": "@day",
                                     "whole": 2, "decimal": 0}}},
             paint({"color": TEXT}, {"style": "fill"}, {"textSize": 14.0}),
             {"drawTextAnchored": {"text": "@dlabel", "x": 98.0, "y": 408.0,
                                   "panX": -1.0, "panY": 0.0, "flags": 0}}]
    cmds.append({"conditionalOperations": {
        "condition": "lt", "v1": "@day", "v2": 7.0,
        "commands": [paint({"color": DIM}, {"style": "fill"}, {"textSize": 11.0}),
                     {"drawTextAnchored": {
                         "text": "before the review, the two are the same curve",
                         "x": 150.0, "y": 408.0, "panX": -1.0, "panY": 0.0, "flags": 0}}]}})
    cmds.append({"conditionalOperations": {
        "condition": "ge", "v1": "@day", "v2": 7.0,
        "commands": [paint({"color": GOOD}, {"style": "fill"}, {"textSize": 11.0}),
                     {"drawTextAnchored": {
                         "text": "one review, and the forgetting slows down for weeks",
                         "x": 150.0, "y": 408.0, "panX": -1.0, "panY": 0.0, "flags": 0}}]}})
    cmds += text_at("the review costs minutes and is worth more the longer you leave it "
                    "- up to a point", 60.0, 450.0, 10.5, TEXT)
    title(cmds, W, H, "Forgetting", "drag through a month")
    return {"header": header(W, H, "A forgetting curve against the same curve with one "
                                   "review on day seven, draggable through a month"),
            "root": canvas(cmds, INK)}


# ── 16. SOC-PSYC-00007  Perception — raster-and-text / compare / 3D ────────
# Two cubes identical on the page and different in space. Depth is the dimension a flat image
# throws away, and every cue the brain uses to put it back is a guess that can be wrong -
# which is what makes this the right slot for 3D rather than a drawing of 3D.
def perception():
    W, H = 520, 600
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.70,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [0.0, 0.5, 4.2], "center": [0.0, 0.42, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.35, -0.6, -0.72], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.55, 0.3, 0.5], "intensity": 0.4}]}}]
    # near-small and far-large: they subtend the same angle, so they measure the same on
    # the page and are nothing like the same object
    for mid, (cxw, cz, size, colour) in enumerate((( -0.62, 0.9, 0.30, GOOD),
                                                   (0.95, -1.6, 0.62, WARM))):
        verts, normals, uv, idx = [], [], [], []
        mesh_box(verts, normals, uv, idx,
                 (cxw - size, 0.42 - size, cz - size), (cxw + size, 0.42 + size, cz + size))
        cmds.append({"defineMesh3D": {"id": 10 + mid, "verts": [round(v, 5) for v in verts],
                                      "normals": normals, "uv": uv, "indices": idx}})
        cmds += [{"matrix3D": {"op": "identity"}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": 10 + mid, "mode": "software-smooth"}}]
    # a ground plane, because without one there is no distance information at all
    v2, n2, u2, i2 = [], [], [], []
    mesh_box(v2, n2, u2, i2, (-3.0, -0.02, -3.2), (3.0, 0.0, 1.6))
    cmds.append({"defineMesh3D": {"id": 20, "verts": [round(v, 5) for v in v2],
                                  "normals": n2, "uv": u2, "indices": i2}})
    cmds += [{"matrix3D": {"op": "identity"}},
             paint({"color": PANEL}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 20, "mode": "software-flat"}}]
    cmds += text_at("near, small", 140.0, 352.0, 10.5, GOOD, pan_x=0.0)
    cmds += text_at("far, large", 370.0, 268.0, 10.5, WARM, pan_x=0.0)

    CUES = [("Occlusion", "whatever covers the other is nearer. Almost never wrong."),
            ("Relative size", "if they are the same object, the smaller is further"),
            ("Height in field", "further things sit higher, up to the horizon"),
            ("Texture gradient", "detail crowds together with distance")]
    y = 408.0
    for name, note in CUES:
        cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 40.0, "top": y - 9, "right": 44.0,
                                  "bottom": y + 5}})
        cmds += text_at(name, 54.0, y, 11.5, TEXT)
        cmds += text_at(note, 164.0, y, 9.5, DIM)
        y += 26.0
    cmds += text_at("remove the ground and these two cubes become the same cube at two "
                    "sizes", 40.0, 528.0, 10.5, TEXT)
    cmds += text_at("- every cue here is an assumption the room is normally kind enough "
                    "to satisfy", 40.0, 546.0, 10.0, DIM)
    title(cmds, W, H, "Putting depth back", "the dimension a picture throws away")
    return {"header": header(W, H, "Two cubes at different distances and sizes on a ground "
                                   "plane, with the depth cues that disambiguate them"),
            "root": canvas(cmds, INK)}


# ── build ──────────────────────────────────────────────────────────────────────
BUILD = [("PHY-QM-00021", wavefunctions), ("PHY-QM-00022", distributions),
         ("PHY-QM-00023", tunneling), ("PHY-QM-00024", double_slit),
         ("BIO-GENE-00022", gene_expression), ("MTH-ALGE-00007", polynomials),
         ("CSC-DS-00007", linked_lists), ("CHM-MS-00007", geometry),
         ("EAR-GEOP-00007", earth_interior), ("ENG-EE-00007", circuits),
         ("MED-DP-00003", cancer), ("MED-DP-00004", cardiovascular),
         ("MED-DP-00005", infection), ("MED-DP-00006", neuro),
         ("SOC-PSYC-00006", memory), ("SOC-PSYC-00007", perception)]

if __name__ == "__main__":
    for doc_id, fn in BUILD:
        name = use(doc_id)
        d = fn()
        (OUT / ("%s.json" % doc_id)).write_text(json.dumps(d, indent=1) + "\n")
        print("  %-16s %-9s %s" % (doc_id, name, d["header"]["contentDescription"][:50]))
    print("  %d documents" % len(BUILD))
