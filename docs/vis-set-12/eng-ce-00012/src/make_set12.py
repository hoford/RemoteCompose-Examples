#!/usr/bin/env python3
"""Build set 12 of the visualization programme: 16 documents.

    python3 work/set-12/make_set12.py

Work order from `python3 tools/visplan.py set 12`.

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


# ── 1. PHY-FM-00037  Turbulence — static-diagram / simulate / 2D ───────────
# The energy cascade: big eddies feeding smaller ones until viscosity eats them. The -5/3
# slope is one of the few exact-looking results in a famously inexact subject, and it is
# drawn here as a straight line on log axes because that is what it is.
def turbulence():
    W, H = 600, 500
    cmds = []
    px0, px1, py0, py1 = 80.0, 540.0, 150.0, 350.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    cmds.append(paint({"color": ACCENT}, {"style": "stroke"}, {"width": 2.8},
                      {"strokeCap": "round"}))
    prev = None
    for i in range(81):
        u = i / 80.0
        if u < 0.13:
            e = 0.92 - 0.3 * (0.13 - u) / 0.13
        elif u < 0.72:
            e = 0.92 - (u - 0.13) * 1.05
        else:
            e = 0.92 - (0.72 - 0.13) * 1.05 - (u - 0.72) * 3.6
        pt = (px0 + (px1 - px0) * u, py1 - max(0.02, e) * (py1 - py0))
        if prev:
            cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": pt[0], "y2": pt[1]}})
        prev = pt
    for u0, u1, name, note, colour in (
            (0.0, 0.13, "Production", "stirring puts energy in at the largest scale", GOOD),
            (0.13, 0.72, "Inertial range", "eddies hand energy down, losing none of it", WARM),
            (0.72, 1.0, "Dissipation", "viscosity finally turns it into heat", HOT)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": px0 + (px1 - px0) * u0, "top": py0,
                                  "right": px0 + (px1 - px0) * u1, "bottom": py0 + 7}})
        cmds += text_at(name, px0 + (px1 - px0) * (u0 + u1) / 2, py0 - 8, 9.0, colour,
                        pan_x=0.0)
    cmds += text_at("slope -5/3", px0 + (px1 - px0) * 0.42, py1 - 0.38 * (py1 - py0) - 14,
                    10.0, WARM)
    cmds += text_at("energy at this scale", px0, py0 - 24, 10.5, DIM)
    cmds += text_at("small eddies", px1, py1 + 20, 9.5, DIM, pan_x=1.0)
    cmds += text_at("large eddies", px0, py1 + 20, 9.5, DIM)
    # the cascade drawn literally, as nested circles
    y = 400.0
    x = 100.0
    for k in range(6):
        r = 34.0 / (1.5 ** k)
        cmds.append(paint({"color": (GOOD, WARM, WARM, WARM, HOT, HOT)[k]}, {"style": "stroke"},
                          {"width": 1.4}))
        cmds.append({"drawCircle": {"cx": x, "cy": y, "radius": r}})
        if k < 5:
            cmds.append(paint({"color": DIM}, {"style": "stroke"}, {"width": 1.0}))
            cmds.append({"drawLine": {"x1": x + r + 2, "y1": y, "x2": x + r + 22, "y2": y}})
        x += r + 34.0
    cmds += text_at("one big eddy becomes several smaller ones, and so on down",
                    100.0, 450.0, 10.0, DIM)
    cmds += text_at("Energy enters at one size and leaves at another, and in between it is "
                    "only being passed along.", 80.0, 476.0, 10.5, TEXT)
    title(cmds, W, H, "The energy cascade", "stirred at the top, heated at the bottom")
    return {"header": header(W, H, "The turbulent energy cascade on log axes with the "
                                   "inertial range and its -5/3 slope marked"),
            "root": canvas(cmds, INK)}


# ── 2. PHY-FM-00038  Vortices — annotated-layout / analyze / 2D ────────────
# Four vortices at wildly different scales, each with the same structure. The point is that
# a bath plug and a hurricane are the same object at different Reynolds numbers, and the
# numbers make that checkable.
def vortices():
    W, H = 520, 620
    KINDS = [("Bath drain", "2 cm", "a few seconds", "the Coriolis force is far too weak to "
              "matter at this size", GOOD),
             ("Dust devil", "5 m", "minutes", "ground heating, no parent storm", ACCENT),
             ("Tornado", "100 m", "tens of minutes", "stretched from a rotating thunderstorm",
              WARM),
             ("Hurricane", "500 km", "days to weeks", "the only one big enough for Coriolis "
              "to set its direction", HOT)]

    def swirl(colour, turns):
        c = [{"clipRect": {"left": 0, "top": 0, "right": 118, "bottom": 96}},
             paint({"color": RULE}, {"style": "fill"}),
             {"drawRect": {"left": 0, "top": 0, "right": 118, "bottom": 96}}]
        cx, cy = 59.0, 48.0
        c.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.6},
                       {"strokeCap": "round"}))
        prev = None
        for i in range(81):
            t = i / 80.0
            a = t * turns * 2 * math.pi
            r = 42.0 * (1 - t) ** 0.7
            px = cx + math.cos(a) * r
            py = cy + math.sin(a) * r * 0.78
            if prev:
                c.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": px, "y2": py}})
            prev = (px, py)
        return {"type": "canvas", "modifiers": [{"width": 118}, {"height": 96}],
                "commands": c}

    kids = [{"type": "text", "value": "Four vortices", "modifiers": [],
             "fontSize": 19.0, "color": TEXT},
            {"type": "spacer", "modifiers": [{"height": 3}]},
            {"type": "text", "value": "seven orders of magnitude apart, same structure",
             "modifiers": [], "fontSize": 11.0, "color": DIM},
            {"type": "spacer", "modifiers": [{"height": 14}]}]
    for i, (name, size, life, note, colour) in enumerate(KINDS):
        kids.append({"type": "row",
                     "modifiers": [{"width": 456}, {"padding": 9}, {"background": PANEL}],
                     "children": [
                         swirl(colour, 2.0 + i * 0.6),
                         {"type": "spacer", "modifiers": [{"width": 12}]},
                         {"type": "column", "modifiers": [{"width": 292}], "children": [
                             {"type": "row", "modifiers": [{"width": 286}], "children": [
                                 {"type": "text", "value": name, "modifiers": [],
                                  "fontSize": 13.0, "color": colour},
                                 {"type": "spacer", "modifiers": [{"width": 1}]},
                                 {"type": "text", "value": size, "modifiers": [],
                                  "fontSize": 12.0, "color": TEXT}]},
                             {"type": "spacer", "modifiers": [{"height": 3}]},
                             {"type": "text", "value": "lasts " + life, "modifiers": [],
                              "fontSize": 9.5, "color": TEXT},
                             {"type": "spacer", "modifiers": [{"height": 3}]},
                             {"type": "text", "value": note, "modifiers": [],
                              "fontSize": 9.0, "color": DIM}]}]})
        kids.append({"type": "spacer", "modifiers": [{"height": 8}]})
    kids.append({"type": "text",
                 "value": "The bath myth is worth killing: Coriolis is about ten million "
                          "times weaker than the jostle you give the water pulling the plug. "
                          "It decides a hurricane's rotation and nothing in a sink.",
                 "modifiers": [], "fontSize": 10.0, "color": TEXT})
    return {"header": header(W, H, "Four vortices from a bath drain to a hurricane with "
                                   "their sizes and lifetimes"),
            "root": {"type": "column",
                     "modifiers": ["fillMaxSize", {"padding": 18}, {"background": INK}],
                     "children": kids}}


# ── 3. BIO-ANAT-00030  Muscular system — data-plot / explain / 2D ──────────
# Force against velocity for muscle, which is the curve that explains why you cannot lift
# heavy things quickly. It is a hyperbola, not a line, and the eccentric branch going above
# maximum is the part that surprises people.
def muscle():
    W, H = 580, 520
    cmds = []
    px0, px1, py0, py1 = 80.0, 540.0, 150.0, 350.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    cx = px0 + (px1 - px0) * 0.42
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.2}))
    cmds.append({"drawLine": {"x1": cx, "y1": py0, "x2": cx, "y2": py1}})
    def force(v):
        if v >= 0:
            return max(0.0, (1.0 - v) / (1.0 + 4.0 * v))
        return min(1.55, 1.0 + 0.55 * (1 - math.exp(v * 3.0)))
    cmds.append(paint({"color": ACCENT}, {"style": "stroke"}, {"width": 2.8},
                      {"strokeCap": "round"}))
    prev = None
    for i in range(101):
        v = -0.7 + i / 100.0 * 1.7
        f = force(v)
        pt = (cx + v * (px1 - px0) * 0.34, py1 - f / 1.6 * (py1 - py0) * 0.95)
        if prev:
            cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": pt[0], "y2": pt[1]}})
        prev = pt
    for v, lbl, colour, dy in ((-0.45, "lengthening", HOT, -14),
                               (0.0, "isometric", WARM, -14),
                               (0.55, "shortening", GOOD, 16)):
        x = cx + v * (px1 - px0) * 0.34
        f = force(v)
        y = py1 - f / 1.6 * (py1 - py0) * 0.95
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": x, "cy": y, "radius": 4.5}})
        cmds += text_at(lbl, x, y + dy, 9.5, colour, pan_x=0.0)
    cmds += text_at("force", px0, py0 - 12, 10.5, DIM)
    cmds += text_at("shortening faster", px1 - 6, py1 + 20, 9.0, DIM, pan_x=1.0)
    cmds += text_at("being stretched", px0 + 6, py1 + 20, 9.0, DIM)
    y = 396.0
    for name, note, colour in (
            ("Fast means weak", "a muscle shortening quickly has fewer cross-bridges "
             "attached at any instant", GOOD),
            ("Holding is stronger than lifting", "which is why you can hold a weight you "
             "cannot raise", WARM),
            ("Lowering is strongest of all", "up to about 1.5 times maximum - and is where "
             "most training damage happens", HOT)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 80.0, "top": y - 9, "right": 85.0, "bottom": y + 5}})
        cmds += text_at(name, 96.0, y, 11.0, colour)
        cmds += text_at(note, 96.0, y + 15, 9.0, DIM)
        y += 36.0
    cmds += text_at("Illustrative of the Hill force-velocity relation; exact values vary by "
                    "muscle and species.", 80.0, 502.0, 8.5, DIM)
    title(cmds, W, H, "Why you cannot lift heavy things fast",
          "force against velocity, for one muscle")
    return {"header": header(W, H, "The muscle force-velocity curve including the eccentric "
                                   "branch above maximum force"),
            "root": canvas(cmds, INK)}


# ── 4. BIO-ANAT-00031  Nervous system — path-form / explore / 3D ───────────
# A neuron in space with a signal running down it. 3D because a neuron is not flat - the
# dendritic tree collects from a volume, and that is the whole reason one cell can integrate
# thousands of inputs.
def nervous():
    W, H = 520, 620
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.72,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [1.9, 1.0, 3.4], "center": [0.0, 0.10, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.4, -0.5, -0.76], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.3, 0.45], "intensity": 0.42}]}}]
    cmds.append(var("sig", "continuousSec() * 0.55 - floor(continuousSec() * 0.55)"))
    # soma
    cmds.append({"meshPrimitive3D": {"id": 1, "primitive": "sphere", "segments": 18,
                                     "radius": 0.17, "center": [0, 0, 0]}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "translate", "x": -0.35, "y": 0.30, "z": 0.0}},
             paint({"color": WARM}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]
    # dendrites, branching into the volume
    seed = 20261004
    def nxt():
        nonlocal seed
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        return seed / float(0x7FFFFFFF)
    verts, normals, uv, idx = [], [], [], []
    def dend(p, d, length, depth):
        if depth > 3 or length < 0.07:
            return
        q = tuple(p[k] + d[k] * length for k in range(3))
        mid = tuple((p[k] + q[k]) / 2 for k in range(3))
        oriented_box(verts, normals, uv, idx, mid, d,
                     math.sqrt(sum((q[k]-p[k])**2 for k in range(3))) / 2,
                     0.022 - depth * 0.004, 0.022 - depth * 0.004)
        for _ in range(2):
            nd = [d[k] + (nxt() - 0.5) * 1.1 for k in range(3)]
            ln = math.sqrt(sum(c * c for c in nd)) or 1.0
            dend(q, [c / ln for c in nd], length * 0.68, depth + 1)
    for base in ((-0.8, 0.5, 0.0), (-0.75, 0.0, 0.35), (-0.7, 0.55, -0.35)):
        d0 = [base[0] + 0.35, base[1] - 0.30, base[2]]
        ln = math.sqrt(sum(c * c for c in d0)) or 1.0
        dend((-0.35, 0.30, 0.0), [-c / ln for c in d0], 0.34, 0)
    cmds.append({"defineMesh3D": {"id": 2, "verts": [round(v,5) for v in verts],
                                  "normals": normals, "uv": uv, "indices": idx}})
    cmds += [{"matrix3D": {"op": "identity"}},
             paint({"color": ACCENT}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 2, "mode": "software-smooth"}}]
    # axon
    v2, n2, u2, i2 = [], [], [], []
    oriented_box(v2, n2, u2, i2, (0.35, 0.30, 0.0), (1.0, 0.0, 0.0), 0.70, 0.030, 0.030)
    cmds.append({"defineMesh3D": {"id": 3, "verts": [round(v,5) for v in v2],
                                  "normals": n2, "uv": u2, "indices": i2}})
    cmds += [{"matrix3D": {"op": "identity"}},
             paint({"color": DIM}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 3, "mode": "software-smooth"}}]
    # the action potential, travelling
    cmds.append({"meshPrimitive3D": {"id": 4, "primitive": "sphere", "segments": 12,
                                     "radius": 0.065, "center": [0, 0, 0]}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "translate", "x": "-0.35 + @sig * 1.40",
                           "y": 0.30, "z": 0.0}},
             paint({"color": HOT}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 4, "mode": "software-smooth"}}]
    cmds += text_at("dendrites collect", 100.0, 392.0, 9.5, ACCENT, pan_x=0.0)
    cmds += text_at("axon carries", 390.0, 392.0, 9.5, DIM, pan_x=1.0)
    y = 436.0
    for name, note, colour in (
            ("Thousands in, one out", "a cortical neuron takes input from up to ten thousand "
             "others and emits a single train", ACCENT),
            ("All or nothing", "the spike does not get bigger with a stronger input - the "
             "rate does", HOT),
            ("Speed needs insulation", "a myelinated axon runs at 100 m/s, a bare one at "
             "about 1", GOOD),
            ("It is a volume, not a diagram", "the dendritic tree samples a region of tissue, "
             "which a flat drawing hides", WARM)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 36.0, "top": y - 9, "right": 41.0, "bottom": y + 5}})
        cmds += text_at(name, 52.0, y, 11.0, colour)
        cmds += text_at(note, 52.0, y + 15, 8.5, DIM)
        y += 38.0
    title(cmds, W, H, "One neuron", "a tree that collects and a cable that sends")
    return {"header": header(W, H, "A neuron in 3D with a branching dendritic tree and an "
                                   "action potential travelling down the axon"),
            "root": canvas(cmds, INK)}


# ── 5. BIO-ANAT-00032  Cardiovascular system — expression-animation / compare ─
# Pressure through the circuit, from aorta to vena cava, with the heartbeat running. The
# collapse across the arterioles is where almost all the resistance lives, which is why they
# and not the heart set blood pressure.
def cardiovascular():
    W, H = 600, 500
    STAGES = [("Aorta", 100, 120, GOOD), ("Arteries", 95, 115, GOOD),
              ("Arterioles", 45, 70, HOT), ("Capillaries", 20, 32, WARM),
              ("Venules", 12, 16, ACCENT), ("Veins", 6, 9, ACCENT),
              ("Vena cava", 3, 5, DIM)]
    cmds = [var("beat", "0.5 + 0.5 * sin(continuousSec() * 7.3)")]
    px0, px1, py0, py1 = 80.0, 540.0, 150.0, 340.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    n = len(STAGES)
    for i, (name, lo, hi, colour) in enumerate(STAGES):
        x0 = px0 + (px1 - px0) * i / n
        x1 = px0 + (px1 - px0) * (i + 1) / n
        ylo = py1 - lo / 130.0 * (py1 - py0)
        yhi = py1 - hi / 130.0 * (py1 - py0)
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0 + 2, "top": yhi, "right": x1 - 2, "bottom": ylo}})
        cmds += text_at(name, (x0 + x1) / 2, py1 + 18, 8.0, colour, pan_x=0.0)
        cmds += text_at("%d" % hi, (x0 + x1) / 2, yhi - 5, 8.0, TEXT, pan_x=0.0)
    # the live pressure trace, pulsing
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 2.0}))
    for i in range(n):
        x0 = px0 + (px1 - px0) * (i + 0.5) / n
        lo, hi = STAGES[i][1], STAGES[i][2]
        cmds.append({"drawCircle": {
            "cx": x0,
            "cy": "%.1f - (%.1f + @beat * %.1f) / 130.0 * %.1f" % (py1, lo, hi - lo, py1 - py0),
            "radius": 3.4}})
    cmds += text_at("pressure, mmHg", px0, py0 - 12, 10.5, DIM)
    cmds.append(paint({"color": HOT}, {"style": "stroke"}, {"width": 1.2}))
    ax = px0 + (px1 - px0) * 2.0 / n
    bx = px0 + (px1 - px0) * 3.0 / n
    cmds.append({"drawLine": {"x1": ax, "y1": py0 + 10, "x2": bx, "y2": py0 + 10}})
    cmds += text_at("most of the pressure is lost here", (ax + bx) / 2, py0 + 4, 9.0, HOT,
                    pan_x=0.0)
    y = 392.0
    for name, note, colour in (
            ("Arterioles are the taps", "they carry most of the resistance, so dilating or "
             "constricting them sets blood pressure", HOT),
            ("The pulse dies at the capillaries", "which is why they are not torn apart "
             "sixty times a minute", WARM),
            ("Veins are a reservoir", "about two thirds of the blood sits in them at any "
             "moment, at very low pressure", ACCENT)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 80.0, "top": y - 9, "right": 85.0, "bottom": y + 5}})
        cmds += text_at(name, 96.0, y, 11.0, colour)
        cmds += text_at(note, 96.0, y + 15, 9.0, DIM)
        y += 34.0
    title(cmds, W, H, "Pressure round the circuit", "beating, from aorta to vena cava")
    return {"header": header(W, H, "Blood pressure through the circulation with the pulse "
                                   "running and the arteriolar drop marked"),
            "root": canvas(cmds, INK)}


# ── 6. BIO-ANAT-00033  Respiratory system — particle-system / demonstrate ──
# Oxygen molecules crossing the alveolar membrane, with the surface area stated. The number
# is the point: the lung's job is done by making a very large area out of a very small
# volume, and the particles make the crossing visible.
def respiratory():
    W, H = 560, 560
    cmds = []
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": 40.0, "top": 140.0, "right": 520.0, "bottom": 380.0}})
    # the membrane
    cmds.append(paint({"color": RULE}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": 40.0, "top": 256.0, "right": 520.0, "bottom": 264.0}})
    cmds += text_at("alveolar wall, half a micrometre thick", 280.0, 252.0, 9.0, DIM,
                    pan_x=0.0)
    cmds += text_at("air", 60.0, 170.0, 11.0, ACCENT)
    cmds += text_at("blood", 60.0, 362.0, 11.0, HOT)
    # oxygen crossing down, carbon dioxide crossing up
    for name, colour, y0, dirn, cid in (("O2", ACCENT, 150.0, 1, "ox"),
                                        ("CO2", HOT, 270.0, -1, "co")):
        cmds.append({"createParticles": {
            "id": cid, "count": 60,
            "variables": ["gx", "gy", "gv", "gp"],
            "initialValues": ["60 + rand() * 440", "%.1f + rand() * 100.0" % y0,
                              "0.5 + rand() * 1.3", "rand() * 6.28"]}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"particlesLoop": {
            "system": "@" + cid,
            "equations": ["gx + sin(gp) * 0.4",
                          "%.1f + ((gy - %.1f + gv * %d) %% 100)" % (y0, y0, dirn),
                          "gv", "gp + 0.04"],
            "commands": [{"drawCircle": {"cx": "@gx", "cy": "@gy", "radius": 2.4}}]}})
    y = 410.0
    for val, lbl, colour in (("70 m²", "surface area for gas exchange - about a tennis court",
                              GOOD),
                             ("0.5 µm", "the distance a molecule has to cross", ACCENT),
                             ("480 million", "alveoli, in a volume of about six litres", WARM),
                             ("0.25 s", "the time a red cell spends in a capillary; the "
                              "transfer finishes in a third of that", HOT)):
        cmds += text_at(val, 40.0, y, 13.0, colour)
        cmds += text_at(lbl, 170.0, y, 9.5, DIM)
        y += 26.0
    cmds += text_at("The lung's whole design problem is packing a tennis court into a chest.",
                    40.0, 524.0, 11.0, TEXT)
    cmds += text_at("- emphysema destroys the walls between alveoli, which loses area "
                    "without losing volume.", 40.0, 542.0, 10.0, DIM)
    title(cmds, W, H, "Across the membrane", "oxygen in, carbon dioxide out")
    return {"header": header(W, H, "Oxygen and carbon dioxide crossing the alveolar membrane "
                                   "as particles, with the lung's dimensions"),
            "root": canvas(cmds, INK)}


# ── 7. MTH-TRIG-00014  Waves — interactive / simulate / 2D ─────────────────
# Drag the phase between two waves and watch the sum. Interference is not a special effect;
# it is addition, and the drag makes that literal by letting the reader run it from complete
# reinforcement to complete cancellation.
def waves():
    W, H = 580, 560
    cmds = [{"touchExpression": {"name": "drag", "defaultValue": 120.0, "min": 60.0,
                                 "max": 520.0, "expression": "touchX()"}},
            var("ph", "(@drag - 60.0) / 460.0 * 6.2832")]
    px0, px1 = 70.0, 540.0
    for row, (name, colour, y) in enumerate((("wave A", GOOD, 190.0),
                                             ("wave B", ACCENT, 280.0),
                                             ("A + B", WARM, 390.0))):
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": px0, "top": y - 52, "right": px1, "bottom": y + 52}})
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 0.8}))
        cmds.append({"drawLine": {"x1": px0, "y1": y, "x2": px1, "y2": y}})
        cmds += text_at(name, px0 + 8, y - 38, 10.0, colour)
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.2},
                          {"strokeCap": "round"}))
        N = 90
        for i in range(N):
            u0 = i / float(N)
            u1 = (i + 1) / float(N)
            x0 = px0 + (px1 - px0) * u0
            x1 = px0 + (px1 - px0) * u1
            if row == 0:
                e0 = "%.4f - sin(%.4f) * 40.0" % (y, u0 * 12.566)
                e1 = "%.4f - sin(%.4f) * 40.0" % (y, u1 * 12.566)
            elif row == 1:
                e0 = "%.4f - sin(%.4f + @ph) * 40.0" % (y, u0 * 12.566)
                e1 = "%.4f - sin(%.4f + @ph) * 40.0" % (y, u1 * 12.566)
            else:
                e0 = "%.4f - (sin(%.4f) + sin(%.4f + @ph)) * 24.0" % (y, u0 * 12.566,
                                                                      u0 * 12.566)
                e1 = "%.4f - (sin(%.4f) + sin(%.4f + @ph)) * 24.0" % (y, u1 * 12.566,
                                                                      u1 * 12.566)
            cmds.append({"drawLine": {"x1": round(x0, 1), "y1": e0,
                                      "x2": round(x1, 1), "y2": e1}})
    cmds += [{"variable": {"name": "deg", "commit": True,
                           "value": {"type": "textFromFloat", "value": "@ph * 57.2958",
                                     "whole": 3, "decimal": 0}}},
             paint({"color": TEXT}, {"style": "fill"}, {"textSize": 15.0}),
             {"drawTextAnchored": {"text": "@deg", "x": 70.0, "y": 474.0,
                                   "panX": -1.0, "panY": 0.0, "flags": 0}}]
    cmds += text_at("degrees out of phase", 126.0, 474.0, 10.5, DIM)
    cmds.append({"conditionalOperations": {
        "condition": "lt", "v1": "@ph", "v2": 0.7,
        "commands": [paint({"color": GOOD}, {"style": "fill"}, {"textSize": 11.0}),
                     {"drawTextAnchored": {"text": "in step - the sum is twice either one",
                                           "x": 290.0, "y": 474.0, "panX": -1.0,
                                           "panY": 0.0, "flags": 0}}]}})
    cmds.append({"conditionalOperations": {
        "condition": "gt", "v1": "@ph", "v2": 2.6,
        "commands": [{"conditionalOperations": {
            "condition": "lt", "v1": "@ph", "v2": 3.7,
            "commands": [paint({"color": HOT}, {"style": "fill"}, {"textSize": 11.0}),
                         {"drawTextAnchored": {
                             "text": "opposed - they cancel, and the energy went elsewhere",
                             "x": 290.0, "y": 474.0, "panX": -1.0, "panY": 0.0,
                             "flags": 0}}]}}]}})
    cmds += text_at("Cancellation does not destroy energy. Where two waves cancel, another "
                    "place gets double -", 70.0, 510.0, 10.5, TEXT)
    cmds += text_at("which is why noise-cancelling headphones work at your ear and nowhere "
                    "else in the room.", 70.0, 526.0, 10.0, DIM)
    cmds += text_at("drag to change the phase", 70.0, 548.0, 9.0, DIM)
    title(cmds, W, H, "Two waves adding", "drag to slide one against the other")
    return {"header": header(W, H, "Two sine waves and their sum, with the phase between "
                                   "them draggable from in-step to opposed"),
            "root": canvas(cmds, INK)}


# ── 8. CSC-CA-00012  GPU — raster-and-text / analyze / 2D ──────────────────
# A CPU and a GPU drawn to the same scale, by what the silicon is spent on. The GPU is not a
# faster CPU; it is a different allocation, and the picture of the two die budgets says so
# better than any benchmark.
def gpu():
    W, H = 600, 500
    CPU = [("Cores (8 big)", 0.22, GOOD), ("Cache", 0.40, ACCENT),
           ("Branch prediction, scheduling", 0.26, WARM), ("Memory controller", 0.12, DIM)]
    GPU = [("Cores (10,000 small)", 0.72, GOOD), ("Cache", 0.10, ACCENT),
           ("Scheduling", 0.06, WARM), ("Memory controller", 0.12, DIM)]
    cmds = []
    for col, (name, parts, note) in enumerate((("CPU", CPU, "optimised for one thread "
                                                "finishing fast"),
                                               ("GPU", GPU, "optimised for ten thousand "
                                                "threads finishing eventually"))):
        x0 = 60.0 + col * 250.0
        cmds += text_at(name, x0 + 100, 150.0, 15.0, TEXT, pan_x=0.0)
        cmds += text_at(note, x0 + 100, 168.0, 8.5, DIM, pan_x=0.0)
        y = 186.0
        for pname, frac, colour in parts:
            h = frac * 190.0
            cmds.append(paint({"color": colour}, {"style": "fill"}))
            cmds.append({"drawRect": {"left": x0, "top": y, "right": x0 + 200,
                                      "bottom": y + h - 2}})
            if h > 20:
                cmds += text_at(pname, x0 + 8, y + h / 2 + 4, 9.0, INK)
                cmds += text_at("%d%%" % int(frac * 100), x0 + 192, y + h / 2 + 4, 9.0,
                                INK, pan_x=1.0)
            y += h
    cmds += text_at("die area", 44.0, 186.0, 9.5, DIM, pan_x=1.0)
    y = 416.0
    for name, note, colour in (
            ("Same transistor budget", "both pictures are the same height; only the "
             "allocation differs", TEXT),
            ("A GPU core is weak on purpose", "no branch prediction, tiny cache, and it "
             "stalls constantly - but there are thousands", GOOD),
            ("Which is why it needs the right problem", "ten thousand independent pieces of "
             "work, or most of the chip idles", HOT)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 60.0, "top": y - 9, "right": 65.0, "bottom": y + 5}})
        cmds += text_at(name, 76.0, y, 10.5, colour)
        cmds += text_at(note, 76.0, y + 14, 8.5, DIM)
        y += 30.0
    cmds += text_at("Proportions are illustrative of the design philosophy, not a floorplan "
                    "of any particular chip.", 60.0, 486.0, 8.0, DIM)
    title(cmds, W, H, "Two ways to spend a die", "the same silicon, different bets")
    return {"header": header(W, H, "CPU and GPU die area budgets drawn to the same scale, "
                                   "showing the different allocation"),
            "root": canvas(cmds, INK)}


# ── 9. CHM-CR-00012  Equilibrium — static-diagram / analyze / 2D ───────────
# Forward and reverse rates meeting, with concentrations beside them. Equilibrium is not the
# reaction stopping - both rates are still high, they are just equal, and the flat lines on
# the right say so.
def equilibrium():
    W, H = 600, 480
    cmds = []
    px0, px1, py0, py1 = 70.0, 320.0, 150.0, 330.0
    qx0, qx1 = 350.0, 540.0
    for x0, x1, title_s in ((px0, px1, "rates"), (qx0, qx1, "concentrations")):
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": py0, "right": x1, "bottom": py1}})
        cmds += text_at(title_s, x0, py0 - 12, 10.5, DIM)
    def fwd(t):
        return 1.0 * math.exp(-t * 2.4) * 0.55 + 0.45
    def rev(t):
        return 0.45 * (1 - math.exp(-t * 2.4))
    for fn, colour, lbl in ((fwd, GOOD, "forward"), (rev, HOT, "reverse")):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6},
                          {"strokeCap": "round"}))
        prev = None
        for i in range(81):
            t = i / 80.0 * 3.0
            pt = (px0 + (px1 - px0) * t / 3.0, py1 - fn(t) * (py1 - py0) * 0.95)
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": pt[0],
                                          "y2": pt[1]}})
            prev = pt
        cmds += text_at(lbl, px1 - 6, prev[1] - 8, 9.5, colour, pan_x=1.0)
    def ca(t):
        return 1.0 - 0.62 * (1 - math.exp(-t * 2.4))
    def cb(t):
        return 0.62 * (1 - math.exp(-t * 2.4))
    for fn, colour, lbl in ((ca, ACCENT, "A"), (cb, WARM, "B")):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6},
                          {"strokeCap": "round"}))
        prev = None
        for i in range(81):
            t = i / 80.0 * 3.0
            pt = (qx0 + (qx1 - qx0) * t / 3.0, py1 - fn(t) * (py1 - py0) * 0.95)
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": pt[0],
                                          "y2": pt[1]}})
            prev = pt
        cmds += text_at(lbl, qx1 - 6, prev[1] - 8, 10.0, colour, pan_x=1.0)
    ex = px0 + (px1 - px0) * 0.62
    for x in (ex, qx0 + (qx1 - qx0) * 0.62):
        cmds.append(paint({"color": DIM}, {"style": "stroke"}, {"width": 1.2}))
        cmds.append({"drawLine": {"x1": x, "y1": py0, "x2": x, "y2": py1}})
    cmds += text_at("equilibrium from about here", ex + 6, py0 + 16, 9.0, DIM)
    y = 372.0
    for name, note, colour in (
            ("Nothing has stopped", "both reactions are still running at the same high rate "
             "- they have only become equal", GOOD),
            ("Which is why it is dynamic", "label an atom and it will move back and forth "
             "across the equilibrium all day", ACCENT),
            ("And why disturbing it works", "remove B and the reverse rate drops, the forward "
             "one wins, and the system shifts", WARM)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 70.0, "top": y - 9, "right": 75.0, "bottom": y + 5}})
        cmds += text_at(name, 86.0, y, 11.0, colour)
        cmds += text_at(note, 86.0, y + 14, 9.0, DIM)
        y += 32.0
    title(cmds, W, H, "What equilibrium is", "equal rates, not no reaction")
    return {"header": header(W, H, "Forward and reverse reaction rates converging beside the "
                                   "concentrations they produce"),
            "root": canvas(cmds, INK)}


# ── 10. EAR-METE-00012  Clouds — annotated-layout / explain / 2D ───────────
# Cloud types by altitude, in one column, with what each one tells you. A cloud is a weather
# instrument you can read without equipment, and the altitude is most of the reading.
def clouds():
    W, H = 520, 640
    TYPES = [("Cirrus", 10000, "ice crystals; warm front coming in a day or so", DIM),
             ("Cirrostratus", 8000, "halo round the sun; rain within 24 hours", DIM),
             ("Altostratus", 5000, "sun as a dim disc; rain is close", ACCENT),
             ("Cumulus", 1500, "fair weather, if they stay small", GOOD),
             ("Stratus", 800, "flat grey; drizzle at worst", ACCENT),
             ("Cumulonimbus", 1000, "the only one that is genuinely dangerous", HOT)]
    cmds = []
    px0, px1, py0, py1 = 60.0, 300.0, 150.0, 480.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    for alt in (0, 2000, 4000, 6000, 8000, 10000, 12000):
        y = py1 - alt / 12000.0 * (py1 - py0)
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 0.7}))
        cmds.append({"drawLine": {"x1": px0, "y1": y, "x2": px1, "y2": y}})
        cmds += text_at("%d m" % alt, px0 - 6, y + 4, 8.0, DIM, pan_x=1.0)
    for name, alt, note, colour in TYPES:
        y = py1 - alt / 12000.0 * (py1 - py0)
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        if name == "Cumulonimbus":
            cmds.append({"drawRect": {"left": px0 + 150, "top": py1 - 11000 / 12000.0 * (py1 - py0),
                                      "right": px0 + 210, "bottom": py1 - 60}})
            cmds.append({"drawOval": {"left": px0 + 130, "top": py1 - 11600 / 12000.0 * (py1 - py0),
                                      "right": px0 + 230,
                                      "bottom": py1 - 10200 / 12000.0 * (py1 - py0)}})
        elif "Cumulus" in name:
            for k in range(3):
                cmds.append({"drawOval": {"left": px0 + 30 + k * 22, "top": y - 14,
                                          "right": px0 + 62 + k * 22, "bottom": y + 10}})
        else:
            cmds.append({"drawRect": {"left": px0 + 14, "top": y - 5,
                                      "right": px0 + 120, "bottom": y + 4}})
    y = 160.0
    for name, alt, note, colour in TYPES:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 320.0, "top": y - 8, "right": 332.0, "bottom": y + 4}})
        cmds += text_at(name, 342.0, y, 11.0, colour)
        cmds += text_at("%d m" % alt, 480.0, y, 9.0, TEXT, pan_x=1.0)
        for wi, w in enumerate(_wrap12(note, 26)):
            cmds += text_at(w, 342.0, y + 14 + wi * 11, 8.5, DIM)
        y += 54.0
    cmds += text_at("High and wispy means a front is coming but not yet. Tall and "
                    "cauliflower-shaped means now.", 60.0, 520.0, 10.5, TEXT)
    cmds += text_at("- the anvil on a cumulonimbus is the top hitting the stratosphere and "
                    "spreading sideways, which is", 60.0, 538.0, 9.5, DIM)
    cmds += text_at("the single most useful shape to recognise in the sky.", 60.0, 554.0,
                    9.5, DIM)
    title(cmds, W, H, "Reading the sky", "altitude is most of the diagnosis")
    return {"header": header(W, H, "Six cloud types placed by altitude with what each one "
                                   "indicates about coming weather"),
            "root": canvas(cmds, INK)}


def _wrap12(text, n):
    out, line = [], ""
    for w in text.split():
        if len(line) + len(w) + 1 > n:
            out.append(line); line = w
        else:
            line = (line + " " + w).strip()
    if line: out.append(line)
    return out


# ── 11. ENG-CE-00012  Bridges — data-plot / explore / 3D ───────────────────
# Three bridge types as 3D forms with their spans. Each one is a different answer to the same
# question - how to get the load into the ground - and the span each can reach follows from
# whether its members are in tension or compression.
def bridges():
    W, H = 540, 620
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.70,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          # Looking down from in front, so the three sit as three separate
                          # rows instead of piling on top of each other. At the old eye the
                          # beam's deck crossed the arch, the arch crossed the suspension,
                          # and the beam's piers ran down into the legend.
                          "eye": [0.0, 3.07, 4.68], "center": [0.0, -0.30, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.42, -0.55, -0.72], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.3, 0.45], "intensity": 0.42}]}}]
    # A smaller swing than before: the framing above is tight, and at 0.42 rad
    # the outer bridges swung past the page edge at the ends of the turn.
    cmds.append(var("spin", "sin(continuousSec() * 0.2) * 0.22"))
    mid = 10
    # Beam nearest, suspension farthest, and not the other way round. Ordering them to
    # match the legend reads better on paper and is wrong in the picture: the suspension
    # bridge is the only tall one, so in front its towers stand over the other two and hide
    # them. Flat thing in front, tall thing behind.
    for bi, (kind, zoff, colour) in enumerate((("beam", 0.52, HOT), ("arch", 0.0, WARM),
                                               ("suspension", -0.52, GOOD))):
        verts, normals, uv, idx = [], [], [], []
        # deck
        mesh_box(verts, normals, uv, idx, (-0.85, -0.02, zoff - 0.09),
                 (0.85, 0.02, zoff + 0.09))
        if kind == "beam":
            for px in (-0.85, -0.28, 0.28, 0.85):
                mesh_box(verts, normals, uv, idx, (px - 0.05, -0.42, zoff - 0.05),
                         (px + 0.05, -0.02, zoff + 0.05))
        elif kind == "arch":
            for k in range(16):
                t0, t1 = k / 16.0, (k + 1) / 16.0
                def arch_pt(t):
                    x = -0.85 + t * 1.7
                    y = -0.42 + 0.40 * math.sin(math.pi * t)
                    return (x, y, zoff)
                A, B = arch_pt(t0), arch_pt(t1)
                m = tuple((A[k2] + B[k2]) / 2 for k2 in range(3))
                ax = tuple(B[k2] - A[k2] for k2 in range(3))
                oriented_box(verts, normals, uv, idx, m, ax,
                             math.sqrt(sum(c * c for c in ax)) / 2, 0.035, 0.035)
        else:
            # The old cable was wrong in three ways at once, and the drawing showed all
            # three: the sag term put mid-span at y = -0.06, which is UNDER the deck; past
            # the towers it was clamped flat at tower-top height instead of descending, so
            # each tower read as an upside-down L with a bar sticking out sideways; and
            # there were no hangers, which are the one feature that says "suspension".
            #
            # What it should be: a parabola slung between the tower tops, sagging to just
            # above the deck, straight back-stays running down to anchorages at deck level,
            # and the deck hung from the cable rather than resting on anything.
            TOWER_X, TOP, SAG, ANCHOR = 0.45, 0.46, 0.10, 0.0

            def cable_y(x):
                if abs(x) <= TOWER_X:
                    return SAG + (TOP - SAG) * (x / TOWER_X) ** 2
                t = (abs(x) - TOWER_X) / (0.85 - TOWER_X)
                return TOP + (ANCHOR - TOP) * t

            for px in (-TOWER_X, TOWER_X):
                mesh_box(verts, normals, uv, idx, (px - 0.04, -0.02, zoff - 0.04),
                         (px + 0.04, TOP, zoff + 0.04))
            N = 28
            for k in range(N):
                xa = -0.85 + 1.7 * k / N
                xb = -0.85 + 1.7 * (k + 1) / N
                A, B = (xa, cable_y(xa), zoff), (xb, cable_y(xb), zoff)
                m = tuple((A[k2] + B[k2]) / 2 for k2 in range(3))
                ax = tuple(B[k2] - A[k2] for k2 in range(3))
                L = math.sqrt(sum(c * c for c in ax))
                if L > 1e-5:
                    oriented_box(verts, normals, uv, idx, m, ax, L / 2, 0.016, 0.016)
            # the hangers: the deck is held up by these, which is the whole mechanism
            for k in range(1, 8):
                hx = -TOWER_X + 2 * TOWER_X * k / 8.0
                hy = cable_y(hx)
                if hy > 0.05:
                    mesh_box(verts, normals, uv, idx, (hx - 0.011, 0.02, zoff - 0.011),
                             (hx + 0.011, hy, zoff + 0.011))
        cmds.append({"defineMesh3D": {"id": mid, "verts": [round(v, 5) for v in verts],
                                      "normals": normals, "uv": uv, "indices": idx}})
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mid, "mode": "software-smooth"}}]
        mid += 1
    y = 418.0
    for name, span, how, colour in (
            ("Beam", "up to 80 m", "the deck itself bends; doubling the span costs eight "
             "times the stiffness", HOT),
            ("Arch", "up to 550 m", "the load goes into compression and out through the "
             "abutments - needs solid rock", WARM),
            ("Suspension", "up to 2,000 m", "the cable is in pure tension, and steel is "
             "strongest in tension", GOOD)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 36.0, "top": y - 9, "right": 41.0, "bottom": y + 5}})
        cmds += text_at(name, 52.0, y, 12.0, colour)
        cmds += text_at(span, 230.0, y, 10.5, TEXT, pan_x=1.0)
        cmds += text_at(how, 52.0, y + 15, 8.5, DIM)
        y += 40.0
    cmds += text_at("Each type is a different answer to one question: how does the load get "
                    "into the ground?", 36.0, 554.0, 10.5, TEXT)
    cmds += text_at("- and the span each can reach follows from whether its main members are "
                    "pushed or pulled.", 36.0, 572.0, 9.5, DIM)
    title(cmds, W, H, "Three bridges", "beam, arch, suspension")
    return {"header": header(W, H, "Beam, arch and suspension bridges as 3D forms with the "
                                   "spans each structural type can reach"),
            "root": canvas(cmds, INK)}


# ── 12. ECO-FE-00016  Markets — path-form / compare / 2D ───────────────────
# The same index drawn on a linear and a log axis. The pair is the argument: on a linear
# axis the recent decades dwarf everything; on a log axis 1929 and 2008 are finally the same
# size as each other, which is what a percentage loss means.
def markets():
    W, H = 600, 540
    import math as _m
    YEARS = list(range(1920, 2026, 2))
    def idx(y):
        base = 1.0 * (1.065 ** (y - 1920))
        if 1929 <= y <= 1932: base *= 0.28 + 0.2 * (y - 1929)
        if 1973 <= y <= 1975: base *= 0.62
        if 2000 <= y <= 2002: base *= 0.58
        if 2008 <= y <= 2009: base *= 0.55
        return base
    vals = [idx(y) for y in YEARS]
    cmds = []
    for row, (logaxis, name, y0, y1, colour) in enumerate(
            ((False, "linear", 150.0, 290.0, WARM), (True, "logarithmic", 320.0, 450.0, GOOD))):
        px0, px1 = 70.0, 540.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": px0, "top": y0, "right": px1, "bottom": y1}})
        if logaxis:
            lo, hi = _m.log10(min(vals)), _m.log10(max(vals))
        else:
            lo, hi = 0.0, max(vals)
        pid = "mk%d" % row
        pts = []
        for i, (yr, v) in enumerate(zip(YEARS, vals)):
            vv = _m.log10(v) if logaxis else v
            pts.append((px0 + (px1 - px0) * i / (len(YEARS) - 1.0),
                        y1 - (vv - lo) / (hi - lo) * (y1 - y0) * 0.92 - 5))
        cmds.append({"pathCreate": {"id": pid, "x": round(pts[0][0],1), "y": round(pts[0][1],1)}})
        for (x, yy) in pts[1:]:
            cmds.append({"pathAppendLineTo": {"path": pid, "x": round(x,1), "y": round(yy,1)}})
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.2},
                          {"strokeCap": "round"}))
        cmds.append({"drawPath": {"path": pid}})
        cmds += text_at(name + " axis", px0 + 8, y0 + 16, 10.0, colour)
        for yr in (1929, 1973, 2000, 2008):
            i = (yr - 1920) // 2
            x = px0 + (px1 - px0) * i / (len(YEARS) - 1.0)
            cmds.append(paint({"color": HOT}, {"style": "stroke"}, {"width": 0.8}))
            cmds.append({"drawLine": {"x1": x, "y1": y0, "x2": x, "y2": y1}})
            if row == 1:
                cmds += text_at("%d" % yr, x, y1 + 16, 8.5, HOT, pan_x=0.0)
    cmds += text_at("On the linear axis the 1929 crash is invisible. On the log axis it is "
                    "the biggest event there.", 70.0, 486.0, 10.5, TEXT)
    cmds += text_at("- a log axis shows equal percentage moves as equal distances, which is "
                    "the only fair way to compare", 70.0, 504.0, 9.5, DIM)
    cmds += text_at("a crash in 1929 with one in 2008. Series is schematic, not real index "
                    "data.", 70.0, 520.0, 9.5, DIM)
    title(cmds, W, H, "The same century, two axes", "and only one of them is honest")
    return {"header": header(W, H, "A schematic market index on linear and logarithmic axes, "
                                   "showing how the axis choice hides or reveals crashes"),
            "root": canvas(cmds, INK)}


# ── 13. ECO-FE-00017  Risk — expression-animation / demonstrate / 2D ───────
# Two portfolios with the same average return, running side by side. Same mean, different
# variance, and the one that swings takes longer to recover - which is the whole reason
# volatility is treated as a cost rather than a curiosity.
def risk():
    W, H = 580, 540
    cmds = [var("t", "continuousSec() * 0.1 - floor(continuousSec() * 0.1)")]
    px0, px1, py0, py1 = 70.0, 540.0, 150.0, 350.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    seed = 20261005
    def nxt():
        nonlocal seed
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        return seed / float(0x7FFFFFFF)
    N = 60
    shocks = [nxt() - 0.5 for _ in range(N)]
    for vol, colour, lbl in ((0.04, GOOD, "steady, 7% a year"),
                             (0.22, HOT, "volatile, 7% a year")):
        v = 1.0
        pts = []
        for i in range(N):
            v *= (1.0 + 0.07 / 12 + shocks[i] * vol)
            pts.append(v)
        mx = 3.2
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.4},
                          {"strokeCap": "round"}))
        prev = None
        for i, pv in enumerate(pts):
            pt = (px0 + (px1 - px0) * i / (N - 1.0),
                  py1 - min(1.0, pv / mx) * (py1 - py0) * 0.95)
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": pt[0],
                                          "y2": pt[1]}})
            prev = pt
        cmds += text_at(lbl, px1 - 6, prev[1] - 8, 9.5, colour, pan_x=1.0)
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.4}))
    cmds.append({"drawLine": {"x1": "%.1f + @t * %.1f" % (px0, px1 - px0), "y1": py0,
                              "x2": "%.1f + @t * %.1f" % (px0, px1 - px0), "y2": py1}})
    cmds += text_at("value", px0, py0 - 12, 10.5, DIM)
    cmds += text_at("five years", (px0 + px1) / 2, py1 + 20, 10.0, DIM, pan_x=0.0)
    y = 392.0
    for name, note, colour in (
            ("Same expected return", "both are drawn with the same 7% a year expectation",
             TEXT),
            ("Different experience", "the volatile one spends long stretches below where it "
             "started", HOT),
            ("And a real cost", "a 50% fall needs a 100% rise to get back, so swings drag "
             "the compounded result down", WARM),
            ("Which is why risk is priced", "an investor will take a lower expected return "
             "for a smoother path, and does", GOOD)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 70.0, "top": y - 9, "right": 75.0, "bottom": y + 5}})
        cmds += text_at(name, 86.0, y, 11.0, colour)
        cmds += text_at(note, 86.0, y + 14, 9.0, DIM)
        y += 32.0
    cmds += text_at("Paths are generated from a fixed seed, not from market data.",
                    70.0, 522.0, 8.5, DIM)
    title(cmds, W, H, "Same return, different ride", "volatility is a cost, not a flavour")
    return {"header": header(W, H, "Two portfolios with the same expected return and "
                                   "different volatility, on one clock"),
            "root": canvas(cmds, INK)}


# ── 14. ECO-FE-00018  Portfolio theory — particle-system / simulate / 2D ───
# Thousands of random portfolios as particles in risk-return space, with the efficient
# frontier emerging as their upper edge. The frontier is not drawn and then justified; it is
# where the cloud happens to stop.
def portfolio():
    W, H = 580, 540
    cmds = []
    px0, px1, py0, py1 = 80.0, 540.0, 150.0, 370.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    cmds.append({"createParticles": {
        "id": "ports", "count": 320,
        "variables": ["w", "jit", "ph", "sp"],
        "initialValues": ["rand()", "rand()", "rand() * 6.28", "0.2 + rand() * 0.6"]}})
    cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
    # risk and return for a two-asset mix, with the cloud filling below the frontier
    cmds.append({"particlesLoop": {
        "system": "@ports",
        "equations": ["w", "jit", "ph + 0.01", "sp"],
        "commands": [{"drawCircle": {
            "cx": "%.1f + (0.12 + @w * @w * 0.55 + (1.0 - @w) * 0.18) * %.1f"
                  % (px0, (px1 - px0) * 1.05),
            "cy": "%.1f - (0.04 + @w * 0.09) * @jit * %.1f" % (py1, (py1 - py0) * 9.0),
            "radius": 1.8}}]}})
    # the frontier itself, drawn over the cloud
    cmds.append(paint({"color": GOOD}, {"style": "stroke"}, {"width": 2.4},
                      {"strokeCap": "round"}))
    prev = None
    for i in range(61):
        w = i / 60.0
        risk_v = 0.12 + w * w * 0.55 + (1 - w) * 0.18
        ret_v = 0.04 + w * 0.09
        pt = (px0 + risk_v * (px1 - px0) * 1.05, py1 - ret_v * (py1 - py0) * 9.0)
        if prev:
            cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": pt[0], "y2": pt[1]}})
        prev = pt
    cmds += text_at("the efficient frontier", px0 + 180, py0 + 26, 10.0, GOOD)
    cmds += text_at("return", px0, py0 - 12, 10.5, DIM)
    cmds += text_at("risk", (px0 + px1) / 2, py1 + 20, 10.0, DIM, pan_x=0.0)
    y = 410.0
    for name, note, colour in (
            ("Every dot is a portfolio", "a different mix of the same two assets", ACCENT),
            ("The frontier is just the edge", "for any level of risk, the best return "
             "available - nothing above it exists", GOOD),
            ("Below it is waste", "a portfolio inside the cloud takes risk it is not being "
             "paid for", HOT),
            ("Diversification bends it left", "mixing imperfectly correlated assets reduces "
             "risk without reducing return", WARM)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 80.0, "top": y - 9, "right": 85.0, "bottom": y + 5}})
        cmds += text_at(name, 96.0, y, 11.0, colour)
        cmds += text_at(note, 96.0, y + 14, 9.0, DIM)
        y += 30.0
    title(cmds, W, H, "Where the frontier comes from",
          "it is the edge of the cloud, not a theory")
    return {"header": header(W, H, "Random portfolios as particles in risk-return space with "
                                   "the efficient frontier as their upper edge"),
            "root": canvas(cmds, INK)}


# ── 15. ECO-FE-00019  Asset pricing — interactive / analyze / 2D ───────────
# Drag the discount rate and watch what a stream of future cash is worth today. The sensitivity
# is the lesson: a small change in the rate moves long-dated value enormously, which is why
# interest rate news moves growth stocks more than anything they actually did.
def asset_pricing():
    W, H = 580, 560
    cmds = [{"touchExpression": {"name": "drag", "defaultValue": 160.0, "min": 60.0,
                                 "max": 520.0, "expression": "touchX()"}},
            var("r", "0.01 + (@drag - 60.0) / 460.0 * 0.14")]
    px0, px1, py0, py1 = 70.0, 540.0, 150.0, 350.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    N = 20
    bw = (px1 - px0) / N
    for i in range(N):
        x = px0 + i * bw
        yr = i + 1
        cmds.append(paint({"color": RULE}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x + 2, "top": py1 - 150, "right": x + bw - 2,
                                  "bottom": py1}})
        cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
        cmds.append({"drawRect": {
            "left": x + 2,
            "top": "%.1f - 150.0 / pow(1.0 + @r, %d.0)" % (py1, yr),
            "right": x + bw - 2, "bottom": py1}})
    cmds += text_at("value today of 100 received in year n", px0 + 8, py0 + 18, 10.0, DIM)
    for yr in (1, 5, 10, 15, 20):
        cmds += text_at("%d" % yr, px0 + (yr - 0.5) * bw, py1 + 20, 9.0, DIM, pan_x=0.0)
    cmds += text_at("years away", (px0 + px1) / 2, py1 + 38, 10.0, DIM, pan_x=0.0)
    cmds += [{"variable": {"name": "rpct", "commit": True,
                           "value": {"type": "textFromFloat", "value": "@r * 100.0",
                                     "whole": 2, "decimal": 1}}},
             paint({"color": TEXT}, {"style": "fill"}, {"textSize": 16.0}),
             {"drawTextAnchored": {"text": "@rpct", "x": 70.0, "y": 420.0,
                                   "panX": -1.0, "panY": 0.0, "flags": 0}}]
    cmds += text_at("per cent discount rate", 132.0, 420.0, 10.5, DIM)
    cmds += [{"variable": {"name": "pv20", "commit": True,
                           "value": {"type": "textFromFloat",
                                     "value": "100.0 / pow(1.0 + @r, 20.0)",
                                     "whole": 3, "decimal": 1}}},
             paint({"color": ACCENT}, {"style": "fill"}, {"textSize": 16.0}),
             {"drawTextAnchored": {"text": "@pv20", "x": 330.0, "y": 420.0,
                                   "panX": -1.0, "panY": 0.0, "flags": 0}}]
    cmds += text_at("is what year 20 is worth", 392.0, 420.0, 10.5, DIM)
    cmds.append({"conditionalOperations": {
        "condition": "gt", "v1": "@r", "v2": 0.09,
        "commands": [paint({"color": HOT}, {"style": "fill"}, {"textSize": 11.0}),
                     {"drawTextAnchored": {
                         "text": "at this rate the far years are worth almost nothing - only "
                                 "the near cash matters",
                         "x": 70.0, "y": 452.0, "panX": -1.0, "panY": 0.0, "flags": 0}}]}})
    cmds.append({"conditionalOperations": {
        "condition": "lt", "v1": "@r", "v2": 0.04,
        "commands": [paint({"color": GOOD}, {"style": "fill"}, {"textSize": 11.0}),
                     {"drawTextAnchored": {
                         "text": "at this rate the distant years still count, and long-dated "
                                 "assets look cheap",
                         "x": 70.0, "y": 452.0, "panX": -1.0, "panY": 0.0, "flags": 0}}]}})
    cmds += text_at("Nothing about the business changed. Only the rate did.",
                    70.0, 492.0, 11.5, TEXT)
    cmds += text_at("- which is why a company whose profits are all ten years out moves "
                    "violently on interest rate news,", 70.0, 510.0, 9.5, DIM)
    cmds += text_at("and a utility paying dividends next quarter barely moves at all.",
                    70.0, 526.0, 9.5, DIM)
    cmds += text_at("drag to change the rate", 70.0, 548.0, 9.0, DIM)
    title(cmds, W, H, "What future money is worth now", "drag the discount rate")
    return {"header": header(W, H, "Present value of a twenty-year cash stream with a "
                                   "draggable discount rate"),
            "root": canvas(cmds, INK)}


# ── 16. FIN-ACCO-00011  Cash flow statement — raster-and-text / explain / 3D ─
# The three sections as 3D columns, with the bridge from opening to closing cash. The sign
# pattern across the three is a diagnosis: a healthy firm looks quite different from one
# living on financing, and the shapes differ at a glance.
def cash_flow_statement():
    W, H = 540, 620
    SECTIONS = [("Operating", 240, GOOD, "cash from actually running the business"),
                ("Investing", -180, WARM, "buying plant, equipment, other companies"),
                ("Financing", -30, ACCENT, "debt raised or repaid, dividends, buybacks")]
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.70,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [1.9, 1.5, 3.6], "center": [0.0, 0.08, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.42, -0.58, -0.70], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.25, 0.48], "intensity": 0.42}]}}]
    cmds.append(var("spin", "sin(continuousSec() * 0.2) * 0.42"))
    SC = 0.0032
    run = 120.0
    mid = 10
    bars = [("Opening", 120.0, 0.0, DIM)] + [(n, None, v, c) for n, v, c, _ in SECTIONS]
    for i, (name, absval, delta, colour) in enumerate(bars):
        x = -0.78 + i * 0.40
        if absval is not None:
            lo, hi = 0.0, absval * SC
        else:
            lo = min(run, run + delta) * SC
            hi = max(run, run + delta) * SC
            run += delta
        verts, normals, uv, idx = [], [], [], []
        mesh_box(verts, normals, uv, idx, (x - 0.14, lo, -0.14), (x + 0.14, hi, 0.14))
        cmds.append({"defineMesh3D": {"id": mid, "verts": [round(v,5) for v in verts],
                                      "normals": normals, "uv": uv, "indices": idx}})
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mid, "mode": "software-smooth"}}]
        mid += 1
    # closing
    verts, normals, uv, idx = [], [], [], []
    mesh_box(verts, normals, uv, idx, (0.82 - 0.14, 0.0, -0.14), (0.82 + 0.14, run * SC, 0.14))
    cmds.append({"defineMesh3D": {"id": mid, "verts": [round(v,5) for v in verts],
                                  "normals": normals, "uv": uv, "indices": idx}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": HOT}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": mid, "mode": "software-smooth"}}]
    labels = ["Opening", "Operating", "Investing", "Financing", "Closing"]
    vals = ["120", "+240", "-180", "-30", "150"]
    for i, (lbl, val) in enumerate(zip(labels, vals)):
        x = 96.0 + i * 88.0
        cmds += text_at(lbl, x, 418.0, 9.5, TEXT, pan_x=0.0)
        cmds += text_at(val, x, 434.0, 10.5, DIM, pan_x=0.0)
    y = 470.0
    for name, note, colour in (
            ("+ - -", "the healthy pattern: operations fund the investing and some is "
             "returned", GOOD),
            ("- + +", "the worrying one: losing cash, selling assets, raising money to "
             "survive", HOT),
            ("Why it is the hardest to fake", "profit involves judgement about timing; cash "
             "either arrived or it did not", ACCENT)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 36.0, "top": y - 9, "right": 41.0, "bottom": y + 5}})
        cmds += text_at(name, 52.0, y, 11.5, colour)
        cmds += text_at(note, 140.0, y, 9.0, DIM)
        y += 32.0
    cmds += text_at("A profitable company can run out of cash, and the first place it shows "
                    "is here.", 36.0, 580.0, 10.0, TEXT)
    title(cmds, W, H, "Where the cash went", "opening, three sections, closing")
    return {"header": header(W, H, "A cash flow statement as a 3D bridge from opening to "
                                   "closing cash through three sections"),
            "root": canvas(cmds, INK)}


# ── build ──────────────────────────────────────────────────────────────────────
BUILD = [("PHY-FM-00037", turbulence), ("PHY-FM-00038", vortices),
         ("BIO-ANAT-00030", muscle), ("BIO-ANAT-00031", nervous),
         ("BIO-ANAT-00032", cardiovascular), ("BIO-ANAT-00033", respiratory),
         ("MTH-TRIG-00014", waves), ("CSC-CA-00012", gpu),
         ("CHM-CR-00012", equilibrium), ("EAR-METE-00012", clouds),
         ("ENG-CE-00012", bridges), ("ECO-FE-00016", markets),
         ("ECO-FE-00017", risk), ("ECO-FE-00018", portfolio),
         ("ECO-FE-00019", asset_pricing), ("FIN-ACCO-00011", cash_flow_statement)]

if __name__ == "__main__":
    for doc_id, fn in BUILD:
        name = use(doc_id)
        d = fn()
        (OUT / ("%s.json" % doc_id)).write_text(json.dumps(d, indent=1) + "\n")
        print("  %-16s %-9s %s" % (doc_id, name, d["header"]["contentDescription"][:44]))
    print("  %d documents" % len(BUILD))
