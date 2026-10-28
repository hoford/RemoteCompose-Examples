#!/usr/bin/env python3
"""balance — the oscillator: a weighted rim, three arms, and the roller that drives it.

Everything else in the watch is a consequence of this wheel. It is a torsional pendulum:
a rim with most of its mass as far from the centre as possible, held by a hairspring, and
its period depends on the rim's inertia and the spring's stiffness — not on how hard it
is pushed. That is the whole trick of a mechanical watch. The going train is only there to
give the balance a nudge twice per swing and to count the swings.

So this is the one part whose motion is a plain sine:

    A * sin(2*pi*f*t)

at four cycles a second for a 28,800 vph movement. The timing screws around the rim are
not decoration — they are how the rate is adjusted, by moving mass in or out.

Underneath the wheel sit two smaller discs on the same staff. The impulse roller carries a
single jewel standing proud of its edge; once per half-swing that jewel sweeps through the
notch in the pallet fork and knocks the lever across. The safety roller behind it is a disc
with one crescent cut in it, and the lever's guard pin rides against it — the crescent only
lines up at the instant the impulse jewel is in the notch, so the lever cannot be unlocked
at any other moment. That is the "safety" in Swiss lever safety escapement.
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
CX = CY = 200.0

SCREWS = 12              # every other dimension lives in parts.balance_shapes


def build():
    cmds = P.frame(W, H, "BALANCE WHEEL",
                   "3 arms · 12 timing screws · impulse jewel · %.1f Hz" % P.FREQ
                   + P.speed_note())
    cmds += P.time_var()

    # The shapes come from the shared module, which is also what the assembly draws. A
    # part that looks one way on its own and another way in the watch is a part nobody can
    # work on: you fix it here, the watch does not change, and you have no idea why.
    body = P.balance_shapes(CX, CY, 1.0, SCREWS)
    cmds += P.spin(P.balance_angle(), CX, CY, body)
    return cmds


def main():
    doc = P.document(W, H, build(),
                     "A balance wheel seen as an X-ray: a weighted rim on three arms with "
                     "twelve timing screws, swinging four times a second, carrying the "
                     "impulse roller and its single jewel and the notched safety roller "
                     "beneath it.")
    out = HERE / "out" / "balance.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print("wrote", out)
    print("  amplitude +/-%.0f deg at %.1f Hz" % (math.degrees(P.BALANCE_AMP), P.FREQ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
