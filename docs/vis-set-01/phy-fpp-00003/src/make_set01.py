#!/usr/bin/env python3
"""Build set 1 of the visualization programme: 16 documents.

    python3 work/set-01/make_set01.py

Work order from `python3 tools/visplan.py set 1`. One curation swap was applied, per the
programme's rule that topics may be permuted between slots as long as the set's technique and
purpose multiset is untouched:

    PHY-FPP-00001  Standard Model            data-plot / compare / 2D   (was static/explain/3D)
    PHY-FPP-00003  Proton/neutron structure  static-diagram / explain / 3D  (was data-plot/2D)

The Standard Model is a table of particles - it wants a comparison plot, and nothing about it
is three-dimensional. Nucleon structure is the opposite: three quarks inside a volume is the
one idea in this set that genuinely needs the third dimension. Everything else is left as the
schedule dealt it, including the deliberately awkward ones.
"""

import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent

# ── shared helpers ──────────────────────────────────────────────────────────────
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
    """panX anchors the text box: -1 left edge at x, 0 centred on x, +1 right edge at x.

    The default is left, because that is what nearly every label here wants. Defaulting to
    0 - which reads like "no offset" - centred every title on its own left margin and put
    half of each one off the canvas.
    """
    return [paint({"color": colour}, {"style": "fill"}, {"textSize": size}),
            {"drawTextAnchored": {"text": s, "x": x, "y": y,
                                  "panX": pan_x, "panY": pan_y, "flags": 0}}]


def var(name, value, commit=True):
    return {"variable": {"name": name, "value": value, "commit": commit}}


INK = "#FF0C1220"
PANEL = "#FF141E33"
RULE = "#FF2B3A5C"
TEXT = "#FFDCE4F2"
DIM = "#FF8A99BC"
ACCENT = "#FF5B8CEE"
WARM = "#FFE8A33D"
GOOD = "#FF4FD6C9"
HOT = "#FFE8564F"

docs = {}

# ── 1. PHY-FPP-00001  Standard Model  —  data-plot / compare / 2D ──────────────
# Fermion masses span 11 orders of magnitude, so a linear axis shows one bar. The data is
# stored as log10(mass in eV) and the plot is honest about that in its axis label.
QUARKS = [("up", 6.3), ("down", 6.7), ("strange", 7.97), ("charm", 9.11),
          ("bottom", 9.62), ("top", 11.24)]
LEPTONS = [("e", 5.71), ("mu", 8.02), ("tau", 9.25),
           ("nu1", 0.0), ("nu2", 0.0), ("nu3", 0.0)]


def standard_model():
    W, H = 520, 340
    rows = QUARKS + LEPTONS
    values = [v for _, v in rows]
    left, right, top, bottom = 86.0, 500.0, 56.0, 276.0
    cmds = [paint({"color": INK}, {"style": "fill"}),
            {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}}]
    cmds += text_at("Standard Model fermions by mass", 20.0, 30.0, 17.0, TEXT)
    cmds += text_at("log10 mass / eV  -  neutrino masses are bounded, not measured",
                    20.0, 48.0, 10.5, DIM)

    cmds.append(var("span", "%.4f" % (right - left)))
    cmds.append(var("barw", "%.4f" % ((right - left) / len(rows) * 0.62)))

    # gridlines every 2 decades, drawn before the bars so bars sit on top
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    for dec in range(0, 13, 2):
        y = bottom - (bottom - top) * dec / 12.0
        cmds.append({"drawLine": {"x1": left, "y1": y, "x2": right, "y2": y}})
        cmds += text_at(str(dec), left - 10.0, y + 4.0, 10.0, DIM, pan_x=1.0)
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))

    # one loop over the array: the data-plot obligation is arrayGet inside a loop, not
    # twelve hand-written bars
    cmds.append({"loop": {"index": "i", "from": 0.0, "until": float(len(rows)),
                          "step": 1.0, "commands": [
        var("m", "arrayGet(@mass, @i)"),
        var("cx", "%.4f + (@i + 0.5) * @span / %d" % (left, len(rows))),
        var("h", "(@m / 12.0) * %.4f" % (bottom - top)),
        paint({"color": ACCENT}, {"style": "fill"},
              {"alpha": "clamp(0.35, 1.0, @m)"}),
        {"drawRoundRect": {"left": "@cx - @barw / 2", "top": "%.1f - @h" % bottom,
                           "right": "@cx + @barw / 2", "bottom": bottom,
                           "rx": 2.0, "ry": 2.0}},
    ]}})

    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.4}))
    cmds.append({"drawLine": {"x1": left, "y1": bottom, "x2": right, "y2": bottom}})

    # labels: literal text, because the dialect has no data-driven text composition
    step = (right - left) / len(rows)
    for i, (name, _) in enumerate(rows):
        cmds += text_at(name, left + (i + 0.5) * step, bottom + 16.0, 10.0, DIM, pan_x=0.0)
    cmds += text_at("quarks", left + step * 3, bottom + 38.0, 11.5, WARM, pan_x=0.0)
    cmds += text_at("leptons", left + step * 9, bottom + 38.0, 11.5, GOOD, pan_x=0.0)
    cmds += text_at("the three neutrinos sit below this axis entirely",
                    left + step * 9, bottom + 56.0, 9.5, DIM)
    return {"header": header(W, H, "Standard Model fermions compared by mass on a log axis, "
                                   "quarks against leptons"),
            "resources": {"floatArrays": [{"mass": values}]},
            "root": canvas(cmds)}


docs["PHY-FPP-00001"] = standard_model()


# ── 2. PHY-FPP-00002  Quarks and gluons  —  annotated-layout / explore / 2D ────
# No canvas at all: the obligation here is the layout subsystem, so the structure is
# containers and text components, and a flow that reflows the six flavour cards.
def quarks_and_gluons():
    W, H = 420, 420

    def card(name, charge, colour):
        return {"type": "box",
                "modifiers": [{"width": 118}, {"height": 76}, {"padding": 6},
                              {"background": colour}],
                "children": [{"type": "column",
                              "modifiers": [{"padding": 8}],
                              "children": [
                                  {"type": "text", "value": name,
                                   "modifiers": [], "fontSize": 17.0,
                                   "color": "#FF0C1220"},
                                  {"type": "spacer", "modifiers": [{"height": 4}]},
                                  {"type": "text", "value": charge,
                                   "modifiers": [], "fontSize": 11.0,
                                   "color": "#FF18243C"}]}]}

    flavours = [("up", "+2/3", "#FF8FB4F2"), ("down", "-1/3", "#FF7FA8EC"),
                ("charm", "+2/3", "#FFF0BD6A"), ("strange", "-1/3", "#FFE3A94E"),
                ("top", "+2/3", "#FFF28F86"), ("bottom", "-1/3", "#FFE87B70")]

    return {
        "header": header(W, H, "The six quark flavours as a reflowing card layout, with "
                               "their electric charges and a note on gluon colour"),
        "root": {"type": "column",
                 "modifiers": ["fillMaxSize", {"background": INK}, {"padding": 16}],
                 "children": [
                     {"type": "text", "value": "Quarks and gluons",
                      "modifiers": [], "fontSize": 20.0, "color": TEXT},
                     {"type": "spacer", "modifiers": [{"height": 4}]},
                     {"type": "text", "value": "six flavours, three colour charges",
                      "modifiers": [], "fontSize": 11.5, "color": DIM},
                     {"type": "spacer", "modifiers": [{"height": 14}]},
                     {"type": "flow",
                      "modifiers": [{"width": 388}],
                      "children": [card(n, c, col) for n, c, col in flavours]},
                     {"type": "spacer", "modifiers": [{"height": 16}]},
                     {"type": "row",
                      "modifiers": [{"width": 388}, {"padding": 10},
                                    {"background": PANEL}],
                      "children": [
                          {"type": "box",
                           "modifiers": [{"width": 10}, {"height": 10},
                                         {"background": GOOD}]},
                          {"type": "spacer", "modifiers": [{"width": 10}]},
                          {"type": "text",
                           "value": "gluons carry colour and bind them",
                           "modifiers": [], "fontSize": 12.0, "color": TEXT}]},
                 ]},
    }


docs["PHY-FPP-00002"] = quarks_and_gluons()


# ── 3. PHY-FPP-00003  Proton structure  —  static-diagram / explain / 3D ───────
# The one document in the set that earns the third dimension: three quarks occupying a
# volume reads as three overlapping discs in 2D and as a nucleon in 3D.
#
# Each quark carries a wireframe halo - its colour-charge cloud - and the three are joined
# by gluon bonds drawn as beads on a standing wave. The beads vibrate because the bond is
# not a stick: the strong force is carried by a field that is never still, and a frozen line
# between two balls says the opposite. The vibration is a time expression per bead, so the
# document also exercises expression-animation beyond its assigned static-diagram slot.
def proton_structure():
    W, H = 420, 420
    cmds = [paint({"color": INK}, {"style": "fill"}),
            {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}},
            {"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.85, "aspect": 1.0,
                          "near": 0.1, "far": 60.0,
                          "eye": [1.4, 1.1, 3.4], "center": [0, 0, 0], "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.4, -0.6, -0.7], "intensity": 1.0},
                {"type": "directional", "color": "#FF5B8CEE",
                 "dir": [0.6, 0.3, 0.5], "intensity": 0.35}]}},
            ]

    quarks = [(0.46, 0.30, 0.18, "#FF8FB4F2", "#FF5E86C4"),      # up
              (-0.44, 0.16, -0.30, "#FF8FB4F2", "#FF5E86C4"),    # up
              (0.02, -0.46, 0.26, "#FFF0BD6A", "#FFC08F3E")]     # down

    # gluon bonds first, so the quark bodies draw over the bead ends
    BEADS, AMP, OMEGA = 6, 0.085, 6.5
    mid = 20
    for bi, (ia, ib) in enumerate([(0, 1), (1, 2), (2, 0)]):
        ax, ay, az = quarks[ia][:3]
        bx, by, bz = quarks[ib][:3]
        dx, dy, dz = bx - ax, by - ay, bz - az
        ln = math.sqrt(dx * dx + dy * dy + dz * dz)
        ux, uy, uz = dx / ln, dy / ln, dz / ln
        # any vector perpendicular to the bond: cross with whichever axis is least aligned
        rx, ry, rz = (0.0, 1.0, 0.0) if abs(uy) < 0.9 else (1.0, 0.0, 0.0)
        px_, py_, pz_ = (uy * rz - uz * ry, uz * rx - ux * rz, ux * ry - uy * rx)
        pl = math.sqrt(px_ * px_ + py_ * py_ + pz_ * pz_)
        px_, py_, pz_ = px_ / pl, py_ / pl, pz_ / pl

        for k in range(1, BEADS + 1):
            t = k / (BEADS + 1)
            # sin(pi t) pins the wave at both quarks, so the bond looks anchored rather
            # than sliding - a standing wave, not a travelling one
            env = math.sin(math.pi * t) * AMP
            bxp, byp, bzp = ax + dx * t, ay + dy * t, az + dz * t
            phase = bi * 2.1 + t * 4.0
            mid += 1
            cmds += [{"meshPrimitive3D": {"id": mid, "primitive": "sphere",
                                          "segments": 8, "radius": 0.045,
                                          "center": [0, 0, 0]}},
                     {"matrix3D": {"op": "identity"}},
                     {"matrix3D": {"op": "translate",
                                   "x": "%.4f + %.4f * sin(continuousSec() * %.2f + %.3f)"
                                        % (bxp, px_ * env, OMEGA, phase),
                                   "y": "%.4f + %.4f * sin(continuousSec() * %.2f + %.3f)"
                                        % (byp, py_ * env, OMEGA, phase),
                                   "z": "%.4f + %.4f * sin(continuousSec() * %.2f + %.3f)"
                                        % (bzp, pz_ * env, OMEGA, phase)}},
                     paint({"color": "#FF6FD4C8"}, {"style": "fill"}),
                     {"drawMesh3D": {"mesh": mid, "mode": "software-smooth"}}]

    # halo first, then the quark inside it
    for qi, (x, y, z, colour, halo) in enumerate(quarks):
        cmds += [{"meshPrimitive3D": {"id": 5 + qi, "primitive": "sphere", "segments": 14,
                                      "radius": 0.22, "center": [0, 0, 0]}},
                 {"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "translate", "x": x, "y": y, "z": z}},
                 paint({"color": halo}, {"style": "stroke"}, {"width": 1.0}),
                 {"drawMesh3D": {"mesh": 5 + qi, "mode": "software-smooth",
                                 "wireframe": True}},
                 {"meshPrimitive3D": {"id": 2 + qi, "primitive": "sphere", "segments": 20,
                                      "radius": 0.13, "center": [0, 0, 0]}},
                 {"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "translate", "x": x, "y": y, "z": z}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": 2 + qi, "mode": "software-smooth"}}]

    # The confining volume goes LAST. A wireframe mesh still writes depth across its whole
    # triangles, not just along the lines it draws, so a shell drawn first silently occludes
    # everything inside it - it cost 62% of the quark pixels (256 against 678) and read as
    # "nothing is rendering". Drawn last, its lines cross in front and the contents survive.
    cmds += [{"meshPrimitive3D": {"id": 1, "primitive": "sphere", "segments": 28,
                                  "radius": 1.15, "center": [0, 0, 0]}},
             {"matrix3D": {"op": "identity"}},
             paint({"color": "#FF2E4976"}, {"style": "stroke"}, {"width": 1.0}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth", "wireframe": True}}]

    cmds += text_at("Proton", 24.0, 34.0, 19.0, TEXT)
    cmds += text_at("two up quarks and one down, bound by gluons",
                    24.0, 54.0, 11.0, DIM)
    cmds += text_at("u", 268.0, 150.0, 15.0, "#FFBCD2FA", pan_x=0.0)
    cmds += text_at("u", 128.0, 196.0, 15.0, "#FFBCD2FA", pan_x=0.0)
    cmds += text_at("d", 214.0, 286.0, 15.0, "#FFF6D49A", pan_x=0.0)
    cmds += text_at("wireframe halo = colour charge", 24.0, 376.0, 10.0, "#FF7E9AC6")
    cmds += text_at("beads = gluon field, vibrating as a standing wave",
                    24.0, 392.0, 10.0, GOOD)
    cmds += text_at("~10^-15 m", 24.0, 408.0, 10.0, DIM)
    return {"header": header(W, H, "Three quarks inside a proton, each with a colour-charge "
                                   "halo, joined by vibrating gluon bonds"),
            "root": canvas(cmds)}


docs["PHY-FPP-00003"] = proton_structure()


# ── 4. BIO-MB-00001  DNA  —  path-form / demonstrate / 2D ─────────────────────
# Two backbones as real paths built point by point in a loop, not as a run of line draws:
# the obligation is the path subsystem.
def dna():
    W, H = 360, 440
    cx, top, bot = 180.0, 50.0, 410.0
    amp, turns = 62.0, 2.6
    cmds = [paint({"color": INK}, {"style": "fill"}),
            {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}}]
    cmds += text_at("DNA", 20.0, 32.0, 19.0, TEXT)

    N = 60
    for strand, (phase, colour) in enumerate([(0.0, ACCENT), (math.pi, "#FF6FD4C8")]):
        pid = "back%d" % strand
        y0 = top
        x0 = cx + amp * math.sin(phase)
        cmds.append({"pathCreate": {"id": pid, "x": x0, "y": y0}})
        for i in range(1, N + 1):
            t = i / N
            y = top + (bot - top) * t
            x = cx + amp * math.sin(phase + turns * 2 * math.pi * t)
            cmds.append({"pathAppendLineTo": {"path": pid, "x": round(x, 2),
                                              "y": round(y, 2)}})
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 5.0},
                          {"strokeCap": "round"}))
        cmds.append({"drawPath": {"path": pid}})

    # base pairs: a rung wherever the two backbones are far apart enough to show one
    for i in range(0, N + 1, 4):
        t = i / N
        y = top + (bot - top) * t
        xa = cx + amp * math.sin(turns * 2 * math.pi * t)
        xb = cx + amp * math.sin(math.pi + turns * 2 * math.pi * t)
        if abs(xa - xb) < 22:
            continue
        cmds.append(paint({"color": "#FF9FB0D4"}, {"style": "stroke"}, {"width": 2.0},
                          {"strokeCap": "round"}))
        cmds.append({"drawLine": {"x1": round(xa, 2), "y1": round(y, 2),
                                  "x2": round(xb, 2), "y2": round(y, 2)}})
    cmds += text_at("sugar-phosphate backbones, antiparallel", 20.0, 52.0, 11.0, DIM)
    cmds += text_at("rungs are base pairs", 20.0, 428.0, 10.0, DIM)
    return {"header": header(W, H, "A DNA double helix built as two stroked paths with base "
                                   "pairs between them"),
            "root": canvas(cmds)}


docs["BIO-MB-00001"] = dna()


# ── 5. BIO-MB-00002  RNA  —  expression-animation / simulate / 2D ─────────────
# Single-stranded, and moving: the strand's shape is a function of continuousSec, so the
# motion is computed in the document rather than baked into frames.
def rna():
    W, H = 420, 300
    cmds = [paint({"color": INK}, {"style": "fill"}),
            {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}}]
    cmds += text_at("RNA", 20.0, 32.0, 19.0, TEXT)
    cmds += text_at("single strand, flexing - shape is a function of time",
                    20.0, 52.0, 11.0, DIM)

    cmds.append(var("ph", "continuousSec() * 1.1"))
    N = 26
    for i in range(N):
        u = i / (N - 1)
        x = 40.0 + u * 340.0
        cmds.append(var("y%d" % i,
                        "170 + sin(@ph + %.4f) * %.2f" % (u * 5.2, 26 + 16 * math.sin(u * 3.1))))
        colour = ["#FF5B8CEE", "#FF4FD6C9", "#FFE8A33D", "#FFE8564F"][i % 4]
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": x, "cy": "@y%d" % i, "radius": 7.0}})
        if i:
            xp = 40.0 + (i - 1) / (N - 1) * 340.0
            cmds.append(paint({"color": "#FF55658A"}, {"style": "stroke"}, {"width": 2.5}))
            cmds.append({"drawLine": {"x1": xp, "y1": "@y%d" % (i - 1),
                                      "x2": x, "y2": "@y%d" % i}})
    cmds += text_at("A  U  G  C", 20.0, 282.0, 11.0, DIM)
    return {"header": header(W, H, "A single RNA strand flexing, with each base position "
                                   "driven by a time expression"),
            "root": canvas(cmds)}


docs["BIO-MB-00002"] = rna()


# ── 6. BIO-MB-00003  DNA replication  —  particle-system / analyze / 3D ───────
# Two subsystems in one document, which is the point of the slot: a 3D fork built from
# meshes, and a particle pool of free nucleotides drifting toward it.
def dna_replication():
    W, H = 440, 440
    cmds = [paint({"color": INK}, {"style": "fill"}),
            {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}},
            {"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.9, "aspect": 1.0,
                          "near": 0.1, "far": 60.0,
                          "eye": [0.4, 0.8, 4.2], "center": [0, 0, 0], "up": [0, 1, 0]}},
            {"lights3D": {"lights": [{"type": "directional", "color": "#FFFFFFFF",
                                      "dir": [-0.4, -0.5, -0.75], "intensity": 1.0}]}}]

    # the parent duplex splitting: spheres along two diverging curves
    mid = 10
    for i in range(14):
        t = i / 13.0
        split = max(0.0, t - 0.45) * 2.2          # strands separate past the fork
        for sgn, colour in ((1, "#FF8FB4F2"), (-1, "#FF6FD4C8")):
            y = 1.25 - t * 2.5
            x = sgn * (0.16 + split * 0.72)
            z = math.sin(t * 6.0) * 0.18 * (1.0 - split)
            mid += 1
            cmds += [{"meshPrimitive3D": {"id": mid, "primitive": "sphere",
                                          "segments": 12, "radius": 0.115,
                                          "center": [0, 0, 0]}},
                     {"matrix3D": {"op": "identity"}},
                     {"matrix3D": {"op": "translate", "x": round(x, 3),
                                   "y": round(y, 3), "z": round(z, 3)}},
                     paint({"color": colour}, {"style": "fill"}),
                     {"drawMesh3D": {"mesh": mid, "mode": "software-smooth"}}]

    # free nucleotide pool, in screen space over the scene
    cmds += [{"createParticles": {
                 "id": "pool",
                 "variables": ["px", "py", "vx", "vy", "sz"],
                 "initialValues": ["rand() * 440", "rand() * 440",
                                   "0.3 + rand() * 0.9", "0.2 + rand() * 0.7",
                                   "1.6 + rand() * 2.2"],
                 "count": 90}},
             {"particlesLoop": {
                 "system": "@pool",
                 "equations": [
                     "(px + vx * sin(py * 0.02 + animationTime) + 440) % 440",
                     "(py + vy) % 440",
                     "vx", "vy", "sz"],
                 "commands": [
                     paint({"color": "#FFBFD0EE"}, {"style": "fill"}, {"alpha": 0.5}),
                     {"drawCircle": {"cx": "px", "cy": "py", "radius": "sz"}}]}}]

    cmds += text_at("DNA replication", 20.0, 34.0, 19.0, TEXT)
    cmds += text_at("fork opening, free nucleotides in solution", 20.0, 54.0, 11.0, DIM)
    cmds += text_at("90 nucleotides in the pool", 20.0, 404.0, 10.5, DIM)
    cmds += text_at("28 bases on the parent duplex", 20.0, 420.0, 10.5, DIM)
    return {"header": header(W, H, "A replication fork in 3D with a particle pool of free "
                                   "nucleotides drifting around it"),
            "root": canvas(cmds)}


docs["BIO-MB-00003"] = dna_replication()


# ── 7. BIO-MB-00004  Transcription  —  interactive / explain / 2D ─────────────
# Drag to move the polymerase along the gene. The readout is a touch expression, so the
# document responds without a host.
def transcription():
    W, H = 460, 300
    left, right, y = 40.0, 420.0, 150.0
    cmds = [paint({"color": INK}, {"style": "fill"}),
            {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}}]
    cmds += text_at("Transcription", 20.0, 32.0, 19.0, TEXT)
    cmds += text_at("drag left or right to move the polymerase", 20.0, 52.0, 11.0, DIM)

    cmds.append({"touchExpression": {"name": "drag", "defaultValue": 120.0,
                                     "min": left, "max": right,
                                     "stopMode": "gently", "expression": "touchX()"}})
    cmds.append(var("pos", "clamp(%.1f, %.1f, @drag)" % (left, right)))

    # template strand
    cmds.append(paint({"color": "#FF2B3A5C"}, {"style": "stroke"}, {"width": 9.0},
                      {"strokeCap": "round"}))
    cmds.append({"drawLine": {"x1": left, "y1": y, "x2": right, "y2": y}})
    # transcribed portion, up to the polymerase
    cmds.append(paint({"color": GOOD}, {"style": "stroke"}, {"width": 9.0},
                      {"strokeCap": "round"}))
    cmds.append({"drawLine": {"x1": left, "y1": y, "x2": "@pos", "y2": y}})

    # the growing mRNA transcript, below and trailing
    cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 4.0},
                      {"strokeCap": "round"}))
    cmds.append({"drawLine": {"x1": left, "y1": y + 46.0, "x2": "@pos", "y2": y + 46.0}})

    # polymerase
    cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
    cmds.append({"drawRoundRect": {"left": "@pos - 17", "top": y - 24.0,
                                   "right": "@pos + 17", "bottom": y + 24.0,
                                   "rx": 8.0, "ry": 8.0}})
    cmds.append(paint({"color": INK}, {"style": "fill"}, {"textSize": 11.0}))
    cmds.append({"drawTextAnchored": {"text": "pol", "x": "@pos", "y": y + 4.0,
                                      "panX": 0.0, "panY": 0.0, "flags": 0}})

    # readout: how far along, as a live number
    cmds.append({"variable": {"name": "pct",
                              "value": {"type": "textFromFloat",
                                        "value": "(@pos - %.1f) / %.1f * 100"
                                                 % (left, right - left),
                                        "whole": 3, "decimal": 0}}})
    cmds.append(paint({"color": TEXT}, {"style": "fill"}, {"textSize": 15.0}))
    cmds.append({"drawTextAnchored": {"text": "@pct", "x": 420.0, "y": 252.0,
                                      "panX": 1.0, "panY": 0.0, "flags": 0}})
    cmds += text_at("% of gene transcribed", 420.0, 272.0, 10.0, DIM, pan_x=1.0)
    cmds += text_at("template strand", 40.0, 118.0, 10.0, DIM)
    cmds += text_at("mRNA transcript", 40.0, 212.0, 10.0, WARM)
    return {"header": header(W, H, "Drag a polymerase along a gene; the transcript grows "
                                   "behind it and the percentage transcribed updates"),
            "root": canvas(cmds)}


docs["BIO-MB-00004"] = transcription()


# ── 8. MTH-AN-00001  Number line  —  raster-and-text / explore / 2D ───────────
# The raster-and-text slot: this is a typography document. Tick labels at three sizes, a
# text-heavy axis, and nothing else carrying the meaning.
def number_line():
    W, H = 560, 220
    left, right, y = 40.0, 520.0, 120.0
    cmds = [paint({"color": INK}, {"style": "fill"}),
            {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}}]
    cmds += text_at("The number line", 20.0, 32.0, 19.0, TEXT)
    cmds += text_at("integers, halves, and one irrational", 20.0, 52.0, 11.0, DIM)

    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.6},
                      {"strokeCap": "round"}))
    cmds.append({"drawLine": {"x1": left, "y1": y, "x2": right, "y2": y}})

    span = right - left
    for n in range(-5, 6):
        x = left + (n + 5) / 10.0 * span
        major = n % 5 == 0
        cmds.append(paint({"color": TEXT if major else RULE}, {"style": "stroke"},
                          {"width": 2.0 if major else 1.0}))
        cmds.append({"drawLine": {"x1": x, "y1": y - (12.0 if major else 7.0),
                                  "x2": x, "y2": y + (12.0 if major else 7.0)}})
        cmds += text_at(str(n), x, y + 32.0, 15.0 if major else 11.5,
                        TEXT if major else DIM, pan_x=0.0)
        if n < 5:
            xh = left + (n + 5.5) / 10.0 * span
            cmds.append(paint({"color": "#FF22304E"}, {"style": "stroke"}, {"width": 1.0}))
            cmds.append({"drawLine": {"x1": xh, "y1": y - 4.0, "x2": xh, "y2": y + 4.0}})

    # pi, marked where it actually falls
    xpi = left + (math.pi + 5) / 10.0 * span
    cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 2.0}))
    cmds.append({"drawLine": {"x1": xpi, "y1": y - 26.0, "x2": xpi, "y2": y + 18.0}})
    cmds += text_at("pi", xpi, y - 34.0, 14.0, WARM, pan_x=0.0)
    cmds += text_at("3.14159...", xpi, y - 50.0, 10.0, DIM, pan_x=0.0)
    cmds += text_at("halves are the short ticks", 40.0, 196.0, 10.0, DIM)
    return {"header": header(W, H, "A labelled number line from -5 to 5 with halves marked "
                                   "and pi placed where it falls"),
            "root": canvas(cmds)}


docs["MTH-AN-00001"] = number_line()


# ── 9. CSC-ALGO-00001  Sorting  —  static-diagram / explore / 2D ──────────────
# One frozen frame per pass of an insertion sort, so the whole algorithm is visible at once
# rather than animated and gone.
def sorting():
    W, H = 520, 400
    data = [5, 2, 9, 1, 7, 3, 8, 4]
    passes = [list(data)]
    a = list(data)
    for i in range(1, len(a)):
        k, j = a[i], i - 1
        while j >= 0 and a[j] > k:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = k
        passes.append(list(a))

    cmds = [paint({"color": INK}, {"style": "fill"}),
            {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}}]
    cmds += text_at("Insertion sort, pass by pass", 20.0, 30.0, 18.0, TEXT)
    cmds += text_at("each row is the array after one more element is placed",
                    20.0, 48.0, 10.5, DIM)

    cell, gap, x0, y0 = 46.0, 6.0, 110.0, 70.0
    for r, row in enumerate(passes):
        y = y0 + r * (cell * 0.62 + 8.0)
        cmds += text_at("pass %d" % r if r else "start", x0 - 14.0, y + 20.0, 10.5, DIM,
                        pan_x=1.0)
        for c, v in enumerate(row):
            x = x0 + c * (cell + gap)
            placed = c <= r
            cmds.append(paint({"color": ACCENT if placed else "#FF27354F"},
                              {"style": "fill"},
                              {"alpha": 1.0 if placed else 0.75}))
            cmds.append({"drawRoundRect": {"left": x, "top": y,
                                           "right": x + cell, "bottom": y + cell * 0.62,
                                           "rx": 4.0, "ry": 4.0}})
            cmds += text_at(str(v), x + cell / 2, y + cell * 0.40,
                            14.0, INK if placed else DIM, pan_x=0.0)
    cmds += text_at("filled cells are in final order", 110.0, 384.0, 10.0, DIM)
    return {"header": header(W, H, "Insertion sort shown as one row per pass, with placed "
                                   "elements highlighted"),
            "root": canvas(cmds)}


docs["CSC-ALGO-00001"] = sorting()


# ── 10. CHM-AC-00001  Atomic structure  —  annotated-layout / compare / 2D ────
# Three atoms side by side in a row of panels, so the comparison is structural rather than
# drawn: the layout engine does the work of making them comparable.
def atomic_structure():
    W, H = 520, 300

    def atom_panel(name, protons, neutrons, electrons, colour):
        return {"type": "column",
                "modifiers": [{"width": 150}, {"padding": 12},
                              {"background": PANEL}],
                "children": [
                    {"type": "text", "value": name, "modifiers": [],
                     "fontSize": 17.0, "color": colour},
                    {"type": "spacer", "modifiers": [{"height": 10}]},
                    {"type": "row", "modifiers": [], "children": [
                        {"type": "text", "value": "p", "modifiers": [],
                         "fontSize": 12.0, "color": DIM},
                        {"type": "spacer", "modifiers": [{"width": 8}]},
                        {"type": "text", "value": protons, "modifiers": [],
                         "fontSize": 13.0, "color": TEXT}]},
                    {"type": "spacer", "modifiers": [{"height": 4}]},
                    {"type": "row", "modifiers": [], "children": [
                        {"type": "text", "value": "n", "modifiers": [],
                         "fontSize": 12.0, "color": DIM},
                        {"type": "spacer", "modifiers": [{"width": 8}]},
                        {"type": "text", "value": neutrons, "modifiers": [],
                         "fontSize": 13.0, "color": TEXT}]},
                    {"type": "spacer", "modifiers": [{"height": 4}]},
                    {"type": "row", "modifiers": [], "children": [
                        {"type": "text", "value": "e", "modifiers": [],
                         "fontSize": 12.0, "color": DIM},
                        {"type": "spacer", "modifiers": [{"width": 8}]},
                        {"type": "text", "value": electrons, "modifiers": [],
                         "fontSize": 13.0, "color": TEXT}]},
                    {"type": "spacer", "modifiers": [{"height": 10}]},
                    {"type": "box", "modifiers": [{"width": 120}, {"height": 5},
                                                  {"background": colour}]},
                ]}

    return {
        "header": header(W, H, "Hydrogen, helium and carbon compared as panels of proton, "
                               "neutron and electron counts"),
        "root": {"type": "column",
                 "modifiers": ["fillMaxSize", {"background": INK}, {"padding": 18}],
                 "children": [
                     {"type": "text", "value": "Atomic structure, three elements",
                      "modifiers": [], "fontSize": 19.0, "color": TEXT},
                     {"type": "spacer", "modifiers": [{"height": 6}]},
                     {"type": "text", "value": "same fields, side by side",
                      "modifiers": [], "fontSize": 11.0, "color": DIM},
                     {"type": "spacer", "modifiers": [{"height": 16}]},
                     {"type": "row", "modifiers": [], "children": [
                         atom_panel("Hydrogen", "1", "0", "1", "#FF8FB4F2"),
                         {"type": "spacer", "modifiers": [{"width": 12}]},
                         atom_panel("Helium", "2", "2", "2", "#FF4FD6C9"),
                         {"type": "spacer", "modifiers": [{"width": 12}]},
                         atom_panel("Carbon", "6", "6", "6", "#FFE8A33D")]},
                 ]},
    }


docs["CHM-AC-00001"] = atomic_structure()


# ── 11. EAR-GEOL-00001  Plate tectonics  —  data-plot / demonstrate / 2D ──────
# Plate speeds as a ranked plot from a float array, which is what makes "demonstrate"
# concrete: the claim is that plates move at centimetres a year, and here are the numbers.
def plate_tectonics():
    W, H = 520, 340
    plates = [("Pacific", 7.5), ("Nazca", 6.8), ("Cocos", 6.4), ("Indian", 5.4),
              ("Australian", 5.2), ("Philippine", 4.6), ("Arabian", 3.4),
              ("African", 2.2), ("S American", 1.5), ("N American", 1.1),
              ("Eurasian", 0.9), ("Antarctic", 0.6)]
    speeds = [s for _, s in plates]
    left, right, top = 120.0, 480.0, 70.0
    rowh = 20.0
    cmds = [paint({"color": INK}, {"style": "fill"}),
            {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}}]
    cmds += text_at("Plate motion", 20.0, 32.0, 19.0, TEXT)
    cmds += text_at("cm per year, ranked - the fast plates are oceanic",
                    20.0, 52.0, 11.0, DIM)
    cmds.append(var("mx", "arrayMax(@speed)"))
    cmds.append(var("scale", "%.4f / @mx" % (right - left)))

    for g in range(0, 9, 2):
        x = left + (right - left) * g / 8.0
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": x, "y1": top - 8.0,
                                  "x2": x, "y2": top + rowh * len(plates)}})
        cmds += text_at(str(g), x, top - 14.0, 10.0, DIM, pan_x=0.0)

    cmds.append({"loop": {"index": "i", "from": 0.0, "until": float(len(plates)),
                          "step": 1.0, "commands": [
        var("v", "arrayGet(@speed, @i)"),
        var("yy", "%.1f + @i * %.1f" % (top, rowh)),
        paint({"color": ACCENT}, {"style": "fill"},
              {"alpha": "clamp(0.45, 1.0, @v / @mx + 0.25)"}),
        {"drawRoundRect": {"left": left, "top": "@yy + 3",
                           "right": "%.1f + @v * @scale" % left, "bottom": "@yy + 15",
                           "rx": 3.0, "ry": 3.0}},
    ]}})

    for i, (name, s) in enumerate(plates):
        yy = top + i * rowh
        cmds += text_at(name, left - 10.0, yy + 13.0, 10.5, TEXT, pan_x=1.0)
        cmds += text_at("%.1f" % s, left + (right - left) * s / max(speeds) + 8.0,
                        yy + 13.0, 10.0, DIM)
    cmds += text_at("cm / year", right, top + rowh * len(plates) + 22.0, 10.5, DIM,
                    pan_x=1.0)
    return {"header": header(W, H, "Tectonic plate speeds in centimetres per year, ranked, "
                                   "plotted from a float array"),
            "resources": {"floatArrays": [{"speed": speeds}]},
            "root": canvas(cmds)}


docs["EAR-GEOL-00001"] = plate_tectonics()


# ── 12. ENG-ME-00001  Mechanisms  —  path-form / simulate / 2D ────────────────
# A four-bar linkage. The coupler curve is the interesting artefact, and it is a path: the
# locus is traced once at build time and stroked as one path.
def mechanism():
    W, H = 440, 380
    ax, ay = 140.0, 250.0       # crank pivot
    bx, by = 300.0, 250.0       # rocker pivot
    crank, coupler, rocker = 48.0, 150.0, 96.0
    cmds = [paint({"color": INK}, {"style": "fill"}),
            {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}}]
    cmds += text_at("Four-bar linkage", 20.0, 32.0, 19.0, TEXT)
    cmds += text_at("the traced curve is the coupler point's path", 20.0, 52.0, 11.0, DIM)

    def solve(theta):
        """Crank pin, then the coupler point by circle intersection."""
        px, py = ax + crank * math.cos(theta), ay - crank * math.sin(theta)
        dx, dy = bx - px, by - py
        d = math.hypot(dx, dy)
        if d > coupler + rocker or d < abs(coupler - rocker):
            return None
        a = (coupler * coupler - rocker * rocker + d * d) / (2 * d)
        h2 = coupler * coupler - a * a
        if h2 < 0:
            return None
        h = math.sqrt(h2)
        mx, my = px + a * dx / d, py + a * dy / d
        return (px, py), (mx - h * dy / d, my + h * dx / d)

    locus = []
    for i in range(181):
        r = solve(i / 180.0 * 2 * math.pi)
        if r:
            locus.append(r[1])

    if locus:
        cmds.append({"pathCreate": {"id": "locus", "x": round(locus[0][0], 2),
                                    "y": round(locus[0][1], 2)}})
        for x, y in locus[1:]:
            cmds.append({"pathAppendLineTo": {"path": "locus", "x": round(x, 2),
                                              "y": round(y, 2)}})
        cmds.append({"pathAppendClose": {"path": "locus"}})
        cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 2.0}))
        cmds.append({"drawPath": {"path": "locus"}})

    # the linkage frozen at one angle, over the curve
    r = solve(0.9)
    if r:
        (px, py), (cxp, cyp) = r
        for (x1, y1, x2, y2, w, col) in [
                (ax, ay, px, py, 6.0, ACCENT),
                (px, py, cxp, cyp, 5.0, "#FF9FB0D4"),
                (bx, by, cxp, cyp, 5.0, GOOD),
                (ax, ay, bx, by, 3.0, RULE)]:
            cmds.append(paint({"color": col}, {"style": "stroke"}, {"width": w},
                              {"strokeCap": "round"}))
            cmds.append({"drawLine": {"x1": round(x1, 2), "y1": round(y1, 2),
                                      "x2": round(x2, 2), "y2": round(y2, 2)}})
        for x, y, rad, col in [(ax, ay, 7.0, TEXT), (bx, by, 7.0, TEXT),
                               (px, py, 5.0, ACCENT), (cxp, cyp, 6.0, WARM)]:
            cmds.append(paint({"color": col}, {"style": "fill"}))
            cmds.append({"drawCircle": {"cx": round(x, 2), "cy": round(y, 2),
                                        "radius": rad}})
        cmds += text_at("crank", ax - 4.0, ay + 24.0, 10.0, ACCENT, pan_x=1.0)
        cmds += text_at("rocker", bx + 6.0, by + 24.0, 10.0, GOOD)
        cmds += text_at("coupler point", round(cxp, 1) + 10.0, round(cyp, 1) - 8.0,
                        10.0, WARM)
    cmds += text_at("ground link", (ax + bx) / 2, ay + 40.0, 10.0, DIM, pan_x=0.0)
    return {"header": header(W, H, "A four-bar linkage with its coupler curve traced as a "
                                   "closed path"),
            "root": canvas(cmds)}


docs["ENG-ME-00001"] = mechanism()


def _box(verts, normals, uv, idx, lo, hi, wind_flip=True):
    """Append an axis-aligned box as 12 triangles, with per-face normals.

    Used for axis rods and ticks. Winding follows the same rule the surface needed
    (finding F-008): the engine culls the opposite order from the one that looks natural,
    and a wrongly wound box is invisible rather than inside-out.
    """
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    faces = [
        ((0, 0, 1),  [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]),
        ((0, 0, -1), [(x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)]),
        ((1, 0, 0),  [(x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)]),
        ((-1, 0, 0), [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)]),
        ((0, 1, 0),  [(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)]),
        ((0, -1, 0), [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]),
    ]
    for n, quad in faces:
        base = len(verts) // 3
        for (px, py, pz) in quad:
            verts += [px, py, pz]
            normals += list(n)
            uv += [0.0, 0.0]
        if wind_flip:
            idx += [base, base + 2, base + 1, base, base + 3, base + 2]
        else:
            idx += [base, base + 1, base + 2, base, base + 2, base + 3]


def _axis_mesh(mesh_id, lo, hi, ticks, tick_axis, rod=0.032, tick_len=0.11):
    """One axis rod plus its ticks, as a single mesh ready for defineMesh3D."""
    verts, normals, uv, idx = [], [], [], []
    _box(verts, normals, uv, idx, lo, hi)
    for t in ticks:
        if tick_axis == "x":
            _box(verts, normals, uv, idx,
                 (t - rod, lo[1] - tick_len, lo[2] - rod),
                 (t + rod, lo[1] + rod, lo[2] + rod))
        elif tick_axis == "z":
            _box(verts, normals, uv, idx,
                 (lo[0] - rod, lo[1] - tick_len, t - rod),
                 (lo[0] + rod, lo[1] + rod, t + rod))
        else:                                   # y
            _box(verts, normals, uv, idx,
                 (lo[0] - tick_len, t - rod, lo[2] - rod),
                 (lo[0] + rod, t + rod, lo[2] + rod))
    return {"defineMesh3D": {"id": mesh_id,
                             "verts": [round(x, 5) for x in verts],
                             "normals": [round(x, 5) for x in normals],
                             "uv": uv, "indices": idx}}


# ── 13. ECO-MICR-00001  Supply and demand  —  expression-animation / analyze / 3D
# Quantity demanded as a function of price and income, as an actual surface.
#
# The first version stacked 81 cube primitives, one per grid point, and it read as a wall of
# blocks rather than a surface - you could not see the shape, which was the only thing it had
# to convey. 81 primitives also cost 12 KB against the Java writer's 2.7 KB (finding F-002).
#
# A surface wants ONE mesh: `defineMesh3D` with computed vertices, the way
# surface-plot3d builds its. Normals are analytic here rather than averaged from
# neighbours - the function is differentiable, so there is no reason to approximate them.
def supply_demand():
    W, H = 460, 440
    N = 17                      # 289 vertices, 512 triangles
    SCALE = 1.25                # quantity -> world height

    def q(u, v):
        """Quantity demanded: falls with price u, rises with income v.

        Constant-elasticity rather than linear. The linear version was honest - the label
        said "demand is linear in both" - but a plane is a poor advertisement for a surface
        plot, and the curvature is the thing a reader is meant to see.
        """
        return (1.0 - u) ** 1.7 * (0.28 + 0.72 * v ** 1.35)

    verts, normals, uv, indices = [], [], [], []
    for i in range(N):
        for j in range(N):
            u, v = i / (N - 1), j / (N - 1)
            verts += [2.0 * u - 1.0, SCALE * q(u, v) - 0.42, 2.0 * v - 1.0]
            # P(u,v) = (2u-1, S*q, 2v-1);  Pu = (2, S*qu, 0),  Pv = (0, S*qv, 2)
            # Pu x Pv = (2*S*qu, -4, 2*S*qv), negated so the normal points up
            # dq/du and dq/dv for the constant-elasticity form above
            a = SCALE * (-1.7 * (1.0 - u) ** 0.7 * (0.28 + 0.72 * v ** 1.35))
            b = SCALE * ((1.0 - u) ** 1.7 * 0.72 * 1.35 * v ** 0.35) if v > 0 else 0.0
            nx, ny, nz = -2.0 * a, 4.0, -2.0 * b
            ln = math.sqrt(nx * nx + ny * ny + nz * nz)
            normals += [nx / ln, ny / ln, nz / ln]
            uv += [u, v]
    # Winding matters and nothing warns you. Backface culling is decided by triangle
    # winding alone - normals make no difference to visibility - so the other order renders
    # a completely invisible mesh with no error from the converter or the player. Measured:
    # 0 surface pixels one way, 11,395 the other. See finding F-008.
    for i in range(N - 1):
        for j in range(N - 1):
            a = i * N + j
            indices += [a, a + N + 1, a + N, a, a + 1, a + N + 1]

    cmds = [paint({"color": INK}, {"style": "fill"}),
            {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}},
            {"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 1.05, "aspect": 1.0,
                          "near": 0.1, "far": 60.0,
                          "eye": [2.1, 1.5, 2.5], "center": [0, 0.05, 0],
                          "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.45, -0.72, -0.52], "intensity": 1.0},
                {"type": "directional", "color": "#FF4FD6C9",
                 "dir": [0.6, 0.25, 0.45], "intensity": 0.32}]}},
            {"defineMesh3D": {"id": 1,
                              "verts": [round(x, 5) for x in verts],
                              "normals": [round(x, 5) for x in normals],
                              "uv": [round(x, 5) for x in uv],
                              "indices": indices}}]

    # Axes, as real geometry rather than screen-space lines, so they rotate WITH the
    # surface and keep meaning which way is which. Three separate meshes because a mesh
    # takes one paint, and the whole point is that each axis carries its own colour.
    FLOOR = -0.42                       # y where quantity is zero
    TOP = SCALE * 1.0 + FLOOR           # y at maximum quantity
    R = 0.032
    cmds.append(_axis_mesh(2, (-1.0, FLOOR - R, -1.0 - R), (1.0, FLOOR + R, -1.0 + R),
                           [-0.5, 0.0, 0.5, 1.0], "x"))                 # price
    cmds.append(_axis_mesh(3, (-1.0 - R, FLOOR - R, -1.0), (-1.0 + R, FLOOR + R, 1.0),
                           [-0.5, 0.0, 0.5, 1.0], "z"))                 # income
    cmds.append(_axis_mesh(4, (-1.0 - R, FLOOR, -1.0 - R), (-1.0 + R, TOP, -1.0 + R),
                           [FLOOR + (TOP - FLOOR) * f for f in (0.25, 0.5, 0.75, 1.0)],
                           "y"))                                        # quantity

    # the animation obligation, now one rotation for the whole surface instead of 81
    cmds.append(var("spin", "sin(continuousSec() * 0.3) * 0.55"))
    cmds += [{"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": "#FF3E7BD4"}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}},
             # the same mesh again as wireframe: on a smooth surface the grid is what lets
             # you read the curvature, and read a value off it
             paint({"color": "#FF9FC2F5"}, {"style": "stroke"}, {"width": 1.0}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth", "wireframe": True}}]

    # same identity+rotate, so the axes stay glued to the surface through the oscillation
    for mesh_id, colour in ((2, WARM), (3, GOOD), (4, "#FFBFCBE4")):
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mesh_id, "mode": "software-flat"}}]

    cmds += text_at("Quantity demanded", 20.0, 32.0, 19.0, TEXT)
    cmds += text_at("a surface over price and income, turning to show its shape",
                    20.0, 52.0, 11.0, DIM)
    cmds += text_at("price", 20.0, 372.0, 12.0, WARM)
    cmds += text_at("income", 86.0, 372.0, 12.0, GOOD)
    cmds += text_at("quantity", 168.0, 372.0, 12.0, "#FFBFCBE4")
    cmds += text_at("axes turn with the surface; ticks mark quarters",
                    20.0, 394.0, 10.0, DIM)
    cmds += text_at("the curve is constant elasticity, not a straight line",
                    20.0, 412.0, 10.0, DIM)
    cmds += text_at("17 x 17 grid, 512 triangles, plus three axis meshes",
                    20.0, 430.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "Quantity demanded as a 3D surface over price and "
                                   "income, built as a single computed mesh"),
            "root": canvas(cmds)}


docs["ECO-MICR-00001"] = supply_demand()


# ── 14. ECO-MICR-00002  Elasticity  —  particle-system / explain / 2D
# The awkward pairing, kept on purpose, and it needed rethinking rather than restyling.
#
# The first version scattered buyers at random and faded them by reservation price. Both
# populations looked like the same cloud, because position carried no information - the one
# thing a particle system gives you for free. Nothing about it explained elasticity.
#
# Now a buyer's HEIGHT IS THEIR RESERVATION PRICE, so the sweeping price line is a cut
# through the population and you can see who it takes. Elastic buyers are packed into a
# narrow band of willingness, so the line clears almost all of them at once; inelastic
# buyers are spread, so the same move costs a few. The share still buying is computed
# analytically alongside, because the distributions are known - that turns a visual
# impression into a number.
def elasticity():
    W, H = 480, 440
    top, bot = 92.0, 330.0          # price axis: 1.0 at the top, 0.0 at the bottom

    cmds = [paint({"color": INK}, {"style": "fill"}),
            {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}}]
    cmds += text_at("Elasticity", 20.0, 32.0, 19.0, TEXT)
    cmds += text_at("each dot is a buyer, placed at the most they will pay",
                    20.0, 52.0, 11.0, DIM)
    cmds += text_at("the line is the price; dots above it have left the market",
                    20.0, 68.0, 11.0, DIM)

    cmds.append(var("price", "0.5 + sin(continuousSec() * 0.45) * 0.44"))
    cmds.append(var("py", "%.1f - @price * %.1f" % (bot, bot - top)))

    bands = [("elastic", 0.44, 0.58, HOT, 44.0, 220.0),
             ("inelastic", 0.06, 0.96, GOOD, 254.0, 430.0)]
    for idx, (label, lo, hi, colour, x0, x1) in enumerate(bands):
        sysid = "b%d" % idx
        cmds.append({"createParticles": {
            "id": sysid,
            "variables": ["bx", "res", "jit"],
            "initialValues": ["%.1f + rand() * %.1f" % (x0, x1 - x0),
                              "%.3f + rand() * %.3f" % (lo, hi - lo),
                              "rand() * 6.283"],
            "count": 110}})
        cmds.append({"particlesLoop": {
            "system": "@" + sysid,
            "equations": ["bx + sin(jit + animationTime * 0.7) * 0.25", "res", "jit"],
            "commands": [
                # res >= price -> still buying. Inlined because a `variable` inside a
                # particle loop is a reassignment the parser refuses.
                paint({"color": colour}, {"style": "fill"},
                      {"alpha": "clamp(0.10, 0.92, (res - @price) * 14 + 0.5)"}),
                {"drawCircle": {"cx": "bx",
                                "cy": "%.1f - res * %.1f" % (bot, bot - top),
                                "radius": 3.8}}]}})

        # the share still buying, from the known uniform distribution
        cmds.append(var("sh%d" % idx,
                        "clamp(0.0, 1.0, (%.3f - @price) / %.3f)" % (hi, hi - lo)))
        barw = (x1 - x0)
        cmds.append(paint({"color": "#FF1B2740"}, {"style": "fill"}))
        cmds.append({"drawRoundRect": {"left": x0, "top": 376.0, "right": x1,
                                       "bottom": 394.0, "rx": 4.0, "ry": 4.0}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRoundRect": {"left": x0, "top": 376.0,
                                       "right": "%.1f + @sh%d * %.1f" % (x0, idx, barw),
                                       "bottom": 394.0, "rx": 4.0, "ry": 4.0}})
        cmds.append({"variable": {"name": "pc%d" % idx,
                                  "value": {"type": "textFromFloat",
                                            "value": "@sh%d * 100" % idx,
                                            "whole": 3, "decimal": 0}}})
        cmds.append(paint({"color": TEXT}, {"style": "fill"}, {"textSize": 13.0}))
        cmds.append({"drawTextAnchored": {"text": "@pc%d" % idx, "x": x1, "y": 412.0,
                                          "panX": 1.0, "panY": 0.0, "flags": 0}})
        cmds += text_at(label, x0, 364.0, 13.0, colour)
        cmds += text_at("% still buying", x0, 412.0, 10.0, DIM)
        cmds += text_at("willingness %.2f-%.2f" % (lo, hi), x0, 430.0, 9.5, "#FF5E6E95")

    # price axis and the sweeping line, drawn over both populations
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = bot - t * (bot - top)
        cmds.append({"drawLine": {"x1": 34.0, "y1": y, "x2": 440.0, "y2": y}})
        cmds += text_at("%.2f" % t, 30.0, y + 4.0, 9.0, "#FF5E6E95", pan_x=1.0)
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))

    cmds.append(paint({"color": WARM}, {"style": "stroke"}, {"width": 2.2}))
    cmds.append({"drawLine": {"x1": 34.0, "y1": "@py", "x2": 440.0, "y2": "@py"}})
    cmds.append(paint({"color": WARM}, {"style": "fill"}, {"textSize": 11.0}))
    cmds.append({"drawTextAnchored": {"text": "price", "x": 440.0, "y": "@py - 8",
                                      "panX": 1.0, "panY": 0.0, "flags": 0}})
    return {"header": header(W, H, "Two buyer populations as particles positioned by "
                                   "willingness to pay, cut by a sweeping price line"),
            "root": canvas(cmds)}


docs["ECO-MICR-00002"] = elasticity()


# ── 15. ECO-MICR-00003  Consumer behavior  —  interactive / explore / 2D ──────
# Drag the budget and watch the basket reallocate. Exploration means the reader sets the
# input, so the whole document hangs off one touch expression.
def consumer_behavior():
    W, H = 460, 360
    cmds = [paint({"color": INK}, {"style": "fill"}),
            {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}}]
    cmds += text_at("Consumer behaviour", 20.0, 32.0, 19.0, TEXT)
    cmds += text_at("drag up and down to change the budget", 20.0, 52.0, 11.0, DIM)

    cmds.append({"touchExpression": {"name": "budget", "defaultValue": 0.5,
                                     "min": 0.0, "max": 1.0,
                                     "stopMode": "gently",
                                     "expression": "1 - touchY() / 360"}})
    cmds.append(var("b", "clamp(0.0, 1.0, @budget)"))

    # Engel curves: necessities take a falling share as income rises, luxuries a rising one
    cats = [("food", "0.52 - @b * 0.26", "#FF4FD6C9"),
            ("housing", "0.30 - @b * 0.06", "#FF5B8CEE"),
            ("transport", "0.11 + @b * 0.05", "#FFE8A33D"),
            ("leisure", "0.07 + @b * 0.27", "#FFE8564F")]
    left, width, top, barh = 40.0, 380.0, 120.0, 34.0
    cmds.append(var("acc", "0"))
    for i, (name, share, colour) in enumerate(cats):
        y = top + i * (barh + 14.0)
        cmds.append(var("s%d" % i, share))
        cmds.append(paint({"color": "#FF1B2740"}, {"style": "fill"}))
        cmds.append({"drawRoundRect": {"left": left, "top": y, "right": left + width,
                                       "bottom": y + barh, "rx": 5.0, "ry": 5.0}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRoundRect": {"left": left, "top": y,
                                       "right": "%.1f + @s%d * %.1f" % (left, i, width),
                                       "bottom": y + barh, "rx": 5.0, "ry": 5.0}})
        cmds += text_at(name, left + 10.0, y + 22.0, 12.5, INK)
        cmds.append({"variable": {"name": "p%d" % i,
                                  "value": {"type": "textFromFloat",
                                            "value": "@s%d * 100" % i,
                                            "whole": 2, "decimal": 0}}})
        cmds.append(paint({"color": TEXT}, {"style": "fill"}, {"textSize": 12.0}))
        cmds.append({"drawTextAnchored": {"text": "@p%d" % i,
                                          "x": left + width - 10.0, "y": y + 22.0,
                                          "panX": 1.0, "panY": 0.0, "flags": 0}})
    cmds += text_at("share of spending, %", left, 332.0, 10.0, DIM)
    cmds += text_at("low budget", left + width, 108.0, 10.0, DIM, pan_x=1.0)
    return {"header": header(W, H, "Drag to change a household budget and watch spending "
                                   "shares reallocate across four categories"),
            "root": canvas(cmds)}


docs["ECO-MICR-00003"] = consumer_behavior()


# ── 16. ECO-MICR-00004  Competition  —  raster-and-text / compare / 2D ────────
# Four market structures as a typographic comparison table. The raster-and-text obligation
# is met by type: three weights of size, aligned columns, no bars at all.
def competition():
    W, H = 560, 340
    rows = [("Perfect competition", "many", "identical", "none", "#FF4FD6C9"),
            ("Monopolistic", "many", "differentiated", "some", "#FF5B8CEE"),
            ("Oligopoly", "few", "either", "considerable", "#FFE8A33D"),
            ("Monopoly", "one", "unique", "total", "#FFE8564F")]
    cols = [26.0, 250.0, 350.0, 480.0]
    cmds = [paint({"color": INK}, {"style": "fill"}),
            {"drawRect": {"left": 0, "top": 0, "right": W, "bottom": H}}]
    cmds += text_at("Market structures", 26.0, 36.0, 20.0, TEXT)
    cmds += text_at("the same three questions, four answers", 26.0, 56.0, 11.0, DIM)

    head_y = 96.0
    for x, h in zip(cols, ["structure", "sellers", "product", "price power"]):
        cmds += text_at(h.upper(), x, head_y, 9.5, DIM)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": 26.0, "y1": head_y + 10.0,
                              "x2": 534.0, "y2": head_y + 10.0}})

    for i, (name, sellers, product, power, colour) in enumerate(rows):
        y = head_y + 46.0 + i * 52.0
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 26.0, "top": y - 16.0,
                                  "right": 30.0, "bottom": y + 8.0}})
        cmds += text_at(name, cols[0] + 12.0, y, 15.0, TEXT)
        cmds += text_at(sellers, cols[1], y, 13.0, colour)
        cmds += text_at(product, cols[2], y, 13.0, "#FFB9C6E0")
        cmds += text_at(power, cols[3], y, 13.0, "#FFB9C6E0")
        if i < len(rows) - 1:
            cmds.append(paint({"color": "#FF1B2740"}, {"style": "stroke"}, {"width": 1.0}))
            cmds.append({"drawLine": {"x1": 26.0, "y1": y + 26.0,
                                      "x2": 534.0, "y2": y + 26.0}})
    cmds += text_at("price power rises as the number of sellers falls",
                    26.0, 324.0, 10.0, DIM)
    return {"header": header(W, H, "Four market structures compared as a typographic table "
                                   "of sellers, product and price power"),
            "root": canvas(cmds)}


docs["ECO-MICR-00004"] = competition()


# ── write ───────────────────────────────────────────────────────────────────────
def main():
    for doc_id, doc in docs.items():
        p = OUT / ("%s.json" % doc_id)
        p.write_text(json.dumps(doc, indent=1) + "\n")
    print("  wrote %d documents to %s" % (len(docs), OUT.name))
    for doc_id in docs:
        print("    %s.json" % doc_id)


if __name__ == "__main__":
    main()
