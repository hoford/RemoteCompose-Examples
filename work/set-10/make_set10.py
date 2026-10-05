#!/usr/bin/env python3
"""Build set 10 of the visualization programme: 16 documents.

    python3 work/set-10/make_set10.py

Work order from `python3 tools/visplan.py set 10`.

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


def surface_normal(f, u, v, half, yscale, h=0.005):
    """The unit normal of y = f(u,v) at (u,v), in the same world units surface_mesh uses.

    The two tangents are Tu = (2*half, df/du * yscale, 0) and Tv = (0, df/dv * yscale,
    2*half), so Tu x Tv is proportional to (-df/du * yscale, 2*half, -df/dv * yscale) once
    it is flipped to point upward.
    """
    du = (f(min(1.0, u + h), v) - f(max(0.0, u - h), v)) / (2.0 * h) * yscale
    dv = (f(u, min(1.0, v + h)) - f(u, max(0.0, v - h))) / (2.0 * h) * yscale
    n = (-du, 2.0 * half, -dv)
    ln = math.sqrt(sum(c * c for c in n)) or 1.0
    return tuple(c / ln for c in n)


def drape_ribbon(mesh_id, f, path_uv, half, yscale, yoff, width, lift):
    """A ribbon lying on the height field y = f(u,v), lifted clear along the surface normal.

    Lifting along +y alone is not enough. Where the surface is steep, a ribbon raised
    straight up still cuts back into it and vanishes - which is exactly what hid both
    reaction routes in CHM-CR-00010, where the only part of either route that ever showed
    was the few pixels crossing the flat top of the ridge. The normal is the one direction
    that clears the surface by the same amount everywhere.

    The ribbon is also widened across the surface rather than horizontally, by taking the
    side vector as tangent x normal, so it stays flat against the slope instead of cutting
    into it edge-on.
    """
    pts = [(u, v) for u, v in path_uv]
    nrm = [surface_normal(f, u, v, half, yscale) for u, v in pts]
    pos = []
    for i, (u, v) in enumerate(pts):
        p = ((u * 2 - 1) * half, f(u, v) * yscale + yoff, (v * 2 - 1) * half)
        pos.append(tuple(p[k] + nrm[i][k] * lift for k in range(3)))
    verts, normals, uv, idx = [], [], [], []
    for i in range(len(pos) - 1):
        A, B, na = pos[i], pos[i + 1], nrm[i]
        t = [B[k] - A[k] for k in range(3)]
        tl = math.sqrt(sum(c * c for c in t)) or 1.0
        t = [c / tl for c in t]
        # normal x tangent, the same order surface_ribbon uses. Taking it the other way
        # round reverses the side vector, which swaps two corners of every quad and leaves
        # the index winding describing a downward-facing strip - culled, and silently so.
        s = [na[1] * t[2] - na[2] * t[1], na[2] * t[0] - na[0] * t[2],
             na[0] * t[1] - na[1] * t[0]]
        sl = math.sqrt(sum(c * c for c in s)) or 1.0
        s = [c / sl * width for c in s]
        quad = [[A[k] - s[k] for k in range(3)], [A[k] + s[k] for k in range(3)],
                [B[k] + s[k] for k in range(3)], [B[k] - s[k] for k in range(3)]]
        base = len(verts) // 3
        for q in quad:
            verts += [round(q[0], 5), round(q[1], 5), round(q[2], 5)]
            normals += [round(na[0], 5), round(na[1], 5), round(na[2], 5)]
            uv += [0.0, 0.0]
        idx += [base, base + 2, base + 1, base, base + 3, base + 2]
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


# ── 1. PHY-CM-00031  Energy — static-diagram / explain / 2D ────────────────
# A pendulum's energy at five points in its swing, with the two forms drawn as a stacked bar
# that is the same height every time. The constant total is the content; the trade is the
# mechanism.
def energy():
    W, H = 620, 420
    STAGES = [("Released", 1.00, 0.00), ("Falling", 0.62, 0.38),
              ("Lowest point", 0.00, 1.00), ("Rising", 0.62, 0.38),
              ("Far side", 1.00, 0.00)]
    cmds = []
    # Narrower bars, shifted right, to leave a margin the row labels fit in: at the old
    # width "height" was right-aligned at x=24 and ran off the left edge as "eight".
    bw = 88.0
    for i, (name, pe, ke) in enumerate(STAGES):
        x0 = 70.0 + i * (bw + 14.0)
        base, top = 320.0, 150.0
        hgt = base - top
        cmds.append(paint({"color": RULE}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": top, "right": x0 + bw, "bottom": base}})
        hp = hgt * pe
        cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": top, "right": x0 + bw,
                                  "bottom": top + hp}})
        cmds.append(paint({"color": WARM}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": top + hp, "right": x0 + bw,
                                  "bottom": base}})
        # the pendulum itself above each bar
        ang = (1 - 2 * abs(i / 4.0 - 0.5)) * 0.0 + (i - 2) * 0.42
        px = x0 + bw / 2 + math.sin(ang) * 30.0
        py = 116.0 + math.cos(ang) * 30.0
        cmds.append(paint({"color": DIM}, {"style": "stroke"}, {"width": 1.2}))
        cmds.append({"drawLine": {"x1": x0 + bw / 2, "y1": 116.0, "x2": px, "y2": py}})
        cmds.append(paint({"color": TEXT}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": px, "cy": py, "radius": 6.0}})
        cmds += text_at(name, x0 + bw / 2, 340.0, 10.0, TEXT, pan_x=0.0)
        if pe > 0.05:
            cmds += text_at("%d%%" % int(pe * 100), x0 + bw / 2, top + hp / 2 + 4, 10.0,
                            INK, pan_x=0.0)
        if ke > 0.05:
            cmds += text_at("%d%%" % int(ke * 100), x0 + bw / 2, top + hp + (base - top - hp) / 2 + 4,
                            10.0, INK, pan_x=0.0)
    cmds += text_at("height", 58.0, 180.0, 10.0, ACCENT, pan_x=1.0)
    cmds += text_at("speed", 58.0, 300.0, 10.0, WARM, pan_x=1.0)
    cmds += text_at("Every bar is the same height. That is the whole of energy conservation.",
                    36.0, 372.0, 11.0, TEXT)
    cmds += text_at("- the pendulum does not run down here because nothing is drawn taking "
                    "energy out; a real one", 36.0, 392.0, 10.0, DIM)
    cmds += text_at("loses it to air and to the pivot, and the bars would shrink.",
                    36.0, 408.0, 10.0, DIM)
    title(cmds, W, H, "Two forms, one total", "a pendulum through one swing")
    return {"header": header(W, H, "A pendulum's potential and kinetic energy as stacked "
                                   "bars of constant total height through one swing"),
            "root": canvas(cmds, INK)}


# ── 2. PHY-CM-00032  Collisions — annotated-layout / explore / 2D ──────────
# Elastic, inelastic and perfectly inelastic, each as a before-and-after card. Momentum is
# conserved in all three; energy is not, and the cards say where it went.
def collisions():
    W, H = 500, 640
    CASES = [("Elastic", "+2.0", "-1.0", "-1.0", "+2.0", "nothing lost - billiard balls, "
              "gas molecules", GOOD, "100%"),
             ("Inelastic", "+2.0", "-1.0", "-0.2", "+1.2", "some goes to heat and sound - "
              "most real collisions", WARM, "62%"),
             ("Perfectly inelastic", "+2.0", "-1.0", "+0.5", "+0.5", "they stick and move "
              "together - a crash test", HOT, "25%")]

    def card(va, vb, wa, wb, colour):
        c = [{"clipRect": {"left": 0, "top": 0, "right": 200, "bottom": 96}},
             paint({"color": RULE}, {"style": "fill"}),
             {"drawRect": {"left": 0, "top": 0, "right": 200, "bottom": 96}}]
        for row, (p, q, lbl) in enumerate(((va, vb, "before"), (wa, wb, "after"))):
            y = 28 + row * 42
            c.append(paint({"color": DIM}, {"style": "fill"}))
            for bi, (v, bx, bcol) in enumerate(((p, 58, GOOD), (q, 140, ACCENT))):
                c.append(paint({"color": bcol}, {"style": "fill"}))
                c.append({"drawRect": {"left": bx - 13, "top": y - 10, "right": bx + 13,
                                       "bottom": y + 10}})
                f = float(v)
                c.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.8},
                               {"strokeCap": "round"}))
                ex = bx + f * 16.0
                c.append({"drawLine": {"x1": bx, "y1": y, "x2": ex, "y2": y}})
                d = 1 if f > 0 else -1
                c.append({"drawLine": {"x1": ex, "y1": y, "x2": ex - d * 5, "y2": y - 4}})
                c.append({"drawLine": {"x1": ex, "y1": y, "x2": ex - d * 5, "y2": y + 4}})
        return {"type": "canvas", "modifiers": [{"width": 200}, {"height": 96}],
                "commands": c}

    kids = [{"type": "text", "value": "Three collisions", "modifiers": [],
             "fontSize": 19.0, "color": TEXT},
            {"type": "spacer", "modifiers": [{"height": 3}]},
            {"type": "text",
             "value": "momentum is conserved in all three; energy is not",
             "modifiers": [], "fontSize": 11.0, "color": DIM},
            {"type": "spacer", "modifiers": [{"height": 14}]}]
    for name, va, vb, wa, wb, note, colour, kept in CASES:
        kids.append({"type": "row",
                     "modifiers": [{"width": 456}, {"padding": 10}, {"background": PANEL}],
                     "children": [
                         card(va, vb, wa, wb, colour),
                         {"type": "spacer", "modifiers": [{"width": 12}]},
                         {"type": "column", "modifiers": [{"width": 212}], "children": [
                             {"type": "text", "value": name, "modifiers": [],
                              "fontSize": 13.0, "color": colour},
                             {"type": "spacer", "modifiers": [{"height": 4}]},
                             {"type": "text", "value": "kinetic energy kept: " + kept,
                              "modifiers": [], "fontSize": 10.5, "color": TEXT},
                             {"type": "spacer", "modifiers": [{"height": 4}]},
                             {"type": "text", "value": note, "modifiers": [],
                              "fontSize": 9.0, "color": DIM}]}]})
        kids.append({"type": "spacer", "modifiers": [{"height": 9}]})
    kids.append({"type": "text",
                 "value": "Momentum survives every collision because nothing outside pushed "
                          "on the pair. Energy does not, because it can leave as heat and "
                          "sound without taking any momentum with it.",
                 "modifiers": [], "fontSize": 10.0, "color": TEXT})
    return {"header": header(W, H, "Elastic, inelastic and perfectly inelastic collisions "
                                   "as before-and-after cards"),
            "root": {"type": "column",
                     "modifiers": ["fillMaxSize", {"padding": 18}, {"background": INK}],
                     "children": kids}}


# ── 3. PHY-CM-00033  Pendulums — data-plot / compare / 3D ──────────────────
# Period against length and amplitude, as a surface. 3D because the interesting fact is that
# the surface is almost flat in one direction and not the other: period depends on length,
# and barely on amplitude until the swing gets large.
def pendulums():
    W, H = 540, 620
    cmds = [{"clearDepth3D": {}},
            # From the short-length end, looking along the climb. The surface rises toward
            # large length, so an eye on the +x side at any useful height is looking at the
            # UNDERSIDE of the rising half and the sheet is culled away entirely; raising
            # the eye until the top face shows again flattens the climb to nothing, which
            # is the sliver the first version drew. Standing at -x solves both: the sheet
            # rises away from the camera, so the climb is screen-vertical and the whole top
            # face is toward us. Checked across the full swing of @spin - no sample goes
            # back-facing, and the sheet stays clear of the legend at y=470.
            {"camera3D": {"projection": "perspective", "fovY": 0.60,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [-5.0, 1.7, 2.6], "center": [0.0, -0.5, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.42, -0.6, -0.68], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.25, 0.5], "intensity": 0.42}]}}]
    cmds.append(var("spin", "sin(continuousSec() * 0.22) * 0.5"))
    def period(u, v):
        L = 0.2 + u * 1.8
        th = v * math.radians(80.0)
        k = math.sin(th / 2.0)
        corr = 1.0 + k * k / 4.0 + 9.0 * k ** 4 / 64.0
        return (math.sqrt(L) * corr - 0.45) * 0.78
    draw_axes(cmds, [(5, axis_rod(5, (-1.0, -0.45, 1.0), (1.0, -0.45, 1.0),
                                  [-0.5, 0.0, 0.5], "x")),
                     (6, axis_rod(6, (-1.0, -0.45, -1.0), (-1.0, -0.45, 1.0),
                                  [-0.5, 0.0, 0.5], "z")),
                     (7, axis_rod(7, (-1.0, -0.45, 1.0), (-1.0, 0.55, 1.0),
                                  [0.0, 0.3], "y"))],
              "@spin", [DIM, DIM, DIM])
    SC = dict(half=1.0, yscale=1.25, yoff=-0.62)
    cmds.append(surface_mesh(1, period, 28, **SC))
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": ACCENT}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]

    # Lines drawn on the surface in each direction, because one flat-shaded sheet does not
    # say which way it is flat. Each line is the colour of the legend entry it demonstrates,
    # so the claims below can be checked against the picture rather than taken on trust:
    #   GOOD  along length, at fixed amplitude - climbs, and that is the whole effect
    #   TEXT  across amplitude, at fixed length - level, which is the surprising part
    #   HOT   the 80-degree edge - the one line that has visibly left the others behind
    mid = 20
    for path, colour in (
            [([(i / 40.0, v0) for i in range(41)], GOOD) for v0 in (0.06, 0.5)] +
            [([(u0, i / 40.0) for i in range(41)], TEXT) for u0 in (0.12, 0.5, 0.88)] +
            [([(i / 40.0, 1.0) for i in range(41)], HOT)]):
        cmds.append(drape_ribbon(mid, period, path, width=0.016, lift=0.022, **SC))
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mid, "mode": "software-flat"}}]
        mid += 1
    # Below the sheet and above the legend, which the new framing leaves clear
    cmds += text_at("length", 440.0, 450.0, 10.0, DIM, pan_x=0.0)
    cmds += text_at("amplitude", 150.0, 450.0, 10.0, DIM, pan_x=0.0)
    cmds += text_at("period", 44.0, 160.0, 10.5, TEXT)
    y = 486.0
    for name, note, colour in (
            ("Length does almost all of it", "the green lines run up the length axis and "
             "climb: four times longer is twice as slow", GOOD),
            ("Amplitude barely matters", "the pale lines run across amplitude and stay "
             "level - under 20 degrees the period moves less than one per cent", TEXT),
            ("Until it does", "the far edge is an 80 degree swing: nearly 10 per cent slow, "
             "which is why clock pendulums swing narrowly", HOT)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 36.0, "top": y - 9, "right": 41.0, "bottom": y + 5}})
        cmds += text_at(name, 52.0, y, 11.0, colour)
        cmds += text_at(note, 52.0, y + 15, 8.5, DIM)
        y += 38.0
    title(cmds, W, H, "What sets a pendulum's period",
          "a surface that is flat one way and not the other")
    return {"header": header(W, H, "Pendulum period as a 3D surface over length and "
                                   "amplitude, nearly flat in amplitude until large swings"),
            "root": canvas(cmds, INK)}


# ── 4. PHY-CM-00034  Rotational mechanics — path-form / demonstrate / 2D ───
# Four objects released together down a ramp, drawn as paths in distance-time. They arrive in
# an order that does not depend on mass or radius at all, only on how the mass is arranged -
# which is the one genuinely surprising fact in rotational mechanics.
def rotational():
    W, H = 580, 520
    OBJECTS = [("Sphere, solid", 2.0/5.0, GOOD), ("Cylinder, solid", 1.0/2.0, ACCENT),
               ("Sphere, hollow", 2.0/3.0, WARM), ("Hoop", 1.0, HOT)]
    cmds = []
    # The plot stops well short of the right edge because each curve is named where it
    # ends, and at the old width those names ran off the page - "Sphere, hollow" needs
    # 65px and had 34. Naming the curve at its own end is worth the width: the legend
    # below gives the same four names, but not which line is which.
    px0, px1, py0, py1 = 70.0, 442.0, 140.0, 360.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    for name, beta, colour in OBJECTS:
        acc = 1.0 / (1.0 + beta)
        pid = name.split(",")[0] + name[-1]
        pts = []
        for i in range(61):
            t = i / 60.0
            d = 0.5 * acc * t * t
            pts.append((px0 + (px1 - px0) * t, py1 - d * (py1 - py0) * 1.9))
        cmds.append({"pathCreate": {"id": pid, "x": pts[0][0], "y": pts[0][1]}})
        for (x, y) in pts[1:]:
            cmds.append({"pathAppendLineTo": {"path": pid, "x": x,
                                              "y": max(py0 + 3, y)}})
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6},
                          {"strokeCap": "round"}))
        cmds.append({"drawPath": {"path": pid}})
        cmds += text_at(name, px1 + 6, max(py0 + 8, pts[-1][1]) + 4, 9.5, colour)
    cmds += text_at("distance down the ramp", px0, py0 - 12, 10.5, DIM)
    cmds += text_at("time", (px0 + px1) / 2, py1 + 22, 10.0, DIM, pan_x=0.0)
    y = 402.0
    for name, beta, colour in OBJECTS:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 70.0, "top": y - 8, "right": 82.0, "bottom": y + 4}})
        cmds += text_at(name, 92.0, y, 10.0, colour)
        cmds += text_at("I = %.2f mr²" % beta, 250.0, y, 10.0, TEXT)
        cmds += text_at("a = g sinθ / %.2f" % (1 + beta), 360.0, y, 10.0, DIM)
        y += 19.0
    cmds += text_at("Mass cancels. Radius cancels. Only the arrangement survives.",
                    70.0, 490.0, 11.0, TEXT)
    cmds += text_at("- a marble beats a ring every time, whatever they weigh, because the "
                    "ring must spin up more", 70.0, 508.0, 10.0, DIM)
    title(cmds, W, H, "A race down a ramp", "they finish in the same order every time")
    return {"header": header(W, H, "Four rolling objects as distance-time paths, finishing "
                                   "in an order set only by how their mass is arranged"),
            "root": canvas(cmds, INK)}


# ── 5. MTH-GEOM-00010  Solids — expression-animation / simulate / 2D ───────
# The five Platonic solids, each unfolding into its net and folding back. The animation is
# the proof that there are only five: the net has to close, and for every other combination
# of regular faces it does not.
def solids():
    W, H = 680, 450
    # Each panel is a VERTEX FIGURE: the polygons that meet at one corner of the solid,
    # gathering to share that corner and separating again. The angle they fail to cover is
    # the whole argument, and it is the only thing in the picture that differs from panel to
    # panel in a way that matters.
    #
    # The previous version drew min(faces, 8) copies of one face sliding apart in a ring,
    # which gave the cube four squares and the icosahedron eight triangles - neither of
    # which is anything. It illustrated no claim the document makes, and the body text has
    # been arguing about corners the whole time.
    #
    #   name, faces, how many meet at a corner, sides per face, colour
    SOLIDS = [("Tetrahedron", 4, 3, 3, GOOD), ("Cube", 6, 3, 4, ACCENT),
              ("Octahedron", 8, 4, 3, WARM), ("Dodecahedron", 12, 3, 5, HOT),
              ("Icosahedron", 20, 5, 3, TEXT), ("No sixth", 0, 3, 6, DIM)]
    cmds = [var("fold", "0.5 + 0.5 * sin(continuousSec() * 0.5)")]
    pw, gap, R = 99.0, 7.0, 21.0
    for i, (name, faces, meet, sides, colour) in enumerate(SOLIDS):
        x0 = 26.0 + i * (pw + gap)
        cx, cy = x0 + pw / 2, 206.0
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": 134.0, "right": x0 + pw,
                                  "bottom": 300.0}})
        theta = (sides - 2) * math.pi / sides          # interior angle of one face
        defect = 2 * math.pi - meet * theta            # what the corner leaves uncovered

        # One face with a vertex at the origin and its interior angle opening along +y, so
        # rotating by (bisector - pi/2) aims that corner wherever it is wanted.
        base = [(math.cos(2 * math.pi * j / sides - math.pi / 2) * R,
                 math.sin(2 * math.pi * j / sides - math.pi / 2) * R + R)
                for j in range(sides)]
        # The fan is centred so the uncovered wedge straddles straight up, the same place in
        # every panel - otherwise the gaps cannot be compared by eye.
        start = -math.pi / 2 + defect / 2
        for k in range(meet):
            bis = start + theta * (k + 0.5)
            d = bis - math.pi / 2
            cs, sn = math.cos(d), math.sin(d)
            poly = [(p[0] * cs - p[1] * sn, p[0] * sn + p[1] * cs) for p in base]
            # @fold 0 separates them along their own bisector, @fold 1 brings every corner
            # onto the shared vertex
            ox = "%.2f + (1 - @fold) * %.2f" % (cx, math.cos(bis) * 13.0)
            oy = "%.2f + (1 - @fold) * %.2f" % (cy, math.sin(bis) * 13.0)
            cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.4}))
            pid = "p%d_%d" % (i, k)
            cmds.append({"pathCreate": {"id": pid,
                                        "x": "%s + %.2f" % (ox, poly[0][0]),
                                        "y": "%s + %.2f" % (oy, poly[0][1])}})
            for (dx, dy) in poly[1:]:
                cmds.append({"pathAppendLineTo": {"path": pid,
                                                  "x": "%s + %.2f" % (ox, dx),
                                                  "y": "%s + %.2f" % (oy, dy)}})
            cmds.append({"pathAppendClose": {"path": pid}})
            cmds.append({"drawPath": {"path": pid}})

        # The leftover wedge, drawn where it is left. Zero degrees for hexagons, which is
        # why there is no sixth solid and why that panel has nothing in it to draw.
        if defect > 0.01:
            cmds.append(paint({"color": WARM if name != "Dodecahedron" else TEXT},
                              {"style": "stroke"}, {"width": 1.2}))
            a0 = math.degrees(-math.pi / 2 - defect / 2)
            cmds.append({"drawArc": {"left": cx - 15, "top": cy - 15, "right": cx + 15,
                                     "bottom": cy + 15, "startAngle": a0,
                                     "sweepAngle": math.degrees(defect)}})
            for e in (-defect / 2, defect / 2):
                b = -math.pi / 2 + e
                cmds.append({"drawLine": {"x1": cx, "y1": cy,
                                          "x2": cx + math.cos(b) * 15,
                                          "y2": cy + math.sin(b) * 15}})

        cmds += text_at(name, cx, 322.0, 10.0, colour, pan_x=0.0)
        cmds += text_at("%d faces" % faces if faces else "does not exist",
                        cx, 339.0, 9.0, TEXT if faces else DIM, pan_x=0.0)
        cmds += text_at("%d x %d-gon at a corner" % (meet, sides), cx, 355.0, 8.0, DIM,
                        pan_x=0.0)
        cmds += text_at("%d%s to spare" % (round(math.degrees(defect)), chr(176)),
                        cx, 369.0, 8.5, WARM if defect > 0.01 else DIM, pan_x=0.0)

    cmds += text_at("There are five, and there cannot be a sixth.", 26.0, 402.0, 11.5, TEXT)
    cmds += text_at("- three regular polygons must meet at a corner with angles summing "
                    "under 360 degrees. Triangles allow 3, 4 or 5 per", 26.0, 420.0, 10.0,
                    DIM)
    cmds += text_at("corner; squares and pentagons allow 3. Three hexagons already use the "
                    "whole 360, so there is nothing left to fold with.",
                    26.0, 436.0, 10.0, DIM)
    title(cmds, W, H, "The five regular solids",
          "what has to be left over at a corner")
    return {"header": header(W, H, "The vertex figure of each Platonic solid, gathering to "
                                   "a shared corner, with the leftover angle that lets it "
                                   "fold - and the hexagons that leave none"),
            "root": canvas(cmds, INK)}


# ── 6. MTH-GEOM-00011  Transformations — particle-system / analyze / 2D ────
# A cloud of points under a repeated linear map. The particles reveal the eigenvectors: the
# cloud stretches along one direction and collapses along the other, which is what an
# eigenvector is before anyone writes down a determinant.
def geom_transformations():
    W, H = 560, 560
    cmds = []
    px0, px1, py0, py1 = 60.0, 500.0, 140.0, 400.0
    cx, cy = (px0 + px1) / 2, (py0 + py1) / 2
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": px0, "y1": cy, "x2": px1, "y2": cy}})
    cmds.append({"drawLine": {"x1": cx, "y1": py0, "x2": cx, "y2": py1}})
    # the two eigendirections of [[1.3,0.4],[0.2,0.9]], drawn first
    for ang, lam, colour, lbl in ((0.52, 1.45, GOOD, "stretched, x1.45"),
                                  (-1.17, 0.75, HOT, "squashed, x0.75")):
        dx, dy = math.cos(ang) * 150, -math.sin(ang) * 150
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.6}))
        cmds.append({"drawLine": {"x1": cx - dx, "y1": cy - dy, "x2": cx + dx, "y2": cy + dy}})
        cmds += text_at(lbl, cx + dx * 0.78, cy + dy * 0.78 - 6, 9.0, colour)
    cmds.append({"createParticles": {
        "id": "cloud", "count": 150,
        "variables": ["qx", "qy", "ph", "sp"],
        "initialValues": ["-1 + rand() * 2", "-1 + rand() * 2", "rand() * 6.28",
                          "0.3 + rand() * 0.6"]}})
    cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
    # one application of the map per frame, re-seeded by the modulo so the cloud recycles
    cmds.append({"particlesLoop": {
        "system": "@cloud",
        "equations": ["qx * 1.004 + qy * 0.002", "qy * 0.998 + qx * 0.001", "ph", "sp"],
        "commands": [{"drawCircle": {"cx": "%.1f + @qx * 150.0" % cx,
                                     "cy": "%.1f + @qy * 110.0" % cy,
                                     "radius": 2.2}}]}})
    cmds += text_at("a square cloud of points, mapped again and again", px0 + 8, py0 + 18,
                    10.0, DIM)
    y = 436.0
    for name, note, colour in (
            ("The green line is an eigenvector", "points on it stay on it, and get further "
             "from the origin", GOOD),
            ("The red line is the other one", "points on it stay on it, and get closer", HOT),
            ("Everything else drifts green", "repeat the map enough and the whole cloud "
             "lies along the stretching direction", ACCENT)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 60.0, "top": y - 9, "right": 65.0, "bottom": y + 5}})
        cmds += text_at(name, 76.0, y, 11.0, colour)
        cmds += text_at(note, 76.0, y + 15, 9.0, DIM)
        y += 38.0
    title(cmds, W, H, "What a matrix does to a cloud",
          "the directions that survive are the eigenvectors")
    return {"header": header(W, H, "A cloud of particles under a repeated linear map, "
                                   "revealing the stretching and squashing eigendirections"),
            "root": canvas(cmds, INK)}


# ── 7. MTH-GEOM-00012  Tessellations — interactive / explain / 2D ──────────
# Drag through the three regular tilings and the reason there are only three. The angle sum
# at a vertex is the whole constraint, and it is printed, so the claim is checkable rather
# than asserted.
def tessellations():
    W, H = 560, 560
    # Five candidates, chosen with buttons, and the tiles pull apart and close again so the
    # test is something you watch happen rather than something the caption asserts.
    #
    # The buttons copy 36_droidkaigi.json, which is device-verified. Two things in that
    # structure are load-bearing and the first attempt here had neither:
    #
    #   the clickable carries real, sized children - an empty box positioned over the canvas
    #   with `offset` measures to nothing and there is no area to hit, so the taps went
    #   nowhere. The hit area is whatever the component actually lays out.
    #
    #   the buttons sit in normal layout flow, not floated over a full-page canvas. The
    #   canvas is a sibling below them with its own coordinate space starting at zero.
    #
    # The selected state is an underline with a `visibility` modifier, the same way that
    # document marks its chosen day, rather than anything drawn from inside the canvas.
    #
    #   name, sides, interior angle, how many fit round one vertex, colour
    TILES = [("Triangle", 3, 60.0, 6, GOOD), ("Square", 4, 90.0, 4, ACCENT),
             ("Pentagon", 5, 108.0, 3, HOT), ("Hexagon", 6, 120.0, 3, WARM),
             ("Heptagon", 7, 128.571, 2, HOT)]
    CW, CH = 520.0, 400.0                  # the canvas under the buttons
    PY1 = 240.0                            # the drawing panel fills its top 240
    CX, CY = CW / 2, PY1 / 2
    GROW = 0.18                            # how far apart the tiles travel, as a fraction

    cmds = [var("fold", "0.5 + 0.5 * sin(continuousSec() * 0.45)")]

    def grown(x, y):
        """A point at (x, y) when gathered and further out when not, scaled about the panel
        centre so the patch breathes as one piece and every shared edge parts evenly."""
        return ("%.2f + %.2f * (1.0 + %.3f * (1.0 - @fold))" % (CX, x - CX, GROW),
                "%.2f + %.2f * (1.0 + %.3f * (1.0 - @fold))" % (CY, y - CY, GROW))

    def emit_poly(ops, pid, pts, colour):
        x, y = grown(*pts[0])
        ops.append({"pathCreate": {"id": pid, "x": x, "y": y}})
        for q in pts[1:]:
            x, y = grown(*q)
            ops.append({"pathAppendLineTo": {"path": pid, "x": x, "y": y}})
        ops.append({"pathAppendClose": {"path": pid}})
        ops.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.3}))
        ops.append({"drawPath": {"path": pid}})

    def patch(sides, a):
        """Tiles of a real tiling of the panel. Only those still inside at full separation
        are kept: expansion is about the centre, so the outer ones travel furthest, and a
        tile sliding out from under the panel edge reads as a hole rather than as the edge
        of the drawing."""
        out = []
        h = a * math.sqrt(3) / 2.0
        if sides == 4:
            for j in range(-6, 7):
                for i in range(-8, 9):
                    c = (CX + i * a, CY + j * a)
                    out.append([(c[0] + dx * a / 2, c[1] + dy * a / 2)
                                for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
        elif sides == 3:
            for j in range(-6, 7):
                top = CY + j * h
                for m in range(-14, 15):
                    left = CX + m * a / 2.0
                    if m % 2 == 0:
                        out.append([(left, top + h), (left + a, top + h),
                                    (left + a / 2, top)])
                    else:
                        out.append([(left, top), (left + a, top),
                                    (left + a / 2, top + h)])
        else:
            for j in range(-6, 7):
                for i in range(-8, 9):
                    ox = CX + i * math.sqrt(3) * a + (math.sqrt(3) * a / 2 if j % 2 else 0)
                    oy = CY + j * 1.5 * a
                    out.append([(ox + math.cos(math.radians(-90 + 60 * k)) * a,
                                 oy + math.sin(math.radians(-90 + 60 * k)) * a)
                                for k in range(6)])
        keep, m = [], 1.0 + GROW
        for poly in out:
            if all(4 <= CX + (x - CX) * m <= CW - 4 and 4 <= CY + (y - CY) * m <= PY1 - 4
                   for x, y in poly):
                keep.append(poly)
        return keep

    def fan(sides, interior, meet, R):
        """The polygons that fit round one vertex, and the wedge they cannot cover."""
        out = []
        theta = math.radians(interior)
        defect = 2 * math.pi - meet * theta
        base = [(math.cos(2 * math.pi * j / sides - math.pi / 2) * R,
                 math.sin(2 * math.pi * j / sides - math.pi / 2) * R + R)
                for j in range(sides)]
        start = -math.pi / 2 + defect / 2
        for k in range(meet):
            bis = start + theta * (k + 0.5)
            d = bis - math.pi / 2
            cs, sn = math.cos(d), math.sin(d)
            out.append([(CX + p[0] * cs - p[1] * sn, CY + p[0] * sn + p[1] * cs)
                        for p in base])
        return out, defect

    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": 0.0, "top": 0.0, "right": CW, "bottom": PY1}})

    for ti, (name, sides, interior, meet, colour) in enumerate(TILES):
        ops = []
        if sides in (3, 4, 6):
            for pi, poly in enumerate(patch(sides, 38.0 if sides == 4 else
                                            (52.0 if sides == 3 else 22.0))):
                emit_poly(ops, "t%d_%d" % (ti, pi), poly, colour)
        else:
            polys, defect = fan(sides, interior, meet, 54.0)
            for pi, poly in enumerate(polys):
                emit_poly(ops, "f%d_%d" % (ti, pi), poly, colour)
            ops.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.3}))
            a0 = math.degrees(-math.pi / 2 - defect / 2)
            ops.append({"drawArc": {"left": CX - 34, "top": CY - 34, "right": CX + 34,
                                    "bottom": CY + 34, "startAngle": a0,
                                    "sweepAngle": math.degrees(defect)}})
            for e in (-defect / 2, defect / 2):
                b = -math.pi / 2 + e
                ops.append({"drawLine": {"x1": CX, "y1": CY,
                                         "x2": CX + math.cos(b) * 34,
                                         "y2": CY + math.sin(b) * 34}})
            ops.append(paint({"color": TEXT}, {"style": "fill"}, {"textSize": 11.0}))
            ops.append({"drawTextAnchored": {
                "text": "%.1f%s will not close" % (math.degrees(defect), chr(176)),
                "x": CX, "y": PY1 - 16, "panX": 0.0, "panY": 0.0, "flags": 0}})
        cmds.append({"conditionalOperations": {
            "condition": "eq", "v1": "@sel", "v2": float(ti), "commands": ops}})

    for ti, (name, sides, interior, meet, colour) in enumerate(TILES):
        works = abs(meet * interior - 360.0) < 0.05
        cmds.append({"conditionalOperations": {
            "condition": "eq", "v1": "@sel", "v2": float(ti),
            "commands": [
                paint({"color": colour}, {"style": "fill"}, {"textSize": 15.0}),
                {"drawTextAnchored": {"text": name, "x": 0.0, "y": 282.0,
                                      "panX": -1.0, "panY": 0.0, "flags": 0}},
                paint({"color": TEXT}, {"style": "fill"}, {"textSize": 11.0}),
                {"drawTextAnchored": {"text": "interior angle %.1f, and %d of them make %.1f"
                                      % (interior, meet, meet * interior),
                                      "x": 0.0, "y": 306.0, "panX": -1.0, "panY": 0.0,
                                      "flags": 0}},
                paint({"color": GOOD if works else HOT}, {"style": "fill"},
                      {"textSize": 11.0}),
                {"drawTextAnchored": {"text": "closes exactly - it tiles the plane" if works
                                      else "cannot close - it leaves a gap",
                                      "x": 0.0, "y": 328.0, "panX": -1.0, "panY": 0.0,
                                      "flags": 0}}]}})

    cmds += text_at("Only three regular polygons tile the plane, and the test is one line "
                    "of arithmetic:", 0.0, 362.0, 10.5, TEXT)
    cmds += text_at("the interior angle must divide 360 exactly. 60, 90 and 120 do. "
                    "108 and 128.6 do not.", 0.0, 380.0, 10.0, DIM)

    def button(ti, name, colour):
        # The underline is driven by a BARE variable reference, and the expression behind it
        # lives in resources.variables. Writing the expression inline in `visibility` does
        # not survive: the reference parser sends that modifier through
        # parseIntegerExpression, so float literals ("0.0") throw NumberFormatException and
        # the document is refused outright - and with integer literals the two writers still
        # disagree, rcj emitting a float expression op where the reference emits an integer
        # one, 4 bytes different per button. A bare reference is byte-identical to the
        # oracle, and it is what 36_droidkaigi.json does, which is the version that has
        # actually run on a phone.
        lit = "@lit%d" % ti
        return {"type": "column",
                "modifiers": [{"width": 104}, {"padding": 2},
                              {"onClick": {"type": "valueFloatExpressionChange",
                                           "target": "@sel", "value": "%.1f" % ti}}],
                "horizontalAlignment": "center",
                "children": [
                    {"type": "box",
                     "modifiers": [{"width": 98}, {"height": 30}, {"background": RULE},
                                   {"clip": {"type": "roundRect", "radius": 8}}],
                     "horizontalAlignment": "center", "verticalAlignment": "center",
                     "children": [{"type": "text", "value": name, "modifiers": [],
                                   "fontSize": 11.0, "color": TEXT}]},
                    {"type": "spacer", "modifiers": [{"height": 4}]},
                    {"type": "box",
                     "modifiers": [{"width": 84}, {"height": 4}, {"background": colour},
                                   {"clip": {"type": "roundRect", "radius": 2}},
                                   {"visibility": lit}]}]}

    return {"header": header(W, H, "Five regular polygons tested for whether they tile the "
                                   "plane, selected with buttons, the tiles pulling apart "
                                   "and closing again"),
            "root": {"type": "column",
                     "modifiers": ["fillMaxSize", {"padding": 20},
                                   {"background": INK}],
                     "children": [
                         {"type": "text", "value": "Which shapes tile", "modifiers": [],
                          "fontSize": 19.0, "color": TEXT},
                         {"type": "spacer", "modifiers": [{"height": 3}]},
                         {"type": "text", "value": "tap one, and watch it try to close",
                          "modifiers": [], "fontSize": 11.0, "color": DIM},
                         {"type": "spacer", "modifiers": [{"height": 14}]},
                         {"type": "row", "modifiers": ["fillMaxWidth"],
                          "children": [button(ti, n, c)
                                       for ti, (n, _, _, _, c) in enumerate(TILES)]},
                         {"type": "spacer", "modifiers": [{"height": 12}]},
                         {"type": "canvas",
                          "modifiers": [{"width": int(CW)}, {"height": int(CH)}],
                          "commands": cmds}]},
            "resources": {"variables":
                          [{"sel": {"value": 0, "export": True}}] +
                          # 0 on every button but the selected one. @sel only ever holds
                          # 0..4, so abs(@sel - ti) is 0 there and at least 1 elsewhere;
                          # clamp flattens the rest to 1. Integer literals throughout.
                          [{"lit%d" % ti: "1 - clamp(0, 1, abs(@sel - %d))" % ti}
                           for ti in range(len(TILES))]}}


# ── 8. BIO-MICR-00028  Microbiomes — raster-and-text / explore / 3D ────────
# Community composition at four body sites, as stacked 3D columns. The sites differ more
# from each other than two people's guts differ, which is the fact that makes "the
# microbiome" a misleading singular.
def microbiomes():
    W, H = 540, 620
    SITES = [("Gut", [0.58, 0.28, 0.09, 0.05]), ("Skin", [0.12, 0.17, 0.62, 0.09]),
             ("Mouth", [0.31, 0.38, 0.14, 0.17]), ("Vagina", [0.06, 0.05, 0.08, 0.81])]
    PHYLA = [("Firmicutes", GOOD), ("Bacteroidetes", ACCENT),
             ("Actinobacteria", WARM), ("Other", HOT)]
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.70,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [2.1, 1.7, 3.6], "center": [0.0, 0.12, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.42, -0.58, -0.70], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.25, 0.48], "intensity": 0.42}]}}]
    cmds.append(var("spin", "sin(continuousSec() * 0.2) * 0.45"))
    mid = 10
    for si, (site, frac) in enumerate(SITES):
        x = -0.78 + si * 0.52
        base = -0.45
        for pi, f in enumerate(frac):
            h = f * 1.5
            verts, normals, uv, idx = [], [], [], []
            mesh_box(verts, normals, uv, idx, (x - 0.16, base, -0.16),
                     (x + 0.16, base + h, 0.16))
            cmds.append({"defineMesh3D": {"id": mid, "verts": [round(v,5) for v in verts],
                                          "normals": normals, "uv": uv, "indices": idx}})
            cmds += [{"matrix3D": {"op": "identity"}},
                     {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                     paint({"color": PHYLA[pi][1]}, {"style": "fill"}),
                     {"drawMesh3D": {"mesh": mid, "mode": "software-smooth"}}]
            mid += 1
            base += h
    for si, (site, frac) in enumerate(SITES):
        cmds += text_at(site, 118.0 + si * 102.0, 446.0, 11.0, TEXT, pan_x=0.0)
    y = 480.0
    for name, colour in PHYLA:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 40.0, "top": y - 9, "right": 54.0, "bottom": y + 3}})
        cmds += text_at(name, 64.0, y, 10.0, colour)
        y += 20.0
    cmds += text_at("Four sites on one body, and they share almost nothing.", 40.0, 574.0,
                    11.0, TEXT)
    cmds += text_at("- two people's guts resemble each other far more than one person's gut "
                    "resembles their own skin,", 40.0, 592.0, 9.5, DIM)
    cmds += text_at("which is why 'the human microbiome' is a misleading singular.",
                    40.0, 606.0, 9.5, DIM)
    return {"header": header(W, H, "Microbial community composition at four body sites as "
                                   "stacked 3D columns"),
            "root": canvas(title(cmds, W, H, "Four sites, four communities",
                                 "the same body throughout"), INK)}


# ── 9. CSC-DS-00010  Hash tables — static-diagram / explore / 2D ───────────
# Buckets with collisions drawn in. The average is O(1) and the worst case is O(n), and the
# picture shows both at once: most buckets hold one thing, one holds four.
def hash_tables():
    W, H = 600, 460
    KEYS = [("apple", 3), ("banana", 7), ("cherry", 3), ("date", 0),
            ("elder", 5), ("fig", 3), ("grape", 7), ("kiwi", 9), ("lemon", 3)]
    cmds = []
    NB = 10
    # The longest chain is bucket 3's four keys, which reach ytop + 40 + 3*32 + 26. At the
    # old ytop that put the last chip at y=322 and the "O(1)" below it topped out at 321 -
    # the one bucket the document is about was touching the line that explains it. There was
    # an empty band above the diagram the whole time.
    bw, x0, ytop = 50.0, 54.0, 118.0
    buckets = {}
    for k, h in KEYS:
        buckets.setdefault(h, []).append(k)
    for b in range(NB):
        x = x0 + b * bw
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x, "top": ytop, "right": x + bw - 6,
                                  "bottom": ytop + 30}})
        cmds += text_at("%d" % b, x + (bw - 6) / 2, ytop + 20, 11.0, DIM, pan_x=0.0)
        chain = buckets.get(b, [])
        y = ytop + 40
        for ci, key in enumerate(chain):
            colour = HOT if len(chain) > 2 else (WARM if len(chain) == 2 else GOOD)
            cmds.append(paint({"color": colour}, {"style": "fill"}))
            cmds.append({"drawRect": {"left": x, "top": y, "right": x + bw - 6,
                                      "bottom": y + 26}})
            cmds += text_at(key, x + (bw - 6) / 2, y + 17, 8.5, INK, pan_x=0.0)
            if ci:
                cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.2}))
                cmds.append({"drawLine": {"x1": x + (bw - 6) / 2, "y1": y - 6,
                                          "x2": x + (bw - 6) / 2, "y2": y}})
            y += 32
    cmds += text_at("buckets", x0, ytop - 10, 10.0, DIM)
    y = 330.0
    for lbl, val, note, colour in (
            ("Average lookup", "O(1)", "most buckets hold one key, so one probe finds it",
             GOOD),
            ("Worst lookup", "O(n)", "bucket 3 holds four; a bad hash puts everything there",
             HOT),
            ("Load factor here", "0.9", "nine keys in ten buckets - most tables grow at 0.75",
             ACCENT)):
        cmds += text_at(lbl, 54.0, y, 11.0, TEXT)
        cmds += text_at(val, 200.0, y, 12.0, colour)
        cmds += text_at(note, 270.0, y, 9.5, DIM)
        y += 24.0
    cmds += text_at("A hash table is fast on average and slow in the worst case, and the "
                    "difference is entirely", 54.0, 414.0, 10.5, TEXT)
    cmds += text_at("the hash function. This one sends four of nine keys to the same place.",
                    54.0, 432.0, 10.0, DIM)
    title(cmds, W, H, "Nine keys, ten buckets", "the collisions are the interesting part")
    return {"header": header(W, H, "A hash table with chained collisions, showing the "
                                   "average and worst-case lookup together"),
            "root": canvas(cmds, INK)}


# ── 10. CHM-CR-00010  Reaction pathways — annotated-layout / compare / 3D ──
# Two routes from the same reactants to the same products, as paths over an energy surface.
# A catalyst does not change where you start or finish, only the pass you go over - which is
# the only thing worth knowing about catalysis.
def pathways():
    W, H = 540, 620
    cmds = [{"clearDepth3D": {}},
            # Elevated enough that no part of the landscape turns away from it, and off
            # axis so the ridge is read as a ridge rather than as a horizon line.
            {"camera3D": {"projection": "perspective", "fovY": 0.62,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [1.13, 3.82, -4.21], "center": [0.0, -0.60, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.42, -0.6, -0.68], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.25, 0.5], "intensity": 0.40}]}}]
    cmds.append(var("spin", "sin(continuousSec() * 0.2) * 0.4"))
    # A broader, shallower ridge than the first version carried. That one peaked at a 68
    # degree flank, and a height field is back-facing wherever its slope away from the
    # camera exceeds the camera's elevation - so no viewpoint short of straight down showed
    # the whole landscape, and straight down is the one view with no landscape in it. This
    # one tops out near 41 degrees, which a normal three-quarter view clears. Nothing about
    # the chemistry is in the width of the barrier; what has to be true is that the ridge
    # blocks every route and the pass is a real gap in it at one place.
    PASS_U = 0.75
    def land(u, v):
        ridge = 0.80 * math.exp(-((v - 0.5) / 0.42) ** 2)
        # The 0.24 is load-bearing. At 0.36 the dip still had depth left at v=0 and v=1,
        # so the two routes started 0.06 apart and finished 0.06 apart - and "Same ends,
        # both times" is one of the three things this document claims. Narrowing it leaves
        # a gap of 0.0055, below a pixel, and costs nothing in steepness: the ridge sets
        # that, not the pass.
        pass_lo = 0.68 * math.exp(-(((u - PASS_U) / 0.21) ** 2 + ((v - 0.5) / 0.24) ** 2))
        return ridge - pass_lo + 0.22 * (1 - v)
    SC = dict(half=1.0, yscale=0.62, yoff=-0.40)
    cmds.append(surface_mesh(1, land, 34, **SC))
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": "#FF4A5570"}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]
    # A faint grid draped on the landscape. Flat-shaded terrain in one colour gives the eye
    # almost nothing to read height from, and the whole argument here is a comparison of two
    # heights; the grid lines bunch where the ground is steep and part where it is flat, so
    # the ridge and the gap in it become visible as shape rather than as shading.
    mid = 30
    for u0 in (0.08, 0.28, 0.5, PASS_U, 0.92):
        cmds.append(drape_ribbon(mid, land, [(u0, k / 36.0) for k in range(37)],
                                 width=0.007, lift=0.012, **SC))
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 paint({"color": "#FF8794B4"}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mid, "mode": "software-flat"}}]
        mid += 1
    for v0 in (0.25, 0.5, 0.75):
        cmds.append(drape_ribbon(mid, land, [(k / 36.0, v0) for k in range(37)],
                                 width=0.007, lift=0.012, **SC))
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 paint({"color": "#FF8794B4"}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mid, "mode": "software-flat"}}]
        mid += 1
    # The start line and the finish line, in the colour of the third legend entry. Both
    # routes leave one and arrive at the other at the same height, and drawing those two
    # heights is the only way the claim is checkable rather than asserted.
    for v0 in (0.03, 0.97):
        cmds.append(drape_ribbon(mid, land, [(k / 36.0, v0) for k in range(37)],
                                 width=0.014, lift=0.016, **SC))
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 paint({"color": ACCENT}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mid, "mode": "software-flat"}}]
        mid += 1

    mid = 10
    for uu, colour in ((0.28, HOT), (PASS_U, GOOD)):
        cmds.append(drape_ribbon(mid, land, [(uu, k / 40.0) for k in range(41)],
                                 width=0.030, lift=0.045, **SC))
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mid, "mode": "software-flat"}}]
        mid += 1
    # Placed against the two ends of the reaction coordinate as this camera projects them:
    # v=0 runs along the lower right edge, v=1 along the upper left.
    cmds += text_at("reactants", 330.0, 400.0, 10.0, DIM, pan_x=0.0)
    cmds += text_at("products", 170.0, 142.0, 10.0, DIM, pan_x=0.0)
    y = 452.0
    for name, note, colour in (
            ("Over the ridge", "the uncatalysed route climbs the full barrier", HOT),
            ("Through the pass", "the catalyst opens a lower crossing, nothing else", GOOD),
            ("Same ends, both times", "a catalyst changes the rate, never the equilibrium",
             ACCENT)):
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 36.0, "top": y - 9, "right": 41.0, "bottom": y + 5}})
        cmds += text_at(name, 52.0, y, 11.0, colour)
        cmds += text_at(note, 52.0, y + 15, 9.0, DIM)
        y += 38.0
    cmds += text_at("If a catalyst could change where the valleys are it would be a source "
                    "of free energy.", 36.0, 580.0, 9.5, DIM)
    title(cmds, W, H, "Two ways over", "a catalyst moves the pass, not the ends")
    return {"header": header(W, H, "Catalysed and uncatalysed routes drawn over the same "
                                   "energy landscape in 3D"),
            "root": canvas(cmds, INK)}


# ── 11. EAR-GEOP-00010  Mantle convection — data-plot / demonstrate / 2D ───
# Temperature against depth with the convecting region marked. The near-constant gradient
# through the mantle is the evidence for convection: conduction alone would give a much
# steeper curve, and the rock would have to be far hotter than it is.
def mantle():
    W, H = 580, 540
    cmds = []
    px0, px1, py0, py1 = 90.0, 520.0, 140.0, 400.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    LAYERS = [(0, 35, "crust", RULE), (35, 660, "upper mantle", ACCENT),
              (660, 2890, "lower mantle", WARM), (2890, 5150, "outer core", HOT)]
    D = 5150.0
    for d0, d1, name, colour in LAYERS:
        x = px0 + (px1 - px0) * d0 / D
        xe = px0 + (px1 - px0) * d1 / D
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x, "top": py0, "right": xe, "bottom": py0 + 7}})
        if xe - x > 48:
            cmds += text_at(name, (x + xe) / 2, py0 - 8, 8.5, colour, pan_x=0.0)
    def adiabat(d):
        if d < 35: return d * 25.0
        if d < 2890: return 875 + (d - 35) * 0.47
        return 2215 + (d - 2890) * 0.55
    def conduction(d):
        return min(9000.0, d * 25.0)
    for fn, colour, lbl in ((adiabat, GOOD, "what the rock actually does"),
                            (conduction, HOT, "if heat only conducted")):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.6},
                          {"strokeCap": "round"}))
        prev = None
        for i in range(81):
            d = D * i / 80.0
            T = fn(d)
            if T > 6500: break
            pt = (px0 + (px1 - px0) * d / D, py1 - T / 6500.0 * (py1 - py0))
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1],
                                          "x2": pt[0], "y2": pt[1]}})
            prev = pt
        if prev:
            cmds += text_at(lbl, min(prev[0] + 6, px1 - 4), prev[1] + 4, 9.0, colour,
                            pan_x=1.0 if prev[0] > px1 - 90 else -1.0)
    for T in (2000, 4000, 6000):
        y = py1 - T / 6500.0 * (py1 - py0)
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 0.8}))
        cmds.append({"drawLine": {"x1": px0, "y1": y, "x2": px1, "y2": y}})
        cmds += text_at("%d C" % T, px0 - 6, y + 4, 9.0, DIM, pan_x=1.0)
    for d in (660, 2890):
        x = px0 + (px1 - px0) * d / D
        cmds.append(paint({"color": DIM}, {"style": "stroke"}, {"width": 0.8}))
        cmds.append({"drawLine": {"x1": x, "y1": py0, "x2": x, "y2": py1}})
        cmds += text_at("%d km" % d, x, py1 + 18, 8.5, DIM, pan_x=0.0)
    cmds += text_at("The mantle's gradient is shallow because the rock is moving.",
                    90.0, 444.0, 11.5, TEXT)
    cmds += text_at("- solid rock, creeping at centimetres a year, carries heat far better "
                    "than conduction does.", 90.0, 464.0, 10.0, DIM)
    cmds += text_at("If it only conducted, the red line would hold, the interior would be "
                    "thousands of degrees", 90.0, 480.0, 10.0, DIM)
    cmds += text_at("hotter than it is, and the surface would look nothing like it does.",
                    90.0, 496.0, 10.0, DIM)
    title(cmds, W, H, "Why the mantle must be moving",
          "the temperature gradient gives it away")
    return {"header": header(W, H, "Temperature against depth through the Earth, comparing "
                                   "the real gradient with pure conduction"),
            "root": canvas(cmds, INK)}


# ── 12. ENG-EE-00010  Signal processing — path-form / simulate / 2D ────────
# A square wave built from its harmonics, one at a time, as filled paths. The overshoot at
# the edges does not go away as terms are added - it narrows and stays about nine per cent,
# which is the thing nobody expects the first time.
def signal_processing():
    W, H = 600, 540
    TERMS = [1, 3, 7, 15]
    cmds = []
    px0, px1, cy = 60.0, 540.0, 250.0
    AMP = 86.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": 140.0, "right": px1, "bottom": 360.0}})
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": px0, "y1": cy, "x2": px1, "y2": cy}})
    # the ideal square, behind everything
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.6}))
    for seg in range(4):
        xa = px0 + (px1 - px0) * seg / 4.0
        xb = px0 + (px1 - px0) * (seg + 1) / 4.0
        yy = cy - AMP if seg % 2 == 0 else cy + AMP
        cmds.append({"drawLine": {"x1": xa, "y1": yy, "x2": xb, "y2": yy}})
        cmds.append({"drawLine": {"x1": xb, "y1": cy - AMP, "x2": xb, "y2": cy + AMP}})
    for ti, n in enumerate(TERMS):
        colour = (HOT, WARM, ACCENT, GOOD)[ti]
        pid = "h%d" % n
        pts = []
        for i in range(241):
            u = i / 240.0
            s = 0.0
            k = 1
            while k <= n:
                s += math.sin(2 * math.pi * 2 * u * k) / k
                k += 2
            pts.append((px0 + (px1 - px0) * u, cy - s * AMP * 4.0 / math.pi))
        cmds.append(paint({"color": colour}, {"style": "stroke"},
                          {"width": 2.4 if n == 15 else 1.4}, {"strokeCap": "round"}))
        for i in range(1, len(pts)):
            cmds.append({"drawLine": {"x1": round(pts[i-1][0],1), "y1": round(pts[i-1][1],1),
                                      "x2": round(pts[i][0],1), "y2": round(pts[i][1],1)}})
        cmds += text_at("%d term%s" % ((n + 1) // 2, "" if n == 1 else "s"),
                        px0 + 8, 160.0 + ti * 15.0, 9.5, colour)
    cmds.append(paint({"color": GOOD}, {"style": "stroke"}, {"width": 1.0}))
    ox = px0 + (px1 - px0) * 0.25
    cmds.append({"drawOval": {"left": ox - 22, "top": cy - AMP - 26, "right": ox + 22,
                              "bottom": cy - AMP + 14}})
    cmds += text_at("the overshoot", ox + 28, cy - AMP - 14, 10.0, GOOD)
    cmds += text_at("About nine per cent, and it never goes away.", 60.0, 404.0, 11.5, TEXT)
    cmds += text_at("- adding terms makes the ringing narrower, not smaller. That is Gibbs' "
                    "phenomenon, and it is", 60.0, 424.0, 10.0, DIM)
    cmds += text_at("why a sharp edge pushed through any band-limited channel comes out with "
                    "a ripple on it -", 60.0, 440.0, 10.0, DIM)
    cmds += text_at("in audio, in images, and in every oscilloscope trace of a fast switch.",
                    60.0, 456.0, 10.0, DIM)
    title(cmds, W, H, "Building a square wave", "odd harmonics, one at a time")
    return {"header": header(W, H, "A square wave approximated by 1, 2, 4 and 8 odd "
                                   "harmonics, with the Gibbs overshoot marked"),
            "root": canvas(cmds, INK)}


# ── 13. SOC-PSYC-00008  Behavior — expression-animation / analyze / 2D ─────
# Four reinforcement schedules running on one clock, with the response rate drawn as it
# accumulates. The variable-ratio curve is the steepest and the hardest to extinguish, which
# is the finding that explains slot machines and very little else as cleanly.
def behaviour():
    W, H = 600, 520
    SCHEDULES = [("Fixed ratio", "a reward every 5th press", 0.72, "scalloped", ACCENT),
                 ("Variable ratio", "a reward on average every 5th", 1.00, "steady and high",
                  HOT),
                 ("Fixed interval", "a reward for the first press after 30 s", 0.42,
                  "pauses, then rushes", WARM),
                 ("Variable interval", "a reward after an unpredictable wait", 0.58,
                  "slow and steady", GOOD)]
    cmds = [var("t", "continuousSec() * 0.12 - floor(continuousSec() * 0.12)")]
    px0, px1, py0, py1 = 70.0, 540.0, 150.0, 350.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    for si, (name, rule, rate, shape, colour) in enumerate(SCHEDULES):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.2},
                          {"strokeCap": "round"}))
        prev = None
        for i in range(97):
            u = i / 96.0
            if shape == "scalloped":
                y = rate * (u + 0.05 * math.sin(u * 44.0))
            elif shape == "pauses, then rushes":
                ph = (u * 6.0) % 1.0
                y = rate * (u - 0.07 * (1 - ph) ** 2)
            else:
                y = rate * u
            pt = (px0 + (px1 - px0) * u, py1 - y * (py1 - py0) * 0.92)
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1],
                                          "x2": pt[0], "y2": pt[1]}})
            prev = pt
        if prev:
            cmds += text_at(name, px1 - 6, prev[1] + 4, 9.5, colour, pan_x=1.0)
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.4}))
    cmds.append({"drawLine": {"x1": "%.1f + @t * %.1f" % (px0, px1 - px0), "y1": py0,
                              "x2": "%.1f + @t * %.1f" % (px0, px1 - px0), "y2": py1}})
    cmds += text_at("cumulative responses", px0, py0 - 12, 10.5, DIM)
    cmds += text_at("time", (px0 + px1) / 2, py1 + 22, 10.0, DIM, pan_x=0.0)
    y = 392.0
    for name, rule, rate, shape, colour in SCHEDULES:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 70.0, "top": y - 8, "right": 82.0, "bottom": y + 4}})
        cmds += text_at(name, 92.0, y, 10.0, colour)
        cmds += text_at(rule, 220.0, y, 9.5, DIM)
        y += 19.0
    cmds += text_at("The unpredictable reward produces the fastest responding and the "
                    "slowest extinction.", 70.0, 482.0, 11.0, TEXT)
    cmds += text_at("- which is a finding about pigeons that turned out to describe slot "
                    "machines exactly.", 70.0, 500.0, 10.0, DIM)
    title(cmds, W, H, "Four reinforcement schedules", "same clock, same animal")
    return {"header": header(W, H, "Cumulative response curves for four reinforcement "
                                   "schedules on a shared clock"),
            "root": canvas(cmds, INK)}


# ── 14. SOC-PSYC-00009  Development — particle-system / explain / 2D ───────
# Synapse count against age, with particles standing in for connections. The shape is the
# surprise: the peak is at two or three years old and the rest of childhood is pruning, not
# building.
def development():
    W, H = 580, 540
    cmds = []
    px0, px1, py0, py1 = 70.0, 540.0, 150.0, 340.0
    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    def density(a):
        if a < 2.5:
            return 0.35 + 0.65 * (a / 2.5) ** 0.7
        return 1.0 - 0.42 * min(1.0, ((a - 2.5) / 17.5) ** 0.75)
    cmds.append(paint({"color": ACCENT}, {"style": "stroke"}, {"width": 2.8},
                      {"strokeCap": "round"}))
    prev = None
    for i in range(81):
        a = i / 80.0 * 20.0
        pt = (px0 + (px1 - px0) * a / 20.0, py1 - density(a) * (py1 - py0) * 0.9)
        if prev:
            cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": pt[0], "y2": pt[1]}})
        prev = pt
    px = px0 + (px1 - px0) * 2.5 / 20.0
    cmds.append(paint({"color": HOT}, {"style": "stroke"}, {"width": 1.4}))
    cmds.append({"drawLine": {"x1": px, "y1": py0, "x2": px, "y2": py1}})
    cmds += text_at("peak at about 2 to 3 years", px + 8, py0 + 20, 10.0, HOT)
    for a in (0, 5, 10, 15, 20):
        x = px0 + (px1 - px0) * a / 20.0
        cmds += text_at("%d" % a, x, py1 + 20, 9.5, DIM, pan_x=0.0)
    cmds += text_at("age, years", (px0 + px1) / 2, py1 + 38, 10.0, DIM, pan_x=0.0)
    cmds += text_at("synapses per neuron", px0, py0 - 12, 10.5, DIM)
    # the pruning itself, as particles leaving
    cmds.append({"createParticles": {
        "id": "syn", "count": 110,
        "variables": ["sx", "sy", "fall", "ph"],
        "initialValues": ["%.1f + rand() * %.1f" % (px0 + 120, px1 - px0 - 140),
                          "360 + rand() * 90", "0.3 + rand() * 1.1", "rand() * 6.28"]}})
    cmds.append(paint({"color": DIM}, {"style": "fill"}))
    cmds.append({"particlesLoop": {
        "system": "@syn",
        "equations": ["sx", "360 + ((sy - 360 + fall) % 90)", "fall", "ph"],
        "commands": [{"drawCircle": {"cx": "@sx", "cy": "@sy", "radius": 1.8}}]}})
    cmds += text_at("connections being pruned", px0 + 120, 468.0, 9.5, DIM)
    cmds += text_at("Most of childhood is subtraction.", 70.0, 492.0, 12.0, TEXT)
    cmds += text_at("- the brain overbuilds by about two years old and then removes what "
                    "goes unused. Learning is", 70.0, 510.0, 10.0, DIM)
    cmds += text_at("as much about which connections are kept as about which are made.",
                    70.0, 526.0, 10.0, DIM)
    title(cmds, W, H, "Synapses over a childhood", "the peak comes early")
    return {"header": header(W, H, "Synaptic density against age with pruning shown as "
                                   "particles leaving"),
            "root": canvas(cmds, INK)}


# ── 15. SOC-ANTH-00010  Human migration — interactive / explore / 3D ───────
# The out-of-Africa routes on a globe, with dates. Ribbons so a route round the back is
# culled, and drag to turn it - the whole point is that these are great-circle distances on
# a sphere, not lines on a wall map.
def migration():
    W, H = 540, 620
    ROUTES = [("Africa to Arabia", (10, 40), (20, 48), "70,000 years ago", GOOD),
              ("Arabia to South Asia", (20, 48), (22, 78), "65,000", ACCENT),
              ("South Asia to Australia", (22, 78), (-20, 133), "50,000", WARM),
              ("Asia to Europe", (40, 60), (48, 16), "45,000", HOT),
              ("Siberia to Americas", (64, 170), (62, -150), "20,000", TEXT)]
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.70,
                          "aspect": float(W) / H, "near": 0.1, "far": 60.0,
                          "eye": [1.5, 1.2, 3.9], "center": [0.0, 0.30, 0.0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.35, -0.42, -0.84], "intensity": 1.0},
                {"type": "directional", "color": ACCENT,
                 "dir": [0.6, 0.3, 0.45], "intensity": 0.40}]}}]
    # A globe has to keep turning. `min` is OMITTED, which is how wrap mode is asked for:
    # the op treats a plain NaN minimum as "wrap at max" rather than "clamp at min", so
    # dragging past the end returns to 0 instead of stopping dead. With min: 0.0 the globe
    # hit a wall after about 100 degrees and the far side could not be reached at all.
    #
    # Wrap alone is not enough. The value wraps at `max`, so the angle has to cover exactly
    # one turn across that range or the seam is a visible jump: at the wrap the angle must
    # already be 2pi, which reads the same as 0. The constant is computed rather than typed
    # so the two cannot drift apart.
    #
    # This is a range of the VALUE, not of pixels. The op accumulates
    # `valueAtDown + (touchX now - touchX at down)`, and how much value a pixel of drag
    # buys depends on the player's touch scaling - measured at about half a unit per CSS
    # pixel in the browser, so roughly 1080 px of dragging per revolution there.
    VALUE_PER_TURN = 540.0
    cmds.append({"touchExpression": {"name": "drag", "defaultValue": 0.0,
                                     "max": VALUE_PER_TURN, "expression": "touchX()"}})
    cmds.append(var("spin", "@drag * %.8f" % (2 * math.pi / VALUE_PER_TURN)))
    def latlon(lat, lon):
        la, lo = math.radians(lat), math.radians(lon)
        return (math.cos(la) * math.sin(lo), math.sin(la), math.cos(la) * math.cos(lo))
    mid = 10
    for name, a, b, when, colour in ROUTES:
        p, q = latlon(*a), latlon(*b)
        dot = max(-1.0, min(1.0, sum(p[k] * q[k] for k in range(3))))
        om = math.acos(dot); so = math.sin(om) or 1e-6
        path = []
        for i in range(25):
            u = i / 24.0
            w0 = math.sin((1 - u) * om) / so; w1 = math.sin(u * om) / so
            m = tuple(p[k] * w0 + q[k] * w1 for k in range(3))
            ln = math.sqrt(sum(c * c for c in m)) or 1.0
            path.append(tuple(m[k] / ln for k in range(3)))
        cmds.append(surface_ribbon(mid, path, 0.030, 0.806))
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 {"matrix3D": {"op": "translate", "x": 0.0, "y": 0.30, "z": 0.0}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mid, "mode": "software-flat"}}]
        mid += 1

    # The globe is textured, and drawn after the routes. "Out of Africa" on a plain blue
    # ball has no Africa in it: the arcs have nothing to be relative to, and a reader cannot
    # tell a great circle from a doodle. Same NASA Blue Marble image set 8 embeds, same
    # uv_sphere, so the map lands on the sphere the same way it does there. Drawing it last
    # keeps the near-side ribbons out of the globe's own shading; the far side needs no help
    # from draw order, since a ribbon round the back is back-facing and culled (F-027).
    cmds.append(uv_sphere(1, 0.80, nlat=22, nlon=44))
    cmds.append({"texture3D": {"bitmap": "@earth"}})
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             {"matrix3D": {"op": "translate", "x": 0.0, "y": 0.30, "z": 0.0}},
             paint({"color": "#FFFFFFFF"}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}]
    cmds.append({"texture3D": {"bitmap": 0}})

    y = 436.0
    for name, a, b, when, colour in ROUTES:
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 40.0, "top": y - 9, "right": 54.0, "bottom": y + 3}})
        cmds += text_at(name, 64.0, y, 10.0, colour)
        cmds += text_at(when, 380.0, y, 9.5, TEXT, pan_x=1.0)
        y += 21.0
    cmds += text_at("Dates are from genetics and archaeology and are revised often; treat "
                    "them as approximate.", 40.0, 556.0, 9.0, DIM)
    cmds += text_at("Every living person outside Africa descends from one of these "
                    "crossings.", 40.0, 580.0, 10.5, TEXT)
    cmds += text_at("drag to turn the globe", 40.0, 600.0, 9.0, DIM)
    cmds += text_at("NASA Blue Marble, public domain", 300.0, 600.0, 8.5, DIM)
    title(cmds, W, H, "Out of Africa", "great circles, not lines on a wall map")
    return {"header": header(W, H, "Five human migration routes as ribbons on a draggable "
                                   "textured globe, with approximate dates"),
            "resources": embedded_bitmap("earth", "textures/earth.png"),
            "root": canvas(cmds, INK)}


# ── 16. SOC-ANTH-00011  Cultures — raster-and-text / compare / 2D ──────────
# Kinship terms across four languages, as a grid. The grid is the argument: English merges
# relations that other languages keep apart, and nothing about the biology changes.
def cultures():
    W, H = 620, 480
    RELATIONS = ["father's brother", "mother's brother", "father's sister",
                 "mother's sister", "older brother", "younger brother"]
    LANGS = [("English", ["uncle", "uncle", "aunt", "aunt", "brother", "brother"], GOOD),
             ("Swedish", ["farbror", "morbror", "faster", "moster", "bror", "bror"], ACCENT),
             ("Mandarin", ["bofu", "jiujiu", "gumu", "yimu", "gege", "didi"], WARM),
             ("Hawaiian", ["makua kane", "makua kane", "makuahine", "makuahine",
                           "kaikuaana", "kaikaina"], HOT)]
    cmds = []
    x0, y0, cw, rh = 170.0, 170.0, 104.0, 44.0
    for ri, rel in enumerate(RELATIONS):
        y = y0 + ri * rh
        cmds += text_at(rel, x0 - 10, y + 24, 9.5, DIM, pan_x=1.0)
    for li, (lang, terms, colour) in enumerate(LANGS):
        x = x0 + li * cw
        cmds += text_at(lang, x + cw / 2 - 4, y0 - 12, 11.0, colour, pan_x=0.0)
        seen = {}
        for ri, term in enumerate(terms):
            y = y0 + ri * rh
            seen.setdefault(term, []).append(ri)
            cmds.append(paint({"color": PANEL}, {"style": "fill"}))
            cmds.append({"drawRect": {"left": x, "top": y, "right": x + cw - 8,
                                      "bottom": y + rh - 8}})
            cmds += text_at(term, x + (cw - 8) / 2, y + 22, 8.5, TEXT, pan_x=0.0)
        # join the cells a language treats as the same word
        for term, rows in seen.items():
            if len(rows) > 1:
                cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.0}))
                cmds.append({"drawRect": {"left": x - 2, "top": y0 + rows[0] * rh - 2,
                                          "right": x + cw - 6,
                                          "bottom": y0 + rows[-1] * rh + rh - 6}})
    cmds += text_at("A box means the language uses one word for all the rows it spans.",
                    40.0, 448.0, 10.5, TEXT)
    cmds += text_at("- English merges both uncles and both aunts and ignores birth order; "
                    "Mandarin separates all six.", 40.0, 466.0, 9.5, DIM)
    title(cmds, W, H, "Six relations, four languages",
          "the biology is identical in every column")
    return {"header": header(W, H, "Kinship terms for six relations across four languages, "
                                   "showing which distinctions each language keeps"),
            "root": canvas(cmds, INK)}


# ── build ──────────────────────────────────────────────────────────────────────
BUILD = [("PHY-CM-00031", energy), ("PHY-CM-00032", collisions),
         ("PHY-CM-00033", pendulums), ("PHY-CM-00034", rotational),
         ("MTH-GEOM-00010", solids), ("MTH-GEOM-00011", geom_transformations),
         ("MTH-GEOM-00012", tessellations), ("BIO-MICR-00028", microbiomes),
         ("CSC-DS-00010", hash_tables), ("CHM-CR-00010", pathways),
         ("EAR-GEOP-00010", mantle), ("ENG-EE-00010", signal_processing),
         ("SOC-PSYC-00008", behaviour), ("SOC-PSYC-00009", development),
         ("SOC-ANTH-00010", migration), ("SOC-ANTH-00011", cultures)]

if __name__ == "__main__":
    for doc_id, fn in BUILD:
        name = use(doc_id)
        d = fn()
        (OUT / ("%s.json" % doc_id)).write_text(json.dumps(d, indent=1) + "\n")
        print("  %-16s %-9s %s" % (doc_id, name, d["header"]["contentDescription"][:44]))
    print("  %d documents" % len(BUILD))
