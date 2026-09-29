#!/usr/bin/env python3
"""Generate thirteen 2D charts as RemoteCompose JSON.

    python3 samples/json/charts2d/make.py
    python3 tools/rcbuild.py samples/json/charts2d/

Reconstructed from the Kotlin `graph2d` demos in androidx
(`.../demos/dsl/graph2d/demos/`), which drive a charting library of scales, ticks, axes and
marks. Nothing of that library is ported here: each chart is drawn directly with the same
2D primitives any document has — rects, lines, circles, sectors, paths and anchored text.

That is the point of the set. A chart is not a widget you need a framework for; it is a few
dozen `drawRect` calls with the arithmetic done up front. Everything below the `# charts`
divider is data and geometry, and an assistant can change any of it without understanding a
class hierarchy.

Colours, type sizes and spacing come from `GraphTheme.Light` and `GraphTheme.DefaultPalette`
in that library, so these sit beside the originals rather than merely resembling them.
"""

from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# ── theme, from GraphTheme.Light ──────────────────────────────────────────────────────
BG          = "#FFFFFFFF"
AXIS        = "#FF9AA0A6"
GRID        = "#FFECEEF1"
ZERO_LINE   = "#FFBDC1C6"
TITLE_C     = "#FF202124"
SUBTITLE_C  = "#FF5F6368"
LABEL_C     = "#FF5F6368"
AXIS_TITLE  = "#FF3C4043"
VALUE_C     = "#FF3C4043"

TITLE_SIZE, AXIS_TITLE_SIZE, LABEL_SIZE, VALUE_SIZE, LEGEND_SIZE = 34, 22, 20, 18, 20
AXIS_STROKE, GRID_STROKE = 1.5, 1.0

PALETTE = ["#FF4C78A8", "#FFF58518", "#FF54A24B", "#FFE45756", "#FF72B7B2",
           "#FFB279A2", "#FFFF9DA6", "#FF9D755D", "#FFEECA3B", "#FFBAB0AC"]
BLUES = ["#FFEFF6FB", "#FFB8D6EA", "#FF6BAED6", "#FF2E7EBC", "#FF08458A"]


# ── drawing helpers ───────────────────────────────────────────────────────────────────

def paint(color=None, style=None, width=None, text_size=None, alpha=1.0):
    """A paint block. `alpha` is always emitted, deliberately.

    Paint state is sticky: an op sets it and it stays set until something changes it. So a
    single translucent fill — the reference band in `annotations`, say — silently applied
    its alpha to every mark drawn afterwards, and the whole chart came out washed out.

    Worse, it did so on only one player. The C++ player renders that document solid while
    the TypeScript player honours the carried alpha, so the same bytes produce two different
    images. Rather than depend on which is right, every paint here states its own alpha and
    is therefore self-contained.
    """
    ops = []
    if color is not None:
        ops.append({"color": color})
    if style is not None:
        ops.append({"style": style})
    if width is not None:
        ops.append({"width": width})          # stroke width; the key is "width"
    if text_size is not None:
        ops.append({"textSize": text_size})
    ops.append({"alpha": alpha})
    return {"paint": {"ops": ops}}


def rect(x0, y0, x1, y1):
    return {"drawRect": {"left": x0, "top": y0, "right": x1, "bottom": y1}}


def line(x0, y0, x1, y1):
    return {"drawLine": {"x1": x0, "y1": y0, "x2": x1, "y2": y1}}


def circle(cx, cy, r):
    return {"drawCircle": {"cx": cx, "cy": cy, "radius": r}}


def sector(cx, cy, r, start_deg, sweep_deg):
    return {"drawSector": {"left": cx - r, "top": cy - r, "right": cx + r, "bottom": cy + r,
                           "startAngle": start_deg, "sweepAngle": sweep_deg}}


def text(s, x, y, pan_x=0.0, pan_y=0.0):
    """panX/panY anchor the string: -1 left/top, 0 centre, 1 right/bottom."""
    return {"drawTextAnchored": {"text": s, "x": x, "y": y,
                                 "panX": pan_x, "panY": pan_y, "flags": 0}}


def lerp_color(a: str, b: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    ca = [int(a[3 + 2 * i:5 + 2 * i], 16) for i in range(3)]
    cb = [int(b[3 + 2 * i:5 + 2 * i], 16) for i in range(3)]
    return "#FF%02X%02X%02X" % tuple(int(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))


def ramp_color(ramp, t: float) -> str:
    t = max(0.0, min(1.0, t)) * (len(ramp) - 1)
    i = min(int(t), len(ramp) - 2)
    return lerp_color(ramp[i], ramp[i + 1], t - i)


def nice_ticks(lo: float, hi: float, target: int = 5):
    """Round tick values covering [lo, hi] — the 1/2/5 x 10^n rule."""
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / target
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            step = m * mag
            break
    start = math.floor(lo / step) * step
    out, v = [], start
    while v <= hi + step * 0.5:
        out.append(round(v, 10))
        v += step
    return out


def fmt(v: float) -> str:
    return str(int(round(v))) if abs(v - round(v)) < 1e-9 else f"{v:g}"


class Plot:
    """A cartesian plot area with a title, gridlines and axes.

    Holds the pixel rectangle and the data ranges, and converts between them. Charts below
    build on this rather than repeating the arithmetic.
    """

    def __init__(self, w, h, title, subtitle=None, *, pad_l=76, pad_r=28, pad_t=104, pad_b=64):
        self.w, self.h = w, h
        self.x0, self.x1 = pad_l, w - pad_r
        self.y0, self.y1 = pad_t, h - pad_b
        self.cmds = [paint(BG, "fill"), rect(0, 0, w, h),
                     paint(TITLE_C, "fill", text_size=TITLE_SIZE),
                     text(title, pad_l, 46, -1.0, 0.0)]
        if subtitle:
            self.cmds += [paint(SUBTITLE_C, "fill", text_size=AXIS_TITLE_SIZE),
                          text(subtitle, pad_l, 70, -1.0, 0.0)]
        self.ylo, self.yhi = 0.0, 1.0

    # -- scales -----------------------------------------------------------------------
    def set_y(self, lo, hi):
        self.ylo, self.yhi = float(lo), float(hi)

    def py(self, v):
        t = (v - self.ylo) / (self.yhi - self.ylo or 1)
        return self.y1 - t * (self.y1 - self.y0)

    def px_band(self, i, n, inner=0.2, outer=0.1):
        """Centre and width of band i of n — the categorical x scale."""
        span = self.x1 - self.x0
        step = span / (n + 2 * outer)
        left = self.x0 + outer * step + i * step
        return left + step * 0.5, step * (1 - inner)

    def px_lin(self, v, lo, hi):
        return self.x0 + (v - lo) / (hi - lo or 1) * (self.x1 - self.x0)

    # -- furniture --------------------------------------------------------------------
    def y_grid(self, ticks=None, y_title=None):
        ticks = nice_ticks(self.ylo, self.yhi) if ticks is None else ticks
        for v in ticks:
            if not (self.ylo - 1e-9 <= v <= self.yhi + 1e-9):
                continue
            y = self.py(v)
            self.cmds += [paint(ZERO_LINE if abs(v) < 1e-9 else GRID, "stroke",
                                width=GRID_STROKE),
                          line(self.x0, y, self.x1, y),
                          paint(LABEL_C, "fill", text_size=LABEL_SIZE),
                          text(fmt(v), self.x0 - 10, y + 6, 1.0, 0.0)]
        if y_title:
            # Left-aligned above the plot rather than right-aligned outside it: anchored
            # into the left margin the longer titles ran off the canvas entirely.
            self.cmds += [paint(AXIS_TITLE, "fill", text_size=AXIS_TITLE_SIZE),
                          text(y_title, self.x0, self.y0 - 12, -1.0, 0.0)]

    def x_categories(self, names, x_title=None):
        self.cmds.append(paint(LABEL_C, "fill", text_size=LABEL_SIZE))
        for i, nm in enumerate(names):
            cx, _ = self.px_band(i, len(names))
            self.cmds.append(text(nm, cx, self.y1 + 26, 0.0, 0.0))
        if x_title:
            self.cmds += [paint(AXIS_TITLE, "fill", text_size=AXIS_TITLE_SIZE),
                          text(x_title, (self.x0 + self.x1) / 2, self.y1 + 54, 0.0, 0.0)]

    def axes(self):
        self.cmds += [paint(AXIS, "stroke", width=AXIS_STROKE),
                      line(self.x0, self.y0, self.x0, self.y1),
                      line(self.x0, self.y1, self.x1, self.y1)]

    def legend(self, entries, x=None, y=None):
        """entries: [(label, colour)] laid out left to right."""
        x = self.x1 if x is None else x
        y = self.y0 - 22 if y is None else y
        run = 0
        for label, col in reversed(entries):
            wpx = 12 + 8 + len(label) * LEGEND_SIZE * 0.55
            run += wpx + 16
        cx = x - run
        for label, col in entries:
            self.cmds += [paint(col, "fill"), rect(cx, y - 10, cx + 12, y + 2),
                          paint(LABEL_C, "fill", text_size=LEGEND_SIZE),
                          text(label, cx + 18, y + 2, -1.0, 0.0)]
            cx += 12 + 8 + len(label) * LEGEND_SIZE * 0.55 + 16

    def doc(self, name, desc):
        return {"header": {"apiLevel": 7, "width": self.w, "height": self.h,
                           "profiles": 513, "contentDescription": desc},
                "root": [{"box": {"modifiers": ["fillMaxSize"], "children": [
                    {"type": "canvas", "modifiers": ["fillMaxSize"],
                     "commands": self.cmds}]}}]}


def gaussian(n, mean, sd, seed):
    """The demos' generator, reproduced so the distribution charts use the same numbers."""
    s = seed
    def rnd():
        nonlocal s
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        return (s % 100000) / 100000.0
    out = []
    for _ in range(n):
        u1 = min(1.0, max(1e-4, rnd()))
        u2 = rnd()
        out.append(mean + sd * math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2))
    return out


def quartiles(xs):
    xs = sorted(xs)
    def q(p):
        i = p * (len(xs) - 1)
        lo = int(math.floor(i))
        return xs[lo] + (xs[min(lo + 1, len(xs) - 1)] - xs[lo]) * (i - lo)
    q1, med, q3 = q(0.25), q(0.5), q(0.75)
    iqr = q3 - q1
    lo = min(x for x in xs if x >= q1 - 1.5 * iqr)
    hi = max(x for x in xs if x <= q3 + 1.5 * iqr)
    return lo, q1, med, q3, hi


# ══ charts ════════════════════════════════════════════════════════════════════════════

MONTHS12 = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS8 = MONTHS12[:8]


def annotations():
    """Line with a reference band, target line, event marker and a callout."""
    vals = [31, 34, 33, 38, 41, 47, 52, 58, 54, 49, 51, 56]
    p = Plot(900, 560, "Weekly Active Users", "Annotated KPIs")
    p.set_y(25, 65)
    p.y_grid(y_title="Users (k)")

    # Goal zone behind everything, so the data reads on top of it.
    p.cmds += [paint("#FF54A24B", "fill", alpha=0.14),
               rect(p.x0, p.py(55), p.x1, p.py(45))]
    p.axes()

    pts = [(p.px_band(i, 12)[0], p.py(v)) for i, v in enumerate(vals)]
    p.cmds.append(paint(PALETTE[0], "stroke", width=2.5))
    for a, b in zip(pts, pts[1:]):
        p.cmds.append(line(a[0], a[1], b[0], b[1]))
    p.cmds.append(paint(PALETTE[0], "fill"))
    for x, y in pts:
        p.cmds.append(circle(x, y, 4))

    # Target line, event line, callout.
    p.cmds += [paint("#FFE45756", "stroke", width=2.0), line(p.x0, p.py(50), p.x1, p.py(50)),
               paint("#FFE45756", "fill", text_size=LABEL_SIZE),
               text("Target", p.x1 - 4, p.py(50) - 8, 1.0, 0.0)]
    ex = p.px_band(5, 12)[0]
    p.cmds += [paint(SUBTITLE_C, "stroke", width=1.5), line(ex, p.y0, ex, p.y1),
               paint(SUBTITLE_C, "fill", text_size=LABEL_SIZE),
               text("v2 launch", ex + 6, p.y0 + 16, -1.0, 0.0)]
    ax, ay = pts[7]
    p.cmds += [paint(VALUE_C, "stroke", width=1.5), line(ax, ay - 10, ax + 34, ay - 40),
               paint(VALUE_C, "fill", text_size=VALUE_SIZE),
               text("All-time high", ax + 38, ay - 36, -1.0, 0.0)]
    p.x_categories(MONTHS12)
    return "annotations", p.doc("annotations", "Annotated KPI line chart")


def bar_grouped():
    regions = ["North", "South", "East", "West", "Central"]
    series = [("2022", [18, 12, 9, 14, 7]),
              ("2023", [22, 15, 11, 13, 9]),
              ("2024", [26, 19, 16, 18, 12])]
    p = Plot(900, 520, "Sales by Region")
    p.set_y(0, 28)
    p.y_grid(y_title="Units (k)")
    p.axes()
    for i in range(len(regions)):
        cx, bw = p.px_band(i, len(regions))
        sub = bw / len(series)
        for s, (_, vals) in enumerate(series):
            x = cx - bw / 2 + s * sub
            p.cmds += [paint(PALETTE[s], "fill"),
                       rect(x + 1, p.py(vals[i]), x + sub - 1, p.py(0))]
    p.x_categories(regions)
    p.legend([(n, PALETTE[i]) for i, (n, _) in enumerate(series)])
    return "bar_grouped", p.doc("bar_grouped", "Grouped bar chart, sales by region")


def box_plot():
    groups = [("Control", gaussian(60, 50, 9, 3)), ("Low", gaussian(60, 56, 7, 11)),
              ("Medium", gaussian(60, 62, 11, 23)), ("High", gaussian(60, 68, 8, 41))]
    p = Plot(800, 520, "Response by Treatment")
    stats = [quartiles(v) for _, v in groups]
    p.set_y(min(s[0] for s in stats) - 4, max(s[4] for s in stats) + 4)
    p.y_grid(y_title="Score")
    p.axes()
    for i, (lo, q1, med, q3, hi) in enumerate(stats):
        cx, bw = p.px_band(i, len(groups), inner=0.45)
        col = PALETTE[i]
        p.cmds += [paint(AXIS, "stroke", width=1.5),
                   line(cx, p.py(lo), cx, p.py(hi)),
                   line(cx - bw * 0.2, p.py(lo), cx + bw * 0.2, p.py(lo)),
                   line(cx - bw * 0.2, p.py(hi), cx + bw * 0.2, p.py(hi)),
                   paint(col, "fill", alpha=0.35),
                   rect(cx - bw / 2, p.py(q3), cx + bw / 2, p.py(q1)),
                   paint(col, "stroke", width=2.0),
                   rect(cx - bw / 2, p.py(q3), cx + bw / 2, p.py(q1)),
                   line(cx - bw / 2, p.py(med), cx + bw / 2, p.py(med))]
    p.x_categories([n for n, _ in groups])
    return "box_plot", p.doc("box_plot", "Box plot, response by treatment")


def heatmap():
    cols = ["6a", "9a", "12p", "3p", "6p", "9p", "12a"]
    rows = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    data = [[2, 8, 14, 11, 9, 5, 1], [3, 9, 16, 13, 10, 6, 2], [4, 10, 18, 15, 12, 7, 2],
            [3, 11, 17, 14, 13, 9, 3], [5, 13, 20, 18, 16, 12, 6]]
    p = Plot(820, 520, "Sessions by Day x Hour", pad_l=90, pad_t=96, pad_b=52)
    hi = max(max(r) for r in data)
    cw = (p.x1 - p.x0) / len(cols)
    ch = (p.y1 - p.y0) / len(rows)
    for r, row in enumerate(data):
        for c, v in enumerate(row):
            x, y = p.x0 + c * cw, p.y0 + r * ch
            p.cmds += [paint(ramp_color(BLUES, v / hi), "fill"),
                       rect(x + 1, y + 1, x + cw - 1, y + ch - 1),
                       # Dark text on the pale end, light on the deep end.
                       paint("#FFFFFFFF" if v / hi > 0.55 else VALUE_C, "fill",
                             text_size=VALUE_SIZE),
                       text(str(v), x + cw / 2, y + ch / 2 + 6, 0.0, 0.0)]
    p.cmds.append(paint(LABEL_C, "fill", text_size=LABEL_SIZE))
    for c, nm in enumerate(cols):
        p.cmds.append(text(nm, p.x0 + (c + 0.5) * cw, p.y1 + 26, 0.0, 0.0))
    for r, nm in enumerate(rows):
        p.cmds.append(text(nm, p.x0 - 12, p.y0 + (r + 0.5) * ch + 6, 1.0, 0.0))
    return "heatmap", p.doc("heatmap", "Heatmap of sessions by day and hour")


def waffle():
    parts = [("Solar", 38), ("Wind", 27), ("Hydro", 18), ("Gas", 12), ("Other", 5)]
    p = Plot(640, 680, "Energy Mix", pad_l=48, pad_r=48, pad_t=86, pad_b=150)
    side, gap = 10, 6
    cell = min((p.x1 - p.x0) / side, (p.y1 - p.y0) / side)
    seq = []
    for i, (_, n) in enumerate(parts):
        seq += [i] * n
    for k in range(100):
        r, c = k // side, k % side
        col = PALETTE[seq[k]] if k < len(seq) else "#FFECEEF1"
        x, y = p.x0 + c * cell, p.y0 + r * cell
        p.cmds += [paint(col, "fill"),
                   {"drawRoundRect": {"left": x, "top": y, "right": x + cell - gap,
                                      "bottom": y + cell - gap, "rx": 3, "ry": 3}}]
    ly = p.y1 + 34
    for i, (nm, n) in enumerate(parts):
        p.cmds += [paint(PALETTE[i], "fill"), rect(p.x0, ly - 11, p.x0 + 13, ly + 2),
                   paint(LABEL_C, "fill", text_size=LEGEND_SIZE),
                   text(f"{nm}  {n}%", p.x0 + 21, ly + 2, -1.0, 0.0)]
        ly += 24
    return "waffle", p.doc("waffle", "Waffle chart of energy mix")


def waterfall():
    steps = [("Q1 Start", 100), ("New Sales", 45), ("Churn", -20),
             ("Upsell", 30), ("Refunds", -15)]
    p = Plot(820, 520, "Revenue Bridge")
    running, tops = 0, []
    for i, (_, v) in enumerate(steps):
        base = 0 if i == 0 else running
        running = base + v
        tops.append((base, running))
    p.set_y(0, 160)
    # "$M" would be rejected: a leading $ marks a variable reference, so a literal string
    # starting with one has to be written differently.
    p.y_grid(y_title="USD (M)")
    p.axes()
    for i, ((_, v), (base, top)) in enumerate(zip(steps, tops)):
        cx, bw = p.px_band(i, len(steps))
        col = PALETTE[0] if i == 0 else (PALETTE[2] if v > 0 else PALETTE[3])
        lo, hi = min(base, top), max(base, top)
        p.cmds += [paint(col, "fill"), rect(cx - bw / 2, p.py(hi), cx + bw / 2, p.py(lo)),
                   paint(VALUE_C, "fill", text_size=VALUE_SIZE),
                   text(("+" if v > 0 and i else "") + str(v), cx, p.py(hi) - 8, 0.0, 0.0)]
        if i < len(steps) - 1:   # connector to the next bar's base
            nx, nbw = p.px_band(i + 1, len(steps))
            p.cmds += [paint(ZERO_LINE, "stroke", width=1.5),
                       line(cx + bw / 2, p.py(top), nx - nbw / 2, p.py(top))]
    p.x_categories([n for n, _ in steps])
    return "waterfall", p.doc("waterfall", "Waterfall / revenue bridge chart")


def bullet():
    items = [("Revenue", 78, 85, [50, 75, 100]), ("Profit", 62, 70, [40, 70, 100]),
             ("CSAT", 88, 80, [60, 80, 100]), ("Retention", 71, 75, [50, 80, 100])]
    p = Plot(760, 420, "KPIs vs Target", pad_l=120, pad_r=40, pad_b=52)
    rowh = (p.y1 - p.y0) / len(items)
    for i, (nm, val, target, bands) in enumerate(items):
        cy = p.y0 + (i + 0.5) * rowh
        h = rowh * 0.42
        prev = 0
        for b, edge in enumerate(bands):     # qualitative bands, palest first
            x0 = p.px_lin(prev, 0, 100)
            x1 = p.px_lin(edge, 0, 100)
            p.cmds += [paint(ramp_color(["#FFEFEFEF", "#FFDADCE0"], b / (len(bands) - 1)),
                             "fill"),
                       rect(x0, cy - h, x1, cy + h)]
            prev = edge
        p.cmds += [paint(PALETTE[0], "fill"),
                   rect(p.x0, cy - h * 0.42, p.px_lin(val, 0, 100), cy + h * 0.42),
                   paint(VALUE_C, "stroke", width=3.0),
                   line(p.px_lin(target, 0, 100), cy - h, p.px_lin(target, 0, 100), cy + h),
                   paint(AXIS_TITLE, "fill", text_size=LABEL_SIZE),
                   text(nm, p.x0 - 12, cy + 6, 1.0, 0.0)]
    p.cmds.append(paint(LABEL_C, "fill", text_size=LABEL_SIZE))
    for v in (0, 25, 50, 75, 100):
        p.cmds.append(text(str(v), p.px_lin(v, 0, 100), p.y1 + 26, 0.0, 0.0))
    return "bullet", p.doc("bullet", "Bullet chart, KPIs against target")


def forest():
    rows = [("Study A", 0.30, 0.10, 0.50, 20), ("Study B", -0.10, -0.40, 0.20, 15),
            ("Study C", 0.50, 0.20, 0.80, 10), ("Study D", 0.20, 0.05, 0.35, 30),
            ("Study E", 0.00, -0.20, 0.20, 8), ("Pooled", 0.22, 0.12, 0.32, 45)]
    p = Plot(820, 520, "Treatment Effect (meta-analysis)", pad_l=130, pad_r=96, pad_b=64)
    lo, hi = -0.5, 0.9
    rowh = (p.y1 - p.y0) / len(rows)
    zx = p.px_lin(0, lo, hi)
    p.cmds += [paint(ZERO_LINE, "stroke", width=1.5), line(zx, p.y0, zx, p.y1)]
    for i, (nm, est, l, h, wt) in enumerate(rows):
        cy = p.y0 + (i + 0.5) * rowh
        pooled = nm == "Pooled"
        col = PALETTE[3] if pooled else PALETTE[0]
        p.cmds += [paint(col, "stroke", width=2.0),
                   line(p.px_lin(l, lo, hi), cy, p.px_lin(h, lo, hi), cy),
                   paint(col, "fill"),
                   # Marker area scales with study weight, as a forest plot should.
                   circle(p.px_lin(est, lo, hi), cy, 4 + math.sqrt(wt) * 1.1),
                   paint(AXIS_TITLE, "fill", text_size=LABEL_SIZE),
                   text(nm, p.x0 - 12, cy + 6, 1.0, 0.0),
                   paint(VALUE_C, "fill", text_size=VALUE_SIZE),
                   text(f"{est:+.2f}", p.x1 + 6, cy + 6, -1.0, 0.0)]
    p.cmds.append(paint(LABEL_C, "fill", text_size=LABEL_SIZE))
    for v in (-0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8):
        p.cmds.append(text(f"{v:g}", p.px_lin(v, lo, hi), p.y1 + 26, 0.0, 0.0))
    p.cmds += [paint(AXIS_TITLE, "fill", text_size=AXIS_TITLE_SIZE),
               text("Effect size (log OR)", (p.x0 + p.x1) / 2, p.y1 + 54, 0.0, 0.0)]
    return "forest", p.doc("forest", "Forest plot of a meta-analysis")


def area_stacked():
    series = [("Organic", [20, 22, 24, 26, 30, 28, 33, 36]),
              ("Paid", [12, 14, 13, 18, 20, 22, 21, 25]),
              ("Referral", [6, 7, 9, 8, 11, 13, 12, 15])]
    p = Plot(900, 520, "Traffic by Source")
    n = len(MONTHS8)
    totals = [sum(s[1][i] for s in series) for i in range(n)]
    p.set_y(0, 80)
    p.y_grid(y_title="Sessions (k)")
    p.axes()
    base = [0.0] * n
    for s, (_, vals) in enumerate(series):
        top = [base[i] + vals[i] for i in range(n)]
        # Filled with quads between adjacent samples: no path op needed, and every player
        # draws rects and lines identically.
        for i in range(n - 1):
            x0, _ = p.px_band(i, n)
            x1, _ = p.px_band(i + 1, n)
            steps = 12
            for k in range(steps):
                t0, t1 = k / steps, (k + 1) / steps
                xa = x0 + (x1 - x0) * t0
                xb = x0 + (x1 - x0) * t1
                ya = p.py(base[i] + (base[i + 1] - base[i]) * t0)
                yb = p.py(top[i] + (top[i + 1] - top[i]) * t0)
                p.cmds += [paint(PALETTE[s], "fill", alpha=0.85), rect(xa, yb, xb + 1, ya)]
        p.cmds.append(paint(PALETTE[s], "stroke", width=2.0))
        for i in range(n - 1):
            x0, _ = p.px_band(i, n)
            x1, _ = p.px_band(i + 1, n)
            p.cmds.append(line(x0, p.py(top[i]), x1, p.py(top[i + 1])))
        base = top
    p.x_categories(MONTHS8)
    p.legend([(nm, PALETTE[i]) for i, (nm, _) in enumerate(series)])
    return "area_stacked", p.doc("area_stacked", "Stacked area chart, traffic by source")


def gantt():
    tasks = [("Research", 0, 6), ("Design", 5, 12), ("Build", 11, 24),
             ("Test", 22, 30), ("Launch", 29, 33)]
    p = Plot(840, 520, "Project Schedule", pad_l=120, pad_b=64)
    lo, hi = 0, 34
    rowh = (p.y1 - p.y0) / len(tasks)
    for v in range(0, hi + 1, 5):
        x = p.px_lin(v, lo, hi)
        p.cmds += [paint(GRID, "stroke", width=GRID_STROKE), line(x, p.y0, x, p.y1),
                   paint(LABEL_C, "fill", text_size=LABEL_SIZE),
                   text(str(v), x, p.y1 + 26, 0.0, 0.0)]
    for i, (nm, s, e) in enumerate(tasks):
        cy = p.y0 + (i + 0.5) * rowh
        h = rowh * 0.3
        p.cmds += [paint(PALETTE[i % len(PALETTE)], "fill"),
                   {"drawRoundRect": {"left": p.px_lin(s, lo, hi), "top": cy - h,
                                      "right": p.px_lin(e, lo, hi), "bottom": cy + h,
                                      "rx": 5, "ry": 5}},
                   paint(AXIS_TITLE, "fill", text_size=LABEL_SIZE),
                   text(nm, p.x0 - 12, cy + 6, 1.0, 0.0)]
    p.axes()
    p.cmds += [paint(AXIS_TITLE, "fill", text_size=AXIS_TITLE_SIZE),
               text("Day", (p.x0 + p.x1) / 2, p.y1 + 54, 0.0, 0.0)]
    return "gantt", p.doc("gantt", "Gantt chart of a project schedule")


def rose():
    items = list(zip(MONTHS12, [42, 38, 55, 70, 88, 110, 120, 105, 82, 60, 48, 40]))
    p = Plot(640, 640, "Monthly Rainfall (mm)", pad_l=40, pad_r=40, pad_b=40)
    cx, cy = p.w / 2, p.h / 2 + 20
    rmax = 230
    hi = max(v for _, v in items)
    for rr in (0.25, 0.5, 0.75, 1.0):     # polar gridlines
        p.cmds += [paint(GRID, "stroke", width=GRID_STROKE),
                   {"drawOval": {"left": cx - rmax * rr, "top": cy - rmax * rr,
                                 "right": cx + rmax * rr, "bottom": cy + rmax * rr}}]
    step = 360 / len(items)
    for i, (nm, v) in enumerate(items):
        r = rmax * (v / hi) ** 0.5      # area-proportional, as a rose should be
        a0 = -90 + i * step
        p.cmds += [paint(ramp_color([PALETTE[4], PALETTE[0]], v / hi), "fill"),
                   sector(cx, cy, r, a0 + 1, step - 2)]
        ang = math.radians(a0 + step / 2)
        lx, ly = cx + math.cos(ang) * (rmax + 22), cy + math.sin(ang) * (rmax + 22)
        p.cmds += [paint(LABEL_C, "fill", text_size=LABEL_SIZE), text(nm, lx, ly + 6, 0.0, 0.0)]
    return "rose", p.doc("rose", "Rose / polar area chart of monthly rainfall")


def radar():
    axes = ["Speed", "Battery", "Camera", "Price", "Display", "Support"]
    series = [("Model X", [8, 6, 9, 5, 8, 7]), ("Model Y", [6, 9, 6, 8, 7, 5])]
    p = Plot(680, 680, "Product Comparison", pad_l=40, pad_r=40, pad_b=40)
    cx, cy, rmax, mx = p.w / 2, p.h / 2 + 10, 220, 10
    n = len(axes)
    def pt(i, v):
        a = math.radians(-90 + i * 360 / n)
        r = rmax * v / mx
        return cx + math.cos(a) * r, cy + math.sin(a) * r
    for ring in (0.25, 0.5, 0.75, 1.0):     # web
        ring_pts = [pt(i, mx * ring) for i in range(n)]
        p.cmds.append(paint(GRID, "stroke", width=GRID_STROKE))
        for a, b in zip(ring_pts, ring_pts[1:] + ring_pts[:1]):
            p.cmds.append(line(a[0], a[1], b[0], b[1]))
    p.cmds.append(paint(GRID, "stroke", width=GRID_STROKE))
    for i in range(n):
        x, y = pt(i, mx)
        p.cmds.append(line(cx, cy, x, y))
    for s, (_, vals) in enumerate(series):
        poly = [pt(i, v) for i, v in enumerate(vals)]
        p.cmds.append(paint(PALETTE[s], "stroke", width=2.5))
        for a, b in zip(poly, poly[1:] + poly[:1]):
            p.cmds.append(line(a[0], a[1], b[0], b[1]))
        p.cmds.append(paint(PALETTE[s], "fill"))
        for x, y in poly:
            p.cmds.append(circle(x, y, 4))
    p.cmds.append(paint(LABEL_C, "fill", text_size=LABEL_SIZE))
    for i, nm in enumerate(axes):
        x, y = pt(i, mx * 1.14)
        p.cmds.append(text(nm, x, y + 6, 0.0, 0.0))
    p.legend([(nm, PALETTE[i]) for i, (nm, _) in enumerate(series)], x=p.x1, y=p.y0 - 14)
    return "radar", p.doc("radar", "Radar chart comparing two products")


def bubble():
    pts = [(20, 35, 8), (35, 52, 30), (48, 41, 14), (55, 70, 55),
           (62, 58, 22), (74, 84, 70), (81, 66, 40), (40, 28, 12)]
    p = Plot(720, 560, "Market Map")
    p.set_y(0, 100)
    p.y_grid(y_title="Satisfaction")
    for v in range(0, 101, 20):
        x = p.px_lin(v, 0, 100)
        p.cmds += [paint(GRID, "stroke", width=GRID_STROKE), line(x, p.y0, x, p.y1),
                   paint(LABEL_C, "fill", text_size=LABEL_SIZE),
                   text(str(v), x, p.y1 + 26, 0.0, 0.0)]
    p.axes()
    smax = max(s for _, _, s in pts)
    for i, (x, y, s) in enumerate(pts):
        r = 5 + math.sqrt(s / smax) * 34      # area-proportional radius
        p.cmds += [paint(PALETTE[i % len(PALETTE)], "fill", alpha=0.55),
                   circle(p.px_lin(x, 0, 100), p.py(y), r)]
    p.cmds += [paint(AXIS_TITLE, "fill", text_size=AXIS_TITLE_SIZE),
               text("Growth (%)", (p.x0 + p.x1) / 2, p.y1 + 54, 0.0, 0.0)]
    return "bubble", p.doc("bubble", "Bubble chart, market map")


CHARTS = [annotations, bar_grouped, box_plot, heatmap, waffle, waterfall, bullet,
          forest, area_stacked, gantt, rose, radar, bubble]


def main() -> None:
    for fn in CHARTS:
        name, doc = fn()
        path = os.path.join(HERE, name + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1)
        n = len(doc["root"][0]["box"]["children"][0]["commands"])
        print(f"  {name:14s} {doc['header']['width']}x{doc['header']['height']}"
              f"  {n:5d} commands")
    print(f"\n  {len(CHARTS)} charts written — now:"
          f" python3 tools/rcbuild.py samples/json/charts2d/")


if __name__ == "__main__":
    main()
