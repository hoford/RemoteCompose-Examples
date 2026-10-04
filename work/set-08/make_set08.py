#!/usr/bin/env python3
"""Build set 8 of the visualization programme: 16 documents.

    python3 work/set-08/make_set08.py

Work order from `python3 tools/visplan.py set 8`. Four 3D slots: spin, seismic waves, trade
and ancient civilisations. The first three earn it plainly - a spin state IS a direction in
space, a seismic wave is the Earth's interior sampled along a ray, and trade is a flow between
places on a globe. The fourth is the weak one, and is kept honest by making the third
dimension carry time depth rather than decorating a map.

History opens here as a new area, which brings a hazard the sciences do not: a date is a
claim. Where a figure is disputed or approximate this says so on the document rather than
printing a confident number.

Helper block carried from set 7. Rules paid for by earlier sets, all load-bearing here:

  clipRect is permanent         intersects, never widens (F-021) - clip last, or in a child
  textFromFloat wants a string  a numeric literal renders as 0, silently (F-020)
  expressions cap at 32 tokens  rcj writes longer ones that a device refuses (F-022)
  3D fills the document         a scene in a sized card projects outside it (F-013)
  translate after rotate        rides the rotated frame - useful, but on purpose
  scale is about the origin     it moves anything not sitting there
  clamp(min, max, value)        the value goes last
  render with --clock AND --seed  the clock alone does not pin rand() (F-023)
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


def embedded_bitmap(name, rel_path):
    """A bitmap resource carrying the image itself rather than naming a file.

    A document that names a file is not self-contained: the JS converter cannot read it at
    all and refuses the document outright (F-030), and the landed doc.json is broken unless
    the texture is copied alongside it. base64 costs about a third more bytes in the JSON
    and nothing at all in the compiled .rc, which embeds the same image either way.
    """
    import base64
    data = (OUT / rel_path).read_bytes()
    return {"bitmaps": [{name: {"base64": base64.b64encode(data).decode("ascii")}}]}


def surface_ribbon(mesh_id, pts, half_w, radius):
    """A flat single-sided strip lying on a sphere, one quad per gap.

    This is how a route on a globe should be built. A tube made of solid boxes has to be
    hidden by the globe when it passes round the back, and that occlusion is not reliable
    here (F-027) - the far half drew across the visible face. A ribbon needs no occlusion:
    its one face points outward, so on the far side it is back-facing and the renderer
    culls it. Being invisible round the back is a property of the geometry rather than
    something the depth buffer has to get right.

    The winding below was established by experiment, not derived: with it, a near-side
    ribbon draws 2249 px and a far-side one draws exactly 0. The opposite winding culls
    both. Normals do not decide this - winding does (F-008).
    """
    verts, normals, uv, idx = [], [], [], []
    P = [tuple(c * radius for c in q) for q in pts]
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]
        out = [c / radius for c in a]
        t = [b[k] - a[k] for k in range(3)]
        tl = math.sqrt(sum(c * c for c in t)) or 1.0
        t = [c / tl for c in t]
        # in-surface perpendicular: outward x tangent
        sv = [out[1] * t[2] - out[2] * t[1],
              out[2] * t[0] - out[0] * t[2],
              out[0] * t[1] - out[1] * t[0]]
        sl = math.sqrt(sum(c * c for c in sv)) or 1.0
        sv = [c / sl * half_w for c in sv]
        quad = [[a[k] - sv[k] for k in range(3)], [a[k] + sv[k] for k in range(3)],
                [b[k] + sv[k] for k in range(3)], [b[k] - sv[k] for k in range(3)]]
        base = len(verts) // 3
        for pt in quad:
            verts += [round(pt[0], 5), round(pt[1], 5), round(pt[2], 5)]
            normals += [round(out[0], 5), round(out[1], 5), round(out[2], 5)]
            uv += [0.0, 0.0]
        idx += [base, base + 2, base + 1, base, base + 3, base + 2]
    return {"defineMesh3D": {"id": mesh_id, "verts": verts, "normals": normals,
                             "uv": uv, "indices": idx}}


def surface_patch(mesh_id, centre_unit, size, radius):
    """A small outward-facing square lying flat on a sphere - a map pin that obeys the same
    culling rule as a ribbon, so it disappears round the back instead of showing through."""
    o = centre_unit
    up = (0.0, 1.0, 0.0) if abs(o[1]) < 0.9 else (1.0, 0.0, 0.0)
    e1 = [o[1] * up[2] - o[2] * up[1], o[2] * up[0] - o[0] * up[2],
          o[0] * up[1] - o[1] * up[0]]
    l1 = math.sqrt(sum(c * c for c in e1)) or 1.0
    e1 = [c / l1 * size for c in e1]
    e2 = [o[1] * e1[2] - o[2] * e1[1], o[2] * e1[0] - o[0] * e1[2],
          o[0] * e1[1] - o[1] * e1[0]]
    l2 = math.sqrt(sum(c * c for c in e2)) or 1.0
    e2 = [c / l2 * size for c in e2]
    c0 = [o[k] * radius for k in range(3)]
    quad = [[c0[k] - e1[k] - e2[k] for k in range(3)],
            [c0[k] + e1[k] - e2[k] for k in range(3)],
            [c0[k] + e1[k] + e2[k] for k in range(3)],
            [c0[k] - e1[k] + e2[k] for k in range(3)]]
    verts, normals, uv = [], [], []
    for pt in quad:
        verts += [round(pt[0], 5), round(pt[1], 5), round(pt[2], 5)]
        normals += [round(o[0], 5), round(o[1], 5), round(o[2], 5)]
        uv += [0.0, 0.0]
    return {"defineMesh3D": {"id": mesh_id, "verts": verts, "normals": normals, "uv": uv,
                             "indices": [0, 2, 1, 0, 3, 2]}}


def uv_sphere(mesh_id, radius, nlat=24, nlon=48, centre=(0.0, 0.0, 0.0)):
    """A sphere carrying equirectangular UVs, for texture mapping.

    meshPrimitive3D makes a sphere but this corpus cannot assume it carries UVs, and a
    texture with nothing to map onto is one of the quieter ways to draw nothing (F-010).
    BOTH texture axes run opposite to the obvious reading, and the two failures look
    completely different (F-024):

      v  the player samples a bitmap with v = 0 at the BOTTOM row, so mapping v = 0 to the
         north pole turns the world upside down - Africa inverted, Antarctica over the
         Arctic. Obvious the moment the texture is a map.

      u  mapping u with increasing longitude mirrors the map east-west. That one is quiet:
         the globe still looks like a globe, and the only tell is that the texture appears
         to rotate OPPOSITE to the geometry drawn on it. Anything placed by latitude and
         longitude then sits on the wrong ocean.

    So this emits (1 - u, 1 - v), and anything positioned on the sphere must use latlon()
    below, which is built from the same convention.
    """
    verts, normals, uv, idx = [], [], [], []
    for i in range(nlat + 1):
        v = i / float(nlat)
        lat = (0.5 - v) * math.pi
        for j in range(nlon + 1):
            u = j / float(nlon)
            lon = (u - 0.5) * 2 * math.pi
            x = math.cos(lat) * math.sin(lon)
            y = math.sin(lat)
            z = math.cos(lat) * math.cos(lon)
            verts += [round(centre[0] + x * radius, 5),
                      round(centre[1] + y * radius, 5),
                      round(centre[2] + z * radius, 5)]
            normals += [round(x, 5), round(y, 5), round(z, 5)]
            # Plain u, and v flipped only because a bitmap's first row is its top while
            # v = 0 is the south pole. No mirror and no offset: once the sphere is wound
            # the right way out, the obvious mapping is the correct one.
            uv += [round(u, 5), round(1.0 - v, 5)]
    for i in range(nlat):
        for j in range(nlon):
            a = i * (nlon + 1) + j
            b = a + nlon + 1
            # The sphere was wound inside out. With this winding the player was showing
            # the INNER surface of the far hemisphere, which is mirrored and travels the
            # opposite way - which is why the UV needed a mirror to look right, why routes
            # placed by latitude and longitude never matched the map, and why the texture
            # appeared to counter-rotate (F-029 was a misdiagnosis of this). Flipped, the
            # map needs no correction at all.
            idx += [a, b, a + 1, a + 1, b, b + 1]
    return {"defineMesh3D": {"id": mesh_id, "verts": verts, "normals": normals,
                             "uv": uv, "indices": idx}}


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


# ── 1. PHY-QM-00025  Entanglement — static-diagram / compare / 2D ───────────
# Correlated against entangled, side by side. The distinction is the one everyone gets wrong:
# a pair of gloves in two boxes is already correlated and nothing spooky happens when you
# open one. The difference only shows up when you measure along a DIFFERENT axis, so both
# columns show three axes and only the right-hand one keeps agreeing.
def entanglement():
    W, H = 620, 440
    AXES = [("same axis", 0.0), ("45° apart", 45.0), ("90° apart", 90.0)]
    cmds = []
    for col, (name, note, colour, agree) in enumerate(
            (("Two gloves in two boxes", "correlated, and nothing more", WARM,
              (1.00, 0.50, 0.00)),
             ("An entangled pair", "correlated along every axis at once", GOOD,
              (1.00, 0.85, 0.00)))):
        cx = 170.0 + col * 290.0
        cmds += text_at(name, cx, 122.0, 13.0, colour, pan_x=0.0)
        cmds += text_at(note, cx, 140.0, 10.0, DIM, pan_x=0.0)
        for row, (axis_name, ang) in enumerate(AXES):
            y = 190.0 + row * 74.0
            cmds.append(paint({"color": PANEL}, {"style": "fill"}))
            cmds.append({"drawRect": {"left": cx - 128, "top": y - 26, "right": cx + 128,
                                      "bottom": y + 36}})
            # the two detectors, drawn at the angle being measured
            for side in (-1, 1):
                dx = cx + side * 86
                a = math.radians(-90.0 + (ang if side > 0 else 0.0))
                cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.4})) 
                cmds.append({"drawCircle": {"cx": dx, "cy": y, "radius": 17.0}})
                cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6},
                                  {"strokeCap": "round"}))
                cmds.append({"drawLine": {"x1": dx, "y1": y,
                                          "x2": dx + 15 * math.cos(a),
                                          "y2": y + 15 * math.sin(a)}})
            cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
            cmds.append({"drawLine": {"x1": cx - 62, "y1": y, "x2": cx + 62, "y2": y}})
            cmds += text_at(axis_name, cx, y + 4, 9.5, DIM, pan_x=0.0)
            # how often the two results agree, as a bar
            frac = agree[row]
            cmds.append(paint({"color": RULE}, {"style": "fill"}))
            cmds.append({"drawRect": {"left": cx - 110, "top": y + 18, "right": cx + 110,
                                      "bottom": y + 28}})
            cmds.append(paint({"color": colour}, {"style": "fill"}))
            cmds.append({"drawRect": {"left": cx - 110, "top": y + 18,
                                      "right": cx - 110 + 220 * frac, "bottom": y + 28}})
            cmds += text_at("%d%% agree" % int(frac * 100), cx + 114, y + 27, 9.0,
                            TEXT, pan_x=1.0)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": 310.0, "y1": 118.0, "x2": 310.0, "y2": 400.0}})
    cmds += text_at("Both columns agree perfectly on the first row, which is why "
                    "correlation alone proves nothing.", 36.0, 412.0, 10.5, TEXT)
    cmds += text_at("The gloves fall to chance as the axes separate. The entangled pair "
                    "does not, and no arrangement of", 36.0, 428.0, 10.0, DIM)
    title(cmds, W, H, "Correlated, or entangled?", "the difference is in the second row")
    return {"header": header(W, H, "A correlated pair and an entangled pair measured along "
                                   "three axes, showing where the two stop agreeing"),
            "root": canvas(cmds, INK)}


# ── 2. PHY-QM-00026  Spin — annotated-layout / demonstrate / 3D ────────────
# A spin state really is a direction in space, so the Bloch sphere is not a metaphor here.
# The 3D canvas fills the document and the cards sit over it (F-013); the labelled poles are
# what makes the picture readable rather than decorative.
def spin():
    W, H = 500, 640
    scene = [{"clearDepth3D": {}},
             {"camera3D": {"projection": "perspective", "fovY": 0.62,
                           "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                           "eye": [1.6, 0.95, 3.4], "center": [0.0, 0.0, 0.0],
                           "up": [0, 1, 0]}},
             {"lights3D": {"lights": [
                 {"type": "directional", "color": "#FFFFFFFF",
                  "dir": [-0.4, -0.5, -0.76], "intensity": 1.0},
                 {"type": "directional", "color": ACCENT,
                  "dir": [0.6, 0.3, 0.45], "intensity": 0.42}]}}]
    scene.append(var("prec", "continuousSec() * 0.8"))
    # the sphere, as a wireframe of rings so the arrow inside stays visible
    verts, normals, uv, idx = [], [], [], []
    for k in range(6):
        phi = k * math.pi / 6.0
        for seg in range(28):
            a0 = seg * 2 * math.pi / 28
            a1 = (seg + 1) * 2 * math.pi / 28
            Rs = 0.72
            p0 = (Rs * math.cos(a0) * math.cos(phi), Rs * math.sin(a0),
                  Rs * math.cos(a0) * math.sin(phi))
            p1 = (Rs * math.cos(a1) * math.cos(phi), Rs * math.sin(a1),
                  Rs * math.cos(a1) * math.sin(phi))
            mid = tuple((p0[i] + p1[i]) / 2 for i in range(3))
            axis = tuple(p1[i] - p0[i] for i in range(3))
            oriented_box(verts, normals, uv, idx,
                         (mid[0], mid[1], mid[2]), axis,
                         math.sqrt(sum(c * c for c in axis)) / 2, 0.011, 0.011)
    scene.append({"defineMesh3D": {"id": 1, "verts": [round(v, 5) for v in verts],
                                   "normals": normals, "uv": uv, "indices": idx}})
    scene += [{"matrix3D": {"op": "identity"}},
              paint({"color": RULE}, {"style": "fill"}),
              {"drawMesh3D": {"mesh": 1, "mode": "software-flat"}}]
    # the state vector, precessing about z
    v2, n2, u2, i2 = [], [], [], []
    oriented_box(v2, n2, u2, i2, (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), 0.36, 0.030, 0.030)
    scene.append({"defineMesh3D": {"id": 2, "verts": [round(v, 5) for v in v2],
                                   "normals": n2, "uv": u2, "indices": i2}})
    scene += [{"matrix3D": {"op": "identity"}},
              {"matrix3D": {"op": "rotate", "angle": "@prec", "axis": [0, 1, 0]}},
              {"matrix3D": {"op": "rotate", "angle": 0.72, "axis": [0, 0, 1]}},
              paint({"color": HOT}, {"style": "fill"}),
              {"drawMesh3D": {"mesh": 2, "mode": "software-smooth"}}]
    scene += text_at("|0>", 250.0, 118.0, 12.0, GOOD, pan_x=0.0)
    scene += text_at("|1>", 250.0, 418.0, 12.0, WARM, pan_x=0.0)
    scene += text_at("every point on this sphere is a state", 36.0, 430.0, 10.0, DIM)

    CARDS = [("Not a little magnet", "spin is an intrinsic angular momentum with no "
              "spinning object underneath it", ACCENT),
             ("Only two outcomes", "measure along any axis and you get up or down - never "
              "a value in between", GOOD),
             ("The angle sets the odds", "a state halfway between the poles gives each "
              "answer half the time", WARM)]
    kids = [{"type": "spacer", "modifiers": [{"height": 446}]}]
    for name, note, colour in CARDS:
        kids.append({"type": "row",
                     "modifiers": [{"width": 452}, {"padding": 8}, {"background": PANEL}],
                     "children": [
                         {"type": "box", "modifiers": [{"width": 4}, {"height": 32},
                                                       {"background": colour}],
                          "children": []},
                         {"type": "spacer", "modifiers": [{"width": 9}]},
                         {"type": "column", "modifiers": [{"width": 418}], "children": [
                             {"type": "text", "value": name, "modifiers": [],
                              "fontSize": 11.5, "color": colour},
                             {"type": "text", "value": note, "modifiers": [],
                              "fontSize": 9.0, "color": DIM}]}]})
        kids.append({"type": "spacer", "modifiers": [{"height": 6}]})
    return {"header": header(W, H, "A precessing spin state on the Bloch sphere, with what "
                                   "the picture does and does not claim"),
            "root": {"type": "box", "modifiers": ["fillMaxSize", {"background": INK}],
                     "children": [
                         {"type": "canvas", "modifiers": ["fillMaxSize"],
                          "commands": title(scene, W, H, "Spin",
                                            "a direction, and only two answers")},
                         {"type": "column",
                          "modifiers": ["fillMaxSize", {"padding": 16}],
                          "children": kids}]}}


# ── 3. BIO-GENE-00023  Population genetics — data-plot / simulate / 2D ─────
# Drift in four populations of different size, all starting at the same allele frequency.
# The small ones fix or vanish within a few dozen generations and the large one wanders
# gently - which is the whole argument for why rare populations lose variation.
def popgen():
    W, H = 600, 470
    SIZES = [(25, HOT, "N = 25"), (100, WARM, "N = 100"),
             (500, ACCENT, "N = 500"), (2000, GOOD, "N = 2000")]
    G = 60
    px0, px1, py0, py1 = 70.0, 540.0, 130.0, 350.0
    cmds = [paint({"color": PANEL}, {"style": "fill"}),
            {"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}}]
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 0.8}))
    for f in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = py1 - f * (py1 - py0)
        cmds.append({"drawLine": {"x1": px0, "y1": y, "x2": px1, "y2": y}})
        cmds += text_at("%.2f" % f, px0 - 6, y + 4, 9.0, DIM, pan_x=1.0)
    # A fixed pseudo-random walk, computed here. Generators in this corpus must be
    # deterministic - the compiled bytes are stored, so a clock or an unseeded random
    # would make every rebuild a false diff.
    seed = 20260308
    def nxt():
        nonlocal seed
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        return seed / float(0x7FFFFFFF)
    for n, colour, label in SIZES:
        p = 0.5
        pts = []
        for g in range(G):
            # binomial sampling, approximated by its normal limit - enough to show drift
            sd = math.sqrt(max(1e-9, p * (1 - p) / n))
            p = max(0.0, min(1.0, p + (nxt() - 0.5) * 2.0 * sd * 1.74))
            pts.append(p)
            if p <= 0.0 or p >= 1.0:
                break
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.2},
                          {"strokeCap": "round"}))
        prev = None
        for i, v in enumerate(pts):
            pt = (px0 + (px1 - px0) * i / (G - 1.0), py1 - v * (py1 - py0))
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1],
                                          "x2": pt[0], "y2": pt[1]}})
            prev = pt
        # mark where a small population lost the allele entirely
        if pts[-1] <= 0.0 or pts[-1] >= 1.0:
            cmds.append(paint({"color": colour}, {"style": "fill"}))
            cmds.append({"drawCircle": {"cx": prev[0], "cy": prev[1], "radius": 4.5}})
            cmds += text_at("fixed at generation %d" % len(pts), prev[0] + 8,
                            prev[1] + 4, 9.0, colour)
        cmds += text_at(label, px1 + 8, py1 - pts[-1] * (py1 - py0) + 4, 10.0, colour)
    cmds += text_at("allele frequency", px0, py0 - 12, 10.5, DIM)
    cmds += text_at("generations", (px0 + px1) / 2, py1 + 24, 10.0, DIM, pan_x=0.0)
    cmds += text_at("every line started at exactly one half, and nothing here is selection",
                    70.0, 392.0, 11.0, TEXT)
    cmds += text_at("- the small populations lost an allele purely by sampling, which is "
                    "why a bottleneck is permanent", 70.0, 412.0, 10.5, DIM)
    cmds += text_at("even after the numbers recover", 70.0, 430.0, 10.5, DIM)
    title(cmds, W, H, "Genetic drift", "four population sizes, no selection at all")
    return {"header": header(W, H, "Allele frequency drifting in four populations of "
                                   "different size, with no selection acting"),
            "root": canvas(cmds, INK)}


# ── 4. MTH-ALGE-00008  Transformations — path-form / analyze / 2D ──────────
# One shape under four matrices, each drawn over a ghost of the original. The determinant is
# printed because it is the thing the picture is evidence for: it is the area ratio, and a
# negative one means the shape was flipped.
def transformations():
    W, H = 620, 470
    SHAPE = [(0.0, 0.0), (1.0, 0.0), (1.0, 0.6), (0.45, 0.6), (0.45, 1.0), (0.0, 1.0)]
    MATS = [("Identity", (1, 0, 0, 1), "nothing moves", DIM),
            ("Scale 1.4, 0.7", (1.4, 0, 0, 0.7), "area x 0.98 - almost unchanged", ACCENT),
            ("Rotate 35°", (0.819, -0.574, 0.574, 0.819), "area x 1.00 - rotation "
             "preserves it", GOOD),
            ("Shear + flip", (1, 0.8, 0, -1), "area x -1.00 - the sign is the flip", HOT)]
    cmds = []
    pw = 140.0
    for i, (name, m, note, colour) in enumerate(MATS):
        ox = 54.0 + i * (pw + 10.0)
        oy = 300.0
        S = 62.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": ox - 12, "top": 150.0, "right": ox + pw - 22,
                                  "bottom": 330.0}})
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 0.8}))
        cmds.append({"drawLine": {"x1": ox - 12, "y1": oy, "x2": ox + pw - 22, "y2": oy}})
        cmds.append({"drawLine": {"x1": ox + 30, "y1": 150.0, "x2": ox + 30, "y2": 330.0}})
        # the ghost of the original, under every panel
        gid = "g%d" % i
        cmds.append({"pathCreate": {"id": gid, "x": ox + 30 + SHAPE[0][0] * S,
                                    "y": oy - SHAPE[0][1] * S}})
        for (sx, sy) in SHAPE[1:]:
            cmds.append({"pathAppendLineTo": {"path": gid, "x": ox + 30 + sx * S,
                                              "y": oy - sy * S}})
        cmds.append({"pathAppendClose": {"path": gid}})
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawPath": {"path": gid}})
        # the transformed shape
        tid = "t%d" % i
        a, b, c, d = m
        def xf(p):
            return (ox + 30 + (a * p[0] + b * p[1]) * S, oy - (c * p[0] + d * p[1]) * S)
        p0 = xf(SHAPE[0])
        cmds.append({"pathCreate": {"id": tid, "x": p0[0], "y": p0[1]}})
        for p in SHAPE[1:]:
            q = xf(p)
            cmds.append({"pathAppendLineTo": {"path": tid, "x": q[0], "y": q[1]}})
        cmds.append({"pathAppendClose": {"path": tid}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawPath": {"path": tid}})
        cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.2}))
        cmds.append({"drawPath": {"path": tid}})
        det = a * d - b * c
        cmds += text_at(name, ox - 12, 142.0, 11.0, colour)
        cmds += text_at("det = %+.2f" % det, ox - 12, 352.0, 11.5, TEXT)
        cmds += text_at(note, ox - 12, 368.0, 8.5, DIM)
    cmds += text_at("the grey outline is the same shape in every panel", 54.0, 404.0,
                    11.0, TEXT)
    cmds += text_at("the determinant is the area ratio, and its sign says whether the "
                    "shape was turned over", 54.0, 424.0, 10.5, DIM)
    title(cmds, W, H, "Four matrices", "what the determinant is actually telling you")
    return {"header": header(W, H, "One polygon under four linear transformations, each "
                                   "over a ghost of the original, with determinants"),
            "root": canvas(cmds, INK)}


# ── 5. CSC-DS-00008  Trees — expression-animation / explain / 2D ───────────
# A search descending a binary tree, one level per beat. The counter beside it is the point:
# a thousand nodes takes ten steps, and the animation is slow enough that the halving is
# something you watch rather than something you are told.
def trees():
    W, H = 600, 470
    DEPTH = 4
    cmds = [var("beat", "continuousSec() * 0.55 - floor(continuousSec() * 0.55 / 5.0) * 5.0"),
            var("lvl", "clamp(0.0, 4.0, floor(@beat))")]
    PATH = [0, 1, 0, 1]          # the branch the search happens to take
    top, vgap = 150.0, 62.0
    def node_x(level, index):
        span = W - 140.0
        n = 2 ** level
        return 70.0 + span * (index + 0.5) / n
    # edges first, so nodes sit over them
    for level in range(DEPTH):
        for i in range(2 ** level):
            for child in (0, 1):
                cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.2}))
                cmds.append({"drawLine": {
                    "x1": node_x(level, i), "y1": top + level * vgap,
                    "x2": node_x(level + 1, i * 2 + child),
                    "y2": top + (level + 1) * vgap}})
    # the branch the search takes, drawn over the edges in the accent colour
    idx_path = [0]
    for step, d in enumerate(PATH):
        idx_path.append(idx_path[-1] * 2 + d)
    for level in range(DEPTH):
        cmds.append({"conditionalOperations": {
            "condition": "gt", "v1": "@lvl", "v2": float(level),
            "commands": [
                paint({"color": ACCENT}, {"style": "stroke"}, {"width": 3.0},
                      {"strokeCap": "round"}),
                {"drawLine": {"x1": node_x(level, idx_path[level]),
                              "y1": top + level * vgap,
                              "x2": node_x(level + 1, idx_path[level + 1]),
                              "y2": top + (level + 1) * vgap}}]}})
    for level in range(DEPTH + 1):
        for i in range(2 ** level):
            x, y = node_x(level, i), top + level * vgap
            on_path = (i == idx_path[level])
            cmds.append(paint({"color": PANEL}, {"style": "fill"}))
            cmds.append({"drawCircle": {"cx": x, "cy": y, "radius": 13.0}})
            cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
            cmds.append({"drawCircle": {"cx": x, "cy": y, "radius": 13.0}})
            if on_path:
                cmds.append({"conditionalOperations": {
                    "condition": "ge", "v1": "@lvl", "v2": float(level),
                    "commands": [paint({"color": ACCENT}, {"style": "fill"}),
                                 {"drawCircle": {"cx": x, "cy": y, "radius": 11.0}}]}})
        cmds += text_at("%d" % (2 ** level), 44.0, top + level * vgap + 4, 9.5,
                        DIM, pan_x=1.0)
    cmds += text_at("nodes", 44.0, top - 20, 9.5, DIM, pan_x=1.0)
    # the discarded half, named at each level
    for level in range(DEPTH):
        cmds.append({"conditionalOperations": {
            "condition": "gt", "v1": "@lvl", "v2": float(level),
            "commands": [paint({"color": DIM}, {"style": "fill"}, {"textSize": 9.0}),
                         {"drawTextAnchored": {
                             "text": "half of what was left, gone",
                             "x": 560.0, "y": top + (level + 1) * vgap + 4,
                             "panX": 1.0, "panY": 0.0, "flags": 0}}]}})
    cmds += text_at("sixteen leaves, four decisions", 70.0, 424.0, 11.0, TEXT)
    cmds += text_at("- a million would take twenty, which is the only reason this "
                    "structure is worth the pointers", 70.0, 444.0, 10.5, DIM)
    title(cmds, W, H, "Searching a tree", "one level per beat")
    return {"header": header(W, H, "A search descending a binary tree one level at a time, "
                                   "halving what remains at each step"),
            "root": canvas(cmds, INK)}


# ── 6. CHM-MS-00008  Polarity — particle-system / explore / 2D ─────────────
# Water molecules lining up against an oil that does not. Particles because the behaviour is
# statistical: no single molecule "decides" anything, and the alignment is what a crowd of
# dipoles does in a field.
def polarity():
    W, H = 560, 520
    cmds = []
    for col, (name, note, aligns, colour) in enumerate(
            (("Water", "a bent molecule with a permanent dipole", True, ACCENT),
             ("Oil", "symmetrical, so the pulls cancel", False, WARM))):
        x0 = 44.0 + col * 248.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": 150.0, "right": x0 + 224,
                                  "bottom": 370.0}})
        cmds += text_at(name, x0 + 112, 142.0, 13.0, colour, pan_x=0.0)
        cmds += text_at(note, x0 + 112, 388.0, 9.5, DIM, pan_x=0.0)
        cmds.append({"createParticles": {
            "id": "mol%d" % col, "count": 44,
            "variables": ["mx", "my", "ang", "sp"],
            "initialValues": ["%.1f + rand() * 200.0" % (x0 + 12),
                              "162 + rand() * 196",
                              "rand() * 6.28",
                              "0.3 + rand() * 0.9"]}})
        # Aligned molecules settle toward a common angle; unaligned ones keep tumbling.
        # Both are one short expression per field - the budget is 32 RPN tokens (F-022).
        turn = "ang * 0.86" if aligns else "ang + sp * 0.04"
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.2},
                          {"strokeCap": "round"}))
        cmds.append({"particlesLoop": {
            "system": "@mol%d" % col,
            "equations": ["mx", "my", turn, "sp"],
            "commands": [
                {"drawLine": {"x1": "@mx - cos(@ang) * 7.0",
                              "y1": "@my - sin(@ang) * 7.0",
                              "x2": "@mx + cos(@ang) * 7.0",
                              "y2": "@my + sin(@ang) * 7.0"}}]}})
        # the field they are sitting in, drawn once per column
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        for k in range(5):
            yy = 170.0 + k * 48.0
            cmds.append({"drawLine": {"x1": x0 + 6, "y1": yy, "x2": x0 + 218, "y2": yy}})
        cmds += text_at("+", x0 + 112, 164.0, 13.0, GOOD, pan_x=0.0)
        cmds += text_at("−", x0 + 112, 368.0, 13.0, HOT, pan_x=0.0)
    cmds += text_at("the field is identical on both sides", 44.0, 428.0, 11.0, TEXT)
    cmds += text_at("- water turns to face it and oil does not, which is the whole of why "
                    "the two will not mix,", 44.0, 448.0, 10.5, DIM)
    cmds += text_at("and why soap, which has one end of each kind, works at all",
                    44.0, 466.0, 10.5, DIM)
    title(cmds, W, H, "Polar and not", "the same field, two responses")
    return {"header": header(W, H, "Polar molecules aligning in a field beside non-polar "
                                   "ones that keep tumbling"),
            "root": canvas(cmds, INK)}


# ── 7. EAR-GEOP-00008  Seismic waves — interactive / compare / 3D ──────────
# Drag to send a wavefront through the Earth. P and S waves differ in one decisive way: S
# waves cannot cross a liquid, so the outer core casts a shadow. That shadow is the reason
# anyone knows the core is liquid, and it is a 3D fact about rays through a sphere.
def seismic():
    W, H = 520, 640
    # The Earth has to be a CAGE, not a solid sphere. The first version drew an opaque globe,
    # which hid the core and every ray inside it - the one thing this document exists to
    # show. Rings let the interior be seen, and the core stays solid because it is the thing
    # casting the shadow.
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.68,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [1.0, 0.8, 5.6], "center": [0.0, 0.46, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.4, -0.5, -0.76], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.3, 0.45], "intensity": 0.45}]}}]
    cmds.append({"touchExpression": {"name": "drag", "defaultValue": 300.0,
                                     "min": 40.0, "max": 480.0,
                                     "expression": "touchX()"}})
    cmds.append(var("t", "clamp(0.0, 1.0, (@drag - 40.0) / 440.0)"))
    CY, R, RC = 0.46, 1.0, 0.545

    # the Earth, as rings
    verts, normals, uv, idx = [], [], [], []
    for k in range(5):
        phi = k * math.pi / 5.0
        for seg in range(30):
            a0, a1 = seg * 2 * math.pi / 30, (seg + 1) * 2 * math.pi / 30
            p0 = (R * math.cos(a0) * math.cos(phi), R * math.sin(a0),
                  R * math.cos(a0) * math.sin(phi))
            p1 = (R * math.cos(a1) * math.cos(phi), R * math.sin(a1),
                  R * math.cos(a1) * math.sin(phi))
            mid = tuple((p0[i] + p1[i]) / 2 for i in range(3))
            ax = tuple(p1[i] - p0[i] for i in range(3))
            oriented_box(verts, normals, uv, idx, (mid[0], mid[1] + CY, mid[2]), ax,
                         math.sqrt(sum(c * c for c in ax)) / 2, 0.009, 0.009)
    cmds.append({"defineMesh3D": {"id": 1, "verts": [round(v, 5) for v in verts],
                                  "normals": normals, "uv": uv, "indices": idx}})
    cmds += [{"matrix3D": {"op": "identity"}},
             paint({"color": RULE}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-flat"}}]
    # the liquid outer core, solid, because it is the obstacle
    cmds.append({"meshPrimitive3D": {"id": 2, "primitive": "sphere", "segments": 24,
                                     "radius": RC, "center": [0, 0, 0]}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "translate", "x": 0.0, "y": CY, "z": 0.0}},
             paint({"color": WARM}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 2, "mode": "software-smooth"}}]

    # Rays from a quake at the north pole. Each is a straight chord; a ray whose closest
    # approach to the centre is inside the core is an S ray that dies there, and the angles
    # where that happens are the shadow zone.
    cmds.append({"meshPrimitive3D": {"id": 3, "primitive": "sphere", "segments": 8,
                                     "radius": 0.048, "center": [0, 0, 0]}})
    SRC = (0.0, R, 0.0)
    blocked_count = 0
    # Both sides, so the shadow zone is symmetric about the quake the way it really is.
    for k in range(26):
        side = 1.0 if k < 13 else -1.0
        ang = math.radians(16.0 + (k % 13) * 12.0)
        dst = (side * R * math.sin(ang), R * math.cos(ang), 0.0)
        # distance from the sphere's centre to the chord
        dx, dy = dst[0] - SRC[0], dst[1] - SRC[1]
        L = math.hypot(dx, dy)
        perp = abs(SRC[0] * dy - SRC[1] * dx) / L
        blocked = perp < RC
        if blocked and side > 0:
            blocked_count += 1
        colour = HOT if blocked else GOOD
        # an S ray stops at the core; a P ray runs the whole chord
        frac = 1.0
        if blocked:
            half = math.sqrt(max(0.0, RC * RC - perp * perp))
            t_entry = (math.sqrt(max(0.0, R * R - perp * perp)) - half) / L
            frac = max(0.08, t_entry)
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "translate",
                               "x": "%.4f * @t" % (dx * frac),
                               "y": "%.4f + %.4f * @t" % (SRC[1] + CY, dy * frac),
                               "z": 0.0}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": 3, "mode": "software-smooth"}}]
    cmds += text_at("quake", 262.0, 84.0, 11.0, TEXT, pan_x=0.0)
    cmds += text_at("liquid outer core", 452.0, 258.0, 9.5, WARM, pan_x=1.0)
    cmds += text_at("%d of every 13 rays on each side never arrive" % blocked_count,
                    36.0, 414.0, 10.0, HOT)

    for i, (name, speed, crosses, colour, note) in enumerate(
            (("P wave", "6 to 13 km/s", "crosses anything", GOOD,
              "a push-pull along the ray - gases, liquids and solids all carry it"),
             ("S wave", "3.5 to 7.2 km/s", "solids only", HOT,
              "a sideways shear, and a liquid has nothing to shear against"))):
        y = 442.0 + i * 64.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 36.0, "top": y - 18, "right": 484.0,
                                  "bottom": y + 36}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 36.0, "top": y - 18, "right": 41.0,
                                  "bottom": y + 36}})
        cmds += text_at(name, 52.0, y, 12.5, colour)
        cmds += text_at(speed, 300.0, y, 10.5, TEXT, pan_x=1.0)
        cmds += text_at(crosses, 476.0, y, 10.5, TEXT, pan_x=1.0)
        cmds += text_at(note, 52.0, y + 17, 9.0, DIM)
    cmds.append({"conditionalOperations": {
        "condition": "gt", "v1": "@t", "v2": 0.72,
        "commands": [paint({"color": HOT}, {"style": "fill"}, {"textSize": 10.0}),
                     {"drawTextAnchored": {
                         "text": "the red rays stopped where the core begins",
                         "x": 300.0, "y": 414.0, "panX": -1.0, "panY": 0.0, "flags": 0}}]}})
    cmds += text_at("drag to send the wavefront out", 36.0, 586.0, 10.0, DIM)
    cmds += text_at("Nobody has been below 12 km. The shadow is how the core was found,",
                    36.0, 608.0, 10.0, TEXT)
    cmds += text_at("by Richard Oldham in 1906 and Inge Lehmann in 1936.",
                    36.0, 624.0, 10.0, DIM)
    title(cmds, W, H, "P and S", "drag to release a quake")
    return {"header": header(W, H, "Drag to send P and S rays through a wireframe Earth, "
                                   "with the S rays dying at the liquid outer core"),
            "root": canvas(cmds, INK)}


# ── 8. ENG-EE-00008  Transistors — raster-and-text / demonstrate / 2D ──────
# The transfer curve with the three regions marked, because the single most useful fact
# about a transistor is that the same device is a switch or an amplifier depending only on
# where you sit on this curve.
def transistors():
    W, H = 600, 460
    px0, px1, py0, py1 = 70.0, 540.0, 130.0, 340.0
    cmds = [paint({"color": PANEL}, {"style": "fill"}),
            {"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}}]
    REGIONS = [(0.00, 0.30, "Cut-off", "off. A switch, open.", RULE),
               (0.30, 0.66, "Active", "a small change in, a large change out. "
                "An amplifier.", GOOD),
               (0.66, 1.00, "Saturation", "fully on. A switch, closed.", ACCENT)]
    for u0, u1, name, note, colour in REGIONS:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": px0 + (px1 - px0) * u0, "top": py0,
                                  "right": px0 + (px1 - px0) * u1, "bottom": py0 + 6}})
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 0.8}))
    for f in (0.25, 0.5, 0.75):
        y = py1 - f * (py1 - py0)
        cmds.append({"drawLine": {"x1": px0, "y1": y, "x2": px1, "y2": y}})
    # the curve itself
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 2.8},
                      {"strokeCap": "round"}))
    prev = None
    for i in range(61):
        u = i / 60.0
        out = 1.0 / (1.0 + math.exp(-(u - 0.48) * 13.0))
        pt = (px0 + (px1 - px0) * u, py1 - out * (py1 - py0) * 0.94)
        if prev:
            cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": pt[0], "y2": pt[1]}})
        prev = pt
    for u0, u1, name, note, colour in REGIONS:
        xm = px0 + (px1 - px0) * (u0 + u1) / 2
        cmds += text_at(name, xm, py0 - 12, 11.0, colour, pan_x=0.0)
    # the steep part, where a tiny input swing becomes a large output swing
    cmds.append(paint({"color": GOOD}, {"style": "stroke"}, {"width": 1.2}))
    ux = px0 + (px1 - px0) * 0.48
    cmds.append({"drawLine": {"x1": ux - 16, "y1": py1 - 0.5 * (py1 - py0) * 0.94,
                              "x2": ux + 16, "y2": py1 - 0.5 * (py1 - py0) * 0.94}})
    cmds += text_at("base voltage", (px0 + px1) / 2, py1 + 24, 10.0, DIM, pan_x=0.0)
    cmds += text_at("collector current", px0, py0 - 30, 10.5, DIM)
    cmds += [{"variable": {"name": "gain", "commit": True,
                           "value": {"type": "textFromFloat", "value": "3.25",
                                     "whole": 1, "decimal": 2}}},
             paint({"color": GOOD}, {"style": "fill"}, {"textSize": 11.0}),
             {"drawTextAnchored": {"text": "@gain", "x": 70.0, "y": 382.0,
                                   "panX": -1.0, "panY": 0.0, "flags": 0}}]
    cmds += text_at("volts out per volt in, at the steepest point", 104.0, 382.0, 10.5, TEXT)
    for i, (name, note, colour) in enumerate(
            [(r[2], r[3], r[4]) for r in REGIONS]):
        cmds += text_at(name, 70.0, 406.0 + i * 16.0, 10.0, colour)
        cmds += text_at(note, 164.0, 406.0 + i * 16.0, 10.0, DIM)
    title(cmds, W, H, "One device, three regions",
          "a switch at the ends, an amplifier in the middle")
    return {"header": header(W, H, "A transistor transfer curve with its cut-off, active "
                                   "and saturation regions marked"),
            "root": canvas(cmds, INK)}


# ── 9. ECO-IE-00012  Trade — static-diagram / demonstrate / 3D ─────────────
# Trade flows as arcs over a globe. The 3D is load-bearing: a flat map cuts the Pacific and
# makes the largest trade corridor on Earth look like two unrelated edges.
def trade():
    W, H = 540, 620
    # One full turn every 16 seconds: 2*pi/16 = 0.3927 rad/s. Positive turns the globe
    # eastward, so a place on the equator crosses the disc from left to right the way the
    # real Earth does.
    cmds = [var("spin", "continuousSec() * 0.3927"),
            {"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.68,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [1.5, 1.0, 5.4],
                          "center": [0.0, 0.62, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.3, -0.35, -0.89], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.3, 0.45], "intensity": 0.42}]}}]
    # The corridors are ribbons lying on the surface, built below and drawn before the
    # globe; the globe is 20x40 because the texture carries the detail.
    def latlon(lat, lon):
        """Matches uv_sphere's convention exactly - a different one puts Tokyo in the
        Atlantic, and on a textured globe that is immediately obvious."""
        la, lo = math.radians(lat), math.radians(lon)
        return (math.cos(la) * math.sin(lo), math.sin(la), math.cos(la) * math.cos(lo))
    # Pacific routes, because the document argues about the Pacific.
    #
    # Every pair must be WELL SHORT of antipodal. A great circle of 160-170 degrees wraps so
    # far round the globe that a large part of it is on the near side at any rotation, and it
    # reads as a line drawn straight through the planet. Brazil-China (161 deg) was dropped
    # for exactly this, and I replaced it with Chile-China, which is 168 - worse, and the
    # same mistake twice. Hence the assertion below rather than another careful choice.
    ROUTES = [((35, 139), (37, -122), "Japan - California", GOOD),
              ((31, 121), (33, -118), "Shanghai - Los Angeles", ACCENT),
              ((-33, 151), (31, 121), "Australia - China", WARM),
              ((-33, -71), (34, -118), "Chile - California", HOT)]

    for (p0, p1, nm, _c) in ROUTES:
        la1, lo1 = math.radians(p0[0]), math.radians(p0[1])
        la2, lo2 = math.radians(p1[0]), math.radians(p1[1])
        cosw = (math.sin(la1) * math.sin(la2)
                + math.cos(la1) * math.cos(la2) * math.cos(lo2 - lo1))
        deg = math.degrees(math.acos(max(-1.0, min(1.0, cosw))))
        assert deg < 110.0, ("%s spans %.0f degrees of arc; over about 110 it stops "
                             "reading as a route on a globe" % (nm, deg))
    for ri, (a, b, name, colour) in enumerate(ROUTES):
        p, q = latlon(*a), latlon(*b)          # unit vectors
        SEG = 24
        # Spherical interpolation, not lerp-then-normalise: for a near-antipodal pair the
        # midpoint of a straight chord sits close to the centre, and normalising it sends
        # the path somewhere arbitrary.
        dot = max(-1.0, min(1.0, sum(p[k] * q[k] for k in range(3))))
        omega = math.acos(dot)
        so = math.sin(omega) or 1e-6
        path = []
        for i in range(SEG + 1):
            u = i / float(SEG)
            w0 = math.sin((1.0 - u) * omega) / so
            w1 = math.sin(u * omega) / so
            m = tuple(p[k] * w0 + q[k] * w1 for k in range(3))
            ln = math.sqrt(sum(c * c for c in m)) or 1.0
            path.append(tuple(m[k] / ln for k in range(3)))
        # 0.7825 against a globe of 0.780: close enough to lie on the surface, far enough
        # not to z-fight with it. A ribbon has no thickness, so unlike the old tube it does
        # not straddle the surface and cannot poke through from inside.
        cmds.append(surface_ribbon(10 + ri, path, 0.018, 0.7825))
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 {"matrix3D": {"op": "translate", "x": 0.0, "y": 0.52, "z": 0.0}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": 10 + ri, "mode": "software-flat"}}]
    # The globe is drawn after the routes. With ribbons this no longer matters for
    # correctness - the far side is culled rather than covered - but it keeps the near-side
    # ribbons from being dimmed by the globe's own shading.
    # Textured. The route-to-map alignment is still not exact (F-028) - CAL-GLOBE-00001 is
    # the instrument for fixing that, and whatever it settles on should be copied back here.
    cmds.append(uv_sphere(1, 0.78, nlat=20, nlon=40))
    cmds.append({"texture3D": {"bitmap": "@earth"}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             {"matrix3D": {"op": "translate", "x": 0.0, "y": 0.52, "z": 0.0}},
             paint({"color": "#FFFFFFFF"}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]
    cmds.append({"texture3D": {"bitmap": 0}})

    y = 452.0
    for a, b, name, colour in ROUTES:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 40.0, "top": y - 9, "right": 54.0,
                                  "bottom": y + 3}})
        cmds += text_at(name, 64.0, y, 11.0, colour)
        y += 24.0
    cmds += text_at("a flat map cuts the Pacific down the middle", 40.0, 578.0, 10.5, TEXT)
    cmds += text_at("- which makes the busiest corridor on Earth look like two separate "
                    "lines leaving the page", 40.0, 596.0, 10.0, DIM)
    cmds += text_at("NASA Blue Marble, public domain", 40.0, 556.0, 8.5, DIM)
    title(cmds, W, H, "Four trade corridors", "drawn on a sphere, because they are")
    return {"header": header(W, H, "Four major trade corridors as arcs over a slowly "
                                   "turning globe"),
            "resources": embedded_bitmap("earth", "textures/earth.png"),
            "root": canvas(cmds, INK)}


# ── 10. ECO-IE-00013  Tariffs — annotated-layout / simulate / 2D ───────────
# Who actually pays. The four boxes add up, which is the thing a tariff argument usually
# skips: the revenue is real, and it is smaller than the sum of what the two sides lose.
def tariffs():
    W, H = 500, 620
    PARTS = [("Consumers pay more", "-100", "the whole price rise lands here first", HOT),
             ("Domestic producers gain", "+42", "they can now charge the higher price too",
              GOOD),
             ("Government collects", "+31", "the tariff itself, on what still comes in",
              ACCENT),
             ("Lost outright", "-27", "trades that simply stop happening. Nobody gets this.",
              WARM)]
    kids = [{"type": "text", "value": "Who pays a tariff", "modifiers": [],
             "fontSize": 19.0, "color": TEXT},
            {"type": "spacer", "modifiers": [{"height": 3}]},
            {"type": "text",
             "value": "a 20% duty on an imported good, as four separate effects",
             "modifiers": [], "fontSize": 11.0, "color": DIM},
            {"type": "spacer", "modifiers": [{"height": 16}]}]
    for name, amount, note, colour in PARTS:
        mag = abs(int(amount))
        kids.append({"type": "column",
                     "modifiers": [{"width": 456}, {"padding": 11}, {"background": PANEL}],
                     "children": [
                         {"type": "row", "modifiers": [{"width": 434}], "children": [
                             {"type": "text", "value": name, "modifiers": [],
                              "fontSize": 13.0, "color": colour},
                             {"type": "spacer", "modifiers": [{"width": 1}]},
                             {"type": "text", "value": amount, "modifiers": [],
                              "fontSize": 14.0, "color": TEXT}]},
                         {"type": "spacer", "modifiers": [{"height": 6}]},
                         {"type": "box", "modifiers": [{"width": 434}, {"height": 8},
                                                       {"background": RULE}],
                          "children": [
                              {"type": "box",
                               "modifiers": [{"width": int(434 * mag / 100.0)},
                                             {"height": 8}, {"background": colour}],
                               "children": []}]},
                         {"type": "spacer", "modifiers": [{"height": 6}]},
                         {"type": "text", "value": note, "modifiers": [],
                          "fontSize": 9.5, "color": DIM}]})
        kids.append({"type": "spacer", "modifiers": [{"height": 9}]})
    kids += [{"type": "box", "modifiers": [{"width": 456}, {"height": 1},
                                           {"background": RULE}], "children": []},
             {"type": "spacer", "modifiers": [{"height": 10}]},
             {"type": "row", "modifiers": [{"width": 456}], "children": [
                 {"type": "text", "value": "Net, for the country imposing it", "modifiers": [],
                  "fontSize": 12.5, "color": TEXT},
                 {"type": "spacer", "modifiers": [{"width": 1}]},
                 {"type": "text", "value": "-54", "modifiers": [],
                  "fontSize": 15.0, "color": HOT}]},
             {"type": "spacer", "modifiers": [{"height": 10}]},
             {"type": "text",
              "value": "The gains are concentrated on a few producers who notice them, and "
                       "the losses are spread across every buyer, who mostly do not. That "
                       "asymmetry is political, not economic.",
              "modifiers": [], "fontSize": 10.0, "color": DIM}]
    return {"header": header(W, H, "The four effects of a tariff as stacked bars on one "
                                   "scale, with the net result"),
            "root": {"type": "column",
                     "modifiers": ["fillMaxSize", {"padding": 18}, {"background": INK}],
                     "children": kids}}


# ── 11. ECO-IE-00014  Currency flows — data-plot / analyze / 2D ────────────
# A currency's value against the two flows that move it. The crossing is the content: trade
# surplus and capital flight pull in opposite directions, and which one wins is visible as
# the gap between the shaded bands.
def currency_flows():
    W, H = 600, 470
    N = 36
    trade, capital, rate = [], [], []
    v = 1.0
    for i in range(N):
        u = i / (N - 1.0)
        t = 0.55 + 0.35 * math.sin(u * 5.2) + 0.10 * math.sin(u * 13.0)
        c = 0.50 + 0.42 * math.sin(u * 4.1 + 2.2)
        trade.append(t); capital.append(c)
        v += (t - c) * 0.045
        rate.append(v)
    px0, px1, py0, py1 = 70.0, 540.0, 130.0, 290.0
    qy0, qy1 = 310.0, 390.0
    cmds = [paint({"color": PANEL}, {"style": "fill"}),
            {"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}},
            paint({"color": PANEL}, {"style": "fill"}),
            {"drawRect": {"left": px0, "top": qy0, "right": px1, "bottom": qy1}}]
    for series, colour, name in ((trade, GOOD, "exports earning foreign currency"),
                                 (capital, HOT, "capital leaving for better returns")):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.4},
                          {"strokeCap": "round"}))
        prev = None
        for i, s in enumerate(series):
            pt = (px0 + (px1 - px0) * i / (N - 1.0), py1 - s * (py1 - py0) * 0.92)
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1],
                                          "x2": pt[0], "y2": pt[1]}})
            prev = pt
        cmds += text_at(name, px0 + 8, py0 + (16 if colour == GOOD else 32), 9.5, colour)
    # where the two cross, which is where the rate turns
    for i in range(1, N):
        if (trade[i-1] - capital[i-1]) * (trade[i] - capital[i]) < 0:
            x = px0 + (px1 - px0) * i / (N - 1.0)
            cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 1.0}))
            cmds.append({"drawLine": {"x1": x, "y1": py0, "x2": x, "y2": qy1}})
    cmds.append(paint({"color": ACCENT}, {"style": "stroke"}, {"width": 2.6},
                      {"strokeCap": "round"}))
    lo, hi = min(rate), max(rate)
    prev = None
    for i, r in enumerate(rate):
        pt = (px0 + (px1 - px0) * i / (N - 1.0),
              qy1 - (r - lo) / max(1e-6, hi - lo) * (qy1 - qy0) * 0.86)
        if prev:
            cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": pt[0], "y2": pt[1]}})
        prev = pt
    cmds += text_at("the exchange rate that results", px0 + 8, qy0 + 16, 10.0, ACCENT)
    cmds += text_at("flows", px0, py0 - 12, 10.5, DIM)
    cmds += text_at("months", (px0 + px1) / 2, qy1 + 22, 10.0, DIM, pan_x=0.0)
    cmds += text_at("the vertical lines are where the two flows cross", 70.0, 424.0,
                    11.0, TEXT)
    cmds += text_at("- and the rate turns at each one, because a currency is just the "
                    "price of wanting it", 70.0, 444.0, 10.5, DIM)
    title(cmds, W, H, "What moves a currency", "two flows, and their net")
    return {"header": header(W, H, "Trade and capital flows plotted above the exchange rate "
                                   "they produce, with the crossings marked"),
            "root": canvas(cmds, INK)}


# ── 12. ECO-IE-00015  Balance of payments — path-form / explain / 2D ───────
# The accounts sum to zero by construction, which is the single most misunderstood thing
# about them. Two mirrored filled paths make that identity visible rather than asserted.
def balance_of_payments():
    W, H = 600, 480
    N = 24
    current = [math.sin(i / 4.0) * 30 - 38 for i in range(N)]
    capital = [-c for c in current]            # the identity, drawn rather than claimed
    px0, px1, cy = 60.0, 540.0, 260.0
    SC = 1.5
    cmds = [paint({"color": PANEL}, {"style": "fill"}),
            {"drawRect": {"left": px0, "top": 140.0, "right": px1, "bottom": 380.0}}]
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.2}))
    cmds.append({"drawLine": {"x1": px0, "y1": cy, "x2": px1, "y2": cy}})
    for series, colour, pid, name in ((current, HOT, "cur", "Current account"),
                                      (capital, GOOD, "cap", "Capital account")):
        xs = [px0 + 12 + (px1 - px0 - 24) * i / (N - 1.0) for i in range(N)]
        cmds.append({"pathCreate": {"id": pid, "x": xs[0], "y": cy}})
        for x, v in zip(xs, series):
            cmds.append({"pathAppendLineTo": {"path": pid, "x": x, "y": cy - v * SC}})
        cmds.append({"pathAppendLineTo": {"path": pid, "x": xs[-1], "y": cy}})
        cmds.append({"pathAppendClose": {"path": pid}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawPath": {"path": pid}})
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.6}))
        cmds.append({"drawPath": {"path": pid}})
    cmds += text_at("Current account", px0 + 10, 160.0, 11.0, HOT)
    cmds += text_at("goods, services, income - what the country sells and buys",
                    px0 + 10, 176.0, 9.0, DIM)
    cmds += text_at("Capital account", px0 + 10, 356.0, 11.0, GOOD)
    cmds += text_at("assets bought and sold - who ends up owning what", px0 + 10,
                    372.0, 9.0, DIM)
    cmds += text_at("zero", px0 - 8, cy + 4, 9.5, DIM, pan_x=1.0)
    for i, q in enumerate(("Q1", "Q2", "Q3", "Q4", "Q5", "Q6")):
        cmds += text_at(q, px0 + 12 + (px1 - px0 - 24) * (i * 4) / (N - 1.0), 400.0,
                        9.5, DIM, pan_x=0.0)
    cmds += text_at("the two shapes are the same shape, mirrored", 60.0, 430.0, 11.5, TEXT)
    cmds += text_at("- a trade deficit IS a capital surplus. The country buying more goods "
                    "than it sells is", 60.0, 450.0, 10.5, DIM)
    cmds += text_at("selling assets to pay for them, and the accounts cannot do otherwise.",
                    60.0, 468.0, 10.5, DIM)
    title(cmds, W, H, "The accounts that must balance", "because they are the same trade, twice")
    return {"header": header(W, H, "The current and capital accounts as mirrored filled "
                                   "paths, showing they sum to zero by construction"),
            "root": canvas(cmds, INK)}


# ── 13. HIS-WH-00001  World history — expression-animation / explore / 2D ──
# A timeline that sweeps, with world population beneath it. The flat stretch is the content:
# for most of recorded history the line barely moves, and the familiar shape is two centuries
# old. Figures before 1700 are estimates and the document says so.
def world_history():
    W, H = 620, 460
    POP = [(-10000, 4), (-5000, 5), (-3000, 14), (-1000, 50), (0, 190), (500, 190),
           (1000, 265), (1500, 460), (1700, 600), (1800, 990), (1900, 1650),
           (1950, 2540), (2000, 6140), (2025, 8200)]
    ERAS = [(-3500, -800, "Bronze and Iron", ACCENT),
            (-800, 500, "Classical", GOOD),
            (500, 1500, "Medieval", WARM),
            (1500, 1800, "Early modern", HOT),
            (1800, 2025, "Industrial", TEXT)]
    px0, px1, py0, py1 = 60.0, 560.0, 180.0, 330.0
    T0, T1 = -4000.0, 2025.0
    def tx(y):
        return px0 + (px1 - px0) * (y - T0) / (T1 - T0)
    cmds = [var("sweep", "continuousSec() * 0.08 - floor(continuousSec() * 0.08)")]
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    for a, b, name, colour in ERAS:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": tx(a), "top": py0 - 22, "right": tx(b),
                                  "bottom": py0 - 12}})
        cmds += text_at(name, (tx(a) + tx(b)) / 2, py0 - 28, 8.5, colour, pan_x=0.0)
    mx = max(p for _, p in POP)
    cmds.append(paint({"color": ACCENT}, {"style": "stroke"}, {"width": 2.6},
                      {"strokeCap": "round"}))
    prev = None
    for yr, p in POP:
        pt = (tx(yr), py1 - (p / mx) * (py1 - py0) * 0.94)
        if prev:
            cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": pt[0], "y2": pt[1]}})
        prev = pt
    for yr, lbl in ((-3000, "3000 BCE"), (-1000, "1000 BCE"), (0, "year 1"),
                    (1000, "1000"), (2000, "2000")):
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 0.8}))
        cmds.append({"drawLine": {"x1": tx(yr), "y1": py0, "x2": tx(yr), "y2": py1}})
        cmds += text_at(lbl, tx(yr), py1 + 20, 9.0, DIM, pan_x=0.0)
    # the sweeping marker
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.6}))
    cmds.append({"drawLine": {"x1": "%.1f + @sweep * %.1f" % (px0, px1 - px0), "y1": py0 - 30,
                              "x2": "%.1f + @sweep * %.1f" % (px0, px1 - px0), "y2": py1 + 8}})
    cmds += text_at("world population", px0 + 8, py0 + 18, 10.5, ACCENT)
    cmds += text_at("8.2 billion", px1 - 6, py1 - (POP[-1][1] / mx) * (py1 - py0) * 0.94 - 8,
                    10.0, ACCENT, pan_x=1.0)
    cmds += text_at("Five thousand years sit in the flat part of that line.",
                    60.0, 376.0, 11.5, TEXT)
    cmds += text_at("Everything that looks like history - the empires, the migrations, the "
                    "whole classical world -", 60.0, 396.0, 10.5, DIM)
    cmds += text_at("happened without the curve moving much at all.", 60.0, 414.0, 10.5, DIM)
    cmds += text_at("Population figures before about 1700 are estimates, and the early "
                    "ones are disputed by a factor of two.", 60.0, 440.0, 9.0, DIM)
    title(cmds, W, H, "Five thousand years", "and where the line actually turns")
    return {"header": header(W, H, "World population from 4000 BCE to the present with "
                                   "historical eras marked, and a sweeping time marker"),
            "root": canvas(cmds, INK)}


# ── 14. HIS-AC-00002  Ancient civilisations — particle-system / compare / 3D ─
# Four civilisations as columns rising out of a plane, with their spans as the heights and
# particles marking the centuries. The 3D carries time depth here rather than decorating a
# map: the overlaps are the point, and they are hard to see on a flat bar chart.
def ancient():
    W, H = 540, 620
    CIVS = [("Egypt", -3100, -30, GOOD, "Old Kingdom to the Roman annexation"),
            ("Mesopotamia", -3500, -539, ACCENT, "Sumer to the fall of Babylon"),
            ("Indus Valley", -3300, -1300, WARM, "Harappa and Mohenjo-daro"),
            ("Shang / Zhou China", -1600, -256, HOT, "the first documented dynasties")]
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.70,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [2.2, 1.9, 3.5], "center": [0.0, 0.30, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.42, -0.58, -0.70], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.25, 0.48], "intensity": 0.42}]}}]
    cmds.append(var("spin", "sin(continuousSec() * 0.2) * 0.45"))
    T0, T1 = -3600.0, 0.0
    SC = 1.5 / (T1 - T0)
    for ci, (name, start, end, colour, note) in enumerate(CIVS):
        x = -0.72 + ci * 0.48
        lo = (start - T0) * SC
        hi = (end - T0) * SC
        verts, normals, uv, idx = [], [], [], []
        mesh_box(verts, normals, uv, idx, (x - 0.15, lo, -0.15), (x + 0.15, hi, 0.15))
        cmds.append({"defineMesh3D": {"id": 10 + ci, "verts": [round(v, 5) for v in verts],
                                      "normals": normals, "uv": uv, "indices": idx}})
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": 10 + ci, "mode": "software-smooth"}}]
    # century markers drifting up the columns
    # One stream, standing clear of the columns as a time axis. Scattered across the four
    # columns they read as decoration beside the bars rather than as centuries passing,
    # because a particle cannot know which column's span it is meant to sit within.
    cmds.append({"createParticles": {
        "id": "cent", "count": 54,
        "variables": ["cx", "cy", "cz", "cs"],
        "initialValues": ["-1.12", "rand() * 1.5", "0.0", "0.25 + rand() * 0.4"]}})
    cmds.append(paint({"color": TEXT}, {"style": "fill"}))
    cmds.append({"meshPrimitive3D": {"id": 20, "primitive": "sphere", "segments": 6,
                                     "radius": 0.022, "center": [0, 0, 0]}})
    cmds.append({"particlesLoop": {
        "system": "@cent",
        "equations": ["cx", "(cy + cs * 0.004) % 1.5", "cz", "cs"],
        "commands": [
            {"matrix3D": {"op": "identity"}},
            {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
            {"matrix3D": {"op": "translate", "x": "@cx", "y": "@cy", "z": "@cz"}},
            {"drawMesh3D": {"mesh": 20, "mode": "software-smooth"}}]}})
    y = 430.0
    for name, start, end, colour, note in CIVS:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 40.0, "top": y - 10, "right": 54.0,
                                  "bottom": y + 4}})
        cmds += text_at(name, 64.0, y, 11.5, colour)
        cmds += text_at("%d - %d BCE" % (-start, -end), 300.0, y, 10.0, TEXT, pan_x=1.0)
        cmds += text_at(note, 312.0, y, 9.0, DIM)
        y += 26.0
    cmds += text_at("These four overlap for most of their length.", 40.0, 552.0, 11.0, TEXT)
    cmds += text_at("Egypt and Mesopotamia were contemporaries for three thousand years - "
                    "longer than the gap", 40.0, 570.0, 10.0, DIM)
    cmds += text_at("between the last pharaoh and now.", 40.0, 586.0, 10.0, DIM)
    cmds += text_at("Start dates are conventional and contested; each marks a threshold "
                    "someone chose.", 40.0, 606.0, 8.5, DIM)
    title(cmds, W, H, "Four civilisations", "as spans, not as a sequence")
    return {"header": header(W, H, "Four ancient civilisations as 3D columns whose heights "
                                   "are their spans, showing how much they overlap"),
            "root": canvas(cmds, INK)}


# ── 15. HIS-MH-00003  Medieval history — interactive / demonstrate / 2D ────
# Drag through three centuries and watch one manor's obligations change. The Black Death is
# the hinge: losing a third of the workforce did more for the bargaining position of the
# survivors than any charter, which is a grim thing to be able to show as a curve.
def medieval():
    W, H = 600, 500
    cmds = [{"touchExpression": {"name": "drag", "defaultValue": 150.0, "min": 60.0,
                                 "max": 540.0, "expression": "touchX()"}},
            var("yr", "1200.0 + (@drag - 60.0) / 480.0 * 300.0")]
    px0, px1, py0, py1 = 60.0, 540.0, 150.0, 330.0
    Y0, Y1 = 1200.0, 1500.0
    def tx(y):
        return px0 + (px1 - px0) * (y - Y0) / (Y1 - Y0)
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    # the plague, as a band rather than a line - it was not one year
    cmds.append(paint({"color": HOT}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": tx(1347), "top": py0, "right": tx(1351),
                              "bottom": py1}})
    cmds += text_at("the plague, 1347-51", tx(1351) + 6, py0 + 16, 10.0, HOT)
    def labour(y):
        """Days of unpaid labour owed per year - high, then collapsing after the plague."""
        if y < 1347:
            return 120 - (y - 1200) * 0.06
        return max(28.0, 111 - (y - 1347) * 0.62)
    def wage(y):
        if y < 1347:
            return 1.0 + (y - 1200) * 0.0008
        return min(2.6, 1.12 + (y - 1347) * 0.011)
    for fn, colour, name, scale in ((labour, WARM, "days of labour owed", 130.0),
                                    (wage, GOOD, "a labourer's real wage", 3.0)):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6},
                          {"strokeCap": "round"}))
        prev = None
        for i in range(61):
            y = Y0 + (Y1 - Y0) * i / 60.0
            pt = (tx(y), py1 - fn(y) / scale * (py1 - py0) * 0.92)
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1],
                                          "x2": pt[0], "y2": pt[1]}})
            prev = pt
        cmds += text_at(name, px0 + 8, py0 + (34 if colour == WARM else 50), 9.5, colour)
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.6}))
    cmds.append({"drawLine": {"x1": "%.1f + (@yr - 1200.0) / 300.0 * %.1f" % (px0, px1 - px0),
                              "y1": py0,
                              "x2": "%.1f + (@yr - 1200.0) / 300.0 * %.1f" % (px0, px1 - px0),
                              "y2": py1}})
    for y in (1200, 1300, 1400, 1500):
        cmds += text_at("%d" % y, tx(y), py1 + 22, 9.5, DIM, pan_x=0.0)
    cmds += [{"variable": {"name": "ylabel", "commit": True,
                           "value": {"type": "textFromFloat", "value": "@yr",
                                     "whole": 4, "decimal": 0}}},
             paint({"color": TEXT}, {"style": "fill"}, {"textSize": 15.0}),
             {"drawTextAnchored": {"text": "@ylabel", "x": 60.0, "y": 382.0,
                                   "panX": -1.0, "panY": 0.0, "flags": 0}}]
    cmds.append({"conditionalOperations": {
        "condition": "lt", "v1": "@yr", "v2": 1347.0,
        "commands": [paint({"color": WARM}, {"style": "fill"}, {"textSize": 11.0}),
                     {"drawTextAnchored": {
                         "text": "labour is owed, not sold - and there is always someone "
                                 "else to do it",
                         "x": 128.0, "y": 382.0, "panX": -1.0, "panY": 0.0, "flags": 0}}]}})
    cmds.append({"conditionalOperations": {
        "condition": "ge", "v1": "@yr", "v2": 1347.0,
        "commands": [paint({"color": GOOD}, {"style": "fill"}, {"textSize": 11.0}),
                     {"drawTextAnchored": {
                         "text": "a third of the workforce is dead, and the survivors can "
                                 "name a price",
                         "x": 128.0, "y": 382.0, "panX": -1.0, "panY": 0.0, "flags": 0}}]}})
    cmds += text_at("Laws were passed to freeze wages at the old rates. They did not hold.",
                    60.0, 424.0, 11.0, TEXT)
    cmds += text_at("- the Ordinance of Labourers in 1349, and the Statute two years later, "
                    "were both ignored", 60.0, 444.0, 10.5, DIM)
    cmds += text_at("widely enough to be re-issued for a century.", 60.0, 462.0, 10.5, DIM)
    cmds += text_at("Figures are illustrative of the English manorial pattern, not one "
                    "manor's records.", 60.0, 484.0, 8.5, DIM)
    title(cmds, W, H, "After the plague", "drag through three centuries")
    return {"header": header(W, H, "Labour obligations falling and real wages rising across "
                                   "the fourteenth century, draggable by year"),
            "root": canvas(cmds, INK)}


# ── 16. HIS-EMH-00004  Early modern — raster-and-text / simulate / 2D ──────
# What a book cost, before and after printing. The figures are the argument: a scribe's
# manuscript was a year's wages and a printed book was a week's, and nothing else about the
# period makes sense without that.
def early_modern():
    W, H = 580, 520
    ROWS = [("A scribe, 1440", "4 to 8 months", "about a year's wages for a labourer",
             1.00, HOT),
            ("Gutenberg, 1455", "a few weeks", "still a cathedral's purchase, not a "
             "person's", 0.42, WARM),
            ("A press, 1500", "days", "roughly a month's wages", 0.09, ACCENT),
            ("A press, 1600", "hours", "a week's wages, and falling", 0.02, GOOD)]
    cmds = []
    y = 150.0
    for name, time_taken, cost, frac, colour in ROWS:
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 44.0, "top": y - 22, "right": 536.0,
                                  "bottom": y + 44}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 44.0, "top": y - 22, "right": 49.0,
                                  "bottom": y + 44}})
        cmds += text_at(name, 62.0, y, 13.0, colour)
        cmds += text_at("to make one copy:", 62.0, y + 18, 9.0, DIM)
        cmds += text_at(time_taken, 168.0, y + 18, 10.0, TEXT)
        cmds += text_at(cost, 62.0, y + 34, 9.5, DIM)
        # relative cost, on one scale across all four rows
        cmds.append(paint({"color": RULE}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 300.0, "top": y - 6, "right": 524.0,
                                  "bottom": y + 8}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 300.0, "top": y - 6,
                                  "right": 300.0 + 224.0 * frac, "bottom": y + 8}})
        cmds += text_at("%.0f%%" % (frac * 100), 524.0, y + 24, 9.0, TEXT, pan_x=1.0)
        y += 84.0
    cmds += text_at("Fifty times cheaper inside two generations.", 44.0, 492.0 - 26, 12.0, TEXT)
    cmds += text_at("Every argument about the Reformation, the scientific revolution and "
                    "the vernacular languages", 44.0, 492.0 - 8, 10.0, DIM)
    cmds += text_at("starts from that one number. Costs are order-of-magnitude estimates "
                    "from scattered records.", 44.0, 492.0 + 8, 10.0, DIM)
    title(cmds, W, H, "What a book cost", "before and after the press")
    return {"header": header(W, H, "The cost and time to produce one book across four "
                                   "stages from manuscript to the mature press"),
            "root": canvas(cmds, INK)}



# ── 17. CAL-GLOBE-00001  Texture calibration — instrument, not a catalogue entry ──
# This document exists to answer one question: does a point placed by latitude and longitude
# land on the place the texture draws there?
#
# It draws the SAME uv_sphere with the SAME texture as ECO-IE-00012, and over it a graticule
# built from latlon() - the same function the trade routes use. If the two agree, the drawn
# equator runs along the map's equator and the drawn prime meridian passes down through
# Greenwich, the Gulf of Guinea and nothing else. If they disagree, the size and the shape of
# the disagreement is visible directly rather than inferred from pixel counts.
#
# Landmark pins are placed at points no one can argue about - the tip of South America, the
# Cape, the Horn of Africa - so a reader can see at a glance whether the overlay is right.
#
# Drag changes the longitude offset applied to the OVERLAY, so a correction can be dialled in
# and read off instead of guessed. The number is printed.
def calibration():
    W, H = 560, 720
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.62,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [0.0, 0.0, 4.6], "center": [0.0, 0.0, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [0.0, 0.0, -1.0], "intensity": 1.0}]}}]
    # Head-on, no y offset, no tilt. Every earlier measurement that disagreed with another
    # did so because it was taken on an oblique camera; this one removes that variable.
    cmds.append({"touchExpression": {"name": "drag", "defaultValue": 280.0,
                                     "min": 0.0, "max": 560.0,
                                     "expression": "touchX()"}})
    cmds.append(var("spin", "(@drag - 280.0) / 180.0"))

    R0 = 1.0
    cmds.append(uv_sphere(1, R0, nlat=32, nlon=64))
    cmds.append({"texture3D": {"bitmap": "@earth"}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": "#FFFFFFFF"}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]
    cmds.append({"texture3D": {"bitmap": 0}})

    def latlon(lat, lon):
        """The convention under test. Identical to the one trade() uses for its routes."""
        la, lo = math.radians(lat), math.radians(lon)
        return (math.cos(la) * math.sin(lo), math.sin(la), math.cos(la) * math.cos(lo))

    def polyline(mesh_id, pts, rad, lift=1.004):
        """Ribbons, not tubes. A tube on the far side of the globe is not reliably hidden
        (F-027), so half the graticule used to show through and made the overlay unreadable.
        A ribbon's single face points outward and is culled round the back."""
        return surface_ribbon(mesh_id, [latlon(la, lo) for (la, lo) in pts], rad, lift)

    def draw(mesh, colour):
        # extend, not += : an augmented assignment inside a nested function would make
        # `cmds` local to it
        cmds.append(mesh)
        cmds.extend([{"matrix3D": {"op": "identity"}},
                     {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                     paint({"color": colour}, {"style": "fill"}),
                     {"drawMesh3D": {"mesh": mesh["defineMesh3D"]["id"],
                                     "mode": "software-flat"}}])

    mid = 10
    # the ordinary graticule, every 30 degrees
    for lon in range(-180, 180, 45):
        if lon == 0:
            continue
        draw(polyline(mid, [(la, lon) for la in range(-80, 81, 6)], 0.004), DIM)
        mid += 1
    for lat in (-60, -30, 30, 60):
        draw(polyline(mid, [(lat, lo) for lo in range(-180, 181, 6)], 0.004), DIM)
        mid += 1
    # the two lines that matter, picked out
    draw(polyline(mid, [(0, lo) for lo in range(-180, 181, 4)], 0.010), GOOD)
    mid += 1
    draw(polyline(mid, [(la, 0) for la in range(-90, 91, 4)], 0.010), HOT)
    mid += 1

    # landmarks that cannot be mistaken for anywhere else
    # Each pin gets its own colour so a misplaced one can be named, not guessed at. All six
    # are coastal extremities - there is no argument about where they are.
    PINS = [("Cape Horn", -55.9, -67.3, "#FFFF3B30"),
            ("Good Hope", -34.4, 18.5, "#FFFFCC00"),
            ("Horn of Africa", 11.8, 51.3, "#FF34C759"),
            ("Gibraltar", 36.1, -5.4, "#FF5AC8FA"),
            ("Kamchatka", 51.2, 157.0, "#FFFF9500"),
            ("Cape York", -10.7, 142.5, "#FFFF2D92")]
    for pi, (nm, la, lo, colour) in enumerate(PINS):
        cmds.append(surface_patch(60 + pi, latlon(la, lo), 0.022, 1.006))
        cmds.extend([{"matrix3D": {"op": "identity"}},
                     {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                     paint({"color": colour}, {"style": "fill"}),
                     {"drawMesh3D": {"mesh": 60 + pi, "mode": "software-flat"}}])

    cmds += text_at("green line = the equator as latlon() draws it", 28.0, 548.0, 10.0, GOOD)
    cmds += text_at("red line = the prime meridian, longitude zero", 28.0, 564.0, 10.0, HOT)
    for i, (nm, la, lo, colour) in enumerate(PINS):
        x = 28.0 + (i % 3) * 178.0
        y = 586.0 + (i // 3) * 17.0
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": x + 4, "cy": y - 4, "radius": 4.0}})
        cmds += text_at("%s  %+.0f %+.0f" % (nm, la, lo), x + 13, y, 9.0, TEXT)
    cmds += text_at("If the mapping is right the green line follows the map's own equator, "
                    "the red line runs down", 28.0, 636.0, 9.5, TEXT)
    cmds += text_at("through the Gulf of Guinea, and every pin sits on its own headland.",
                    28.0, 652.0, 9.5, TEXT)
    cmds += text_at("A constant gap is an offset. A gap that changes along the line is a "
                    "distortion. They need", 28.0, 670.0, 9.5, DIM)
    cmds += text_at("different fixes, which is why the earlier single-number corrections "
                    "kept half-working.", 28.0, 686.0, 9.5, DIM)
    cmds += text_at("drag to turn the globe. Every mark here is outward-facing, so anything "
                    "round the back is culled.", 28.0, 708.0, 9.0, DIM)
    cmds += text_at("uv = ((1.5 - u) % 1, 1 - v)", 532.0, 708.0, 9.5, DIM, pan_x=1.0)
    title(cmds, W, H, "Texture calibration",
          "does a place drawn by lat/lon land where the map puts it?")
    return {"header": header(W, H, "A graticule and six coastal landmarks drawn by latitude "
                                   "and longitude over the Blue Marble texture, to check "
                                   "that the two agree"),
            "resources": embedded_bitmap("earth", "textures/earth.png"),
            "root": canvas(cmds, INK)}


# ── build ──────────────────────────────────────────────────────────────────────
BUILD = [("PHY-QM-00025", entanglement), ("PHY-QM-00026", spin),
         ("BIO-GENE-00023", popgen), ("MTH-ALGE-00008", transformations),
         ("CSC-DS-00008", trees), ("CHM-MS-00008", polarity),
         ("EAR-GEOP-00008", seismic), ("ENG-EE-00008", transistors),
         ("ECO-IE-00012", trade), ("ECO-IE-00013", tariffs),
         ("ECO-IE-00014", currency_flows), ("ECO-IE-00015", balance_of_payments),
         ("HIS-WH-00001", world_history), ("HIS-AC-00002", ancient),
         ("HIS-MH-00003", medieval), ("HIS-EMH-00004", early_modern),
         # An instrument rather than a catalogue document: it exists to measure the texture
         # mapping, not to explain anything. Set 8 therefore ships 17 files.
         ("CAL-GLOBE-00001", calibration)]

if __name__ == "__main__":
    for doc_id, fn in BUILD:
        name = use(doc_id)
        d = fn()
        (OUT / ("%s.json" % doc_id)).write_text(json.dumps(d, indent=1) + "\n")
        print("  %-16s %-9s %s" % (doc_id, name, d["header"]["contentDescription"][:48]))
    print("  %d documents" % len(BUILD))
