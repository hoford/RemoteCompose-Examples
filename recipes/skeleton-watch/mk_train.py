#!/usr/bin/env python3
"""train — the two shapes the going train is made of: a wheel and a pinion.

Writes two documents, because they are two parts, but one generator because they are the
same idea at two scales and the interesting thing is the contrast between them.

A WHEEL has many fine teeth and almost no metal: a thin rim carried on four or five narrow
arms, with the openings between the arms taking most of the area. That is not styling. The
wheel has to be light, because every scrap of inertia in the train is energy the mainspring
spends accelerating brass instead of running the watch, and it has to be stiff, which a rim
on arms is and a disc of the same weight is not.

A PINION is the opposite: six to ten fat leaves on a solid body, no crossings at all. It is
small, so there is nothing to save by hollowing it, and it takes the full torque of the
wheel driving it. Its leaves are not small wheel teeth either — with eight of them the
flanks run nearly radial and the tips are well rounded, which is why the profile here is
its own rather than the wheel's with a low count.

They turn at the ratio of their counts and in opposite directions, which is the only motion
either of them has: a going-train wheel is the easy case, a constant angular velocity.
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


def wheel_doc(teeth=64, arms=5, module=4.2, rate=0.22, label="WHEEL"):
    cmds = P.frame(W, H, label,
                   "%d teeth · %d crossings · constant rate%s"
                   % (teeth, arms, P.speed_note()))
    cmds += P.time_var()

    # The shapes come from the shared module, which is also what the assembly draws. A
    # part that looks one way on its own and another way in the watch is a part nobody can
    # work on: you fix it here, the watch does not change, and you have no idea why.
    body = P.wheel_shapes(CX, CY, teeth, module, arms)

    cmds += P.spin("t * %.5f" % rate, CX, CY, body)
    return cmds


def pinion_doc(leaves=8, module=9.0, rate=-1.76, label="PINION"):
    cmds = P.frame(W, H, label,
                   "%d leaves · solid body · %.1fx the wheel's rate, opposite sense%s"
                   % (leaves, abs(rate / 0.22), P.speed_note()))
    cmds += P.time_var()

    body = P.pinion_shapes(CX, CY, leaves, module)

    cmds += P.spin("t * %.5f" % rate, CX, CY, body)
    return cmds


def main():
    out = HERE / "out"
    out.mkdir(parents=True, exist_ok=True)

    wheel = P.document(W, H, wheel_doc(),
                       "A watch train wheel seen as an X-ray: sixty-four fine teeth on a "
                       "thin rim carried by five narrow arms, turning at a constant rate. "
                       "The openings between the arms are most of its area, because a "
                       "train wheel has to be light as well as stiff.")
    (out / "wheel.json").write_text(json.dumps(wheel, indent=1) + "\n")

    pinion = P.document(W, H, pinion_doc(),
                        "A watch pinion seen as an X-ray: eight fat leaves on a solid "
                        "body, with no crossings, turning fast and the other way. A "
                        "pinion is small enough that there is nothing to gain by "
                        "hollowing it.")
    (out / "pinion.json").write_text(json.dumps(pinion, indent=1) + "\n")

    print("wrote", out / "wheel.json")
    print("wrote", out / "pinion.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
