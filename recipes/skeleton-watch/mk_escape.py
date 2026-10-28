#!/usr/bin/env python3
"""escape — the escape wheel: fifteen club teeth, four crossings, and a staircase.

The tooth is the part worth getting right. An escape-wheel tooth is not a gear tooth: it
is a slender neck leaning backwards out of the rim, carrying a club at its end. The club
has two working surfaces and they do different jobs — a short locking face that a pallet
jewel rests against while the balance swings, and a flat impulse plane that slides under
the jewel and pushes it on its way. Everything between them is undercut so it clears.

THE MOTION is the real point. The wheel is stationary for most of its life. It sits
locked against a pallet jewel, the balance swings all the way out and all the way back,
and only when the lever is knocked over does the wheel run forward by exactly one tooth
and lock again. So the angle is a staircase:

    floor(beat)                how many teeth have gone by
    fract(beat)                where we are within the current one
    advance over the first 16% of the beat, then nothing

Give the wheel a sine and it reads as a fan. The stillness is what makes it a watch.
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

TEETH = P.ESCAPE_TEETH
R_TIP = 150.0
R_RIM = 118.0            # outer edge of the rim the teeth stand on
R_RIM_IN = 100.0
R_HUB = 26.0
ARMS = 4
ARM_HALF = 7.0


def club_tooth(i):
    """One tooth, in the wheel's own frame.

    Written as fractions of a pitch so the shape keeps its proportions at any tooth count.
    """
    pitch = 2 * math.pi / TEETH
    a = pitch * i

    def pt(r, f):
        ang = a + f * pitch
        return (CX + r * math.cos(ang), CY + r * math.sin(ang))

    return P.poly([
        pt(R_RIM, -0.30),          # out of the rim
        pt(R_RIM + 6, -0.26),
        pt(R_TIP - 20, -0.085),    # the neck, leaning back against rotation
        pt(R_TIP - 9, -0.055),     # heel of the club
        pt(R_TIP, -0.025),         # the locking face: short, nearly radial
        pt(R_TIP, 0.085),          # the impulse plane: flat across the top
        pt(R_TIP - 13, 0.125),     # the toe drops away
        pt(R_RIM + 3, 0.175),      # undercut, so the next jewel clears
        pt(R_RIM, 0.21),
    ])


def build():
    cmds = P.frame(W, H, "ESCAPE WHEEL",
                   "%d club teeth · locked, half a tooth, locked · %g a second"
                   % (TEETH, 2 * P.FREQ)
                   + P.speed_note())
    cmds += P.time_var()

    # The shapes come from the shared module, which is also what the assembly draws. A
    # part that looks one way on its own and another way in the watch is a part nobody can
    # work on: you fix it here, the watch does not change, and you have no idea why.
    body = P.escape_shapes(CX, CY, 1.0, TEETH)

    cmds += P.spin(P.escape_angle(TEETH), CX, CY, body)
    return cmds


def main():
    doc = P.document(W, H, build(),
                     "An escape wheel of fifteen club teeth on four crossings, seen as an "
                     "X-ray. It is still for most of each beat, locked against a pallet "
                     "jewel, then runs forward by exactly one tooth and locks again.")
    out = HERE / "out" / "escape.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print("wrote", out)
    print("  %d teeth, advance %.0f%% of a beat, %g ticks a second"
          % (TEETH, P.UNLOCK * 100, 2 * P.FREQ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
