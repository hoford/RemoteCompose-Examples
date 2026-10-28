#!/usr/bin/env python3
"""pallet — the lever: two jewels, two horns, a guard pin, and a snap.

The pallet fork is the referee between the balance and the going train. Its two jewels sit
over the escape wheel; one of them is always resting against a tooth, holding the whole
train still. The notch at the other end waits for the balance's impulse jewel to come
round and knock it over. When that happens the lever flicks across to the other banking
pin, one jewel releases its tooth and the other catches the next one, and in passing the
escape wheel delivers a push back through the lever to the balance. That push is the only
thing keeping the balance swinging.

So the lever has exactly two resting places and spends almost all its time in one of them.

    clamp(9 * sin(2*pi*f*t))

is a sine made nine times too steep and then clipped: flat at each end — the lever against
a banking pin — with a fast crossing in between. The steepness is what reads as a snap.
A plain sine here would look like a windscreen wiper.

The entry pallet is drawn with its locking face slightly undercut and the exit with a
little draw, which is what keeps a real lever pulled against its banking rather than
floating. At this scale that is two or three pixels, but it is the difference between a
drawing of a lever and a drawing of a wishbone.
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
PIVOT = (210.0, 268.0)          # the lever pivots here; the balance is above, wheel below

ARM = 86.0                      # pivot to pallet jewel
SPREAD = math.radians(31.0)     # half-angle between the two arms, measured from down
TAIL = 118.0                    # pivot to the fork notch
BODY_W = 11.0

BANK = math.radians(10.0)       # how far it swings each way


def rot(p, a, about):
    c, s = math.cos(a), math.sin(a)
    dx, dy = p[0] - about[0], p[1] - about[1]
    return (about[0] + dx * c - dy * s, about[1] + dx * s + dy * c)


def arm_end(sign):
    """Centre of one pallet jewel, in the lever's rest frame."""
    a = math.pi / 2 + sign * SPREAD          # downward, splayed
    return (PIVOT[0] + ARM * math.cos(a), PIVOT[1] + ARM * math.sin(a))


def lever_body():
    """The anchor, as a list of simple overlapping shapes rather than one outline.

    A single polygon round the whole lever self-intersects where the arms meet the tail,
    and the fill rule then hollows the arms out to a pair of lines. Separate convex pieces
    are robust, and for an X-ray the seams where they overlap are not a defect: they read
    as the internal structure of the part, which is the look being aimed at.
    """
    px, py = PIVOT
    out = []
    for sign in (-1, 1):
        a = math.pi / 2 + sign * SPREAD
        dx, dy = math.cos(a), math.sin(a)
        nx, ny = -dy, dx                       # across the arm
        hub_w, tip_w = 12.0, 14.0
        root, tip = 10.0, ARM + 13.0
        out.append(P.poly([
            (px + dx * root + nx * hub_w, py + dy * root + ny * hub_w),
            (px + dx * tip + nx * tip_w, py + dy * tip + ny * tip_w),
            (px + dx * tip - nx * tip_w, py + dy * tip - ny * tip_w),
            (px + dx * root - nx * hub_w, py + dy * root - ny * hub_w),
        ]))
    w = BODY_W
    # The tail: a tapering neck up to the fork, with a horn either side of the notch.
    out.append(P.poly([
        (px - w * 1.15, py + 6),
        (px + w * 1.15, py + 6),
        (px + w * 0.80, py - TAIL + 34),
        (px + w * 2.05, py - TAIL),            # right horn
        (px + w * 1.15, py - TAIL + 6),
        (px + w * 0.46, py - TAIL + 20),       # the notch the impulse jewel enters
        (px - w * 0.46, py - TAIL + 20),
        (px - w * 1.15, py - TAIL + 6),
        (px - w * 2.05, py - TAIL),            # left horn
        (px - w * 0.80, py - TAIL + 34),
    ]))
    return out


def jewel(sign):
    """A pallet jewel: a small rectangle set at an angle into the end of the arm.

    Entry and exit are not mirror images. The entry jewel's locking face leans one way and
    the exit's the other, which is the draw that keeps the lever against its banking pin.
    """
    c = arm_end(sign)
    lean = math.radians(-14.0 if sign < 0 else 20.0)
    hw, hh = 9.0, 17.0
    pts = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    a = math.pi / 2 + sign * SPREAD + lean
    ca, sa = math.cos(a), math.sin(a)
    return P.poly([(c[0] + x * ca - y * sa, c[1] + x * sa + y * ca) for x, y in pts])


def build():
    cmds = P.frame(W, H, "PALLET FORK",
                   "entry and exit jewels · guard pin · snaps between banking pins"
                   + P.speed_note())
    cmds += P.time_var()

    px, py = PIVOT

    # The banking pins do not move: they are what the lever stops against, so they belong
    # to the plate and are drawn outside the rotation.
    cmds.append(P.stroke(P.LINE_DIM, 1.1))
    for s in (-1, 1):
        a = -math.pi / 2 + s * (BANK + math.radians(2.0))
        bx = px + (TAIL - 18) * math.cos(a)
        by = py + (TAIL - 18) * math.sin(a)
        cmds.append({"drawPath": {"path": P.circle_path(bx, by, 5.5, 24)}})

    # The shapes come from the shared module, which is also what the assembly draws. A
    # part that looks one way on its own and another way in the watch is a part nobody can
    # work on: you fix it here, the watch does not change, and you have no idea why.
    body = P.pallet_shapes(px, py, 1.0)

    cmds += P.spin(P.pallet_angle(), px, py, body)
    return cmds


def main():
    doc = P.document(W, H, build(),
                     "A pallet fork seen as an X-ray: two jewels on splayed arms, a "
                     "forked tail with horns and a guard pin, pivoting between two "
                     "banking pins. It rests against one pin or the other and snaps "
                     "across eight times a second.")
    out = HERE / "out" / "pallet.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print("wrote", out)
    print("  swing +/-%.1f deg, locked for most of each beat" % math.degrees(P.PALLET_AMP))
    return 0


if __name__ == "__main__":
    sys.exit(main())
