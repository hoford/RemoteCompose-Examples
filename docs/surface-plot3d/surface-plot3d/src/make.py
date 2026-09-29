#!/usr/bin/env python3
"""Generate `surface_plot3d.json` and its three textures.

    python3 samples/json/surface_plot3d/make.py
    python3 tools/rcbuild.py samples/json/surface_plot3d/

A 3D surface plot: the classic MATLAB `peaks` height field, coloured by height with a jet
colormap, standing in a gridded axes box with the contour projected on the floor. Drag to
orbit; flick and it coasts.

**Why this one is generated rather than hand-written.** Most samples here are JSON you can
open and edit. This one cannot be: `peaks` is

    3(1-x)^2 e^(-x^2-(y+1)^2) - 10(x/5 - x^3 - y^5) e^(-x^2-y^2) - (1/3) e^(-(x+1)^2-y^2)

which is far past the 32-token cap on a `meshExpression3D` height expression, so the surface
has to ship as explicit geometry — 3,136 vertices with positions, normals and UVs, plus
18,150 indices. That is data, not something to read. The readable artifact is this script.

That is a pattern worth knowing rather than a wart: when a document needs more geometry than
an expression can describe, generate the JSON. The document stays declarative and portable;
the generator stays readable and diffable.

Pure standard library, including the PNG writer, so this runs on a clean Python 3.8+ with
nothing installed.
"""

from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools"))

from rctex import jet, make_jet_strip, make_wall_grid, write_png  # noqa: E402

# Geometry, matching the original: a 56x56 grid over [-half, half] with the surface
# occupying [0, BOX_H] vertically.
NX = NY = 56
HALF = 1.1
BOX_H = 1.35
W = H = 1000


# ── the surface ───────────────────────────────────────────────────────────────────────

def peaks(x: float, y: float) -> float:
    """MATLAB's `peaks`, x and y over [-3, 3]."""
    return (3.0 * (1 - x) ** 2 * math.exp(-(x * x) - (y + 1) ** 2)
            - 10.0 * (x / 5.0 - x ** 3 - y ** 5) * math.exp(-(x * x) - (y * y))
            - (1.0 / 3.0) * math.exp(-((x + 1) ** 2) - (y * y)))


def z_raw(u: float, v: float) -> float:
    return peaks(-3.0 + 6.0 * u, -3.0 + 6.0 * v)


# Normalise heights to [0,1] from the field's own extent, sampled on a finer grid than the
# mesh so the range does not depend on the mesh resolution.
_LO, _HI = None, None


def z_norm(u: float, v: float) -> float:
    global _LO, _HI
    if _LO is None:
        n = 80
        vals = [z_raw(i / n, j / n) for i in range(n + 1) for j in range(n + 1)]
        _LO, _HI = min(vals), max(vals)
    return max(0.0, min(1.0, (z_raw(u, v) - _LO) / (_HI - _LO)))


def build_mesh():
    """Vertices, finite-difference normals, UVs and indices for the surface.

    `uv.v` is the vertex's normalised height, so sampling a 1-D jet strip with it colours
    the surface by height with no per-vertex colour data at all — the texture *is* the
    colour map. `uv.u` is the grid column, which only matters for the strip's width.
    """
    zg = [[z_norm(i / (NX - 1), j / (NY - 1)) for j in range(NY)] for i in range(NX)]
    verts, normals, uv = [], [], []
    for i in range(NX):
        for j in range(NY):
            verts += [-HALF + 2 * HALF * i / (NX - 1), BOX_H * zg[i][j],
                      -HALF + 2 * HALF * j / (NY - 1)]
            uv += [i / (NX - 1), zg[i][j]]

    cell = 2.0 * HALF / (NX - 1)
    for i in range(NX):
        for j in range(NY):
            zl = zg[i - 1][j] * BOX_H if i > 0 else zg[i][j] * BOX_H
            zr = zg[i + 1][j] * BOX_H if i < NX - 1 else zg[i][j] * BOX_H
            zd = zg[i][j - 1] * BOX_H if j > 0 else zg[i][j] * BOX_H
            zu = zg[i][j + 1] * BOX_H if j < NY - 1 else zg[i][j] * BOX_H
            nx, ny, nz = (zr - zl), 2.0 * cell, (zu - zd)
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            normals += [-nx / ln, ny / ln, -nz / ln]

    indices = []
    for i in range(NX - 1):
        for j in range(NY - 1):
            a, b = i * NY + j, (i + 1) * NY + j
            c, d = (i + 1) * NY + (j + 1), i * NY + (j + 1)
            indices += [a, c, b, a, d, c]
    return verts, normals, uv, indices


# ── textures ──────────────────────────────────────────────────────────────────────────
# write_png, jet, make_jet_strip and make_wall_grid are shared with the other 3D samples;
# make_contour stays here because it samples this document's own height field.

def make_contour(path: str) -> None:
    """The same field seen from above, quantised into bands with dark lines between."""
    s, bands, px = 256, 14, bytearray()
    for py in range(s):
        for qx in range(s):
            z = z_norm(qx / (s - 1), py / (s - 1))
            band = min(bands - 1, int(z * bands))
            frac = z * bands - band
            if frac < 0.06 or frac > 0.94:
                px += bytes([0x3A, 0x3A, 0x3A, 255])
            else:
                r, g, b = jet((band + 0.5) / bands)
                px += bytes([r, g, b, 255])
    write_png(path, s, s, bytes(px))


def make_wall_grid(path: str) -> None:
    """Light panel with a 6x6 grid.

    The lines are antialiased by coverage rather than drawn hard. The original uses an
    Android Canvas with ANTI_ALIAS_FLAG and a 2px stroke; hard-edged lines here left a
    visible residue along every gridline when the two renders were differenced, which is
    the sort of difference that looks like a bug in the player and is not.
    """
    s_px, div, half_w = 256, 6, 1.0     # half_w 1.0 => a 2px stroke
    lines = [s_px * k / div for k in range(div + 1)]
    bg = (0xF3, 0xF4, 0xF7)
    fg = (0xC4, 0xC7, 0xCE)

    def coverage(q: float) -> float:
        """How much of pixel q is covered by the nearest gridline, in [0,1]."""
        best = 0.0
        for t in lines:
            c = max(0.0, min(1.0, half_w + 0.5 - abs(q + 0.5 - t)))
            best = max(best, c)
        return best

    cov_x = [coverage(q) for q in range(s_px)]
    px = bytearray()
    for py in range(s_px):
        cy = coverage(py)
        for qx in range(s_px):
            a = max(cy, cov_x[qx])
            px += bytes([int(bg[i] + (fg[i] - bg[i]) * a) for i in range(3)] + [255])
    write_png(path, s_px, s_px, bytes(px))


# ── the document ──────────────────────────────────────────────────────────────────────

# Drag to orbit. touchExpression accumulates across drags and coasts to a stop on release;
# a plain expression over touchX() would track the finger's absolute position and snap back
# the moment it lifted. The value is in *pixels of travel*, so the tilt limit is expressed
# as a pixel range derived from the angle limit — the op can only clamp its own value.
SPIN_PER_PX, TILT_PER_PX = 0.012, 0.006
TILT_LIMIT = 1.0
SPIN = f"spinPx * {SPIN_PER_PX}"
TILT = f"tiltPx * {TILT_PER_PX}"


def orbit():
    """Reset, tilt, spin — emitted before every object so the scene turns as one body.

    The camera never moves. Rotating the camera instead would swing the lights across the
    data as it turned; rotating the model keeps the lighting fixed relative to the viewer.
    Tilt before spin, or the spin axis tilts with the model and the plot corkscrews.
    """
    return [
        {"matrix3D": {"op": "identity"}},
        {"matrix3D": {"op": "rotate", "angle": TILT, "axis": [1, 0, 0]}},
        {"matrix3D": {"op": "rotate", "angle": SPIN, "axis": [0, 1, 0]}},
    ]


def build_doc():
    verts, normals, uv, indices = build_mesh()
    hp = math.pi / 2
    cmds = [
        {"paint": {"ops": [{"color": "#FFFFFFFF"}, {"style": "fill"}]}},
        {"drawRect": {"left": 0, "top": 0,
                      "right": "componentWidth()", "bottom": "componentHeight()"}},

        {"touchExpression": {"name": "spinPx", "defaultValue": 0.0,
                             "min": -100000.0, "max": 100000.0,
                             "stopMode": "gently", "expression": "touchX()"}},
        {"touchExpression": {"name": "tiltPx", "defaultValue": 0.0,
                             "min": -TILT_LIMIT / TILT_PER_PX,
                             "max": TILT_LIMIT / TILT_PER_PX,
                             "stopMode": "gently", "expression": "touchY()"}},

        {"clearDepth3D": {}},
        {"camera3D": {"projection": "perspective", "fovY": math.radians(33.0),
                      "aspect": 1.0, "near": 0.1, "far": 100.0,
                      "eye": [2.8, 2.2, 3.0], "center": [0.0, 0.45, 0.0], "up": [0, 1, 0]}},
        # Soft, fairly frontal lighting so the colormap reads clearly.
        {"lights3D": {"lights": [
            {"type": "directional", "color": "#FFFFFFFF", "dir": [-0.3, -0.55, -0.75],
             "intensity": 0.75},
            {"type": "directional", "color": "#FFE0E6F0", "dir": [0.5, -0.2, 0.5],
             "intensity": 0.5}]}},

        # A unit plane, instanced by the matrix for the floor and all four walls.
        # "uv": "uv" is required — a primitive generates no texture coordinates by default,
        # and an untextured plane looks like a working document with the wrong colour rather
        # than a missing feature. The floor and walls are entirely texture.
        {"meshPrimitive3D": {"id": 1, "primitive": "plane", "segments": 2,
                             "width": 1.0, "height": 1.0, "center": [0, 0, 0],
                             "uv": "uv"}},
        {"defineMesh3D": {"id": 2, "verts": verts, "normals": normals,
                          "uv": uv, "indices": indices}},
    ]

    # Floor: the contour map, laid flat. The plane faces +Z, so -90 about X turns it face up.
    cmds += [{"texture3D": {"bitmap": "contour"}}]
    cmds += orbit() + [
        {"matrix3D": {"op": "rotate", "angle": -hp, "axis": [1, 0, 0]}},
        {"matrix3D": {"op": "scale", "x": 2 * HALF, "y": 2 * HALF, "z": 1.0}},
        {"paint": {"ops": [{"color": "#FFFFFFFF"}]}},
        {"drawMesh3D": {"mesh": 1, "mode": "software-flat"}},
    ]

    # All four walls, each facing inward. Backface culling keeps the two behind the data and
    # drops the two in front, so the grid stays behind the surface at any spin — no need to
    # choose which walls to draw as the plot turns.
    cmds += [{"texture3D": {"bitmap": "wall"}}]
    for tx, tz, ang in ((0.0, -HALF, 0.0), (0.0, HALF, math.pi),
                        (-HALF, 0.0, hp), (HALF, 0.0, -hp)):
        cmds += orbit() + [
            {"matrix3D": {"op": "translate", "x": tx, "y": BOX_H * 0.5, "z": tz}},
            {"matrix3D": {"op": "rotate", "angle": ang, "axis": [0, 1, 0]}},
            {"matrix3D": {"op": "scale", "x": 2 * HALF, "y": BOX_H, "z": 1.0}},
            {"drawMesh3D": {"mesh": 1, "mode": "software-flat"}},
        ]

    # The surface, textured by height through the jet strip.
    cmds += [{"texture3D": {"bitmap": "jet"}}]
    cmds += orbit() + [
        # No material3D: the original sets none, so the surface is purely Lambert plus the
        # jet texture. Adding a specular term here made the whole surface visibly brighter.
        {"drawMesh3D": {"mesh": 2, "mode": "software-smooth"}},
        {"texture3D": {"bitmap": 0}},
    ]

    # Title and axis ticks. 2D, drawn over the scene in document order.
    cmds += [
        {"paint": {"ops": [{"color": "#FF2A2A2A"}, {"textSize": 38}]}},
        {"drawTextAnchored": {"text": "Surface Plot", "x": 500, "y": 70,
                              "panX": 0.0, "panY": 0.0, "flags": 0}},
        {"paint": {"ops": [{"color": "#FF555555"}, {"textSize": 24}]}},
    ]
    for label, y in (("2.0", 150), ("1.0", 360), ("0.0", 560)):
        cmds.append({"drawTextAnchored": {"text": label, "x": 70, "y": y,
                                          "panX": 1.0, "panY": 0.0, "flags": 0}})

    return {
        "header": {"apiLevel": 7, "width": W, "height": H, "profiles": 513,
                   "contentDescription": "3D surface plot — drag to orbit"},
        "resources": {"bitmaps": {
            "jet": "jet.png", "contour": "contour.png", "wall": "wall.png"}},
        "root": [{"box": {"modifiers": ["fillMaxSize"], "children": [
            {"type": "canvas", "modifiers": ["fillMaxSize"], "commands": cmds}]}}],
    }


def main() -> None:
    make_jet_strip(os.path.join(HERE, "jet.png"))
    make_contour(os.path.join(HERE, "contour.png"))
    make_wall_grid(os.path.join(HERE, "wall.png"))
    doc = build_doc()
    out = os.path.join(HERE, "surface_plot3d.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    n = len(doc["root"][0]["box"]["children"][0]["commands"])
    print(f"  wrote surface_plot3d.json  ({os.path.getsize(out) // 1024} KB, {n} commands)")
    print("  wrote jet.png contour.png wall.png")
    print("  now: python3 tools/rcbuild.py samples/json/surface_plot3d/")


if __name__ == "__main__":
    main()
