#!/usr/bin/env python3
"""Build set 4 of the visualization programme: 16 documents.

    python3 work/set-04/make_set04.py

Work order from `python3 tools/visplan.py set 4`. No curation swap: only two slots are 3D
and both suit their topics - a protein is a volume, and an engine cylinder is a volume.

The helper block below is carried from set 3 unchanged, including the six palettes and the
axis_rod/draw_axes pair. Everything sets 1 to 3 paid for is baked into it:

  * text components key on `value`; `resources` at document top level; paint `ops` form
  * panX -1 left, 0 centres
  * mesh triangles wind [a, a+N+1, a+N] or the mesh is invisible with no error (F-008)
  * containing wireframes drawn LAST - they write depth across whole faces (F-009)
  * a texture needs a FILLED mesh (F-010)
  * particle equations must not accumulate, and position or size has to encode something
  * palettes are hashed from the document id, never random: generators must be deterministic
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


# ── 1. PHY-AP-00012  Energy levels — static-diagram / explain / 2D ────────────
# Hydrogen levels sit at -13.6/n^2, so they crowd towards zero. Drawing them to scale is
# the explanation: the gaps shrink, which is why the Lyman series is ultraviolet and the
# Balmer series is visible.
def energy_levels():
    W, H = 640, 430
    left, right = 210.0, 430.0
    top, bottom = 92.0, 320.0

    def ypos(n):
        e = -13.6 / (n * n)
        return bottom - (e + 13.6) / 13.6 * (bottom - top)

    cmds = []
    # The levels themselves crowd towards zero - that IS the physics - so the labels cannot
    # sit beside them without colliding. Space the labels evenly instead and lead a line
    # from each one to the level it names, on both sides: n on the left, energy on the right.
    def label_y(n):
        return bottom - (n - 1) / 5.0 * (bottom - top - 24.0)

    for n in range(1, 7):
        y = ypos(n)
        ly = label_y(n)
        cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 2.0}))
        cmds.append({"drawLine": {"x1": left, "y1": y, "x2": right, "y2": y}})

        for side in (-1, 1):
            x_lab = (left - 86.0) if side < 0 else (right + 86.0)
            x_end = (left - 6.0) if side < 0 else (right + 6.0)
            cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
            # a dog-leg: out from the level, across to the label's row, then in to the text
            cmds.append({"drawLine": {"x1": x_end, "y1": y,
                                      "x2": x_end + side * 30.0, "y2": y}})
            cmds.append({"drawLine": {"x1": x_end + side * 30.0, "y1": y,
                                      "x2": x_end + side * 46.0, "y2": ly}})
            cmds.append({"drawLine": {"x1": x_end + side * 46.0, "y1": ly,
                                      "x2": x_lab + side * 6.0, "y2": ly}})
        cmds += text_at("n = %d" % n, left - 92.0, label_y(n) + 4.0, 13.0, TEXT, pan_x=1.0)
        cmds += text_at("%.2f eV" % (-13.6 / (n * n)), right + 92.0, label_y(n) + 4.0,
                        12.0, DIM)

    series = [(2, 1, HOT, "Lyman", "ultraviolet"),
              (3, 2, ACCENT, "Balmer", "visible"),
              (4, 3, GOOD, "Paschen", "infrared")]
    for hi, lo, colour, name, band in series:
        x = left + 36.0 + (lo - 1) * 68.0
        y0, y1 = ypos(hi), ypos(lo)
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.4}))
        cmds.append({"drawLine": {"x1": x, "y1": y0, "x2": x, "y2": y1}})
        for sgn in (-1, 1):
            cmds.append({"drawLine": {"x1": x, "y1": y1,
                                      "x2": x + sgn * 5.0, "y2": y1 - 9.0}})
        cmds += text_at(name, x + 8.0, (y0 + y1) / 2, 10.5, colour)
        cmds += text_at(band, x + 8.0, (y0 + y1) / 2 + 14.0, 9.0, DIM)

    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": left, "y1": top, "x2": right, "y2": top}})
    cmds += text_at("0 eV - the electron is free", left, top - 10.0, 9.5, DIM)
    cmds += text_at("levels crowd towards zero, so the jumps get smaller",
                    24.0, 362.0, 11.0, TEXT)
    cmds += text_at("a drop to n=1 releases the most energy, which is why Lyman is "
                    "ultraviolet", 24.0, 380.0, 10.0, DIM)
    cmds += text_at("labels are evenly spaced and led to their level; the levels are not",
                    24.0, 398.0, 10.0, "#FF5E6E95")
    cmds += text_at("drawn to scale: -13.6/n^2 eV", 24.0, 416.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "Hydrogen energy levels drawn to scale, with evenly "
                                   "spaced labels led to each level on both sides"),
            "root": canvas(title(cmds, W, H, "Energy levels", "hydrogen, to scale"))}


use("PHY-AP-00012")
docs["PHY-AP-00012"] = energy_levels()


# ── 2. PHY-AP-00013  Atomic spectra — annotated-layout / explore / 2D ─────────
# One card per element, each holding its own spectrum strip. The layout makes them
# comparable; the strips carry the data.
SPECTRA = {
    "Hydrogen": [(410, "#FF8A2BE2"), (434, "#FF4169E1"), (486, "#FF00CED1"),
                 (656, "#FFDC143C")],
    "Helium": [(447, "#FF4169E1"), (502, "#FF00FA9A"), (588, "#FFFFD700"),
               (668, "#FFDC143C")],
    "Sodium": [(589, "#FFFFA500"), (590, "#FFFFA500")],
    "Mercury": [(405, "#FF8A2BE2"), (436, "#FF4169E1"), (546, "#FF32CD32"),
                (578, "#FFFFD700")],
}


def spectra():
    W, H = 480, 460

    def strip(lines):
        c = [paint({"color": "#FF07080C"}, {"style": "fill"}),
             {"drawRect": {"left": 0, "top": 0, "right": 380, "bottom": 46}}]
        for nm, colour in lines:
            x = (nm - 390) / (700 - 390) * 380
            c.append(paint({"color": colour}, {"style": "fill"}))
            c.append({"drawRect": {"left": round(x - 1.6, 1), "top": 0,
                                   "right": round(x + 1.6, 1), "bottom": 46}})
        for nm in (400, 500, 600, 700):
            x = (nm - 390) / (700 - 390) * 380
            c.append(paint({"color": "#FF55658A"}, {"style": "fill"},
                           {"textSize": 8.0}))
            c.append({"drawTextAnchored": {"text": str(nm), "x": round(x, 1), "y": 42.0,
                                           "panX": 0.0, "panY": 0.0, "flags": 0}})
        return {"type": "canvas", "modifiers": [{"width": 380}, {"height": 46}],
                "commands": c}

    cards = []
    for name, lines in SPECTRA.items():
        cards.append({"type": "column",
                      "modifiers": [{"width": 410}, {"padding": 10},
                                    {"background": PANEL}],
                      "children": [
                          {"type": "row", "modifiers": [], "children": [
                              {"type": "text", "value": name, "modifiers": [],
                               "fontSize": 13.0, "color": TEXT},
                              {"type": "spacer", "modifiers": [{"width": 12}]},
                              {"type": "text",
                               "value": "%d lines" % len(lines), "modifiers": [],
                               "fontSize": 10.0, "color": DIM}]},
                          {"type": "spacer", "modifiers": [{"height": 6}]},
                          strip(lines)]})
        cards.append({"type": "spacer", "modifiers": [{"height": 8}]})

    return {
        "header": header(W, H, "Emission spectra for four elements as cards, each with its "
                               "own strip over the visible range"),
        "root": {"type": "column",
                 "modifiers": ["fillMaxSize", {"background": INK}, {"padding": 16}],
                 "children": [
                     {"type": "text", "value": "Atomic spectra", "modifiers": [],
                      "fontSize": 20.0, "color": TEXT},
                     {"type": "spacer", "modifiers": [{"height": 4}]},
                     {"type": "text",
                      "value": "every element emits its own set of wavelengths, in nm",
                      "modifiers": [], "fontSize": 11.0, "color": DIM},
                     {"type": "spacer", "modifiers": [{"height": 12}]},
                 ] + cards + [
                     {"type": "text",
                      "value": "sodium's two lines are 1 nm apart and look like one",
                      "modifiers": [], "fontSize": 9.5, "color": "#FF5E6E95"}]},
    }


use("PHY-AP-00013")
docs["PHY-AP-00013"] = spectra()


# ── 3. PHY-AP-00014  Ionization — data-plot / compare / 2D ───────────────────
# Successive ionizations of magnesium. Set 3 plotted FIRST ionization across elements; this
# is the other cut - one element, stripped one electron at a time - and the jumps are where
# a shell runs out.
MG_IONIZATION = [738, 1451, 7733, 10543, 13630, 18020, 21711, 25661]


def ionization_series():
    W, H = 560, 380
    left, right, top, bottom = 80.0, 520.0, 96.0, 300.0
    cmds = []
    for e in (0, 5000, 10000, 15000, 20000, 25000):
        y = bottom - e / 26000.0 * (bottom - top)
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": left, "y1": y, "x2": right, "y2": y}})
        cmds += text_at("%dk" % (e // 1000) if e else "0", left - 8.0, y + 4.0,
                        9.0, DIM, pan_x=1.0)

    n = len(MG_IONIZATION)
    cmds.append(var("bw", "%.3f" % ((right - left) / n * 0.6)))
    cmds.append({"loop": {"index": "i", "from": 0.0, "until": float(n), "step": 1.0,
                          "commands": [
        var("e", "arrayGet(@mg, @i)"),
        var("cx", "%.1f + (@i + 0.5) * %.3f" % (left, (right - left) / n)),
        var("h", "@e / 26000.0 * %.1f" % (bottom - top)),
        paint({"color": ACCENT}, {"style": "fill"},
              {"alpha": "clamp(0.45, 1.0, @e / 9000)"}),
        {"drawRoundRect": {"left": "@cx - @bw / 2", "top": "%.1f - @h" % bottom,
                           "right": "@cx + @bw / 2", "bottom": bottom,
                           "rx": 3.0, "ry": 3.0}},
    ]}})

    for i, e in enumerate(MG_IONIZATION):
        cx = left + (i + 0.5) * (right - left) / n
        cmds += text_at(str(i + 1), cx, bottom + 16.0, 10.0, DIM, pan_x=0.0)
        cmds += text_at("%d" % e, cx, bottom - e / 26000.0 * (bottom - top) - 8.0,
                        9.0, TEXT, pan_x=0.0)
    # the two jumps that give the shell structure away
    for after, label, colour in ((2, "2 valence electrons gone", WARM),
                                 (10, "", None)):
        if colour is None:
            continue
        x = left + after * (right - left) / n
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 1.8}))
        cmds.append({"drawLine": {"x1": x, "y1": top - 6.0, "x2": x, "y2": bottom}})
        cmds += text_at(label, x + 8.0, top + 6.0, 10.5, colour)
    cmds += text_at("electron removed", left, bottom + 36.0, 10.0, DIM)
    cmds += text_at("energy to remove the nth electron from magnesium, kJ/mol",
                    24.0, 342.0, 11.0, TEXT)
    cmds += text_at("the jump after the second says magnesium has two outer electrons",
                    24.0, 360.0, 10.0, DIM)
    return {"header": header(W, H, "Successive ionization energies of magnesium, where the "
                                   "jump after the second reveals two valence electrons"),
            "resources": {"floatArrays": [{"mg": [float(v) for v in MG_IONIZATION]}]},
            "root": canvas(title(cmds, W, H, "Stripping an atom",
                                 "magnesium, one electron at a time"))}


use("PHY-AP-00014")
docs["PHY-AP-00014"] = ionization_series()


# ── 4. BIO-CB-00013  Cellular transport — path-form / demonstrate / 2D ───────
# Vesicle trafficking is a set of routes, so the routes are real paths and the vesicles ride
# along them at positions sampled from the same geometry.
def cellular_transport():
    W, H = 520, 420
    stops = [("Nucleus", 90.0, 300.0), ("ER", 180.0, 200.0), ("Golgi", 300.0, 150.0),
             ("Membrane", 440.0, 230.0)]
    cmds = []
    cmds.append(var("t", "(continuousSec() * 0.25) % 1"))

    for si in range(len(stops) - 1):
        (n0, x0, y0), (n1, x1, y1) = stops[si], stops[si + 1]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2 - 60.0
        pid = "route%d" % si
        pts = []
        for k in range(31):
            u = k / 30.0
            px = (1 - u) ** 2 * x0 + 2 * (1 - u) * u * mx + u * u * x1
            py = (1 - u) ** 2 * y0 + 2 * (1 - u) * u * my + u * u * y1
            pts.append((round(px, 2), round(py, 2)))
        cmds.append({"pathCreate": {"id": pid, "x": pts[0][0], "y": pts[0][1]}})
        for px, py in pts[1:]:
            cmds.append({"pathAppendLineTo": {"path": pid, "x": px, "y": py}})
        cmds.append(paint({"color": "#FF46608E"}, {"style": "stroke"}, {"width": 2.2}))
        cmds.append({"drawPath": {"path": pid}})
        # vesicles riding the route, their positions sampled from the same Bezier
        for v in range(3):
            off = v / 3.0
            cmds.append(paint({"color": [GOOD, WARM, ACCENT][si]}, {"style": "fill"}))
            u_expr = "((@t + %.3f) %% 1)" % off
            cmds.append({"drawCircle": {
                "cx": "%.1f + (%.1f) * %s + (%.1f) * %s * %s"
                      % (x0, 2 * (mx - x0), u_expr, (x1 - 2 * mx + x0), u_expr, u_expr),
                "cy": "%.1f + (%.1f) * %s + (%.1f) * %s * %s"
                      % (y0, 2 * (my - y0), u_expr, (y1 - 2 * my + y0), u_expr, u_expr),
                "radius": 5.5}})

    for name, x, y in stops:
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": x, "cy": y, "radius": 34.0}})
        cmds.append(paint({"color": "#FF7E9AC6"}, {"style": "stroke"}, {"width": 2.0}))
        cmds.append({"drawCircle": {"cx": x, "cy": y, "radius": 34.0}})
        cmds.append(paint({"color": TEXT}, {"style": "fill"}, {"textSize": 10.5}))
        cmds.append({"drawTextAnchored": {"text": name, "x": x, "y": y + 4.0,
                                          "panX": 0.0, "panY": 0.0, "flags": 0}})

    cmds += text_at("proteins are made at the ER, modified at the Golgi, then shipped out",
                    24.0, 366.0, 11.0, TEXT)
    cmds += text_at("each route is a path; the vesicles are sampled from the same curve",
                    24.0, 384.0, 10.0, DIM)
    cmds += text_at("three routes, nine vesicles", 24.0, 402.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "Vesicles travelling curved routes from nucleus to ER to "
                                   "Golgi to membrane"),
            "root": canvas(title(cmds, W, H, "Cellular transport",
                                 "the secretory pathway"))}


use("BIO-CB-00013")
docs["BIO-CB-00013"] = cellular_transport()


# ── 5. BIO-BIOC-00014  Proteins — expression-animation / simulate / 3D ───────
# A backbone as a 3D helix of residues, turning. Secondary structure is the point, so the
# helix pitch and the sheet run are both present and coloured differently.
def proteins():
    W, H = 460, 460
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.9, "aspect": 1.0,
                          "near": 0.1, "far": 60.0,
                          "eye": [0.4, 0.9, 3.5], "center": [0, 0, 0], "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.35, -0.6, -0.72], "intensity": 1.0},
                {"type": "directional", "color": "#FF4FD6C9",
                 "dir": [0.5, 0.25, 0.4], "intensity": 0.3}]}}]
    cmds.append(var("spin", "continuousSec() * 0.4"))

    mid = 20
    N = 46
    for i in range(N):
        u = i / (N - 1.0)
        if u < 0.45:                       # alpha helix
            t = u / 0.45
            ang = t * 7.5 * math.pi
            x, y, z = 0.34 * math.cos(ang), -0.95 + t * 0.95, 0.34 * math.sin(ang)
            colour, r = ACCENT, 0.075
        elif u < 0.6:                      # loop
            t = (u - 0.45) / 0.15
            x, y, z = 0.34 + t * 0.30, 0.02 + t * 0.14, -t * 0.20
            colour, r = DIM, 0.06
        else:                              # beta strand
            t = (u - 0.6) / 0.4
            x, y, z = 0.64 - t * 0.1, 0.16 + t * 0.78, -0.20 + math.sin(t * 9.0) * 0.08
            colour, r = WARM, 0.075
        mid += 1
        cmds += [{"meshPrimitive3D": {"id": mid, "primitive": "sphere", "segments": 10,
                                      "radius": r, "center": [0, 0, 0]}},
                 {"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 {"matrix3D": {"op": "translate", "x": round(x, 4),
                               "y": round(y, 4), "z": round(z, 4)}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mid, "mode": "software-smooth"}}]

    for i, (label, colour) in enumerate([("alpha helix", ACCENT), ("loop", DIM),
                                         ("beta strand", WARM)]):
        yy = 372.0 + i * 17.0
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": 28.0, "cy": yy - 3.0, "radius": 5.0}})
        cmds += text_at(label, 42.0, yy, 10.5, DIM)
    cmds += text_at("46 residues, turning on the document's own clock",
                    24.0, 436.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "A protein backbone of 46 residues turning in 3D, with "
                                   "helix, loop and strand coloured separately"),
            "root": canvas(title(cmds, W, H, "Protein structure",
                                 "a backbone, folded"))}


use("BIO-BIOC-00014")
docs["BIO-BIOC-00014"] = proteins()


# ── 6. BIO-BIOC-00015  Enzymes — particle-system / analyze / 2D ──────────────
# Substrate particles, and the analysis is the saturation curve beside them: as substrate
# rises the rate climbs and then flattens, because the enzymes run out of sites. Position
# encodes concentration, which is what makes the particles worth their cost.
def enzymes():
    W, H = 540, 420
    px0, px1, py0, py1 = 30.0, 270.0, 100.0, 300.0
    cmds = []
    cmds.append(var("sub", "0.5 + sin(continuousSec() * 0.35) * 0.45"))

    cmds.append(paint({"color": PANEL}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": px0, "top": py0, "right": px1, "bottom": py1}})
    cmds.append({"createParticles": {
        "id": "sb",
        "variables": ["bx", "by", "lv", "ph"],
        "initialValues": ["%.1f + rand() * %.1f" % (px0 + 10, px1 - px0 - 20),
                          "%.1f + rand() * %.1f" % (py0 + 10, py1 - py0 - 20),
                          "rand()", "rand() * 6.283"],
        "count": 110}})
    cmds.append({"particlesLoop": {
        "system": "@sb",
        "equations": ["bx", "by", "lv", "ph"],
        "commands": [
            # a molecule is present only while the concentration exceeds its own level
            paint({"color": GOOD}, {"style": "fill"},
                  {"alpha": "clamp(0.0, 0.9, (@sub - lv) * 9)"}),
            {"drawCircle": {"cx": "bx + sin(ph + animationTime * 1.4) * 3",
                            "cy": "by + cos(ph + animationTime * 1.2) * 3",
                            "radius": 4.2}}]}})
    # four enzymes along the bottom, saturating
    for k in range(4):
        x = px0 + 36.0 + k * 58.0
        cmds.append(paint({"color": WARM}, {"style": "fill"},
                          {"alpha": "clamp(0.3, 1.0, @sub * 2.2 - %.2f)" % (k * 0.22)}))
        cmds.append({"drawRoundRect": {"left": x - 16.0, "top": py1 - 26.0,
                                       "right": x + 16.0, "bottom": py1 - 4.0,
                                       "rx": 5.0, "ry": 5.0}})
    cmds += text_at("substrate", px0, py0 - 10.0, 10.5, GOOD)
    cmds += text_at("enzymes", px0, py1 + 16.0, 10.5, WARM)

    # the saturation curve, with the live point on it
    cx0, cx1, cy0, cy1 = 310.0, 510.0, 100.0, 300.0
    for g in (0.0, 0.5, 1.0):
        y = cy1 - g * (cy1 - cy0)
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": cx0, "y1": y, "x2": cx1, "y2": y}})
    pts = []
    for k in range(41):
        s = k / 40.0
        v = s / (0.25 + s)                      # Michaelis-Menten, Km = 0.25
        pts.append((round(cx0 + s * (cx1 - cx0), 2), round(cy1 - v * (cy1 - cy0), 2)))
    cmds.append({"pathCreate": {"id": "mm", "x": pts[0][0], "y": pts[0][1]}})
    for a, b in pts[1:]:
        cmds.append({"pathAppendLineTo": {"path": "mm", "x": a, "y": b}})
    cmds.append(paint({"color": ACCENT}, {"style": "stroke"}, {"width": 2.2}))
    cmds.append({"drawPath": {"path": "mm"}})
    cmds.append(var("vel", "@sub / (0.25 + @sub)"))
    cmds.append(paint({"color": HOT}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": "%.1f + @sub * %.1f" % (cx0, cx1 - cx0),
                                "cy": "%.1f - @vel * %.1f" % (cy1, cy1 - cy0),
                                "radius": 7.0}})
    cmds += text_at("rate", cx0, cy0 - 10.0, 10.5, ACCENT)
    cmds += text_at("substrate concentration", cx0, cy1 + 16.0, 10.0, DIM)
    cmds.append({"variable": {"name": "vt", "value": {"type": "textFromFloat",
                                                      "value": "@vel * 100",
                                                      "whole": 3, "decimal": 0}}})
    cmds.append(paint({"color": HOT}, {"style": "fill"}, {"textSize": 22.0}))
    cmds.append({"drawTextAnchored": {"text": "@vt", "x": cx1, "y": 342.0,
                                      "panX": 1.0, "panY": 0.0, "flags": 0}})
    cmds += text_at("% of maximum rate", cx1, 360.0, 10.0, DIM, pan_x=1.0)
    cmds += text_at("doubling the substrate stops helping once every site is busy",
                    24.0, 392.0, 11.0, TEXT)
    cmds += text_at("the curve flattens at saturation: more molecules, same enzymes",
                    24.0, 410.0, 10.0, DIM)
    return {"header": header(W, H, "Substrate molecules as particles beside the saturation "
                                   "curve they produce, with the live rate marked"),
            "root": canvas(title(cmds, W, H, "Enzyme saturation",
                                 "why more substrate stops helping"))}


use("BIO-BIOC-00015")
docs["BIO-BIOC-00015"] = enzymes()


# ── 7. BIO-BIOC-00016  Metabolism — interactive / explain / 2D ───────────────
# Drag the oxygen supply. With it, glucose goes all the way through and yields about 32 ATP;
# without it, glycolysis alone yields 2. That ratio is the single fact worth carrying away,
# and it is far more convincing when you move the slider yourself.
def metabolism():
    W, H = 540, 400
    cmds = []
    cmds.append({"touchExpression": {"name": "o2", "defaultValue": 0.72,
                                     "min": 0.0, "max": 1.0, "stopMode": "gently",
                                     "expression": "touchX() / 540"}})
    cmds.append(var("ox", "clamp(0.0, 1.0, @o2)"))
    cmds.append(var("atp", "2 + @ox * 30"))

    stages = [("Glycolysis", 2.0, 1.0, GOOD),
              ("Krebs cycle", 2.0, 0.0, WARM),
              ("Electron transport", 28.0, 0.0, ACCENT)]
    left, width, top, barh = 40.0, 440.0, 116.0, 44.0
    for i, (name, yield_, always, colour) in enumerate(stages):
        y = top + i * (barh + 16.0)
        frac = yield_ / 32.0
        gate = "1" if always else "@ox"
        cmds.append(paint({"color": "#FF1B2740"}, {"style": "fill"}))
        cmds.append({"drawRoundRect": {"left": left, "top": y, "right": left + width,
                                       "bottom": y + barh, "rx": 6.0, "ry": 6.0}})
        cmds.append(paint({"color": colour}, {"style": "fill"},
                          {"alpha": "clamp(0.25, 1.0, %s)" % gate}))
        cmds.append({"drawRoundRect": {"left": left, "top": y,
                                       "right": "%.1f + %s * %.2f" % (left, gate,
                                                                      width * frac),
                                       "bottom": y + barh, "rx": 6.0, "ry": 6.0}})
        cmds += text_at(name, left + 14.0, y + 27.0, 13.0, INK)
        cmds += text_at("%d ATP" % yield_, left + width - 14.0, y + 27.0, 12.0, TEXT,
                        pan_x=1.0)
        if not always:
            cmds += text_at("needs oxygen", left + width - 14.0, y + 42.0, 9.0, DIM,
                            pan_x=1.0)

    cmds.append({"variable": {"name": "at", "value": {"type": "textFromFloat",
                                                      "value": "@atp", "whole": 2,
                                                      "decimal": 0}}})
    cmds.append(paint({"color": TEXT}, {"style": "fill"}, {"textSize": 34.0}))
    cmds.append({"drawTextAnchored": {"text": "@at", "x": left + width, "y": 326.0,
                                      "panX": 1.0, "panY": 0.0, "flags": 0}})
    cmds += text_at("ATP per glucose molecule", left, 326.0, 11.5, DIM)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 2.0}))
    cmds.append({"drawLine": {"x1": left, "y1": 350.0, "x2": left + width, "y2": 350.0}})
    cmds.append(paint({"color": GOOD}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": "%.1f + @ox * %.1f" % (left, width),
                                "cy": 350.0, "radius": 7.0}})
    cmds += text_at("no oxygen", left, 372.0, 10.0, DIM)
    cmds += text_at("full oxygen", left + width, 372.0, 10.0, GOOD, pan_x=1.0)
    cmds += text_at("without oxygen only glycolysis runs: 2 ATP instead of 32",
                    left, 392.0, 10.0, TEXT)
    return {"header": header(W, H, "Drag the oxygen supply and watch ATP yield per glucose "
                                   "fall from 32 to 2"),
            "root": canvas(title(cmds, W, H, "Respiration", "what oxygen is worth"))}


use("BIO-BIOC-00016")
docs["BIO-BIOC-00016"] = metabolism()


# ── 8. MTH-AN-00004  Number systems — raster-and-text / explore / 2D ─────────
# The same value in four bases, set as a table. Binary is given a monospaced treatment with
# nibbles separated, because the grouping is what makes it readable at all.
def number_systems():
    W, H = 560, 400
    values = [5, 12, 27, 64, 100, 170, 255]
    cols = [30.0, 190.0, 400.0, 470.0, 545.0]
    cmds = []
    for name, x, pan in (("DECIMAL", cols[0], -1.0), ("BINARY", cols[1], -1.0),
                         ("OCTAL", cols[2], 1.0), ("HEX", cols[3], 1.0),
                         ("BITS", cols[4], 1.0)):
        cmds += text_at(name, x, 96.0, 9.5, DIM, pan_x=pan)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": 30.0, "y1": 104.0, "x2": 545.0, "y2": 104.0}})

    for i, v in enumerate(values):
        y = 134.0 + i * 36.0
        cmds += text_at(str(v), cols[0], y, 16.0, TEXT)
        bits = format(v, "08b")
        # nibble by nibble, so the eye can group them
        for b, ch in enumerate(bits):
            x = cols[1] + b * 20.0 + (10.0 if b >= 4 else 0.0)
            on = ch == "1"
            cmds.append(paint({"color": ACCENT if on else "#FF26324C"}, {"style": "fill"}))
            cmds.append({"drawRect": {"left": x, "top": y - 13.0,
                                      "right": x + 16.0, "bottom": y + 3.0}})
            cmds += text_at(ch, x + 8.0, y - 1.0, 10.5,
                            INK if on else "#FF5E6E95", pan_x=0.0)
        cmds += text_at(format(v, "o"), cols[2], y, 13.0, GOOD, pan_x=1.0)
        cmds += text_at(format(v, "02X"), cols[3], y, 14.0, WARM, pan_x=1.0)
        cmds += text_at(str(bin(v).count("1")), cols[4], y, 12.0, DIM, pan_x=1.0)
        if i < len(values) - 1:
            cmds.append(paint({"color": "#FF1B2740"}, {"style": "stroke"}, {"width": 1.0}))
            cmds.append({"drawLine": {"x1": 30.0, "y1": y + 14.0,
                                      "x2": 545.0, "y2": y + 14.0}})
    cmds += text_at("128   64   32   16        8    4    2    1", cols[1], 384.0, 9.0,
                    "#FF5E6E95")
    cmds += text_at("each column is worth twice the one to its right", 30.0, 384.0,
                    10.0, TEXT)
    return {"header": header(W, H, "Seven values in decimal, binary, octal and hex, with the "
                                   "binary split into nibbles"),
            "root": canvas(title(cmds, W, H, "Number systems", "one value, four bases"))}


use("MTH-AN-00004")
docs["MTH-AN-00004"] = number_systems()


# ── 9. CSC-ALGO-00004  Dynamic programming — static-diagram / explore / 2D ───
# The edit-distance table for two short words, filled in, with the traceback marked. A DP
# document should show the TABLE, because the table is the algorithm; animating the fill
# would hide the thing worth looking at.
def dynamic_programming():
    A, B = "kitten", "sitting"
    W, H = 560, 470
    n, m = len(A), len(B)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + (A[i - 1] != B[j - 1]))
    # traceback
    path, i, j = set(), n, m
    while i or j:
        path.add((i, j))
        if i and j and d[i][j] == d[i - 1][j - 1] + (A[i - 1] != B[j - 1]):
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            i -= 1
        else:
            j -= 1
    path.add((0, 0))

    cell, x0, y0 = 38.0, 124.0, 108.0
    table_bottom = y0 + (n + 1) * cell
    cmds = []
    for j in range(m + 1):
        if j:
            cmds += text_at(B[j - 1], x0 + j * cell + cell / 2, y0 - 12.0, 13.0,
                            GOOD, pan_x=0.0)
    for i in range(n + 1):
        if i:
            cmds += text_at(A[i - 1], x0 - 14.0, y0 + i * cell + cell / 2 + 5.0, 13.0,
                            WARM, pan_x=1.0)
    for i in range(n + 1):
        for j in range(m + 1):
            x, y = x0 + j * cell, y0 + i * cell
            on = (i, j) in path
            cmds.append(paint({"color": ACCENT if on else PANEL}, {"style": "fill"}))
            cmds.append({"drawRect": {"left": x + 1, "top": y + 1,
                                      "right": x + cell - 1, "bottom": y + cell - 1}})
            cmds += text_at(str(d[i][j]), x + cell / 2, y + cell / 2 + 5.0, 13.0,
                            INK if on else DIM, pan_x=0.0)
    cmds += text_at("edit distance %d" % d[n][m], 24.0, table_bottom + 32.0, 16.0, TEXT)
    cmds += text_at("each cell is the cheapest way to reach it from the three above and "
                    "to its left", 24.0, table_bottom + 56.0, 10.5, DIM)
    cmds += text_at("the highlighted run is the edit path the table encodes",
                    24.0, table_bottom + 74.0, 10.0, ACCENT)
    return {"header": header(W, H, "The edit-distance table between kitten and sitting, "
                                   "filled, with the traceback highlighted"),
            "root": canvas(title(cmds, W, H, "Edit distance",
                                 "kitten to sitting, one table"))}


use("CSC-ALGO-00004")
docs["CSC-ALGO-00004"] = dynamic_programming()


# ── 10. CHM-MS-00004  Molecules — annotated-layout / compare / 2D ────────────
# Four molecules as cards, each with its own small canvas. The comparison is bond angle
# against shape, so every card states the angle and draws the geometry to match it.
MOLECULES = [("Water", "H2O", 104.5, 2, 2, "bent", ACCENT),
             ("Ammonia", "NH3", 107.0, 3, 1, "pyramidal", GOOD),
             ("Methane", "CH4", 109.5, 4, 0, "tetrahedral", WARM),
             ("Carbon dioxide", "CO2", 180.0, 2, 0, "linear", HOT)]


def molecules():
    W, H = 500, 620

    def geometry(angle, bonds, lone, colour):
        c = [paint({"color": "#FF0F1830"}, {"style": "fill"}),
             {"drawRect": {"left": 0, "top": 0, "right": 150, "bottom": 110}}]
        cx, cy = 75.0, 58.0
        half = math.radians(angle) / 2
        for k in range(bonds):
            if bonds == 2:
                th = -math.pi / 2 + (half if k else -half)
            else:
                th = -math.pi / 2 + (k - (bonds - 1) / 2) * math.radians(angle) * 0.72
            ex, ey = cx + 40 * math.sin(th + math.pi / 2), cy - 40 * math.cos(th + math.pi / 2)
            c.append(paint({"color": "#FF9FB0D4"}, {"style": "stroke"}, {"width": 2.6},
                           {"strokeCap": "round"}))
            c.append({"drawLine": {"x1": cx, "y1": cy, "x2": round(ex, 1),
                                   "y2": round(ey, 1)}})
            c.append(paint({"color": "#FFE4ECFA"}, {"style": "fill"}))
            c.append({"drawCircle": {"cx": round(ex, 1), "cy": round(ey, 1),
                                     "radius": 10.0}})
        for k in range(lone):
            th = math.pi / 2 + (k - (lone - 1) / 2) * 0.5
            c.append(paint({"color": colour}, {"style": "fill"}, {"alpha": 0.5}))
            c.append({"drawCircle": {"cx": round(cx + 26 * math.cos(th), 1),
                                     "cy": round(cy + 26 * math.sin(th), 1),
                                     "radius": 7.0}})
        c.append(paint({"color": colour}, {"style": "fill"}))
        c.append({"drawCircle": {"cx": cx, "cy": cy, "radius": 15.0}})
        return {"type": "canvas", "modifiers": [{"width": 150}, {"height": 110}],
                "commands": c}

    cards = []
    for name, formula, angle, bonds, lone, shape, colour in MOLECULES:
        cards.append({"type": "row",
                      "modifiers": [{"width": 460}, {"padding": 8},
                                    {"background": PANEL}],
                      "children": [
                          geometry(angle, bonds, lone, colour),
                          {"type": "spacer", "modifiers": [{"width": 12}]},
                          {"type": "column", "modifiers": [{"width": 270}], "children": [
                              {"type": "text", "value": "%s   %s" % (name, formula),
                               "modifiers": [], "fontSize": 14.0, "color": colour},
                              {"type": "spacer", "modifiers": [{"height": 6}]},
                              {"type": "text", "value": "%.1f degrees" % angle,
                               "modifiers": [], "fontSize": 16.0, "color": TEXT},
                              {"type": "spacer", "modifiers": [{"height": 4}]},
                              {"type": "text",
                               "value": "%s - %d bonding, %d lone"
                                        % (shape, bonds, lone),
                               "modifiers": [], "fontSize": 10.5, "color": DIM}]}]})
        cards.append({"type": "spacer", "modifiers": [{"height": 8}]})

    return {
        "header": header(W, H, "Four molecules compared by bond angle and shape, each card "
                               "drawing the geometry it states"),
        "root": {"type": "column",
                 "modifiers": ["fillMaxSize", {"background": INK}, {"padding": 16}],
                 "children": [
                     {"type": "text", "value": "Molecular shape", "modifiers": [],
                      "fontSize": 20.0, "color": TEXT},
                     {"type": "spacer", "modifiers": [{"height": 4}]},
                     {"type": "text",
                      "value": "lone pairs push bonds closer together",
                      "modifiers": [], "fontSize": 11.0, "color": DIM},
                     {"type": "spacer", "modifiers": [{"height": 12}]},
                 ] + cards + [
                     {"type": "text",
                      "value": "methane has none and opens to 109.5; water has two and "
                               "closes to 104.5",
                      "modifiers": [], "fontSize": 9.5, "color": "#FF5E6E95"}]},
    }


use("CHM-MS-00004")
docs["CHM-MS-00004"] = molecules()


# ── 11. EAR-GEOL-00004  Earthquakes — data-plot / demonstrate / 2D ───────────
# Magnitude is logarithmic and nobody believes how steeply until they see the energy beside
# it. Two bars per quake: the magnitude, which looks mild, and the energy, which does not.
QUAKES = [("Minor", 3.0), ("Light", 4.0), ("Moderate", 5.0), ("Strong", 6.0),
          ("Major", 7.0), ("Great", 8.0), ("Tohoku 2011", 9.1)]


def earthquakes():
    W, H = 560, 420
    left, right, top = 150.0, 520.0, 110.0
    rowh = 38.0
    cmds = []
    mags = [m for _, m in QUAKES]
    energies = [10 ** (1.5 * (m - 3.0)) for _, m in QUAKES]
    emax = max(energies)

    cmds.append({"loop": {"index": "i", "from": 0.0, "until": float(len(QUAKES)),
                          "step": 1.0, "commands": [
        var("m", "arrayGet(@mag, @i)"),
        var("yy", "%.1f + @i * %.1f" % (top, rowh)),
        paint({"color": "#FF2B3A5C"}, {"style": "fill"}),
        {"drawRoundRect": {"left": left, "top": "@yy + 2",
                           "right": "%.1f + @m / 9.1 * %.1f" % (left, (right - left) * 0.45),
                           "bottom": "@yy + 12", "rx": 3.0, "ry": 3.0}},
    ]}})

    for i, (name, m) in enumerate(QUAKES):
        y = top + i * rowh
        e = 10 ** (1.5 * (m - 3.0))
        # energy on a log width, or the first six rows would be invisible
        w = (math.log10(e) / math.log10(emax)) * (right - left)
        cmds.append(paint({"color": HOT}, {"style": "fill"},
                          {"alpha": 0.55 + 0.45 * (i / (len(QUAKES) - 1))}))
        cmds.append({"drawRoundRect": {"left": left, "top": y + 16.0,
                                       "right": left + max(w, 3.0), "bottom": y + 30.0,
                                       "rx": 3.0, "ry": 3.0}})
        cmds += text_at(name, left - 12.0, y + 20.0, 11.5, TEXT, pan_x=1.0)
        cmds += text_at("M%.1f" % m, left + 6.0, y + 11.0, 9.5, DIM)
        if e >= 1000:
            lbl = "%.0f thousand x" % (e / 1000)
        else:
            lbl = "%.0f x" % e
        cmds += text_at(lbl, left + max(w, 3.0) + 8.0, y + 27.0, 9.5, HOT)

    cmds += text_at("magnitude", left, top - 14.0, 10.0, "#FF7E9AC6")
    cmds += text_at("energy released, relative to M3 (log scale)", left + 150.0,
                    top - 14.0, 10.0, HOT)
    cmds += text_at("one step up in magnitude is about 32 times the energy",
                    24.0, 384.0, 11.5, TEXT)
    cmds += text_at("Tohoku released roughly a million times a minor quake",
                    24.0, 402.0, 10.0, DIM)
    return {"header": header(W, H, "Earthquake magnitude against energy released, showing "
                                   "the 32-fold step the scale hides"),
            "resources": {"floatArrays": [{"mag": mags}]},
            "root": canvas(title(cmds, W, H, "Earthquake energy",
                                 "what one point of magnitude costs"))}


use("EAR-GEOL-00004")
docs["EAR-GEOL-00004"] = earthquakes()


# ── 12. ENG-ME-00004  Engines — path-form / simulate / 3D ────────────────────
# The four-stroke cycle. The piston path is a real path traced from the crank geometry, the
# cylinder is a 3D wireframe, and the stroke label follows the same clock - so the diagram
# cannot drift out of step with its own caption.
def engines():
    W, H = 480, 476
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.95, "aspect": 1.0,
                          "near": 0.1, "far": 60.0,
                          "eye": [1.9, 1.1, 2.6], "center": [0, -0.1, 0], "up": [0, 1, 0]}},
            {"lights3D": {"lights": [{"type": "directional", "color": "#FFFFFFFF",
                                      "dir": [-0.4, -0.55, -0.73], "intensity": 1.0}]}}]
    cmds.append(var("a", "continuousSec() * 1.2"))
    # Phased so a stroke BEGINS at a dead centre. Unshifted, top dead centre fell at
    # stroke 1.5 - the middle of compression - so every label described the wrong half of
    # the travel. 2.5pi is the offset that puts intake at TDC.
    cmds.append(var("stroke", "((continuousSec() * 1.2 + 7.853982) / 3.141593) % 4"))
    # Combustion: a short flash at the top of the power stroke, which begins at TDC when
    # stroke crosses 2. Peaks there and is gone within a third of a stroke.
    cmds.append(var("burst", "clamp(0.0, 1.0, 1 - abs(@stroke - 2.0) * 3.2)"))

    ox, oy, crank, rod = 240.0, 330.0, 42.0, 120.0
    cmds.append(var("cy", "%.1f + sin(@a) * %.1f" % (oy, crank)))
    cmds.append(var("cx", "%.1f + cos(@a) * %.1f" % (ox, crank)))
    cmds.append(var("piston", "@cy - sqrt(%.1f - (@cx - %.1f) * (@cx - %.1f))"
                   % (rod * rod, ox, ox)))

    # the piston's travel, as a path traced from the same geometry
    pts = []
    for k in range(73):
        th = k / 72.0 * 2 * math.pi
        px = ox + math.cos(th) * crank
        py = oy + math.sin(th) * crank
        yy = py - math.sqrt(rod * rod - (px - ox) ** 2)
        pts.append((round(ox + 86.0, 2), round(yy, 2)))
    lo = min(p[1] for p in pts)
    hi = max(p[1] for p in pts)
    cmds.append(paint({"color": "#FF46608E"}, {"style": "stroke"}, {"width": 2.0}))
    cmds.append({"drawLine": {"x1": ox + 86.0, "y1": lo, "x2": ox + 86.0, "y2": hi}})
    for yy, lbl in ((lo, "top dead centre"), (hi, "bottom dead centre")):
        cmds.append({"drawLine": {"x1": ox + 78.0, "y1": yy, "x2": ox + 94.0, "y2": yy}})
        cmds += text_at(lbl, ox + 100.0, yy + 4.0, 9.0, DIM)

    cmds.append(paint({"color": "#FF1A2540"}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": ox - 46.0, "top": lo - 30.0,
                              "right": ox + 46.0, "bottom": oy}})
    # the burning charge fills the chamber between the head and the piston crown
    cmds.append(paint({"color": HOT}, {"style": "fill"}, {"alpha": "@burst * 0.85"}))
    cmds.append({"drawRoundRect": {"left": ox - 40.0, "top": lo - 26.0,
                                   "right": ox + 40.0, "bottom": "@piston - 20",
                                   "rx": 6.0, "ry": 6.0}})
    cmds.append(paint({"color": WARM}, {"style": "fill"}, {"alpha": "@burst"}))
    cmds.append({"drawCircle": {"cx": ox, "cy": lo - 14.0, "radius": "6 + @burst * 16"}})
    # spark lines, radiating from the plug
    for k in range(8):
        th = k * math.pi / 4
        cmds.append(paint({"color": "#FFFFF0C0"}, {"style": "stroke"}, {"width": 2.0},
                          {"strokeCap": "round"}, {"alpha": "@burst"}))
        cmds.append({"drawLine": {
            "x1": round(ox + math.cos(th) * 10, 1), "y1": round(lo - 14.0 + math.sin(th) * 10, 1),
            "x2": "%.1f + @burst * %.1f" % (ox + math.cos(th) * 12, math.cos(th) * 26),
            "y2": "%.1f + @burst * %.1f" % (lo - 14.0 + math.sin(th) * 12,
                                            math.sin(th) * 26)}})
    # the plug itself, always present
    cmds.append(paint({"color": "#FF8A99BC"}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": ox - 5.0, "top": lo - 34.0,
                              "right": ox + 5.0, "bottom": lo - 16.0}})

    cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
    cmds.append({"drawRoundRect": {"left": ox - 40.0, "top": "@piston - 22",
                                   "right": ox + 40.0, "bottom": "@piston + 22",
                                   "rx": 5.0, "ry": 5.0}})
    cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 4.0},
                      {"strokeCap": "round"}))
    cmds.append({"drawLine": {"x1": "@cx", "y1": "@cy", "x2": ox, "y2": "@piston"}})
    cmds.append(paint({"color": GOOD}, {"style": "stroke"}, {"width": 5.0},
                      {"strokeCap": "round"}))
    cmds.append({"drawLine": {"x1": ox, "y1": oy, "x2": "@cx", "y2": "@cy"}})
    cmds.append(paint({"color": TEXT}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": ox, "cy": oy, "radius": 7.0}})

    # the cylinder as a 3D wireframe, drawn last
    verts, normals, uv, idx = [], [], [], []
    mesh_box(verts, normals, uv, idx, (-0.45, -0.9, -0.45), (0.45, 0.9, 0.45))
    cmds.append({"defineMesh3D": {"id": 1, "verts": verts, "normals": normals,
                                  "uv": uv, "indices": idx}})
    cmds += [{"matrix3D": {"op": "identity"}},
             paint({"color": "#FF27385C"}, {"style": "stroke"}, {"width": 1.0}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth", "wireframe": True}}]

    for i, (name, colour) in enumerate([("intake", GOOD), ("compression", ACCENT),
                                        ("power", HOT), ("exhaust", DIM)]):
        x = 30.0 + i * 108.0
        cmds.append(paint({"color": colour}, {"style": "fill"},
                          {"alpha": "clamp(0.2, 1.0, 1.2 - abs(@stroke - %d))" % i}))
        cmds.append({"drawRoundRect": {"left": x, "top": 392.0, "right": x + 96.0,
                                       "bottom": 416.0, "rx": 5.0, "ry": 5.0}})
        cmds += text_at(name, x + 48.0, 408.0, 10.5, INK, pan_x=0.0)
    cmds.append(paint({"color": WARM}, {"style": "fill"}, {"textSize": 11.0},
                      {"alpha": "@burst"}))
    cmds.append({"drawTextAnchored": {"text": "ignition", "x": ox + 54.0, "y": lo - 12.0,
                                      "panX": -1.0, "panY": 0.0, "flags": 0}})
    cmds += text_at("the charge fires at top dead centre and drives the power stroke",
                    24.0, 438.0, 10.0, DIM)
    cmds += text_at("stroke phase is tied to the crank, so the label and the piston cannot "
                    "disagree", 24.0, 454.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "A four-stroke engine with the piston travel traced as a "
                                   "path and the current stroke highlighted"),
            "root": canvas(title(cmds, W, H, "Four strokes", "one cylinder, one cycle"))}


use("ENG-ME-00004")
docs["ENG-ME-00004"] = engines()


# ── 13. SOC-SOCI-00001  Social networks — expression-animation / analyze / 2D ─
# A fixed graph with a signal spreading through it. The analysis is reach over time: at each
# step the wavefront is a ring of nodes, and the counter says how many have been touched.
NET_NODES = [(0.50, 0.18), (0.26, 0.30), (0.74, 0.30), (0.14, 0.54), (0.38, 0.50),
             (0.62, 0.50), (0.86, 0.54), (0.22, 0.76), (0.46, 0.74), (0.66, 0.76),
             (0.86, 0.80), (0.34, 0.90), (0.58, 0.92)]
NET_EDGES = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6), (4, 5), (3, 7), (4, 8),
             (5, 9), (6, 10), (7, 11), (8, 11), (8, 9), (9, 12), (10, 9), (11, 12)]


def social_networks():
    W, H = 480, 460

    # breadth-first depth from node 0, so each node knows when the signal reaches it
    depth = {0: 0}
    frontier = [0]
    while frontier:
        nxt = []
        for u in frontier:
            for a, b in NET_EDGES:
                for x, y in ((a, b), (b, a)):
                    if x == u and y not in depth:
                        depth[y] = depth[u] + 1
                        nxt.append(y)
        frontier = nxt
    maxd = max(depth.values())

    def pos(i):
        x, y = NET_NODES[i]
        return 50.0 + x * 380.0, 100.0 + y * 250.0

    cmds = []
    cmds.append(var("w", "(continuousSec() * 0.55) %% %d" % (maxd + 2)))

    for a, b in NET_EDGES:
        ax, ay = pos(a)
        bx, by = pos(b)
        lit = max(depth[a], depth[b])
        cmds.append(paint({"color": ACCENT}, {"style": "stroke"}, {"width": 1.6},
                          {"alpha": "clamp(0.12, 0.9, (@w - %d) * 1.6)" % lit}))
        cmds.append({"drawLine": {"x1": round(ax, 1), "y1": round(ay, 1),
                                  "x2": round(bx, 1), "y2": round(by, 1)}})
    for i in range(len(NET_NODES)):
        x, y = pos(i)
        d = depth[i]
        cmds.append(paint({"color": GOOD if d else WARM}, {"style": "fill"},
                          {"alpha": "clamp(0.18, 1.0, (@w - %d) * 2.2)" % d}))
        cmds.append({"drawCircle": {"cx": round(x, 1), "cy": round(y, 1),
                                    "radius": 13.0 if d else 17.0}})
        cmds += text_at(str(d), round(x, 1), round(y, 1) + 4.0, 10.0, INK, pan_x=0.0)

    # reach: how many nodes are within the current wavefront
    counts = [sum(1 for v in depth.values() if v <= k) for k in range(maxd + 1)]
    bx0, bw = 50.0, 380.0
    cmds.append(paint({"color": "#FF1B2740"}, {"style": "fill"}))
    cmds.append({"drawRoundRect": {"left": bx0, "top": 384.0, "right": bx0 + bw,
                                   "bottom": 404.0, "rx": 4.0, "ry": 4.0}})
    for k, c in enumerate(counts):
        cmds.append(paint({"color": GOOD}, {"style": "fill"},
                          {"alpha": "clamp(0.0, 1.0, (@w - %d) * 2.0)" % k}))
        cmds.append({"drawRoundRect": {
            "left": bx0, "top": 384.0,
            "right": bx0 + bw * c / len(NET_NODES), "bottom": 404.0,
            "rx": 4.0, "ry": 4.0}})
    cmds += text_at("reach", bx0, 378.0, 10.0, DIM)
    cmds += text_at("%d people" % len(NET_NODES), bx0 + bw, 378.0, 10.0, DIM, pan_x=1.0)
    cmds += text_at("the number in each node is how many steps from the source",
                    24.0, 426.0, 10.5, TEXT)
    cmds += text_at("every node is within %d steps: that is what makes it a small world"
                    % maxd, 24.0, 444.0, 10.0, DIM)
    return {"header": header(W, H, "A signal spreading through a 13-person network, with "
                                   "each node labelled by its distance from the source"),
            "root": canvas(title(cmds, W, H, "How far news travels",
                                 "one source, thirteen people"))}


use("SOC-SOCI-00001")
docs["SOC-SOCI-00001"] = social_networks()


# ── 14. SOC-SOCI-00002  Population structure — particle-system / explain / 2D ─
# A population pyramid where every dot is a person: height is age band, side is sex, and the
# number of dots in a band IS the cohort size. The shape falls out of the data rather than
# being drawn.
COHORTS = [("0-9", 62, 59), ("10-19", 64, 61), ("20-29", 70, 67), ("30-39", 66, 64),
           ("40-49", 58, 58), ("50-59", 50, 52), ("60-69", 38, 42),
           ("70-79", 24, 30), ("80+", 10, 18)]


def population():
    W, H = 540, 460
    cx = 270.0
    top, bandh = 92.0, 34.0
    cmds = []
    scale = 2.2
    for bi, (label, male, female) in enumerate(COHORTS):
        y = top + bi * bandh
        # the cohort extent, drawn first: without it the silhouette depends on where random
        # dots happen to land, and a pyramid with a ragged edge is not a pyramid
        for side, n, colour in ((-1, male, ACCENT), (1, female, GOOD)):
            span = n * scale
            x0 = cx + 6.0 if side > 0 else cx - 6.0 - span
            cmds.append(paint({"color": colour}, {"style": "fill"}, {"alpha": 0.16}))
            cmds.append({"drawRect": {"left": round(x0, 2), "top": y + 2.0,
                                      "right": round(x0 + span, 2),
                                      "bottom": y + bandh - 8.0}})
        for side, n, colour in ((-1, male, ACCENT), (1, female, GOOD)):
            sysid = "c%d%s" % (bi, "m" if side < 0 else "f")
            count = max(4, int(n / 5))
            span = n * scale
            cmds.append({"createParticles": {
                "id": sysid,
                "variables": ["dx", "dy", "ph"],
                "initialValues": [
                    "%.2f + rand() * %.2f" % (cx + (6.0 if side > 0 else -6.0 - span),
                                              span),
                    "%.2f + rand() * %.2f" % (y + 4, bandh - 12),
                    "rand() * 6.283"],
                "count": count}})
            cmds.append({"particlesLoop": {
                "system": "@" + sysid,
                "equations": ["dx", "dy", "ph"],
                "commands": [
                    paint({"color": colour}, {"style": "fill"}, {"alpha": 0.85}),
                    {"drawCircle": {"cx": "dx + sin(ph + animationTime * 0.8) * 1.6",
                                    "cy": "dy + cos(ph + animationTime * 0.7) * 1.6",
                                    "radius": 3.4}}]}})
        cmds += text_at(label, cx, y + 20.0, 9.5, DIM, pan_x=0.0)

    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": cx, "y1": top - 6.0,
                              "x2": cx, "y2": top + len(COHORTS) * bandh}})
    cmds += text_at("men", cx - 120.0, top - 16.0, 12.0, ACCENT, pan_x=0.0)
    cmds += text_at("women", cx + 120.0, top - 16.0, 12.0, GOOD, pan_x=0.0)
    cmds += text_at("every dot is roughly five people in a thousand",
                    24.0, 418.0, 11.0, TEXT)
    cmds += text_at("the bands narrow with age, and women outnumber men at the top",
                    24.0, 436.0, 10.0, DIM)
    return {"header": header(W, H, "A population pyramid where each dot is a person, by age "
                                   "band and sex"),
            "root": canvas(title(cmds, W, H, "Population structure",
                                 "a pyramid made of people"))}


use("SOC-SOCI-00002")
docs["SOC-SOCI-00002"] = population()


# ── 15. SOC-SOCI-00003  Social mobility — interactive / explore / 2D ─────────
# Pick the quintile a child is born into and see where they end up. The diagonal is the
# finding: the top and bottom are stickier than the middle, and you can only feel that by
# moving between them.
MOBILITY = [  # rows: origin quintile, cols: destination
    [0.34, 0.28, 0.18, 0.12, 0.08],
    [0.25, 0.25, 0.22, 0.17, 0.11],
    [0.18, 0.21, 0.23, 0.21, 0.17],
    [0.13, 0.16, 0.21, 0.26, 0.24],
    [0.10, 0.12, 0.16, 0.24, 0.38],
]
QNAMES = ["poorest", "lower", "middle", "upper", "richest"]


def mobility():
    W, H = 540, 420
    cmds = []
    cmds.append({"touchExpression": {"name": "pick", "defaultValue": 0.0,
                                     "min": 0.0, "max": 4.99, "stopMode": "gently",
                                     "expression": "touchY() / 420 * 5"}})
    cmds.append(var("q", "clamp(0.0, 4.99, @pick)"))

    lx, rx = 90.0, 440.0
    top, gap = 120.0, 48.0
    for i, name in enumerate(QNAMES):
        y = top + i * gap
        cmds.append(paint({"color": PANEL}, {"style": "fill"},
                          {"alpha": "clamp(0.3, 1.0, 1.4 - abs(@q - %d))" % i}))
        cmds.append({"drawRoundRect": {"left": lx - 64.0, "top": y - 15.0,
                                       "right": lx - 6.0, "bottom": y + 15.0,
                                       "rx": 5.0, "ry": 5.0}})
        cmds += text_at(name, lx - 35.0, y + 4.0, 10.0, TEXT, pan_x=0.0)
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRoundRect": {"left": rx + 6.0, "top": y - 15.0,
                                       "right": rx + 64.0, "bottom": y + 15.0,
                                       "rx": 5.0, "ry": 5.0}})
        cmds += text_at(name, rx + 35.0, y + 4.0, 10.0, TEXT, pan_x=0.0)

    # one flow per origin/destination pair, lit only for the selected origin
    for i in range(5):
        for j in range(5):
            p = MOBILITY[i][j]
            y0 = top + i * gap
            y1 = top + j * gap
            colour = GOOD if j < i else (WARM if j == i else ACCENT)
            cmds.append(paint({"color": colour}, {"style": "stroke"},
                              {"width": max(1.5, p * 26.0)},
                              {"alpha": "clamp(0.0, 0.85, 1.2 - abs(@q - %d))" % i}))
            cmds.append({"drawLine": {"x1": lx, "y1": y0, "x2": rx, "y2": y1}})
            cmds.append(paint({"color": TEXT}, {"style": "fill"}, {"textSize": 9.5},
                              {"alpha": "clamp(0.0, 1.0, 1.2 - abs(@q - %d))" % i}))
            cmds.append({"drawTextAnchored": {
                "text": "%d%%" % round(p * 100), "x": rx - 30.0,
                "y": y1 + (j - i) * 0.0 + 4.0, "panX": 1.0, "panY": 0.0, "flags": 0}})

    cmds += text_at("born", lx - 35.0, top - 28.0, 11.0, DIM, pan_x=0.0)
    cmds += text_at("ends up", rx + 35.0, top - 28.0, 11.0, DIM, pan_x=0.0)
    cmds += text_at("drag up and down to choose where a child starts",
                    24.0, 374.0, 11.0, TEXT)
    cmds += text_at("34% born poorest stay poorest; 38% born richest stay richest",
                    24.0, 392.0, 10.0, WARM)
    cmds += text_at("the middle is the least sticky place to start", 24.0, 410.0,
                    10.0, DIM)
    return {"header": header(W, H, "Drag to choose a starting income quintile and see where "
                                   "children end up"),
            "root": canvas(title(cmds, W, H, "Social mobility",
                                 "where you start, where you land"))}


use("SOC-SOCI-00003")
docs["SOC-SOCI-00003"] = mobility()


# ── 16. SOC-SOCI-00004  Inequality — raster-and-text / compare / 2D ──────────
# Decile shares for four countries. A table, because the comparison is between numbers that
# sum to the same 100 - and the bottom-decile column is the one to read across.
INEQ = [("Slovakia", [3.9, 5.4, 6.4, 7.3, 8.3, 9.4, 10.8, 12.6, 15.3, 20.6], 24.1),
        ("France",   [3.1, 4.5, 5.6, 6.6, 7.7, 8.9, 10.4, 12.3, 15.4, 25.5], 30.7),
        ("Britain",  [2.7, 4.0, 5.1, 6.1, 7.2, 8.6, 10.3, 12.5, 16.1, 27.4], 32.6),
        ("Brazil",   [1.1, 2.1, 3.0, 3.9, 5.0, 6.4, 8.3, 11.2, 16.4, 42.6], 52.9)]


def inequality():
    W, H = 580, 400
    cmds = []
    x0, x1 = 120.0, 470.0
    cmds += text_at("COUNTRY", 26.0, 96.0, 9.5, DIM)
    cmds += text_at("POOREST TENTH TO RICHEST TENTH", x0, 96.0, 9.5, DIM)
    cmds += text_at("GINI", 554.0, 96.0, 9.5, DIM, pan_x=1.0)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": 26.0, "y1": 104.0, "x2": 554.0, "y2": 104.0}})

    for i, (name, deciles, gini) in enumerate(INEQ):
        y = 140.0 + i * 58.0
        cmds += text_at(name, 26.0, y, 14.5, TEXT)
        acc = 0.0
        for d, share in enumerate(deciles):
            w = (x1 - x0) * share / 100.0
            shade = int(60 + d * 18)
            cmds.append(paint({"color": "#FF%02X%02X%02X" % (shade, int(shade * 0.75),
                                                             int(shade * 0.55))},
                              {"style": "fill"}))
            cmds.append({"drawRect": {"left": round(x0 + acc, 2), "top": y - 14.0,
                                      "right": round(x0 + acc + w - 0.8, 2),
                                      "bottom": y + 4.0}})
            acc += w
        # the two ends, called out as numbers because they are the comparison
        cmds += text_at("%.1f" % deciles[0], x0, y + 20.0, 10.0, GOOD)
        cmds += text_at("%.1f" % deciles[-1], x1, y + 20.0, 10.0, HOT, pan_x=1.0)
        cmds += text_at("%.1f" % gini, 554.0, y, 16.0, WARM, pan_x=1.0)
        if i < len(INEQ) - 1:
            cmds.append(paint({"color": "#FF1B2740"}, {"style": "stroke"}, {"width": 1.0}))
            cmds.append({"drawLine": {"x1": 26.0, "y1": y + 32.0,
                                      "x2": 554.0, "y2": y + 32.0}})
    cmds += text_at("each row is the same 100% of a country's income, split ten ways",
                    26.0, 372.0, 11.0, TEXT)
    cmds += text_at("in Brazil the richest tenth takes 42.6%; in Slovakia, 20.6%",
                    26.0, 390.0, 10.0, DIM)
    return {"header": header(W, H, "Income decile shares for four countries with Gini "
                                   "coefficients, as a comparison table"),
            "root": canvas(title(cmds, W, H, "Who gets what",
                                 "income by tenth, four countries"))}


use("SOC-SOCI-00004")
docs["SOC-SOCI-00004"] = inequality()


# ── write ───────────────────────────────────────────────────────────────────────
def main():
    for doc_id, doc in docs.items():
        (OUT / ("%s.json" % doc_id)).write_text(json.dumps(doc, indent=1) + "\n")
    print("  wrote %d documents to %s" % (len(docs), OUT.name))
    import collections
    print("  palettes: %s" % dict(sorted(collections.Counter(PALETTE_USED.values()).items())))


if __name__ == "__main__":
    main()
