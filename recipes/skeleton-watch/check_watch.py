#!/usr/bin/env python3
"""check_watch — verify the escapement assembly from the document it ships, not the code.

The generator could be wrong in a way the generator agrees with. So this reads
`out/watch.json`, replays the drawing commands to recover where every part actually
is and how it actually moves, and then asks five questions of the result:

  1. one clock      — every part's rotation is a function of `t` alone, and there are
                      exactly four arbors
  2. locking        — at both ends of the lever's travel, both pallet jewels sit on the
                      escape wheel's tooth-tip circle; a jewel that floats clear of the
                      teeth is a watch that does not tick
  3. impulse        — the balance's impulse jewel is inside the fork notch at the instant
                      the lever flips, and well clear of it the rest of the time
  4. mesh           — the fourth wheel and the escape pinion never interfere, swept over a
                      full tooth pitch
  5. beat           — the escape wheel advances exactly one tooth per beat, no more

Why these five: they are the five things I could have got wrong and still produced a
drawing that looks like a watch. Everything else about the picture is obvious on sight.

Run with --selftest to watch it fail. Eight deliberate breaks, each the shape of a real
mistake — a lever a little too long, a balance a little too far away, one wheel cut to a
different module, the staircase constant off by a tooth. A checker that has never been
seen to fail has not been shown to work.
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

_pt = importlib.util.spec_from_file_location("parts", HERE / "parts.py")
PARTS = importlib.util.module_from_spec(_pt)
_pt.loader.exec_module(PARTS)

_cg = importlib.util.spec_from_file_location("expr", HERE / "expr.py")
CG = importlib.util.module_from_spec(_cg)
_cg.loader.exec_module(CG)

DOC = ROOT / "out" / "watch.json"

# Read from the palette, never spelled out: a literal here stops matching the
# moment the drawing is taken up or down a notch.
JEWEL_RGB = PARTS.JEWEL[3:].upper()

FAILURES = []


def check(cond, msg):
    if not cond:
        FAILURES.append(msg)
    return bool(cond)


# ── replaying the document ───────────────────────────────────────────────────

_NUM = r"-?\d+(?:\.\d+)?"
_TOKEN = re.compile(r"([ML])\s*(%s)\s+(%s)" % (_NUM, _NUM))


def commands_of(doc):
    """The canvas command list. Every checker here walks the same one."""
    return doc["root"][0]["box"]["children"][0]["commands"]


def parse_path(d):
    """An 'M x y L x y ...' string back into points."""
    return [(float(x), float(y)) for _, x, y in _TOKEN.findall(d)]


class Group(object):
    """A run of paths that share one rotation about one pivot."""

    def __init__(self, angle, pivot):
        self.angle, self.pivot = angle, pivot
        self.paths = []                 # (colour, points)

    def at(self, t):
        """Every point, rotated to where it is at time t."""
        if self.angle is None:
            return [(c, list(p)) for c, p in self.paths]
        # `walk` keeps the expression with the radians-to-degrees factor stripped off, so
        # what is stored is already radians. Converting it again turns 149 degrees of
        # balance swing into two and a half, and every part then looks nailed down.
        a = CG.evaluate(self.angle, {}, t) if self.angle else 0.0
        ca, sa = math.cos(a), math.sin(a)
        px, py = self.pivot
        out = []
        for colour, pts in self.paths:
            out.append((colour, [(px + (x - px) * ca - (y - py) * sa,
                                  py + (x - px) * sa + (y - py) * ca)
                                 for x, y in pts]))
        return out


def walk(doc):
    """Recover the groups. `rotate` inside save/restore is the only transform used."""
    cmds = commands_of(doc)
    groups, stack, colour = [], [], None
    cur = Group(None, (0.0, 0.0))
    groups.append(cur)
    for c in cmds:
        if "paint" in c:
            for op in c["paint"]["ops"]:
                if "color" in op:
                    colour = op["color"]
        elif "save" in c:
            stack.append(cur)
        elif "restore" in c:
            cur = stack.pop() if stack else groups[0]
        elif "rotate" in c:
            r = c["rotate"]
            m = re.match(r"^\((.*)\)\s*\*\s*57\.29577951$", str(r["angle"]))
            check(m is not None, "a rotation is not the usual radians-to-degrees form")
            cur = Group(m.group(1) if m else "0", (r["pivotX"], r["pivotY"]))
            groups.append(cur)
        elif "drawPath" in c:
            p = c["drawPath"]["path"]
            if isinstance(p, str) and p.startswith("M"):
                cur.paths.append((colour, parse_path(p)))
    return [g for g in groups if g.paths]


def clock(doc):
    """The one variable the whole movement is a function of, and how fast it runs.

    This checker evaluates every motion by handing it a `t` of its own, which means that
    until now it never once looked at what the document says `t` actually is. A document
    whose clock had been set to a constant would have sailed through every test below with
    a glowing report, because all the motions are perfectly correct functions of a `t` that
    never advances. So: read the clock, insist it is real time and that it goes forwards,
    and report how fast.
    """
    cmds = doc["root"][0]["box"]["children"][0]["commands"]
    decls = [c["variable"] for c in cmds
             if "variable" in c and c["variable"].get("name") == "t"]
    if not check(len(decls) == 1,
                 "the movement should be driven by exactly one clock; found %d "
                 "declarations of t" % len(decls)):
        return 1.0
    value = str(decls[0]["value"]).strip()

    # The clock has to be the REAL one, and it has to span twelve hours.
    #
    # `continuousSec()` is not elapsed time: the player computes it as
    # `minute*60 + second + millis/1000`, the second within the hour, to the millisecond.
    # A movement driven by that alone already shows the true seconds and the true minutes
    # — but it wraps every hour, and an hour hand geared off a clock that resets hourly
    # flies back to twelve every hour. `timeInHr()` carries the hour across the wrap.
    #
    # So both must be present. Insisting on it is the difference between a watch and a
    # watch that is right for fifty-nine minutes out of every sixty.
    check("continuousSec()" in value,
          "the clock is %r; it must be built on continuousSec(), which is the real second "
          "within the hour, to the millisecond" % value)
    check("timeInHr()" in value,
          "the clock is %r; it carries no hour. continuousSec() wraps every hour, so an "
          "hour hand geared off it alone snaps back to twelve on the hour" % value)
    for n in re.findall(r"[A-Za-z_]\w*(?=\s*\()", value):
        check(n in ("continuousSec", "timeInHr", "floor"),
              "the clock calls %r; it should be built from continuousSec(), timeInHr() "
              "and floor alone" % n)
    m = re.search(r"\)\s*\*\s*(-?[0-9.]+)\s*$", value)
    scale = float(m.group(1)) if m else 1.0
    check(scale > 0, "the clock is scaled by %g: time would stand still or run backwards"
          % scale)
    return 1.0 / scale if scale else 1.0


def arbors(groups):
    """Group the rotating groups by pivot; return {pivot: [groups]}."""
    byp = {}
    for g in groups:
        if g.angle is None:
            continue
        key = (round(g.pivot[0], 3), round(g.pivot[1], 3))
        byp.setdefault(key, []).append(g)
    return byp


def centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def jewels(group, t):
    """Centroids of the ruby-coloured outlines in a group, at time t.

    Every jewel is drawn twice — a wash and then an edge over it — so the same outline
    comes back twice and the duplicates have to go. Deduping on the centroid is exact
    here, because the two draws are the same path.
    """
    out = []
    for colour, pts in group.at(t):
        if colour and JEWEL_RGB in colour.upper() and len(pts) >= 3:
            c = centroid(pts)
            if not any(math.hypot(c[0] - o[0], c[1] - o[1]) < 0.5 for o in out):
                out.append(c)
    return out


def envelope(groups, pivot, bins=720):
    """Max radius per bearing over every path on an arbor, as one outline.

    The escape wheel is not one path: its rim is a circle and each of its fifteen teeth is
    a separate little polygon. Measuring the biggest single path would measure the rim and
    report a wheel with no teeth at all — which is exactly what it did the first time this
    ran. The envelope is what the wheel actually sweeps.
    """
    env = [0.0] * bins
    for _, pts in groups:
        # Walk the EDGES, not the corners. A tooth is four or five points and the gaps
        # between them straddle many bins; binning only the corners leaves those bins
        # empty, and empty bins read as deep notches — which is how a fifteen-tooth wheel
        # first measured as having a hundred and sixty-nine.
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            # Four samples a pixel. At one a pixel a big circle still cannot
            # reach every bin, and the gaps then get filled from whatever
            # smaller path happens to be beside them.
            n = max(2, int(4 * math.hypot(x1 - x0, y1 - y0)) + 2)
            for k in range(n):
                f = k / float(n)
                x, y = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
                a = math.atan2(y - pivot[1], x - pivot[0]) % (2 * math.pi)
                b = int(a / (2 * math.pi) * bins) % bins
                r = math.hypot(x - pivot[0], y - pivot[1])
                if r > env[b]:
                    env[b] = r
    # Bins no sample reached are not notches, they are gaps. A small circle of radius six
    # is forty pixels round and cannot fill seven hundred bins, so leaving them at zero
    # makes a smooth hub look like a wheel with as many teeth as it has empty bins — which
    # is how the pinion search first picked the hub. Carry the neighbours across instead.
    filled = [r for r in env if r > 0]
    if not filled:
        return env
    first = next(i for i, r in enumerate(env) if r > 0)
    last = first
    for k in range(bins):
        i = (first + k) % bins
        if env[i] > 0:
            last = i
        else:
            env[i] = env[last]
    return env


def peaks(env):
    """How many times the envelope rises clear of its own mean: the tooth count.

    "Above the mean" alone is not a tooth. A circle written out to three decimal places
    wobbles by a thousandth of a pixel, and a bare mean crossing counts every one of those
    wobbles — a hundred and twenty teeth on a plain hub. The rise has to clear a band
    around the mean scaled to how much the outline actually varies, which is zero for a
    circle and large for a gear.
    """
    live = [r for r in env if r > 0]
    if not live:
        return 0, 0.0
    mean = sum(live) / len(live)
    lo, hi = min(live), max(live)
    if hi - lo < 0.02 * hi:          # a circle: no teeth, whatever the noise says
        return 0, mean
    band = 0.10 * (hi - lo)
    # Two laps. With hysteresis the starting state matters, and a tooth that straddles
    # index zero is lost if the first lap begins mid-tooth — which is how fifteen teeth
    # counted as fourteen. The first lap only settles the state; the second one counts.
    above = False
    n = 0
    for lap in (0, 1):
        for r in env:
            if r > mean + band:
                if not above and lap:
                    n += 1
                above = True
            elif r < mean - band:
                above = False
    return n, mean


def polar_table(pts, cx, cy):
    """Sorted (bearing, radius) for an outline, for inside-tests."""
    tab = sorted((math.atan2(y - cy, x - cx), math.hypot(x - cx, y - cy))
                 for x, y in pts)
    return tab


def radius_at(tab, a):
    """Outline radius in direction `a`, linearly interpolated between samples."""
    a = (a + math.pi) % (2 * math.pi) - math.pi
    lo, hi = 0, len(tab)
    while lo < hi:
        mid = (lo + hi) // 2
        if tab[mid][0] < a:
            lo = mid + 1
        else:
            hi = mid
    i0 = (lo - 1) % len(tab)
    i1 = lo % len(tab)
    a0, r0 = tab[i0]
    a1, r1 = tab[i1]
    da = (a1 - a0) % (2 * math.pi)
    if da < 1e-9:
        return r0
    f = ((a - a0) % (2 * math.pi)) / da
    return r0 + (r1 - r0) * max(0.0, min(1.0, f))


# ── the parts, found by how they move ────────────────────────────────────────

def classify(groups):
    """Name the arbors by the shape of their motion, which is unambiguous here.

    The lever is the only thing that clamps, and the balance is the only thing that is a
    bare sine. That leaves the two arbors driven by the escape wheel's staircase — and
    those are told apart by the fact that the driven one's expression CONTAINS the driving
    one's. That is not a trick for the checker's convenience; it is the invariant. A fourth
    wheel whose angle is not literally built out of the escape wheel's angle is a wheel
    that is only pretending to be geared to it, and the containment test says so.
    """
    byp = arbors(groups)
    found, stair = {}, []
    for pivot, gs in byp.items():
        expr = gs[0].angle
        if "max(-1" in expr:
            found["pallet"] = (pivot, gs)
        elif "floor(" in expr:
            stair.append((pivot, gs))
        elif "sin(" in expr:
            found["balance"] = (pivot, gs)
    if len(stair) == 2:
        a, b = sorted(stair, key=lambda pg: len(pg[1][0].angle))
        check(a[1][0].angle in b[1][0].angle,
              "two arbors both step, but neither angle is built from the other: they are "
              "not geared together, they only happen to move at similar rates")
        found["escape"], found["fourth"] = a, b
    return found, byp


def biggest(gs):
    """The widest outline on an arbor — the wheel rather than the pinion."""
    best, span = None, -1.0
    for g in gs:
        for _, pts in g.paths:
            if len(pts) < 8:
                continue
            s = max(p[0] for p in pts) - min(p[0] for p in pts)
            if s > span:
                best, span = (g, pts), s
    return best


def smallest_toothed(gs, pivot):
    """The pinion: the smallest outline that actually has teeth.

    "Smallest outline with enough points" is not enough — a wheel's inner rim is a
    hundred-and-twenty-point circle sitting well inside its own teeth, so that rule picks
    the rim every time and then reports a generous clearance between two things that were
    never going to touch. Counting the peaks is what separates a toothed outline from a
    circle.
    """
    best, span = None, 1e9
    for g in gs:
        for _, pts in g.paths:
            if len(pts) < 40:
                continue
            n, _ = peaks(envelope([(None, pts)], pivot, bins=360))
            if n < 5:
                continue
            r = max(math.hypot(x - pivot[0], y - pivot[1]) for x, y in pts)
            if r < span:
                best, span = (g, pts), r
    return best


# ── the five checks ──────────────────────────────────────────────────────────

def run(doc, verbose=True):
    del FAILURES[:]
    groups = walk(doc)
    parts, byp = classify(groups)

    def say(*a):
        if verbose:
            print(*a)

    # 0 ── the clock. Everything after this is measured in `t`, not in seconds, which is
    # the whole point of there being one clock: slowing the movement down cannot change
    # any invariant, because no invariant is written in seconds.
    divisor = clock(doc)
    say("  clock       the real time of day over twelve hours%s"
        % ("" if divisor == 1 else ", at %gx speed" % (1.0 / divisor)))

    # 1 ── one clock.
    check(len(byp) == 4, "expected four arbors, found %d" % len(byp))
    for name in ("escape", "pallet", "balance", "fourth"):
        if not check(name in parts, "no arbor moves like the %s" % name):
            return FAILURES
    for pivot, gs in byp.items():
        for g in gs:
            for n in re.findall(r"[A-Za-z_]\w*", g.angle):
                check(n in CG._FUNCS or n == "t",
                      "a rotation reads %r rather than t: that part is wired to its own "
                      "clock and will not follow the movement when the speed changes" % n)
    say("  arbors      4, every rotation a function of t alone")

    # The beat rate and the banking angle come from the document, not from constants.
    # They were hardcoded at 4 Hz and 0.175 rad, and when the movement's train forced the
    # balance to 2.5 Hz every window below was sampling 1.25 beats instead of 2 — so the
    # lever only ever reached one of its two banking pins inside the window, and the
    # checker reported that one ruby was doing all the work.
    m = re.search(r"sin\(\s*([\d.]+)\s*\*\s*t", str(parts["balance"][1][0].angle))
    if not check(m is not None, "cannot read the balance's frequency"):
        return FAILURES
    freq = float(m.group(1)) / (2 * math.pi)
    cycle = 1.0 / freq                     # one full oscillation: two beats
    amp = max(abs(CG.evaluate(parts["pallet"][1][0].angle, {}, cycle * k / 200.0))
              for k in range(200))

    esc_p, esc_g = parts["escape"]
    pal_p, pal_g = parts["pallet"]
    bal_p, bal_g = parts["balance"]
    fou_p, fou_g = parts["fourth"]

    # The escape wheel, measured from the document as the envelope of everything on its
    # arbor minus the pinion, which is small and central.
    esc_all = [pr for g in esc_g for pr in g.at(0.0)]
    env = envelope(esc_all, esc_p)
    r_tip = max(env)
    teeth_e, mean_r = peaks(env)
    tooth_h = r_tip - min(r for r in env if r > r_tip * 0.55)
    say("  escape      %d teeth, tip radius %.1f, tooth height %.1f"
        % (teeth_e, r_tip, tooth_h))
    # Not a fixed count — what matters is the SPAN rule, which is tested directly in the
    # escaping-action check below. Pinning the tooth count here just makes the checker
    # fail whenever the train is redesigned around it.
    check(teeth_e >= 12, "the escape wheel has only %d teeth" % teeth_e)

    # 2 ── locking. At each end of the lever's travel both jewels must be on the teeth.
    # It is not enough that a jewel is somewhere near a tooth. A watchmaker measures the
    # LOCK: how far the stone's locking corner dips inside the circle the tooth tips sweep.
    # Too shallow and the wheel slips past under its own torque; too deep and the balance
    # spends its swing dragging the lever out again. A quarter of the tooth is about right,
    # and the two stones must lock equally or the watch runs at two rates on alternate
    # beats.
    #
    # Measured from the stone's INNER FACE, not its centre. The stone sits almost wholly
    # outside the path of the teeth — that is what stops a tooth passing through it — so
    # its centre is well clear of the tooth band and asking where the centre is reports
    # that nothing is locked at all.
    def stone_polys(t):
        out = []
        for colour, pts in pal_g[0].at(t):
            if colour and JEWEL_RGB in colour.upper() and 4 <= len(pts) <= 6:
                key = round(sum(p[0] for p in pts), 1)
                if not any(abs(key - k) < 0.5 for k, _ in out):
                    out.append((key, pts))
        return [p for _, p in out]

    depths = []
    for t in (cycle * 0.25, cycle * 0.75):
        stones = stone_polys(t)
        check(len(stones) == 2, "the lever should carry two jewels, found %d" % len(stones))
        dipped = []
        for st in stones:
            inner = min(math.hypot(x - esc_p[0], y - esc_p[1]) for x, y in st)
            if inner < r_tip:
                dipped.append(r_tip - inner)
        check(len(dipped) == 1,
              "at the banking pin t=%.4f, %d stones reach inside the circle the tooth "
              "tips sweep; exactly one must hold the wheel while the other stands clear "
              "of it" % (t, len(dipped)))
        depths += dipped
    if depths:
        frac = [v / tooth_h for v in depths]
        for f in frac:
            check(0.10 <= f <= 0.40,
                  "a pallet stone locks %.0f%% of the way down the tooth; the lock should "
                  "be between a tenth and two fifths, or the lever is the wrong length "
                  "for this wheel" % (100 * f))
        check(max(depths) - min(depths) < 1.0,
              "the two stones lock at different depths (%.1f and %.1f px below the tip): "
              "the escapement would run unevenly on alternate beats"
              % (min(depths), max(depths)))
        say("  locking     one stone dips %.1f px past the tooth tips, %.0f%% of the tooth"
            % (sum(depths) / len(depths), 100 * sum(frac) / len(frac)))

    # 3 ── impulse. Not "is the jewel at the notch" — the notch is not a thing the document
    # names — but the thing that matters: how close the impulse jewel gets to the fork. It
    # must be among the horns while the lever flips and nowhere near it while locked.
    bj = jewels(bal_g[0], 0.0)
    check(len(bj) == 1, "the balance should carry one impulse jewel, found %d" % len(bj))
    if bj:
        orbit = math.hypot(bj[0][0] - bal_p[0], bj[0][1] - bal_p[1])
        # Over a full beat, the jewel has to come in to the fork, push it over, and then
        # leave it entirely while the balance completes its swing. Three things make that
        # true, and the third is the one that is actually about phase:
        #
        #   it reaches the fork       — otherwise nothing drives the escapement
        #   it clears the fork        — otherwise it never lets go
        #   the closest approach happens AT the flip, not at either extreme
        #
        # An earlier version of this took the smallest distance during the locked part of
        # the beat and expected it to be large. That is dominated by the instant the
        # locked window opens, a hair after the flip, when the jewel is still right beside
        # the fork — so it reported a healthy number for the wrong reason, and a garbage
        # one as soon as the lever was thrown the other way.
        trace = []
        for k in range(400):
            t = k / 400.0 * cycle
            js = jewels(bal_g[0], t)
            if not js:
                continue
            jx, jy = js[0]
            d = min(math.hypot(jx - x, jy - y)
                    for _, pts in pal_g[0].at(t) for x, y in pts)
            trace.append((d, t, CG.evaluate(pal_g[0].angle, {}, t)))
        near, t_near, lever_near = min(trace)
        away = max(d for d, _, _ in trace)
        check(near < 0.25 * orbit,
              "the impulse jewel never gets closer than %.1f to the fork (it orbits at "
              "%.1f): the balance is not driving the escapement" % (near, orbit))
        check(away > 0.8 * orbit,
              "the impulse jewel never gets further than %.1f from the fork: it never "
              "lets go, and the balance is not free to swing" % away)
        # The phase test. Not "where is the lever" — the fork is moving too, so the
        # closest approach is not exactly at the midpoint of the crossing — but "is the
        # lever MOVING". A lever being pushed is a lever in motion; a lever that is
        # already parked against its banking pin when the jewel shows up is being
        # arrived at, not driven.
        h = cycle / 400.0
        def rate(t):
            return abs(CG.evaluate(pal_g[0].angle, {}, t + h)
                       - CG.evaluate(pal_g[0].angle, {}, t - h))
        peak = max(rate(t) for _, t, _ in trace)
        check(rate(t_near) > 0.2 * peak,
              "at the moment the jewel is closest, the lever is moving at %.0f%% of its "
              "crossing speed — it is parked against a banking pin. The balance arrives "
              "after the lever has already gone, so nothing is being driven."
              % (100 * rate(t_near) / (peak or 1e-9)))
        say("  impulse     orbit %.1f; jewel %.1f from the fork at the flip, %.1f away "
            "at the extreme" % (orbit, near, away))

    # 3b ── the jewel must DRIVE the fork, not meet it.
    #
    # Everything up to here would pass just as happily with the lever thrown the wrong
    # way: it still flips at the right instant, the jewel is still at the fork when it
    # does, the jewels still lock at the right depth. What none of that notices is the
    # DIRECTION. The balance drives the lever, so through the impulse the fork has to be
    # travelling the same way as the jewel that is pushing it. If they close on each other
    # the drawing shows a lever being met head-on by the thing meant to throw it.
    #
    # Measured on material points: pick the vertex of the lever nearest the jewel at the
    # moment of impulse, and then follow THAT vertex. Taking "nearest point" afresh at
    # each instant picks a different horn tip as the lever swings and the velocity is
    # nonsense.
    if bj:
        t0 = 0.0
        jx0, jy0 = jewels(bal_g[0], t0)[0]
        shot = pal_g[0].at(t0)
        best = None
        for pi, (_, pts) in enumerate(shot):
            for vi, (x, y) in enumerate(pts):
                d = math.hypot(x - jx0, y - jy0)
                if best is None or d < best[0]:
                    best = (d, pi, vi)
        _, pi, vi = best
        h = 0.0015
        jm, jp = jewels(bal_g[0], t0 - h)[0], jewels(bal_g[0], t0 + h)[0]
        fm = pal_g[0].at(t0 - h)[pi][1][vi]
        fp = pal_g[0].at(t0 + h)[pi][1][vi]
        jv = (jp[0] - jm[0], jp[1] - jm[1])
        fv = (fp[0] - fm[0], fp[1] - fm[1])
        dot = jv[0] * fv[0] + jv[1] * fv[1]
        jn = math.hypot(*jv) or 1e-9
        fn = math.hypot(*fv) or 1e-9
        check(dot > 0,
              "through the impulse the fork moves against the jewel (%.0f degrees apart): "
              "the balance is meant to push the lever over, but these two close on each "
              "other. The lever is being driven from the balance without the sign that "
              "their opposite pivot senses require."
              % math.degrees(math.acos(max(-1.0, min(1.0, dot / (jn * fn))))))
        say("  drive       jewel and fork travel %.0f degrees apart through the impulse"
            % math.degrees(math.acos(max(-1.0, min(1.0, dot / (jn * fn))))))

    # 3c ── the escaping action. The thing the whole mechanism is for.
    #
    # Tested on the SHAPES, not on the jewels' centres. A pallet stone sits almost entirely
    # outside the path of the teeth with only its locking corner dipping in, so its centre
    # is nowhere near the tooth band and any test that asks where the centre is will say
    # the wheel is never held. Worse, the centre test passes happily while a tooth runs
    # clean through the middle of the stone, which is exactly what it did: at both banking
    # positions TWO teeth crossed the engaged jewel and nothing noticed.
    #
    # So: a stone HOLDS a tooth when their outlines are in contact, is CLEAR when it is
    # well away from every tooth, and may never CROSS one. Through each locked phase
    # exactly one stone holds; through the crossing neither does; and the two take turns.
    def teeth_at(t):
        out = []
        for colour, pts in [pr for g in esc_g for pr in g.at(t)]:
            if 5 <= len(pts) <= 14:
                r = max(math.hypot(x - esc_p[0], y - esc_p[1]) for x, y in pts)
                out.append((r, pts))
        if not out:
            return []
        rmax = max(r for r, _ in out)
        return [p for r, p in out if r > rmax - 1.0]

    def stones_at(t):
        out = []
        for colour, pts in pal_g[0].at(t):
            if colour and JEWEL_RGB in colour.upper() and 4 <= len(pts) <= 6:
                key = round(sum(p[0] for p in pts), 1)
                if not any(abs(key - k) < 0.5 for k, _ in out):
                    out.append((key, pts))
        return [p for _, p in out]

    env0 = envelope(esc_all, esc_p, bins=1440)
    contact = 0.18 * tooth_h
    holders, crossed, jam = [], 0, 0
    for k in range(32):
        t = k / 32.0 * cycle
        teeth, stones = teeth_at(t), stones_at(t)
        if len(stones) != 2 or not teeth:
            continue
        lever = CG.evaluate(pal_g[0].angle, {}, t)
        state = []
        for st in stones:
            if any(PARTS.polys_overlap(st, tp) for tp in teeth):
                state.append("cross")
                crossed += 1
            elif min(PARTS.polys_gap(st, tp) for tp in teeth) < contact:
                state.append("hold")
            else:
                state.append("clear")
        if abs(lever) > 0.9 * amp:
            holders.append(tuple(state))
            check(state.count("hold") == 1,
                  "at t=%.4f the lever is against a banking pin but %d rubies are holding "
                  "a tooth; exactly one must hold while the other slips past"
                  % (t, state.count("hold")))
        elif abs(lever) < 0.05 * amp:
            jam += state.count("hold")
    check(crossed == 0,
          "a tooth passes THROUGH a pallet jewel at %d sampled instants: the stones are "
          "reaching into the wheel instead of resting against it" % crossed)
    check(jam == 0,
          "a ruby is still holding a tooth as the lever crosses: the wheel cannot run "
          "and the escapement is jammed")
    sides = {st.index("hold") for st in holders if "hold" in st}
    check(len(sides) == 2,
          "the same ruby holds at both banking pins: the two pallets are not taking "
          "turns, so only one of them is doing any work")
    say("  escaping    one ruby holds, the other clears, nothing crosses a tooth, and "
        "they alternate")

    # 4 ── mesh. Fourth wheel against the pinion on the escape arbor.
    fg, fpts = biggest(fou_g)
    pg, ppts = smallest_toothed(esc_g, esc_p)
    teeth_f, _ = peaks(envelope([(None, fpts)], fou_p))
    # A beat turns the fourth wheel by less than one of its own teeth, so sweeping one
    # beat would test only part of a pitch and could miss the tooth that collides.
    # Four beats carries it past a full pitch whatever the ratio is here.
    worst, worst_t = 1e9, 0.0
    for k in range(400):
        t = k / 400.0 * 0.5
        fw = rotated(fg, fpts, t)
        pw = rotated(pg, ppts, t)
        tab = polar_table(pw, esc_p[0], esc_p[1])
        for x, y in fw:
            a = math.atan2(y - esc_p[1], x - esc_p[0])
            d = math.hypot(x - esc_p[0], y - esc_p[1]) - radius_at(tab, a)
            if d < worst:
                worst, worst_t = d, t
    check(worst > -0.75,
          "the fourth wheel cuts %.2f px into the escape pinion at t=%.4f: they are not "
          "cut to the same module, or the phase is wrong" % (-worst, worst_t))
    say("  mesh        %d teeth on the fourth wheel, clearance %.2f px at worst"
        % (teeth_f, worst))

    # 5 ── beat. One tooth per beat and not a fraction more.
    # ONE TOOTH PER OSCILLATION, not per beat. The pallets are half a pitch apart, so a
    # beat only has to move the wheel far enough for the next tooth to reach the other
    # pallet — half a tooth. Two beats make an oscillation, so teeth per second equals the
    # balance's own frequency, and that is read from the balance rather than assumed.
    a0 = CG.evaluate(esc_g[0].angle, {}, 0.30)
    a1 = CG.evaluate(esc_g[0].angle, {}, 1.30)
    per_sec = abs(a1 - a0) / (2 * math.pi / teeth_e)
    check(abs(per_sec - freq) < 0.02,
          "the escape wheel advances %.3f teeth per unit of t; the balance runs at %.2f "
          "Hz and one whole tooth goes by per oscillation, so it must advance exactly "
          "%.2f. Stepping a full pitch per beat instead of half runs the wheel — and "
          "every hand on the dial — at double speed." % (per_sec, freq, freq))
    say("  beat        %d teeth, %.2f Hz balance, %.3f teeth per unit of t "
        "(%.3f a second on screen)" % (teeth_e, freq, per_sec, per_sec / divisor))

    return FAILURES


def rotated(group, pts, t, vars_=None):
    # `vars_` matters for documents where the wheels are written against a shared
    # variable rather than inline — the movement does that so each rotate stays short.
    a = CG.evaluate(group.angle, vars_ or {}, t)   # radians; see Group.at
    ca, sa = math.cos(a), math.sin(a)
    px, py = group.pivot
    return [(px + (x - px) * ca - (y - py) * sa,
             py + (x - px) * sa + (y - py) * ca) for x, y in pts]



# ── selftest ─────────────────────────────────────────────────────────────────

def _rotations(doc):
    """Every rotate command in the document, so a break can reach in and change one."""
    return [c["rotate"] for c in doc["root"][0]["box"]["children"][0]["commands"]
            if "rotate" in c]



# Breaks name parts by the SHAPE of their motion, never by a frequency constant. Three of
# them were pinned to "sin(25.132741" and stopped matching the moment the going train
# forced the balance from 4 Hz to 2.5 — at which point they silently changed nothing and
# reported themselves caught.
BALANCE = "2.6000 * sin("
LEVER = "max(-1"


def _shift_pivot(doc, which, dx, dy):
    """Move one arbor and everything drawn on it."""
    cmds = commands_of(doc)
    target, moving, touched = None, False, [0]
    for c in cmds:
        if "rotate" in c:
            moving = which in c["rotate"]["angle"]
            if moving:
                target = (c["rotate"]["pivotX"], c["rotate"]["pivotY"])
                c["rotate"]["pivotX"] += dx
                c["rotate"]["pivotY"] += dy
        elif "restore" in c:
            moving = False
        elif moving and "drawPath" in c and isinstance(c["drawPath"]["path"], str):
            c["drawPath"]["path"] = re.sub(
                r"(%s)\s+(%s)" % (_NUM, _NUM),
                lambda m: "%.3f %.3f" % (float(m.group(1)) + dx, float(m.group(2)) + dy),
                c["drawPath"]["path"])
            touched[0] += 1
    _shift_pivot_guard(touched, which)


def _shift_pivot_guard(touched, which):
    if not touched[0]:
        raise AssertionError("break found nothing matching %r to move" % which)


def _scale_about(doc, which, k):
    """Resize whatever is drawn on one arbor, about its own pivot."""
    cmds = commands_of(doc)
    moving, pivot, touched = False, None, [0]
    for c in cmds:
        if "rotate" in c:
            moving = which in c["rotate"]["angle"]
            pivot = (c["rotate"]["pivotX"], c["rotate"]["pivotY"])
        elif "restore" in c:
            moving = False
        elif moving and "drawPath" in c and isinstance(c["drawPath"]["path"], str):
            px, py = pivot
            c["drawPath"]["path"] = re.sub(
                r"(%s)\s+(%s)" % (_NUM, _NUM),
                lambda m: "%.3f %.3f" % (px + (float(m.group(1)) - px) * k,
                                         py + (float(m.group(2)) - py) * k),
                c["drawPath"]["path"])
            touched[0] += 1
    _shift_pivot_guard(touched, which)


def _whole_pitch(doc):
    """Step a whole pitch per beat instead of half: the wheel at double speed."""
    hits = False
    for r in _rotations(doc):
        # `_rotations` hands back the raw angle, still wrapped in its radians-to-degrees
        # multiply, so this has to search rather than anchor at the start.
        m = re.search(r"([-\d.]+) \* \(floor", str(r["angle"]))
        if m:
            # Every staircase, not just the first: the fourth wheel's angle is built out
            # of the escape wheel's, so doubling only one of them would break the gearing
            # test and get caught for the wrong reason.
            r["angle"] = str(r["angle"]).replace(
                m.group(1) + " * (floor", "%.8f * (floor" % (2 * float(m.group(1))))
            hits = True
    if not any(re.search(r"\* \(floor", str(r["angle"])) for r in _rotations(doc)):
        raise AssertionError("cannot find the escape staircase")


def _whole_pitch_span(doc):
    """Put the rubies a whole number of pitches apart instead of n + 1/2.

    Rotating one pallet arm by half a pitch about the lever pivot is the smallest change
    that breaks the span rule while leaving everything else — arm length, lock depth,
    banking — exactly as it was.
    """
    cmds = doc["root"][0]["box"]["children"][0]["commands"]
    moving, pivot, colour, done = False, None, None, 0
    half = math.pi / 15.0
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
            px, py = pivot
            ca, sa = math.cos(half), math.sin(half)
            c["drawPath"]["path"] = re.sub(
                r"(%s)\s+(%s)" % (_NUM, _NUM),
                lambda m: "%.3f %.3f" % (
                    px + (float(m.group(1)) - px) * ca - (float(m.group(2)) - py) * sa,
                    py + (float(m.group(1)) - px) * sa + (float(m.group(2)) - py) * ca),
                c["drawPath"]["path"])
            done += 1
    if not done:
        raise AssertionError("found no rubies on the lever")


def _sink_stones(doc, frac=0.55):
    """Pull the pallet stones in towards the wheel so the teeth run through them.

    The exact shape of the original bug: a stone centred on the locking radius rather than
    standing on it, so it reached right across the tooth band and two teeth crossed it at
    every banking position.
    """
    moving, pivot, colour, hits = False, None, None, 0
    for c in commands_of(doc):
        if "rotate" in c:
            moving = LEVER in str(c["rotate"]["angle"])
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
            ux, uy = cx - pivot[0], cy - pivot[1]
            n = math.hypot(ux, uy) or 1.0
            d = frac * max(math.hypot(q[0] - cx, q[1] - cy) for q in pts)
            c["drawPath"]["path"] = PARTS.poly(
                [(x + d * ux / n, y + d * uy / n) for x, y in pts])
            hits += 1
    if not hits:
        raise AssertionError("found no pallet stones to move")


def _slow_unlock(doc):
    """Let the wheel keep running after the lever has banked.

    The stone drops into the path and the tooth arrives afterwards, through it.
    """
    hits = 0
    for r in _rotations(doc):
        a = str(r["angle"])
        m = re.search(r"fract\(([^)]*)\) / ([\d.]+)", a)
        if m:
            r["angle"] = a.replace(m.group(0), "fract(%s) / %.4f"
                                   % (m.group(1), float(m.group(2)) * 5.0))
            hits += 1
    if not hits:
        raise AssertionError("cannot find the unlock ramp")


BREAKS = [
    ("the pallet stones sunk into the wheel, teeth running through them", _sink_stones),
    ("the wheel still running after the lever has banked", _slow_unlock),
    ("the wheel stepping a whole pitch per beat, at double speed", _whole_pitch),
    ("the rubies a whole pitch apart, so both meet a tooth at once", _whole_pitch_span),
    ("lever 8% longer, so it locks too deep",
     lambda d: _scale_about(d, "max(-1", 1.08)),
    ("lever 8% shorter, so the lock is too shallow to hold",
     lambda d: _scale_about(d, "max(-1", 0.92)),
    ("balance moved 30px away from the fork",
     lambda d: _shift_pivot(d, BALANCE, 0.0, -30.0)),
    ("balance running at 3 Hz while the escapement still beats at 4",
     lambda d: _retune_freq(d, 0.75)),
    ("escape staircase off by a tooth (24 deg -> 26 deg)",
     lambda d: _retime(d, "0.41887902", "0.45378560")),
    ("escape wheel advancing on every half beat",
     lambda d: _retime(d, "floor((8.0000 * t))", "floor((16.0000 * t))")),
    ("fourth wheel cut to a different module",
     lambda d: _scale_about(d, "0.17241", 1.05)),
    ("the clock stopped, so the whole movement is frozen",
     lambda d: _reclock(d, "0")),
    ("the clock running backwards",
     lambda d: _reclock(d, "(3600 * (timeInHr() - 12 * floor(timeInHr() / 12)) "
                           "+ continuousSec()) * -1")),
    ("the clock replaced by something that is not real time",
     lambda d: _reclock(d, "sin(1.0)")),
    ("the clock wrapping hourly, so the hour hand resets on the hour",
     lambda d: _reclock(d, "continuousSec()")),
    ("the balance wired straight to the wall clock, ignoring the speed knob",
     lambda d: _unhook(d, BALANCE)),
    ("the lever thrown the wrong way, so the jewel meets it head-on",
     lambda d: _retime(d, "max(-1, min(1, -9.0000 * sin(", "max(-1, min(1, 9.0000 * sin(")),
    ("the balance a quarter cycle out, arriving when the lever has already gone",
     # Shifted inside the sine, so the balance still LOOKS like a balance to the
     # classifier and the phase test is what has to catch it.
     # Only the balance: shifting the string both parts share would move them together
     # and change nothing about their relationship. Shifted inside the sine, too, so the
     # balance still LOOKS like a balance to the classifier and the phase test is what
     # has to catch it.
     lambda d: _quarter_turn_balance(d)),
    ("lever locked solid, never flipping",
     lambda d: _freeze_lever(d)),
]


def _reclock(doc, value):
    """Replace the movement's clock with something else."""
    for c in doc["root"][0]["box"]["children"][0]["commands"]:
        if "variable" in c and c["variable"].get("name") == "t":
            c["variable"]["value"] = value
            return
    raise AssertionError("no clock to replace")


def _unhook(doc, which):
    """Wire one part straight to the wall clock, behind the movement's back."""
    hits = 0
    for r in _rotations(doc):
        if which in str(r["angle"]):
            r["angle"] = str(r["angle"]).replace("t", "continuousSec()")
            hits += 1
    if not hits:
        raise AssertionError("found no %r to unhook" % which)


def _retune_freq(doc, factor):
    """Run the balance at a different rate while the escapement keeps its own."""
    hits = 0
    for r in _rotations(doc):
        a = str(r["angle"])
        if BALANCE not in a:
            continue
        m = re.search(r"sin\(([\d.]+) \* t", a)
        r["angle"] = a.replace(m.group(0), "sin(%.6f * t" % (float(m.group(1)) * factor))
        hits += 1
    if not hits:
        raise AssertionError("no balance to retune")


def _quarter_turn_balance(doc):
    """Shift the balance a quarter cycle against everything else."""
    hits = 0
    for r in _rotations(doc):
        a = str(r["angle"])
        if BALANCE not in a:
            continue
        m = re.search(r"sin\(([\d.]+) \* t\)", a)
        r["angle"] = a.replace(m.group(0), "sin(%s * t + 1.570796)" % m.group(1))
        hits += 1
    if not hits:
        raise AssertionError("no balance to shift")


def _freeze_lever(doc):
    """Park the lever against one banking pin for good."""
    hits = 0
    for r in _rotations(doc):
        a = str(r["angle"])
        if LEVER in a:
            r["angle"] = re.sub(r"max\(-1, min\(1,[^)]*\)\)", "1", a)
            hits += 1
    if not hits:
        raise AssertionError("no lever to freeze")


def _retime(doc, old, new):
    """Rewrite part of every rotation, and insist it actually changed something.

    A break that silently matches nothing is the worst outcome a selftest can have: the
    checker passes the "broken" document, the run says 8 of 8, and nobody has tested
    anything. One of these breaks was exactly that — it looked for `floor(8.0000 * t)`
    while the document says `floor((8.0000 * t))`, and the missing pair of brackets turned
    the test into a no-op that reported success.
    """
    hits = 0
    for r in _rotations(doc):
        before = str(r["angle"])
        r["angle"] = before.replace(old, new)
        hits += before != r["angle"]
    if not hits:
        raise AssertionError("break found no %r to replace: it would not have broken "
                             "anything" % old)


def selftest():
    base = json.loads(DOC.read_text())
    print("selftest: the checker must pass the shipped document and fail every break\n")
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
            # A break that also crashes the evaluator still counts as caught, but the
            # failures collected before the crash are the ones worth reading — the
            # exception only says the arithmetic gave up, not what was wrong.
            got = list(FAILURES) + ["raised %s: %s" % (type(e).__name__, e)]
        if got:
            print("  caught   %s" % label)
            print("           %s" % got[0][:110])
        else:
            print("  MISSED   %s" % label)
            bad += 1
    print("\n%d of %d breaks caught" % (len(BREAKS) - bad, len(BREAKS)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true",
                    help="break the document on purpose and prove the checker notices")
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
