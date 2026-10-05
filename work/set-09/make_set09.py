#!/usr/bin/env python3
"""Build set 9 of the visualization programme: 16 documents.

    python3 work/set-09/make_set09.py

Work order from `python3 tools/visplan.py set 9`.

Helper block carried from set 8, where a long-running defect was finally found: uv_sphere
had been winding its triangles inside out, so the player drew the inner surface of the far
hemisphere - mirrored and travelling backwards. Everything that block now contains is
post-fix. The rules it encodes, each paid for by an earlier set:

  winding decides visibility     a wrongly wound mesh is invisible (F-008), and a wrongly
                                 wound SPHERE is worse - it quietly shows you its far side
  routes are ribbons             one outward-facing face, culled round the back, so nothing
                                 depends on occlusion (F-027)
  embed bitmaps as base64        a file-named bitmap is not self-contained (F-030)
  clipRect is permanent          it intersects and never widens (F-021)
  textFromFloat wants a string   a numeric literal renders as 0, silently (F-020)
  expressions cap at 32 tokens   rcj writes longer ones that a device refuses (F-022)
  3D fills the document          a scene in a sized card projects outside it (F-013)
  clamp(min, max, value)         the value goes last
  render with --clock AND --seed the clock alone does not pin rand() (F-023)
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


# ── 1. PHY-QM-00027  Quantum fields — static-diagram / simulate / 2D ────────
# A field is a number at every point; a particle is a lump in it. Drawing the same field at
# four excitation levels is the only honest way to show that "particle" is a description of
# the field's state rather than a separate kind of thing.
def quantum_fields():
    W, H = 620, 420
    PANELS = [("Vacuum", 0, "not nothing - the lowest state the field can hold", DIM),
              ("One quantum", 1, "a single lump. This is what we call a particle.", GOOD),
              ("Two quanta", 2, "two lumps in the same field, not two fields", ACCENT),
              ("A wave packet", 3, "many quanta, and it starts to look classical", WARM)]
    cmds = []
    pw = 136.0
    for i, (name, n, note, colour) in enumerate(PANELS):
        x0 = 26.0 + i * (pw + 10.0)
        cy = 230.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": 130.0, "right": x0 + pw,
                                  "bottom": 310.0}})
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": x0 + 6, "y1": cy, "x2": x0 + pw - 6, "y2": cy}})
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.2},
                          {"strokeCap": "round"}))
        prev = None
        for k in range(49):
            u = k / 48.0
            xx = x0 + 6 + u * (pw - 12)
            if n == 0:
                amp = 3.0 * math.sin(u * 37.0)
            elif n == 3:
                amp = 44.0 * math.exp(-((u - 0.5) / 0.22) ** 2) * math.cos(u * 26.0)
            else:
                amp = sum(38.0 * math.exp(-((u - (j + 1) / (n + 1.0)) / 0.10) ** 2)
                          for j in range(n))
            yy = cy - amp
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": xx, "y2": yy}})
            prev = (xx, yy)
        cmds += text_at(name, x0 + pw / 2, 122.0, 11.5, colour, pan_x=0.0)
        # Wrapped to the panel. Unwrapped, every note was wider than the 136px panel it
        # belonged to, and the fourth one ran off the page - so the first three overlapped
        # their neighbour's note and the last lost its ending.
        for wi, line in enumerate(_wrap(note, 30)):
            cmds += text_at(line, x0, 330.0 + wi * 12.0, 8.5, DIM)
    cmds += text_at("The field is the same object in all four panels. Only its state differs.",
                    26.0, 374.0, 11.0, TEXT)
    cmds += text_at("- which is why particles can be created and destroyed, and why their "
                    "number is not conserved", 26.0, 394.0, 10.0, DIM)
    title(cmds, W, H, "A field, four states", "the particle is the lump, not the thing")
    return {"header": header(W, H, "One quantum field drawn at four excitation levels, "
                                   "showing particles as lumps in the field"),
            "root": canvas(cmds, INK)}


# ── 2. PHY-CM-00028  Forces — annotated-layout / analyze / 2D ───────────────
# A free-body diagram per situation, with the forces named and the net stated. The layout is
# the argument: the same four arrows appear in every card, and only their lengths change.
def forces():
    W, H = 500, 640
    CASES = [("At rest on a table", 0, "weight down, normal up, and they cancel exactly",
              ((0, -1, "normal", GOOD), (0, 1, "weight", HOT)), "net zero", DIM),
             ("Sliding, friction on", 1, "a push forward, friction back, still no "
              "acceleration", ((1, 0, "push", ACCENT), (-0.7, 0, "friction", WARM),
                               (0, -1, "normal", GOOD), (0, 1, "weight", HOT)),
              "net forward, small", ACCENT),
             ("In free fall", 2, "nothing holds it up any more",
              ((0, 1, "weight", HOT),), "net down, full g", HOT),
             ("Circling on a string", 3, "the tension points at the centre, always",
              ((-1, 0, "tension", ACCENT), (0, 1, "weight", HOT)),
              "net toward the centre", GOOD)]

    def card(name, note, arrows, net, colour):
        c = [{"clipRect": {"left": 0, "top": 0, "right": 120, "bottom": 104}},
             paint({"color": RULE}, {"style": "fill"}),
             {"drawRect": {"left": 0, "top": 0, "right": 120, "bottom": 104}}]
        cx, cy = 60.0, 52.0
        c.append(paint({"color": PANEL}, {"style": "fill"}))
        c.append({"drawRect": {"left": cx - 13, "top": cy - 13, "right": cx + 13,
                               "bottom": cy + 13}})
        for dx, dy, lbl, acol in arrows:
            L = 34.0
            ex, ey = cx + dx * L, cy + dy * L
            c.append(paint({"color": acol}, {"style": "stroke"}, {"width": 2.4},
                           {"strokeCap": "round"}))
            c.append({"drawLine": {"x1": cx, "y1": cy, "x2": ex, "y2": ey}})
            hx, hy = -dy, dx
            c.append({"drawLine": {"x1": ex, "y1": ey,
                                   "x2": ex - dx * 7 + hx * 5, "y2": ey - dy * 7 + hy * 5}})
            c.append({"drawLine": {"x1": ex, "y1": ey,
                                   "x2": ex - dx * 7 - hx * 5, "y2": ey - dy * 7 - hy * 5}})
        return {"type": "canvas", "modifiers": [{"width": 120}, {"height": 104}],
                "commands": c}

    kids = [{"type": "text", "value": "Four free bodies", "modifiers": [],
             "fontSize": 19.0, "color": TEXT},
            {"type": "spacer", "modifiers": [{"height": 3}]},
            {"type": "text", "value": "the same arrows every time; only the lengths change",
             "modifiers": [], "fontSize": 11.0, "color": DIM},
            {"type": "spacer", "modifiers": [{"height": 14}]}]
    for name, idx, note, arrows, net, colour in CASES:
        kids.append({"type": "row",
                     "modifiers": [{"width": 456}, {"padding": 9}, {"background": PANEL}],
                     "children": [
                         card(name, note, arrows, net, colour),
                         {"type": "spacer", "modifiers": [{"width": 12}]},
                         {"type": "column", "modifiers": [{"width": 300}], "children": [
                             {"type": "text", "value": name, "modifiers": [],
                              "fontSize": 13.0, "color": colour},
                             {"type": "spacer", "modifiers": [{"height": 4}]},
                             {"type": "text", "value": note, "modifiers": [],
                              "fontSize": 9.5, "color": DIM},
                             {"type": "spacer", "modifiers": [{"height": 6}]},
                             {"type": "text", "value": net, "modifiers": [],
                              "fontSize": 11.0, "color": TEXT}]}]})
        kids.append({"type": "spacer", "modifiers": [{"height": 8}]})
    kids.append({"type": "text",
                 "value": "An object at rest and an object sliding at a steady speed have "
                          "the same net force on them: none. Newton's first law is the "
                          "claim that those two states need no explaining.",
                 "modifiers": [], "fontSize": 10.0, "color": DIM})
    return {"header": header(W, H, "Four free-body diagrams with their forces named and "
                                   "the net force stated for each"),
            "root": {"type": "column",
                     "modifiers": ["fillMaxSize", {"padding": 18}, {"background": INK}],
                     "children": kids}}


# ── 3. PHY-CM-00029  Motion — data-plot / explain / 2D ──────────────────────
# Position, velocity and acceleration stacked on one time axis for a single journey. Stacking
# is the whole point: the slope of each curve is the one below it, and a reader can check
# that by eye instead of taking it on trust.
def motion():
    W, H = 580, 520
    N = 80
    def a(t):
        if t < 0.25: return 1.0
        if t < 0.60: return 0.0
        if t < 0.85: return -1.4
        return 0.0
    acc, vel, pos = [], [], []
    v = p = 0.0
    for i in range(N):
        t = i / (N - 1.0)
        A = a(t)
        v += A * (1.0 / N) * 4.0
        p += v * (1.0 / N) * 4.0
        acc.append(A); vel.append(v); pos.append(p)
    px0, px1 = 70.0, 540.0
    bands = [("position", pos, GOOD, 140.0, 240.0),
             ("velocity", vel, ACCENT, 250.0, 350.0),
             ("acceleration", acc, WARM, 360.0, 440.0)]
    cmds = []
    for name, series, colour, y0, y1 in bands:
        lo, hi = min(series), max(series)
        rng = (hi - lo) or 1.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": px0, "top": y0, "right": px1, "bottom": y1}})
        if lo < 0 < hi:
            zy = y1 - (0 - lo) / rng * (y1 - y0)
            cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
            cmds.append({"drawLine": {"x1": px0, "y1": zy, "x2": px1, "y2": zy}})
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.4},
                          {"strokeCap": "round"}))
        prev = None
        for i, s in enumerate(series):
            x = px0 + (px1 - px0) * i / (N - 1.0)
            y = y1 - (s - lo) / rng * (y1 - y0) * 0.92 - 4
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": x, "y2": y}})
            prev = (x, y)
        cmds += text_at(name, px0 + 8, y0 + 16, 10.5, colour)
    for frac, lbl in ((0.25, "stops speeding up"), (0.60, "brakes"), (0.85, "stopped")):
        x = px0 + (px1 - px0) * frac
        cmds.append(paint({"color": DIM}, {"style": "stroke"}, {"width": 0.8}))
        cmds.append({"drawLine": {"x1": x, "y1": 140.0, "x2": x, "y2": 440.0}})
        cmds += text_at(lbl, x + 4, 456.0, 8.5, DIM)
    cmds += text_at("each curve is the slope of the one above it", 70.0, 480.0, 11.0, TEXT)
    cmds += text_at("- the corners in acceleration are where velocity changes direction of "
                    "bend, and position never kinks", 70.0, 498.0, 10.0, DIM)
    title(cmds, W, H, "One journey, three ways", "position, velocity, acceleration")
    return {"header": header(W, H, "Position, velocity and acceleration for one journey "
                                   "stacked on a shared time axis"),
            "root": canvas(cmds, INK)}


# ── 4. PHY-CM-00030  Momentum — path-form / explore / 2D ────────────────────
# Two carts colliding, drawn as paths in position-time. The slopes before and after encode
# the velocities, and the fact that total momentum is unchanged becomes a statement about
# the slopes rather than a formula.
def momentum():
    W, H = 580, 500
    cmds = []
    px0, px1, py0, py1 = 70.0, 540.0, 140.0, 380.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    tc = 0.52
    CARTS = [("Cart A, 2 kg", 2.0, 0.30, 1.6, 0.4, GOOD),
             ("Cart B, 1 kg", 1.0, 0.80, -0.8, 1.8, ACCENT)]
    for name, m, x0, v0, v1, colour in CARTS:
        pid = name.split(",")[0].replace(" ", "")
        def X(t):
            return x0 + (v0 * t if t <= tc else v0 * tc + v1 * (t - tc))
        pts = [(px0 + (px1 - px0) * (t / 1.0), py1 - X(t) * 72.0) for t in
               [i / 60.0 for i in range(61)]]
        cmds.append({"pathCreate": {"id": pid, "x": pts[0][0], "y": pts[0][1]}})
        for (x, y) in pts[1:]:
            cmds.append({"pathAppendLineTo": {"path": pid, "x": x, "y": max(py0 + 4, min(py1 - 4, y))}})
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.8},
                          {"strokeCap": "round"}))
        cmds.append({"drawPath": {"path": pid}})
        cmds += text_at(name, px0 + 8, py0 + (18 if colour == GOOD else 34), 10.0, colour)
    cx = px0 + (px1 - px0) * tc
    cmds.append(paint({"color": HOT}, {"style": "stroke"}, {"width": 1.4}))
    cmds.append({"drawLine": {"x1": cx, "y1": py0, "x2": cx, "y2": py1}})
    cmds += text_at("they touch", cx + 6, py0 + 14, 10.0, HOT)
    cmds += text_at("position", px0, py0 - 12, 10.5, DIM)
    cmds += text_at("time", (px0 + px1) / 2, py1 + 22, 10.0, DIM, pan_x=0.0)
    y = 416.0
    for lbl, before, after in (("Cart A momentum", "2 x 1.6 = +3.2", "2 x 0.4 = +0.8"),
                               ("Cart B momentum", "1 x -0.8 = -0.8", "1 x 1.8 = +1.8"),
                               ("Total", "+2.4", "+2.6")):
        cmds += text_at(lbl, 70.0, y, 10.5, TEXT if lbl != "Total" else GOOD)
        cmds += text_at(before, 250.0, y, 10.5, DIM)
        cmds += text_at(after, 400.0, y, 10.5, DIM)
        y += 18.0
    cmds += text_at("the totals differ only by rounding in the numbers printed here",
                    70.0, 478.0, 9.5, DIM)
    title(cmds, W, H, "A collision in position-time", "the slopes are the velocities")
    return {"header": header(W, H, "Two carts colliding, drawn as paths in position against "
                                   "time, with the momentum arithmetic beneath"),
            "root": canvas(cmds, INK)}


# ── 5. BIO-MICR-00024  Bacteria — expression-animation / compare / 3D ──────
# Two bacteria at true relative scale, dividing on a shared clock. 3D because a cell is a
# volume and the difference between a coccus and a bacillus is a shape fact, not a drawing
# convention.
def bacteria():
    W, H = 520, 620
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.70,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [1.1, 0.8, 4.6], "center": [0.0, 0.25, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.4, -0.5, -0.76], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.3, 0.45], "intensity": 0.42}]}}]
    cmds.append(var("ph", "continuousSec() * 0.22 - floor(continuousSec() * 0.22)"))
    cmds.append(var("sep", "@ph * 0.62"))
    # a coccus pair and a bacillus pair, drawn at the same scale
    for mid, kind, cx, colour in ((1, "sphere", -0.62, GOOD), (3, "box", 0.72, ACCENT)):
        for half in (0, 1):
            sign = -1.0 if half == 0 else 1.0
            if kind == "sphere":
                cmds.append({"meshPrimitive3D": {"id": mid + half, "primitive": "sphere",
                                                 "segments": 20, "radius": 0.26,
                                                 "center": [0, 0, 0]}})
            else:
                v, n, u, i = [], [], [], []
                mesh_box(v, n, u, i, (-0.17, -0.17, -0.42), (0.17, 0.17, 0.42))
                cmds.append({"defineMesh3D": {"id": mid + half, "verts": v, "normals": n,
                                              "uv": u, "indices": i}})
            cmds += [{"matrix3D": {"op": "identity"}},
                     {"matrix3D": {"op": "translate",
                                   "x": "%.2f + @sep * %.2f" % (cx, sign * 0.62),
                                   "y": 0.25, "z": 0.0}},
                     paint({"color": colour}, {"style": "fill"}),
                     {"drawMesh3D": {"mesh": mid + half, "mode": "software-smooth"}}]
    cmds += text_at("Coccus", 140.0, 400.0, 13.0, GOOD, pan_x=0.0)
    cmds += text_at("about 1 micrometre across", 140.0, 418.0, 9.0, DIM, pan_x=0.0)
    cmds += text_at("Bacillus", 380.0, 400.0, 13.0, ACCENT, pan_x=0.0)
    cmds += text_at("1 by 3 micrometres", 380.0, 418.0, 9.0, DIM, pan_x=0.0)
    ROWS = [("Doubling time", "20 minutes for E. coli in a rich broth, hours in soil"),
            ("What limits it", "not the genome - the ribosomes, which must be built first"),
            ("Why shape matters", "a rod has more surface for the same volume, which helps "
             "when food is scarce")]
    y = 462.0
    for name, note in ROWS:
        cmds.append(paint({"color": WARM}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 36.0, "top": y - 9, "right": 41.0,
                                  "bottom": y + 5}})
        cmds += text_at(name, 52.0, y, 11.0, TEXT)
        cmds += text_at(note, 52.0, y + 15, 9.0, DIM)
        y += 38.0
    title(cmds, W, H, "Two shapes, one clock", "both dividing, drawn at the same scale")
    return {"header": header(W, H, "A coccus and a bacillus dividing in 3D on a shared "
                                   "clock, at true relative scale"),
            "root": canvas(cmds, INK)}


# ── 6. BIO-MICR-00025  Viruses — particle-system / demonstrate / 2D ────────
# One infected cell releasing virions. The particle count is the argument: a single burst is
# hundreds to thousands, which is why an infection goes from undetectable to overwhelming in
# a day and why "the dose" matters so little once it has started.
def viruses():
    W, H = 540, 560
    cmds = []
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": 40.0, "top": 130.0, "right": 500.0, "bottom": 390.0}})
    # the cell, bursting
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 2.0}))
    cmds.append({"drawCircle": {"cx": 270.0, "cy": 260.0, "radius": 52.0}})
    cmds.append(paint({"color": HOT}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": 270.0, "cy": 260.0, "radius": 16.0}})
    cmds += text_at("one infected cell", 270.0, 330.0, 10.0, DIM, pan_x=0.0)
    cmds.append({"createParticles": {
        "id": "virions", "count": 180,
        "variables": ["vx", "vy", "sp", "ang"],
        "initialValues": ["270.0", "260.0", "0.4 + rand() * 1.6", "rand() * 6.28"]}})
    cmds.append(paint({"color": WARM}, {"style": "fill"}))
    cmds.append({"particlesLoop": {
        "system": "@virions",
        "equations": ["270 + cos(ang) * ((sp * 40.0) % 210)",
                      "260 + sin(ang) * ((sp * 40.0) % 125)",
                      "sp + 0.004", "ang"],
        "commands": [{"drawCircle": {"cx": "@vx", "cy": "@vy", "radius": 2.2}}]}})
    y = 420.0
    for n, lbl, colour in (("~1", "virions needed to start an infection", HOT),
                           ("100 - 10,000", "released when one cell bursts", WARM),
                           ("8 - 12 hours", "from entry to burst, for influenza", ACCENT)):
        cmds += text_at(n, 40.0, y, 13.0, colour)
        cmds += text_at(lbl, 170.0, y, 10.5, TEXT)
        y += 24.0
    cmds += text_at("one cell's output can infect a thousand more, so the curve is "
                    "exponential from the first hour", 40.0, 504.0, 10.0, TEXT)
    cmds += text_at("- not because the virus changes, but because every new cell does the "
                    "same thing again", 40.0, 522.0, 10.0, DIM)
    title(cmds, W, H, "One burst", "which is why the second day looks nothing like the first")
    return {"header": header(W, H, "A single infected cell releasing a burst of virions as "
                                   "a particle system, with the numbers beside it"),
            "root": canvas(cmds, INK)}


# ── 7. BIO-MICR-00026  Fungi — interactive / simulate / 2D ─────────────────
# Drag to grow a mycelium. A fungus is not a plant that happens to lack leaves - it is a
# network that eats by growing through its food, and the branching rule is the organism.
def fungi():
    W, H = 560, 560
    cmds = [{"touchExpression": {"name": "drag", "defaultValue": 320.0, "min": 60.0,
                                 "max": 520.0, "expression": "touchX()"}},
            var("grow", "clamp(0.0, 1.0, (@drag - 60.0) / 460.0)")]
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": 40.0, "top": 130.0, "right": 520.0, "bottom": 410.0}})
    # a deterministic branching network, revealed progressively by @grow
    seed = 20260309
    def nxt():
        nonlocal seed
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        return seed / float(0x7FFFFFFF)
    segs = []
    def branch(x, y, ang, length, depth):
        if depth > 5 or length < 7:
            return
        ex = x + math.cos(ang) * length
        ey = y + math.sin(ang) * length
        segs.append((x, y, ex, ey, depth))
        n = 2 if nxt() > 0.25 else 3
        for _ in range(n):
            branch(ex, ey, ang + (nxt() - 0.5) * 1.5, length * (0.62 + nxt() * 0.22),
                   depth + 1)
    branch(80.0, 270.0, -0.15, 56.0, 0)
    total = len(segs)
    for i, (x0, y0, x1, y1, d) in enumerate(segs):
        frac = i / float(total)
        colour = (GOOD, ACCENT, WARM, HOT, DIM, TEXT)[min(d, 5)]
        cmds.append({"conditionalOperations": {
            "condition": "gt", "v1": "@grow", "v2": round(frac, 4),
            "commands": [
                paint({"color": colour}, {"style": "stroke"},
                      {"width": max(1.0, 3.4 - d * 0.55)}, {"strokeCap": "round"}),
                {"drawLine": {"x1": round(x0, 1), "y1": round(y0, 1),
                              "x2": round(x1, 1), "y2": round(y1, 1)}}]}})
    cmds += text_at("a single spore", 60.0, 300.0, 9.5, DIM)
    cmds += [{"variable": {"name": "pct", "commit": True,
                           "value": {"type": "textFromFloat", "value": "@grow * 100.0",
                                     "whole": 3, "decimal": 0}}},
             paint({"color": TEXT}, {"style": "fill"}, {"textSize": 15.0}),
             {"drawTextAnchored": {"text": "@pct", "x": 40.0, "y": 448.0,
                                   "panX": -1.0, "panY": 0.0, "flags": 0}}]
    cmds += text_at("per cent grown", 86.0, 448.0, 10.5, DIM)
    cmds.append({"conditionalOperations": {
        "condition": "gt", "v1": "@grow", "v2": 0.75,
        "commands": [paint({"color": GOOD}, {"style": "fill"}, {"textSize": 10.5}),
                     {"drawTextAnchored": {
                         "text": "the tips are where everything happens - the old network "
                                 "is plumbing",
                         "x": 200.0, "y": 448.0, "panX": -1.0, "panY": 0.0, "flags": 0}}]}})
    cmds += text_at("A fungus has no mouth. It grows into its food and digests it outside "
                    "itself,", 40.0, 490.0, 11.0, TEXT)
    cmds += text_at("so the body and the feeding apparatus are the same object - which is "
                    "why size has no", 40.0, 508.0, 10.0, DIM)
    cmds += text_at("fixed limit, and the largest known organism on Earth is one of these.",
                    40.0, 524.0, 10.0, DIM)
    title(cmds, W, H, "Growing a mycelium", "drag to let it spread")
    return {"header": header(W, H, "Drag to grow a branching fungal network from a single "
                                   "spore"),
            "root": canvas(cmds, INK)}


# ── 8. BIO-MICR-00027  Protozoa — raster-and-text / analyze / 2D ───────────
# Four protozoa by how they move, with their sizes to scale against a human hair. The scale
# bar is doing the work: these are single cells doing things that look like animal behaviour.
def _wrap(text, n):
    out, line = [], ""
    for w in text.split():
        if len(line) + len(w) + 1 > n:
            out.append(line); line = w
        else:
            line = (line + " " + w).strip()
    if line: out.append(line)
    return out


def protozoa():
    W, H = 600, 480
    KINDS = [("Amoeba", "flows - pushes its own cytoplasm forward", "400", GOOD),
             ("Paramecium", "beats thousands of cilia in waves", "250", ACCENT),
             ("Euglena", "whips one flagellum, and photosynthesises", "100", WARM),
             ("Plasmodium", "glides with no visible organelle at all", "10", HOT)]
    cmds = []
    x = 48.0
    for name, how, size, colour in KINDS:
        w = 128.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x, "top": 130.0, "right": x + w,
                                  "bottom": 300.0}})
        cx, cy = x + w / 2, 206.0
        sz = math.sqrt(float(size)) * 2.4
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        if name == "Amoeba":
            for k in range(7):
                a = k * 2 * math.pi / 7
                r = sz * (0.5 + 0.28 * math.sin(k * 2.1))
                cmds.append({"drawCircle": {"cx": cx + math.cos(a) * r * 0.5,
                                            "cy": cy + math.sin(a) * r * 0.5,
                                            "radius": sz * 0.34}})
        elif name == "Paramecium":
            cmds.append({"drawOval": {"left": cx - sz * 0.6, "top": cy - sz * 0.3,
                                      "right": cx + sz * 0.6, "bottom": cy + sz * 0.3}})
            cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.0}))
            for k in range(22):
                a = k * 2 * math.pi / 22
                cmds.append({"drawLine": {"x1": cx + math.cos(a) * sz * 0.6,
                                          "y1": cy + math.sin(a) * sz * 0.3,
                                          "x2": cx + math.cos(a) * sz * 0.76,
                                          "y2": cy + math.sin(a) * sz * 0.42}})
        elif name == "Euglena":
            cmds.append({"drawOval": {"left": cx - sz * 0.32, "top": cy - sz * 0.62,
                                      "right": cx + sz * 0.32, "bottom": cy + sz * 0.62}})
            cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.6}))
            prev = None
            for k in range(14):
                t = k / 13.0
                px = cx + math.sin(t * 7.0) * 9.0
                py = cy - sz * 0.62 - t * 34.0
                if prev:
                    cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1],
                                              "x2": px, "y2": py}})
                prev = (px, py)
        else:
            cmds.append({"drawOval": {"left": cx - sz * 1.1, "top": cy - sz * 0.42,
                                      "right": cx + sz * 1.1, "bottom": cy + sz * 0.42}})
        cmds += text_at(name, cx, 322.0, 12.0, colour, pan_x=0.0)
        cmds += text_at(size + " um", cx, 340.0, 10.0, TEXT, pan_x=0.0)
        for wi, word in enumerate(_wrap(how, 22)):
            cmds += text_at(word, x + 2, 358.0 + wi * 11.0, 7.5, DIM)
        x += w + 8.0
    # a human hair, to scale
    hair = math.sqrt(70.0) * 2.4
    cmds.append(paint({"color": DIM}, {"style": "stroke"}, {"width": 1.4}))
    cmds.append({"drawLine": {"x1": 48.0, "y1": 392.0, "x2": 48.0 + hair * 2, "y2": 392.0}})
    cmds += text_at("a human hair is about 70 um across, drawn to the same scale",
                    48.0 + hair * 2 + 10, 396.0, 9.5, DIM)
    cmds += text_at("Every one of these is a single cell, and three of the four hunt.",
                    48.0, 418.0, 11.0, TEXT)
    cmds += text_at("- behaviour does not require a nervous system, only a cell with "
                    "something to gain", 48.0, 438.0, 10.0, DIM)
    title(cmds, W, H, "Four ways to move", "single cells, drawn to one scale")
    return {"header": header(W, H, "Four protozoa drawn to a common scale against a human "
                                   "hair, grouped by how they move"),
            "root": canvas(cmds, INK)}


# ── 9. MTH-GEOM-00009  Euclidean geometry — static-diagram / analyze / 2D ──
# The five postulates, four of which are obvious and one of which is not. Drawing the fifth
# alongside the others makes visible why two thousand years of mathematicians tried to prove
# it from the rest, and why failing to was the discovery.
def euclid():
    W, H = 620, 474
    cmds = []
    # Four in a 2x2 block and the fifth alone beside them, which puts the document's claim
    # into the layout: the first four are of a kind and the fifth is not. All five in one
    # row ran the captions into each other and pushed the fifth off the right edge, and the
    # captions are the only thing saying what each drawing is.
    GW, GH, GAP = 152.0, 120.0, 10.0
    GX, GY = 26.0, 100.0
    X5, W5, H5 = 352.0, 242.0, GH * 2 + GAP

    def panel(x0, y0, w, h):
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": y0, "right": x0 + w,
                                  "bottom": y0 + h}})

    def caption(x0, y0, w, h, n, text, colour):
        cmds.extend(text_at(n, x0 + 9, y0 + 23, 15.0, colour))
        cmds.extend(text_at(text, x0 + 9, y0 + h - 11, 8.5, DIM))

    def stroke(colour, width=1.8):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": width},
                          {"strokeCap": "round"}))

    def right_angle(corner, u, v, arm, colour):
        """Two arms and the little square between them. Taking the arm directions as
        vectors is what lets the second one be drawn at 45 degrees - the square mark is
        just the parallelogram on the two arms, which is square exactly when they are
        perpendicular, so it rotates with them and no rotated drawRect is needed."""
        x, y = corner
        stroke(colour)
        for dx, dy in (u, v):
            cmds.append({"drawLine": {"x1": x, "y1": y, "x2": x + dx * arm,
                                      "y2": y + dy * arm}})
        m = 11.0
        rx, ry = x + (u[0] + v[0]) * m, y + (u[1] + v[1]) * m
        cmds.append({"drawLine": {"x1": x + u[0] * m, "y1": y + u[1] * m,
                                  "x2": rx, "y2": ry}})
        cmds.append({"drawLine": {"x1": x + v[0] * m, "y1": y + v[1] * m,
                                  "x2": rx, "y2": ry}})

    POSTS = ["1", "2", "3", "4"]
    TEXTS = {"1": "a line between any two points",
             "2": "a line extends forever",
             "3": "a circle, given centre and radius",
             "4": "all right angles are equal"}
    for i, n in enumerate(POSTS):
        x0 = GX + (i % 2) * (GW + GAP)
        y0 = GY + (i // 2) * (GH + GAP)
        cx, cy = x0 + GW / 2, y0 + 62
        panel(x0, y0, GW, GH)
        stroke(GOOD)
        if n == "1":
            cmds.append({"drawLine": {"x1": cx - 44, "y1": cy + 16, "x2": cx + 44,
                                      "y2": cy - 16}})
            cmds.append(paint({"color": TEXT}, {"style": "fill"}))
            for dx, dy in ((-44, 16), (44, -16)):
                cmds.append({"drawCircle": {"cx": cx + dx, "cy": cy + dy, "radius": 3.5}})
        elif n == "2":
            cmds.append({"drawLine": {"x1": x0 + 16, "y1": cy, "x2": x0 + GW - 16,
                                      "y2": cy}})
            for sx, d in ((x0 + 16, 1), (x0 + GW - 16, -1)):
                cmds.append({"drawLine": {"x1": sx, "y1": cy, "x2": sx + d * 9,
                                          "y2": cy - 6}})
                cmds.append({"drawLine": {"x1": sx, "y1": cy, "x2": sx + d * 9,
                                          "y2": cy + 6}})
        elif n == "3":
            cmds.append({"drawCircle": {"cx": cx, "cy": cy, "radius": 32.0}})
            cmds.append({"drawLine": {"x1": cx, "y1": cy, "x2": cx + 32, "y2": cy}})
            cmds.append(paint({"color": TEXT}, {"style": "fill"}))
            cmds.append({"drawCircle": {"cx": cx, "cy": cy, "radius": 3.0}})
        else:
            # two of them, at different orientations - one right angle on its own cannot
            # show that right angles are equal to each other
            right_angle((cx - 46, cy + 20), (1.0, 0.0), (0.0, -1.0), 32, GOOD)
            right_angle((cx + 26, cy + 22), (0.707, -0.707), (-0.707, -0.707), 32, GOOD)
        caption(x0, y0, GW, GH, n, TEXTS[n], GOOD)

    # the fifth, given the whole right-hand side to itself
    panel(X5, GY, W5, H5)
    cx5 = X5 + W5 / 2
    yl, yp = GY + 168, GY + 96
    stroke(DIM, 1.2)
    for tx in (X5 + 36, X5 + 206):      # other lines through P all meet the line below
        cmds.append({"drawLine": {"x1": cx5, "y1": yp, "x2": tx, "y2": yl + 22}})
    stroke(HOT)
    cmds.append({"drawLine": {"x1": X5 + 22, "y1": yl, "x2": X5 + W5 - 22, "y2": yl}})
    cmds.append({"drawLine": {"x1": X5 + 22, "y1": yp, "x2": X5 + W5 - 22, "y2": yp}})
    cmds.append(paint({"color": TEXT}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": cx5, "cy": yp, "radius": 4.0}})
    cmds += text_at("P", cx5 + 9, yp - 7, 10.0, TEXT)
    cmds += text_at("every other line through P meets it", X5 + 9, yl + 44, 8.5, DIM)
    caption(X5, GY, W5, H5, "5", "through a point, exactly one parallel", HOT)

    body = GY + H5 + 36
    cmds += text_at("The fifth is the odd one. It is longer, less obvious, and for two "
                    "thousand years people tried", 26.0, body, 11.0, TEXT)
    cmds += text_at("to derive it from the other four. They could not - and the reason is "
                    "that it is a choice.", 26.0, body + 18, 11.0, TEXT)
    cmds += text_at("Deny it and you do not get a contradiction. You get a different "
                    "geometry, and the surface of", 26.0, body + 44, 10.0, DIM)
    cmds += text_at("a sphere is one: there, every pair of 'parallels' meets, and a "
                    "triangle's angles exceed 180.", 26.0, body + 60, 10.0, DIM)
    title(cmds, W, H, "Five postulates", "four are obvious; the fifth is a decision")
    return {"header": header(W, H, "Euclid's five postulates drawn as diagrams, with the "
                                   "parallel postulate set apart"),
            "root": canvas(cmds, INK)}


# ── 10. CSC-DS-00009  Graphs — annotated-layout / explain / 2D ─────────────
# The same seven nodes under four readings. A graph is not a picture; the picture is one of
# many, and the only things that are real are the vertices and the edges.
def graphs():
    W, H = 540, 502
    # The seven nodes carry a Hamiltonian cycle, and that is what makes the document work.
    # The first edge set had no such cycle, so the "ring" was seven dots sitting on a circle
    # with chords slashing over the middle, and a reader had to take the ring on faith. With
    # a cycle each layout can genuinely be the shape it claims to be: the cycle walks the
    # perimeter, snakes along the grid rows, hangs as tree branches, runs down the line.
    # Nine edges either way - the seven cycle edges plus two chords.
    CYCLE = [(i, (i + 1) % 7) for i in range(7)]
    CHORDS = [(1, 4), (2, 6)]
    EDGES = CYCLE + CHORDS
    PW, PH = 236, 150
    ox, oy = PW / 2.0, PH / 2.0
    LAYOUTS = {
        # -pi/2 puts node 0 at twelve o'clock, so the cycle reads clockwise from the top
        "circle": [(math.cos(i * 2 * math.pi / 7 - math.pi / 2) * 56,
                    math.sin(i * 2 * math.pi / 7 - math.pi / 2) * 56) for i in range(7)],
        # snake order: the cycle runs along the rows and back, so the only diagonals in the
        # picture are the two chords
        "grid": [(-66, -32), (-22, -32), (22, -32), (66, -32),
                 (44, 32), (0, 32), (-48, 32)],
        # Breadth-first from node 0 - a root the graph does not have. One row per depth,
        # and each node placed under the parent that reached it, so all six tree edges run
        # strictly downward and the branching is the thing the eye picks up. Laying it out
        # by hand around the cycle instead made the perimeter the dominant shape and the
        # panel came out looking like the ring again.
        #   depth 0: 0        depth 1: 1, 6        depth 2: 2, 4, 5        depth 3: 3
        # Three edges are left over - 2-6, 3-4, 4-5 - because a tree on seven nodes has six
        # and this graph has nine. Those three are the crossings, and they are the evidence
        # that the root was never there.
        "tree": [(0, -58), (-40, -20), (-72, 18), (-72, 56),
                 (-20, 18), (46, 18), (46, -20)],
        "line": [(-66 + i * 22, 0) for i in range(7)],
    }

    def arc(c, xa, xb, above):
        """A semicircle spanning xa..xb on the centre line. 180/+180 is the upper half:
        angle 0 is three o'clock and sweep runs clockwise with y pointing down."""
        r = abs(xb - xa) / 2.0
        c.append({"drawArc": {"left": min(xa, xb), "top": oy - r,
                              "right": max(xa, xb), "bottom": oy + r,
                              "startAngle": 180.0 if above else 0.0,
                              "sweepAngle": 180.0}})

    def panel(key, colour):
        pts = LAYOUTS[key]
        c = [{"clipRect": {"left": 0, "top": 0, "right": PW, "bottom": PH}},
             paint({"color": RULE}, {"style": "fill"}),
             {"drawRect": {"left": 0, "top": 0, "right": PW, "bottom": PH}},
             paint({"color": DIM}, {"style": "stroke"}, {"width": 1.3})]
        if key == "line":
            # An arc diagram. With every node on one line a straight edge between distant
            # nodes would be drawn straight through the nodes between them; as semicircles
            # each edge stays clear of the ones it does not touch, and the reading order
            # survives. Short cycle hops bulge below, the long jumps arch above.
            for a, b in EDGES:
                arc(c, ox + pts[a][0], ox + pts[b][0], abs(a - b) != 1)
        else:
            for a, b in EDGES:
                c.append({"drawLine": {"x1": ox + pts[a][0], "y1": oy + pts[a][1],
                                       "x2": ox + pts[b][0], "y2": oy + pts[b][1]}})
        c.append(paint({"color": colour}, {"style": "fill"}))
        for px, py in pts:
            c.append({"drawCircle": {"cx": ox + px, "cy": oy + py, "radius": 7.5}})
        return {"type": "canvas", "modifiers": [{"width": PW}, {"height": PH}],
                "commands": c}
    CARDS = [("circle", "Drawn as a ring", "no node is special", GOOD),
             ("grid", "Drawn as a grid", "looks like a map; it is not one", ACCENT),
             ("tree", "Drawn as a tree", "suggests a root that does not exist", WARM),
             ("line", "Drawn as a line", "suggests an order that does not exist", HOT)]
    rows = []
    for key, name, note, colour in CARDS:
        rows.append({"type": "column",
                     "modifiers": [{"width": 252}, {"padding": 8}, {"background": PANEL}],
                     "children": [
                         panel(key, colour),
                         {"type": "spacer", "modifiers": [{"height": 6}]},
                         {"type": "text", "value": name, "modifiers": [],
                          "fontSize": 12.0, "color": colour},
                         {"type": "text", "value": note, "modifiers": [],
                          "fontSize": 9.0, "color": DIM}]})
    return {"header": header(W, H, "One graph drawn four ways, showing that the layout "
                                   "carries meaning the graph does not"),
            "root": {"type": "column",
                     "modifiers": ["fillMaxSize", {"padding": 16}, {"background": INK}],
                     "children": [
                         {"type": "text", "value": "One graph, four drawings",
                          "modifiers": [], "fontSize": 19.0, "color": TEXT},
                         {"type": "spacer", "modifiers": [{"height": 3}]},
                         {"type": "text",
                          "value": "same seven nodes, same nine edges, every time",
                          "modifiers": [], "fontSize": 11.0, "color": DIM},
                         {"type": "spacer", "modifiers": [{"height": 12}]},
                         {"type": "flow", "modifiers": [{"width": 508}], "children": rows},
                         {"type": "spacer", "modifiers": [{"height": 14}]},
                         {"type": "text",
                          "value": "Only the vertices and the edges are the graph. "
                                   "Everything else - the ring, the rows, the apparent root "
                                   "- is something the drawing added, and a reader will "
                                   "believe it unless told otherwise.",
                          "modifiers": [], "fontSize": 10.5, "color": TEXT}]}}


# ── 11. CHM-CR-00009  Reaction mechanisms — data-plot / explore / 2D ───────
# An energy profile with two steps, showing which one actually sets the rate. The tall
# barrier is the whole mechanism as far as kinetics is concerned, and the intermediate in
# the dip is the thing textbooks draw and nobody ever isolates.
def mechanisms():
    W, H = 580, 480
    cmds = []
    px0, px1, py0, py1 = 60.0, 540.0, 140.0, 350.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    def E(u):
        a = 1.00 * math.exp(-((u - 0.26) / 0.085) ** 2)
        b = 0.55 * math.exp(-((u - 0.70) / 0.085) ** 2)
        base = 0.30 * (1 - u) + 0.04
        return base + a + b - 0.22 * math.exp(-((u - 0.48) / 0.07) ** 2)
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 2.6},
                      {"strokeCap": "round"}))
    prev = None
    for i in range(97):
        u = i / 96.0
        pt = (px0 + (px1 - px0) * u, py1 - E(u) * 150.0)
        if prev:
            cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": pt[0], "y2": pt[1]}})
        prev = pt
    MARKS = [(0.02, "reactants", GOOD, 0),
             (0.26, "transition state 1", HOT, -16),
             (0.48, "intermediate", WARM, 16),
             (0.70, "transition state 2", ACCENT, -16),
             (0.98, "products", GOOD, 0)]
    for u, lbl, colour, dy in MARKS:
        x = px0 + (px1 - px0) * u
        y = py1 - E(u) * 150.0
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": x, "cy": y, "radius": 4.5}})
        cmds += text_at(lbl, x, y + dy - 6, 9.0, colour, pan_x=0.0)
    # the rate-determining barrier, measured
    cmds.append(paint({"color": HOT}, {"style": "stroke"}, {"width": 1.2}))
    x1 = px0 + (px1 - px0) * 0.26
    cmds.append({"drawLine": {"x1": x1 - 60, "y1": py1 - E(0.02) * 150.0,
                              "x2": x1 - 60, "y2": py1 - E(0.26) * 150.0}})
    cmds += text_at("this barrier", x1 - 118, (py1 - E(0.14) * 150.0), 10.0, HOT)
    cmds += text_at("sets the rate", x1 - 118, (py1 - E(0.14) * 150.0) + 15, 10.0, HOT)
    cmds += text_at("energy", px0, py0 - 12, 10.5, DIM)
    cmds += text_at("reaction coordinate", (px0 + px1) / 2, py1 + 22, 10.0, DIM, pan_x=0.0)
    cmds += text_at("The second step is faster, so it is invisible in the rate law.",
                    60.0, 394.0, 11.0, TEXT)
    cmds += text_at("- a mechanism with two steps can look like a one-step reaction from "
                    "the outside, and usually does", 60.0, 412.0, 10.0, DIM)
    cmds += text_at("The intermediate in the dip is real but short-lived: too unstable to "
                    "bottle, too stable to ignore.", 60.0, 436.0, 10.0, DIM)
    title(cmds, W, H, "A two-step mechanism", "only the tallest barrier matters")
    return {"header": header(W, H, "A two-step reaction energy profile with the rate-"
                                   "determining barrier marked"),
            "root": canvas(cmds, INK)}


# ── 12. EAR-GEOP-00009  Magnetic field — path-form / compare / 3D ──────────
# Field lines as ribbons around a tilted dipole. 3D earns it: the field is a volume, the
# tilt between magnetic and rotational poles is a three-dimensional fact, and ribbons mean
# the far side of each loop vanishes instead of cluttering the near side.
def magnetic_field():
    W, H = 520, 620
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.66,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          # Pulled back until the field lines stay on the page. The scene
                          # turns on the clock, so the overflow moves with the rotation and
                          # a single frame proves nothing: 1.25x looked clean over 8 sampled
                          # frames and still crossed the edge by 88px somewhere in the turn.
                          # 1.65x is the first distance clean across 24 samples of the 28.6s
                          # revolution.
                          "eye": [3.135, 1.485, 6.6], "center": [0.0, 0.30, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.35, -0.45, -0.82], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.3, 0.45], "intensity": 0.40}]}}]
    cmds.append(var("spin", "continuousSec() * 0.22"))
    TILT = math.radians(11.0)
    cmds.append({"meshPrimitive3D": {"id": 1, "primitive": "sphere", "segments": 26,
                                     "radius": 0.42, "center": [0, 0, 0]}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             {"matrix3D": {"op": "translate", "x": 0.0, "y": 0.30, "z": 0.0}},
             paint({"color": RULE}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]
    # dipole field lines, as ribbons so the far half culls
    # A dipole line is not on a sphere, so surface_ribbon cannot build it - that helper
    # normalises every point to one radius, which collapsed these to a single arc. The strip
    # is assembled here from the real r = L sin^2(theta) points, with the outward direction
    # taken from each point itself so the far half still culls.
    def field_ribbon(mesh_id, pts, half_w):
        verts, normals, uv, idx = [], [], [], []
        for i in range(len(pts) - 1):
            A, B = pts[i], pts[i + 1]
            rA = math.sqrt(sum(c * c for c in A)) or 1.0
            out = [c / rA for c in A]
            t = [B[k] - A[k] for k in range(3)]
            tl = math.sqrt(sum(c * c for c in t)) or 1.0
            t = [c / tl for c in t]
            sv = [out[1] * t[2] - out[2] * t[1], out[2] * t[0] - out[0] * t[2],
                  out[0] * t[1] - out[1] * t[0]]
            sl = math.sqrt(sum(c * c for c in sv)) or 1.0
            sv = [c / sl * half_w for c in sv]
            quad = [[A[k] - sv[k] for k in range(3)], [A[k] + sv[k] for k in range(3)],
                    [B[k] + sv[k] for k in range(3)], [B[k] - sv[k] for k in range(3)]]
            base = len(verts) // 3
            for q in quad:
                verts += [round(q[0], 5), round(q[1], 5), round(q[2], 5)]
                normals += [round(out[0], 5), round(out[1], 5), round(out[2], 5)]
                uv += [0.0, 0.0]
            idx += [base, base + 2, base + 1, base, base + 3, base + 2]
        return {"defineMesh3D": {"id": mesh_id, "verts": verts, "normals": normals,
                                 "uv": uv, "indices": idx}}

    mid = 10
    for li, L in enumerate((0.75, 1.05, 1.45, 1.95)):
        for phi in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
            pts = []
            for k in range(61):
                th = math.pi * (0.02 + 0.96 * k / 60.0)
                r = L * math.sin(th) ** 2
                if r < 0.44:
                    continue
                xr = r * math.sin(th)
                yr = r * math.cos(th)
                x2 = xr * math.cos(TILT) - yr * math.sin(TILT)
                y2 = xr * math.sin(TILT) + yr * math.cos(TILT)
                pts.append((x2 * math.cos(phi), y2, x2 * math.sin(phi)))
            if len(pts) < 3:
                continue
            colour = (ACCENT, GOOD, WARM, HOT)[li]
            cmds.append(field_ribbon(mid, pts, 0.012))
            cmds += [{"matrix3D": {"op": "identity"}},
                     {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                     {"matrix3D": {"op": "translate", "x": 0.0, "y": 0.30, "z": 0.0}},
                     paint({"color": colour}, {"style": "fill"}),
                     {"drawMesh3D": {"mesh": mid, "mode": "software-flat"}}]
            mid += 1
    cmds += text_at("geographic north", 262.0, 92.0, 9.5, DIM, pan_x=0.0)
    cmds += text_at("magnetic north sits about 11 degrees off it", 262.0, 420.0, 9.5, WARM,
                    pan_x=0.0)
    y = 462.0
    for name, note, colour in (
            ("It is a dipole, roughly", "two poles, like a bar magnet - but only roughly, "
             "and only for now", ACCENT),
            ("It reverses", "hundreds of times in the rock record, at no fixed interval", HOT),
            ("It is why there is air", "the field turns the solar wind aside; Mars lost its "
             "field and then its atmosphere", GOOD)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 36.0, "top": y - 9, "right": 41.0, "bottom": y + 5}})
        cmds += text_at(name, 52.0, y, 11.0, colour)
        cmds += text_at(note, 52.0, y + 15, 9.0, DIM)
        y += 40.0
    title(cmds, W, H, "The geomagnetic field", "a tilted dipole, turning with the planet")
    return {"header": header(W, H, "Dipole field lines as ribbons around a tilted magnetic "
                                   "axis, with the Earth turning beneath"),
            "root": canvas(cmds, INK)}


# ── 13. ENG-EE-00009  Digital logic — expression-animation / demonstrate ───
# A full adder with its signals running. The carry chain is the point: the top bit cannot
# settle until every bit below it has, which is the reason adders are the thing CPU
# designers spend their cleverness on.
def digital_logic():
    W, H = 600, 450
    BITS = 4
    A, B = 0b1011, 0b0111
    TOTAL = A + B

    # Each stage gets two half-beats: it reads its two input bits and the carry arriving
    # from the right, then it writes its sum bit and the carry leaving to the left. One
    # variable carries both, because floor(t * 2) numbers the half-beats directly: stage p
    # reads on half-beat 2p and writes on 2p+1. A fifth beat holds the finished sum before
    # the cycle restarts, which is the only part of it a still frame can show.
    cmds = [var("t", "continuousSec() * 0.8 - floor(continuousSec() * 0.8 / 5.0) * 5.0"),
            var("ph", "floor(@t * 2.0)")]

    x0, bw, boxw = 56.0, 116.0, 104.0
    y0 = 158.0
    WIRE = y0 + 116            # the carry runs on its own line under the stages
    bx, bh = 24.0, 24.0        # bit box inset within a stage, and its height
    bitw = 56.0

    def flash(phase, lo, hi, box_top, colour):
        """An outline that appears for one half-beat. Drawn over the resting box rather
        than replacing it, so the digit underneath is never disturbed."""
        return {"conditionalOperations": {
            "condition": "eq", "v1": "@ph", "v2": float(phase),
            "commands": [paint({"color": colour}, {"style": "stroke"}, {"width": 2.6}),
                         {"drawRect": {"left": lo - 3, "top": box_top - 3, "right": hi + 3,
                                       "bottom": box_top + bh + 3}}]}}

    for i in range(BITS):
        col = BITS - 1 - i     # leftmost column on screen is the most significant bit
        p = col                # ...and the carry reaches it last, after `col` stages
        x = x0 + i * bw
        lo, hi = x + bx, x + bx + bitw
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x, "top": y0 - 4, "right": x + boxw,
                                  "bottom": y0 + 96}})
        cmds += text_at("bit %d" % col, x + 2, y0 - 12, 9.0, DIM)

        a, b = (A >> col) & 1, (B >> col) & 1
        s = (TOTAL >> col) & 1
        rows = [(y0 + 4, "%d" % a, GOOD), (y0 + 32, "%d" % b, ACCENT)]
        for top, digit, colour in rows:
            cmds.append(paint({"color": RULE}, {"style": "fill"}))
            cmds.append({"drawRect": {"left": lo, "top": top, "right": hi,
                                      "bottom": top + bh}})
            cmds += text_at(digit, (lo + hi) / 2, top + bh / 2 + 5, 15.0, colour, pan_x=0.0)
            cmds.append(flash(2 * p, lo, hi, top, TEXT))

        # the sum box is empty until this stage writes it, and stays written afterwards
        stop = y0 + 60
        cmds.append(paint({"color": RULE}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": lo, "top": stop, "right": hi,
                                  "bottom": stop + bh}})
        cmds.append({"conditionalOperations": {
            "condition": "ge", "v1": "@ph", "v2": float(2 * p + 1),
            "commands": text_at("%d" % s, (lo + hi) / 2, stop + bh / 2 + 5, 15.0,
                                WARM, pan_x=0.0)}})
        cmds.append(flash(2 * p + 1, lo, hi, stop, HOT))

    cmds += text_at("A", 46.0, y0 + 20, 11.0, GOOD, pan_x=1.0)
    cmds += text_at("B", 46.0, y0 + 48, 11.0, ACCENT, pan_x=1.0)
    cmds += text_at("sum", 46.0, y0 + 76, 11.0, WARM, pan_x=1.0)

    # The carry travels right to left, which is the direction the old drawing had backwards.
    # Segment p leaves stage p once stage p has written, so the lit length of this wire is
    # exactly how far the answer can be trusted.
    centre = [x0 + i * bw + boxw / 2 for i in range(BITS)]
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 2.0}))
    cmds.append({"drawLine": {"x1": 30.0, "y1": WIRE, "x2": 556.0, "y2": WIRE}})
    cmds += text_at("carry in 0", 560.0, WIRE + 4, 9.0, DIM)
    hops = [(centre[3], centre[2]), (centre[2], centre[1]),
            (centre[1], centre[0]), (centre[0], 32.0)]
    for p, (xa, xb) in enumerate(hops):
        cmds.append({"conditionalOperations": {
            "condition": "ge", "v1": "@ph", "v2": float(2 * p + 1),
            "commands": [
                paint({"color": HOT}, {"style": "stroke"}, {"width": 2.8},
                      {"strokeCap": "round"}),
                {"drawLine": {"x1": xa, "y1": WIRE, "x2": xb, "y2": WIRE}},
                {"drawLine": {"x1": xb, "y1": WIRE, "x2": xb + 7, "y2": WIRE - 5}},
                {"drawLine": {"x1": xb, "y1": WIRE, "x2": xb + 7, "y2": WIRE + 5}},
                paint({"color": HOT}, {"style": "fill"}, {"textSize": 10.0}),
                {"drawTextAnchored": {"text": "1", "x": (xa + xb) / 2, "y": WIRE - 7,
                                      "panX": 0.0, "panY": 0.0, "flags": 0}}]}})
    cmds += text_at("carry out", 26.0, WIRE + 20, 9.0, HOT)

    # The legend names the two flashes, since a still frame of this document shows neither.
    # Stacked rather than side by side: in one row the first gloss ran under the second
    # swatch, and the glosses are the part that has to be readable.
    for ly, colour, word, gloss in [
            (76.0, TEXT, "read", "takes its two bits and the carry arriving from the right"),
            (102.0, HOT, "write", "puts out its sum bit and a carry leaving to the left")]:
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.0}))
        cmds.append({"drawRect": {"left": 56.0, "top": ly, "right": 76.0,
                                  "bottom": ly + 18}})
        cmds += text_at(word, 84.0, ly + 13, 11.0, colour)
        cmds += text_at(gloss, 130.0, ly + 13, 9.5, DIM)

    cmds += text_at("The carry has to walk from the right-hand end to the left before the "
                    "answer is correct.", 56.0, 322.0, 11.0, TEXT)
    cmds += text_at("- that walk is why a 64-bit add is not 64 times a 1-bit add, and why "
                    "real adders predict the", 56.0, 342.0, 10.0, DIM)
    cmds += text_at("carries in parallel instead of waiting for them. The trick costs gates "
                    "and buys depth.", 56.0, 358.0, 10.0, DIM)
    cmds += text_at("1011 + 0111 = 10010", 56.0, 396.0, 13.0, TEXT)
    cmds += text_at("11 + 7 = 18", 266.0, 396.0, 11.0, DIM)
    title(cmds, W, H, "A ripple-carry adder", "each box is one bit; it flashes when it is "
                                              "read, and again when it is written")
    return {"header": header(W, H, "A four-bit ripple-carry adder drawn as bit cells that "
                                   "flash as each stage reads its inputs and writes its "
                                   "sum"),
            "root": canvas(cmds, INK)}


# ── 14. FIN-CF-00008  Capital structure — particle-system / simulate / 2D ──
# Cash arriving and being claimed, as particles. Debt holders are paid first and in a fixed
# amount; equity gets what is left. Running it as a stream makes the asymmetry visible:
# the debt bucket fills to the same line every time, and all the variance lands on equity.
def capital_structure():
    W, H = 540, 580
    cmds = []
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": 40.0, "top": 130.0, "right": 500.0, "bottom": 290.0}})
    cmds += text_at("cash coming in, quarter by quarter", 270.0, 150.0, 10.0, DIM, pan_x=0.0)
    cmds.append({"createParticles": {
        "id": "cash", "count": 90,
        "variables": ["cx", "cy", "sp", "ph"],
        "initialValues": ["60 + rand() * 420", "140 + rand() * 130",
                          "0.5 + rand() * 1.4", "rand() * 6.28"]}})
    cmds.append(paint({"color": GOOD}, {"style": "fill"}))
    cmds.append({"particlesLoop": {
        "system": "@cash",
        "equations": ["cx", "140 + ((cy - 140 + sp) % 130)", "sp", "ph"],
        "commands": [{"drawCircle": {"cx": "@cx", "cy": "@cy", "radius": 2.4}}]}})
    cmds.append(var("swing", "0.5 + 0.42 * sin(continuousSec() * 0.5)"))
    for i, (name, note, colour) in enumerate(
            (("Debt", "paid first, and the same amount whatever happens", ACCENT),
             ("Equity", "paid last, and gets every bit of the variation", HOT))):
        x0 = 56.0 + i * 236.0
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 2.0}))
        cmds.append({"drawLine": {"x1": x0, "y1": 320.0, "x2": x0, "y2": 440.0}})
        cmds.append({"drawLine": {"x1": x0 + 200, "y1": 320.0, "x2": x0 + 200, "y2": 440.0}})
        cmds.append({"drawLine": {"x1": x0, "y1": 440.0, "x2": x0 + 200, "y2": 440.0}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        if i == 0:
            cmds.append({"drawRect": {"left": x0 + 3, "top": 440.0 - 62.0,
                                      "right": x0 + 197, "bottom": 438.0}})
        else:
            cmds.append({"drawRect": {"left": x0 + 3, "top": "438.0 - 112.0 * @swing",
                                      "right": x0 + 197, "bottom": 438.0}})
        cmds += text_at(name, x0 + 100, 464.0, 13.0, colour, pan_x=0.0)
        cmds += text_at(note, x0 + 100, 482.0, 8.5, DIM, pan_x=0.0)
    cmds += text_at("Leverage does not create value. It moves the variation off the debt "
                    "and onto the equity,", 40.0, 518.0, 11.0, TEXT)
    cmds += text_at("which is why a leveraged firm's shares swing more than its business "
                    "does - and why, in a bad", 40.0, 536.0, 10.0, DIM)
    cmds += text_at("quarter, the equity bucket is the one that empties.", 40.0, 552.0,
                    10.0, DIM)
    title(cmds, W, H, "Who gets paid first", "the same stream, two claims on it")
    return {"header": header(W, H, "Cash arriving as particles and being claimed by debt at "
                                   "a fixed level and equity with all the variation"),
            "root": canvas(cmds, INK)}


# ── 15. FIN-ACCO-00009  Income statement — interactive / analyze / 2D ──────
# Drag down the statement and watch what survives each deduction. The point is that "profit"
# is five different numbers depending where you stop, and arguments about profitability are
# usually arguments about which line someone means.
def income_statement():
    W, H = 560, 580
    LINES = [("Revenue", 1000, GOOD, "what customers paid"),
             ("Cost of goods sold", -610, HOT, "what the product itself cost"),
             ("Gross profit", 390, GOOD, "the first number anyone calls profit"),
             ("Operating expenses", -230, HOT, "salaries, rent, marketing"),
             ("Operating profit", 160, ACCENT, "EBIT - the business, before financing"),
             ("Interest", -45, HOT, "the cost of the debt"),
             ("Tax", -29, HOT, "on what is left"),
             ("Net profit", 86, WARM, "the last line, and the smallest")]
    cmds = [{"touchExpression": {"name": "drag", "defaultValue": 70.0, "min": 60.0,
                                 "max": 520.0, "expression": "touchX()"}},
            var("sel", "clamp(0.0, %d.0, floor((@drag - 60.0) / 460.0 * %d.0))"
                       % (len(LINES) - 1, float(len(LINES))))]
    y = 150.0
    for i, (name, amt, colour, note) in enumerate(LINES):
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 40.0, "top": y - 13, "right": 520.0,
                                  "bottom": y + 13}})
        w = abs(amt) / 1000.0 * 300.0
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 210.0, "top": y - 9,
                                  "right": 210.0 + w, "bottom": y + 9}})
        cmds += text_at(name, 48.0, y + 4, 10.5, colour)
        cmds += text_at("%+d" % amt, 200.0, y + 4, 10.5, TEXT, pan_x=1.0)
        cmds.append({"conditionalOperations": {
            "condition": "eq", "v1": "@sel", "v2": float(i),
            "commands": [paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.6}),
                         {"drawRect": {"left": 38.0, "top": y - 15, "right": 522.0,
                                       "bottom": y + 15}}]}})
        y += 34.0
    for i, (name, amt, colour, note) in enumerate(LINES):
        cmds.append({"conditionalOperations": {
            "condition": "eq", "v1": "@sel", "v2": float(i),
            "commands": [paint({"color": DIM}, {"style": "fill"}, {"textSize": 11.0}),
                         {"drawTextAnchored": {"text": note, "x": 40.0, "y": 448.0,
                                               "panX": -1.0, "panY": 0.0, "flags": 0}}]}})
    cmds += text_at("Five of these eight lines get called 'profit' by somebody.",
                    40.0, 486.0, 11.0, TEXT)
    cmds += text_at("- a company can have a healthy gross margin and still lose money, and "
                    "most arguments about", 40.0, 506.0, 10.0, DIM)
    cmds += text_at("whether a business is profitable are really arguments about which line "
                    "is meant.", 40.0, 522.0, 10.0, DIM)
    cmds += text_at("drag to move down the statement", 40.0, 552.0, 9.5, DIM)
    title(cmds, W, H, "Where the money goes", "one thousand in, eighty-six out")
    return {"header": header(W, H, "An income statement as proportional bars, draggable "
                                   "line by line from revenue to net profit"),
            "root": canvas(cmds, INK)}


# ── 16. FIN-ACCO-00010  Balance sheet — raster-and-text / explain / 2D ─────
# Assets on one side, claims on the other, drawn so the two columns are literally the same
# height. The identity is not a rule to remember; it is what a balance sheet is.
def balance_sheet():
    W, H = 560, 540
    ASSETS = [("Cash", 120, GOOD), ("Receivables", 180, GOOD),
              ("Inventory", 150, ACCENT), ("Property and plant", 450, ACCENT),
              ("Goodwill", 100, WARM)]
    CLAIMS = [("Payables", 140, HOT), ("Short-term debt", 90, HOT),
              ("Long-term debt", 420, HOT), ("Equity", 350, WARM)]
    total = sum(v for _, v, _ in ASSETS)
    assert total == sum(v for _, v, _ in CLAIMS), "the two sides must balance"
    cmds = []
    top, bot = 150.0, 420.0
    for side, items, x0, x1, label in (("A", ASSETS, 60.0, 260.0, "What it owns"),
                                       ("C", CLAIMS, 300.0, 500.0, "Who has a claim on it")):
        cmds += text_at(label, (x0 + x1) / 2, 138.0, 12.0, TEXT, pan_x=0.0)
        y = top
        for name, v, colour in items:
            h = (bot - top) * v / float(total)
            cmds.append(paint({"color": colour}, {"style": "fill"}))
            cmds.append({"drawRect": {"left": x0, "top": y, "right": x1, "bottom": y + h - 2}})
            if h > 22:
                cmds += text_at(name, x0 + 8, y + h / 2 + 4, 9.5, INK)
                cmds += text_at("%d" % v, x1 - 8, y + h / 2 + 4, 9.5, INK, pan_x=1.0)
            y += h
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.2}))
    cmds.append({"drawLine": {"x1": 60.0, "y1": top - 6, "x2": 500.0, "y2": top - 6}})
    cmds.append({"drawLine": {"x1": 60.0, "y1": bot + 6, "x2": 500.0, "y2": bot + 6}})
    cmds += text_at("1000", 280.0, top - 12, 11.0, TEXT, pan_x=0.0)
    cmds += text_at("1000", 280.0, bot + 22, 11.0, TEXT, pan_x=0.0)
    cmds += text_at("The two columns are the same height because they are the same money, "
                    "counted twice:", 60.0, 462.0, 11.0, TEXT)
    cmds += text_at("once by what it was spent on, once by where it came from. That is the "
                    "whole identity.", 60.0, 480.0, 10.5, DIM)
    cmds += text_at("Goodwill is the one entry with no physical referent - it is the premium "
                    "paid over book value", 60.0, 506.0, 9.5, DIM)
    cmds += text_at("in some past acquisition, and it is the first thing to be written off "
                    "when things go wrong.", 60.0, 522.0, 9.5, DIM)
    title(cmds, W, H, "Two columns, one height", "assets equal claims, by construction")
    return {"header": header(W, H, "A balance sheet as two stacked columns of equal height, "
                                   "assets against the claims on them"),
            "root": canvas(cmds, INK)}


# ── build ──────────────────────────────────────────────────────────────────────
BUILD = [("PHY-QM-00027", quantum_fields), ("PHY-CM-00028", forces),
         ("PHY-CM-00029", motion), ("PHY-CM-00030", momentum),
         ("BIO-MICR-00024", bacteria), ("BIO-MICR-00025", viruses),
         ("BIO-MICR-00026", fungi), ("BIO-MICR-00027", protozoa),
         ("MTH-GEOM-00009", euclid), ("CSC-DS-00009", graphs),
         ("CHM-CR-00009", mechanisms), ("EAR-GEOP-00009", magnetic_field),
         ("ENG-EE-00009", digital_logic), ("FIN-CF-00008", capital_structure),
         ("FIN-ACCO-00009", income_statement), ("FIN-ACCO-00010", balance_sheet)]

if __name__ == "__main__":
    for doc_id, fn in BUILD:
        name = use(doc_id)
        d = fn()
        (OUT / ("%s.json" % doc_id)).write_text(json.dumps(d, indent=1) + "\n")
        print("  %-16s %-9s %s" % (doc_id, name, d["header"]["contentDescription"][:46]))
    print("  %d documents" % len(BUILD))
