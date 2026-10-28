#!/usr/bin/env python3
"""check_hairspring — verify the coil from the document it ships, not the code.

The hairspring is the one part here whose motion is not a rotation, which means it is the
one part where a shape can be wrong while every endpoint is right. The first version was
exactly that: both ends landed where they should, the wrap grew and shrank with the
balance, and it still drew a spring made of wire that got four percent longer when you
wound it. Nothing about the endpoints would ever have told you.

So this evaluates the path expression the document actually carries, at points across a
full swing of the balance, and asks five things of the curve itself:

  1. pinned inside   — the inner end sits ON the collet, at every point of the swing, so
                       the wire is attached to the pole rather than floating near it
  2. pinned outside  — the outer end finishes inside the stud, not somewhere else on the
                       same circle; a whole number of turns is what puts it there
  3. inextensible    — the wire is the same length wound up as unwound
  4. breathes        — the middle of the coil genuinely moves in and out, and in the right
                       direction: anticlockwise at the inner end means tighter AND inward
  5. no collisions   — neighbouring turns never touch, at either end of the swing

Run with --selftest. Seven breaks, and the first of them is the original model — if this
checker cannot fail on the bug it was written for, it is not a checker.
"""

import argparse
import copy
import importlib.util
import json
import math
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE

_cg = importlib.util.spec_from_file_location("expr", HERE / "expr.py")
CG = importlib.util.module_from_spec(_cg)
_cg.loader.exec_module(CG)

_cw = importlib.util.spec_from_file_location("check_watch", HERE / "check_watch.py")
CW = importlib.util.module_from_spec(_cw)
_cw.loader.exec_module(CW)

DOC = ROOT / "out" / "hairspring.json"

SAMPLES = 3000
FAILURES = []


def check(cond, msg):
    if not cond:
        FAILURES.append(msg)
    return bool(cond)


# ── reading the document ─────────────────────────────────────────────────────

def commands(doc):
    return doc["root"][0]["box"]["children"][0]["commands"]


def variables(doc):
    return {c["variable"]["name"]: c["variable"]["value"]
            for c in commands(doc) if "variable" in c}


def path_expression(doc):
    for c in commands(doc):
        if "pathExpression" in c:
            return c["pathExpression"]
    return None


def circles(doc):
    """Every drawn path that is actually a circle, as (centre, radius, points).

    Used to find the collet and the stud without being told which is which: the wire has
    to start on one of them and finish inside another, and that is the whole test.
    """
    out = []
    for c in commands(doc):
        if "drawPath" not in c:
            continue
        p = c["drawPath"]["path"]
        if not isinstance(p, str) or not p.startswith("M"):
            continue
        pts = CW.parse_path(p)
        if len(pts) < 8:
            continue
        cx = sum(x for x, _ in pts) / len(pts)
        cy = sum(y for _, y in pts) / len(pts)
        rs = [math.hypot(x - cx, y - cy) for x, y in pts]
        if max(rs) - min(rs) < 0.5:
            out.append(((cx, cy), sum(rs) / len(rs), len(pts)))
    return out


def curve(pe, vars_, t, n=SAMPLES):
    """The coil at time t, as points. `a[0]` is the sweep parameter."""
    ex = str(pe["expressionX"]).replace("a[0]", "s")
    ey = str(pe["expressionY"]).replace("a[0]", "s")
    lo, hi = float(pe.get("start", 0)), float(pe.get("end", 1))
    pts = []
    env = dict(vars_)
    for k in range(n):
        env["s"] = lo + (hi - lo) * k / (n - 1.0)
        pts.append((CG.evaluate(ex, env, t), CG.evaluate(ey, env, t)))
    return pts


def polyline_length(pts):
    return sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
               for i in range(len(pts) - 1))


def radii(pts, centre):
    return [math.hypot(x - centre[0], y - centre[1]) for x, y in pts]


def min_turn_gap(pts, centre):
    """Smallest radial distance between one turn and the next.

    Walk the coil, and for each point find where it was exactly one turn earlier by
    bearing. If the gap ever reaches zero the coils are touching, which for a real spring
    means it has gone solid and stopped being a spring.
    """
    cx, cy = centre
    ang, rad, unwrapped = [], [], 0.0
    prev = None
    for x, y in pts:
        a = math.atan2(y - cy, x - cx)
        if prev is not None:
            d = a - prev
            while d > math.pi:
                d -= 2 * math.pi
            while d < -math.pi:
                d += 2 * math.pi
            unwrapped += d
        else:
            unwrapped = a
        prev = a
        ang.append(unwrapped)
        rad.append(math.hypot(x - cx, y - cy))

    worst = 1e9
    j = 0
    turn = 2 * math.pi if ang[-1] > ang[0] else -2 * math.pi
    for i in range(len(ang)):
        target = ang[i] + turn
        while j < len(ang) - 1 and ((ang[j] < target) == (turn > 0)):
            j += 1
        if j <= i or j >= len(ang) - 1:
            continue
        worst = min(worst, abs(rad[j] - rad[i]))
    return worst


# ── the checks ───────────────────────────────────────────────────────────────

def run(doc, verbose=True):
    del FAILURES[:]

    def say(*a):
        if verbose:
            print(*a)

    pe = path_expression(doc)
    if not check(pe is not None, "the document draws no pathExpression: there is no coil"):
        return FAILURES
    vars_ = variables(doc)
    rings = circles(doc)
    if not check(len(rings) >= 2,
                 "found %d circles; the coil needs a collet to start on and a stud to "
                 "finish in" % len(rings)):
        return FAILURES

    # A full swing: the balance is a sine, so a quarter of its period covers rest to one
    # extreme, and half covers both extremes.
    span = 0.25
    times = [span * k / 12.0 for k in range(13)]
    shapes = [(t, curve(pe, vars_, t)) for t in times]

    # 1 ── the inner end must sit ON the collet, not near it, at every point of the swing.
    p0 = shapes[0][1][0]
    collet = None
    for c, r, n in rings:
        if abs(math.hypot(p0[0] - c[0], p0[1] - c[1]) - r) < 1.0:
            collet = (c, r)
            break
    if not check(collet is not None,
                 "the inner end of the wire does not start on any drawn circle: it is not "
                 "attached to the collet, it just floats near the middle"):
        return FAILURES
    centre, collet_r = collet
    off = max(abs(math.hypot(pts[0][0] - centre[0], pts[0][1] - centre[1]) - collet_r)
              for _, pts in shapes)
    check(off < 0.5,
          "the inner end leaves the collet by up to %.2f px during the swing; it is pinned "
          "there and cannot move" % off)
    say("  inner end   on the collet at r=%.1f, within %.2f px all swing"
        % (collet_r, off))

    # 2 ── the outer end must finish inside the stud, and stay there.
    pl = shapes[0][1][-1]
    stud = None
    for c, r, n in rings:
        if (c, r) != collet and math.hypot(pl[0] - c[0], pl[1] - c[1]) < r:
            stud = (c, r)
            break
    check(stud is not None,
          "the outer end of the wire finishes %.0f px from the stud: a fractional turn "
          "count leaves it somewhere else on the same circle, usually straight across"
          % min(math.hypot(pl[0] - c[0], pl[1] - c[1])
                for c, r, n in rings if (c, r) != collet))
    if stud:
        drift = max(math.hypot(pts[-1][0] - stud[0][0], pts[-1][1] - stud[0][1])
                    for _, pts in shapes)
        check(drift < stud[1],
              "the outer end wanders %.1f px from the stud centre, outside the stud "
              "itself; that end is clamped and must not move at all" % drift)
        say("  outer end   inside the stud, drift %.2f px across the swing" % drift)

    # 3 ── the wire is inextensible. This is the one the first version failed.
    lengths = [polyline_length(pts) for _, pts in shapes]
    spread = (max(lengths) - min(lengths)) / (sum(lengths) / len(lengths))
    check(spread < 0.01,
          "the wire changes length by %.1f%% across the swing (%.0f to %.0f px): a spring "
          "whose wire grows when you wind it does not breathe, its turns slide through "
          "each other" % (100 * spread, min(lengths), max(lengths)))
    say("  wire        %.0f px, varying by %.2f%% across the swing"
        % (sum(lengths) / len(lengths), 100 * spread))

    # 4 ── it breathes, and the right way round. Compare the two extremes of the swing by
    # the mean radius of the coil: wound tighter, the metal has to go somewhere, and with
    # both ends pinned the only way is inward.
    def mean_r(pts):
        rs = radii(pts, centre)
        return sum(rs) / len(rs)

    # The coil names its own variables after itself so two springs can share a document,
    # so the driving angle is found rather than assumed.
    drive = next((k for k in vars_ if k.endswith("_d")), None)
    if not check(drive is not None,
                 "the coil has no driving variable: nothing turns its inner end"):
        return FAILURES
    bal = [CG.evaluate(vars_[drive], vars_, t) for t, _ in shapes]
    anti = min(range(len(bal)), key=lambda i: bal[i])     # inner end furthest anticlockwise
    clock = max(range(len(bal)), key=lambda i: bal[i])
    r_anti, r_clock = mean_r(shapes[anti][1]), mean_r(shapes[clock][1])
    breath = abs(r_anti - r_clock)
    check(breath > 1.0,
          "the coil's mean radius moves only %.2f px between the ends of the swing: it is "
          "changing pitch without breathing" % breath)
    check(r_anti < r_clock,
          "the coil moves OUTWARD (%.1f -> %.1f px) as the inner end turns anticlockwise; "
          "anticlockwise adds wrap, so it must tighten and draw inward. The spiral is "
          "wound the wrong way." % (r_clock, r_anti))
    say("  breathing   mean radius %.1f px anticlockwise, %.1f clockwise (%.1f px)"
        % (r_anti, r_clock, breath))

    # 5 ── turns must not touch. A coil that closes up has gone solid.
    gaps = [min_turn_gap(shapes[i][1], centre) for i in (anti, clock)]
    check(min(gaps) > 1.0,
          "neighbouring turns come within %.2f px at one end of the swing: the coil is "
          "binding on itself" % min(gaps))
    say("  clearance   %.2f px between turns at the tightest point" % min(gaps))

    return FAILURES


# ── selftest ─────────────────────────────────────────────────────────────────

def _rewrite(doc, old, new, where="expr"):
    """Change the path expression or a variable, and insist something actually changed."""
    hits = 0
    for c in commands(doc):
        if where == "expr" and "pathExpression" in c:
            for k in ("expressionX", "expressionY"):
                before = str(c["pathExpression"][k])
                c["pathExpression"][k] = before.replace(old, new)
                hits += before != c["pathExpression"][k]
        elif where == "var" and "variable" in c:
            before = str(c["variable"]["value"])
            c["variable"]["value"] = before.replace(old, new)
            hits += before != c["variable"]["value"]
    if not hits:
        raise AssertionError("break found no %r to replace: it would not have broken "
                             "anything" % old)


def _no_bow(doc):
    """The original model: drop the length-conserving term entirely."""
    _rewrite(doc, " + bow * a[0] * (1 - a[0])", "")


def _flip_bow(doc):
    """Breathe the wrong way: expand when wound tighter."""
    _rewrite(doc, "bow * a[0] * (1 - a[0])", "0 - bow * a[0] * (1 - a[0])")


def _unwind(doc):
    """Wind the spiral the other way, so it tightens clockwise instead."""
    for c in commands(doc):
        if "variable" in c and c["variable"]["name"] == "wrap":
            m = re.match(r"^([-\d.]+) - bal$", str(c["variable"]["value"]))
            if not m:
                raise AssertionError("wrap is not the expected form")
            c["variable"]["value"] = "%.6f - bal" % (-float(m.group(1)))
            return
    raise AssertionError("no wrap variable")


def _half_turn(doc):
    """A fractional turn count: the outer end lands opposite its own stud."""
    for c in commands(doc):
        if "variable" in c and c["variable"]["name"] == "wrap":
            m = re.match(r"^([-\d.]+) - bal$", str(c["variable"]["value"]))
            c["variable"]["value"] = "%.6f - bal" % (float(m.group(1)) + math.pi)
            return
    raise AssertionError("no wrap variable")


def _detach_collet(doc):
    """Start the wire 9 px clear of the collet, as the first version did."""
    pe = path_expression(doc)
    for k in ("expressionX", "expressionY"):
        pe[k] = re.sub(r"\(([\d.]+) \+ ", lambda m: "(%.3f + " % (float(m.group(1)) + 9.0),
                       str(pe[k]), count=1)


def _freeze(doc):
    """Pin the coil's shape so it cannot breathe at all."""
    _rewrite(doc, "bow", "0.0")


def _stretch(doc):
    """Keep the bow but scale it, so the wire no longer keeps its length."""
    _rewrite(doc, "6 * (", "2.5 * (", where="var")


BREAKS = [
    ("the original model: no length conservation at all", _no_bow),
    ("the coil breathing the wrong way (out when wound tighter)", _flip_bow),
    ("the spiral wound the other way, so it tightens clockwise", _unwind),
    ("half a turn, so the outer end lands opposite its stud", _half_turn),
    ("the wire starting 9 px clear of the collet", _detach_collet),
    ("the coil frozen, pitch changing but nothing moving", _freeze),
    ("the bow mis-scaled, so the wire stretches anyway", _stretch),
]


def selftest():
    base = json.loads(DOC.read_text())
    print("selftest: the checker must pass the shipped coil and fail every break\n")
    fails = run(copy.deepcopy(base), verbose=True)
    if fails:
        print("\nFAIL: the shipped document does not pass")
        for f in fails:
            print("   ", f)
        return 1
    print("\n  shipped document: PASS\n")

    bad = 0
    for label, break_it in BREAKS:
        d = copy.deepcopy(base)
        try:
            break_it(d)
            got = run(d, verbose=False)
        except Exception as e:
            got = list(FAILURES) + ["raised %s: %s" % (type(e).__name__, e)]
        if got:
            print("  caught   %s" % label)
            print("           %s" % got[0][:108])
        else:
            print("  MISSED   %s" % label)
            bad += 1
    print("\n%d of %d breaks caught" % (len(BREAKS) - bad, len(BREAKS)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true",
                    help="break the coil on purpose and prove the checker notices")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    print("checking", DOC.name)
    fails = run(json.loads(DOC.read_text()))
    if fails:
        print("\nFAIL")
        for f in fails:
            print("  -", f)
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
