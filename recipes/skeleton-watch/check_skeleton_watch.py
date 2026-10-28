#!/usr/bin/env python3
"""check_skeleton_watch — does the watch actually tell the time?

Reads `out/skeleton_watch.json` and replays it. A drawing of gears is easy; a drawing whose
gears would turn each other at the right rates is not, and the difference is invisible by
eye. Six questions:

  1. one source     — every wheel's angle is the SAME variable times a constant, so the
                      whole movement is geared rather than separately animated
  2. the ratios     — each of those constants matches the tooth counts actually drawn on
                      the two wheels it connects
  3. the meshes     — every pair sits at m*(Z+z)/2 and the teeth clear over a full pitch
  4. the hands      — seconds one turn a minute, minutes one an hour, hours one in twelve
  5. 12:1           — the minute hand passes the hour hand exactly eleven times in twelve
                      hours, which is the thing a wrong motion work gets wrong
  6. set to twelve  — all three hands start at twelve

Run with --selftest.
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

_pt = importlib.util.spec_from_file_location("parts", HERE / "parts.py")
PARTS = importlib.util.module_from_spec(_pt)
_pt.loader.exec_module(PARTS)

_cw = importlib.util.spec_from_file_location("check_watch", HERE / "check_watch.py")
CW = importlib.util.module_from_spec(_cw)
_cw.loader.exec_module(CW)

DOC = ROOT / "out" / "skeleton_watch.json"
# Read from the palette, never spelled out: a literal here stops matching the
# moment the drawing is taken up or down a notch.
JEWEL_RGB = PARTS.JEWEL[3:].upper()

FAILURES = []


def check(cond, msg):
    if not cond:
        FAILURES.append(msg)
    return bool(cond)


def _at(group, t, vars_):
    """`Group.at` with the document's variables in scope."""
    a = CG.evaluate(group.angle, vars_, t)
    ca, sa = math.cos(a), math.sin(a)
    px, py = group.pivot
    return [(c, [(px + (x - px) * ca - (y - py) * sa,
                  py + (x - px) * sa + (y - py) * ca) for x, y in pts])
            for c, pts in group.paths]


def variables(doc):
    return {c["variable"]["name"]: c["variable"]["value"]
            for c in CW.commands_of(doc) if "variable" in c}


def rate(expr, vars_, t0=11.0, t1=71.0):
    """Radians per unit of t. Measured over a whole number of beats so the staircase
    contributes its average rather than wherever it happens to be mid-step."""
    return (CG.evaluate(expr, vars_, t1) - CG.evaluate(expr, vars_, t0)) / (t1 - t0)


def run(doc, verbose=True):
    del FAILURES[:]

    def say(*a):
        if verbose:
            print(*a)

    vars_ = variables(doc)
    groups = [g for g in CW.walk(doc) if g.angle is not None]
    check(len(groups) > 8, "only %d moving parts; this is not a movement" % len(groups))

    # 1 ── one source. Every rotation must be built from the same single variable.
    # Per wheel, not across the union. Taking the union lets a part driven by bare `t`
    # pass unnoticed — it contributes no variable name at all, so the set stays {esc} and
    # the document looks geared while one hand is quietly animated at the right rate by
    # hand. That is precisely the thing this check exists to forbid.
    # Per part, not across the union. Taking the union lets something driven by bare `t`
    # pass unnoticed — it contributes no variable name at all, so the set stays {esc} and
    # the document looks geared while one hand is quietly animated at the right rate by
    # hand. That is precisely what this exists to forbid.
    #
    # But only for the WHEELS and the HANDS. The balance and the lever are the oscillator,
    # not the train: they are functions of the clock itself, and the escape wheel follows
    # THEM. Requiring those to be geared to the wheel they drive has the causality
    # backwards.
    srcs, ungeared = set(), 0
    for g in groups:
        own = {n for n in re.findall(r"[A-Za-z_]\w*", g.angle)
               if n not in CG._FUNCS and n != "t"}
        srcs |= own
        if own:
            continue
        # The oscillator, identified by the SHAPE of its motion the way check_watch does
        # it: the lever is the only thing that clamps, and the balance is the only bare
        # sine. Anything else with no source is a wheel or a hand running loose.
        a = str(g.angle)
        oscillator = "max(-1" in a or ("sin(" in a and "floor(" not in a)
        if not oscillator:
            ungeared += 1
    check(len(srcs) == 1,
          "the wheels are driven from %d different variables (%s): a movement has one "
          "source of motion and everything else is geared to it"
          % (len(srcs), ", ".join(sorted(srcs)) or "none"))
    check(ungeared == 0,
          "%d moving parts reference no source at all: they are animated directly off the "
          "clock instead of being driven by the train, so their rate is a coincidence "
          "rather than a consequence" % ungeared)
    say("  source      every wheel is a multiple of %s" % (", ".join(srcs) or "t"))

    base = rate(vars_["esc"], vars_) if "esc" in vars_ else None
    if not check(base, "no escape-wheel variable to measure against"):
        return FAILURES

    # Every toothed outline in the document, with where it is, how many teeth it has,
    # what module it is cut to, and how fast it turns.
    #
    # NOT grouped by pivot. A watch's centre arbor carries three things at three different
    # speeds — the centre wheel, the cannon pinion driven with it, and the hour wheel
    # riding free on the tube at a twelfth of the rate — and collapsing them by position
    # loses two of the three. The first version of this did, and then reported that the
    # movement had no arbor for an hour hand to sit on.
    gears, seen = [], set()
    for g in groups:
        r = rate(g.angle, vars_) / base
        for _, pts in g.paths:
            if len(pts) < 40:
                continue
            env = CW.envelope([(None, pts)], g.pivot, bins=1440)
            n, _ = CW.peaks(env)
            if n < 5:
                continue
            tip = max(env)
            module = tip / (n / 2.0 + 0.95)        # the profile puts the tip here
            # Each gear is drawn twice, a wash and then an edge, so the same outline
            # arrives twice and every mesh would be counted four times over.
            key = (round(g.pivot[0], 1), round(g.pivot[1], 1), n, round(module, 2))
            if key in seen:
                continue
            seen.add(key)
            gears.append({"pivot": g.pivot, "n": n, "m": module,
                          "rp": module * n / 2.0, "r": r, "g": g, "pts": pts})

    # 2 ── the ratios, against the teeth actually drawn.
    #
    # What counts as a mesh: two outlines cut to the SAME module whose pitch circles
    # touch. Both fall out of the drawing. Proximity alone is not enough — in a movement
    # this dense almost everything is near something.
    meshes = []
    for i in range(len(gears)):
        for j in range(i + 1, len(gears)):
            A, B = gears[i], gears[j]
            d = math.hypot(A["pivot"][0] - B["pivot"][0], A["pivot"][1] - B["pivot"][1])
            if d < 1.0:
                continue                           # coaxial: stacked, not meshing
            if abs(A["m"] - B["m"]) > 0.02 * max(A["m"], B["m"]):
                continue
            if abs(A["rp"] + B["rp"] - d) > 0.02 * d:
                continue
            meshes.append((A, B, d))
    check(len(meshes) >= 4,
          "found only %d meshing pairs; the train should have at least four" % len(meshes))

    for A, B, d in meshes:
        want = -float(A["n"]) / B["n"]
        got = B["r"] / A["r"] if A["r"] else 0.0
        check(abs(got - want) < 0.02 * abs(want) + 1e-9,
              "a %d-tooth wheel drives a %d-tooth wheel, so the second must turn at "
              "%.4f times the first and in the opposite sense; it turns at %.4f"
              % (A["n"], B["n"], want, got))
    say("  meshes      %d pairs, every ratio matching its own tooth counts" % len(meshes))

    # 3 ── and they must not foul. Swept over a full pitch of the slower wheel.
    worst = 1e9
    for A, B, d in meshes:
        period = abs(2 * math.pi / B["n"] / (rate(B["g"].angle, vars_) or 1e-9))
        for k in range(48):
            t = k / 48.0 * period
            pa = CW.rotated(A["g"], A["pts"], t, vars_)
            pb = CW.rotated(B["g"], B["pts"], t, vars_)
            tab = CW.polar_table(pb, B["pivot"][0], B["pivot"][1])
            for x, y in pa:
                rr = math.hypot(x - B["pivot"][0], y - B["pivot"][1])
                if rr > d:
                    continue
                worst = min(worst, rr - CW.radius_at(
                    tab, math.atan2(y - B["pivot"][1], x - B["pivot"][0])))
    check(worst > -1.2,
          "two wheels cut %.2f px into each other: they are not cut to a common module "
          "or their phases are wrong" % -worst)
    say("  clearance   %.2f px at the tightest point of any mesh" % worst)

    # 3b ── the escapement. The movement carries the same lever and wheel as the
    # escapement document, so it inherits the same requirement: at each banking position
    # exactly one pallet stone may dip inside the circle the tooth tips sweep, and NO
    # tooth may pass through a stone. A stone centred on the locking radius reaches right
    # across the tooth band and two teeth run through it, which draws as steel through
    # steel and is invisible unless you test the outlines against each other.
    esc_g = [g for g in groups if str(g.angle).strip() == "esc"]
    pal_g = [g for g in groups if "max(-1" in str(g.angle)]
    if esc_g and pal_g:
        epiv = esc_g[0].pivot
        teeth = []
        for g in esc_g:
            for _, pts in g.paths:
                if 5 <= len(pts) <= 14:
                    teeth.append((max(math.hypot(x - epiv[0], y - epiv[1])
                                      for x, y in pts), pts))
        rmax = max((r for r, _ in teeth), default=0.0)
        tooth_polys = [p for r, p in teeth if r > rmax - 1.0]
        amp = max(abs(CG.evaluate(pal_g[0].angle, vars_, k / 200.0))
                  for k in range(200)) if tooth_polys else 0.0
        beat = 1.0 / 5.0
        crossed, dips = 0, []
        for t in (beat * 0.5, beat * 1.5):
            stones, seen_s = [], []
            for colour, pts in _at(pal_g[0], t, vars_):
                if colour and JEWEL_RGB in colour.upper() and 4 <= len(pts) <= 6:
                    key = round(sum(q[0] for q in pts), 1)
                    if not any(abs(key - k) < 0.5 for k in seen_s):
                        seen_s.append(key)
                        stones.append(pts)
            tp = [CW.rotated(esc_g[0], q, t, vars_) for q in tooth_polys]
            inside = 0
            for st in stones:
                if any(PARTS.polys_overlap(st, q) for q in tp):
                    crossed += 1
                if min(math.hypot(x - epiv[0], y - epiv[1]) for x, y in st) < rmax:
                    inside += 1
            dips.append(inside)
        check(crossed == 0,
              "a tooth passes THROUGH a pallet stone at %d of the banking positions: the "
              "stones reach into the wheel instead of resting against it" % crossed)
        check(all(d == 1 for d in dips),
              "at the banking pins %s stones reach inside the tooth circle; exactly one "
              "must hold while the other stands clear" % dips)
        say("  escapement  one stone holds at each banking pin, no tooth through a stone")

    # 4 ── the rates. Tested on the ARBORS, not on the hand shapes: what has to be true
    # is that the movement contains something turning once a minute, something once an
    # hour and something once in twelve, all geared off the same escape wheel.
    periods = {}
    for g in groups:
        r = rate(g.angle, vars_)
        if abs(r) > 1e-12:
            periods[round(abs(2 * math.pi / r), 3)] = g
    for secs, label in ((60.0, "seconds"), (3600.0, "minutes"), (43200.0, "hours")):
        near = [p for p in periods if abs(p - secs) <= max(0.5, 0.004 * secs)]
        check(bool(near),
              "nothing in the movement turns once every %.0f seconds of t, so there is "
              "no arbor the %s hand could sit on. The arbors turn once every %s."
              % (secs, label, ", ".join("%.1f" % p for p in sorted(periods))))
    say("  rates       arbors turn once every %s seconds of t"
        % ", ".join("%.4g" % p for p in sorted(periods)))

    # The hands themselves: five-point blades, each on one of those arbors.
    # A hand is a five-point blade much longer than it is wide. Measured on the SHAPE,
    # not from the pivot: the seconds hand is short and its counterpoise is a big fraction
    # of that length, so a reach-against-nearest-point rule throws it out and reports a
    # watch with two hands.
    hands = []
    for g in groups:
        for colour, pts in g.paths:
            if len(pts) != 5:
                continue
            best = max(((math.hypot(a[0] - b[0], a[1] - b[1]), a, b)
                        for a in pts for b in pts), key=lambda v: v[0])
            length, a, b = best
            if length < 1e-6:
                continue
            ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
            width = (max(-(x - a[0]) * uy + (y - a[1]) * ux for x, y in pts)
                     - min(-(x - a[0]) * uy + (y - a[1]) * ux for x, y in pts))
            if length > 4.0 * max(width, 1e-6):
                reach = max(math.hypot(x - g.pivot[0], y - g.pivot[1]) for x, y in pts)
                hands.append((reach, g, pts))
    seen, uniq = set(), []
    for reach, g, pts in hands:
        k = (round(reach, 1), round(g.pivot[0], 1), round(g.pivot[1], 1))
        if k not in seen:
            seen.add(k)
            uniq.append((reach, g, pts))
    check(len(uniq) == 3, "found %d hands; a watch has three" % len(uniq))
    if len(uniq) < 3:
        return FAILURES
    hands = uniq

    # 5 ── the 12:1. The minute hand must lap the hour hand eleven times in twelve hours,
    # which is what you actually see on a dial and what a wrong motion work ruins.
    by_period = {}
    for reach, g, pts in hands:
        by_period[round(abs(2 * math.pi / (rate(g.angle, vars_) or 1e-9)))] = g
    mh = [g for k, g in by_period.items() if abs(k - 3600) <= 14]
    hh = [g for k, g in by_period.items() if abs(k - 43200) <= 172]
    if mh and hh:
        rm = rate(mh[0].angle, vars_)
        rh = rate(hh[0].angle, vars_)
        laps = abs(rm - rh) * 43200 / (2 * math.pi)
        check(abs(laps - 11.0) < 0.05,
              "the minute hand laps the hour hand %.3f times in twelve hours; on a watch "
              "it is exactly eleven" % laps)
        check(rm * rh > 0, "the minute and hour hands turn in opposite directions")
        say("  12:1        minute laps hour %.3f times in twelve hours" % laps)

    # 6 ── set to twelve. Every hand points straight up at t = 0.
    for reach, g, pts in hands:
        tip = max(pts, key=lambda p: math.hypot(p[0] - g.pivot[0], p[1] - g.pivot[1]))
        a = CG.evaluate(g.angle, vars_, 0.0)
        ca, sa = math.cos(a), math.sin(a)
        tx = g.pivot[0] + (tip[0] - g.pivot[0]) * ca - (tip[1] - g.pivot[1]) * sa
        ty = g.pivot[1] + (tip[0] - g.pivot[0]) * sa + (tip[1] - g.pivot[1]) * ca
        off = math.degrees(math.atan2(tx - g.pivot[0], g.pivot[1] - ty))
        check(abs(off) < 1.0,
              "a hand starts %.1f degrees from twelve: the hands have inherited their "
              "wheels' meshing phases instead of being set" % off)
    say("  set         all three hands start at twelve")

    return FAILURES


# ── selftest ─────────────────────────────────────────────────────────────────

def _retune(doc, old, new):
    hits = 0
    for c in CW.commands_of(doc):
        if "rotate" in c:
            before = str(c["rotate"]["angle"])
            c["rotate"]["angle"] = before.replace(old, new)
            hits += before != c["rotate"]["angle"]
        if "variable" in c:
            before = str(c["variable"]["value"])
            c["variable"]["value"] = before.replace(old, new)
            hits += before != c["variable"]["value"]
    if not hits:
        raise AssertionError("break found no %r to replace" % old)


def ratios(doc):
    """Every distinct gear ratio the document actually uses."""
    out = set()
    for c in CW.commands_of(doc):
        if "rotate" in c:
            for v in re.findall(r"esc \* (-?[\d.]+)", str(c["rotate"]["angle"])):
                out.add(abs(float(v)))
    return sorted(out)


def _scale_rate(doc, rank, factor):
    """Change one arbor's gear ratio without touching its drawn teeth.

    Picked by RANK among the ratios the document uses — slowest first — rather than by a
    literal constant. Three of these breaks were pinned to numbers from an earlier train
    and quietly stopped matching anything the moment the tooth counts changed; they then
    reported themselves caught, because a break that raises looks the same as a break that
    was noticed.
    """
    rs = ratios(doc)
    which = rs[rank]
    hits = 0
    for c in CW.commands_of(doc):
        if "rotate" not in c:
            continue
        m = re.search(r"esc \* (-?[\d.]+)", str(c["rotate"]["angle"]))
        if m and abs(abs(float(m.group(1))) - which) < 1e-12:
            c["rotate"]["angle"] = str(c["rotate"]["angle"]).replace(
                m.group(0), "esc * %.9f" % (float(m.group(1)) * factor))
            hits += 1
    if not hits:
        raise AssertionError("no arbor turning at %r" % which)


def _free_hand(doc):
    """Animate the seconds hand directly instead of gearing it.

    The escape arbor is written as the bare variable, so it carries no `esc * N` at all;
    the largest ratio in the list is therefore the fourth wheel, which carries the seconds
    hand.
    """
    fast = ratios(doc)[-1]
    for c in CW.commands_of(doc):
        if "rotate" in c and re.search(r"esc \* -?%.6f" % fast, str(c["rotate"]["angle"])):
            c["rotate"]["angle"] = "(t * 0.1047198) * 57.29577951"
            return
    raise AssertionError("cannot find the seconds hand")


def _sink_stones(doc, frac=0.55):
    """Pull the pallet stones in towards the wheel so the teeth run through them.

    The exact shape of the original bug: a stone centred on the locking radius rather than
    standing on it, reaching right across the tooth band.
    """
    cmds = CW.commands_of(doc)
    moving, pivot, colour, hits = False, None, None, 0
    for c in cmds:
        if "rotate" in c:
            moving = "max(-1" in str(c["rotate"]["angle"])
            pivot = (c["rotate"]["pivotX"], c["rotate"]["pivotY"])
        elif "restore" in c:
            moving = False
        elif "paint" in c:
            for op in c["paint"]["ops"]:
                if "color" in op:
                    colour = op["color"]
        elif moving and "drawPath" in c and colour and JEWEL_RGB in colour.upper():
            pts = PARTS._poly_pts(c["drawPath"]["path"])
            cx = sum(q[0] for q in pts) / len(pts)
            cy = sum(q[1] for q in pts) / len(pts)
            px, py = pivot
            ux, uy = cx - px, cy - py
            n = math.hypot(ux, uy) or 1.0
            d = frac * max(math.hypot(q[0] - cx, q[1] - cy) for q in pts)
            c["drawPath"]["path"] = PARTS.poly(
                [(x + d * ux / n, y + d * uy / n) for x, y in pts])
            hits += 1
    if not hits:
        raise AssertionError("found no pallet stones to move")


BREAKS = [
    ("the pallet stones sunk into the wheel, teeth running through them", _sink_stones),
    ("the motion work geared 10:1 instead of 12:1",
     lambda d: _scale_rate(d, 0, 12.0 / 10.0)),
    ("the hour hand running backwards",
     lambda d: _scale_rate(d, 0, -1.0)),
    ("the seconds hand animated directly rather than geared", _free_hand),
    ("the whole train running at double speed",
     lambda d: _retune(d, "esc * ", "esc * 2 * ")),
    ("the escape wheel stepping a whole pitch, doubling every hand",
     lambda d: _retune(d, "0.15707963 * (floor", "0.31415927 * (floor")),
]


def selftest():
    base = json.loads(DOC.read_text())
    print("selftest: the checker must pass the movement and fail every break\n")
    fails = run(copy.deepcopy(base), verbose=True)
    if fails:
        print("\nFAIL: the shipped movement does not pass")
        for f in fails:
            print("   ", f)
        return 1
    print("\n  shipped movement: PASS\n")
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
            print("           %s" % got[0][:106])
        else:
            print("  MISSED   %s" % label)
            bad += 1
    print("\n%d of %d breaks caught" % (len(BREAKS) - bad, len(BREAKS)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
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
