#!/usr/bin/env python3
"""skeleton_watch — the whole watch, built outwards from the escapement until it tells the time.

Five layers, drawn back to front, each one hanging off the one before it:

    1  barrel        the mainspring's drum, turning once in eight hours
    2  going train   centre and third wheels: the gearing that counts beats
    3  escapement    escape wheel, lever, balance, hairspring — layer 1 of this corpus
    4  motion work   cannon pinion, minute wheel, hour wheel: the 12:1 for the hour hand
    5  dial          the minute track, the numerals, and three hands

NOTHING HERE IS DECORATIVE GEARING. Every wheel's angle is derived from the escape wheel's
by the ratio of the teeth actually drawn on it, so the hands are not animated to the right
speed — they arrive at it. Change a tooth count and the hands change with it, which is the
only way to be sure the picture is of a watch rather than of some wheels and a clock.

THE TRAIN, and why these counts:

    balance 0.5 Hz                -> one tick a second
    escape wheel  20 t            -> 7.5 rev/min
    escape pinion 10 <- fourth 75 ->  1 rev/min     the SECOND hand
    fourth pinion 10 <- third  80 ->  1/8 rev/min
    third pinion  12 <- centre 90 ->  1/60 rev/min  the MINUTE hand
    centre pinion 10 <- barrel 80 ->  1/480 rev/min = one turn in eight hours

    cannon pinion 12 -> minute wheel 36
    minute pinion 10 -> hour wheel   40            1/720 rev/min = the HOUR hand

    check: 1 rev/min * 30 teeth / 60 = 0.5 teeth/sec = the balance's own 0.5 Hz,
    and half a pitch per beat is 1/60 of a turn — one second-mark per tick.

THE WHEEL DIRECTIONS ARE NOT FREE. There are two meshes between the escape wheel and the
centre wheel, an even number, so they turn the same way — and the centre carries the minute
hand, which has to go clockwise. So the escape wheel runs clockwise too. With the old
three-mesh train it was forced the other way, and its teeth and the pallet stones had to be
drawn mirrored; now they are not.

WHAT TIME IT SHOWS. The real one. `continuousSec()` is not elapsed time — the player
computes it as `minute*60 + second + millis/1000`, the second within the hour, accurate to
the millisecond. Extend it over the twelve hours a dial covers,

    t = 3600 * (timeInHr() mod 12) + continuousSec()

and every hand, being a plain gear ratio off `t`, reads the correct time with no offset of
its own. The seconds hand ticks once a second because the escape wheel does.
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

W = H = 720
# No caption and no margin: this one is the finished watch, not a plate in a study, so it
# is a dial and nothing else. The parts documents keep their captions — you need to be told
# which part you are looking at — but a watch face with a label under it is a diagram.
CAPTION = 0
FILL_FRAC = 0.995

ESC_TEETH = P.ESCAPE_TEETH
# Two meshes between the centre wheel and the escape wheel now, an EVEN number, so they
# turn the same way — and the centre carries the minute hand. The escape wheel therefore
# runs CLOCKWISE, where the old three-mesh train with a fourth wheel forced it backwards.
SENSE = 1

# (name, wheel teeth, pinion teeth on the same arbor)
BARREL, CENTRE, THIRD = 80, 80, 75
# No pinion below parts.MIN_PINION. That constraint, plus a seconds hand on the
# fourth wheel, is what picks the beat rate: at 0.5 Hz on a thirty-tooth escape
# wheel every pinion can be ten leaves or more and the fourth wheel comes out at
# 75, smaller than the centre wheel, which is how a real watch is laid out.
#
# The counts also have to be DISTINCT enough. With centre 80 / third 75 / fourth 75
# the third and fourth arbors are spanned equally well by two different pairings —
# third wheel into fourth pinion, or third pinion into fourth wheel — and nothing in
# the geometry says which is the real mesh. Watches avoid repeating counts anyway, to
# spread the wear; here it also keeps the drawing unambiguous.
CENTRE_PIN, THIRD_PIN, ESC_PIN = 10, 10, 10
CANNON, MINUTE_WHEEL, MINUTE_PIN, HOUR_WHEEL = 12, 36, 10, 40

MODULE = 1.0                    # one module for the whole train; scaled at the end
MW_MODULE_A = 1.30              # motion work runs finer than the train
R_ESC = 27.0                    # escape wheel tip radius; it carries the seconds hand
R_BAL = 31.0                    # balance rim, in modules

D_CE = 66.0                     # centre to escape: the seconds subdial sits at six o'clock
THETA_E = math.radians(243.0)   # which way the escapement points out of the escape wheel
BETA_CB = math.radians(312.0)   # centre -> barrel
BETA_CM = math.radians(62.0)    # centre -> minute wheel post


def mesh_phase(beta, n_driver, n_driven, phase_driver):
    """Where the driven wheel's teeth have to start so they fall into the driver's gaps.

    Two steps, and conflating them is how this goes wrong. First the rule in terms of each
    wheel's TOTAL angle — the bearing of its own tooth zero. Rolling without slipping gives
    `theta_B = C - (NA/NB) * theta_A`, and meshing demands that whenever A has a tooth on
    the line of centres, B has a gap facing it:

        theta_A = beta (mod 2pi/NA)  =>  theta_B = beta + pi + pi/NB (mod 2pi/NB)

    Substituting theta_A = beta gives `C = beta + pi + pi/NB + (NA/NB)*beta`, which depends
    on the bearing and the two counts and nothing else.

    But C is not what goes in the document. Each wheel here is written `ph + esc * R`, so
    theta_A carries its own constant ph_A, and matching the constant terms of
    `theta_B = C - (NA/NB)*theta_A` gives what is actually needed:

        ph_B = C - (NA/NB) * ph_A

    That last term looks like double counting and is not: it converts a rule stated about
    total angles into the constant of an expression whose driver already carries one.
    Dropping it threw four of the six meshes five to seven pixels into each other.

    `phase_driver` is the driver's WRITTEN constant, which is not always its phase. The
    escape arbor's angle in this document is the bare variable `esc`, and its phase lives
    inside that variable — so for the one mesh driven straight off it, the written constant
    is zero. Passing the escape wheel's phase there instead put the fourth wheel an eighth
    of a pitch out: enough to cut four pixels in, and small enough to look fine.
    """
    return (beta + math.pi + math.pi / n_driven
            + (float(n_driver) / n_driven) * (beta - phase_driver))


def layout(m=MODULE):
    """Every centre, in modules. The train is a chain of solved triangles, not a sketch."""
    centre = (0.0, 0.0)
    escape = (0.0, D_CE * m)

    # The third wheel is wherever both its meshes can be satisfied at once: distance
    # d(centre, third) from one and d(third, escape) from the other. Two circles, two
    # intersections; take the one to the right so the train winds clockwise round the
    # plate and leaves the left side for the balance.
    a = (CENTRE + THIRD_PIN) / 2.0 * m
    b = (THIRD + ESC_PIN) / 2.0 * m
    c = D_CE * m
    y = (c * c + a * a - b * b) / (2.0 * c)
    x = math.sqrt(max(a * a - y * y, 0.0))
    third = (x, y)

    d_cb = (BARREL + CENTRE_PIN) / 2.0 * m
    barrel = (centre[0] + d_cb * math.cos(BETA_CB),
              centre[1] + d_cb * math.sin(BETA_CB))

    d_cm = (CANNON + MINUTE_WHEEL) / 2.0 * MW_MODULE_A * m
    minute = (centre[0] + d_cm * math.cos(BETA_CM),
              centre[1] + d_cm * math.sin(BETA_CM))
    # The hour wheel is coaxial with the cannon pinion, so the second motion-work mesh has
    # to span the same distance with different counts -- which only works if it is cut to
    # its own module. That is what real motion work does.
    mw_module_b = 2.0 * d_cm / ((MINUTE_PIN + HOUR_WHEEL) * m)

    # The escapement, solved from the escape wheel outwards and then pointed outwards.
    r_tip = R_ESC * m
    tooth_h = (150.0 - 118.0) / 150.0 * r_tip
    E = P.escapement_layout(r_tip, tooth_h)
    # carried through so the stones can be placed by their locking face

    s_pal = E["arm"] / P.PALLET_ARM
    s_bal = R_BAL * m / 150.0
    # In its own frame the lever points along -y and the balance lies beyond it. THETA_E
    # turns that whole assembly about the escape wheel.
    ux, uy = math.cos(THETA_E), math.sin(THETA_E)
    lever = (escape[0] + E["pivot_dist"] * ux, escape[1] + E["pivot_dist"] * uy)
    reach = (P.PALLET_TAIL - 20.0) * s_pal + P.BALANCE_JEWEL_R * s_bal
    balance = (escape[0] + (E["pivot_dist"] + reach) * ux,
               escape[1] + (E["pivot_dist"] + reach) * uy)
    orient = THETA_E + math.pi / 2.0        # extra rotation for the lever and balance

    return {
        "m": m, "centre": centre, "third": third,
        "escape": escape, "barrel": barrel, "minute": minute,
        "lever": lever, "balance": balance, "orient": orient,
        "E": E, "s_pal": s_pal, "s_bal": s_bal, "r_tip": r_tip, "tooth_h": tooth_h,
        "mw_module_b": mw_module_b,
    }


def plate_radius(g):
    """How far the mechanism reaches FROM THE CENTRE WHEEL.

    Not a bounding box. The dial is concentric with the centre wheel because that is where
    the hands are, so the thing that has to fit the frame is a circle about the centre
    arbor — and fitting a bounding box instead leaves the dial hanging off one edge while
    the opposite corner sits empty, which is exactly what the first attempt did.
    """
    m, c = g["m"], g["centre"]
    discs = [(g["centre"], CENTRE / 2.0 * m + m), (g["third"], THIRD / 2.0 * m + m),
             (g["barrel"], BARREL / 2.0 * m + m),
             (g["escape"], g["r_tip"]), (g["balance"], R_BAL * m),
             (g["minute"], MINUTE_WHEEL / 2.0 * MW_MODULE_A * m)]
    return max(math.hypot(p[0] - c[0], p[1] - c[1]) + r for p, r in discs)


def ruby_bearings(g, at, lever_angle):
    """The drawn pallet stones as polygons, rotated to where the lever holds them."""
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
            key = round(sum(q[0] for q in pts), 1)
            if not any(abs(key - k) < 0.5 for k, _ in out):
                out.append((key, pts))
    ca, sa = math.cos(lever_angle), math.sin(lever_angle)
    return [[(at[0] + (x - at[0]) * ca - (y - at[1]) * sa,
              at[1] + (x - at[0]) * sa + (y - at[1]) * ca) for x, y in pts]
            for _, pts in out]


def tooth_polys(g, esc_at, phase):
    """The escape wheel's tooth polygons with the wheel at `phase`."""
    out, colour = [], None
    for c in P.escape_shapes(esc_at[0], esc_at[1], g["r_tip"] / 150.0,
                             teeth=ESC_TEETH, opaque=False, sense=SENSE):
        if "paint" in c:
            for op in c["paint"]["ops"]:
                if "color" in op:
                    colour = op["color"]
        elif "drawPath" in c and colour == P.LINE:
            pts = P._poly_pts(c["drawPath"]["path"])
            if 5 <= len(pts) <= 14:
                out.append(pts)
    ca, sa = math.cos(phase), math.sin(phase)
    return [[(esc_at[0] + (x - esc_at[0]) * ca - (y - esc_at[1]) * sa,
              esc_at[1] + (x - esc_at[0]) * sa + (y - esc_at[1]) * ca) for x, y in pts]
            for pts in out]


def wheel_phase(g, esc_at, lever_at):
    """Start the wheel so a tooth comes to rest ON the locking stone, not inside it."""
    pitch = 2.0 * math.pi / ESC_TEETH
    rest = SENSE * pitch / 2.0
    banks = [(ruby_bearings(g, lever_at, g["orient"] - P.PALLET_AMP), 0.0),
             (ruby_bearings(g, lever_at, g["orient"] + P.PALLET_AMP), rest)]
    ph, gap = P.solve_lock_phase(
        lambda a: tooth_polys(g, esc_at, a + rest), banks, pitch)
    if ph is None:
        raise SystemExit("no wheel phase locks without the teeth cutting into a stone")
    return ph


# ── the gear ratios, as multiples of the escape wheel's angle ────────────────
#
# Every one of these is the product of the tooth counts actually drawn, with a sign flip
# per mesh. They are not tuned: if a count changes, the hand speed changes with it.

R_ESCAPE = 1.0
R_THIRD = -float(ESC_PIN) / THIRD
R_CENTRE = R_THIRD / (-float(CENTRE) / THIRD_PIN)
R_BARREL = R_CENTRE / (-float(BARREL) / CENTRE_PIN)
R_MINUTE_W = R_CENTRE * (-float(CANNON) / MINUTE_WHEEL)
R_HOUR = R_MINUTE_W * (-float(MINUTE_PIN) / HOUR_WHEEL)


def arbor(ratio, phase=0.0):
    """A wheel's angle, written against the one escape-wheel variable."""
    if abs(ratio - 1.0) < 1e-12 and not phase:
        return "esc"
    return "%.9f + esc * %.9f" % (phase, ratio)


def escape_at_zero(phase):
    """What the escape-wheel expression evaluates to at t = 0.

    floor(0) is 0 and the easing ramp starts at 0, so the whole staircase contributes
    nothing and only the phase is left — but spelling that out here means the hands stay
    zeroed if the staircase ever changes shape.
    """
    return phase


def hand(cx, cy, length, back, width, taper=0.34):
    """A watch hand: a long tapering blade with a short counterpoise behind the arbor."""
    return P.poly([(cx - width * taper, cy + back),
                   (cx - width, cy - length * 0.62),
                   (cx, cy - length),
                   (cx + width, cy - length * 0.62),
                   (cx + width * taper, cy + back)])


def build():
    frame_r = min(W, H - CAPTION) / 2.0 * FILL_FRAC
    g = layout()
    g = layout(MODULE * frame_r / plate_radius(g))
    m = g["m"]
    dial_r = plate_radius(g)
    dx = W / 2.0 - g["centre"][0]
    dy = (H - CAPTION) / 2.0 - g["centre"][1]

    def at(p):
        return (p[0] + dx, p[1] + dy)

    C, T, Esc = at(g["centre"]), at(g["third"]), at(g["escape"])
    Bar, Min, Lev, Bal = at(g["barrel"]), at(g["minute"]), at(g["lever"]), at(g["balance"])
    mb = g["mw_module_b"]

    cmds = P.frame(W, H)
    cmds += P.time_var()

    # One variable for the whole movement. Every wheel below is a multiple of it, which
    # keeps each rotate short enough to read and makes the gearing literal.
    phase_esc = wheel_phase(g, Esc, Lev)
    cmds.append({"variable": {"name": "esc",
                              "value": P.escape_angle(ESC_TEETH, SENSE, phase_esc),
                              "commit": True}})

    # Tooth phases, each from the mesh before it.
    # Zero, not phase_esc: the driver's angle is written as the bare `esc`.
    # Zero for the first one, not phase_esc: the driver's angle is written as bare `esc`.
    ph_third = mesh_phase(math.atan2(T[1] - Esc[1], T[0] - Esc[0]),
                          ESC_PIN, THIRD, 0.0)
    ph_centre = mesh_phase(math.atan2(C[1] - T[1], C[0] - T[0]),
                           THIRD_PIN, CENTRE, ph_third)
    ph_barrel = mesh_phase(BETA_CB, CENTRE_PIN, BARREL, ph_centre)
    ph_minw = mesh_phase(BETA_CM, CANNON, MINUTE_WHEEL, ph_centre)
    # The hour wheel is driven by the minute PINION, so it takes its phase from that, not
    # from the minute wheel it happens to share an arbor with. Handing it the minute
    # wheel's phase — which looks harmless, they are the same part — drove it almost eight
    # pixels into the pinion.
    ph_hour = mesh_phase(BETA_CM + math.pi, MINUTE_PIN, HOUR_WHEEL, ph_minw)

    # ── layer 1: the barrel ──────────────────────────────────────────────────
    # Dimmest, because it is the bottom plane and the eye should walk past it.
    cmds += P.spin(arbor(R_BARREL, ph_barrel), Bar[0], Bar[1],
                   P.wheel_shapes(Bar[0], Bar[1], BARREL, m, arms=0,
                                  opaque=False, edge=P.LINE_DIM))
    cmds.append(P.stroke(P.LINE_DIM, 1.0))
    for r in (BARREL / 2.0 - 4.0, BARREL / 2.0 - 7.0):
        cmds.append({"drawPath": {"path": P.circle_path(Bar[0], Bar[1], r * m, 96)}})
    # The mainspring inside it, as a coil that does not move: a barrel is a closed drum
    # and what it contains is the one part of a watch you never see working.
    bar_angle = arbor(R_BARREL, ph_barrel)
    cmds += HAIR.spiral(Bar[0], Bar[1], 7.0 * m, (BARREL / 2.0 - 9.0) * m, 9,
                        math.radians(20.0), name="spring", drive=bar_angle,
                        rest=ph_barrel)
    cmds.append(P.stroke(P.wash(P.LINE_DIM, 0x2A), 0.9))
    cmds.append({"drawPath": {"path": "spring"}})

    # ── layer 2: the going train ─────────────────────────────────────────────
    for pos, teeth, pin, ratio, phase, arms in (
            (C, CENTRE, CENTRE_PIN, R_CENTRE, ph_centre, 4),
            (T, THIRD, THIRD_PIN, R_THIRD, ph_third, 4)):
        a = arbor(ratio, phase)
        cmds += P.spin(a, pos[0], pos[1],
                       P.wheel_shapes(pos[0], pos[1], teeth, m, arms=arms, opaque=False))
        # Drawn with the WHEEL profile, not the leaf-pinion one. A real pinion's leaves
        # are a different shape from a wheel's teeth and the two are cut to match each
        # other; the leaf profile in this corpus was drawn as a portrait of a pinion and
        # has never been verified against anything. Meshing it here puts the escape pinion
        # four and a half pixels into the fourth wheel.
        cmds += P.spin(a, pos[0], pos[1],
                       P.wheel_shapes(pos[0], pos[1], pin, m, arms=0, opaque=False))

    # ── layer 3: the escapement ──────────────────────────────────────────────
    cmds += P.spin("esc", Esc[0], Esc[1],
                   P.wheel_shapes(Esc[0], Esc[1], ESC_PIN, m, arms=0, opaque=False))
    cmds += P.spin("esc", Esc[0], Esc[1],
                   P.escape_shapes(Esc[0], Esc[1], g["r_tip"] / 150.0,
                                   teeth=ESC_TEETH, opaque=False, sense=SENSE))
    cmds += P.spin("%s + %.6f" % (P.pallet_angle(), g["orient"]), Lev[0], Lev[1],
                   P.pallet_shapes(Lev[0], Lev[1], g["s_pal"], spread=g["E"]["spread"],
                                   sense=SENSE, wheel_dist=g["E"]["pivot_dist"],
                                   tooth_h=g["tooth_h"]))
    cmds += P.spin("%s + %.6f" % (P.balance_angle(), g["orient"]), Bal[0], Bal[1],
                   P.balance_shapes(Bal[0], Bal[1], g["s_bal"], opaque=False))
    cmds += HAIR.spiral(Bal[0], Bal[1], 22.0 * g["s_bal"], 130.0 * g["s_bal"] - 4, 11,
                        g["orient"] + math.radians(68.0))
    cmds.append(P.stroke(P.LINE_DIM, 0.9))
    cmds.append({"drawPath": {"path": "hair"}})

    # ── layer 4: the motion work ─────────────────────────────────────────────
    # Gold, because it is the one part of the going side that exists only to drive the
    # hands: it takes no power from the train and keeps no time.
    cmds += P.spin(arbor(R_CENTRE, ph_centre), C[0], C[1],
                   P.wheel_shapes(C[0], C[1], CANNON, MW_MODULE_A * m, arms=0,
                                  opaque=False, edge=P.GOLD))
    cmds += P.spin(arbor(R_MINUTE_W, ph_minw), Min[0], Min[1],
                   P.wheel_shapes(Min[0], Min[1], MINUTE_WHEEL, MW_MODULE_A * m,
                                  arms=3, opaque=False, edge=P.GOLD))
    cmds += P.spin(arbor(R_MINUTE_W, ph_minw), Min[0], Min[1],
                   P.wheel_shapes(Min[0], Min[1], MINUTE_PIN, mb * m, arms=0,
                                  opaque=False, edge=P.GOLD))
    cmds += P.spin(arbor(R_HOUR, ph_hour), C[0], C[1],
                   P.wheel_shapes(C[0], C[1], HOUR_WHEEL, mb * m, arms=0,
                                  opaque=False, edge=P.GOLD))

    # ── layer 5: the dial ────────────────────────────────────────────────────
    #
    # The one layer that is not an X-ray. Everything under it is drawn to be looked
    # through; this is drawn to be read, so it keeps full brightness and sits on a thin
    # ground of its own wherever it crosses the mechanism.
    cmds.append(P.stroke(P.DIAL, 2.2))
    cmds.append({"drawPath": {"path": P.circle_path(C[0], C[1], dial_r, 180)}})
    cmds.append(P.stroke(P.DIAL_DIM, 1.0))
    cmds.append({"drawPath": {"path": P.circle_path(C[0], C[1], dial_r - 15, 180)}})
    for i in range(60):
        a = -math.pi / 2 + 2 * math.pi * i / 60.0
        five = (i % 5 == 0)
        r1 = dial_r - (15 if five else 7)
        cmds.append(P.stroke(P.DIAL if five else P.DIAL_DIM, 3.0 if five else 1.1))
        cmds.append({"drawPath": {"path": P.poly(
            [(C[0] + r1 * math.cos(a), C[1] + r1 * math.sin(a)),
             (C[0] + dial_r * math.cos(a), C[1] + dial_r * math.sin(a))], close=False)}})

    # Numerals: large, and on a disc of the ground colour so a gear tooth never runs
    # through a digit. A number you have to disentangle from a wheel is not legible.
    num_r = dial_r - 42
    cmds.append(P.fill(P.HALO))
    for i in range(12):
        a = -math.pi / 2 + 2 * math.pi * i / 12.0
        cmds.append({"drawPath": {"path": P.circle_path(
            C[0] + num_r * math.cos(a), C[1] + num_r * math.sin(a), 17.0, 24)}})
    cmds.append({"paint": {"ops": [{"color": P.DIAL}, {"style": "fill"},
                                   {"textSize": 30.0}]}})
    for i in range(12):
        a = -math.pi / 2 + 2 * math.pi * i / 12.0
        cmds.append({"drawTextAnchored": {
            "text": str(12 if i == 0 else i), "x": C[0] + num_r * math.cos(a),
            "y": C[1] + num_r * math.sin(a), "panX": 0.0, "panY": 0.0, "flags": 0}})

    # The small seconds, on the escape wheel, which is where it actually is.
    sub_r = g["r_tip"] * 0.80
    # On its own thin ground, like the numerals: the escape wheel's twenty teeth sweep
    # right through this ring and a dim marker is simply lost among them.
    cmds.append(P.stroke(P.HALO, 5.0))
    cmds.append({"drawPath": {"path": P.circle_path(Esc[0], Esc[1], sub_r, 96)}})
    cmds.append(P.stroke(P.DIAL, 1.8))
    cmds.append({"drawPath": {"path": P.circle_path(Esc[0], Esc[1], sub_r, 96)}})
    for i in range(12):
        a = 2 * math.pi * i / 12.0
        five = (i % 3 == 0)
        cmds.append(P.stroke(P.HALO, (3.4 if five else 2.4) + 2.5))
        cmds.append({"drawPath": {"path": P.poly(
            [(Esc[0] + (sub_r - (9 if five else 5)) * math.cos(a),
              Esc[1] + (sub_r - (9 if five else 5)) * math.sin(a)),
             (Esc[0] + sub_r * math.cos(a), Esc[1] + sub_r * math.sin(a))], close=False)}})
        cmds.append(P.stroke(P.DIAL if five else P.DIAL_DIM, 3.4 if five else 2.4))
        cmds.append({"drawPath": {"path": P.poly(
            [(Esc[0] + (sub_r - (9 if five else 5)) * math.cos(a),
              Esc[1] + (sub_r - (9 if five else 5)) * math.sin(a)),
             (Esc[0] + sub_r * math.cos(a), Esc[1] + sub_r * math.sin(a))], close=False)}})

    # The hands. A hand is a separate part pressed onto its arbor, and which way it points
    # relative to that wheel's TEETH is set when it is fitted — so it must not inherit the
    # wheel's meshing phase. Inherit it and every hand starts at a different random angle,
    # which is what the first build did. Instead each one is zeroed so that at t = 0 it
    # points at twelve, exactly like setting a watch before you wear it.
    #
    # Each is laid down three times: a wide stroke of the ground to cut it out of whatever
    # is behind, a solid fill, then its own edge. Over a drawing this busy a thin outline
    # alone disappears into the wheels.
    esc0 = escape_at_zero(phase_esc)
    for pos, ratio, length, back, wdt, col in (
            (C, R_HOUR, dial_r * 0.58, 20, 9.0, P.HAND),
            (C, R_CENTRE, dial_r - 46, 22, 6.0, P.HAND),
            (Esc, R_ESCAPE, sub_r - 3, 12, 2.6, P.HAND_SECONDS)):
        d = hand(pos[0], pos[1], length, back, wdt)
        cmds += P.spin(arbor(ratio, -esc0 * ratio), pos[0], pos[1],
                       [P.stroke(P.HALO, 6.0), {"drawPath": {"path": d}},
                        P.fill(P.wash(col, 0xC0)), {"drawPath": {"path": d}},
                        P.stroke(col, 1.6), {"drawPath": {"path": d}}])
    cmds.append(P.fill(P.BG))
    cmds.append({"drawPath": {"path": P.circle_path(C[0], C[1], 8.0, 24)}})
    cmds.append(P.stroke(P.HAND, 2.0))
    cmds.append({"drawPath": {"path": P.circle_path(C[0], C[1], 8.0, 24)}})

    return cmds, g, (C, T, Esc, Bar, Min, Lev, Bal)


def main():
    cmds, g, pos = build()
    doc = P.document(W, H, cmds,
                     "A complete mechanical watch movement drawn as an X-ray, built "
                     "outwards from its escapement: the mainspring barrel, the going "
                     "train of centre, third and fourth wheels, the lever escapement "
                     "with its balance and hairspring, the motion work that divides the "
                     "hours from the minutes, and a dial with three hands. Every wheel "
                     "turns at the ratio of the teeth drawn on it.")
    out = HERE / "out" / "skeleton_watch.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n")
    names = ("centre", "third", "escape", "barrel", "minute wheel", "lever", "balance")
    print("wrote", out)
    for n, p in zip(names, pos):
        print("  %-13s (%6.1f, %6.1f)" % (n, p[0], p[1]))
    esc_rpm = SENSE * P.FREQ * 60.0 / ESC_TEETH
    for n, r in (("escape/seconds", R_ESCAPE),
                 ("third", R_THIRD), ("centre/minutes", R_CENTRE),
                 ("barrel", R_BARREL), ("hour", R_HOUR)):
        rpm = esc_rpm * r
        print("  %-15s %+10.5f rev/min  = one turn in %s"
              % (n, rpm, "%.4g min" % (1.0 / abs(rpm)) if rpm else "never"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
