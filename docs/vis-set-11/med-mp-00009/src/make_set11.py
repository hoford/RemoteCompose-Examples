#!/usr/bin/env python3
"""Build set 11 of the visualization programme: 16 documents.

    python3 work/set-11/make_set11.py

Work order from `python3 tools/visplan.py set 11`.

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

    Emits uv = (u, 1 - v). Plain u; v inverted only because a bitmap's first row is its top
    while v = 0 is the south pole. Map v = 0 to the north pole instead and the world is
    upside down - Africa inverted, Antarctica over the Arctic - which is obvious the moment
    the texture is a map.

    **meshPrimitive3D would also do this**, and would halve the document, since the vertices
    are built on the player instead of shipped: 50.7 KB against 97.5 KB for the trade globe.
    Two things to know before reaching for it, both measured rather than assumed:

      uv defaults to "none".  {"primitive": "sphere"} with no "uv": "uv" produces a sphere
         with no texture coordinates at all. The texture still binds, the mesh still draws,
         and you get a plain white ball with nothing to say why (F-010).

      its convention is rotated 90 degrees from this one, NOT mirrored.  The primitive
         measures its angle from +x and reverses u; this measures from +z and leaves u
         alone. The two reversals cancel, so east still runs to screen-right on the near
         face and neither map is a mirror image. What is left is where the angle starts.
         Insert a +pi/2 rotation about y and the two spheres agree to a mean absolute
         difference of 0.32 of 255 - the residue is tessellation, not orientation. At
         -pi/2 it is 13.55, unrotated 15.82.

    So either mesh will show the Earth correctly. What cannot differ is the convention used
    by the mesh and the convention used to place things on it: latlon() below is built from
    this one, and against the primitive every pin would sit 90 degrees of longitude east.

    (An earlier version of this note claimed the primitive mirrors the map east-west, and
    that mapping u with increasing longitude does the same. Both were wrong; the rendering
    above is what settled it.)
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


# ── 1. PHY-CM-00035  Gyroscopes — static-diagram / compare / 3D ────────────
# A spinning wheel that refuses to fall, with the torque and the resulting precession drawn
# as what they are: two vectors at right angles. The counter-intuitive part is that the
# response is perpendicular to the push, and only 3D shows that honestly.
def gyroscopes():
    W, H = 520, 620
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.72,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [2.3, 1.5, 3.2], "center": [0.0, 0.10, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.42, -0.5, -0.76], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.3, 0.45], "intensity": 0.42}]}}]
    cmds.append(var("prec", "continuousSec() * 0.6"))
    cmds.append(var("spin", "continuousSec() * 7.0"))
    # the wheel, as a ring of boxes, spinning fast about its own axle
    verts, normals, uv, idx = [], [], [], []
    for k in range(28):
        a = k * 2 * math.pi / 28
        mid = (math.cos(a) * 0.55, math.sin(a) * 0.55, 0.0)
        ax = (-math.sin(a), math.cos(a), 0.0)
        oriented_box(verts, normals, uv, idx, mid, ax, 0.062, 0.045, 0.045)
    cmds.append({"defineMesh3D": {"id": 1, "verts": [round(v,5) for v in verts],
                                  "normals": normals, "uv": uv, "indices": idx}})
    v2, n2, u2, i2 = [], [], [], []
    oriented_box(v2, n2, u2, i2, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.62, 0.035, 0.035)
    cmds.append({"defineMesh3D": {"id": 2, "verts": [round(v,5) for v in v2],
                                  "normals": n2, "uv": u2, "indices": i2}})
    for mid, colour in ((1, ACCENT), (2, DIM)):
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@prec", "axis": [0, 1, 0]}},
                 {"matrix3D": {"op": "rotate", "angle": 0.42, "axis": [1, 0, 0]}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mid, "mode": "software-smooth"}}]
    # gravity, and the precession it causes - drawn as arrows, not described
    for vec, colour, mid2 in (((0.0, -1.0, 0.0), HOT, 4), ((1.0, 0.0, 0.0), GOOD, 5)):
        v3, n3, u3, i3 = [], [], [], []
        oriented_box(v3, n3, u3, i3, tuple(c * 0.34 for c in vec), vec, 0.34, 0.022, 0.022)
        cmds.append({"defineMesh3D": {"id": mid2, "verts": [round(v,5) for v in v3],
                                      "normals": n3, "uv": u3, "indices": i3}})
        chain = [{"matrix3D": {"op": "identity"}}]
        if mid2 == 5:
            chain.append({"matrix3D": {"op": "rotate", "angle": "@prec", "axis": [0, 1, 0]}})
        chain.append({"matrix3D": {"op": "translate", "x": 0.0, "y": -0.55, "z": 0.0}})
        cmds += chain + [paint({"color": colour}, {"style": "fill"}),
                         {"drawMesh3D": {"mesh": mid2, "mode": "software-smooth"}}]
    cmds += text_at("gravity pulls down", 160.0, 396.0, 10.0, HOT, pan_x=0.0)
    cmds += text_at("the axle goes sideways", 370.0, 396.0, 10.0, GOOD, pan_x=0.0)
    y = 448.0
    for name, note, colour in (
            ("Push it down", "and it turns sideways instead of falling", HOT),
            ("Why", "torque changes angular momentum, and angular momentum is a vector "
             "along the axle", ACCENT),
            ("The rate", "faster spin means slower precession - a fast top stands up "
             "straighter for longer", GOOD)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 36.0, "top": y - 9, "right": 41.0, "bottom": y + 5}})
        cmds += text_at(name, 52.0, y, 11.0, colour)
        cmds += text_at(note, 52.0, y + 15, 9.0, DIM)
        y += 40.0
    cmds += text_at("Nothing here is mysterious; it is only that the response to a push is "
                    "at right angles to it.", 36.0, 586.0, 9.5, DIM)
    title(cmds, W, H, "A wheel that will not fall", "the push is down, the motion is sideways")
    return {"header": header(W, H, "A spinning gyroscope with the gravitational torque and "
                                   "the resulting precession drawn as perpendicular vectors"),
            "root": canvas(cmds, INK)}


# ── 2. PHY-FM-00036  Laminar flow — annotated-layout / demonstrate / 2D ────
# Velocity profiles in a pipe at four Reynolds numbers. The parabola is the signature of
# laminar flow, and the flattening as Re rises is turbulence mixing the momentum across the
# pipe - visible as a shape change rather than asserted as a number.
def laminar():
    W, H = 520, 620
    CASES = [("Re = 200", 0, "deep parabola; every layer slides past its neighbour", GOOD),
             ("Re = 1,800", 1, "still laminar, but only just", ACCENT),
             ("Re = 4,000", 2, "transition - it flickers between the two", WARM),
             ("Re = 40,000", 3, "flat core, thin wall layer; fully turbulent", HOT)]

    def profile(kind, colour):
        c = [{"clipRect": {"left": 0, "top": 0, "right": 150, "bottom": 96}},
             paint({"color": RULE}, {"style": "fill"}),
             {"drawRect": {"left": 0, "top": 0, "right": 150, "bottom": 96}}]
        c.append(paint({"color": DIM}, {"style": "stroke"}, {"width": 1.4}))
        c.append({"drawLine": {"x1": 0, "y1": 6, "x2": 150, "y2": 6}})
        c.append({"drawLine": {"x1": 0, "y1": 90, "x2": 150, "y2": 90}})
        n = (2.0, 2.4, 4.0, 9.0)[kind]
        c.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.0}))
        prev = None
        for i in range(25):
            r = -1.0 + 2.0 * i / 24.0
            v = 1.0 - abs(r) ** n
            y = 48 + r * 42
            x = 12 + v * 120
            if prev:
                c.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": x, "y2": y}})
            prev = (x, y)
        for k in range(7):
            r = -0.86 + 1.72 * k / 6.0
            v = 1.0 - abs(r) ** n
            y = 48 + r * 42
            c.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.0},
                           {"strokeCap": "round"}))
            c.append({"drawLine": {"x1": 12, "y1": y, "x2": 12 + v * 120, "y2": y}})
        return {"type": "canvas", "modifiers": [{"width": 150}, {"height": 96}],
                "commands": c}

    kids = [{"type": "text", "value": "Flow in a pipe", "modifiers": [],
             "fontSize": 19.0, "color": TEXT},
            {"type": "spacer", "modifiers": [{"height": 3}]},
            {"type": "text", "value": "the velocity profile across the diameter",
             "modifiers": [], "fontSize": 11.0, "color": DIM},
            {"type": "spacer", "modifiers": [{"height": 14}]}]
    for name, kind, note, colour in CASES:
        kids.append({"type": "row",
                     "modifiers": [{"width": 456}, {"padding": 10}, {"background": PANEL}],
                     "children": [
                         profile(kind, colour),
                         {"type": "spacer", "modifiers": [{"width": 12}]},
                         {"type": "column", "modifiers": [{"width": 262}], "children": [
                             {"type": "text", "value": name, "modifiers": [],
                              "fontSize": 13.0, "color": colour},
                             {"type": "spacer", "modifiers": [{"height": 4}]},
                             {"type": "text", "value": note, "modifiers": [],
                              "fontSize": 9.5, "color": DIM}]}]})
        kids.append({"type": "spacer", "modifiers": [{"height": 9}]})
    kids.append({"type": "text",
                 "value": "Laminar flow wastes energy only at the wall. Turbulent flow mixes "
                          "momentum across the whole pipe, which is why the pressure needed "
                          "jumps when the transition happens - and why pipeline engineers "
                          "care about a dimensionless number.",
                 "modifiers": [], "fontSize": 10.0, "color": TEXT})
    return {"header": header(W, H, "Velocity profiles across a pipe at four Reynolds "
                                   "numbers, from parabolic to flat-cored"),
            "root": {"type": "column",
                     "modifiers": ["fillMaxSize", {"padding": 18}, {"background": INK}],
                     "children": kids}}


# ── 3. BIO-ANAT-00029  Skeletal system — data-plot / simulate / 2D ─────────
# Bone mass across a lifetime, by sex, with the thresholds marked. The shape is the message:
# peak bone mass is set by about thirty and everything after is management, so the decisive
# interventions happen decades before the fracture.
def skeleton():
    W, H = 580, 540
    cmds = []
    px0, px1, py0, py1 = 70.0, 540.0, 150.0, 360.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    def mass(age, female):
        peak = 1.00 if not female else 0.88
        if age < 30:
            return peak * (0.25 + 0.75 * (age / 30.0) ** 0.75)
        d = age - 30
        if female and age > 50:
            return peak * max(0.46, 1.0 - 0.004 * 20 - 0.021 * (age - 50))
        return peak * max(0.46, 1.0 - 0.004 * d)
    for female, colour, lbl in ((False, ACCENT, "male"), (True, HOT, "female")):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6},
                          {"strokeCap": "round"}))
        prev = None
        for i in range(91):
            age = i
            pt = (px0 + (px1 - px0) * age / 90.0,
                  py1 - mass(age, female) * (py1 - py0) * 0.92)
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1],
                                          "x2": pt[0], "y2": pt[1]}})
            prev = pt
        cmds += text_at(lbl, prev[0] - 6, prev[1] - 8, 10.0, colour, pan_x=1.0)
    for frac, lbl, colour in ((0.70, "osteopenia", WARM), (0.55, "osteoporosis", HOT)):
        y = py1 - frac * (py1 - py0) * 0.92
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.2}))
        cmds.append({"drawLine": {"x1": px0, "y1": y, "x2": px1, "y2": y}})
        cmds += text_at(lbl, px0 + 6, y - 5, 9.0, colour)
    px = px0 + (px1 - px0) * 30.0 / 90.0
    cmds.append(paint({"color": GOOD}, {"style": "stroke"}, {"width": 1.4}))
    cmds.append({"drawLine": {"x1": px, "y1": py0, "x2": px, "y2": py1}})
    cmds += text_at("peak, about 30", px + 6, py0 + 18, 10.0, GOOD)
    pm = px0 + (px1 - px0) * 50.0 / 90.0
    cmds.append(paint({"color": DIM}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": pm, "y1": py0, "x2": pm, "y2": py1}})
    cmds += text_at("menopause", pm + 6, py0 + 36, 9.5, DIM)
    for a in (0, 30, 60, 90):
        cmds += text_at("%d" % a, px0 + (px1 - px0) * a / 90.0, py1 + 20, 9.5, DIM, pan_x=0.0)
    cmds += text_at("age, years", (px0 + px1) / 2, py1 + 38, 10.0, DIM, pan_x=0.0)
    cmds += text_at("bone mineral density", px0, py0 - 12, 10.5, DIM)
    cmds += text_at("The height of the peak is decided before thirty; everything after is "
                    "how slowly it falls.", 70.0, 442.0, 11.0, TEXT)
    cmds += text_at("- which is why calcium and loading in adolescence matter more to a "
                    "fracture at seventy than", 70.0, 462.0, 10.0, DIM)
    cmds += text_at("anything done at sixty-five. Curves are illustrative of population "
                    "averages, not an individual.", 70.0, 478.0, 10.0, DIM)
    title(cmds, W, H, "Bone over a lifetime", "the peak is set early")
    return {"header": header(W, H, "Bone mineral density across a lifetime for both sexes "
                                   "with the clinical thresholds marked"),
            "root": canvas(cmds, INK)}


# ── 4. MTH-TRIG-00013  Unit circle — path-form / analyze / 2D ──────────────
# The circle on the left, the sine wave unrolled to the right, and a tie line between them.
# The wave is not an analogy for the circle - it is the circle's height, plotted against the
# angle, and the construction says so.
def unit_circle():
    W, H = 620, 440
    cmds = [var("ang", "continuousSec() * 0.7 - floor(continuousSec() * 0.7 / 6.2832) * 6.2832")]
    ccx, ccy, R = 150.0, 260.0, 92.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": ccx, "cy": ccy, "radius": R}})
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawCircle": {"cx": ccx, "cy": ccy, "radius": R}})
    cmds.append({"drawLine": {"x1": ccx - R, "y1": ccy, "x2": ccx + R, "y2": ccy}})
    cmds.append({"drawLine": {"x1": ccx, "y1": ccy - R, "x2": ccx, "y2": ccy + R}})
    px0, px1 = 280.0, 580.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": ccy - R, "right": px1, "bottom": ccy + R}})
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": px0, "y1": ccy, "x2": px1, "y2": ccy}})
    # the sine curve, as a path
    cmds.append({"pathCreate": {"id": "sine", "x": px0, "y": ccy}})
    for i in range(1, 121):
        t = i / 120.0
        cmds.append({"pathAppendLineTo": {"path": "sine", "x": px0 + (px1 - px0) * t,
                                          "y": ccy - math.sin(t * 2 * math.pi) * R}})
    cmds.append(paint({"color": ACCENT}, {"style": "stroke"}, {"width": 2.4},
                      {"strokeCap": "round"}))
    cmds.append({"drawPath": {"path": "sine"}})
    # the moving radius, and the tie across to the wave
    cmds.append(paint({"color": GOOD}, {"style": "stroke"}, {"width": 2.2},
                      {"strokeCap": "round"}))
    cmds.append({"drawLine": {"x1": ccx, "y1": ccy,
                              "x2": "%.1f + cos(@ang) * %.1f" % (ccx, R),
                              "y2": "%.1f - sin(@ang) * %.1f" % (ccy, R)}})
    cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 1.2}))
    cmds.append({"drawLine": {"x1": "%.1f + cos(@ang) * %.1f" % (ccx, R),
                              "y1": "%.1f - sin(@ang) * %.1f" % (ccy, R),
                              "x2": "%.1f + @ang / 6.2832 * %.1f" % (px0, px1 - px0),
                              "y2": "%.1f - sin(@ang) * %.1f" % (ccy, R)}})
    cmds.append(paint({"color": WARM}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": "%.1f + @ang / 6.2832 * %.1f" % (px0, px1 - px0),
                                "cy": "%.1f - sin(@ang) * %.1f" % (ccy, R), "radius": 4.5}})
    cmds += text_at("sin", ccx + 10, ccy - R - 10, 10.0, GOOD)
    for frac, lbl in ((0.0, "0"), (0.25, "pi/2"), (0.5, "pi"), (0.75, "3pi/2"), (1.0, "2pi")):
        cmds += text_at(lbl, px0 + (px1 - px0) * frac, ccy + R + 20, 9.0, DIM, pan_x=0.0)
    cmds += text_at("The wave is the circle's height, plotted against how far round you have "
                    "gone.", 60.0, 396.0, 11.0, TEXT)
    cmds += text_at("- not an analogy, a construction. Cosine is the same picture read "
                    "horizontally instead.", 60.0, 416.0, 10.0, DIM)
    title(cmds, W, H, "Unrolling a circle", "the radius turns, the wave is its shadow")
    return {"header": header(W, H, "A rotating radius on the unit circle tied across to the "
                                   "sine curve it traces"),
            "root": canvas(cmds, INK)}


# ── 5. CSC-CA-00011  CPU — expression-animation / explain / 2D ─────────────
# Five instructions moving through a five-stage pipeline, one stage per beat. The diagonal
# is the whole idea: throughput is one instruction per cycle even though each one takes five,
# and the empty triangles at each end are the cost of filling and draining.
def cpu():
    W, H = 620, 480
    STAGES = ["fetch", "decode", "execute", "memory", "write"]
    COLOURS = [GOOD, ACCENT, WARM, HOT, TEXT]
    N = 6
    cmds = [var("beat", "continuousSec() * 0.9 - floor(continuousSec() * 0.9 / 11.0) * 11.0"),
            # 9, not 10: the clock line is drawn one cell to the RIGHT of @clk, so at 10 it
            # landed past the last column and off the page.
            var("clk", "clamp(0.0, 9.0, floor(@beat))")]
    # Ten columns have to fit the page. At the old x0/cw the grid was 870px wide on a
    # 620px document and columns 7, 8 and 9 were drawn entirely off the right-hand edge -
    # a third of the pipeline, including the whole drain phase the caption talks about.
    x0, y0, cw, rh = 76.0, 165.0, 52.0, 36.0
    for s, name in enumerate(STAGES):
        cmds += text_at(name, x0 - 12, y0 + s * rh + 22, 10.0, COLOURS[s], pan_x=1.0)
    for c in range(10):
        cmds += text_at("%d" % c, x0 + c * cw + cw / 2, y0 - 10, 9.0, DIM, pan_x=0.0)
    for i in range(N):
        for s in range(len(STAGES)):
            cyc = i + s
            if cyc > 9:
                continue
            x = x0 + cyc * cw
            y = y0 + s * rh
            cmds.append({"conditionalOperations": {
                "condition": "ge", "v1": "@clk", "v2": float(cyc),
                "commands": [
                    paint({"color": COLOURS[s]}, {"style": "fill"}),
                    {"drawRect": {"left": x + 2, "top": y + 2, "right": x + cw - 4,
                                  "bottom": y + rh - 4}},
                    paint({"color": INK}, {"style": "fill"}, {"textSize": 9.5}),
                    {"drawTextAnchored": {"text": "i%d" % i, "x": x + cw / 2,
                                          "y": y + rh / 2 + 3, "panX": 0.0, "panY": 0.0,
                                          "flags": 0}}]}})
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.6}))
    cmds.append({"drawLine": {"x1": "%.1f + @clk * %.1f + %.1f" % (x0, cw, cw),
                              "y1": y0 - 4,
                              "x2": "%.1f + @clk * %.1f + %.1f" % (x0, cw, cw),
                              "y2": y0 + len(STAGES) * rh + 4}})
    cmds += text_at("Each instruction takes five cycles. One finishes every cycle anyway.",
                    60.0, 390.0, 11.5, TEXT)
    cmds += text_at("- the empty triangle at the start is the pipeline filling, and the one "
                    "at the end is it draining.", 60.0, 410.0, 10.0, DIM)
    cmds += text_at("A branch that guesses wrong throws away everything in flight and pays "
                    "that fill cost again,", 60.0, 426.0, 10.0, DIM)
    cmds += text_at("which is why branch prediction is worth so much silicon.",
                    60.0, 442.0, 10.0, DIM)
    title(cmds, W, H, "A five-stage pipeline", "one stage per beat")
    return {"header": header(W, H, "Six instructions advancing through a five-stage CPU "
                                   "pipeline, one stage per clock"),
            "root": canvas(cmds, INK)}


# ── 6. CHM-CR-00011  Catalysis — particle-system / explore / 3D ────────────
# Molecules bouncing around a catalytic surface, with the few that land on it reacting. The
# particle picture carries the real mechanism: a catalyst works by holding two things still
# next to each other, not by pushing them together.
def catalysis():
    W, H = 540, 600
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.74,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [1.9, 1.4, 3.3], "center": [0.0, 0.0, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.4, -0.55, -0.73], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.3, 0.45], "intensity": 0.42}]}}]
    cmds.append(var("spin", "sin(continuousSec() * 0.18) * 0.4"))
    # the catalyst surface, a slab with a lattice of sites
    verts, normals, uv, idx = [], [], [], []
    mesh_box(verts, normals, uv, idx, (-1.0, -0.56, -1.0), (1.0, -0.46, 1.0))
    cmds.append({"defineMesh3D": {"id": 1, "verts": verts, "normals": normals,
                                  "uv": uv, "indices": idx}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": RULE}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]
    v2, n2, u2, i2 = [], [], [], []
    for gx in range(5):
        for gz in range(5):
            cx = -0.8 + gx * 0.4
            cz = -0.8 + gz * 0.4
            mesh_box(v2, n2, u2, i2, (cx - 0.07, -0.46, cz - 0.07),
                     (cx + 0.07, -0.40, cz + 0.07))
    cmds.append({"defineMesh3D": {"id": 2, "verts": [round(v,5) for v in v2],
                                  "normals": n2, "uv": u2, "indices": i2}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": GOOD}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 2, "mode": "software-smooth"}}]
    # gas molecules above, in 2D over the scene so the count is legible
    cmds.append({"createParticles": {
        "id": "gas", "count": 80,
        "variables": ["gx", "gy", "gv", "gp"],
        "initialValues": ["70 + rand() * 400", "150 + rand() * 150",
                          "0.4 + rand() * 1.3", "rand() * 6.28"]}})
    cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
    cmds.append({"particlesLoop": {
        "system": "@gas",
        "equations": ["gx + sin(gp) * 0.6", "150 + ((gy - 150 + gv) % 150)", "gv", "gp + 0.05"],
        "commands": [{"drawCircle": {"cx": "@gx", "cy": "@gy", "radius": 2.6}}]}})
    cmds += text_at("gas molecules, moving freely", 270.0, 142.0, 9.5, DIM, pan_x=0.0)
    cmds += text_at("the catalyst surface, with its sites", 270.0, 404.0, 9.5, GOOD, pan_x=0.0)
    y = 442.0
    for name, note, colour in (
            ("It holds, it does not push", "two molecules adsorb on neighbouring sites and "
             "are simply held still, facing each other", GOOD),
            ("Orientation is most of it", "in the gas they must collide correctly aligned; "
             "on the surface they already are", ACCENT),
            ("It is not consumed", "the site is vacated afterwards, which is why a few grams "
             "can process tonnes", WARM)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 36.0, "top": y - 9, "right": 41.0, "bottom": y + 5}})
        cmds += text_at(name, 52.0, y, 11.0, colour)
        cmds += text_at(note, 52.0, y + 15, 8.5, DIM)
        y += 40.0
    cmds += text_at("Poisoning a catalyst means occupying its sites with something that will "
                    "not leave.", 36.0, 574.0, 9.5, DIM)
    title(cmds, W, H, "A catalytic surface", "the trick is holding still, not pushing")
    return {"header": header(W, H, "Gas molecules above a catalytic surface with its "
                                   "adsorption sites drawn in 3D"),
            "root": canvas(cmds, INK)}


# ── 7. EAR-METE-00011  Atmospheric circulation — interactive / compare / 2D ─
# Drag through latitude and watch which cell you are in, what the surface wind does, and why
# the deserts sit where they do. The three-cell structure explains the Sahara, the Amazon
# and the trade winds with one picture.
def circulation():
    W, H = 580, 580
    BANDS = [(-90, -60, "Polar cell", "cold air sinking, easterly surface winds", HOT),
             (-60, -30, "Ferrel cell", "westerlies; the storm track", ACCENT),
             (-30, 0, "Hadley cell", "trade winds blowing toward the equator", GOOD),
             (0, 30, "Hadley cell", "trade winds blowing toward the equator", GOOD),
             (30, 60, "Ferrel cell", "westerlies; the storm track", ACCENT),
             (60, 90, "Polar cell", "cold air sinking, easterly surface winds", HOT)]
    cmds = [{"touchExpression": {"name": "drag", "defaultValue": 290.0, "min": 60.0,
                                 "max": 520.0, "expression": "touchX()"}},
            var("lat", "(@drag - 60.0) / 460.0 * 180.0 - 90.0")]
    px0, px1, py0, py1 = 70.0, 520.0, 150.0, 370.0
    for lo, hi, name, note, colour in BANDS:
        y0 = py1 - (lo + 90) / 180.0 * (py1 - py0)
        y1 = py1 - (hi + 90) / 180.0 * (py1 - py0)
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": px0, "top": min(y0, y1) + 1,
                                  "right": px0 + 26, "bottom": max(y0, y1) - 1}})
    # rising and sinking, drawn where they happen
    for lat, kind, colour in ((0, "rising", GOOD), (30, "sinking", WARM), (-30, "sinking", WARM),
                              (60, "rising", ACCENT), (-60, "rising", ACCENT),
                              (90, "sinking", HOT), (-90, "sinking", HOT)):
        y = py1 - (lat + 90) / 180.0 * (py1 - py0)
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.8},
                          {"strokeCap": "round"}))
        d = -1 if kind == "rising" else 1
        for k in range(3):
            x = px0 + 60 + k * 54
            cmds.append({"drawLine": {"x1": x, "y1": y + d * 16, "x2": x, "y2": y - d * 16}})
            cmds.append({"drawLine": {"x1": x, "y1": y - d * 16, "x2": x - 4,
                                      "y2": y - d * 11}})
            cmds.append({"drawLine": {"x1": x, "y1": y - d * 16, "x2": x + 4,
                                      "y2": y - d * 11}})
        cmds += text_at(kind, px0 + 230, y + 4, 9.0, colour)
    for lat, lbl in ((90, "north pole"), (30, "30 N - deserts"), (0, "equator - rainforest"),
                     (-30, "30 S - deserts"), (-90, "south pole")):
        y = py1 - (lat + 90) / 180.0 * (py1 - py0)
        cmds += text_at(lbl, px1 - 6, y + 4, 9.0, DIM, pan_x=1.0)
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.6}))
    cmds.append({"drawLine": {"x1": px0 - 6, "y1": "%.1f - (@lat + 90.0) / 180.0 * %.1f"
                                                   % (py1, py1 - py0),
                              "x2": px1 + 6, "y2": "%.1f - (@lat + 90.0) / 180.0 * %.1f"
                                                   % (py1, py1 - py0)}})
    cmds += [{"variable": {"name": "latlbl", "commit": True,
                           "value": {"type": "textFromFloat", "value": "@lat",
                                     "whole": 3, "decimal": 0}}},
             paint({"color": TEXT}, {"style": "fill"}, {"textSize": 15.0}),
             {"drawTextAnchored": {"text": "@latlbl", "x": 70.0, "y": 414.0,
                                   "panX": -1.0, "panY": 0.0, "flags": 0}}]
    cmds += text_at("degrees latitude", 128.0, 414.0, 10.5, DIM)
    for lo, hi, name, note, colour in BANDS:
        cmds.append({"conditionalOperations": {
            "condition": "ge", "v1": "@lat", "v2": float(lo),
            "commands": [{"conditionalOperations": {
                "condition": "lt", "v1": "@lat", "v2": float(hi),
                "commands": [
                    paint({"color": colour}, {"style": "fill"}, {"textSize": 13.0}),
                    {"drawTextAnchored": {"text": name, "x": 70.0, "y": 446.0,
                                          "panX": -1.0, "panY": 0.0, "flags": 0}},
                    paint({"color": DIM}, {"style": "fill"}, {"textSize": 10.0}),
                    {"drawTextAnchored": {"text": note, "x": 70.0, "y": 466.0,
                                          "panX": -1.0, "panY": 0.0, "flags": 0}}]}}]}})
    cmds += text_at("Air rises at the equator, dries out, and comes back down at thirty "
                    "degrees.", 70.0, 506.0, 11.0, TEXT)
    cmds += text_at("- that descending dry air is the Sahara, the Arabian, the Kalahari and "
                    "the Australian interior,", 70.0, 524.0, 10.0, DIM)
    cmds += text_at("all at the same latitude on both sides, for the same reason.",
                    70.0, 540.0, 10.0, DIM)
    cmds += text_at("drag to move north and south", 70.0, 564.0, 9.0, DIM)
    title(cmds, W, H, "Three cells per hemisphere", "drag through the latitudes")
    return {"header": header(W, H, "The three-cell atmospheric circulation by latitude, "
                                   "draggable, with the desert bands explained"),
            "root": canvas(cmds, INK)}


# ── 8. ENG-EE-00011  RF systems — raster-and-text / demonstrate / 2D ───────
# The radio spectrum as a single bar with the allocations marked, plus what each band can
# physically do. The trade is monotonic and worth stating plainly: higher frequency carries
# more data and travels less far.
def rf():
    W, H = 620, 460
    BANDS = [("LF", 0.03, 0.3, "submarine comms", HOT),
             ("MF", 0.3, 3, "AM radio", HOT),
             ("HF", 3, 30, "shortwave, bounces off the ionosphere", WARM),
             ("VHF", 30, 300, "FM radio, air traffic", WARM),
             ("UHF", 300, 3000, "TV, mobile, Wi-Fi 2.4", GOOD),
             ("SHF", 3000, 30000, "Wi-Fi 5/6, satellite, radar", ACCENT),
             ("EHF", 30000, 300000, "5G mmWave, short and thirsty", TEXT)]
    cmds = []
    px0, px1, by = 60.0, 560.0, 190.0
    import math as _m
    def lx(f):
        return px0 + (px1 - px0) * (_m.log10(f) - _m.log10(0.03)) / (_m.log10(300000) - _m.log10(0.03))
    for name, f0, f1, use, colour in BANDS:
        x0, x1 = lx(f0), lx(f1)
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0 + 1, "top": by, "right": x1 - 1,
                                  "bottom": by + 40}})
        if x1 - x0 > 26:
            cmds += text_at(name, (x0 + x1) / 2, by + 26, 10.0, INK, pan_x=0.0)
    y = by + 62
    for name, f0, f1, use, colour in BANDS:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 60.0, "top": y - 8, "right": 72.0, "bottom": y + 4}})
        cmds += text_at(name, 82.0, y, 10.0, colour)
        cmds += text_at("%g - %g MHz" % (f0, f1), 130.0, y, 9.5, TEXT)
        cmds += text_at(use, 290.0, y, 9.5, DIM)
        y += 20.0
    cmds.append(paint({"color": DIM}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": px0, "y1": by - 14, "x2": px1, "y2": by - 14}})
    cmds += text_at("more range, less data", px0, by - 20, 9.5, HOT)
    cmds += text_at("more data, less range", px1, by - 20, 9.5, ACCENT, pan_x=1.0)
    cmds += text_at("The whole engineering trade is monotonic along this bar.",
                    60.0, 400.0, 11.0, TEXT)
    cmds += text_at("- a 5G mmWave cell reaches a few hundred metres and is stopped by a "
                    "window; an AM transmitter", 60.0, 420.0, 10.0, DIM)
    cmds += text_at("reaches a county and carries voice. Nobody has found a way around it.",
                    60.0, 436.0, 10.0, DIM)
    title(cmds, W, H, "The radio spectrum", "on a log scale, because it spans seven decades")
    return {"header": header(W, H, "The radio spectrum as a logarithmic bar with band "
                                   "allocations and what each is physically good for"),
            "root": canvas(cmds, INK)}


# ── 9. MED-PHAR-00007  Drug mechanisms — static-diagram / demonstrate / 2D ─
# Four ways a drug can act at a receptor, drawn as the same receptor four times. Agonist and
# antagonist are not opposites in the way the words suggest, and the pictures make the
# difference between blocking and reversing visible.
def drug_mechanisms():
    W, H = 620, 440
    KINDS = [("Agonist", "binds and switches it on, like the natural signal", 1.0, GOOD),
             ("Partial agonist", "binds and switches it part-way on, and blocks the rest",
              0.45, ACCENT),
             ("Antagonist", "binds, does nothing, and keeps the signal out", 0.0, WARM),
             ("Inverse agonist", "binds and pushes it below its resting activity", -0.4, HOT)]
    cmds = []
    # Narrower panels, pushed right, to leave a margin the baseline label fits in. Right-
    # aligned at x=26 "resting activity" started at about x=-44 and lost its first word.
    pw = 124.0
    for i, (name, note, level, colour) in enumerate(KINDS):
        x0 = 84.0 + i * (pw + 10.0)
        cx = x0 + pw / 2
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": 130.0, "right": x0 + pw,
                                  "bottom": 300.0}})
        # the receptor: a notch in a membrane
        cmds.append(paint({"color": RULE}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0 + 6, "top": 206.0, "right": x0 + pw - 6,
                                  "bottom": 226.0}})
        cmds.append(paint({"color": INK}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": cx - 16, "top": 206.0, "right": cx + 16,
                                  "bottom": 226.0}})
        # the drug, sitting in it
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": cx - 14, "top": 186.0, "right": cx + 14,
                                  "bottom": 224.0}})
        # the signal that results, as a bar below the baseline
        base = 268.0
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": x0 + 10, "y1": base, "x2": x0 + pw - 10, "y2": base}})
        h = level * 34.0
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        if h >= 0:
            cmds.append({"drawRect": {"left": cx - 22, "top": base - h, "right": cx + 22,
                                      "bottom": base}})
        else:
            cmds.append({"drawRect": {"left": cx - 22, "top": base, "right": cx + 22,
                                      "bottom": base - h}})
        cmds += text_at(name, cx, 122.0, 11.0, colour, pan_x=0.0)
        cmds += text_at("%+d%%" % int(level * 100), cx, 290.0, 9.5, TEXT, pan_x=0.0)
        for wi, w in enumerate(_wrap11(note, 26)):
            cmds += text_at(w, x0 + 2, 318.0 + wi * 12.0, 8.0, DIM)
    cmds += text_at("resting activity", 76.0, 268.0, 8.5, DIM, pan_x=1.0)
    cmds += text_at("An antagonist does not switch anything off. It occupies the site so "
                    "nothing else can.", 26.0, 376.0, 11.0, TEXT)
    cmds += text_at("- which is why it does nothing at all in someone with no natural signal "
                    "present, and why an", 26.0, 396.0, 10.0, DIM)
    cmds += text_at("inverse agonist is a genuinely different drug rather than a stronger "
                    "blocker.", 26.0, 412.0, 10.0, DIM)
    title(cmds, W, H, "Four things a drug can do", "at one receptor")
    return {"header": header(W, H, "Agonist, partial agonist, antagonist and inverse agonist "
                                   "at the same receptor, with the resulting signal"),
            "root": canvas(cmds, INK)}


def _wrap11(text, n):
    out, line = [], ""
    for w in text.split():
        if len(line) + len(w) + 1 > n:
            out.append(line); line = w
        else:
            line = (line + " " + w).strip()
    if line: out.append(line)
    return out


# ── 10. MED-PHAR-00008  Drug metabolism — annotated-layout / simulate / 2D ─
# Plasma concentration after dosing, with the therapeutic window drawn as a band. The band
# is the whole of dosing: too little does nothing, too much is toxic, and the schedule is an
# attempt to stay between two lines.
def drug_metabolism():
    W, H = 580, 540
    cmds = []
    px0, px1, py0, py1 = 70.0, 540.0, 150.0, 360.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    TOXIC, MIN = 0.80, 0.30
    for lvl, lbl, colour in ((TOXIC, "toxic above here", HOT),
                             (MIN, "no effect below here", DIM)):
        y = py1 - lvl * (py1 - py0)
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.4}))
        cmds.append({"drawLine": {"x1": px0, "y1": y, "x2": px1, "y2": y}})
        cmds += text_at(lbl, px1 - 6, y - 5, 9.0, colour, pan_x=1.0)
    cmds.append(paint({"color": GOOD}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py1 - TOXIC * (py1 - py0),
                              "right": px1, "bottom": py1 - MIN * (py1 - py0)}})
    cmds += text_at("therapeutic window", px0 + 8, py1 - (TOXIC + MIN) / 2 * (py1 - py0) + 4,
                    10.0, INK)
    for doses, colour, lbl in ((1, WARM, "one big dose"), (4, ACCENT, "four small doses")):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.4},
                          {"strokeCap": "round"}))
        prev = None
        for i in range(121):
            t = i / 120.0 * 24.0
            c = 0.0
            for d in range(doses):
                td = d * (24.0 / doses)
                if t >= td:
                    amt = (0.95 if doses == 1 else 0.33)
                    c += amt * (1 - math.exp(-(t - td) * 2.2)) * math.exp(-(t - td) / 5.0)
            pt = (px0 + (px1 - px0) * t / 24.0, py1 - min(1.0, c) * (py1 - py0))
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1],
                                          "x2": pt[0], "y2": pt[1]}})
            prev = pt
        cmds += text_at(lbl, px0 + 8, py0 + (18 if doses == 1 else 34), 9.5, colour)
    for h in (0, 6, 12, 18, 24):
        cmds += text_at("%d" % h, px0 + (px1 - px0) * h / 24.0, py1 + 20, 9.0, DIM, pan_x=0.0)
    cmds += text_at("hours", (px0 + px1) / 2, py1 + 38, 10.0, DIM, pan_x=0.0)
    cmds += text_at("plasma concentration", px0, py0 - 12, 10.5, DIM)
    y = 420.0
    for name, note, colour in (
            ("One big dose", "overshoots into toxicity, then falls below useful before the "
             "day is out", WARM),
            ("Four small doses", "stays inside the window the whole time, which is the "
             "entire reason for dosing schedules", ACCENT),
            ("Half-life sets the spacing", "a drug cleared in two hours cannot be given "
             "once a day, whatever is convenient", GOOD)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 70.0, "top": y - 9, "right": 75.0, "bottom": y + 5}})
        cmds += text_at(name, 86.0, y, 11.0, colour)
        cmds += text_at(note, 86.0, y + 15, 9.0, DIM)
        y += 36.0
    cmds += text_at("Illustrative curves, not a specific drug.", 70.0, 526.0, 8.5, DIM)
    title(cmds, W, H, "Staying inside the window", "the same total dose, two schedules")
    return {"header": header(W, H, "Plasma concentration for one large dose against four "
                                   "small ones, against a therapeutic window"),
            "root": canvas(cmds, INK)}


# ── 11. MED-MP-00009  Surgery — data-plot / analyze / 2D ───────────────────
# Risk against time for open and keyhole versions of the same operation. The curves cross,
# which is the honest shape of the choice: keyhole costs longer in theatre and returns it in
# recovery, and for a frail patient the theatre time is the part that matters.
def surgery():
    W, H = 580, 520
    cmds = []
    px0, px1, py0, py1 = 70.0, 540.0, 150.0, 350.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    def open_risk(d):
        return 0.82 * math.exp(-d / 9.0) + 0.06
    def lap_risk(d):
        return 0.52 * math.exp(-d / 4.0) + 0.04
    for fn, colour, lbl in ((open_risk, WARM, "open"), (lap_risk, ACCENT, "keyhole")):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6},
                          {"strokeCap": "round"}))
        prev = None
        for i in range(61):
            d = i / 60.0 * 30.0
            pt = (px0 + (px1 - px0) * d / 30.0, py1 - fn(d) * (py1 - py0) * 0.95)
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1],
                                          "x2": pt[0], "y2": pt[1]}})
            prev = pt
        cmds += text_at(lbl, prev[0] - 6, prev[1] - 8, 10.0, colour, pan_x=1.0)
    for d in (0, 10, 20, 30):
        cmds += text_at("day %d" % d, px0 + (px1 - px0) * d / 30.0, py1 + 20, 9.0, DIM,
                        pan_x=0.0)
    cmds += text_at("remaining complication risk", px0, py0 - 12, 10.5, DIM)
    y = 396.0
    ROWS = [("Theatre time", "95 min", "160 min", "keyhole takes longer under anaesthetic",
             WARM),
            ("Nights in hospital", "5", "1", "and gives it back immediately", ACCENT),
            ("Back to work", "6 weeks", "2 weeks", "the difference most patients notice",
             GOOD),
            ("Conversion to open", "-", "4%", "sometimes abandoned mid-operation", HOT)]
    cmds += text_at("", 70.0, y - 20, 10.0, DIM)
    # Columns pulled left to give the notes room: at 430 the last one needed 240px and had
    # 150, so it ran off the right-hand edge mid-word.
    cmds += text_at("open", 240.0, y - 18, 10.0, WARM, pan_x=0.0)
    cmds += text_at("keyhole", 310.0, y - 18, 10.0, ACCENT, pan_x=0.0)
    for name, a, b, note, colour in ROWS:
        cmds += text_at(name, 70.0, y, 10.0, TEXT)
        cmds += text_at(a, 240.0, y, 10.0, WARM, pan_x=0.0)
        cmds += text_at(b, 310.0, y, 10.0, ACCENT, pan_x=0.0)
        cmds += text_at(note, 370.0, y, 8.5, DIM)
        y += 21.0
    cmds += text_at("The curves cross, so neither operation is simply better.",
                    70.0, 496.0, 11.0, TEXT)
    cmds += text_at("Illustrative of a common abdominal procedure; not figures for any "
                    "specific operation or centre.", 70.0, 512.0, 8.5, DIM)
    title(cmds, W, H, "Two routes to the same repair", "the trade is theatre time for recovery")
    return {"header": header(W, H, "Complication risk over 30 days for open against keyhole "
                                   "surgery, with the operative trade-offs tabulated"),
            "root": canvas(cmds, INK)}


# ── 12. MED-MP-00010  Imaging — path-form / explain / 2D ───────────────────
# Four modalities ranked by what they see and what they cost you. The dose column is the one
# usually left out, and it is the reason the choice is never simply "the best picture".
def imaging():
    W, H = 600, 500
    MODES = [("X-ray", 0.02, "bone, air, metal", "0.1 mSv", "seconds", GOOD),
             ("CT", 0.35, "everything, in slices", "8 mSv", "minutes", HOT),
             ("Ultrasound", 0.18, "soft tissue, moving, live", "none", "minutes", ACCENT),
             ("MRI", 0.95, "soft tissue, exquisite contrast", "none", "30-60 min", WARM)]
    cmds = []
    px0, px1 = 70.0, 540.0
    y = 170.0
    for name, detail, sees, dose, dur, colour in MODES:
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": px0, "top": y - 16, "right": px1, "bottom": y + 40}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": px0, "top": y - 16, "right": px0 + 5,
                                  "bottom": y + 40}})
        cmds += text_at(name, px0 + 16, y + 4, 13.0, colour)
        cmds += text_at(sees, px0 + 16, y + 22, 9.0, DIM)
        # soft-tissue detail, as a bar
        cmds.append(paint({"color": RULE}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 250.0, "top": y - 4, "right": 410.0, "bottom": y + 8}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 250.0, "top": y - 4, "right": 250.0 + 160 * detail,
                                  "bottom": y + 8}})
        cmds += text_at(dose, 448.0, y + 6, 10.0, HOT if dose != "none" else GOOD, pan_x=0.0)
        cmds += text_at(dur, 516.0, y + 6, 9.0, DIM, pan_x=1.0)
        y += 66.0
    cmds += text_at("soft-tissue detail", 330.0, 152.0, 9.5, DIM, pan_x=0.0)
    cmds += text_at("dose", 448.0, 152.0, 9.5, DIM, pan_x=0.0)
    cmds += text_at("time", 516.0, 152.0, 9.5, DIM, pan_x=1.0)
    cmds += text_at("One CT is roughly three years of natural background radiation.",
                    70.0, 452.0, 11.0, TEXT)
    cmds += text_at("- which is why the best picture is not automatically the right test, "
                    "and why ultrasound is", 70.0, 470.0, 10.0, DIM)
    cmds += text_at("first for a pregnancy and MRI for a knee. Doses are typical adult "
                    "figures and vary widely.", 70.0, 486.0, 10.0, DIM)
    title(cmds, W, H, "Four ways to look inside", "what each one sees, and what it costs")
    return {"header": header(W, H, "Four imaging modalities compared on soft-tissue detail, "
                                   "radiation dose and time"),
            "root": canvas(cmds, INK)}


# ── 13. GEO-PG-00001  Mountains — expression-animation / explore / 3D ──────
# A range rising and eroding on one clock. Uplift and erosion are both continuous, and the
# height you see is the difference between them - which is why a mountain range has a steady
# state rather than a maximum.
def mountains_geo():
    W, H = 540, 600
    cmds = [{"clearDepth3D": {}},
            # Pulled back and dropped, so the range sits above the legend instead of across
            # it. A 3D scene is painted over the whole document - there is no card holding
            # it in - so the only thing keeping it off the text is where the camera stands.
            # The old framing ran the terrain off the left edge and over all four legend
            # entries. Checked at every value of @age: the mesh is scaled in y as the range
            # grows, so a camera that fits the young range can still overflow the old one.
            {"camera3D": {"projection": "perspective", "fovY": 0.62,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [2.54, 1.20, 4.77], "center": [0.0, -0.50, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.45, -0.58, -0.68], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.25, 0.5], "intensity": 0.42}]}}]
    cmds.append(var("age", "0.5 + 0.5 * sin(continuousSec() * 0.25)"))
    def ridge(u, v):
        spine = math.exp(-((v - 0.5) / 0.17) ** 2)
        rough = 0.22 * math.sin(u * 19.0) * math.sin(v * 23.0)
        return spine * (0.85 + rough)
    cmds.append(surface_mesh(1, ridge, 30, half=1.0, yscale=0.95, yoff=-0.40))
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "scale", "x": 1.0, "y": "0.25 + @age * 0.95", "z": 1.0}},
             paint({"color": WARM}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]
    y = 400.0
    for name, note, colour in (
            ("Uplift", "plates collide and the crust thickens; it goes up at millimetres a "
             "year", GOOD),
            ("Erosion", "rain, ice and gravity take it away, faster the higher it gets", HOT),
            ("Steady state", "a range stops growing when the two rates match - the Himalaya "
             "is near it now", ACCENT),
            ("Isostasy", "removing a kilometre of rock lets the root float up by most of "
             "that, so erosion is slow to win", WARM)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 36.0, "top": y - 9, "right": 41.0, "bottom": y + 5}})
        cmds += text_at(name, 52.0, y, 11.0, colour)
        cmds += text_at(note, 52.0, y + 15, 8.5, DIM)
        y += 38.0
    cmds += text_at("Everest is not the highest a mountain could be - it is where uplift and "
                    "erosion currently balance.", 36.0, 566.0, 9.5, DIM)
    title(cmds, W, H, "A range, rising and wearing down",
          "height is the difference between two rates")
    return {"header": header(W, H, "A mountain range as a 3D surface rising and eroding on "
                                   "one clock"),
            "root": canvas(cmds, INK)}


# ── 14. GEO-PG-00002  Rivers — particle-system / compare / 2D ──────────────
# Water as particles down two channels - one steep and straight, one shallow and meandering.
# The meander is not indecision; it is what a river does when it has more water than slope,
# and the particle speed shows why.
def rivers():
    W, H = 580, 540
    cmds = []
    for col, (name, steep, note, colour) in enumerate(
            (("Steep, young", True, "straight, fast, cutting down", ACCENT),
             ("Shallow, mature", False, "meandering, slow, cutting sideways", GOOD))):
        x0 = 44.0 + col * 258.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": 150.0, "right": x0 + 230,
                                  "bottom": 400.0}})
        cmds += text_at(name, x0 + 115, 142.0, 12.0, colour, pan_x=0.0)
        # the channel itself
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 14.0},
                          {"strokeCap": "round"}))
        prev = None
        for i in range(41):
            t = i / 40.0
            px = x0 + 20 + t * 190
            py = 170.0 + t * 210 + (0 if steep else math.sin(t * 7.5) * 26.0)
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": px, "y2": py}})
            prev = (px, py)
        cmds.append({"createParticles": {
            "id": "w%d" % col, "count": 70,
            "variables": ["wt", "wo", "wv", "wp"],
            "initialValues": ["rand()", "-5 + rand() * 10",
                              "%.2f + rand() * %.2f" % (0.9 if steep else 0.3,
                                                        0.5 if steep else 0.25),
                              "rand() * 6.28"]}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        wig = "0.0" if steep else "sin(@wt * 7.5) * 26.0"
        cmds.append({"particlesLoop": {
            "system": "@w%d" % col,
            "equations": ["(wt + wv * 0.004) % 1.0", "wo", "wv", "wp"],
            "commands": [{"drawCircle": {
                "cx": "%.1f + @wt * 190.0 + @wo" % (x0 + 20),
                "cy": "170.0 + @wt * 210.0 + %s" % wig,
                "radius": 2.4}}]}})
        cmds += text_at(note, x0 + 115, 420.0, 9.0, DIM, pan_x=0.0)
    y = 452.0
    for name, note, colour in (
            ("Slope decides the shape", "steep water has energy to spare and goes straight "
             "down; flat water spends it sideways", ACCENT),
            ("Meanders migrate", "the outside of a bend erodes and the inside deposits, so "
             "the whole curve walks downstream", GOOD),
            ("And they cut themselves off", "when two bends meet, the river takes the short "
             "way and leaves an oxbow lake", WARM)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 44.0, "top": y - 9, "right": 49.0, "bottom": y + 5}})
        cmds += text_at(name, 60.0, y, 11.0, colour)
        cmds += text_at(note, 60.0, y + 15, 9.0, DIM)
        y += 32.0
    title(cmds, W, H, "Two rivers", "the same water, different slope")
    return {"header": header(W, H, "Water as particles down a steep straight channel and a "
                                   "shallow meandering one"),
            "root": canvas(cmds, INK)}


# ── 15. GEO-PG-00003  Deserts — interactive / demonstrate / 2D ─────────────
# Drag across a continent and watch rainfall, with the four separate ways a desert forms
# marked where each one applies. "Hot and sandy" is not a definition; dryness is.
def deserts():
    W, H = 580, 560
    CAUSES = [(0.08, 0.20, "Subtropical", "descending dry air at 30 degrees - Sahara, "
               "Arabian", WARM),
              (0.32, 0.44, "Rain shadow", "the range took the water out - Atacama, Gobi",
               ACCENT),
              (0.56, 0.68, "Continental", "simply too far from any ocean - Taklamakan", HOT),
              (0.80, 0.94, "Coastal", "a cold current means no evaporation - Namib", GOOD)]
    cmds = [{"touchExpression": {"name": "drag", "defaultValue": 120.0, "min": 60.0,
                                 "max": 520.0, "expression": "touchX()"}},
            var("pos", "clamp(0.0, 1.0, (@drag - 60.0) / 460.0)")]
    px0, px1, py0, py1 = 60.0, 540.0, 150.0, 330.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    def rain(u):
        r = 0.18
        for c0, c1, *_ in CAUSES:
            mid = (c0 + c1) / 2
            r -= 0.16 * math.exp(-((u - mid) / 0.075) ** 2)
        r += 0.55 * math.exp(-((u - 0.26) / 0.05) ** 2)
        r += 0.48 * math.exp(-((u - 0.73) / 0.06) ** 2)
        return max(0.02, r)
    cmds.append(paint({"color": ACCENT}, {"style": "stroke"}, {"width": 2.6},
                      {"strokeCap": "round"}))
    prev = None
    for i in range(97):
        u = i / 96.0
        pt = (px0 + (px1 - px0) * u, py1 - rain(u) * (py1 - py0) * 1.5)
        if prev:
            cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": pt[0], "y2": pt[1]}})
        prev = pt
    ARID = 0.10
    ay = py1 - ARID * (py1 - py0) * 1.5
    cmds.append(paint({"color": HOT}, {"style": "stroke"}, {"width": 1.2}))
    cmds.append({"drawLine": {"x1": px0, "y1": ay, "x2": px1, "y2": ay}})
    cmds += text_at("below this line it is a desert", px0 + 6, ay - 6, 9.0, HOT)
    for c0, c1, name, note, colour in CAUSES:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": px0 + (px1 - px0) * c0, "top": py1 + 4,
                                  "right": px0 + (px1 - px0) * c1, "bottom": py1 + 12}})
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.6}))
    cmds.append({"drawLine": {"x1": "%.1f + @pos * %.1f" % (px0, px1 - px0), "y1": py0,
                              "x2": "%.1f + @pos * %.1f" % (px0, px1 - px0), "y2": py1 + 14}})
    for c0, c1, name, note, colour in CAUSES:
        cmds.append({"conditionalOperations": {
            "condition": "ge", "v1": "@pos", "v2": round(c0, 3),
            "commands": [{"conditionalOperations": {
                "condition": "lt", "v1": "@pos", "v2": round(c1, 3),
                "commands": [
                    paint({"color": colour}, {"style": "fill"}, {"textSize": 14.0}),
                    {"drawTextAnchored": {"text": name + " desert", "x": 60.0, "y": 388.0,
                                          "panX": -1.0, "panY": 0.0, "flags": 0}},
                    paint({"color": DIM}, {"style": "fill"}, {"textSize": 10.0}),
                    {"drawTextAnchored": {"text": note, "x": 60.0, "y": 410.0,
                                          "panX": -1.0, "panY": 0.0, "flags": 0}}]}}]}})
    cmds += text_at("rainfall", px0, py0 - 12, 10.5, DIM)
    cmds += text_at("west coast", px0, py1 + 30, 9.0, DIM)
    cmds += text_at("east coast", px1, py1 + 30, 9.0, DIM, pan_x=1.0)
    y = 442.0
    for c0, c1, name, note, colour in CAUSES:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 60.0, "top": y - 8, "right": 72.0, "bottom": y + 4}})
        cmds += text_at(name, 82.0, y, 10.0, colour)
        cmds += text_at(note, 180.0, y, 9.0, DIM)
        y += 20.0
    cmds += text_at("A desert is defined by dryness, not by heat or sand.", 60.0, 540.0,
                    10.5, TEXT)
    title(cmds, W, H, "Four ways to make a desert", "drag across the continent")
    return {"header": header(W, H, "Rainfall across a continent with the four separate "
                                   "mechanisms that produce deserts marked"),
            "root": canvas(cmds, INK)}


# ── 16. GEO-PG-00004  Biomes — raster-and-text / simulate / 2D ─────────────
# The Whittaker diagram: every biome placed by temperature and rainfall alone. Two numbers
# predict the vegetation of almost anywhere on Earth, which is a stronger claim than it
# sounds and mostly holds.
def biomes():
    W, H = 600, 520
    BIOMES = [("Tropical rainforest", 25, 350, GOOD),
              ("Savanna", 24, 120, WARM),
              ("Desert", 22, 25, HOT),
              ("Temperate forest", 12, 140, GOOD),
              ("Grassland", 10, 55, WARM),
              ("Boreal forest", 0, 60, ACCENT),
              ("Tundra", -8, 25, DIM),
              ("Temperate rainforest", 11, 280, GOOD)]
    cmds = []
    px0, px1, py0, py1 = 90.0, 540.0, 150.0, 380.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    def X(t):
        return px0 + (px1 - px0) * (t + 15) / 45.0
    def Y(p):
        return py1 - (py1 - py0) * p / 400.0
    for t in (-10, 0, 10, 20, 30):
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 0.8}))
        cmds.append({"drawLine": {"x1": X(t), "y1": py0, "x2": X(t), "y2": py1}})
        cmds += text_at("%d C" % t, X(t), py1 + 18, 9.0, DIM, pan_x=0.0)
    for p in (100, 200, 300, 400):
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 0.8}))
        cmds.append({"drawLine": {"x1": px0, "y1": Y(p), "x2": px1, "y2": Y(p)}})
        cmds += text_at("%d" % p, px0 - 6, Y(p) + 4, 9.0, DIM, pan_x=1.0)
    for name, t, p, colour in BIOMES:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": X(t), "cy": Y(p), "radius": 7.0}})
        cmds += text_at(name, X(t) + 11, Y(p) + 4, 8.5, colour)
    cmds += text_at("annual rainfall, cm", px0 - 6, py0 - 12, 10.0, DIM)
    cmds += text_at("mean annual temperature", (px0 + px1) / 2, py1 + 38, 10.0, DIM, pan_x=0.0)
    cmds += text_at("Two numbers, and you can name the vegetation almost anywhere.",
                    90.0, 432.0, 11.5, TEXT)
    cmds += text_at("- soil, fire and grazing move the boundaries, and people have moved "
                    "them a great deal, but the", 90.0, 452.0, 10.0, DIM)
    cmds += text_at("first-order prediction from temperature and rainfall alone is "
                    "remarkably good.", 90.0, 468.0, 10.0, DIM)
    cmds += text_at("The empty top-left is not an accident: cold air cannot hold enough "
                    "water to rain that much.", 90.0, 492.0, 9.5, DIM)
    title(cmds, W, H, "Where the biomes sit", "temperature across, rainfall up")
    return {"header": header(W, H, "The Whittaker biome diagram, placing eight biomes by "
                                   "temperature and rainfall alone"),
            "root": canvas(cmds, INK)}


# ── build ──────────────────────────────────────────────────────────────────────
BUILD = [("PHY-CM-00035", gyroscopes), ("PHY-FM-00036", laminar),
         ("BIO-ANAT-00029", skeleton), ("MTH-TRIG-00013", unit_circle),
         ("CSC-CA-00011", cpu), ("CHM-CR-00011", catalysis),
         ("EAR-METE-00011", circulation), ("ENG-EE-00011", rf),
         ("MED-PHAR-00007", drug_mechanisms), ("MED-PHAR-00008", drug_metabolism),
         ("MED-MP-00009", surgery), ("MED-MP-00010", imaging),
         ("GEO-PG-00001", mountains_geo), ("GEO-PG-00002", rivers),
         ("GEO-PG-00003", deserts), ("GEO-PG-00004", biomes)]

if __name__ == "__main__":
    for doc_id, fn in BUILD:
        name = use(doc_id)
        d = fn()
        (OUT / ("%s.json" % doc_id)).write_text(json.dumps(d, indent=1) + "\n")
        print("  %-16s %-9s %s" % (doc_id, name, d["header"]["contentDescription"][:44]))
    print("  %d documents" % len(BUILD))
