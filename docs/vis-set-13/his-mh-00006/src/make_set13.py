#!/usr/bin/env python3
"""Build set 13 of the visualization programme: 16 documents.

    python3 work/set-13/make_set13.py

Work order from `python3 tools/visplan.py set 13`. Opens Astronomy, which the corpus has not
touched before.

## The helper block changed: geometry is built by the player now

Sets 1-12 shipped their vertices. This set asks the player to generate them from
`meshPrimitive3D` instead, which is the same change that took the two Earth globes from
269 KB of JSON to 109 KB. Everything that used to be a loop writing `verts`/`indices` is now
a single op, and four documents here are spheres and rings, so it matters more than usual.

What the primitives are built around, which is the thing that costs time if you guess:

    sphere icosphere      centre, no axis       (icosphere's `segments` is a SUBDIVISION
                                                 level, 20*4^n triangles, not a slice count)
    cylinder              arbitrary from/to     - takes two endpoints, so no rotation needed
    cone sphericalDome    apex/cap toward +Y
    torus                 ring in the XZ plane  - lies flat; standing it up needs RX(90)
    lathe helix           built around Y
    the whole extrude*    profile in XY, depth along Z, centred on +/- depth/2
    plane                 XY facing +Z, and always exactly 2 triangles

Hazards carried from this week's primitive work, each paid for once already:

  sweep, not extrudePath, for a closed ribbon    extrudePath closes its ends by scanline
                                                 triangulation, which on a concave ring emits
                                                 zero-area triangles that rasterize as garbage
  pin ringsPerSpan on a tube                     ring spacing is 2*r*sin(pi/sides) of ARC, so
                                                 the thinner the tube the more rings it gets
  bevel < half the shortest contour edge         a wider bevel folds the inset through itself
                                                 and the normals go NaN
  no camera low over a big plane                 there is no near-plane clipping; a vertex a
                                                 hair in front of the eye is not rejected and
                                                 1/w throws the triangle across the frame
  omit `min` to make a drag wrap                 a plain-NaN minimum means "wrap at max"

And the rules the earlier sets paid for, unchanged:

  winding decides visibility     a wrongly wound mesh is invisible (F-008)
  embed bitmaps as base64        a file-named bitmap is not self-contained (F-030)
  clipRect is permanent          it intersects and never widens (F-021)
  textFromFloat wants a string   a numeric literal renders as 0, silently (F-020)
  expressions cap at 32 tokens   rcj writes longer ones that a device refuses (F-022)
  3D fills the document          a scene in a sized card projects outside it (F-013)
  clamp(min, max, value)         the value goes last
  2D rotate is DEGREES           while matrix3D rotate is radians
  render with --clock AND --seed the clock alone does not pin rand() (F-023)
"""

import base64
import hashlib
import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent
TAU = 2.0 * math.pi
HP = math.pi / 2.0


# ── document scaffolding ───────────────────────────────────────────────────────
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


def rect(x0, y0, x1, y1, colour):
    return [paint({"color": colour}, {"style": "fill"}),
            {"drawRect": {"left": x0, "top": y0, "right": x1, "bottom": y1}}]


def line(x0, y0, x1, y1, colour, w=1.5):
    return [paint({"color": colour}, {"style": "stroke"}, {"strokeWidth": w}),
            {"drawLine": {"x1": x0, "y1": y0, "x2": x1, "y2": y1}}]


def wrap(text, n):
    """Greedy wrap to lines of at most n characters."""
    out, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > n:
            out.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    if cur:
        out.append(cur)
    return out


def embedded_bitmap(name, rel_path):
    """A bitmap carried inside the document, so it is self-contained (F-030)."""
    data = (Path(__file__).resolve().parent.parent.parent / rel_path).read_bytes()
    return {"bitmaps": [{name: {"base64": base64.b64encode(data).decode("ascii")}}]}


# ── geometry, generated by the player ──────────────────────────────────────────
def prim(mesh_id, kind, **kw):
    spec = {"id": mesh_id, "primitive": kind}
    spec.update(kw)
    return {"meshPrimitive3D": spec}


def ball(mesh_id, radius, centre=(0, 0, 0), segments=24, uv=None):
    """A sphere. `uv` must be given explicitly to texture it — the default is `none`, and a
    textured sphere without it draws as a plain white object with nothing logged."""
    kw = {"radius": radius, "center": list(centre), "segments": segments}
    if uv:
        kw["uv"] = uv
    return prim(mesh_id, "sphere", **kw)


def rock(mesh_id, radius, centre=(0, 0, 0), level=1):
    """A low-poly lump. `level` is a subdivision count: 20*4^level triangles."""
    return prim(mesh_id, "icosphere", radius=radius, center=list(centre), segments=level)


def rod(mesh_id, p0, p1, radius=0.02, segments=10):
    """A cylinder between two arbitrary points — no rotation needed to aim it."""
    return prim(mesh_id, "cylinder", radius=radius, segments=segments,
                **{"from": [round(v, 5) for v in p0], "to": [round(v, 5) for v in p1]})


def ring(mesh_id, major, minor, centre=(0, 0, 0), segments=48):
    """A torus. Its ring lies in the XZ plane, so this is already flat — an orbit, not a
    wheel. Standing it up would need RX(90)."""
    return prim(mesh_id, "torus", majorRadius=major, minorRadius=minor,
                center=list(centre), segments=segments)


def disc(mesh_id, radius, depth=0.02, segments=40):
    """A coin in XY with its depth along Z; RX(-90) lays it flat."""
    return prim(mesh_id, "extrudeCircle", radius=radius, depth=depth,
                center=[0, 0, 0], segments=segments)


def ribbon(mesh_id, pts, half_w, thickness=0.01, closed_loop=True):
    """A flat band along a 3D path, as a `sweep`.

    Deliberately not `extrudePath`: that closes its ends by scanline triangulation, and on a
    concave ring it emits zero-area triangles whose edge functions are undefined — they
    rasterize as bands of garbage colour at glancing angles. A sweep has no caps to
    triangulate on a closed path, and it came out four times cheaper besides.
    """
    return prim(mesh_id, "sweep", closed=True, capStart=not closed_loop,
                capEnd=not closed_loop, center=[0, 0, 0], segments=0,
                section=[[-half_w, -thickness], [half_w, -thickness],
                         [half_w, thickness], [-half_w, thickness]],
                path=[[round(c, 5) for c in p] for p in pts])


def orbit_pts(radius, n=96, tilt=0.0, y=0.0):
    """A circular path in the XZ plane, optionally tilted about X."""
    out = []
    for i in range(n):
        a = TAU * i / n
        x, z = radius * math.cos(a), radius * math.sin(a)
        yy = y + z * math.sin(tilt)
        zz = z * math.cos(tilt)
        out.append((x, yy, zz))
    return out


# ── 3D staging ─────────────────────────────────────────────────────────────────
SPIN_PER_PX, TILT_PER_PX = 0.011, 0.005


def touch_orbit(spin_base, tilt_base, tilt_lo=-0.25, tilt_hi=1.05):
    """Two accumulating drag values.

    `touchExpression`, not an expression over touchX(): this one integrates, so it carries
    across drags instead of snapping back when the finger lifts. Spin omits `min`, which is
    how WRAP is spelled — the op reads a plain-NaN minimum as "wrap at max". Without it the
    scene stops part way round and the far side is unreachable.
    """
    return [
        {"touchExpression": {"name": "spinPx", "defaultValue": 0.0,
                             "max": TAU / SPIN_PER_PX, "stopMode": "gently",
                             "expression": "touchX()"}},
        {"touchExpression": {"name": "tiltPx", "defaultValue": 0.0,
                             "min": (tilt_lo - tilt_base) / TILT_PER_PX,
                             "max": (tilt_hi - tilt_base) / TILT_PER_PX,
                             "stopMode": "gently", "expression": "touchY()"}},
    ]


def spin_expr(base):
    return "spinPx * %s + %s" % (SPIN_PER_PX, base)


def tilt_expr(base):
    return "tiltPx * %s + %s" % (TILT_PER_PX, base)


def scene3d(W, H, dist, look_y, fov=0.8, near=0.4, far=120.0, lights=None):
    """Background, depth clear, camera and lights.

    `aspect` and the background rect are read from the live viewport, not baked: a hardcoded
    rect paints a small square in the corner of a phone screen, and a baked aspect stretches
    the whole scene vertically on a tall canvas. Both look perfect at the authored size.
    """
    return [
        paint({"color": INK}, {"style": "fill"}),
        {"drawRect": {"left": 0, "top": 0,
                      "right": "componentWidth()", "bottom": "componentHeight()"}},
        {"clearDepth3D": {}},
        {"camera3D": {"projection": "perspective", "fovY": fov,
                      "aspect": "componentWidth() / componentHeight()",
                      "near": near, "far": far,
                      "eye": [0.0, look_y,
                              "%s * max(1.0, componentHeight() / componentWidth())" % dist],
                      "center": [0.0, 0.0, 0.0], "up": [0, 1, 0]}},
        {"lights3D": {"lights": lights or [
            {"type": "directional", "color": "#FFFFF4E8", "dir": [-0.35, -0.62, -0.70],
             "intensity": 1.05},
            {"type": "directional", "color": "#FF5C7FB4", "dir": [0.60, 0.22, 0.50],
             "intensity": 0.38}]}},
    ]


def place(chain=()):
    """Reset the model matrix, then whatever this instance needs. There is no matrix stack,
    so every drawn thing restates its chain from identity."""
    return [{"matrix3D": {"op": "identity"}}] + list(chain)


def T(x=0, y=0, z=0):
    return {"matrix3D": {"op": "translate", "x": x, "y": y, "z": z}}


def RY(a):
    return {"matrix3D": {"op": "rotate", "angle": a, "axis": [0, 1, 0]}}


def RX(a):
    return {"matrix3D": {"op": "rotate", "angle": a, "axis": [1, 0, 0]}}


def draw(mesh_id, colour, mode="software-smooth"):
    return [paint({"color": colour}, {"style": "fill"}),
            {"drawMesh3D": {"mesh": mesh_id, "mode": mode}}]


# ── palettes ───────────────────────────────────────────────────────────────────
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


# ── 1. PHY-FM-00039  Pressure — static-diagram / 2D ────────────────────────────
# The teaching point is that pressure at a point has no direction: it pushes equally on
# every surface through that point, which is why the arrows on the base, the walls and the
# submerged plate are all the same length at the same depth.
def pressure():
    W, H = 600, 520
    cmds = []
    tx, ty, tw, th = 60.0, 110.0, 250.0, 330.0
    cmds += rect(tx, ty, tx + tw, ty + th, PANEL)
    # water
    surf = ty + 48.0
    cmds += rect(tx, surf, tx + tw, ty + th, "#4C5B8CEE" if INK != "#FFEDEFF2" else "#4C2F6BD8")
    cmds += line(tx, surf, tx + tw, surf, ACCENT, 2.0)
    cmds += text_at("surface", tx + 6, surf - 8, 10.0, ACCENT)
    cmds += [paint({"color": RULE}, {"style": "stroke"}, {"strokeWidth": 2.0}),
             {"drawRect": {"left": tx, "top": ty, "right": tx + tw, "bottom": ty + th}}]

    # depth rungs: arrow length is proportional to depth, and identical on every face
    for k in range(1, 5):
        d = k / 4.0
        y = surf + (ty + th - surf) * d
        L = 10.0 + 46.0 * d
        cmds += line(tx, y, tx + L, y, WARM, 2.2)                 # pushing right on the left wall
        cmds += line(tx + tw, y, tx + tw - L, y, WARM, 2.2)       # and left on the right wall
        cmds += text_at("%d m" % (k * 2), tx + tw + 12, y, 9.5, DIM)
    for k in range(1, 6):
        x = tx + tw * k / 6.0
        cmds += line(x, ty + th, x, ty + th - 56.0, WARM, 2.2)    # and up on the base

    # a plate held at mid depth: same pressure both sides, so it feels no net force
    py = surf + (ty + th - surf) * 0.55
    cmds += rect(tx + 70, py - 4, tx + 180, py + 4, TEXT)
    for s in (-1, 1):
        for x in (tx + 86, tx + 125, tx + 164):
            cmds += line(x, py + s * 6, x, py + s * 34, GOOD, 2.0)
    cmds += text_at("a submerged plate feels the same push from", 330.0, py - 16, 10.0, GOOD)
    cmds += text_at("above and below, so it does not move", 330.0, py - 2, 10.0, GOOD)

    # the law
    cmds += rect(330.0, 120.0, 566.0, 206.0, PANEL)
    cmds += text_at("p = p₀ + ρgh", 346.0, 150.0, 20.0, ACCENT)
    for i, s in enumerate(["p₀  pressure at the surface",
                           "ρ   density of the fluid",
                           "h   depth below the surface"]):
        cmds += text_at(s, 346.0, 170.0 + i * 15.0, 9.5, DIM)

    cmds += rect(330.0, 300.0, 566.0, 440.0, PANEL)
    cmds += text_at("What the arrows show", 346.0, 322.0, 12.0, TEXT)
    for i, ln in enumerate(wrap(
            "Arrow length is pressure. It grows with depth and nothing else — not with the "
            "width of the tank, not with how much water is in it. At the same depth the push "
            "on the wall, on the base and on a plate is identical, because pressure at a "
            "point acts equally in every direction.", 44)):
        cmds += text_at(ln, 346.0, 342.0 + i * 14.0, 9.5, DIM)

    title(cmds, W, H, "Pressure in a standing fluid",
          "depth sets it; shape and volume do not")
    return {"header": header(W, H, "Hydrostatic pressure shown as arrows that grow with "
                                   "depth and push equally on every surface"),
            "root": canvas(cmds, INK)}


# ── 2. PHY-FM-00040  Aerodynamics — annotated-layout / 2D ──────────────────────
# Streamlines are pushed around the section rather than drawn as gently kinked straight
# lines: the body displaces them, they crowd above where the flow is faster, and they leave
# deflected DOWNWARD. The downwash is the point — the wing turns air down, and lift is the
# reaction. A first attempt drew the deflection as a small analytic bump and it read as a
# flat line with a dent in it, which teaches nothing.
def aerodynamics():
    W, H = 640, 500
    cmds = []
    le, chord, cy = 170.0, 300.0, 268.0        # leading edge x, chord length, chord height
    aoa = math.radians(10.0)

    def foil_pt(t, upper):
        """NACA-ish cambered section in chord coordinates, rotated by the angle of attack."""
        th = 0.60 * (1.4845 * math.sqrt(t) - 0.63 * t - 1.758 * t * t
                     + 1.4215 * t ** 3 - 0.5075 * t ** 4)
        cam = 0.26 * (1.0 - (2.0 * t - 1.0) ** 2)
        xc, yc = (t - 0.5) * chord, (-cam + (-th if upper else th)) * chord * 0.22
        return (le + chord * 0.5 + xc * math.cos(aoa) + yc * math.sin(aoa),
                cy - xc * math.sin(aoa) + yc * math.cos(aoa))

    upper = [foil_pt(i / 60.0, True) for i in range(61)]
    lower = [foil_pt(i / 60.0, False) for i in range(61)]
    poly = upper + lower[::-1]

    # Camber line and half-thickness as functions of screen x. Taken from the midpoint and
    # separation of the two surfaces at the same chord station, so both go smoothly to zero at
    # the leading and trailing edges — which is what keeps the streamlines smooth. A first
    # attempt clamped each line outside the silhouette with min(), and the clamp switching on
    # and off put a hard step in every line at the leading edge.
    camber = []
    for u, l in zip(upper, lower):
        camber.append(((u[0] + l[0]) * 0.5, (u[1] + l[1]) * 0.5,
                       math.hypot(u[0] - l[0], u[1] - l[1]) * 0.5))
    xs0, xs1 = camber[0][0], camber[-1][0]
    max_half = max(c[2] for c in camber) or 1.0

    def body_at(x):
        """(camber y, half thickness) at this x, both zero outside the section."""
        if x <= xs0 or x >= xs1:
            return cy, 0.0
        for a, b in zip(camber, camber[1:]):
            if a[0] <= x <= b[0] and b[0] != a[0]:
                f = (x - a[0]) / (b[0] - a[0])
                return a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f
        return cy, 0.0

    NS = 80                      # samples per streamline, and the dot path's resolution

    def streamline(h):
        """One line, h pixels from the free stream far upstream. Negative is above.

        The free stream is HORIZONTAL — the wing is at an angle to the air, not the air to
        the wing. Drawing the lines along the chord instead made the oncoming air look as if
        it arrived already tilted, which is the one thing the picture must not say.
        """
        pts = []
        for i in range(NS + 1):
            x = 24.0 + 594.0 * i / NS
            yc, half = body_at(x)
            # Both displacements are windowed by the section's own thickness, which is zero
            # at the leading and trailing edges. Without that window the camber term — and a
            # constant stand-off — switch on the instant x enters the section, and every
            # streamline gets a hard vertical step there.
            env = half / max_half
            y = cy + h
            y += (yc - cy) * env * math.exp(-abs(h) / 58.0)     # carried by the body
            y -= (1.0 if h < 0 else -1.0) * (half + 7.0 * env) * math.exp(-abs(h) / 52.0)
            if x > xs1:                                         # downwash behind it
                f = 1.0 - math.exp(-(x - xs1) / 80.0)
                y += 32.0 * f * math.exp(-abs(h) / 130.0)
            pts.append((x, y))
        return pts

    HS = (-150.0, -112.0, -78.0, -48.0, -22.0, 24.0, 54.0, 92.0, 136.0)
    lines = [streamline(h) for h in HS]

    # Dot speed comes from the streamline SPACING, not from an assertion. Continuity says
    # the flow through the gap between two streamlines is the same everywhere along them, so
    # where the gap narrows the air must be moving faster. Measuring the gap at mid-chord and
    # taking its reciprocal is therefore the speed, and the crowding visible above the wing
    # and the dots overtaking there are the same fact told twice.
    # Each line is paired with its neighbour ON THE SAME SIDE. Pairing by index alone put
    # the innermost upper line next to the innermost lower one, and the gap between those two
    # spans the aerofoil — so the fastest-moving line in the picture came out the slowest.
    mid_i = int(NS * (le + chord * 0.5 - 24.0) / 594.0)
    n_above = sum(1 for h in HS if h < 0)

    # Each line's channel is bounded on one side by its neighbour, and for the line hugging
    # the wing by the WING. That distinction matters: in a displacement model the gaps
    # between streamlines widen near the body, and all of the crowding ends up concentrated
    # in the channel between the surface and the first line. Measuring the innermost line
    # against its neighbour instead made the fastest-moving line in the picture the slowest.
    mid_x = 24.0 + 594.0 * mid_i / NS
    yc_mid, half_mid = body_at(mid_x)

    speeds = []
    for k, h in enumerate(HS):
        inner_most = (k == n_above - 1) or (k == len(HS) - 1 and False) or (k == n_above)
        if k == n_above - 1:                               # closest above the wing
            near = abs(lines[k][mid_i][1] - (yc_mid - half_mid))
            far = abs(lines[k][0][1] - cy)
        elif k == n_above:                                 # closest below it
            near = abs(lines[k][mid_i][1] - (yc_mid + half_mid))
            far = abs(lines[k][0][1] - cy)
        else:
            j = (k + 1) if (k + 1 < n_above or (k >= n_above and k + 1 < len(HS))) else k - 1
            near = abs(lines[k][mid_i][1] - lines[j][mid_i][1])
            far = abs(lines[k][0][1] - lines[j][0][1])
        speeds.append(max(0.6, min(2.2, far / max(near, 1e-3))))

    for k, h in enumerate(HS):
        above = h < 0
        cmds.append(paint({"color": ACCENT if above else RULE}, {"style": "stroke"},
                          {"strokeWidth": 2.0 if above else 1.5}))
        for a, b in zip(lines[k], lines[k][1:]):
            cmds.append({"drawLine": {"x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1]}})

    # the section, filled so it reads as a solid body rather than a hairline
    cmds.append(paint({"color": TEXT}, {"style": "fill"}))
    cmds.append({"pathCreate": {"id": "foil", "x": poly[0][0], "y": poly[0][1]}})
    for px, py in poly[1:]:
        cmds.append({"pathAppendLineTo": {"path": "foil", "x": px, "y": py}})
    cmds.append({"pathAppendClose": {"path": "foil"}})
    cmds.append({"drawPath": {"path": "foil"}})

    # chord line, horizontal reference and the angle between them
    # Tracer dots. x advances smoothly with the phase; y is read from the line's own sampled
    # path, so a dot cannot drift off the line it belongs to. One shared x because every
    # streamline is sampled at the same x values.
    cmds.append(var("ft", "continuousSec()"))
    cmds.append(paint({"color": "#FFF2F6FF"}, {"style": "fill"}))
    for k in range(len(HS)):
        for j in range(4):
            ph = "fp%d_%d" % (k, j)
            cmds.append(var(ph, "((ft * %0.4f + %0.3f) %% 1.0)" % (speeds[k] * 0.17, j / 4.0)))
            cmds.append({"drawCircle": {
                "cx": "24.0 + 594.0 * %s" % ph,
                "cy": "arrayGet(@sy%d, floor(%s * %d.0))" % (k, ph, NS),
                "radius": 2.6}})

    # chord, and the horizontal the angle of attack is measured from
    c0, c1 = camber[0], camber[-1]
    cmds += line(c0[0] - 20, c0[1], c1[0] + 48, c1[1], DIM, 1.2)
    cmds += line(c0[0] - 20, c0[1], c1[0] + 48, c0[1], DIM, 1.2)
    cmds += text_at("α = 10° from the oncoming air", c1[0] + 10, c0[1] + 20, 10.0, DIM)

    # forces, relative to the free stream and not to the chord
    ax, ay = le + chord * 0.42, cy - 22.0
    cmds += line(ax, ay, ax, ay - 128.0, GOOD, 4.0)
    cmds += line(ax - 7, ay - 116, ax, ay - 132, GOOD, 4.0)
    cmds += line(ax + 7, ay - 116, ax, ay - 132, GOOD, 4.0)
    cmds += text_at("lift", ax + 12, ay - 120, 13.0, GOOD)
    cmds += line(ax, ay, ax + 96.0, ay, HOT, 3.4)
    cmds += line(ax + 86, ay - 6, ax + 100, ay, HOT, 3.4)
    cmds += line(ax + 86, ay + 6, ax + 100, ay, HOT, 3.4)
    cmds += text_at("drag", ax + 104, ay, 12.0, HOT)

    cmds += text_at("crowded above — faster air, lower pressure", 30.0, 104.0, 11.0, ACCENT)
    cmds += text_at("spread below — slower air, higher pressure", 30.0, 430.0, 11.0, TEXT)
    cmds += text_at("and it all leaves pointing down", 430.0, 400.0, 11.0, WARM)

    cmds += rect(24.0, 446.0, 616.0, 492.0, PANEL)
    for i, ln in enumerate(wrap(
            "The wing turns air downward and lift is the reaction to that. Pressure "
            "difference and downwash are two descriptions of one event, not two causes. Past "
            "about 15° the flow over the top separates and lift collapses — a stall is an "
            "angle, not a speed.", 88)):
        cmds += text_at(ln, 36.0, 462.0 + i * 13.0, 9.0, DIM)

    title(cmds, W, H, "How a wing makes lift", "watch the dots overtake above the wing")
    arrays = [{"sy%d" % k: [round(p[1], 2) for p in lines[k]]} for k in range(len(HS))]
    return {"header": header(W, H, "An aerofoil at ten degrees with tracer dots running the "
                                   "streamlines, faster where the flow crowds above the wing"),
            "resources": {"floatArrays": arrays},
            "root": canvas(cmds, INK)}


# ── 3. MTH-TRIG-00015  Trigonometric identities — data-plot / 2D ───────────────
# sin²+cos²=1 drawn as two stacked areas that always reach the same ceiling: the identity
# as a picture rather than a rearrangement.
def trig_identities():
    W, H = 640, 540
    cmds = []
    px, py, pw, ph = 60.0, 100.0, 520.0, 170.0
    cmds += rect(px, py, px + pw, py + ph, PANEL)

    def X(t):
        return px + pw * t / TAU

    def Y(v):
        return py + ph * (1.0 - v)

    N = 160
    for i in range(N):
        t0, t1 = TAU * i / N, TAU * (i + 1) / N
        s0, s1 = math.sin(t0) ** 2, math.sin(t1) ** 2
        cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": X(t0), "top": Y(s0), "right": X(t1) + 0.6,
                                  "bottom": Y(0.0)}})
        cmds.append(paint({"color": GOOD}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": X(t0), "top": Y(1.0), "right": X(t1) + 0.6,
                                  "bottom": Y(s0)}})
    cmds += line(px, Y(1.0), px + pw, Y(1.0), TEXT, 2.0)
    cmds += text_at("1", px - 10, Y(1.0), 10.0, TEXT, pan_x=1.0)
    cmds += text_at("sin²θ", px + 14, Y(0.16), 12.0, INK)
    cmds += text_at("cos²θ", px + 14, Y(0.86), 12.0, INK)
    cmds += text_at("the two always stack to exactly 1 — that is the identity",
                    px + 120, py + ph + 18, 10.0, DIM)
    for k in range(5):
        t = TAU * k / 4.0
        cmds += line(X(t), py + ph, X(t), py + ph + 5, RULE, 1.2)
        cmds += text_at(["0", "π/2", "π", "3π/2", "2π"][k], X(t), py + ph + 16, 9.0,
                        DIM, pan_x=0.0)

    # the addition formula, built from its two pieces
    qx, qy, qw, qh = 60.0, 330.0, 520.0, 150.0
    cmds += rect(qx, qy, qx + qw, qy + qh, PANEL)
    b = math.radians(50.0)

    def plot(f, colour, w=2.0):
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"strokeWidth": w}))
        prev = None
        for i in range(161):
            t = TAU * i / 160.0
            x = qx + qw * i / 160.0
            y = qy + qh * (0.5 - 0.42 * f(t))
            if prev:
                cmds.append({"drawLine": {"x1": prev[0], "y1": prev[1], "x2": x, "y2": y}})
            prev = (x, y)

    plot(lambda t: math.sin(t) * math.cos(b), DIM, 1.4)
    plot(lambda t: math.cos(t) * math.sin(b), RULE, 1.4)
    plot(lambda t: math.sin(t + b), ACCENT, 2.6)
    cmds += line(qx, qy + qh * 0.5, qx + qw, qy + qh * 0.5, RULE, 1.0)
    cmds += text_at("sin(θ+φ) = sinθ cosφ + cosθ sinφ", qx + 12, qy + 22, 13.0, ACCENT)
    cmds += text_at("the thick curve is the sum of the two faint ones, everywhere",
                    qx + 12, qy + qh + 18, 10.0, DIM)

    cmds += text_at("φ = 50°", qx + qw - 12, qy + 22, 11.0, WARM, pan_x=1.0)
    title(cmds, W, H, "Two identities, drawn",
          "an identity holds at every θ, so it has a shape")
    return {"header": header(W, H, "The Pythagorean identity as two stacked areas and the "
                                   "sine addition formula as a sum of two curves"),
            "root": canvas(cmds, INK)}


# ── 4. CSC-CA-00013  Memory hierarchy — path-form / 2D ─────────────────────────
# Latency on a log scale, because the point of the hierarchy is that the steps are
# multiplicative. The human-scale column is what makes 100 ns versus 10 ms land.
def memory_hierarchy():
    W, H = 620, 560
    cmds = []
    LEVELS = [("registers", 0.3, "1 KB", "1 s"),
              ("L1 cache", 1.0, "64 KB", "3 s"),
              ("L2 cache", 4.0, "1 MB", "13 s"),
              ("L3 cache", 20.0, "32 MB", "1 min"),
              ("DRAM", 80.0, "32 GB", "4 min"),
              ("SSD", 100000.0, "2 TB", "3 days"),
              ("spinning disk", 8000000.0, "16 TB", "8 months")]
    x0, y0, w = 44.0, 110.0, 300.0
    lo, hi = math.log10(0.3), math.log10(8000000.0)
    for i, (name, ns, size, human) in enumerate(LEVELS):
        y = y0 + i * 56.0
        f = (math.log10(ns) - lo) / (hi - lo)
        bar = 18.0 + (w - 18.0) * f
        col = [GOOD, GOOD, ACCENT, ACCENT, WARM, HOT, HOT][i]
        cmds += rect(x0, y, x0 + bar, y + 26.0, col)
        cmds += text_at(name, x0 + 6, y + 17, 11.5, INK)
        cmds += text_at("%s ns" % ("{:,.0f}".format(ns) if ns >= 1 else "0.3"),
                        x0 + bar + 8, y + 17, 10.0, TEXT)
        cmds += text_at(size, x0 + w + 96, y + 17, 10.0, DIM)
        cmds += text_at(human, x0 + w + 160, y + 17, 10.5, col)
        if i:
            cmds += line(x0 + 9, y - 30, x0 + 9, y, RULE, 1.2)
    cmds += text_at("capacity", x0 + w + 96, y0 - 14, 9.5, DIM)
    cmds += text_at("if one cycle were a second", x0 + w + 160, y0 - 14, 9.5, DIM)

    cmds += rect(36.0, 494.0, 584.0, 544.0, PANEL)
    for i, ln in enumerate(wrap(
            "Each step down is roughly four times slower than the one above until DRAM, and "
            "then the floor falls away: an SSD is a thousand times slower again. Caches "
            "exist because that cliff is unaffordable, and a cache miss costs what the next "
            "level costs, not what the cache costs.", 84)):
        cmds += text_at(ln, 48.0, 512.0 + i * 14.0, 9.5, DIM)

    title(cmds, W, H, "The memory hierarchy", "latency on a log scale, and in human time")
    return {"header": header(W, H, "Memory levels from registers to disk with latency on a "
                                   "logarithmic scale and a human-time column"),
            "root": canvas(cmds, INK)}


# ── 5. BIO-ANAT-00034  Digestive system — expression-animation / 2D ────────────
# Peristalsis is the whole mechanism: a ring of muscle contracts behind the bolus and
# relaxes ahead of it, so the food is squeezed along. The wave travels; the tissue does not.
def digestion():
    W, H = 620, 540
    cmds = [var("t", "continuousSec()")]
    gx, gy, gw = 70.0, 120.0, 480.0
    seg = 7

    # the tract as a chain of segments, each one's bore driven by the same travelling wave
    for i in range(seg):
        x0 = gx + gw * i / seg
        x1 = gx + gw * (i + 1) / seg
        phase = "%0.4f" % (TAU * i / seg)
        # contraction in 0..1; the wave moves left to right at one segment per 0.45 s
        cmds.append(var("c%d" % i, "0.5 + 0.5 * sin(t * 2.6 - %s)" % phase))
        cmds.append(var("h%d" % i, "14.0 + 26.0 * (1.0 - c%d)" % i))
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRoundRect": {"left": x0, "top": "160.0 - h%d" % i,
                                       "right": x1 + 1.0, "bottom": "160.0 + h%d" % i,
                                       "rx": 10.0, "ry": 10.0}})
        cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
        cmds.append({"drawRoundRect": {"left": x0 + 2, "top": "162.0 - h%d" % i,
                                       "right": x1 - 1.0, "bottom": "158.0 + h%d" % i,
                                       "rx": 8.0, "ry": 8.0}})

    # the bolus rides the relaxed part of the wave
    cmds.append(var("bx", "%0.1f + %0.1f * ((t * 0.26) %% 1.0)" % (gx + 20.0, gw - 40.0)))
    cmds += [paint({"color": WARM}, {"style": "fill"}),
             {"drawCircle": {"cx": "bx", "cy": 160.0, "radius": 15.0}}]
    cmds += text_at("bolus", "bx", 196.0, 10.0, WARM, pan_x=0.0)

    cmds += text_at("contracted behind", gx + 10, 108.0, 10.0, DIM)
    cmds += text_at("relaxed ahead", gx + gw - 10, 108.0, 10.0, DIM, pan_x=1.0)

    # the tract end to end, with transit times — the reason the organs differ in length
    stages = [("mouth / oesophagus", "8 s", 0.06), ("stomach", "2–4 h", 0.20),
              ("small intestine", "4–6 h", 0.56), ("large intestine", "12–48 h", 0.84)]
    by = 300.0
    cmds += rect(gx, by, gx + gw, by + 26.0, PANEL)
    for name, dur, f in stages:
        x = gx + gw * f
        cmds += line(x, by, x, by + 26.0, ACCENT, 2.0)
    for i, (name, dur, f) in enumerate(stages):
        y = by + 54.0 + i * 36.0
        cmds += line(gx + gw * f, by + 26.0, gx + gw * f, y - 10, RULE, 1.0)
        cmds += text_at(name, gx + gw * f, y, 11.0, TEXT)
        cmds += text_at(dur, gx + gw * f, y + 14, 10.0, GOOD)

    cmds += rect(36.0, 474.0, 584.0, 524.0, PANEL)
    for i, ln in enumerate(wrap(
            "The wave is the mechanism, not the muscle. A ring contracts behind and relaxes "
            "ahead, so the contents move even against gravity — which is why you can swallow "
            "upside down. Transit time varies a hundredfold along the tract because each "
            "section is doing a different job.", 86)):
        cmds += text_at(ln, 48.0, 492.0 + i * 13.0, 9.0, DIM)

    title(cmds, W, H, "Peristalsis", "a travelling squeeze, not a push")
    return {"header": header(W, H, "A travelling wave of contraction moving a bolus along "
                                   "the gut, with transit times for each section"),
            "root": canvas(cmds, INK)}


# ── 6. CHM-CR-00013  Reaction kinetics — particle-system / 2D ──────────────────
# Rate = k[A][B] is a statement about collisions: double either population and you double
# the number of encounters per second. The particles here are the argument.
def kinetics():
    W, H = 620, 560
    cmds = []
    bx, by, bw, bh = 56.0, 112.0, 300.0, 250.0
    cmds += rect(bx, by, bx + bw, by + bh, PANEL)

    # Two systems rather than one, so A and B are actually distinguishable — a single
    # system draws with one paint, and "A and B" in the caption over one colour of dot is a
    # caption that lies. Coordinates are LOCAL to the box so the wrap is a plain modulo, and
    # `rand()` takes no argument: `rand(0)` returns the same value for every particle and the
    # whole population stacks in one spot.
    for sysname, count, colour, rad in (("molA", 26, ACCENT, "3.2"), ("molB", 13, WARM, "4.6")):
        cmds.append({"createParticles": {
            "id": sysname, "count": count,
            "variables": [sysname + "x", sysname + "y", sysname + "vx", sysname + "vy"],
            "initialValues": ["rand() * %0.1f" % bw, "rand() * %0.1f" % bh,
                              "(rand() - 0.5) * 3.0", "(rand() - 0.5) * 3.0"]}})
        cmds.append({"particlesLoop": {
            "system": sysname,
            "equations": ["(%sx + %svx + %0.1f) %% %0.1f" % (sysname, sysname, bw, bw),
                          "(%sy + %svy + %0.1f) %% %0.1f" % (sysname, sysname, bh, bh),
                          sysname + "vx", sysname + "vy"],
            "commands": [
                paint({"color": colour}, {"style": "fill"}),
                {"drawCircle": {"cx": "%0.1f + %sx" % (bx, sysname),
                                "cy": "%0.1f + %sy" % (by, sysname), "radius": rad}},
            ]}})
    cmds += text_at("A and B, moving and colliding", bx, by - 10, 10.0, DIM)

    # rate against concentration: doubling either reactant doubles the encounter rate
    px0, py0, pw, ph = 390.0, 112.0, 182.0, 250.0
    cmds += rect(px0, py0, px0 + pw, py0 + ph, PANEL)
    for k in range(5):
        y = py0 + ph * k / 4.0
        cmds += line(px0, y, px0 + pw, y, RULE, 0.8)
    prev = None
    for i in range(41):
        c = i / 40.0
        x = px0 + pw * c
        y = py0 + ph * (1.0 - c)
        if prev:
            cmds += line(prev[0], prev[1], x, y, ACCENT, 2.4)
        prev = (x, y)
    cmds += text_at("rate", px0 + 8, py0 + 18, 11.0, ACCENT)
    cmds += text_at("[A]", px0 + pw - 8, py0 + ph - 10, 10.0, DIM, pan_x=1.0)
    cmds += text_at("first order in A: a straight line", px0, py0 + ph + 18, 9.5, DIM)

    cmds += text_at("rate = k [A] [B]", 56.0, 420.0, 22.0, WARM)
    for i, (sym, what) in enumerate((("k", "how often a collision actually reacts — "
                                           "orientation and energy, not numbers"),
                                     ("[A] [B]", "how often the two meet at all"))):
        cmds += text_at(sym, 56.0, 452.0 + i * 20.0, 11.0, TEXT)
        cmds += text_at(what, 136.0, 452.0 + i * 20.0, 9.5, DIM)

    cmds += rect(44.0, 498.0, 576.0, 544.0, PANEL)
    for i, ln in enumerate(wrap(
            "Temperature enters through k, not through the concentrations: heating does not "
            "add molecules, it makes a larger fraction of the collisions energetic enough to "
            "matter. That is why a ten-degree rise can double a rate.", 84)):
        cmds += text_at(ln, 56.0, 516.0 + i * 13.0, 9.0, DIM)

    title(cmds, W, H, "Why rate depends on concentration",
          "a rate law is a statement about collisions")
    return {"header": header(W, H, "Colliding particles beside a first-order rate plot, "
                                   "showing that rate follows the number of encounters"),
            "root": canvas(cmds, INK)}


# ── 7. EAR-METE-00013  Storms — interactive / 2D ───────────────────────────────
# Drag to move through the three stages. The updraught-only, updraught-and-downdraught,
# downdraught-only sequence is the whole life cycle, and it is why a storm kills itself.
def storms():
    W, H = 640, 560
    # Opens at the mature stage, not at zero. The rest state is what every still of this
    # document shows — the contact sheet, the gallery card — and at stage zero the cloud has
    # no height at all, so the document read as blank until it was touched.
    cmds = [{"touchExpression": {"name": "sPx", "defaultValue": 165.0,
                                 "min": 0.0, "max": 340.0, "stopMode": "gently",
                                 "expression": "touchX()"}},
            var("st", "sPx / 340.0"),
            var("up", "clamp(0.0, 1.0, 1.6 - abs(st - 0.30) * 3.4)"),
            var("dn", "clamp(0.0, 1.0, (st - 0.34) * 2.6)")]
    gx, gy, gw, gh = 60.0, 120.0, 400.0, 300.0
    cmds += rect(gx, gy, gx + gw, gy + gh, PANEL)
    cmds += line(gx, gy + gh, gx + gw, gy + gh, RULE, 2.0)
    cmds += text_at("ground", gx + 4, gy + gh + 16, 9.5, DIM)

    # the cloud grows with the stage
    cmds.append(var("top", "%0.1f - 220.0 * clamp(0.1, 1.0, st * 1.7)" % (gy + gh)))
    cmds += [paint({"color": DIM}, {"style": "fill"})]
    cmds.append({"drawRoundRect": {"left": gx + 90, "top": "top", "right": gx + 310,
                                   "bottom": gy + gh - 20.0, "rx": 26.0, "ry": 26.0}})
    # anvil, only once the top is high
    cmds.append(var("anv", "clamp(0.0, 1.0, (st - 0.38) * 3.4)"))
    cmds += [paint({"color": TEXT}, {"style": "fill"})]
    cmds.append({"drawRoundRect": {"left": "%0.1f - 110.0 * anv" % (gx + 200),
                                   "top": "top - 6.0",
                                   "right": "%0.1f + 110.0 * anv" % (gx + 200),
                                   "bottom": "top + 22.0", "rx": 11.0, "ry": 11.0}})

    # the two currents, each with its own window of the life cycle
    for i in range(4):
        x = gx + 120.0 + i * 46.0
        cmds += [paint({"color": GOOD}, {"style": "stroke"}, {"strokeWidth": 3.0})]
        cmds.append({"drawLine": {"x1": x, "y1": gy + gh - 26.0,
                                  "x2": x, "y2": "%0.1f - 150.0 * up" % (gy + gh - 26.0)}})
    for i in range(3):
        x = gx + 196.0 + i * 46.0
        cmds += [paint({"color": ACCENT}, {"style": "stroke"}, {"strokeWidth": 3.0})]
        cmds.append({"drawLine": {"x1": x, "y1": "%0.1f - 150.0 * dn" % (gy + gh - 26.0),
                                  "x2": x, "y2": gy + gh - 26.0}})
    cmds += text_at("updraught", gx + 100, gy + 38, 10.5, GOOD)
    cmds += text_at("downdraught + rain", gx + 230, gy + 38, 10.5, ACCENT)

    # the scrubber
    sy = 470.0
    cmds += rect(gx, sy, gx + 340.0, sy + 8.0, PANEL)
    cmds += [paint({"color": WARM}, {"style": "fill"})]
    cmds.append({"drawCircle": {"cx": "%0.1f + sPx" % gx, "cy": sy + 4.0, "radius": 10.0}})
    cmds += text_at("drag", gx, sy + 32.0, 10.0, WARM)
    for name, f in (("cumulus", 0.0), ("mature", 0.45), ("dissipating", 0.92)):
        cmds += text_at(name, gx + 340.0 * f, sy - 14.0, 10.0, DIM,
                        pan_x=0.0 if 0 < f < 0.9 else (-1.0 if f == 0 else 1.0))

    cmds += rect(492.0, 120.0, 616.0, 420.0, PANEL)
    cmds += text_at("Why it ends", 504.0, 146.0, 12.0, TEXT)
    for i, ln in enumerate(wrap(
            "Rain falling through the updraught drags air down with it. Once the downdraught "
            "reaches the ground it spreads out and cuts off the warm inflow the storm was "
            "feeding on. The storm is destroyed by its own rain.", 20)):
        cmds += text_at(ln, 504.0, 168.0 + i * 14.0, 9.5, DIM)

    title(cmds, W, H, "The life of a thunderstorm", "drag through the three stages")
    return {"header": header(W, H, "A thunderstorm cross-section with a draggable scrubber "
                                   "through cumulus, mature and dissipating stages"),
            "root": canvas(cmds, INK)}


# ── 8. ENG-CE-00013  Buildings — raster-and-text / 2D ──────────────────────────
# Two load paths, drawn as two columns of blocks. Gravity accumulates downward and is the
# easy one; wind is a bending moment that grows as the square of height, which is why tall
# buildings are shaped by lateral load and not by weight.
def buildings():
    W, H = 620, 580
    cmds = []
    floors = 14
    bx, by, bw, fh = 90.0, 118.0, 150.0, 28.0

    # the frame
    for i in range(floors):
        y = by + i * fh
        cmds += rect(bx, y, bx + bw, y + fh - 3.0, PANEL)
        cmds += rect(bx + bw * 0.40, y, bx + bw * 0.60, y + fh - 3.0, RULE)
    cmds += rect(bx - 16.0, by + floors * fh, bx + bw + 16.0, by + floors * fh + 16.0, RULE)
    cmds += text_at("core", bx + bw * 0.5, by - 10.0, 10.0, DIM, pan_x=0.0)
    cmds += text_at("foundation", bx + bw * 0.5, by + floors * fh + 32.0, 10.0, DIM, pan_x=0.0)

    # gravity: accumulating, drawn as a widening bar
    for i in range(floors):
        y = by + i * fh
        w = 4.0 + 46.0 * (i + 1) / floors
        cmds += rect(bx + bw + 26.0, y + 4, bx + bw + 26.0 + w, y + fh - 7.0, GOOD)
    cmds += text_at("gravity", bx + bw + 26.0, by - 10.0, 10.5, GOOD)
    cmds += text_at("each floor adds its own weight to everything below — linear in height",
                    bx + bw + 26.0, by + floors * fh + 20.0, 9.0, DIM)

    # wind: pressure roughly uniform, but the MOMENT it makes grows as height squared
    for i in range(floors):
        y = by + i * fh
        cmds += line(bx - 76.0, y + fh * 0.5, bx - 20.0, y + fh * 0.5, ACCENT, 2.0)
    cmds += text_at("wind", bx - 76.0, by - 10.0, 10.5, ACCENT)
    prev = None
    for i in range(floors + 1):
        h = 1.0 - i / floors
        x = bx - 20.0 - 56.0 * h * h
        y = by + i * fh
        if prev:
            cmds += line(prev[0], prev[1], x, y, HOT, 2.6)
        prev = (x, y)
    cmds += text_at("overturning moment ∝ height²", 20.0, by + floors * fh + 20.0, 9.5, HOT)

    cmds += rect(330.0, 118.0, 596.0, 300.0, PANEL)
    cmds += text_at("Which one shapes the building", 344.0, 144.0, 12.0, TEXT)
    for i, ln in enumerate(wrap(
            "Below about ten storeys, weight decides the structure. Above that, wind does: "
            "the moment it has to resist grows with the square of height while the building's "
            "ability to resist it grows only with its width. That is why tall buildings get a "
            "stiff core, or a braced perimeter, long before they need thicker columns.", 40)):
        cmds += text_at(ln, 344.0, 166.0 + i * 14.0, 9.5, DIM)

    cmds += rect(330.0, 322.0, 596.0, 470.0, PANEL)
    cmds += text_at("Load paths", 344.0, 348.0, 12.0, TEXT)
    for i, (name, note, col) in enumerate((
            ("slab → beam", "floor load to the frame", GOOD),
            ("beam → column", "gathered at each level", GOOD),
            ("column → foundation", "accumulated weight", GOOD),
            ("façade → core", "wind, as shear and moment", ACCENT))):
        y = 372.0 + i * 24.0
        cmds += rect(344.0, y - 8, 349.0, y + 5, col)
        cmds += text_at(name, 358.0, y, 10.5, col)
        cmds += text_at(note, 470.0, y, 9.0, DIM)

    title(cmds, W, H, "What holds a tall building up", "two load paths, and which one wins")
    return {"header": header(W, H, "A tall building's gravity and wind load paths, with the "
                                   "overturning moment growing as the square of height"),
            "root": canvas(cmds, INK)}


# ── 9. HIS-MH-00005  Modern History — static-diagram / 2D ──────────────────────
# Berlin sat 160 km inside the Soviet zone and was itself split four ways. Every crisis of
# the next forty-four years follows from that one piece of geometry, so the map is the
# explanation.
def divided_germany():
    W, H = 620, 560
    cmds = []
    mx, my, mw, mh = 70.0, 110.0, 330.0, 330.0
    ZONES = [("Soviet", HOT, 0.52, 0.0, 0.48, 1.0),
             ("British", ACCENT, 0.0, 0.0, 0.30, 0.46),
             ("Soviet ", HOT, 0.0, 0.0, 0.0, 0.0),
             ("American", WARM, 0.18, 0.46, 0.34, 0.54),
             ("French", GOOD, 0.0, 0.30, 0.18, 0.46)]
    for name, col, fx, fy, fw, fh in ZONES:
        if fw <= 0:
            continue
        cmds += rect(mx + mw * fx, my + mh * fy, mx + mw * (fx + fw),
                     my + mh * (fy + fh), col)
    cmds += rect(mx, my + mh * 0.46, mx + mw * 0.18, my + mh * 1.0, GOOD)
    cmds += rect(mx + mw * 0.30, my, mx + mw * 0.52, my + mh * 0.46, ACCENT)
    cmds += [paint({"color": INK}, {"style": "stroke"}, {"strokeWidth": 2.0}),
             {"drawRect": {"left": mx, "top": my, "right": mx + mw, "bottom": my + mh}}]

    # Berlin: deep inside the Soviet zone, and itself divided
    bx, byy, bs = mx + mw * 0.74, my + mh * 0.34, 44.0
    cmds += rect(bx, byy, bx + bs, byy + bs, INK)
    for i, col in enumerate((HOT, ACCENT, WARM, GOOD)):
        cmds += rect(bx + bs * 0.5 * (i % 2) + 2, byy + bs * 0.5 * (i // 2) + 2,
                     bx + bs * 0.5 * (i % 2 + 1) - 2, byy + bs * 0.5 * (i // 2 + 1) - 2, col)
    cmds += text_at("Berlin", bx + bs * 0.5, byy - 8.0, 10.5, TEXT, pan_x=0.0)
    cmds += line(bx + bs, byy + bs * 0.5, mx + mw + 30.0, byy + bs * 0.5, RULE, 1.2)
    cmds += text_at("divided the same four ways,", mx + mw + 36.0, byy + bs * 0.5 - 7, 9.5, TEXT)
    cmds += text_at("160 km inside the Soviet zone", mx + mw + 36.0, byy + bs * 0.5 + 7, 9.5, DIM)

    for i, (name, col) in enumerate((("Soviet", HOT), ("British", ACCENT),
                                     ("American", WARM), ("French", GOOD))):
        y = 470.0 + (i // 2) * 24.0
        x = 70.0 + (i % 2) * 180.0
        cmds += rect(x, y - 9, x + 14, y + 4, col)
        cmds += text_at(name, x + 22, y, 10.5, TEXT)

    cmds += rect(430.0, 190.0, 596.0, 430.0, PANEL)
    cmds += text_at("What followed", 444.0, 216.0, 12.0, TEXT)
    for i, ln in enumerate(wrap(
            "An enclave reachable only by road, rail and air corridors through hostile "
            "territory. Blockaded in 1948 and supplied by air for eleven months; walled in "
            "1961; and the place where the division ended in 1989. The geometry set in 1945 "
            "produced every one of those.", 25)):
        cmds += text_at(ln, 444.0, 238.0 + i * 14.0, 9.5, DIM)

    title(cmds, W, H, "Germany and Berlin, 1945", "four zones, and a city inside one of them")
    return {"header": header(W, H, "The four occupation zones of Germany with Berlin divided "
                                   "the same way deep inside the Soviet zone"),
            "root": canvas(cmds, INK)}


# ── 10. HIS-MH-00006  Battles — annotated-layout / 2D ──────────────────────────
# Five beaches over eighty kilometres, each with a different outcome on the day. The layout
# is the argument: the landings were one operation, but the day was five different days.
def normandy():
    W, H = 660, 520
    cmds = []
    cx, cy = 40.0, 250.0
    span = 580.0
    # coastline
    pts = [(cx + span * i / 40.0, cy + 26.0 * math.sin(i / 40.0 * 5.2) - 6.0 * (i / 40.0))
           for i in range(41)]
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"strokeWidth": 2.4}))
    for a, b in zip(pts, pts[1:]):
        cmds.append({"drawLine": {"x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1]}})
    cmds += rect(cx, cy + 60.0, cx + span, 420.0, PANEL)
    cmds += text_at("Normandy", cx + 12, 404.0, 10.0, DIM)
    cmds += text_at("the Channel", cx + 12, 150.0, 10.0, DIM)

    BEACHES = [("Utah", "US", 0.06, "23,000 landed, 197 casualties", GOOD),
               ("Omaha", "US", 0.26, "34,000 landed, ~2,400 casualties", HOT),
               ("Gold", "UK", 0.49, "25,000 landed, 413 casualties", ACCENT),
               ("Juno", "CAN", 0.67, "21,400 landed, 1,200 casualties", WARM),
               ("Sword", "UK", 0.84, "29,000 landed, 630 casualties", ACCENT)]
    for name, nation, f, note, col in BEACHES:
        x = cx + span * f
        ytop = 190.0
        cmds += line(x, ytop, x, cy + 18.0, col, 2.4)
        cmds += [paint({"color": col}, {"style": "fill"}),
                 {"drawCircle": {"cx": x, "cy": cy + 18.0, "radius": 7.0}}]
        cmds += text_at(name, x, ytop - 26.0, 13.0, col, pan_x=0.0)
        cmds += text_at(nation, x, ytop - 12.0, 9.0, DIM, pan_x=0.0)
        for i, ln in enumerate(wrap(note, 17)):
            cmds += text_at(ln, x, 300.0 + i * 13.0, 8.5, DIM, pan_x=0.0)

    cmds += text_at("6 June 1944 — 80 km of coast, five landings, one day",
                    cx, 448.0, 11.0, TEXT)
    cmds += rect(cx, 462.0, cx + span, 506.0, PANEL)
    for i, ln in enumerate(wrap(
            "Omaha differed from the rest in ground, not in plan: bluffs instead of dunes, a "
            "full-strength defending division where intelligence expected a weak one, and "
            "armour that foundered before it reached the sand. Same operation, same hour — "
            "ten times the cost.", 94)):
        cmds += text_at(ln, cx + 12, 480.0 + i * 13.0, 9.0, DIM)

    title(cmds, W, H, "Five beaches", "one operation, five different days")
    return {"header": header(W, H, "The five Normandy landing beaches along eighty kilometres "
                                   "of coast with the strength landed and casualties at each"),
            "root": canvas(cmds, INK)}


# ── 11. HIS-MH-00007  Campaigns — data-plot / 2D ───────────────────────────────
# After Minard, 1869. The band's width is the army, and it never recovers — the retreat is
# drawn below the advance so the two can be read against the same positions.
def campaign_1812():
    W, H = 680, 520
    cmds = []
    x0, x1 = 60.0, 620.0
    ADV = [(0.00, 422), (0.16, 400), (0.32, 175), (0.52, 145), (0.72, 127), (1.00, 100)]
    RET = [(1.00, 100), (0.82, 87), (0.66, 55), (0.50, 37), (0.34, 24), (0.16, 20), (0.00, 10)]
    ay, ry = 196.0, 300.0
    scale = 0.085

    def band(series, base, colour, label):
        for (f0, v0), (f1, v1) in zip(series, series[1:]):
            xa, xb = x0 + (x1 - x0) * f0, x0 + (x1 - x0) * f1
            cmds.append(paint({"color": colour}, {"style": "fill"}))
            cmds.append({"drawRect": {"left": min(xa, xb), "top": base - v0 * scale * 0.5,
                                      "right": max(xa, xb), "bottom": base + v0 * scale * 0.5}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))

    band(ADV, ay, ACCENT, "advance")
    band(RET, ry, HOT, "retreat")
    cmds += text_at("advance — 422,000 men cross the Niemen", x0, ay - 36.0, 11.0, ACCENT)
    cmds += text_at("retreat — 10,000 recross it", x0, ry + 36.0, 11.0, HOT)

    for f, name in ((0.0, "Niemen"), (0.32, "Vitebsk"), (0.52, "Smolensk"), (1.0, "Moscow")):
        x = x0 + (x1 - x0) * f
        cmds += line(x, 150.0, x, 340.0, RULE, 1.0)
        cmds += text_at(name, x, 140.0, 10.0, DIM, pan_x=0.0 if 0 < f < 1 else
                        (-1.0 if f == 0 else 1.0))

    # temperature on the retreat, the second variable Minard put underneath
    ty = 400.0
    TEMP = [(0.82, 0), (0.66, -9), (0.50, -21), (0.34, -11), (0.16, -26), (0.00, -30)]
    prev = None
    for f, t in TEMP:
        x = x0 + (x1 - x0) * f
        y = ty - t * 2.2
        if prev:
            cmds += line(prev[0], prev[1], x, y, WARM, 2.0)
        cmds += text_at("%d°" % t, x, y + 14.0, 9.0, WARM, pan_x=0.0)
        prev = (x, y)
    cmds += text_at("temperature on the retreat, °C", x0, ty - 44.0, 10.0, WARM)

    cmds += rect(48.0, 448.0, 632.0, 500.0, PANEL)
    for i, ln in enumerate(wrap(
            "The band loses more than half its width before Moscow is reached, and before any "
            "major battle: sickness, heat and desertion did that, not the enemy. The cold "
            "arrives afterwards and finishes an army already a tenth of its original size.", 94)):
        cmds += text_at(ln, 60.0, 466.0 + i * 13.0, 9.0, DIM)

    title(cmds, W, H, "1812, after Minard", "width is the army; it never recovers")
    return {"header": header(W, H, "Napoleon's 1812 campaign as a band whose width is army "
                                   "strength, with retreat temperatures beneath"),
            "root": canvas(cmds, INK)}


# ── 12. HIS-MH-00008  Territorial change — path-form / 2D ──────────────────────
# Four outlines of the same country, drawn as paths on common axes. Poland does not grow or
# shrink so much as travel westward, which no single map shows.
def shifting_borders():
    W, H = 640, 560
    cmds = []
    ox, oy, sc = 90.0, 150.0, 1.0
    OUTLINES = [
        ("1772", ACCENT, [(0.10, 0.22), (0.46, 0.08), (0.82, 0.20), (0.92, 0.52),
                          (0.70, 0.80), (0.34, 0.78), (0.12, 0.54)]),
        ("1815", WARM, [(0.26, 0.26), (0.54, 0.16), (0.74, 0.30), (0.78, 0.60),
                        (0.56, 0.76), (0.32, 0.70), (0.22, 0.48)]),
        ("1919", GOOD, [(0.18, 0.30), (0.46, 0.20), (0.68, 0.32), (0.72, 0.62),
                        (0.48, 0.76), (0.24, 0.68), (0.14, 0.48)]),
        ("1945", HOT, [(0.06, 0.32), (0.34, 0.22), (0.54, 0.34), (0.58, 0.64),
                       (0.36, 0.78), (0.12, 0.70), (0.02, 0.50)]),
    ]
    for i, (year, col, pts) in enumerate(OUTLINES):
        scr = [(ox + 300.0 * x, oy + 250.0 * y) for x, y in pts]
        pid = "b%d" % i
        cmds.append({"pathCreate": {"id": pid, "x": scr[0][0], "y": scr[0][1]}})
        for px, py in scr[1:]:
            cmds.append({"pathAppendLineTo": {"path": pid, "x": px, "y": py}})
        cmds.append({"pathAppendClose": {"path": pid}})
        cmds.append(paint({"color": col}, {"style": "stroke"}, {"strokeWidth": 2.6}))
        cmds.append({"drawPath": {"path": pid}})
        cx = sum(p[0] for p in scr) / len(scr)
        cy = sum(p[1] for p in scr) / len(scr)
        cmds += text_at(year, cx, cy + (i - 1.5) * 18.0, 12.0, col, pan_x=0.0)

    # the centroid of each outline, which is the thing actually moving
    cmds += line(ox, 440.0, ox + 300.0, 440.0, RULE, 1.2)
    for i, (year, col, pts) in enumerate(OUTLINES):
        cx = ox + 300.0 * (sum(p[0] for p in pts) / len(pts))
        cmds += [paint({"color": col}, {"style": "fill"}),
                 {"drawCircle": {"cx": cx, "cy": 440.0, "radius": 6.0}}]
        cmds += text_at(year, cx, 462.0, 9.0, col, pan_x=0.0)
    cmds += text_at("centre of the territory, west is left", ox, 418.0, 10.0, DIM)

    cmds += rect(48.0, 486.0, 592.0, 544.0, PANEL)
    for i, ln in enumerate(wrap(
            "Partitioned out of existence in 1795 and absent from the map for 123 years; "
            "restored in 1918; and in 1945 moved bodily some 200 km west, losing its eastern "
            "half and gaining German territory in the west. The area changed less than the "
            "position did.", 90)):
        cmds += text_at(ln, 60.0, 504.0 + i * 13.0, 9.0, DIM)

    title(cmds, W, H, "A country that moved", "Poland's borders, four dates")
    return {"header": header(W, H, "Four outlines of Poland's borders in 1772, 1815, 1919 and "
                                   "1945 with the territory's centre travelling westward"),
            "root": canvas(cmds, INK)}


# ── 13. AST-SS-00001  Solar system — expression-animation / 3D ─────────────────
# Orbit radii are compressed (cube root) or the inner four would be a dot; the PERIODS are
# real, so the relative speeds are honest even though the distances are not. Each orbit is a
# torus, which lies in the XZ plane already — exactly the orbit plane, no rotation needed.
def solar_system():
    W, H = 640, 600
    # Bodies are drawn far larger than scale — at true proportions Earth would be a third of
    # a pixel beside this Sun. The orbit PERIODS are real, which is the claim the document
    # actually makes, and the caption says so rather than letting the sizes imply otherwise.
    PLANETS = [("Mercury", 0.387, 0.241, 0.13, "#FFB0A79C"),
               ("Venus", 0.723, 0.615, 0.21, "#FFE8C07A"),
               ("Earth", 1.000, 1.000, 0.23, "#FF7FA8F5"),
               ("Mars", 1.524, 1.881, 0.17, "#FFE07A52"),
               ("Jupiter", 5.203, 11.86, 0.46, "#FFD8A878"),
               ("Saturn", 9.537, 29.45, 0.40, "#FFE3CE9B")]
    cmds = scene3d(W, H, dist=8.4, look_y=6.6, fov=0.80, far=60.0, lights=[
        {"type": "point", "color": "#FFFFF0D0", "pos": [0, 0, 0], "intensity": 1.5},
        {"type": "directional", "color": "#FF3A4E7A", "dir": [-0.4, -0.5, -0.6],
         "intensity": 0.30}])
    cmds.insert(2, var("t", "continuousSec()"))

    def radius_of(au):
        return 0.95 + 2.6 * (au ** (1.0 / 3.0))

    mid = 1
    cmds.append(ball(mid, 0.50, segments=28))
    sun = mid
    mid += 1
    for name, au, per, rad, col in PLANETS:
        r = radius_of(au)
        # minor radius well above a pixel at this distance: at 0.006 the rings
        # aliased into dashes and read as broken rather than thin
        cmds.append(ring(mid, r, 0.022, segments=72))
        cmds.append(ball(mid + 1, rad, segments=18))
        mid += 2

    cmds += place() + draw(sun, "#FFFFE9A8")
    mid = 2
    for i, (name, au, per, rad, col) in enumerate(PLANETS):
        r = radius_of(au)
        cmds += place() + draw(mid, "#FF4A6A58", "software-flat")
        # The phase is reduced modulo a turn before it reaches cos/sin. `continuousSec()`
        # under a pinned clock is an epoch-sized number, and `t * k` for some of these
        # multipliers lands far enough out that the trig stops returning a usable value —
        # Earth and Mars simply failed to draw, with nothing logged anywhere.
        ang = "((t * %0.4f) %% %0.5f)" % (TAU / (per * 6.0), TAU)
        cmds += place([T("%0.3f * cos(%s)" % (r, ang), 0.0, "%0.3f * sin(%s)" % (r, ang))])
        cmds += draw(mid + 1, col)
        mid += 2

    # Saturn's rings, a flat torus around the planet's own position
    sat_r = radius_of(9.537)
    sang = "((t * %0.4f) %% %0.5f)" % (TAU / (29.45 * 6.0), TAU)
    cmds.append(ring(mid, 0.66, 0.055, segments=48))
    cmds += place([T("%0.3f * cos(%s)" % (sat_r, sang), 0.0,
                     "%0.3f * sin(%s)" % (sat_r, sang)), RX(0.22)])
    cmds += draw(mid, "#FFC9B48A", "software-flat")

    cmds += rect(14.0, 448.0, 626.0, 590.0, "#CC0B1410")
    for i, (name, au, per, rad, col) in enumerate(PLANETS):
        y = 470.0 + i * 20.0
        cmds += [paint({"color": col}, {"style": "fill"}),
                 {"drawCircle": {"cx": 48.0, "cy": y - 4.0, "radius": 5.0}}]
        cmds += text_at(name, 62.0, y, 10.5, TEXT)
        cmds += text_at("%.3f AU" % au, 150.0, y, 9.5, DIM)
        cmds += text_at("%.3g yr" % per, 230.0, y, 9.5, DIM)
    for i, ln in enumerate(wrap(
            "Distances are compressed as the cube root and the bodies are drawn far larger "
            "than scale. The periods are real: Kepler's third law is why the outer ones "
            "crawl, since period grows as the 3/2 power of distance.", 46)):
        cmds += text_at(ln, 320.0, 470.0 + i * 14.0, 9.0, DIM)
    cmds += text_at("The Solar System", 20.0, 32.0, 19.0, TEXT)
    cmds += text_at("one Earth year every six seconds", 20.0, 52.0, 11.0, DIM)
    return {"header": header(W, H, "Six planets orbiting the Sun on torus orbit rings at "
                                   "their true relative periods, radii compressed to fit"),
            "root": canvas(cmds, INK)}


# ── 14. AST-PLAN-00002  Planets — particle-system / 2D ─────────────────────────
# Why Earth keeps nitrogen and loses hydrogen, and why the Moon kept nothing: a gas is held
# if its molecules are slow compared with escape velocity. The particles are the test.
def planet_atmospheres():
    W, H = 640, 560
    cmds = []
    bx, by, bw, bh = 56.0, 112.0, 280.0, 250.0
    cmds += rect(bx, by, bx + bw, by + bh, PANEL)
    # the planet's limb, as a band at the foot of the box rather than a disc over it: a
    # filled circle big enough to read as a horizon also covered the particles
    cmds += rect(bx, by + bh - 26.0, bx + bw, by + bh, ACCENT)
    cmds += text_at("a planet's upper atmosphere", bx, by - 10.0, 10.0, DIM)

    cmds.append({"createParticles": {
        "id": "gas", "count": 44,
        "variables": ["gx", "gy", "gv", "drift"],
        "initialValues": ["rand() * %0.1f" % bw, "rand() * %0.1f" % bh,
                          "rand()", "(rand() - 0.5) * 1.1"]}})
    cmds.append({"particlesLoop": {
        "system": "gas",
        # Fast molecules climb and wrap off the top; slow ones barely move. `gv` is the
        # molecule's speed, held for its lifetime, so the population keeps a spread.
        "equations": ["(gx + drift + %0.1f) %% %0.1f" % (bw, bw),
                      "(gy - 0.4 - gv * 3.2 + %0.1f) %% %0.1f" % (bh, bh),
                      "gv", "drift"],
        "commands": [
            paint({"color": HOT}, {"style": "fill"}),
            {"drawCircle": {"cx": "%0.1f + gx" % bx, "cy": "%0.1f + gy" % by,
                            "radius": "2.0 + 2.6 * gv"}},
        ]}})
    cmds += line(bx, by + 6.0, bx + bw, by + 6.0, WARM, 2.0)
    cmds += text_at("out of the atmosphere", bx + bw, by - 10.0, 10.0, WARM, pan_x=1.0)

    # which bodies hold which gases: escape speed against typical molecular speeds
    tx, ty = 376.0, 112.0
    BODIES = [("Jupiter", 59.5, "holds everything, hydrogen included", GOOD),
              ("Earth", 11.2, "holds N₂, O₂, CO₂ — loses H₂ and He", ACCENT),
              ("Mars", 5.0, "holds a thin CO₂ atmosphere", WARM),
              ("Moon", 2.4, "holds nothing at all", HOT),
              ("Mercury", 4.3, "nothing, and far too hot besides", HOT)]
    cmds += text_at("escape velocity, km/s", tx, ty - 10.0, 9.5, DIM)
    for i, (name, v, note, col) in enumerate(BODIES):
        y = ty + 18.0 + i * 46.0
        w = 10.0 + 190.0 * (v / 59.5) ** 0.5
        cmds += rect(tx, y, tx + w, y + 18.0, col)
        cmds += text_at(name, tx + 6, y + 13.0, 10.5, INK)
        cmds += text_at("%.1f" % v, tx + w + 8, y + 13.0, 9.5, TEXT)
        for j, ln in enumerate(wrap(note, 34)):
            cmds += text_at(ln, tx, y + 32.0 + j * 11.0, 8.5, DIM)

    cmds += rect(48.0, 400.0, 336.0, 470.0, PANEL)
    cmds += text_at("The rule of thumb", 60.0, 424.0, 11.5, TEXT)
    for i, ln in enumerate(wrap(
            "A body keeps a gas if its escape speed is more than about six times the gas's "
            "typical molecular speed. Lighter molecules move faster at the same temperature, "
            "so hydrogen is always the first to go.", 44)):
        cmds += text_at(ln, 60.0, 442.0 + i * 12.0, 9.0, DIM)

    cmds += rect(48.0, 486.0, 592.0, 544.0, PANEL)
    for i, ln in enumerate(wrap(
            "This is why Earth has nitrogen but no free hydrogen, why Titan — colder than "
            "Mars and smaller — holds a thicker atmosphere than Mars does, and why "
            "temperature matters as much as mass.", 92)):
        cmds += text_at(ln, 60.0, 504.0 + i * 13.0, 9.0, DIM)

    title(cmds, W, H, "Why some worlds keep an atmosphere",
          "escape speed against molecular speed")
    return {"header": header(W, H, "Gas molecules escaping a planet beside escape velocities "
                                   "for five bodies and what each can hold"),
            "root": canvas(cmds, INK)}


# ── 15. AST-MOON-00003  Moons — interactive / 3D ───────────────────────────────
# The Laplace resonance: Io, Europa and Ganymede lock at 4:2:1, so the three can never line
# up at once. Drag to turn the system; the periods are the real ones.
def galilean_moons():
    W, H = 620, 600
    MOONS = [("Io", 1.00, 1.769, 0.085, "#FFE8D06A"),
             ("Europa", 1.59, 3.551, 0.072, "#FFD8D2C4"),
             ("Ganymede", 2.54, 7.155, 0.120, "#FFA89A86"),
             ("Callisto", 4.47, 16.69, 0.110, "#FF8A7F72")]
    cmds = scene3d(W, H, dist=7.0, look_y=2.4, fov=0.74, far=60.0)
    cmds.insert(2, var("t", "continuousSec()"))
    cmds[2:2] = touch_orbit(0.55, 0.34)

    spin, tilt = spin_expr(0.55), tilt_expr(0.34)

    def turn(extra=()):
        return place([RX(tilt), RY(spin)] + list(extra))

    mid = 1
    cmds.append(ball(mid, 0.62, segments=30))               # Jupiter
    jup = mid
    mid += 1
    for name, r, per, rad, col in MOONS:
        cmds.append(ring(mid, r, 0.016, segments=64))
        cmds.append(ball(mid + 1, rad, segments=16))
        mid += 2

    cmds += turn() + draw(jup, "#FFD8A878")
    mid = 2
    for i, (name, r, per, rad, col) in enumerate(MOONS):
        cmds += turn() + draw(mid, "#FF6B5A50", "software-flat")
        # same phase reduction as the solar system, for the same reason
        ang = "((t * %0.4f) %% %0.5f)" % (TAU / (per * 1.6), TAU)
        cmds += turn([T("%0.3f * cos(%s)" % (r, ang), 0.0, "%0.3f * sin(%s)" % (r, ang))])
        cmds += draw(mid + 1, col)
        mid += 2

    for i, (name, r, per, rad, col) in enumerate(MOONS):
        y = 452.0 + i * 22.0
        cmds += [paint({"color": col}, {"style": "fill"}),
                 {"drawCircle": {"cx": 44.0, "cy": y - 4.0, "radius": 5.0}}]
        cmds += text_at(name, 58.0, y, 11.0, TEXT)
        cmds += text_at("%.3f days" % per, 160.0, y, 9.5, DIM)
        if i < 3:
            cmds += text_at(["1", "2", "4"][i] + "×", 250.0, y, 10.0, ACCENT)
    cmds += text_at("the inner three are locked at 4 : 2 : 1 — a Laplace resonance",
                    290.0, 452.0, 9.5, ACCENT)
    for i, ln in enumerate(wrap(
            "Because of it the three can never be in conjunction together. The repeated tugs "
            "keep their orbits slightly elliptical, and the tidal flexing that follows is why "
            "Io is the most volcanic body in the Solar System and why Europa has a liquid "
            "ocean under its ice.", 64)):
        cmds += text_at(ln, 290.0, 470.0 + i * 13.0, 9.0, DIM)

    cmds += text_at("Jupiter's Galilean moons", 20.0, 32.0, 19.0, TEXT)
    cmds += text_at("drag to turn — periods are the real ones", 20.0, 52.0, 11.0, DIM)
    return {"header": header(W, H, "Jupiter and its four Galilean moons on their real "
                                   "relative periods, turnable by dragging"),
            "root": canvas(cmds, INK)}


# ── 16. AST-ASTE-00004  Asteroids — raster-and-text / 2D ───────────────────────
# The Kirkwood gaps: the belt is not uniform, and the holes are exactly at the orbital
# periods that beat against Jupiter's. An absence is the evidence.
def asteroids():
    W, H = 660, 540
    cmds = []
    gx, gy, gw, gh = 60.0, 150.0, 540.0, 210.0
    cmds += rect(gx, gy, gx + gw, gy + gh, PANEL)
    lo, hi = 2.0, 3.6
    GAPS = [(2.065, "4:1"), (2.502, "3:1"), (2.825, "5:2"), (2.958, "7:3"), (3.279, "2:1")]

    def X(a):
        return gx + gw * (a - lo) / (hi - lo)

    # population, as a histogram with the resonant gaps cut out of it
    for i in range(108):
        a = lo + (hi - lo) * (i + 0.5) / 108.0
        base = math.exp(-((a - 2.75) ** 2) / 0.42) * 0.92 + 0.12
        for ga, _ in GAPS:
            base *= 1.0 - 0.93 * math.exp(-((a - ga) ** 2) / 0.00085)
        h = gh * max(0.0, min(1.0, base))
        cmds += rect(X(a) - 2.2, gy + gh - h, X(a) + 2.2, gy + gh, ACCENT)

    for ga, ratio in GAPS:
        cmds += line(X(ga), gy - 16.0, X(ga), gy + gh, HOT, 1.4)
        cmds += text_at(ratio, X(ga), gy - 22.0, 10.0, HOT, pan_x=0.0)
    cmds += text_at("resonance with Jupiter", X(2.065), gy - 40.0, 10.0, HOT)

    for k in range(9):
        a = lo + (hi - lo) * k / 8.0
        cmds += line(X(a), gy + gh, X(a), gy + gh + 6.0, RULE, 1.0)
        cmds += text_at("%.1f" % a, X(a), gy + gh + 18.0, 9.0, DIM, pan_x=0.0)
    cmds += text_at("semi-major axis, AU", gx + gw * 0.5, gy + gh + 36.0, 10.0, DIM, pan_x=0.0)
    cmds += text_at("number of asteroids", gx, gy - 6.0, 10.0, DIM)

    # the belt in context — it is mostly empty, which the histogram cannot show
    cmds += rect(60.0, 406.0, 350.0, 500.0, PANEL)
    cmds += text_at("How empty it is", 72.0, 430.0, 11.5, TEXT)
    for i, ln in enumerate(wrap(
            "Over a million asteroids larger than a kilometre, and their total mass is about "
            "4% of the Moon's. The typical separation is a few million kilometres: every "
            "spacecraft sent through has crossed without incident.", 46)):
        cmds += text_at(ln, 72.0, 450.0 + i * 12.0, 9.0, DIM)

    cmds += rect(366.0, 406.0, 600.0, 500.0, PANEL)
    cmds += text_at("Why the gaps are there", 378.0, 430.0, 11.5, TEXT)
    for i, ln in enumerate(wrap(
            "An asteroid at 2.5 AU orbits exactly three times for each Jupiter orbit, so it "
            "gets the same tug at the same point every time. The nudges add instead of "
            "cancelling, and the orbit is pulled out of the belt.", 38)):
        cmds += text_at(ln, 378.0, 450.0 + i * 12.0, 9.0, DIM)

    title(cmds, W, H, "The Kirkwood gaps", "the belt is emptiest where Jupiter keeps time")
    return {"header": header(W, H, "The asteroid belt's population against distance with the "
                                   "Kirkwood gaps at resonances with Jupiter"),
            "root": canvas(cmds, INK)}


BUILD = [("PHY-FM-00039", pressure), ("PHY-FM-00040", aerodynamics),
         ("MTH-TRIG-00015", trig_identities), ("CSC-CA-00013", memory_hierarchy),
         ("BIO-ANAT-00034", digestion), ("CHM-CR-00013", kinetics),
         ("EAR-METE-00013", storms), ("ENG-CE-00013", buildings),
         ("HIS-MH-00005", divided_germany), ("HIS-MH-00006", normandy),
         ("HIS-MH-00007", campaign_1812), ("HIS-MH-00008", shifting_borders),
         ("AST-SS-00001", solar_system), ("AST-PLAN-00002", planet_atmospheres),
         ("AST-MOON-00003", galilean_moons), ("AST-ASTE-00004", asteroids)]

if __name__ == "__main__":
    for doc_id, fn in BUILD:
        name = use(doc_id)
        d = fn()
        (OUT / ("%s.json" % doc_id)).write_text(json.dumps(d, indent=1) + "\n")
        print("  %-16s %-9s %s" % (doc_id, name, d["header"]["contentDescription"][:44]))
    print("  %d documents" % len(BUILD))
