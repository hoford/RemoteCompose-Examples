#!/usr/bin/env python3
"""gen.py — generate the layout conformance corpus.

    python3 layout/gen.py [category-letter ...]

Documents are small and vary one axis at a time; see PLAN.md for the categories. They are
generated rather than hand-written because the point is systematic coverage of a matrix
(6 arrangements x 3 alignments, 3x3 box alignment, and so on), and because a
hand-maintained matrix drifts.
"""
import json, sys
from pathlib import Path
from collections import OrderedDict as OD

SRC = Path(__file__).resolve().parent / "src"
SRC.mkdir(parents=True, exist_ok=True)

BG = "#FF101828"
COLS = ["#FF4DA3FF", "#FFFFB020", "#FF4FD6C0", "#FFFF4D6D", "#FF8B5CF6"]


def doc(desc, root, w=400, h=400):
    return OD([
        ("header", OD([("apiLevel", 7), ("width", w), ("height", h), ("profiles", 513),
                       ("contentDescription", desc)])),
        ("root", root),
    ])


def box(mods=None, children=None, halign=None, valign=None, ctype="box"):
    o = OD([("type", ctype)])
    if mods: o["modifiers"] = mods
    # The parser reads `horizontalAlignment`/`verticalAlignment` (falling back to
    # `horizontalArrangement`/`verticalArrangement`). Using `horizontal`/`vertical` is
    # silently ignored, which makes every alignment document test the default and all
    # three engines "agree" on nothing.
    if halign: o["horizontalAlignment"] = halign
    if valign: o["verticalAlignment"] = valign
    if children is not None: o["children"] = children
    return o


def kid(w=None, h=None, colour=0, extra=None):
    mods = []
    if w is not None: mods.append({"width": w})
    if h is not None: mods.append({"height": h})
    mods.append({"background": COLS[colour % len(COLS)]})
    if extra: mods += extra
    return box(mods)


def write(name, d):
    (SRC / f"{name}.json").write_text(json.dumps(d, indent=2) + "\n")
    return name


# ── A. sizing ────────────────────────────────────────────────────────────────
def cat_a():
    n = []
    root = lambda kids, mods=None: box((mods or []) + [{"background": BG}], kids,
                                       "start", "top")
    n.append(write("a01_child_fixed", doc(
        "A01 fixed 120x80 child in a filled root",
        root([kid(120, 80)], ["fillMaxSize"]))))
    n.append(write("a02_child_fillmaxsize", doc(
        "A02 child fillMaxSize inside filled root",
        root([box(["fillMaxSize", {"background": COLS[0]}])], ["fillMaxSize"]))))
    n.append(write("a03_child_fillmaxwidth", doc(
        "A03 child fillMaxWidth, fixed height",
        root([box(["fillMaxWidth", {"height": 90}, {"background": COLS[0]}])],
             ["fillMaxSize"]))))
    n.append(write("a04_child_fillmaxheight", doc(
        "A04 child fillMaxHeight, fixed width",
        root([box(["fillMaxHeight", {"width": 90}, {"background": COLS[0]}])],
             ["fillMaxSize"]))))
    n.append(write("a05_fill_fraction", doc(
        "A05 fractional fill: 0.5 width, 0.25 height",
        root([box([{"fillMaxWidth": 0.5}, {"fillMaxHeight": 0.25},
                   {"background": COLS[0]}])], ["fillMaxSize"]))))
    n.append(write("a06_size_modifier", doc(
        "A06 size modifier as a pair",
        root([box([{"size": [140, 60]}, {"background": COLS[0]}])], ["fillMaxSize"]))))
    n.append(write("a07_wrap_default", doc(
        "A07 no size modifier anywhere: everything wraps",
        box([{"background": BG}], [kid(70, 40)], "start", "top"))))
    n.append(write("a08_fill_in_wrap_parent", doc(
        "A08 fillMaxSize child inside a WRAP parent - no maximum to fill",
        box([{"background": BG}],
            [box(["fillMaxSize", {"background": COLS[0]}])], "start", "top"))))
    n.append(write("a09_fixed_bigger_than_root", doc(
        "A09 child larger than the root",
        root([kid(520, 480)], ["fillMaxSize"]))))
    n.append(write("a11_child_exceeds_fixed_parent", doc(
        "A11 child larger than a fixed-size parent that is NOT the root, so overflow is visible",
        root([box([{"width": 200}, {"height": 140}, {"background": "#FF223049"}],
                  [kid(320, 260, 0)], "start", "top")], ["fillMaxSize"]))))
    n.append(write("a10_root_fixed_size", doc(
        "A10 root has a fixed size smaller than the document",
        box([{"width": 240}, {"height": 160}, {"background": BG}],
            [box(["fillMaxSize", {"background": COLS[0]}])], "start", "top"))))
    return n


# ── B. box alignment ─────────────────────────────────────────────────────────
def cat_b():
    n = []
    for i, ha in enumerate(["start", "center", "end"]):
        for j, va in enumerate(["top", "center", "bottom"]):
            n.append(write("b%02d_box_%s_%s" % (i * 3 + j + 1, ha, va), doc(
                "B box alignment %s/%s" % (ha, va),
                box(["fillMaxSize", {"background": BG}], [kid(100, 60)], ha, va))))
    n.append(write("b10_box_two_children", doc(
        "B10 two children of different size, centred - they stack",
        box(["fillMaxSize", {"background": BG}],
            [kid(160, 120, 0), kid(80, 50, 1)], "center", "center"))))
    n.append(write("b11_box_fixed_parent", doc(
        "B11 alignment inside a fixed-size box, not the root",
        box(["fillMaxSize", {"background": BG}],
            [box([{"width": 240}, {"height": 180}, {"background": "#FF223049"}],
                 [kid(60, 40)], "end", "bottom")], "center", "center"))))
    return n


# ── C. row: main-axis arrangement x cross-axis alignment ─────────────────────
# Children differ in both width and height so main-axis distribution and cross-axis
# alignment are each observable; equal-sized children would hide alignment entirely.
ROW_KIDS = [(60, 40, 0), (90, 70, 1), (50, 55, 2)]
# The two axes have *different* vocabularies. Horizontal accepts start/center/end,
# vertical accepts top/center/bottom; both accept the space* values. Passing "end" as a
# vertical arrangement is silently ignored and falls back to the default, which reads as
# "the engine ignores `end`" rather than "that token does not exist on this axis".
ARRANGE_H = ["start", "center", "end", "spaceBetween", "spaceEvenly", "spaceAround"]
ARRANGE_V = ["top", "center", "bottom", "spaceBetween", "spaceEvenly", "spaceAround"]
CROSS_V = ["top", "center", "bottom"]


def cat_c():
    n = []
    kids = [kid(w, h, c) for w, h, c in ROW_KIDS]
    for i, arr in enumerate(ARRANGE_H):
        n.append(write("c%02d_row_arrange_%s" % (i + 1, arr.lower()), doc(
            "C row horizontalArrangement=%s" % arr,
            box(["fillMaxSize", {"background": BG}], kids, arr, "top", ctype="row"))))
    for j, va in enumerate(CROSS_V):
        n.append(write("c%02d_row_valign_%s" % (7 + j, va), doc(
            "C row verticalAlignment=%s" % va,
            box(["fillMaxSize", {"background": BG}], kids, "start", va, ctype="row"))))
    n.append(write("c10_row_spacedby", doc(
        "C10 row with spacedBy 20",
        box(["fillMaxSize", {"spacedBy": 20}, {"background": BG}],
            kids, "start", "top", ctype="row"))))
    n.append(write("c11_row_wrap_width", doc(
        "C11 row that wraps its width - arrangement has no slack to distribute",
        box([{"background": BG}], kids, "spaceBetween", "top", ctype="row"))))
    n.append(write("c12_row_single_child_spacebetween", doc(
        "C12 spaceBetween with one child - degenerate case",
        box(["fillMaxSize", {"background": BG}], [kid(80, 50, 0)],
            "spaceBetween", "top", ctype="row"))))
    n.append(write("c13_row_fixed_height_children_fill", doc(
        "C13 children filling the cross axis inside a row",
        box(["fillMaxSize", {"background": BG}],
            [box([{"width": 70}, "fillMaxHeight", {"background": COLS[0]}]),
             box([{"width": 70}, {"height": 60}, {"background": COLS[1]}])],
            "start", "top", ctype="row"))))
    return n


# ── D. column: the same transposed ───────────────────────────────────────────
COL_KIDS = [(60, 40, 0), (90, 70, 1), (50, 55, 2)]
CROSS_H = ["start", "center", "end"]


def cat_d():
    n = []
    kids = [kid(w, h, c) for w, h, c in COL_KIDS]
    for i, arr in enumerate(ARRANGE_V):
        n.append(write("d%02d_col_arrange_%s" % (i + 1, arr.lower()), doc(
            "D column verticalArrangement=%s" % arr,
            box(["fillMaxSize", {"background": BG}], kids, "start", arr,
                ctype="column"))))
    for j, ha in enumerate(CROSS_H):
        n.append(write("d%02d_col_halign_%s" % (7 + j, ha), doc(
            "D column horizontalAlignment=%s" % ha,
            box(["fillMaxSize", {"background": BG}], kids, ha, "top",
                ctype="column"))))
    n.append(write("d10_col_spacedby", doc(
        "D10 column with spacedBy 20",
        box(["fillMaxSize", {"spacedBy": 20}, {"background": BG}],
            kids, "start", "top", ctype="column"))))
    n.append(write("d11_col_wrap_height", doc(
        "D11 column that wraps its height - arrangement has no slack",
        box([{"background": BG}], kids, "start", "spaceBetween", ctype="column"))))
    n.append(write("d12_col_single_child_spacebetween", doc(
        "D12 spaceBetween with one child - degenerate case",
        box(["fillMaxSize", {"background": BG}], [kid(80, 50, 0)],
            "start", "spaceBetween", ctype="column"))))
    n.append(write("d13_col_children_fill_width", doc(
        "D13 children filling the cross axis inside a column",
        box(["fillMaxSize", {"background": BG}],
            [box(["fillMaxWidth", {"height": 50}, {"background": COLS[0]}]),
             box([{"width": 120}, {"height": 50}, {"background": COLS[1]}])],
            "start", "top", ctype="column"))))
    return n


# ── E. weight ────────────────────────────────────────────────────────────────
# Weight distributes the space left after fixed-size siblings are measured, so every
# case here is really "what counts as slack".
def cat_e():
    n = []
    R = lambda kids, mods=None, ct="row", ha="start", va="top": box(
        (mods or []) + ["fillMaxSize", {"background": BG}], kids, ha, va, ctype=ct)
    wkid = lambda wt, c, extra=None: box(
        [{"weight": wt}, {"background": COLS[c]}] + (extra or []))

    n.append(write("e01_row_one_weight", doc(
        "E01 single weighted child takes the whole row",
        R([wkid(1, 0)]))))
    n.append(write("e02_row_two_equal", doc(
        "E02 two children, weight 1 and 1",
        R([wkid(1, 0), wkid(1, 1)]))))
    n.append(write("e03_row_two_unequal", doc(
        "E03 two children, weight 1 and 2",
        R([wkid(1, 0), wkid(2, 1)]))))
    n.append(write("e04_row_weight_beside_fixed", doc(
        "E04 fixed 100 beside weight 1 - the weighted child gets what is left",
        R([kid(100, 60, 3), wkid(1, 0)]))))
    n.append(write("e05_row_padding_on_row", doc(
        "E05 weights inside a padded row - slack is the padded width",
        R([wkid(1, 0), wkid(1, 1)], [{"padding": 30}]))))
    n.append(write("e06_row_padding_on_weighted_child", doc(
        "E06 padding on the weighted child itself",
        R([wkid(1, 0, [{"padding": 20}]), wkid(1, 1)]))))
    n.append(write("e07_row_weight_in_wrap_row", doc(
        "E07 weight inside a row that wraps its width - there is no slack to share",
        box([{"background": BG}], [wkid(1, 0), kid(80, 40, 1)], "start", "top",
            ctype="row"))))
    n.append(write("e08_col_vertical_weight", doc(
        "E08 verticalWeight in a column",
        R([box([{"verticalWeight": 1}, {"background": COLS[0]}]),
           box([{"verticalWeight": 3}, {"background": COLS[1]}])], ct="column"))))
    n.append(write("e09_col_horizontal_weight_wrong_axis", doc(
        "E09 horizontalWeight used in a column - weight on the cross axis",
        R([box([{"horizontalWeight": 1}, {"height": 60}, {"background": COLS[0]}]),
           box([{"horizontalWeight": 3}, {"height": 60}, {"background": COLS[1]}])],
          ct="column"))))
    n.append(write("e10_row_three_weights", doc(
        "E10 three children, weights 1, 2, 3",
        R([wkid(1, 0), wkid(2, 1), wkid(3, 2)]))))
    n.append(write("e11_row_weight_cross_fill", doc(
        "E11 weighted child also filling the cross axis",
        R([wkid(1, 0, ["fillMaxHeight"]), wkid(1, 1)]))))
    n.append(write("e12_row_fractional_weights", doc(
        "E12 fractional weights 0.5 and 1.5",
        R([wkid(0.5, 0), wkid(1.5, 1)]))))
    return n


# ── F. padding ───────────────────────────────────────────────────────────────
def cat_f():
    n = []
    root = lambda kids, mods=None: box((mods or []) + ["fillMaxSize", {"background": BG}],
                                       kids, "start", "top")
    n.append(write("f01_padding_uniform", doc(
        "F01 uniform padding on the root",
        root([box(["fillMaxSize", {"background": COLS[0]}])], [{"padding": 40}]))))
    n.append(write("f02_padding_per_side", doc(
        "F02 per-side padding object",
        root([box(["fillMaxSize", {"background": COLS[0]}])],
             [{"padding": {"start": 10, "top": 20, "end": 30, "bottom": 40}}]))))
    n.append(write("f03_padding_pair", doc(
        "F03 padding as [horizontal, vertical]",
        root([box(["fillMaxSize", {"background": COLS[0]}])], [{"padding": [25, 45]}]))))
    n.append(write("f04_padding_quad", doc(
        "F04 padding as [left, top, right, bottom]",
        root([box(["fillMaxSize", {"background": COLS[0]}])],
             [{"padding": [10, 20, 30, 40]}]))))
    n.append(write("f05_padding_on_child", doc(
        "F05 padding on the child, not the parent",
        root([box([{"width": 200}, {"height": 140}, {"padding": 30},
                   {"background": COLS[0]}],
                  [box(["fillMaxSize", {"background": COLS[1]}])], "start", "top")]))))
    n.append(write("f06_padding_nested", doc(
        "F06 padding at two levels",
        root([box(["fillMaxSize", {"padding": 30}, {"background": COLS[0]}],
                  [box(["fillMaxSize", {"background": COLS[1]}])], "start", "top")],
             [{"padding": 25}]))))
    n.append(write("f07_padding_then_fill", doc(
        "F07 does a filling child fill inside or outside the parent padding?",
        root([box(["fillMaxWidth", {"height": 80}, {"background": COLS[0]}])],
             [{"padding": 50}]))))
    n.append(write("f08_padding_exceeds_space", doc(
        "F08 padding larger than the box it is on",
        root([box([{"width": 100}, {"height": 60}, {"padding": 90},
                   {"background": COLS[0]}],
                  [box(["fillMaxSize", {"background": COLS[1]}])], "start", "top")]))))
    n.append(write("f09_padding_row_arrangement", doc(
        "F09 padding on a row changes the slack the arrangement distributes",
        box(["fillMaxSize", {"padding": 40}, {"background": BG}],
            [kid(60, 40, 0), kid(60, 40, 1)], "spaceBetween", "top", ctype="row"))))
    n.append(write("f10_padding_asymmetric_center", doc(
        "F10 centring inside an asymmetrically padded box",
        box(["fillMaxSize", {"padding": {"start": 100, "top": 0, "end": 0, "bottom": 0}},
             {"background": BG}], [kid(80, 60, 0)], "center", "center"))))
    return n


# ── G. constraints ───────────────────────────────────────────────────────────
def cat_g():
    n = []
    root = lambda kids: box(["fillMaxSize", {"background": BG}], kids, "start", "top")
    n.append(write("g01_widthin_min_forces_growth", doc(
        "G01 widthIn min larger than the requested width",
        root([box([{"width": 60}, {"widthIn": [200, 400]}, {"height": 60},
                   {"background": COLS[0]}])]))))
    n.append(write("g02_widthin_max_caps", doc(
        "G02 widthIn max smaller than the requested width",
        root([box([{"width": 300}, {"widthIn": [0, 120]}, {"height": 60},
                   {"background": COLS[0]}])]))))
    n.append(write("g03_widthin_within_range", doc(
        "G03 requested width already inside the range",
        root([box([{"width": 150}, {"widthIn": [100, 200]}, {"height": 60},
                   {"background": COLS[0]}])]))))
    n.append(write("g04_heightin_min_and_max", doc(
        "G04 heightIn clamping a requested height",
        root([box([{"width": 120}, {"height": 300}, {"heightIn": [0, 100]},
                   {"background": COLS[0]}])]))))
    n.append(write("g05_widthin_on_fill", doc(
        "G05 widthIn max applied to a filling child",
        root([box(["fillMaxWidth", {"widthIn": [0, 180]}, {"height": 60},
                   {"background": COLS[0]}])]))))
    n.append(write("g06_required_widthin", doc(
        "G06 requiredWidthIn - required constraints ignore the incoming ones",
        root([box([{"width": 60}, {"requiredWidthIn": [260, 400]}, {"height": 60},
                   {"background": COLS[0]}])]))))
    n.append(write("g07_required_heightin", doc(
        "G07 requiredHeightIn",
        root([box([{"width": 120}, {"height": 40}, {"requiredHeightIn": [180, 400]},
                   {"background": COLS[0]}])]))))
    n.append(write("g08_widthin_wrap_parent", doc(
        "G08 widthIn min inside a wrapping parent",
        box([{"background": BG}],
            [box([{"widthIn": [220, 400]}, {"height": 60}, {"background": COLS[0]}])],
            "start", "top"))))
    n.append(write("g09_dimension_constraints", doc(
        "G09 dimensionConstraints modifier",
        root([box([{"width": 90}, {"dimensionConstraints": {"min": 150, "max": 300}},
                   {"height": 60}, {"background": COLS[0]}])]))))
    n.append(write("g10_widthin_exceeds_parent", doc(
        "G10 widthIn min larger than the parent - does the parent still bound it?",
        root([box([{"width": 500}, {"widthIn": [0, 500]}, {"height": 60},
                   {"background": COLS[0]}])]))))
    return n


# ── H. nesting ───────────────────────────────────────────────────────────────
def cat_h():
    n = []
    ROOT = lambda kids, ha="start", va="top", ct="box", mods=None: box(
        (mods or []) + ["fillMaxSize", {"background": BG}], kids, ha, va, ctype=ct)
    panel = lambda kids, w=None, h=None, ha="start", va="top", ct="box", extra=None: box(
        ([{"width": w}] if w else []) + ([{"height": h}] if h else [])
        + [{"background": "#FF223049"}] + (extra or []), kids, ha, va, ctype=ct)

    n.append(write("h01_row_in_column", doc(
        "H01 a row nested inside a column",
        ROOT([panel([kid(50, 30, 0), kid(70, 30, 1)], h=60, ct="row"),
              kid(90, 40, 2)], ct="column"))))
    n.append(write("h02_column_in_row", doc(
        "H02 a column nested inside a row",
        ROOT([panel([kid(50, 30, 0), kid(50, 40, 1)], w=120, ct="column"),
              kid(60, 90, 2)], ct="row"))))
    n.append(write("h03_box_in_row_aligned", doc(
        "H03 a box inside a row, aligned within its own bounds",
        ROOT([panel([kid(40, 30, 0)], w=140, h=120, ha="center", va="center"),
              kid(60, 60, 2)], ct="row"))))
    n.append(write("h04_three_levels", doc(
        "H04 three levels of nesting, each inset",
        ROOT([panel([panel([kid(50, 40, 0)], w=160, h=120, ha="end", va="bottom")],
                    w=260, h=200, ha="center", va="center")], ha="center", va="center"))))
    n.append(write("h05_alignment_through_nesting", doc(
        "H05 outer centres, inner pushes to the end - alignment does not inherit",
        ROOT([panel([kid(40, 40, 0)], w=200, h=150, ha="end", va="bottom")],
             ha="center", va="center"))))
    n.append(write("h06_nested_fills", doc(
        "H06 fill inside fill inside a fixed box",
        ROOT([panel([box(["fillMaxSize", {"background": COLS[0]}],
                         [box(["fillMaxSize", {"background": COLS[1]}])],
                         "start", "top")], w=240, h=180)]))))
    n.append(write("h07_nested_weights", doc(
        "H07 a weighted row inside a weighted column",
        ROOT([box([{"verticalWeight": 1}, {"background": "#FF223049"}],
                  [box([{"weight": 1}, {"background": COLS[0]}]),
                   box([{"weight": 2}, {"background": COLS[1]}])],
                  "start", "top", ctype="row"),
              box([{"verticalWeight": 2}, {"background": COLS[2]}])], ct="column"))))
    n.append(write("h08_nested_padding_alignment", doc(
        "H08 padding at two levels with centring at both",
        ROOT([panel([kid(60, 40, 0)], w=240, h=180, ha="center", va="center",
                    extra=[{"padding": 30}])], ha="center", va="center",
             mods=[{"padding": 20}]))))
    n.append(write("h09_wrap_inside_fill", doc(
        "H09 a wrapping box inside a filling one",
        ROOT([box([{"background": "#FF223049"}], [kid(70, 50, 0)], "start", "top")]))))
    n.append(write("h10_row_of_columns", doc(
        "H10 a row of three columns, each with its own arrangement",
        ROOT([panel([kid(40, 30, 0), kid(40, 30, 1)], w=100, ct="column", va="top"),
              panel([kid(40, 30, 0), kid(40, 30, 1)], w=100, ct="column", va="center"),
              panel([kid(40, 30, 0), kid(40, 30, 1)], w=100, ct="column", va="bottom")],
             ct="row"))))
    return n


# ── I. overflow and clip ─────────────────────────────────────────────────────
def cat_i():
    n = []
    ROOT = lambda kids, ct="box": box(["fillMaxSize", {"background": BG}], kids,
                                      "start", "top", ctype=ct)
    n.append(write("i01_row_children_overflow", doc(
        "I01 row whose children total more than its width",
        ROOT([kid(180, 40, 0), kid(180, 40, 1), kid(180, 40, 2)], ct="row"))))
    n.append(write("i02_column_children_overflow", doc(
        "I02 column whose children total more than its height",
        ROOT([kid(60, 180, 0), kid(60, 180, 1), kid(60, 180, 2)], ct="column"))))
    n.append(write("i03_nested_overflow", doc(
        "I03 a grandchild larger than its grandparent",
        ROOT([box([{"width": 200}, {"height": 150}, {"background": "#FF223049"}],
                  [box([{"width": 320}, {"height": 260}, {"background": COLS[0]}])],
                  "start", "top")]))))
    n.append(write("i04_clip_oversized_child", doc(
        "I04 clip on a parent holding an oversized child",
        ROOT([box([{"width": 200}, {"height": 150}, {"clip": {"type": "rect"}},
                   {"background": "#FF223049"}],
                  [box([{"width": 320}, {"height": 260}, {"background": COLS[0]}])],
                  "start", "top")]))))
    n.append(write("i05_clip_with_padding", doc(
        "I05 clip combined with padding",
        ROOT([box([{"width": 220}, {"height": 160}, {"padding": 25},
                   {"clip": {"type": "rect"}}, {"background": "#FF223049"}],
                  [box(["fillMaxSize", {"background": COLS[0]}])], "start", "top")]))))
    n.append(write("i06_row_overflow_spacebetween", doc(
        "I06 overflowing row with spaceBetween - no slack, possibly negative",
        box(["fillMaxSize", {"background": BG}],
            [kid(180, 40, 0), kid(180, 40, 1), kid(180, 40, 2)],
            "spaceBetween", "top", ctype="row"))))
    return n


# ── J. layout-affecting modifiers ────────────────────────────────────────────
def cat_j():
    n = []
    ROOT = lambda kids, ct="box", ha="start", va="top", mods=None: box(
        (mods or []) + ["fillMaxSize", {"background": BG}], kids, ha, va, ctype=ct)
    n.append(write("j01_spacedby_with_center", doc(
        "J01 spacedBy combined with a centring arrangement",
        ROOT([kid(60, 40, 0), kid(60, 40, 1)], ct="row", ha="center",
             mods=[{"spacedBy": 30}]))))
    n.append(write("j02_spacedby_column", doc(
        "J02 spacedBy on a column",
        ROOT([kid(60, 40, 0), kid(60, 40, 1), kid(60, 40, 2)], ct="column",
             mods=[{"spacedBy": 25}]))))
    n.append(write("j03_offset", doc(
        "J03 offset modifier on a child",
        ROOT([box([{"width": 100}, {"height": 70}, {"offset": [40, 60]},
                   {"background": COLS[0]}])]))))
    n.append(write("j04_offset_negative", doc(
        "J04 negative offset pushing a child out of its parent",
        ROOT([box([{"width": 100}, {"height": 70}, {"offset": [-30, -20]},
                   {"background": COLS[0]}])]))))
    n.append(write("j05_visibility_gone", doc(
        "J05 a GONE child in a row - does it still take space?",
        ROOT([kid(60, 40, 0),
              box([{"width": 80}, {"height": 40}, {"visibility": 0},
                   {"background": COLS[1]}]),
              kid(60, 40, 2)], ct="row"))))
    n.append(write("j06_visibility_invisible", doc(
        "J06 an INVISIBLE child in a row - space should be kept",
        ROOT([kid(60, 40, 0),
              box([{"width": 80}, {"height": 40}, {"visibility": 2},
                   {"background": COLS[1]}]),
              kid(60, 40, 2)], ct="row"))))
    n.append(write("j07_zindex", doc(
        "J07 zIndex should reorder painting, not layout",
        ROOT([box([{"width": 120}, {"height": 90}, {"zIndex": 5},
                   {"background": COLS[0]}]),
              kid(120, 90, 1)], ct="row"))))
    n.append(write("j08_spacedby_exceeds", doc(
        "J08 spacedBy larger than the space left over",
        ROOT([kid(150, 40, 0), kid(150, 40, 1)], ct="row",
             mods=[{"spacedBy": 200}]))))
    return n


# ── K. text and intrinsic sizing ─────────────────────────────────────────────
# The headless Java reference measures every text component as 0x0 (NoOpPaintContext
# returns no metrics), so this category is arbitrated by the *phone*, which renders with
# real fonts. Every text carries a background so the painted block is exactly the
# component's computed bounds and can be recovered from a screenshot.
#
# Two different things are being compared here and they must not be conflated:
#   * container geometry - pure layout logic, must agree everywhere;
#   * the text's own measured size - font metrics, expected to differ between
#     node-canvas, Skia and the device.
LOREM = "Handgloves quickly vexed the wizard"


def cat_k():
    n = []
    ROOT = lambda kids, ct="box", ha="start", va="top": box(
        ["fillMaxSize", {"background": BG}], kids, ha, va, ctype=ct)
    txt = lambda v, mods=None, **kw: OD(
        [("type", "text"), ("text", v), ("color", "#FF0B1020"),
         ("fontSize", kw.pop("fontSize", 18))]
        + [(k, v2) for k, v2 in kw.items()]
        + [("modifiers", (mods or []) + [{"background": COLS[0]}])])

    n.append(write("k01_text_wrap", doc(
        "K01 text sizing itself - pure font metrics, expected to differ",
        ROOT([txt("Handgloves")]))))
    n.append(write("k02_text_in_fixed_box", doc(
        "K02 text inside a fixed 200-wide box - the BOX must be 200 everywhere",
        ROOT([box([{"width": 200}, {"height": 90}, {"background": "#FF223049"}],
                  [txt(LOREM)], "start", "top")]))))
    n.append(write("k03_text_maxlines_1", doc(
        "K03 maxLines 1 in a narrow box - height should be one line",
        ROOT([box([{"width": 160}, {"background": "#FF223049"}],
                  [txt(LOREM, maxLines=1)], "start", "top")]))))
    n.append(write("k04_text_maxlines_3", doc(
        "K04 the same text with maxLines 3 - height should be taller than K03",
        ROOT([box([{"width": 160}, {"background": "#FF223049"}],
                  [txt(LOREM, maxLines=3)], "start", "top")]))))
    n.append(write("k05_text_weight_in_row", doc(
        "K05 text with weight beside a fixed sibling - the weighted BOX is pure logic",
        ROOT([kid(120, 50, 3), txt("Weighted", mods=[{"weight": 1}])], ct="row"))))
    n.append(write("k06_text_padding", doc(
        "K06 padding around text inside a fixed box",
        ROOT([box([{"width": 240}, {"height": 100}, {"background": "#FF223049"}],
                  [txt("Padded", mods=[{"padding": 20}])], "start", "top")]))))
    n.append(write("k07_text_fontsize", doc(
        "K07 two font sizes stacked - relative heights should track the sizes",
        ROOT([txt("Small", fontSize=12), txt("Large", fontSize=30)], ct="column"))))
    n.append(write("k08_text_fill_width", doc(
        "K08 text filling the width - the box is logic, the wrapping is metrics",
        ROOT([box([{"width": 300}, {"background": "#FF223049"}],
                  [txt(LOREM + " " + LOREM, mods=["fillMaxWidth"])], "start", "top")]))))
    return n


def cat_l():
    """Flow segmentation with spacing.

    Nothing else in the corpus puts a non-zero `spacedBy` on a flow, so nothing else can
    catch a segmentation rule that ignores the spacing — the wrap point only moves once the
    accumulated spacing is enough to push a child past the edge. Sized so that it does:
    four 90-wide children in a 400-wide root fit on one row flush (360), and cannot once
    30 of spacing is added between them.
    """
    n = []
    ROOT = lambda kids, mods=None: box(
        (mods or []) + ["fillMaxSize", {"background": BG}], kids, ctype="flow")
    n.append(write("l01_flow_no_spacing", doc(
        "L01 flow, four children that exactly fit one row with no spacing",
        ROOT([kid(90, 40, i) for i in range(4)]))))
    n.append(write("l02_flow_spacedby_wraps", doc(
        "L02 same flow with spacedBy 30 - the spacing alone must force a wrap",
        ROOT([kid(90, 40, i) for i in range(4)], mods=[{"spacedBy": 30}]))))
    n.append(write("l03_flow_spacedby_large", doc(
        "L03 flow spacing larger than the children, so each row holds fewer",
        ROOT([kid(90, 40, i) for i in range(4)], mods=[{"spacedBy": 140}]))))
    return n


CATS = {"a": cat_a, "b": cat_b, "c": cat_c, "d": cat_d,
        "e": cat_e, "f": cat_f, "g": cat_g,
        "h": cat_h, "i": cat_i, "j": cat_j, "k": cat_k, "l": cat_l}

if __name__ == "__main__":
    want = [a.lower() for a in sys.argv[1:]] or sorted(CATS)
    made = []
    for c in want:
        if c not in CATS:
            print("no such category:", c); continue
        made += CATS[c]()
    print("generated %d documents: %s" % (len(made), ", ".join(made)))
