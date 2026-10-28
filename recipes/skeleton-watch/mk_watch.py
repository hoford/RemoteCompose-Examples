#!/usr/bin/env python3
"""watch — the parts stacked into one transparent drawing.

Every shape here comes from the same builders the individual part documents use, so what
you see assembled is exactly what you see alone. Nothing is redrawn for the assembly; that
is the whole reason the geometry lives in the shared module.

THE LAYOUT IS SOLVED, NOT ARRANGED. Three constraints fix it and there is nothing left to
nudge:

  * the pallet jewels must sit on the escape wheel's locking circle, which puts the lever
    pivot at   D = A*cos(spread) + sqrt(R_lock^2 - (A*sin(spread))^2)   above the wheel
  * the balance's impulse jewel must reach the notch between the lever's horns, which puts
    the balance staff one jewel-radius beyond it
  * the fourth wheel must mesh the escape pinion, which fixes their centre distance at
    m*(Nw+Np)/2 and the pinion's phase by the reflection rule

Place them by eye instead and the drawing is of three parts that happen to be near each
other rather than of a mechanism.

THE PHASES ARE ONE PHASE. The balance swings, and a quarter of a beat later the lever is
knocked across, and the escape wheel runs one tooth. All three read the same `t` and the
same beat, so the impulse jewel arrives at the notch at the moment the lever moves — which
is the only thing that makes the picture read as cause and effect rather than as three
animations playing at once.

Drawn as an X-ray: thin bright edges, fills at about eight percent, so the places where
parts overlap are brighter and you can see the lever through the wheel beneath it.
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

hs_spec = importlib.util.spec_from_file_location("hair", HERE / "mk_hairspring.py")
HAIR = importlib.util.module_from_spec(hs_spec)
hs_spec.loader.exec_module(HAIR)

W = H = 560

S_ESC = 0.62                  # the parts are drawn at their own scale; shrink to fit
S_PAL = 0.74
S_BAL = 0.56

TRAIN_MODULE = 2.9
FOURTH_TEETH = 58
ESC_PINION_TEETH = 10
TRAIN_BETA = math.radians(196.0)     # where the fourth wheel sits from the escape arbor
SENSE = -1                           # the escape wheel turns anticlockwise; see build()

FILL_FRAC = 0.94                     # how much of the frame the mechanism takes
CAPTION = 44                         # reserved at the bottom for the title block


def layout(k=1.0):
    """Solve the escapement geometry at an overall scale `k`.

    The escapement is no longer arranged here: `parts.escapement_layout` solves it from
    the wheel outwards, and what this does is place that solution on the canvas and hang
    the balance and the fourth wheel off it.

    Every length is linear in `k`, which is what makes the two-pass fit in `build`
    legitimate: solve once at k=1 to find out how big the mechanism wants to be, then solve
    again at the k that makes it fill the canvas. Scaling the *result* of the first pass
    would work too, but only by accident — it would stop working the moment a constraint
    stopped being homogeneous, and solving twice costs nothing.
    """
    s_esc, s_bal, module = S_ESC * k, S_BAL * k, TRAIN_MODULE * k
    r_tip = 150.0 * s_esc
    tooth_h = (150.0 - 118.0) * s_esc
    E = P.escapement_layout(r_tip, tooth_h)
    s_pal = E["pallet_scale"] * s_esc * (150.0 / 150.0)
    # pallet_scale is relative to PALLET_ARM at scale 1, and the solver worked in the same
    # units as r_tip, so it already carries s_esc.
    s_pal = E["arm"] / P.PALLET_ARM

    esc = (0.0, 0.0)
    lever = (0.0, -E["pivot_dist"])
    # The notch between the horns, and the balance staff one impulse-jewel beyond it.
    notch_y = lever[1] - (P.PALLET_TAIL - 20.0) * s_pal
    balance = (0.0, notch_y - P.BALANCE_JEWEL_R * s_bal)
    # The fourth wheel, meshing the pinion on the escape arbor.
    c = module * (FOURTH_TEETH + ESC_PINION_TEETH) / 2.0
    fourth = (esc[0] + c * math.cos(TRAIN_BETA), esc[1] + c * math.sin(TRAIN_BETA))
    return {"orient": 0.0, "tooth_h": tooth_h,
            "esc": esc, "lever": lever, "balance": balance, "fourth": fourth,
            "centre_dist": c, "s_esc": s_esc, "s_pal": s_pal, "s_bal": s_bal,
            "module": module, "E": E, "r_tip": r_tip}


def ruby_polys(g, at, lever):
    """The two pallet stones as polygons, with the lever at `lever` radians."""
    out, colour = [], None
    for c in P.pallet_shapes(at[0], at[1], g["s_pal"], spread=g["E"]["spread"],
                             sense=SENSE, wheel_dist=g["E"]["pivot_dist"],
                             tooth_h=g["tooth_h"]):
        if "paint" in c:
            for op in c["paint"]["ops"]:
                if "color" in op:
                    colour = op["color"]
        elif "drawPath" in c and colour and P.JEWEL[3:].upper() in colour.upper():
            pts = P._poly_pts(c["drawPath"]["path"])
            if not any(abs(sum(q[0] for q in pts) - sum(q[0] for q in o)) < 0.5
                       for o in out):
                out.append(pts)
    ca, sa = math.cos(lever), math.sin(lever)
    return [[(at[0] + (x - at[0]) * ca - (y - at[1]) * sa,
              at[1] + (x - at[0]) * sa + (y - at[1]) * ca) for x, y in pts]
            for pts in out]


def tooth_polys(g, esc_at, phase):
    """The escape wheel's tooth polygons with the wheel at `phase`."""
    out, colour = [], None
    for c in P.escape_shapes(esc_at[0], esc_at[1], g["r_tip"] / 150.0,
                             teeth=P.ESCAPE_TEETH, opaque=False, sense=SENSE):
        if "paint" in c:
            for op in c["paint"]["ops"]:
                if "color" in op:
                    colour = op["color"]
        elif "drawPath" in c and colour and colour == P.LINE:
            pts = P._poly_pts(c["drawPath"]["path"])
            if 5 <= len(pts) <= 14:
                out.append(pts)
    ca, sa = math.cos(phase), math.sin(phase)
    return [[(esc_at[0] + (x - esc_at[0]) * ca - (y - esc_at[1]) * sa,
              esc_at[1] + (x - esc_at[0]) * sa + (y - esc_at[1]) * ca) for x, y in pts]
            for pts in out]


def wheel_phase(g, esc_at, lever_at):
    """Start the wheel so a tooth comes to rest ON the locking stone, not inside it."""
    pitch = 2.0 * math.pi / P.ESCAPE_TEETH
    rest = SENSE * pitch / 2.0
    # Banking pin -1 holds with the wheel where the beat left it; by banking pin +1 the
    # wheel has run on by half a pitch, which is the whole point of the escapement.
    banks = [(ruby_polys(g, lever_at, g["orient"] - P.PALLET_AMP), 0.0),
             (ruby_polys(g, lever_at, g["orient"] + P.PALLET_AMP), SENSE * pitch / 2.0)]
    ph, gap = P.solve_lock_phase(
        lambda a: tooth_polys(g, esc_at, a + rest), banks, pitch)
    if ph is None:
        raise SystemExit("no wheel phase locks without the teeth cutting into a stone")
    return ph, gap


def extent(g):
    """Half-width and half-height of everything, about its own centre."""
    discs = [(g["esc"], g["r_tip"]), (g["lever"], 30.0 * g["s_pal"]),
             (g["balance"], 150.0 * g["s_bal"]),
             (g["fourth"], g["module"] * FOURTH_TEETH / 2.0 + 3)]
    xs = [c[0] + d for c, r in discs for d in (-r, r)]
    ys = [c[1] + d for c, r in discs for d in (-r, r)]
    return min(xs), max(xs), min(ys), max(ys)


def build():
    # Pass one at k=1 to measure, pass two at the k that fills the canvas. The caption
    # takes the bottom of the frame, so the height available is short of the full canvas.
    g = layout()
    x0, x1, y0, y1 = extent(g)
    k = min(W * FILL_FRAC / (x1 - x0), (H - CAPTION) * FILL_FRAC / (y1 - y0))
    g = layout(k)
    x0, x1, y0, y1 = extent(g)

    dx = W / 2.0 - (x0 + x1) / 2.0
    dy = (H - CAPTION) / 2.0 - (y0 + y1) / 2.0

    def at(p):
        return (p[0] + dx, p[1] + dy)

    E, L, B, F = at(g["esc"]), at(g["lever"]), at(g["balance"]), at(g["fourth"])
    S_e, S_p, S_b, MOD = g["s_esc"], g["s_pal"], g["s_bal"], g["module"]
    centre_dist = g["centre_dist"]

    cmds = P.frame(W, H, "SWISS LEVER ESCAPEMENT",
                   "balance %g Hz · lever snaps · one tick a second" % P.FREQ
                   + P.speed_note())
    cmds += P.time_var()

    # The wheel runs anticlockwise. That is not a style choice: there are three meshes
    # between the escape wheel and the centre wheel, an odd number, so the centre reverses
    # relative to the escape wheel — and the centre carries the minute hand, which has to
    # go clockwise. The tooth and jewel profiles are mirrored to match.
    phase, lock_gap = wheel_phase(g, E, L)
    esc_angle = P.escape_angle(sense=SENSE, phase=phase)

    # Fourth wheel, behind everything. It meshes the pinion on the escape arbor, so it
    # turns the other way at the ratio of the counts, and its tooth phase comes from the
    # same reflection rule the gear documents use.
    ratio = ESC_PINION_TEETH / float(FOURTH_TEETH)
    alpha = (TRAIN_BETA + math.pi - math.pi / FOURTH_TEETH
             + ratio * (TRAIN_BETA - 0.0))
    fourth_angle = "%.6f - (%s) * %.6f" % (alpha, esc_angle, ratio)
    # Drawn in its dim edge colour, because it is a plane below the escapement and should
    # read as the thing in the background that the eye skips over on the way to the lever.
    cmds += P.spin(fourth_angle, F[0], F[1],
                   P.wheel_shapes(F[0], F[1], FOURTH_TEETH, MOD, arms=5,
                                  opaque=False, edge=P.LINE_DIM))

    # The escape wheel and, on the same arbor, its pinion. One angle drives both.
    cmds += P.spin(esc_angle, E[0], E[1],
                   P.escape_shapes(E[0], E[1], S_e, opaque=False, sense=SENSE))
    cmds += P.spin(esc_angle, E[0], E[1],
                   P.wheel_shapes(E[0], E[1], ESC_PINION_TEETH, MOD, arms=3,
                                  opaque=False))

    # The lever, then the balance over it: the balance is the top plate of this stack and
    # you should be able to see the lever through it.
    cmds += P.spin(P.pallet_angle(), L[0], L[1],
                   P.pallet_shapes(L[0], L[1], S_p, spread=g["E"]["spread"], sense=SENSE,
                                   wheel_dist=g["E"]["pivot_dist"],
                                   tooth_h=g["tooth_h"]))
    cmds += P.spin(P.balance_angle(), B[0], B[1],
                   P.balance_shapes(B[0], B[1], S_b, opaque=False))

    # The hairspring last. It belongs under the balance and in an X-ray that makes no
    # difference to where it is drawn, only to whether you can see it: eleven turns of
    # hair-fine wire lose every argument with a wheel rim drawn over the top of them.
    # Whole turns, so the outer end comes back round to its own bearing rather than
    # finishing across the coil from it, and the inner end starts on the balance's staff
    # rather than floating beside it.
    cmds += HAIR.spiral(B[0], B[1], 22.0 * S_b, 130.0 * S_b - 7, 11,
                        math.radians(68.0))
    cmds.append(P.stroke(P.LINE_DIM, 0.9))
    cmds.append({"drawPath": {"path": "hair"}})

    # The jewelled bearings each part turns in. They belong to the plate, so they do not
    # move with anything.
    cmds.append(P.fill(P.wash(P.JEWEL, 0x40)))
    for c in (E, L, B, F):
        cmds.append({"drawPath": {"path": P.circle_path(c[0], c[1], 6.0 * S_p, 20)}})
    cmds.append(P.stroke(P.JEWEL, 1.1))
    for c in (E, L, B, F):
        cmds.append({"drawPath": {"path": P.circle_path(c[0], c[1], 6.0 * S_p, 20)}})

    return cmds, (E, L, B, F, centre_dist)


def main():
    cmds, geom = build()
    doc = P.document(W, H, cmds,
                     "A Swiss lever escapement drawn as an X-ray: a fourth wheel driving "
                     "the pinion on the escape arbor, a fifteen-tooth escape wheel that "
                     "advances half a tooth per beat, a pallet lever snapping between its "
                     "banking pins, and a balance wheel swinging four times a second over "
                     "its hairspring. Every part is translucent, so the mechanism can be "
                     "read through itself.")
    out = HERE / "out" / "watch.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n")
    E, L, B, F, c = geom
    print("wrote", out)
    print("  escape  (%6.1f,%6.1f)" % E)
    print("  lever   (%6.1f,%6.1f)   %.1f above the escape arbor" % (L[0], L[1], E[1] - L[1]))
    print("  balance (%6.1f,%6.1f)   %.1f above the lever" % (B[0], B[1], L[1] - B[1]))
    print("  fourth  (%6.1f,%6.1f)   centre distance %.1f (want %.1f)"
          % (F[0], F[1], math.hypot(F[0] - E[0], F[1] - E[1]), c))
    return 0


if __name__ == "__main__":
    sys.exit(main())
