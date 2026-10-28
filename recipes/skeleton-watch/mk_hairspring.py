#!/usr/bin/env python3
"""hairspring — twelve turns of wire that decide what time it is.

The balance would swing once and stop without this. The hairspring is what makes the
balance a harmonic oscillator rather than a flywheel: it stores the energy at the end of
each swing and gives it back, and the period of the whole thing comes from its stiffness
and the balance's inertia. Nothing else in the watch sets the rate. The going train only
counts.

ITS MOTION IS NOT A ROTATION, which is the whole reason it is worth a document of its own.
Every other part here is a rigid shape turning about a point. The hairspring deforms: the
inner end is pinned to the balance staff and swings with it, the outer end is pinned to a
stud on the balance cock and does not move at all, so the coil between them winds up and
unwinds. It breathes.

That falls out of two observations, and the second one is easy to miss. If the spiral runs
from the inner end at angle `balance` to the outer end at a FIXED angle, then the total
wrap is

    wrap = fixed_angle - balance_angle

so the number of turns is itself a function of the balance. But a changing wrap alone is
not a breathing spring. Pin both radii as well and the wire has to stretch to cover the
extra turns, and what you get is a coil that changes pitch while standing still — turns
sliding through each other. The wire keeping its length is the second half of the idea,
and `spiral` below is where it is paid for.

A real Breguet overcoil lifts the last turn up and over the others to keep the coil
concentric as it breathes. That is a third dimension and this is a flat drawing, so what
is here is a flat spiral — honest about being the simpler kind.
"""

import importlib.util
import json
import math
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("parts", HERE / "parts.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

W = H = 420
CX = CY = 205.0

COLLET_R = 22.0          # the collet on the balance staff: the wire starts ON this
R_OUT = 158.0            # pinned to the stud
TURNS = 12               # whole turns, so the outer end comes back round to the stud
STUD = math.radians(68.0)
SAMPLES = 1500


def spiral(cx, cy, r_in, r_out, turns, stud, name="hair", drive=None, rest=None):
    """The coil, as a path whose shape is an expression in the balance angle.

    THE WIRE HAS TO KEEP ITS LENGTH. That is the whole correction here, and it is worth
    being precise about what the first version got wrong, because it looked plausible.

    It swept from the inner end at angle `bal` to the outer end at a fixed angle, with the
    radius running straight from `r_in` to `r_out`. Both ends land in the right place and
    the wrap grows and shrinks with the balance, which is why it passed a glance. But with
    both radii pinned and the radius strictly linear, the only thing a change in wrap can
    do is change the pitch — the coil never moves in or out. And a spiral of that shape has
    length roughly `mean_radius * wrap`, so winding on an extra half turn silently made the
    wire four percent longer. A spring made of wire that grows when you wind it does not
    breathe; its turns slide through each other, which is exactly what it looked like.

    Conserving the length instead, with both ends still pinned, needs one more degree of
    freedom in the radius — a term that is zero at both ends and free in between:

        r(s) = r_in + (r_out - r_in) * s  +  k * s * (1 - s)

    `s*(1-s)` vanishes at s=0 and s=1, so the collet and the stud never move whatever `k`
    does. The length of a flat spiral is close enough to `wrap * mean(r)`, and the mean of
    that bow over s is `(r_in + r_out)/2 + k/6`, so holding the length at its resting value
    gives `k` directly:

        k = 6 * (L0 / wrap - (r_in + r_out) / 2)

    Wind it tighter and wrap grows, so `k` goes negative and the middle coils draw inward.
    Let it unwind and they push out. Both ends stay pinned the entire time. That is the
    breathing, and the wire is the same length throughout.

    The direction was never wrong: the coil winds clockwise outward, so turning the inner
    end anticlockwise adds wrap and tightens it. What made it look flipped was the outer
    end, which `turns = 11.5` left sitting diametrically opposite its own stud.
    """
    # `drive` is whatever turns the inner end — the balance for a hairspring, the barrel
    # arbor for a mainspring — and `name` keeps two coils in one document from trying to
    # claim the same variables. A document that defines `bal` twice does not draw two
    # springs; it fails to convert.
    drive = P.balance_angle() if drive is None else drive
    rest = P.balance_rest() if rest is None else rest
    fixed = stud + 2 * math.pi * turns
    mean = (r_in + r_out) / 2.0
    span = fixed - rest                      # wrap when the driver is at its rest position
    length = mean * span                     # the wire, measured once and then kept
    v_d, v_w, v_b = name + "_d", name + "_w", name + "_b"
    return [
        {"variable": {"name": v_d, "value": drive, "commit": True}},
        # Total wrap from the inner end to the stud. The stud does not move, so when the
        # balance turns one way this grows and the coil tightens; the other way, it opens.
        {"variable": {"name": v_w, "value": "%.6f - %s" % (fixed, v_d),
                      "commit": True}},
        # How far the middle of the coil has to move to keep the wire the same length.
        {"variable": {"name": v_b,
                      "value": "6 * (%.4f / %s - %.4f)" % (length, v_w, mean),
                      "commit": True}},
        {"pathExpression": {
            "id": name,
            "expressionX": "%.2f + (%.3f + %.3f * a[0] + %s * a[0] * (1 - a[0]))"
                           " * cos(%s + a[0] * %s)"
                           % (cx, r_in, r_out - r_in, v_b, v_d, v_w),
            "expressionY": "%.2f + (%.3f + %.3f * a[0] + %s * a[0] * (1 - a[0]))"
                           " * sin(%s + a[0] * %s)"
                           % (cy, r_in, r_out - r_in, v_b, v_d, v_w),
            "start": 0, "end": 1, "count": SAMPLES, "flags": 4}},
    ]


def build():
    cmds = P.frame(W, H, "HAIRSPRING",
                   "12 turns · pinned at both ends · the wire keeps its length"
                   + P.speed_note())
    cmds += P.time_var()
    cmds += spiral(CX, CY, COLLET_R, R_OUT, TURNS, STUD)

    cmds.append(P.stroke(P.LINE, 1.15))
    cmds.append({"drawPath": {"path": "hair"}})

    # The collet at the inner end turns with the balance; the stud at the outer end does
    # not. Showing both is the only way the drawing says which end is which — and both
    # have to actually touch the wire, or the eye reads the whole coil as detached.
    cmds.append(P.stroke(P.LINE_DIM, 1.1))
    cmds.append({"drawPath": {"path": P.circle_path(CX, CY, COLLET_R, 32)}})
    # On the stud, not near it: with a whole number of turns the outer end comes back
    # round to the stud's own bearing, so this is where the wire actually finishes.
    sx = CX + R_OUT * math.cos(STUD)
    sy = CY + R_OUT * math.sin(STUD)
    cmds.append(P.fill(P.wash(P.GOLD, 0x40)))
    cmds.append({"drawPath": {"path": P.circle_path(sx, sy, 8.0, 24)}})
    cmds.append(P.stroke(P.GOLD, 1.3))
    cmds.append({"drawPath": {"path": P.circle_path(sx, sy, 8.0, 24)}})
    return cmds


def main():
    doc = P.document(W, H, build(),
                     "A watch hairspring seen as an X-ray: twelve turns of flat spiral, "
                     "pinned to the collet on the balance staff at the inner end and to a "
                     "fixed stud at the outer. It does not rotate. It winds and unwinds as "
                     "the balance swings, and because the wire keeps its length the coils "
                     "draw inward as it tightens and push out again as it opens.")
    out = HERE / "out" / "hairspring.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print("wrote", out)
    print("  %d turns at rest, wrap varies by +/-%.2f rad; wire length held constant"
          % (TURNS, P.BALANCE_AMP))
    return 0


if __name__ == "__main__":
    sys.exit(main())
