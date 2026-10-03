#!/usr/bin/env python3
"""Build set 2 of the visualization programme: 16 documents.

    python3 work/set-02/make_set02.py

Work order from `python3 tools/visplan.py set 2`. One curation swap, under the rule that
topics may be permuted between slots as long as the set's technique and purpose multiset is
untouched:

    BIO-CB-00008  Organelles  raster-and-text / simulate / 3D   (was demonstrate / 2D)
    ECO-MACR-00007 Inflation  raster-and-text / demonstrate / 2D (was simulate / 3D)

Inflation is a time series and nothing about it is volumetric; text does not exist in the 3D
pipeline at all, so "raster-and-text in 3D" could only have meant a texture. A cell is
genuinely a volume and `texture3D` is in that subsystem's command list, so the swap puts the
3D texture work where it belongs and leaves inflation as the typographic document it wants
to be.

Everything the set-1 build cost a round to discover is applied here from the start: text
components key on `value`, `resources` sits at document top level, paint uses the `ops`
array, panX -1 is left-aligned, mesh triangles wind [a, a+N+1, a+N], a containing wireframe
is drawn LAST because it writes depth across whole faces, and no `variable` appears inside a
`particlesLoop`.
"""

import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent


# ── shared helpers (kept in-file so each document's src/ copy runs standalone) ──
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


# ── 1. PHY-FPP-00004  Particle interactions — static-diagram / compare / 2D ────
# Four forces, four columns, one shared log axis. The comparison is the whole document, so
# everything that is not comparable across all four is left out.
def interactions():
    W, H = 540, 360
    forces = [("Strong", 38.0, "10^-15 m", "gluon", HOT),
              ("Electromagnetic", 36.0, "infinite", "photon", WARM),
              ("Weak", 25.0, "10^-18 m", "W, Z", ACCENT),
              ("Gravity", 0.0, "infinite", "graviton?", GOOD)]
    cmds = []
    left, right, top, barh = 150.0, 500.0, 92.0, 30.0
    for g in range(0, 41, 10):
        x = left + (right - left) * g / 40.0
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": x, "y1": top - 10.0,
                                  "x2": x, "y2": top + len(forces) * 62.0}})
        cmds += text_at("10^%d" % g, x, top - 18.0, 9.5, DIM, pan_x=0.0)

    for i, (name, strength, rng, carrier, colour) in enumerate(forces):
        y = top + i * 62.0
        w = (right - left) * strength / 40.0
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRoundRect": {"left": left, "top": y,
                                       "right": left + max(w, 3.0), "bottom": y + barh,
                                       "rx": 4.0, "ry": 4.0}})
        cmds += text_at(name, left - 12.0, y + 20.0, 13.0, TEXT, pan_x=1.0)
        cmds += text_at("range %s" % rng, left + 6.0, y + barh + 14.0, 9.5, DIM)
        cmds += text_at("carrier %s" % carrier, left + 150.0, y + barh + 14.0, 9.5, colour)
    cmds += text_at("relative strength, powers of ten", 150.0, 340.0, 10.0, DIM)
    cmds += text_at("gravity is 10^38 times weaker than the strong force",
                    150.0, 356.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "The four fundamental interactions compared by relative "
                                   "strength, range and force carrier"),
            "root": canvas(title(cmds, W, H, "Fundamental interactions",
                                 "one log axis, four forces"))}


docs["PHY-FPP-00004"] = interactions()


# ── 2. PHY-FPP-00005  Feynman diagrams — annotated-layout / demonstrate / 2D ───
# Layout carries the structure: three cards in a column, each a box holding its own small
# canvas plus a caption component. The drawing is incidental; the containers are the point.
def feynman():
    W, H = 420, 470

    def diagram_canvas(kind):
        c = [paint({"color": "#FF0F1830"}, {"style": "fill"}),
             {"drawRect": {"left": 0, "top": 0, "right": 150, "bottom": 86}}]
        st = [paint({"color": "#FFBCD2FA"}, {"style": "stroke"}, {"width": 2.0},
                    {"strokeCap": "round"})]
        if kind == "annihilation":
            c += st + [{"drawLine": {"x1": 16, "y1": 16, "x2": 62, "y2": 43}},
                       {"drawLine": {"x1": 16, "y1": 70, "x2": 62, "y2": 43}}]
            c += [paint({"color": WARM}, {"style": "stroke"}, {"width": 2.0})]
            for k in range(5):                     # a wavy photon line
                x0 = 62 + k * 10
                c.append({"drawArc": {"left": x0, "top": 37, "right": x0 + 10,
                                      "bottom": 49, "startAngle": 0.0 if k % 2 else 180.0,
                                      "sweepAngle": 180.0}})
            c += st + [{"drawLine": {"x1": 112, "y1": 43, "x2": 138, "y2": 18}},
                       {"drawLine": {"x1": 112, "y1": 43, "x2": 138, "y2": 68}}]
        elif kind == "scattering":
            c += st + [{"drawLine": {"x1": 14, "y1": 20, "x2": 136, "y2": 20}},
                       {"drawLine": {"x1": 14, "y1": 66, "x2": 136, "y2": 66}}]
            c += [paint({"color": WARM}, {"style": "stroke"}, {"width": 2.0})]
            for k in range(4):
                y0 = 24 + k * 10
                c.append({"drawArc": {"left": 69, "top": y0, "right": 81,
                                      "bottom": y0 + 10, "startAngle": 90.0 if k % 2 else 270.0,
                                      "sweepAngle": 180.0}})
        else:                                       # beta decay
            c += st + [{"drawLine": {"x1": 14, "y1": 43, "x2": 70, "y2": 43}}]
            c += [paint({"color": GOOD}, {"style": "stroke"}, {"width": 2.0})]
            for k in range(4):
                x0 = 70 + k * 9
                c.append({"drawArc": {"left": x0, "top": 38, "right": x0 + 9,
                                      "bottom": 48, "startAngle": 0.0 if k % 2 else 180.0,
                                      "sweepAngle": 180.0}})
            c += st + [{"drawLine": {"x1": 70, "y1": 43, "x2": 136, "y2": 20}},
                       {"drawLine": {"x1": 106, "y1": 43, "x2": 136, "y2": 50}},
                       {"drawLine": {"x1": 106, "y1": 43, "x2": 136, "y2": 76}}]
        return {"type": "canvas", "modifiers": [{"width": 150}, {"height": 86}],
                "commands": c}

    def card(kind, name, caption):
        return {"type": "row",
                "modifiers": [{"width": 388}, {"padding": 10}, {"background": PANEL}],
                "children": [
                    diagram_canvas(kind),
                    {"type": "spacer", "modifiers": [{"width": 14}]},
                    {"type": "column", "modifiers": [{"width": 196}], "children": [
                        {"type": "text", "value": name, "modifiers": [],
                         "fontSize": 14.0, "color": TEXT},
                        {"type": "spacer", "modifiers": [{"height": 6}]},
                        {"type": "text", "value": caption, "modifiers": [],
                         "fontSize": 10.5, "color": DIM}]}]}

    return {
        "header": header(W, H, "Three Feynman diagrams as cards in a column, each pairing a "
                               "small canvas with its caption"),
        "root": {"type": "column",
                 "modifiers": ["fillMaxSize", {"background": INK}, {"padding": 16}],
                 "children": [
                     {"type": "text", "value": "Feynman diagrams", "modifiers": [],
                      "fontSize": 20.0, "color": TEXT},
                     {"type": "spacer", "modifiers": [{"height": 4}]},
                     {"type": "text", "value": "time runs left to right",
                      "modifiers": [], "fontSize": 11.0, "color": DIM},
                     {"type": "spacer", "modifiers": [{"height": 14}]},
                     card("annihilation", "Annihilation",
                          "an electron and a positron meet, become a photon, and produce a "
                          "new pair"),
                     {"type": "spacer", "modifiers": [{"height": 10}]},
                     card("scattering", "Scattering",
                          "two electrons exchange a virtual photon and deflect"),
                     {"type": "spacer", "modifiers": [{"height": 10}]},
                     card("beta", "Beta decay",
                          "a down quark emits a W boson, becoming up; the W decays to an "
                          "electron and an antineutrino"),
                 ]},
    }


docs["PHY-FPP-00005"] = feynman()


# ── 3. PHY-FPP-00006  Particle accelerators — data-plot / simulate / 2D ────────
# The Livingston plot: beam energy against year, on a log axis, from float arrays. The
# simulate obligation is a bunch circulating a ring beside it, on the same clock.
ACCEL = [("Cockcroft-Walton", 1932, 5.9), ("Cyclotron", 1939, 7.2),
         ("Bevatron", 1954, 9.8), ("AGS", 1960, 10.5), ("SPS", 1976, 11.6),
         ("Tevatron", 1983, 11.9), ("LEP", 1989, 11.0), ("HERA", 1992, 11.5),
         ("RHIC", 2000, 11.1), ("LHC", 2008, 12.8), ("HL-LHC", 2029, 13.0)]


def accelerators():
    W, H = 560, 380
    years = [float(y) for _, y, _ in ACCEL]
    energy = [e for _, _, e in ACCEL]
    left, right, top, bottom = 70.0, 360.0, 80.0, 300.0
    cmds = []
    for dec in range(6, 14, 2):
        y = bottom - (bottom - top) * (dec - 6) / 7.0
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawLine": {"x1": left, "y1": y, "x2": right, "y2": y}})
        cmds += text_at("10^%d" % dec, left - 8.0, y + 4.0, 9.0, DIM, pan_x=1.0)

    cmds.append(var("ymin", "1930.0"))
    cmds.append(var("yspan", "105.0"))
    cmds.append({"loop": {"index": "i", "from": 0.0, "until": float(len(ACCEL)),
                          "step": 1.0, "commands": [
        var("yr", "arrayGet(@years, @i)"),
        var("ev", "arrayGet(@energy, @i)"),
        var("px", "%.1f + (@yr - @ymin) / @yspan * %.1f" % (left, right - left)),
        var("py", "%.1f - (@ev - 6.0) / 7.0 * %.1f" % (bottom, bottom - top)),
        paint({"color": ACCENT}, {"style": "fill"}),
        {"drawCircle": {"cx": "@px", "cy": "@py", "radius": 4.5}},
    ]}})

    for name, yr, ev in ACCEL:
        px = left + (yr - 1930.0) / 105.0 * (right - left)
        py = bottom - (ev - 6.0) / 7.0 * (bottom - top)
        if name in ("Cockcroft-Walton", "Tevatron", "LHC", "HL-LHC"):
            cmds += text_at(name, px + 7.0, py + 3.0, 9.0, DIM)
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.3}))
    cmds.append({"drawLine": {"x1": left, "y1": bottom, "x2": right, "y2": bottom}})
    for yr in (1940, 1970, 2000, 2030):
        px = left + (yr - 1930.0) / 105.0 * (right - left)
        cmds += text_at(str(yr), px, bottom + 16.0, 9.5, DIM, pan_x=0.0)

    # a bunch going round the ring, on the document's own clock
    cx, cy, r = 460.0, 190.0, 72.0
    cmds.append(paint({"color": "#FF22304E"}, {"style": "stroke"}, {"width": 10.0}))
    cmds.append({"drawCircle": {"cx": cx, "cy": cy, "radius": r}})
    cmds.append(var("th", "continuousSec() * 2.4"))
    for k in range(3):
        cmds.append(paint({"color": [GOOD, WARM, HOT][k]}, {"style": "fill"}))
        cmds.append({"drawCircle": {
            "cx": "%.1f + cos(@th + %.2f) * %.1f" % (cx, k * 2.094, r),
            "cy": "%.1f + sin(@th + %.2f) * %.1f" % (cy, k * 2.094, r),
            "radius": 6.0}})
    cmds += text_at("three bunches circulating", cx, cy + r + 26.0, 10.0, DIM, pan_x=0.0)
    cmds += text_at("beam energy, eV", left, 344.0, 10.0, DIM)
    cmds += text_at("a factor of ten every six years, for seventy years",
                    left, 360.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "Accelerator beam energy against year on a log axis, with "
                                   "bunches circulating a ring"),
            "resources": {"floatArrays": [{"years": years}, {"energy": energy}]},
            "root": canvas(title(cmds, W, H, "Accelerators", "energy per beam, 1930 to 2030"))}


docs["PHY-FPP-00006"] = accelerators()


# ── 4. PHY-FPP-00007  Particle decay — path-form / analyze / 3D ───────────────
# Deliberately a mixed document: a wireframe chamber from the 3D pipeline with the decay
# tracks drawn as real 2D paths over it. Charged tracks in a magnetic field are helices, so
# the geometry is computed and projected here; this also probes whether 2D path drawing and
# a 3D scene coexist, which nothing in the corpus currently tests.
def decay():
    W, H = 460, 460
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.9, "aspect": 1.0,
                          "near": 0.1, "far": 60.0,
                          "eye": [2.2, 1.6, 2.8], "center": [0, 0, 0], "up": [0, 1, 0]}},
            {"lights3D": {"lights": [{"type": "directional", "color": "#FFFFFFFF",
                                      "dir": [-0.4, -0.6, -0.7], "intensity": 1.0}]}}]

    # tracks first, as 2D paths; the chamber wireframe goes last so it does not occlude
    # them with its depth (finding F-009)
    cx, cy, scale = 230.0, 250.0, 150.0

    def project(x, y, z):
        """A fixed isometric projection, so the paths line up with the 3D chamber."""
        px = cx + (x - z) * 0.866 * scale
        py = cy - (y - (x + z) * 0.5) * 0.7 * scale
        return round(px, 2), round(py, 2)

    tracks = [("mu-", 1.0, 0.55, GOOD), ("e+", -2.2, 0.30, WARM),
              ("pi-", 1.7, 0.42, ACCENT), ("p", -0.8, 0.70, HOT)]
    for ti, (name, curl, pitch, colour) in enumerate(tracks):
        pid = "trk%d" % ti
        pts = []
        for k in range(46):
            t = k / 45.0
            ang = curl * t * 3.2 + ti * 1.3
            rad = 0.15 + t * 0.55
            pts.append(project(rad * math.cos(ang), (t - 0.5) * pitch,
                               rad * math.sin(ang)))
        cmds.append({"pathCreate": {"id": pid, "x": pts[0][0], "y": pts[0][1]}})
        for px, py in pts[1:]:
            cmds.append({"pathAppendLineTo": {"path": pid, "x": px, "y": py}})
        cmds.append(paint({"color": colour}, {"style": "stroke"}, {"width": 2.2},
                          {"strokeCap": "round"}))
        cmds.append({"drawPath": {"path": pid}})
        cmds += text_at(name, pts[-1][0] + 6.0, pts[-1][1], 11.0, colour)

    cmds.append(paint({"color": "#FFFFFFFF"}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": project(0, 0, 0)[0], "cy": project(0, 0, 0)[1],
                                "radius": 4.0}})

    # the chamber, last
    cmds += [{"meshPrimitive3D": {"id": 1, "primitive": "cube", "dimX": 1.9,
                                  "dimY": 1.9, "dimZ": 1.9, "center": [0, 0, 0]}},
             {"matrix3D": {"op": "identity"}},
             paint({"color": "#FF27385C"}, {"style": "stroke"}, {"width": 1.0}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth", "wireframe": True}}]

    cmds += text_at("curvature gives momentum; sign gives charge", 20.0, 408.0, 10.0, DIM)
    cmds += text_at("tracks are 2D paths over a 3D chamber", 20.0, 424.0, 10.0, "#FF5E6E95")
    cmds += text_at("4 tracks, 46 points each", 20.0, 440.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "Four decay tracks drawn as paths inside a wireframe "
                                   "chamber, curving by charge and momentum"),
            "root": canvas(title(cmds, W, H, "Particle decay",
                                 "a vertex and what leaves it"))}


docs["PHY-FPP-00007"] = decay()


# ── 5. BIO-MB-00005  Translation — expression-animation / explain / 2D ────────
# The ribosome walks the mRNA and the chain grows behind it. Everything is a function of
# one clock, so there is no frame list anywhere.
def translation():
    W, H = 520, 320
    left, right, y = 50.0, 470.0, 150.0
    cmds = []
    cmds.append(var("t", "continuousSec() % 8"))
    cmds.append(var("pos", "%.1f + @t / 8 * %.1f" % (left, right - left)))

    cmds.append(paint({"color": "#FF22304E"}, {"style": "stroke"}, {"width": 7.0},
                      {"strokeCap": "round"}))
    cmds.append({"drawLine": {"x1": left, "y1": y, "x2": right, "y2": y}})
    for k in range(14):                       # codon ticks
        x = left + k * (right - left) / 14.0
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.5}))
        cmds.append({"drawLine": {"x1": x, "y1": y - 8.0, "x2": x, "y2": y + 8.0}})

    # the growing polypeptide: beads behind the ribosome, each appearing as it is passed
    for k in range(13):
        frac = (k + 1) / 14.0
        cmds.append(paint({"color": ["#FF5B8CEE", "#FF4FD6C9", "#FFE8A33D", "#FFE8564F"][k % 4]},
                          {"style": "fill"},
                          {"alpha": "clamp(0.0, 1.0, (@t / 8 - %.4f) * 30)" % frac}))
        cmds.append({"drawCircle": {
            "cx": "@pos - %.1f" % (18 + k * 17),
            "cy": "%.1f - sin(%.3f + @t * 1.2) * 12" % (y - 52.0, k * 0.8),
            "radius": 7.0}})

    # the tRNA arriving at the A site, dropping in and leaving
    cmds.append(paint({"color": GOOD}, {"style": "stroke"}, {"width": 2.5}))
    cmds.append({"drawLine": {"x1": "@pos + 26", "y1": "%.1f - 60 + abs(sin(@t * 3.1)) * 44" % y,
                              "x2": "@pos + 26", "y2": "%.1f - 30 + abs(sin(@t * 3.1)) * 44" % y}})

    cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
    cmds.append({"drawRoundRect": {"left": "@pos - 24", "top": y - 26.0,
                                   "right": "@pos + 24", "bottom": y + 26.0,
                                   "rx": 12.0, "ry": 12.0}})
    cmds.append(paint({"color": INK}, {"style": "fill"}, {"textSize": 11.0}))
    cmds.append({"drawTextAnchored": {"text": "ribosome", "x": "@pos", "y": y + 4.0,
                                      "panX": 0.0, "panY": 0.0, "flags": 0}})
    cmds += text_at("mRNA", left, y + 34.0, 11.0, DIM)
    cmds += text_at("polypeptide", left, y - 84.0, 11.0, TEXT)
    cmds += text_at("tRNA delivers the next amino acid at the A site",
                    20.0, 288.0, 10.0, GOOD)
    cmds += text_at("one codon, one amino acid", 20.0, 304.0, 10.0, DIM)
    return {"header": header(W, H, "A ribosome translating mRNA, with the polypeptide chain "
                                   "growing behind it"),
            "root": canvas(title(cmds, W, H, "Translation", "the ribosome reads codon by codon"))}


docs["BIO-MB-00005"] = translation()


# ── 6. BIO-MB-00006  Gene regulation — particle-system / explore / 2D ─────────
# Transcription factors as a particle cloud. Position carries meaning, which is the lesson
# set 1 paid for: height is binding affinity, so the promoter captures the top of the
# population and the rest drift.
def gene_regulation():
    W, H = 480, 400
    prom_y = 300.0
    cmds = []
    cmds.append(var("sig", "0.5 + sin(continuousSec() * 0.4) * 0.45"))

    cmds.append({"createParticles": {
        "id": "tf",
        "variables": ["fx", "fy", "aff", "ph"],
        "initialValues": ["30 + rand() * 420", "60 + rand() * 200",
                          "rand()", "rand() * 6.283"],
        "count": 120}})
    cmds.append({"particlesLoop": {
        "system": "@tf",
        "equations": [
            "fx + sin(ph + animationTime * 0.9) * 0.6",
            # bound factors sink to the promoter, free ones drift
            "fy + ifElse(-0.3, 1.6, aff - (1 - @sig)) * 0.9",
            "aff", "ph"],
        "commands": [
            paint({"color": GOOD}, {"style": "fill"},
                  {"alpha": "clamp(0.15, 0.95, aff)"}),
            {"drawCircle": {"cx": "fx", "cy": "clamp(50, %.1f, fy)" % (prom_y - 14),
                            "radius": 4.0}}]}})

    cmds.append(paint({"color": "#FF22304E"}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": 30.0, "top": prom_y, "right": 450.0,
                              "bottom": prom_y + 18.0}})
    cmds.append(paint({"color": WARM}, {"style": "fill"}))
    cmds.append({"drawRect": {"left": 150.0, "top": prom_y, "right": 250.0,
                              "bottom": prom_y + 18.0}})
    cmds += text_at("promoter", 150.0, prom_y + 34.0, 10.5, WARM)
    cmds += text_at("gene", 262.0, prom_y + 34.0, 10.5, DIM)

    # transcription output, as a bar driven by the same signal
    cmds.append(paint({"color": "#FF1B2740"}, {"style": "fill"}))
    cmds.append({"drawRoundRect": {"left": 30.0, "top": 348.0, "right": 450.0,
                                   "bottom": 366.0, "rx": 4.0, "ry": 4.0}})
    cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
    cmds.append({"drawRoundRect": {"left": 30.0, "top": 348.0,
                                   "right": "30 + @sig * 420", "bottom": 366.0,
                                   "rx": 4.0, "ry": 4.0}})
    cmds.append({"variable": {"name": "pct", "value": {"type": "textFromFloat",
                                                       "value": "@sig * 100",
                                                       "whole": 3, "decimal": 0}}})
    cmds.append(paint({"color": TEXT}, {"style": "fill"}, {"textSize": 12.0}))
    cmds.append({"drawTextAnchored": {"text": "@pct", "x": 450.0, "y": 384.0,
                                      "panX": 1.0, "panY": 0.0, "flags": 0}})
    cmds += text_at("% transcription", 30.0, 384.0, 10.0, DIM)
    return {"header": header(W, H, "Transcription factors as a particle cloud binding a "
                                   "promoter, with transcription rising as they bind"),
            "root": canvas(title(cmds, W, H, "Gene regulation",
                                 "brighter factors bind more tightly"))}


docs["BIO-MB-00006"] = gene_regulation()


# ── 7. BIO-CB-00007  Cell structure — interactive / compare / 2D ──────────────
# Drag to cross-fade between an animal cell and a plant cell. A comparison you operate
# yourself lands harder than two pictures side by side, and the shared organelles stay put
# so only the differences move.
def cell_structure():
    W, H = 480, 400
    cx, cy = 240.0, 215.0
    cmds = []
    cmds.append({"touchExpression": {"name": "mix", "defaultValue": 0.0,
                                     "min": 0.0, "max": 1.0, "stopMode": "gently",
                                     "expression": "touchX() / 480"}})
    cmds.append(var("m", "clamp(0.0, 1.0, @mix)"))

    # plant-only: the cell wall, square and rigid, fading in with the mix
    cmds.append(paint({"color": GOOD}, {"style": "stroke"}, {"width": 6.0},
                      {"alpha": "@m"}))
    cmds.append({"drawRect": {"left": cx - 170.0, "top": cy - 130.0,
                              "right": cx + 170.0, "bottom": cy + 130.0}})
    # the membrane, always there
    cmds.append(paint({"color": "#FF7E9AC6"}, {"style": "stroke"}, {"width": 3.0}))
    cmds.append({"drawOval": {"left": cx - 158.0, "top": cy - 118.0,
                              "right": cx + 158.0, "bottom": cy + 118.0}})
    # plant-only: a big central vacuole
    cmds.append(paint({"color": "#FF2E7FA8"}, {"style": "fill"}, {"alpha": "@m * 0.8"}))
    cmds.append({"drawOval": {"left": cx - 92.0, "top": cy - 60.0,
                              "right": cx + 52.0, "bottom": cy + 74.0}})
    # plant-only: chloroplasts
    for k, (ox, oy) in enumerate([(90, -70), (116, 10), (72, 66), (-120, 60)]):
        cmds.append(paint({"color": "#FF46C46A"}, {"style": "fill"}, {"alpha": "@m"}))
        cmds.append({"drawOval": {"left": cx + ox - 20, "top": cy + oy - 11,
                                  "right": cx + ox + 20, "bottom": cy + oy + 11}})
    # shared: nucleus, mitochondria
    cmds.append(paint({"color": ACCENT}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": cx - 42.0, "cy": cy - 34.0, "radius": 40.0}})
    cmds.append(paint({"color": "#FF2A4A86"}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": cx - 42.0, "cy": cy - 34.0, "radius": 16.0}})
    for ox, oy in [(66, -88), (-108, -10), (16, 92)]:
        cmds.append(paint({"color": WARM}, {"style": "fill"}))
        cmds.append({"drawOval": {"left": cx + ox - 22, "top": cy + oy - 10,
                                  "right": cx + ox + 22, "bottom": cy + oy + 10}})

    cmds += text_at("nucleus", cx - 42.0, cy - 80.0, 10.5, "#FFBCD2FA", pan_x=0.0)
    cmds += text_at("mitochondria", cx + 66.0, cy - 104.0, 10.0, WARM, pan_x=0.0)
    cmds.append(paint({"color": GOOD}, {"style": "fill"}, {"textSize": 10.0},
                      {"alpha": "@m"}))
    cmds.append({"drawTextAnchored": {"text": "cell wall", "x": cx - 170.0,
                                      "y": cy - 140.0, "panX": -1.0, "panY": 0.0,
                                      "flags": 0}})
    cmds.append(paint({"color": "#FF46C46A"}, {"style": "fill"}, {"textSize": 10.0},
                      {"alpha": "@m"}))
    cmds.append({"drawTextAnchored": {"text": "chloroplasts", "x": cx + 120.0,
                                      "y": cy + 96.0, "panX": 0.0, "panY": 0.0,
                                      "flags": 0}})

    cmds += text_at("animal", 24.0, 372.0, 13.0, DIM)
    cmds += text_at("plant", 456.0, 372.0, 13.0, GOOD, pan_x=1.0)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 2.0}))
    cmds.append({"drawLine": {"x1": 80.0, "y1": 368.0, "x2": 400.0, "y2": 368.0}})
    cmds.append(paint({"color": TEXT}, {"style": "fill"}))
    cmds.append({"drawCircle": {"cx": "80 + @m * 320", "cy": 368.0, "radius": 7.0}})
    cmds += text_at("drag across to compare", 24.0, 392.0, 10.0, DIM)
    return {"header": header(W, H, "Drag to cross-fade an animal cell into a plant cell; "
                                   "shared organelles stay put"),
            "root": canvas(title(cmds, W, H, "Cell structure", "animal against plant"))}


docs["BIO-CB-00007"] = cell_structure()


# ── 8. BIO-CB-00008  Organelles — raster-and-text / simulate / 3D ─────────────
# The swapped slot. A textured membrane on a 3D cell, turning, with organelles inside it as
# labelled bodies. texture3D needs a real bitmap resource, which is the thinnest part of the
# corpus - 5 documents use images at all.
def organelles():
    W, H = 460, 460
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 0.95, "aspect": 1.0,
                          "near": 0.1, "far": 60.0,
                          "eye": [0.6, 0.9, 3.4], "center": [0, 0, 0], "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.35, -0.55, -0.75], "intensity": 1.0},
                {"type": "directional", "color": "#FF4FD6C9",
                 "dir": [0.5, 0.2, 0.4], "intensity": 0.3}]}}]
    cmds.append(var("spin", "continuousSec() * 0.35"))

    # the nucleus is drawn separately below, because it is the one that carries the texture
    bodies = [("mitochondrion", 0.62, 0.34, 0.20, 0.17, "#FFE8A33D"),
              ("mitochondrion", -0.55, -0.30, 0.34, 0.15, "#FFE8A33D"),
              ("golgi", 0.18, -0.58, -0.30, 0.19, "#FF4FD6C9"),
              ("lysosome", -0.42, 0.52, -0.36, 0.12, "#FFE8564F"),
              ("ribosome", 0.48, -0.12, -0.60, 0.07, "#FFBCD2FA")]
    for i, (name, x, y, z, r, colour) in enumerate(bodies):
        cmds += [{"meshPrimitive3D": {"id": 10 + i, "primitive": "sphere", "segments": 16,
                                      "radius": r, "center": [0, 0, 0]}},
                 {"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 {"matrix3D": {"op": "translate", "x": x, "y": y, "z": z}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": 10 + i, "mode": "software-smooth"}}]

    # The nucleus carries the bitmap. A texture is only visible on a FILLED mesh - setting
    # texture3D and then drawing wireframe shows the lines and nothing else, which is what
    # the first version of this document did while claiming a texture in its own caption.
    cmds += [{"texture3D": {"bitmap": "@membrane"}},
             {"meshPrimitive3D": {"id": 2, "primitive": "sphere", "segments": 24,
                                  "radius": 0.42, "center": [0, 0, 0], "uv": "uv"}},
             {"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": "#FFFFFFFF"}, {"style": "fill"}),
             {"drawMesh3D": {"mesh": 2, "mode": "software-smooth"}}]

    # the membrane last, as a wireframe cage over everything (F-009)
    cmds += [{"meshPrimitive3D": {"id": 1, "primitive": "sphere", "segments": 30,
                                  "radius": 1.18, "center": [0, 0, 0]}},
             {"matrix3D": {"op": "identity"}},
             {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
             paint({"color": "#FF6E89B4"}, {"style": "stroke"}, {"width": 1.0}),
             {"drawMesh3D": {"mesh": 1, "mode": "software-smooth", "wireframe": True}}]

    legend = [("nucleus (textured)", "#FFBCD2FA"), ("mitochondria", WARM), ("golgi", GOOD),
              ("lysosome", HOT), ("ribosomes", "#FFBCD2FA")]
    for i, (name, colour) in enumerate(legend):
        yy = 372.0 + i * 16.0
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": 22.0, "top": yy - 7.0,
                                  "right": 32.0, "bottom": yy + 1.0}})
        cmds += text_at(name, 40.0, yy, 10.0, DIM)
    cmds += text_at("the nucleus is a bitmap texture", 240.0, 372.0, 10.0, "#FFBCD2FA")
    cmds += text_at("membrane is a wireframe cage", 240.0, 388.0, 10.0, "#FF6E89B4")
    cmds += text_at("the cell turns on its own clock", 240.0, 404.0, 10.0, DIM)
    return {"header": header(W, H, "A turning 3D cell with a bitmap-textured membrane and "
                                   "labelled organelles inside"),
            "resources": {"bitmaps": [{"membrane": {"file": "textures/membrane.png"}}]},
            "root": canvas(title(cmds, W, H, "Organelles", "inside a single cell"))}


docs["BIO-CB-00008"] = organelles()


# ── 9. MTH-AN-00002  Fractions — static-diagram / demonstrate / 2D ────────────
# One claim, demonstrated three ways on a shared width: halves, quarters and sixths all
# reaching the same place.
def fractions():
    W, H = 520, 340
    left, width = 60.0, 400.0
    rows = [(2, 1, ACCENT), (4, 2, GOOD), (6, 3, WARM), (8, 4, HOT)]
    cmds = []
    for i, (den, num, colour) in enumerate(rows):
        y = 96.0 + i * 56.0
        for k in range(den):
            x0 = left + width * k / den
            x1 = left + width * (k + 1) / den
            filled = k < num
            cmds.append(paint({"color": colour if filled else "#FF1B2740"},
                              {"style": "fill"}))
            cmds.append({"drawRect": {"left": x0 + 1.5, "top": y,
                                      "right": x1 - 1.5, "bottom": y + 34.0}})
        cmds += text_at("%d/%d" % (num, den), left - 12.0, y + 23.0, 14.0, TEXT, pan_x=1.0)
        cmds += text_at("%d of %d parts" % (num, den), left + width + 12.0, y + 22.0,
                        10.0, DIM)
    # the shared half line, which is the point of the figure
    xhalf = left + width / 2
    cmds.append(paint({"color": TEXT}, {"style": "stroke"}, {"width": 1.6}))
    cmds.append({"drawLine": {"x1": xhalf, "y1": 86.0, "x2": xhalf, "y2": 304.0}})
    cmds += text_at("every bar fills to the same line", xhalf + 8.0, 318.0, 10.5, TEXT)
    return {"header": header(W, H, "Four equivalent fractions as bars on a shared width, all "
                                   "reaching the same half line"),
            "root": canvas(title(cmds, W, H, "Equivalent fractions",
                                 "different parts, same amount"))}


docs["MTH-AN-00002"] = fractions()


# ── 10. CSC-ALGO-00002  Searching — annotated-layout / simulate / 2D ──────────
# Binary search, one row per step, built from layout containers rather than drawn: each
# step is a row of boxes and the window narrows down the page.
def searching():
    W, H = 560, 420
    data = [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]
    target = 23
    steps, lo, hi = [], 0, len(data) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        steps.append((lo, hi, mid))
        if data[mid] == target:
            break
        if data[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1

    def cell(v, state):
        bg = {"in": "#FF1E2C4A", "mid": ACCENT, "out": "#FF121A2C"}[state]
        fg = {"in": TEXT, "mid": INK, "out": "#FF46536E"}[state]
        return {"type": "box",
                "modifiers": [{"width": 44}, {"height": 34}, {"background": bg}],
                "children": [{"type": "text", "value": str(v), "modifiers": [],
                              "fontSize": 13.0, "color": fg}]}

    rows = []
    for si, (lo, hi, mid) in enumerate(steps):
        cells = []
        for i, v in enumerate(data):
            st = "mid" if i == mid else ("in" if lo <= i <= hi else "out")
            cells.append(cell(v, st))
            if i < len(data) - 1:
                cells.append({"type": "spacer", "modifiers": [{"width": 4}]})
        rows.append({"type": "row", "modifiers": [], "children": [
            {"type": "box", "modifiers": [{"width": 58}], "children": [
                {"type": "text", "value": "step %d" % (si + 1), "modifiers": [],
                 "fontSize": 10.5, "color": DIM}]},
            {"type": "row", "modifiers": [], "children": cells}]})
        rows.append({"type": "spacer", "modifiers": [{"height": 8}]})

    return {
        "header": header(W, H, "Binary search for 23, one row of boxes per step, the live "
                               "window narrowing down the page"),
        "root": {"type": "column",
                 "modifiers": ["fillMaxSize", {"background": INK}, {"padding": 18}],
                 "children": [
                     {"type": "text", "value": "Binary search", "modifiers": [],
                      "fontSize": 20.0, "color": TEXT},
                     {"type": "spacer", "modifiers": [{"height": 4}]},
                     {"type": "text", "value": "looking for 23; dim cells are out of the window",
                      "modifiers": [], "fontSize": 11.0, "color": DIM},
                     {"type": "spacer", "modifiers": [{"height": 16}]},
                 ] + rows + [
                     {"type": "text",
                      "value": "ten elements, %d steps - log2(10) rounded up" % len(steps),
                      "modifiers": [], "fontSize": 10.0, "color": "#FF5E6E95"}]},
    }


docs["CSC-ALGO-00002"] = searching()


def _box(verts, normals, uv, idx, lo, hi):
    """Append an axis-aligned box as 12 triangles with per-face normals.

    Winding is [base, base+2, base+1] / [base, base+3, base+2] because the engine culls the
    opposite order from the one that reads naturally, and a wrongly wound mesh renders as
    nothing at all with no error anywhere (finding F-008).
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
        idx += [base, base + 2, base + 1, base, base + 3, base + 2]


def _axis_mesh(mesh_id, lo, hi, ticks, tick_axis, rod=0.03, tick_len=0.1):
    """An axis rod plus its ticks, as one mesh. One mesh per axis, because a mesh takes a
    single paint and each axis needs its own colour."""
    verts, normals, uv, idx = [], [], [], []
    _box(verts, normals, uv, idx, lo, hi)
    for t in ticks:
        if tick_axis == "x":
            _box(verts, normals, uv, idx, (t - rod, lo[1] - tick_len, lo[2] - rod),
                 (t + rod, lo[1] + rod, lo[2] + rod))
        elif tick_axis == "z":
            _box(verts, normals, uv, idx, (lo[0] - tick_len, lo[1] - rod, t - rod),
                 (lo[0] + rod, lo[1] + rod, t + rod))
        else:
            _box(verts, normals, uv, idx, (lo[0] - tick_len, t - rod, lo[2] - rod),
                 (lo[0] + rod, t + rod, lo[2] + rod))
    return {"defineMesh3D": {"id": mesh_id,
                             "verts": [round(x, 5) for x in verts],
                             "normals": [round(x, 5) for x in normals],
                             "uv": uv, "indices": idx}}


# ── 11. CHM-AC-00002  Periodic table — data-plot / analyze / 3D ───────────────
# The table's own grid is already two axes, so the third is free for a property. Atomic
# radius bars over period and group: the sawtooth down each period is the whole point and
# it is invisible on a flat table.
RADII = {
    1: [53, 31], 2: [167, 112, 87, 67, 56, 48, 42, 38],
    3: [190, 145, 118, 111, 98, 88, 79, 71],
    4: [243, 194, 184, 176, 171, 166, 161, 156, 152, 149, 145, 142, 136, 125, 114, 103, 94, 88],
}


def periodic_table():
    W, H = 500, 460
    cmds = [{"clearDepth3D": {}},
            {"camera3D": {"projection": "perspective", "fovY": 1.0, "aspect": 1.0,
                          "near": 0.1, "far": 60.0,
                          "eye": [2.0, 2.3, 2.9], "center": [0, -0.1, 0], "up": [0, 1, 0]}},
            {"lights3D": {"lights": [
                {"type": "directional", "color": "#FFFFFFFF",
                 "dir": [-0.4, -0.7, -0.55], "intensity": 1.0},
                {"type": "directional", "color": "#FF5B8CEE",
                 "dir": [0.55, 0.25, 0.4], "intensity": 0.3}]}}]
    cmds.append(var("spin", "sin(continuousSec() * 0.25) * 0.5"))

    mid = 20
    maxr = 243.0
    for period, radii in RADII.items():
        for gi, r in enumerate(radii):
            hgt = r / maxr * 1.3
            x = -1.0 + gi / 17.0 * 2.0
            z = -0.7 + (period - 1) / 3.0 * 1.4
            mid += 1
            # colour by how far down the period: the sawtooth made visible
            frac = gi / max(1, len(radii) - 1)
            colour = "#FF%02X%02X%02X" % (int(90 + 150 * (1 - frac)),
                                          int(120 + 60 * frac),
                                          int(220 - 60 * frac))
            cmds += [{"meshPrimitive3D": {"id": mid, "primitive": "cube",
                                          "dimX": 0.085, "dimY": round(hgt, 4),
                                          "dimZ": 0.085, "center": [0, 0, 0]}},
                     {"matrix3D": {"op": "identity"}},
                     {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                     {"matrix3D": {"op": "translate", "x": round(x, 4),
                                   "y": round(-0.75 + hgt / 2, 4), "z": round(z, 4)}},
                     paint({"color": colour}, {"style": "fill"}),
                     {"drawMesh3D": {"mesh": mid, "mode": "software-smooth"}}]

    # Axes as real geometry so they turn with the bars and keep saying which way is which.
    # The floor is the y the bars stand on; the top is the tallest bar.
    FLOOR, TOP = -0.75, -0.75 + 1.3
    # clear of the outermost bars (x reaches 1.0, z reaches 0.7) so the rods read
    # as a frame rather than being swallowed by the data
    GX, GZ = 1.18, 0.98
    group_ticks = [-1.0 + (g - 1) / 17.0 * 2.0 for g in (1, 5, 10, 15, 18)]
    period_ticks = [-0.7 + (pd - 1) / 3.0 * 1.4 for pd in (1, 2, 3, 4)]
    radius_ticks = [FLOOR + (r / maxr) * 1.3 for r in (50, 100, 150, 200)]
    cmds.append(_axis_mesh(2, (-GX, FLOOR - 0.03, -GZ - 0.03), (GX, FLOOR + 0.03, -GZ + 0.03),
                           group_ticks, "x"))
    cmds.append(_axis_mesh(3, (-GX - 0.03, FLOOR - 0.03, -GZ), (-GX + 0.03, FLOOR + 0.03, GZ),
                           period_ticks, "z"))
    cmds.append(_axis_mesh(4, (-GX - 0.03, FLOOR, -GZ - 0.03), (-GX + 0.03, TOP, -GZ + 0.03),
                           radius_ticks, "y"))
    for mesh_id, colour in ((2, WARM), (3, GOOD), (4, "#FFBFCBE4")):
        cmds += [{"matrix3D": {"op": "identity"}},
                 {"matrix3D": {"op": "rotate", "angle": "@spin", "axis": [0, 1, 0]}},
                 paint({"color": colour}, {"style": "fill"}),
                 {"drawMesh3D": {"mesh": mesh_id, "mode": "software-flat"}}]

    cmds += text_at("group", 20.0, 352.0, 12.0, WARM)
    cmds += text_at("period", 86.0, 352.0, 12.0, GOOD)
    cmds += text_at("radius", 160.0, 352.0, 12.0, "#FFBFCBE4")
    cmds += text_at("ticks: groups 1 5 10 15 18, periods 1-4, radius every 50 pm",
                    20.0, 368.0, 9.5, DIM)
    cmds += text_at("atomic radius falls across each period", 20.0, 386.0, 11.0, TEXT)
    cmds += text_at("and jumps at the start of the next one", 20.0, 404.0, 11.0, WARM)
    cmds += text_at("periods 1 to 4, 36 elements, picometres", 20.0, 428.0, 9.5,
                    "#FF5E6E95")
    return {"header": header(W, H, "Atomic radius as 3D bars over the periodic table's own "
                                   "grid, showing the sawtooth across each period"),
            "root": canvas(title(cmds, W, H, "Atomic radius", "the periodic table's third axis"))}


docs["CHM-AC-00002"] = periodic_table()


# ── 12. EAR-GEOL-00002  Rock cycle — path-form / explain / 2D ─────────────────
# A cycle wants curved arrows, and curved arrows want paths. The three rock types sit at the
# corners and every transition is a real path with an arrowhead.
def rock_cycle():
    W, H = 460, 440
    cx, cy, R = 230.0, 240.0, 130.0
    nodes = [("Igneous", -90, ACCENT), ("Sedimentary", 30, WARM), ("Metamorphic", 150, GOOD)]
    pos = {}
    for name, deg, colour in nodes:
        a = math.radians(deg)
        pos[name] = (cx + R * math.cos(a), cy + R * math.sin(a))

    cmds = []
    arrows = [("Igneous", "Sedimentary", "weathering"),
              ("Sedimentary", "Metamorphic", "heat & pressure"),
              ("Metamorphic", "Igneous", "melting")]
    for ai, (a, b, label) in enumerate(arrows):
        ax, ay = pos[a]
        bx, by = pos[b]
        mx, my = (ax + bx) / 2, (ay + by) / 2
        # bow the path outward from the centre so the three arcs do not overlap
        ox, oy = mx - cx, my - cy
        ol = math.hypot(ox, oy) or 1.0
        ctrlx, ctrly = mx + ox / ol * 54.0, my + oy / ol * 54.0
        pid = "arc%d" % ai
        pts = []
        for k in range(25):
            t = k / 24.0
            # quadratic Bezier, sampled: the dialect has lineTo but no curveTo
            px = (1 - t) ** 2 * ax + 2 * (1 - t) * t * ctrlx + t * t * bx
            py = (1 - t) ** 2 * ay + 2 * (1 - t) * t * ctrly + t * t * by
            pts.append((round(px, 2), round(py, 2)))
        # trim the ends so the arc starts and finishes outside the node discs
        pts = pts[3:-3]
        cmds.append({"pathCreate": {"id": pid, "x": pts[0][0], "y": pts[0][1]}})
        for px, py in pts[1:]:
            cmds.append({"pathAppendLineTo": {"path": pid, "x": px, "y": py}})
        cmds.append(paint({"color": "#FF7E9AC6"}, {"style": "stroke"}, {"width": 2.4},
                          {"strokeCap": "round"}))
        cmds.append({"drawPath": {"path": pid}})
        # arrowhead, from the last segment's direction
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        ang = math.atan2(y2 - y1, x2 - x1)
        for sgn in (1, -1):
            cmds.append({"drawLine": {
                "x1": x2, "y1": y2,
                "x2": round(x2 - 13 * math.cos(ang + sgn * 0.42), 2),
                "y2": round(y2 - 13 * math.sin(ang + sgn * 0.42), 2)}})
        lx, ly = ctrlx, ctrly
        cmds += text_at(label, lx, ly, 10.0, DIM, pan_x=0.0)

    for name, deg, colour in nodes:
        x, y = pos[name]
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": x, "cy": y, "radius": 46.0}})
        cmds.append(paint({"color": INK}, {"style": "fill"}, {"textSize": 11.5}))
        cmds.append({"drawTextAnchored": {"text": name, "x": x, "y": y + 4.0,
                                          "panX": 0.0, "panY": 0.0, "flags": 0}})
    cmds += text_at("every arc is a sampled Bezier: the dialect has lineTo, not curveTo",
                    20.0, 416.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "The rock cycle as three nodes joined by curved arrow "
                                   "paths with arrowheads"),
            "root": canvas(title(cmds, W, H, "The rock cycle", "one rock becomes another"))}


docs["EAR-GEOL-00002"] = rock_cycle()


# ── 13. ENG-ME-00002  Gears — expression-animation / explore / 2D ─────────────
# Two gears meshing at the correct ratio. The small gear turns faster by exactly the tooth
# ratio, which is the only thing a gear diagram has to get right, and it is a single
# expression rather than two animations kept in step by hand.
def gears():
    W, H = 500, 380
    g1 = (190.0, 200.0, 25, 96.0)      # cx, cy, teeth, pitch radius
    g2 = (352.0, 200.0, 15, 58.0)
    cmds = []
    cmds.append(var("a1", "continuousSec() * 0.6"))
    cmds.append(var("a2", "-@a1 * %.5f" % (g1[2] / g2[2])))

    for (cx, cy, teeth, pr), angvar, colour, rim in (
            (g1, "@a1", ACCENT, "#FF2A4A86"), (g2, "@a2", WARM, "#FF7A5A22")):
        cmds.append(paint({"color": rim}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": cx, "cy": cy, "radius": pr + 10.0}})
        cmds.append(paint({"color": colour}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": cx, "cy": cy, "radius": pr - 6.0}})
        # teeth, each rotated by the gear's own angle expression
        for k in range(teeth):
            base = k * 2 * math.pi / teeth
            cmds.append({"save": {"commands": [
                {"rotate": {"angle": "(%s + %.5f) * 57.29578" % (angvar, base),
                            "pivotX": cx, "pivotY": cy}},
                paint({"color": colour}, {"style": "fill"}),
                {"drawRoundRect": {"left": cx - 5.0, "top": cy - pr - 11.0,
                                   "right": cx + 5.0, "bottom": cy - pr + 5.0,
                                   "rx": 2.0, "ry": 2.0}},
            ]}})
        cmds.append(paint({"color": INK}, {"style": "fill"}))
        cmds.append({"drawCircle": {"cx": cx, "cy": cy, "radius": 16.0}})
        # a spoke, so the rotation is visible even where teeth blur together
        cmds.append({"save": {"commands": [
            {"rotate": {"angle": "%s * 57.29578" % angvar, "pivotX": cx, "pivotY": cy}},
            paint({"color": TEXT}, {"style": "stroke"}, {"width": 3.0},
                  {"strokeCap": "round"}),
            {"drawLine": {"x1": cx, "y1": cy, "x2": cx, "y2": cy - pr + 14.0}},
        ]}})

    cmds += text_at("25 teeth", g1[0], g1[1] + g1[3] + 30.0, 11.5, ACCENT, pan_x=0.0)
    cmds += text_at("15 teeth", g2[0], g2[1] + g2[3] + 30.0, 11.5, WARM, pan_x=0.0)
    cmds += text_at("ratio 5:3 - the small gear turns 1.67 times per turn of the large",
                    24.0, 338.0, 10.5, TEXT)
    cmds += text_at("one clock drives both; the second angle is the first times the ratio",
                    24.0, 356.0, 10.0, DIM)
    return {"header": header(W, H, "Two meshing gears turning at a 25:15 tooth ratio from a "
                                   "single clock"),
            "root": canvas(title(cmds, W, H, "Gear ratio", "25 teeth driving 15"))}


docs["ENG-ME-00002"] = gears()


# ── 14. ECO-MICR-00005  Market structures — particle-system / compare / 2D ────
# Four regimes as four populations of firms, and the encoding is the whole document:
#
#   one ball            = one firm
#   ball AREA           = that firm's market share
#   total area per panel = the same 100% market, in all four panels
#
# So radius goes as 1/sqrt(n): 70 firms share the market into slivers, one firm takes the
# lot, and the panels are directly comparable because the ink in each is equal.
#
# The first version of this document had two faults. The equations ACCUMULATED -
# `sx + sin(...) * 0.3` updates the stored position every frame, so it is an unbounded
# random walk and the balls wandered off their panels and across the display. The corpus's
# own snow example wraps every term with `% 400` for exactly this reason. Here the base
# position is an immutable particle variable and the wobble is applied at draw time, so
# motion is bounded by construction. And nothing said what a ball was, which is the other
# half of why it read as noise.
def market_structures():
    W, H = 540, 420
    PTOP, PBOT = 110.0, 300.0
    K = 42.0                                   # radius scale: r = K / sqrt(n)
    AMP = 7.0                                  # wobble amplitude, px
    panels = [("Perfect", 70, GOOD, 26.0),
              ("Monopolistic", 40, ACCENT, 156.0),
              ("Oligopoly", 5, WARM, 286.0),
              ("Monopoly", 1, HOT, 416.0)]
    PW = 98.0
    cmds = []
    for pi, (name, count, colour, x0) in enumerate(panels):
        r = K / math.sqrt(count)
        # Amplitude and containment are one decision, not two. The base position is spread
        # over whatever room is left after the radius AND the wobble, so a ball can never
        # reach its panel edge. The monopolist is 42 px in a 98 px panel and has only 5 px
        # of slack, so it wobbles less than the slivers do - which is also how it should
        # look: a firm that large does not move much.
        amp = max(1.5, min(AMP, PW / 2 - r - 2.0))
        cmds.append(paint({"color": PANEL}, {"style": "fill"}))
        cmds.append({"drawRect": {"left": x0, "top": PTOP,
                                  "right": x0 + PW, "bottom": PBOT}})
        cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
        cmds.append({"drawRect": {"left": x0, "top": PTOP,
                                  "right": x0 + PW, "bottom": PBOT}})

        sysid = "m%d" % pi
        if count == 1:
            init = ["%.2f" % (x0 + PW / 2), "%.2f" % ((PTOP + PBOT) / 2), "0.0"]
        else:
            mx = r + amp + 1.0
            init = ["%.2f + rand() * %.2f" % (x0 + mx, PW - 2 * mx),
                    "%.2f + rand() * %.2f" % (PTOP + mx, (PBOT - PTOP) - 2 * mx),
                    "rand()"]
        cmds.append({"createParticles": {
            "id": sysid,
            "variables": ["bx", "by", "tone", "ph"],
            "initialValues": init + ["rand() * 6.283"],
            "count": count}})
        # every equation returns its variable unchanged: the base position is fixed and the
        # only motion is the bounded wobble added at draw time
        alpha = "0.5 + tone * 0.5" if name == "Monopolistic" else "0.92"
        cmds.append({"particlesLoop": {
            "system": "@" + sysid,
            "equations": ["bx", "by", "tone", "ph"],
            "commands": [
                paint({"color": colour}, {"style": "fill"}, {"alpha": alpha}),
                {"drawCircle": {
                    "cx": "bx + sin(ph + animationTime * 3.4) * %.2f" % amp,
                    "cy": "by + cos(ph + animationTime * 3.0) * %.2f" % amp,
                    "radius": round(r, 2)}}]}})

        cmds += text_at(name, x0 + PW / 2, 100.0, 11.5, colour, pan_x=0.0)
        cmds += text_at("%d" % count, x0 + PW / 2, 328.0, 20.0, TEXT, pan_x=0.0)
        cmds += text_at("firm" if count == 1 else "firms", x0 + PW / 2, 346.0,
                        9.5, DIM, pan_x=0.0)
        share = 100.0 / count
        cmds += text_at("%.1f%% each" % share if count > 1 else "100% share",
                        x0 + PW / 2, 364.0, 9.5, colour, pan_x=0.0)

    cmds += text_at("one ball is one firm; its area is that firm's market share",
                    26.0, 392.0, 11.0, TEXT)
    cmds += text_at("every panel holds the same total area, so it is the same market "
                    "divided four ways", 26.0, 408.0, 10.0, DIM)
    return {"header": header(W, H, "Four market structures as firm populations, ball area "
                                   "showing market share and total area equal across panels"),
            "root": canvas(title(cmds, W, H, "Market structures",
                                 "the same market, split four ways"))}


docs["ECO-MICR-00005"] = market_structures()


# ── 15. ECO-MACR-00006  GDP — interactive / demonstrate / 2D ──────────────────
# C + I + G + NX, with one term under your finger. Demonstrating an identity works best when
# you can push on it and watch the total follow.
def gdp():
    W, H = 520, 380
    base = [("Consumption", 68.0, GOOD), ("Investment", 18.0, ACCENT),
            ("Government", 17.0, WARM), ("Net exports", -3.0, HOT)]
    left, width, top, barh = 40.0, 440.0, 120.0, 40.0
    cmds = []
    cmds.append({"touchExpression": {"name": "inv", "defaultValue": 18.0,
                                     "min": 2.0, "max": 34.0, "stopMode": "gently",
                                     "expression": "touchY() / 380 * 36"}})
    cmds.append(var("iv", "clamp(2.0, 34.0, @inv)"))
    cmds.append(var("tot", "68.0 + @iv + 17.0 - 3.0"))

    x = left
    for i, (name, share, colour) in enumerate(base):
        y = top + i * (barh + 12.0)
        expr = "@iv" if name == "Investment" else "%.1f" % abs(share)
        cmds.append(paint({"color": "#FF1B2740"}, {"style": "fill"}))
        cmds.append({"drawRoundRect": {"left": left, "top": y, "right": left + width,
                                       "bottom": y + barh, "rx": 5.0, "ry": 5.0}})
        cmds.append(paint({"color": colour}, {"style": "fill"},
                          {"alpha": 0.55 if share < 0 else 1.0}))
        cmds.append({"drawRoundRect": {"left": left, "top": y,
                                       "right": "%.1f + %s * %.2f" % (left, expr, width / 90.0),
                                       "bottom": y + barh, "rx": 5.0, "ry": 5.0}})
        cmds += text_at(name, left + 12.0, y + 26.0, 13.0, INK)
        if name == "Investment":
            cmds.append({"variable": {"name": "ivt",
                                      "value": {"type": "textFromFloat", "value": "@iv",
                                                "whole": 2, "decimal": 1}}})
            cmds.append(paint({"color": TEXT}, {"style": "fill"}, {"textSize": 13.0}))
            cmds.append({"drawTextAnchored": {"text": "@ivt", "x": left + width - 12.0,
                                              "y": y + 26.0, "panX": 1.0, "panY": 0.0,
                                              "flags": 0}})
        else:
            cmds += text_at("%.0f" % share, left + width - 12.0, y + 26.0, 13.0, DIM,
                            pan_x=1.0)

    cmds.append({"variable": {"name": "tt", "value": {"type": "textFromFloat",
                                                      "value": "@tot", "whole": 3,
                                                      "decimal": 1}}})
    cmds.append(paint({"color": TEXT}, {"style": "fill"}, {"textSize": 26.0}))
    cmds.append({"drawTextAnchored": {"text": "@tt", "x": left + width, "y": 342.0,
                                      "panX": 1.0, "panY": 0.0, "flags": 0}})
    cmds += text_at("GDP, % of a 100-unit economy", left, 342.0, 11.0, DIM)
    cmds += text_at("drag up and down to move investment", left, 360.0, 10.0, ACCENT)
    cmds += text_at("net exports are negative, so the bar is drawn faded",
                    left, 376.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "GDP as C plus I plus G plus NX, with investment under "
                                   "your finger and the total following"),
            "root": canvas(title(cmds, W, H, "GDP", "an identity you can push on"))}


docs["ECO-MACR-00006"] = gdp()


# ── 16. ECO-MACR-00007  Inflation — raster-and-text / demonstrate / 2D ────────
# The swapped slot, now where it belongs. A price list is a typographic object: the same
# basket priced across five decades, set in three weights, with the money column aligned.
BASKET = [("Loaf of bread", [0.22, 0.50, 1.00, 1.98, 2.89]),
          ("Litre of milk", [0.18, 0.41, 0.72, 1.12, 1.55]),
          ("Dozen eggs", [0.53, 0.88, 1.47, 2.30, 3.82]),
          ("Cinema ticket", [1.55, 2.69, 4.23, 7.89, 12.50]),
          ("Litre of petrol", [0.11, 0.33, 0.68, 1.02, 1.74])]
DECADES = [1980, 1990, 2000, 2010, 2020]


def inflation():
    W, H = 580, 380
    colx = [26.0, 250.0, 318.0, 386.0, 454.0, 522.0]
    cmds = []
    for i, d in enumerate(DECADES):
        cmds += text_at(str(d), colx[i + 1], 92.0, 11.0, DIM, pan_x=1.0)
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": 26.0, "y1": 100.0, "x2": 554.0, "y2": 100.0}})

    for ri, (name, prices) in enumerate(BASKET):
        y = 130.0 + ri * 40.0
        cmds += text_at(name, colx[0], y, 13.5, TEXT)
        for ci, p in enumerate(prices):
            last = ci == len(prices) - 1
            cmds += text_at("%.2f" % p, colx[ci + 1], y,
                            14.5 if last else 12.0,
                            WARM if last else "#FFB9C6E0", pan_x=1.0)
        if ri < len(BASKET) - 1:
            cmds.append(paint({"color": "#FF1B2740"}, {"style": "stroke"}, {"width": 1.0}))
            cmds.append({"drawLine": {"x1": 26.0, "y1": y + 14.0,
                                      "x2": 554.0, "y2": y + 14.0}})

    total = [sum(p[i] for _, p in BASKET) for i in range(5)]
    y = 130.0 + len(BASKET) * 40.0 + 6.0
    cmds.append(paint({"color": RULE}, {"style": "stroke"}, {"width": 1.0}))
    cmds.append({"drawLine": {"x1": 26.0, "y1": y - 18.0, "x2": 554.0, "y2": y - 18.0}})
    cmds += text_at("Basket", colx[0], y, 14.0, TEXT)
    for ci, t in enumerate(total):
        cmds += text_at("%.2f" % t, colx[ci + 1], y, 16.0 if ci == 4 else 12.5,
                        WARM if ci == 4 else DIM, pan_x=1.0)
    cmds += text_at("the same basket costs %.1f times what it did in 1980"
                    % (total[-1] / total[0]), 26.0, y + 34.0, 11.5, WARM)
    cmds += text_at("illustrative prices, one currency, five decades",
                    26.0, y + 52.0, 9.5, "#FF5E6E95")
    return {"header": header(W, H, "The same shopping basket priced across five decades, as "
                                   "a typographic table with the money column aligned"),
            "root": canvas(title(cmds, W, H, "Inflation", "what a basket costs"))}


docs["ECO-MACR-00007"] = inflation()


# ── write ───────────────────────────────────────────────────────────────────────
def main():
    for doc_id, doc in docs.items():
        (OUT / ("%s.json" % doc_id)).write_text(json.dumps(doc, indent=1) + "\n")
    print("  wrote %d documents to %s" % (len(docs), OUT.name))


if __name__ == "__main__":
    main()
