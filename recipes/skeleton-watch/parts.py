#!/usr/bin/env python3
"""Shared geometry and motion for the watch parts.

Every part is a separate document so it can be worked on alone, but they must agree about
two things or the assembly is nonsense: the shapes have to be drawn to one scale, and the
escapement's three moving pieces have to share one phase. Both live here.

THE MOTION. A mechanical watch beats at a fixed rate — 4 Hz for a 28,800 vph movement, so
the balance completes four full oscillations a second and the escapement is unlocked eight
times a second, once per half-swing. Everything below is written against

    beat = 2 * FREQ * t

so `floor(beat)` counts impulses and `fract(beat)` is the position within one. The three
parts then differ in character, and that difference is the escapement:

    balance   smooth.      A * sin(2*pi*FREQ*t)      a harmonic oscillator, nothing else
    pallet    snaps.       clamped steep sine        locked at a banking pin, flicks over
    escape    staircase.   floor(beat) + a ramp      locked, one tooth, locked

A naive model gives all three a sine and the result looks like a toy. The watch is
interesting precisely because the escape wheel does NOT move most of the time: it sits
locked against a pallet jewel while the balance swings out and comes back, and advances
only during the few milliseconds the lever is unlocked.

X-RAY. Parts are drawn as thin bright strokes with very low alpha fills, so that where two
sit over one another the overlap reads brighter — which is what makes a stack of flat
drawings look like a radiograph rather than a pile of stickers.
"""

import math

# ── the beat ─────────────────────────────────────────────────────────────────

# ── one clock for everything ─────────────────────────────────────────────────
#
# Every motion in every one of these documents is an expression in `t`, and `t` is defined
# in exactly one place: here. That is what keeps the movement geared — the balance, the
# lever, the wheel, the train and the hands all come off one number, because nothing
# anywhere reads a clock for itself.
#
# AND THAT ONE NUMBER IS THE REAL CLOCK. `continuousSec()` is not elapsed time, which is
# the easy thing to assume and what this assumed for a long while. The player computes it
# as `minute*60 + second + millis/1000` — the second within the HOUR, accurate to the
# millisecond and wrapping hourly. So a movement driven by it is already showing the true
# seconds and the true minutes; nothing has to be set.
#
# Only the hour hand needs more, because it has to survive the wrap. `timeInHr()` is the
# hour, 0..23, so a modulo twelve and an hour's worth of seconds extends the clock to the
# twelve hours a dial covers:
#
#     t = 3600 * (timeInHr() mod 12) + continuousSec()
#
# which runs 0 .. 43200 and is exactly the dial's own span. Every hand is then a plain
# gear ratio off it and no hand needs an offset of its own.
#
# The other time variables are worth knowing about and worth avoiding here. `timeInSec()`
# is the same as continuousSec() but whole seconds — no good for a balance, which needs
# the milliseconds to swing smoothly — and `timeInMin()` is the minute within the DAY.
# ISSUES B1l records timeInHr() and timeInMin() disagreeing under a pinned clock in the
# C++ player, so this uses timeInHr() and continuousSec() only, and they meet exactly at
# the hour boundary.


def time_var(scale=1.0):
    """The one variable the whole movement is a function of: the real time of day.

    `scale` is a speed knob for studying the escapement — 1 is the truth. Anything else
    and the hands stop telling the time, which is why it is not a module constant any
    more: it has to be asked for.
    """
    hours12 = "timeInHr() - 12 * floor(timeInHr() / 12)"
    value = "3600 * (%s) + continuousSec()" % hours12
    if scale != 1.0:
        value = "(%s) * %g" % (value, scale)
    return [{"variable": {"name": "t", "value": value, "commit": True}}]


def speed_note(scale=1.0):
    """How to say the speed in a caption, or nothing when it is telling the truth."""
    return "" if scale == 1.0 else " · shown at %gx speed" % scale


# Half a hertz: the balance takes two seconds to swing out and back, and the escapement
# unlocks once a second. A seconds-beating movement, the rate a longcase regulator keeps,
# and slow enough to watch the lock and the release happen.
#
# It also makes the train collapse to something very clean. The seconds hand must advance
# one mark per tick, which is 1/60 of a turn, and the escape wheel advances half a pitch
# per tick, which is 1/(2N). Those are equal at N = 30 — so a thirty-tooth escape wheel
# turns once a minute and carries the seconds hand DIRECTLY, with no fourth wheel at all.
# That is not a shortcut; it is what a one-second tick always reduces to, and it is how a
# seconds-beating regulator is built.
FREQ = 0.5                 # balance oscillations per second: one tick a second
BALANCE_AMP = 2.60         # radians of swing each way, about 150 degrees
PALLET_AMP = 0.175         # radians between the banking pins, about 10 degrees

ESCAPE_TEETH = 30
ESCAPE_PITCH = 2.0 * math.pi / ESCAPE_TEETH

# How far apart the two pallet jewels sit, measured in tooth pitches. THE HALF IS THE
# WHOLE POINT. Put the jewels a whole number of pitches apart and both of them face a
# tooth at the same moment, so the wheel is blocked twice over and can never advance.
# At (n + 1/2), one jewel faces a tooth while the other faces the gap between two, which
# is what lets a ruby slip past the wheel while its partner holds it.
PALLET_SPAN_PITCHES = 2.5
# The fraction of a beat the escape wheel is actually moving. NOT a free dial: in a real
# escapement the wheel's own tooth drives the lever across, so the run and the crossing are
# the same event. Here they come from two independent expressions and have to be aligned by
# hand, and the wheel must finish as the lever reaches its banking pin. Leave it longer —
# it was 0.16 against a lever that crosses in 0.071 — and for most of the beat the stone is
# already sitting in the path with the tooth still coming, which draws as a tooth passing
# clean through a jewel. See escape_angle; the bound is asin(1/9)/(pi*FREQ) / beat.
UNLOCK = 0.055

BEAT = "(%.4f * t)" % (2.0 * FREQ)


def balance_angle():
    """Smooth harmonic swing. The balance is the only part here that is a plain sine."""
    return "%.4f * sin(%.6f * t)" % (BALANCE_AMP, 2.0 * math.pi * FREQ)


def balance_rest():
    """Where the balance sits at the centre of its swing: the position everything is
    measured from. The hairspring is at its free length here and nowhere else."""
    return 0.0


def pallet_angle():
    """Locked at one banking pin, then over to the other.

    A steep sine clamped to +/-1: flat for most of the beat, which is the lever resting
    against a banking pin, with a fast crossing as the balance's impulse jewel drives it
    through. Multiplying the sine by a large factor before clamping is what turns a smooth
    curve into something that reads as a mechanism snapping over.

    NOTE THE MINUS SIGN. It is the whole difference between the jewel pushing the lever and
    the two of them arriving head-on, and the reason it is not obvious is that the two
    parts hang off their pivots in opposite senses. The impulse jewel is BELOW the balance
    staff, so turning the balance anticlockwise sweeps the jewel to the right. The fork
    notch is ABOVE the lever pivot, so turning the lever anticlockwise sweeps the notch to
    the left. Drive both from the same `+sin(wt)` — which looks obviously correct, and is
    what this did at first — and the jewel and the notch move towards each other. The
    lever leads the jewel that is supposed to be pushing it.

    So the lever runs off the balance NEGATED. Nothing else about the escapement changes:
    it still flips at the same instants, the escape wheel still unlocks on the same beats,
    and the jewels still lock at the same depth. Only the direction the lever is thrown.
    """
    steep = "%.4f * sin(%.6f * t)" % (-9.0, 2.0 * math.pi * FREQ)
    return "%.5f * max(-1, min(1, %s))" % (PALLET_AMP, steep)


def escape_angle(teeth=ESCAPE_TEETH, sense=1, phase=0.0):
    """HALF a tooth per beat: locked, a quick advance, locked again.

    Half, not one, and getting that wrong is easy because "one tooth per beat" sounds
    exactly like what an escapement does. It is not. The pallets are (n + 1/2) pitches
    apart, so when one releases, the wheel only has to turn far enough for the next tooth
    to reach the OTHER pallet -- half a pitch. A whole tooth goes by per full oscillation
    of the balance, which is two beats. At four hertz that is four teeth a second, and
    stepping a whole pitch per beat ran the wheel at exactly double speed, which would
    have put every hand on the dial out by a factor of two.

    `floor(beat)` is how many half-teeth have gone by and `fract(beat)` is the position
    within the current one. The advance happens over the first UNLOCK of the beat and the
    wheel is stationary for the rest, which is the behaviour that makes an escapement read
    as an escapement. The ramp is cosine-eased so the wheel does not start and stop
    infinitely fast.

    `sense` runs the wheel the other way. `phase` lands a tooth exactly on the locking
    jewel instead of wherever the tooth numbering happened to start.
    """
    step = sense * math.pi / teeth           # half a pitch
    u = "max(0, min(1, fract(%s) / %.4f))" % (BEAT, UNLOCK)
    body = "%.8f * (floor(%s) + 0.5 - 0.5 * cos(3.14159265 * %s))" % (step, BEAT, u)
    return body if not phase else "%.6f + %s" % (phase, body)


# ── geometry helpers ─────────────────────────────────────────────────────────

def poly(points, close=True):
    """A point list as an SVG path."""
    if not points:
        return ""
    d = "M %.3f %.3f" % (points[0][0], points[0][1])
    for x, y in points[1:]:
        d += " L %.3f %.3f" % (x, y)
    return d + (" Z" if close else "")


def circle_path(cx, cy, r, count=64):
    return poly([(cx + r * math.cos(2 * math.pi * k / count),
                  cy + r * math.sin(2 * math.pi * k / count)) for k in range(count)])


# The smallest pinion this tooth profile can actually mesh. Measured, not assumed: swept
# against a 72-tooth wheel over a full pitch, seven leaves cut 0.13 of a module into the
# wheel and six cut 0.23, while eight clears by 0.03 and ten by 0.22. The profile is a
# raised cosine rather than a true involute, so it has no undercut to give it room, and
# below eight leaves there is no phase that saves it. Real watch pinions stop at six
# because they ARE cut with the relief this one does not have.
# Ten, with nine as the true threshold. Swept against wheels from 60 to 120 teeth at the
# best phase available: ten leaves clear by 0.22 of a module and nine by 0.19, but eight
# sits on the knife edge — +0.05 in one geometry and -0.002 in another — and seven cuts in
# properly. Real watch pinions go down to six because they are cut with a relief this
# raised-cosine profile has not got.
MIN_PINION = 10


def tooth_wheel(cx, cy, teeth, module, add=0.95, ded=1.20, ht=0.13, hr=0.29,
                samples=16):
    """A going-train wheel rim, using the tooth profile tuned for the gear documents.

    Slender tips and wide spaces, which is what a watch wheel actually looks like and is
    also what meshes without interference.
    """
    rp = module * teeth / 2.0
    rroot = rp - ded * module
    height = (add + ded) * module
    pts = []
    n = teeth * samples
    for k in range(n):
        a = 2 * math.pi * k / n
        u = (teeth * a / (2 * math.pi)) % 1.0
        s = max(0.0, min(1.0, (hr - abs(u - 0.5)) / (hr - ht)))
        r = rroot + height * (0.5 - 0.5 * math.cos(math.pi * s))
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return poly(pts)


def leaf_pinion(cx, cy, leaves, module, samples=18):
    """A pinion. Fewer, fatter leaves than a wheel's teeth, and a deeper space.

    Pinion leaves are not small wheel teeth: with eight or ten of them the flanks are
    nearly radial and the tips are well rounded, which is why this uses its own profile
    rather than the wheel's with a small count.
    """
    rp = module * leaves / 2.0
    rroot = rp - 1.35 * module
    height = 2.25 * module
    pts = []
    n = leaves * samples
    for k in range(n):
        a = 2 * math.pi * k / n
        u = (leaves * a / (2 * math.pi)) % 1.0
        s = max(0.0, min(1.0, (0.33 - abs(u - 0.5)) / 0.21))
        r = rroot + height * (0.5 - 0.5 * math.cos(math.pi * s))
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return poly(pts)


def crossings(cx, cy, arms, r_hub, r_rim, arm_half, taper=0.55):
    if arms <= 0:
        return []
    """The cut-outs between a wheel's spokes, as one path per opening.

    A watch wheel is not a disc: it is a rim carried on four or five narrow arms, and the
    openings between them are most of its area. Drawing the openings rather than the arms
    keeps the rim and hub as single closed shapes, which is what the X-ray stack wants —
    an outline it can stroke.
    """
    out = []
    half = math.pi / arms
    for k in range(arms):
        mid = 2 * math.pi * k / arms + half
        # Angular half-width of the opening, narrower at the hub where the arms converge.
        wide_out = half - math.asin(min(0.99, arm_half / max(r_rim, 1e-6)))
        wide_in = half - math.asin(min(0.99, arm_half / max(r_hub * taper + arm_half, 1e-6)))
        pts = []
        steps = 14
        for i in range(steps + 1):
            a = mid - wide_out + 2 * wide_out * i / steps
            pts.append((cx + r_rim * math.cos(a), cy + r_rim * math.sin(a)))
        for i in range(steps + 1):
            a = mid + wide_in - 2 * wide_in * i / steps
            pts.append((cx + r_hub * math.cos(a), cy + r_hub * math.sin(a)))
        out.append(poly(pts))
    return out


# ── the X-ray look ───────────────────────────────────────────────────────────

# ── the palette ──────────────────────────────────────────────────────────────
#
# Every colour is derived, not written out, so that the whole drawing can be taken up or
# down in one place. `wash` makes the low-alpha version of an ink, which is what gives the
# X-ray its character: where two parts overlap, two washes add and the overlap reads
# brighter than either part alone.
#
# Nothing downstream should spell a colour as a hex literal. The checkers find the pallet
# stones by their colour, and a literal "#FFE0453C" in a checker stops matching the moment
# the palette moves — so they read JEWEL from here instead.

BRIGHT = 0.80               # the whole drawing's level; 1.0 is the original


def shade(colour, f=None):
    """An ARGB string with its RGB scaled, alpha untouched."""
    f = BRIGHT if f is None else f
    a, r, g, b = (colour[1:3], int(colour[3:5], 16), int(colour[5:7], 16),
                  int(colour[7:9], 16))
    return "#%s%02X%02X%02X" % (a, min(255, int(r * f)), min(255, int(g * f)),
                                min(255, int(b * f)))


def wash(colour, alpha=0x30):
    """The same ink at low alpha, for the fills that make overlaps glow."""
    return "#%02X%s" % (alpha, colour[3:])


BG = "#FF070B12"            # the ground: left alone, dimming it only adds contrast
LINE = shade("#FF86D8FF")   # the bright edge
LINE_DIM = shade("#FF3F7FA8")
FILL = shade("#141F6FA8")   # barely-there wash, so overlaps brighten
JEWEL = shade("#FFE0453C")
GOLD = shade("#FFE8B45A")
# ── the reading layer ────────────────────────────────────────────────────────
#
# The dial and the hands are NOT dimmed with the rest. A watch is a thing you read, and
# everything behind it — the barrel, the train, the escapement — is there to be looked
# through, not at. Taking the mechanism down a notch and leaving the dial where it is puts
# the contrast exactly where the eye needs it; dimming all of it together just makes a
# darker picture that is no easier to read.
HAND = "#FFFFFFFF"              # hour and minute: white, the only pure thing on the dial
HAND_SECONDS = "#FF49E89A"      # the seconds hand, green, because it is the one that
                                # moves and the eye should go straight to it
DIAL = "#FFEAF2FA"              # the ring, the hour markers and the numerals
DIAL_DIM = "#FF8FA6B8"          # the minute ticks between them
HALO = "#D0070B12"              # the ground, laid under a hand so its edge reads over
                                # whatever wheel happens to be behind it


def stroke(colour=LINE, width=1.2):
    return {"paint": {"ops": [{"color": colour}, {"style": "stroke"}, {"width": width}]}}


def fill(colour=FILL):
    return {"paint": {"ops": [{"color": colour}, {"style": "fill"}]}}


def frame(w, h, title=None, subtitle=None):
    """Background and, for a part shown on its own, a caption naming it."""
    cmds = [fill(BG), {"drawRect": {"left": 0, "top": 0, "right": w, "bottom": h}}]
    if title:
        cmds += [
            {"paint": {"ops": [{"color": LINE}, {"style": "fill"}, {"textSize": 15.0}]}},
            {"drawTextAnchored": {"text": title, "x": 14, "y": h - 30,
                                  "panX": -1.0, "panY": 0.0, "flags": 0}},
        ]
    if subtitle:
        cmds += [
            {"paint": {"ops": [{"color": LINE_DIM}, {"style": "fill"},
                               {"textSize": 11.5}]}},
            {"drawTextAnchored": {"text": subtitle, "x": 14, "y": h - 13,
                                  "panX": -1.0, "panY": 0.0, "flags": 0}},
        ]
    return cmds


def document(w, h, cmds, description):
    return {
        "header": {"width": w, "height": h, "apiLevel": 7, "profiles": 512,
                   "contentDescription": description},
        "root": [{"box": {"modifiers": ["fillMaxSize"], "children":
            [{"type": "canvas", "modifiers": ["fillMaxSize"], "commands": cmds}]}}],
    }


def spin(angle_expr, cx, cy, body):
    """Rotate a static shape about a point by an expression in t."""
    return ([{"save": {}},
             {"rotate": {"angle": "(%s) * 57.29577951" % angle_expr,
                         "pivotX": cx, "pivotY": cy}}]
            + body + [{"restore": {}}])


# ── the parts themselves ─────────────────────────────────────────────────────
#
# Each returns the drawing commands for one part at a given centre and scale, WITHOUT the
# rotation — the caller wraps it in `spin` with the right motion. They live here rather
# than in the individual generators so that the standalone documents and the assembly draw
# the same shapes from the same code. A part that looks different on its own than it does
# in the watch is a part nobody can work on.


def escape_shapes(cx, cy, s=1.0, teeth=ESCAPE_TEETH, opaque=True, sense=1):
    """The escape wheel. See `wheel_shapes` for what `opaque` means and why."""
    r_tip, r_rim, r_rim_in, r_hub = 150.0 * s, 118.0 * s, 100.0 * s, 26.0 * s
    pitch = 2 * math.pi / teeth
    out = []

    def ring(r, n=96):
        return circle_path(cx, cy, r, n)

    if opaque:
        out += [fill(), {"drawPath": {"path": ring(r_rim)}}]
    out += [stroke(LINE, 1.3 * s), {"drawPath": {"path": ring(r_rim)}},
            {"drawPath": {"path": ring(r_rim_in)}}]
    cuts = crossings(cx, cy, 4, r_hub + 4 * s, r_rim_in, 7.0 * s)
    out.append(fill(BG) if opaque else fill())
    out += [{"drawPath": {"path": d}} for d in cuts]
    out.append(stroke(LINE_DIM, 1.0))
    out += [{"drawPath": {"path": d}} for d in cuts]

    for i in range(teeth):
        a = pitch * i

        def pt(r, f):
            # `sense` mirrors the tooth about its own radius. A club tooth is asymmetric —
            # a short locking face and a long impulse plane — and which way it leans has
            # to follow which way the wheel runs, or the wheel is trying to escape over
            # the backs of its own teeth.
            ang = a + sense * f * pitch
            return (cx + r * math.cos(ang), cy + r * math.sin(ang))

        d = poly([pt(r_rim, -0.30), pt(r_rim + 6 * s, -0.26), pt(r_tip - 20 * s, -0.085),
                  pt(r_tip - 9 * s, -0.055), pt(r_tip, -0.025), pt(r_tip, 0.085),
                  pt(r_tip - 13 * s, 0.125), pt(r_rim + 3 * s, 0.175), pt(r_rim, 0.21)])
        out += [fill(), {"drawPath": {"path": d}},
                stroke(LINE, 1.2 * s), {"drawPath": {"path": d}}]

    out += [fill(), {"drawPath": {"path": ring(r_hub, 48)}},
            stroke(LINE, 1.3 * s), {"drawPath": {"path": ring(r_hub, 48)}},
            stroke(LINE_DIM, 1.0), {"drawPath": {"path": ring(9.0 * s, 32)}}]
    return out


# Derived, not chosen: half the span, in radians. It used to be a round 31 degrees, which
# is 2.583 pitches on a fifteen-tooth wheel -- close enough to look right and wrong enough
# that the jewels never cleanly straddled a gap.
# gamma: half the angle the two locking points subtend AT THE WHEEL CENTRE. This is the
# vertex the (n + 1/2) rule is about, and applying it at the lever pivot instead -- which
# is the easy mistake, because that is where the pallets visibly fork -- puts the jewels
# 2.583 pitches apart and they never cleanly straddle anything.
PALLET_GAMMA = PALLET_SPAN_PITCHES * ESCAPE_PITCH / 2.0

# Half-span at the LEVER, which is a consequence rather than a choice. See
# escapement_layout for where it comes from; with the arm equal to the locking radius it
# is just the banking angle plus gamma.
PALLET_SPREAD = PALLET_AMP + PALLET_GAMMA
PALLET_ARM, PALLET_TAIL, PALLET_W = 86.0, 118.0, 11.0


def solve_lock_phase(teeth_at, banks, pitch, steps=720):
    """Find the wheel phase that lands a tooth AGAINST the locking stone.

    The analytic phase puts a tooth tip at the stone's own bearing, which is right only if
    the stone is a point. It is not: it is a rectangle a tooth-and-a-bit long, so a tip
    aimed at its centre arrives in the middle of it and the drawing shows steel through
    steel. What is wanted is the tooth's locking face resting on the stone's, which is a
    condition on two polygons rather than on two bearings.

    So this scans a whole pitch and keeps the phase that leaves no interpenetration at
    either banking position while bringing the tooth as close to the holding stone as it
    can get. Both banking positions are tested, because a phase that locks beautifully on
    one beat and buries a tooth on the next is no good.

    `teeth_at(angle)` returns the wheel's tooth polygons with the wheel at that angle.
    `banks` is a list of (stone polygons, wheel offset) — one entry per banking position,
    because the wheel is HALF A PITCH further on at the second one. Testing both banks
    against the same wheel position asks for a phase that satisfies two constraints half a
    pitch apart, which no phase can, and the search comes back empty.
    """
    best = None
    for k in range(steps):
        ph = (k / float(steps)) * pitch
        bad = False
        gap = 1e9
        for stones, extra in banks:
            teeth = teeth_at(ph + extra)
            for stone in stones:
                near = 1e9
                for tooth in teeth:
                    if polys_overlap(stone, tooth):
                        bad = True
                        break
                    near = min(near, polys_gap(stone, tooth))
                if bad:
                    break
                gap = min(gap, near)
            if bad:
                break
        if not bad and (best is None or gap < best[0]):
            best = (gap, ph)
    if best is None:
        return None, None
    return best[1], best[0]


def _poly_pts(d):
    return [tuple(float(v) for v in seg.split()[-2:])
            for seg in d.replace("Z", "").split("L")]


def _inside(p, poly):
    x, y = p
    c = False
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        if ((y0 > y) != (y1 > y)) and (x < (x1 - x0) * (y - y0) / (y1 - y0 + 1e-12) + x0):
            c = not c
    return c


def _cross(a, b, c, d):
    def o(p, q, r):
        return (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
    return ((o(a, b, c) > 0) != (o(a, b, d) > 0)
            and (o(c, d, a) > 0) != (o(c, d, b) > 0))


def _shrunk(poly, eps):
    """The polygon pulled in towards its own centroid by eps."""
    if eps <= 0:
        return poly
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    out = []
    for x, y in poly:
        d = math.hypot(x - cx, y - cy) or 1.0
        f = max(0.0, (d - eps) / d)
        out.append((cx + (x - cx) * f, cy + (y - cy) * f))
    return out


def polys_overlap(A, B, eps=0.35):
    """Do two polygons genuinely cross?

    Touching is not crossing. A tooth resting ON a pallet stone shares a boundary with it,
    and the whole point of the escapement is that it does — so both shapes are pulled in
    by `eps` first, and only a real interpenetration survives.
    """
    A, B = _shrunk(A, eps), _shrunk(B, eps)
    if any(_inside(p, B) for p in A) or any(_inside(p, A) for p in B):
        return True
    for i in range(len(A)):
        for j in range(len(B)):
            if _cross(A[i], A[(i + 1) % len(A)], B[j], B[(j + 1) % len(B)]):
                return True
    return False


def polys_gap(A, B):
    return min(math.hypot(p[0] - q[0], p[1] - q[1]) for p in A for q in B)


def escapement_layout(r_tip, tooth_h, lock_frac=0.25):
    """Solve the escapement from the wheel outwards. Everything else is a consequence.

    Two conditions fix it, and only the second is easy to get wrong:

        r(S - B) = r_lock           the engaged jewel bites the tooth at the right depth
        2 * gamma = 2.5 * pitch     the two LOCKING POINTS, measured at the wheel centre,
                                    sit two and a half pitches apart

    A jewel's distance from the wheel centre is `sqrt(A^2 + D^2 - 2 A D cos(phi))` -- the
    law of cosines on the triangle wheel-centre / pivot / jewel -- so it depends only on
    the jewel's half-angle. Rocking the lever raises phi for one jewel and lowers it for
    the other, which sends one out of the wheel as the other drops in. That swap IS the
    escaping action.

    Imposing the first condition on the second collapses to

        A sin(S - B) = r_lock sin(gamma)        D = A cos(S - B) + r_lock cos(gamma)

    and taking the arm equal to the locking radius -- close to the real proportion -- makes
    it exact: S = B + gamma, D = 2 r_lock cos(gamma).

    The half pitch is what lets a ruby slip past. Two and a half pitches apart means that
    when one jewel is facing a tooth, the other is facing the middle of a gap, so the
    wheel is held once and only once. A whole number of pitches would have both jewels
    meet a tooth together and the wheel could never turn at all.
    """
    r_lock = r_tip - lock_frac * tooth_h
    gamma = PALLET_GAMMA
    arm = r_lock
    spread = PALLET_AMP + gamma
    pivot = 2.0 * r_lock * math.cos(gamma)
    return {
        "r_lock": r_lock, "gamma": gamma, "arm": arm, "spread": spread,
        "pivot_dist": pivot,
        # Where the two locks happen, as bearings from the wheel centre. Straight up from
        # the wheel is -pi/2; the locks sit gamma either side of it.
        "lock_bearings": (gamma - math.pi / 2.0, -gamma - math.pi / 2.0),
        # Scale to draw the pallet at so its arm comes out this long.
        "pallet_scale": arm / PALLET_ARM,
    }


def pallet_shapes(cx, cy, s=1.0, spread=None, sense=1, wheel_dist=None,
                  tooth_h=None):
    spread = PALLET_SPREAD if spread is None else spread
    arm, tail, w = PALLET_ARM * s, PALLET_TAIL * s, PALLET_W * s
    out = []
    for sign in (-1, 1):
        a = math.pi / 2 + sign * spread
        dx, dy = math.cos(a), math.sin(a)
        nx, ny = -dy, dx
        root, tip, hw, tw = 10.0 * s, arm + 13.0 * s, 12.0 * s, 14.0 * s
        d = poly([(cx + dx * root + nx * hw, cy + dy * root + ny * hw),
                  (cx + dx * tip + nx * tw, cy + dy * tip + ny * tw),
                  (cx + dx * tip - nx * tw, cy + dy * tip - ny * tw),
                  (cx + dx * root - nx * hw, cy + dy * root - ny * hw)])
        out += [fill(), {"drawPath": {"path": d}},
                stroke(LINE, 1.3), {"drawPath": {"path": d}}]
    d = poly([(cx - w * 1.15, cy + 6 * s), (cx + w * 1.15, cy + 6 * s),
              (cx + w * 0.80, cy - tail + 34 * s), (cx + w * 2.05, cy - tail),
              (cx + w * 1.15, cy - tail + 6 * s), (cx + w * 0.46, cy - tail + 20 * s),
              (cx - w * 0.46, cy - tail + 20 * s), (cx - w * 1.15, cy - tail + 6 * s),
              (cx - w * 2.05, cy - tail), (cx - w * 0.80, cy - tail + 34 * s)])
    out += [fill(), {"drawPath": {"path": d}},
            stroke(LINE, 1.3), {"drawPath": {"path": d}}]
    # ── the pallet stones ────────────────────────────────────────────────────
    #
    # PLACED BY THEIR LOCKING FACE, not by their centre, and this is the whole difference
    # between a tooth resting on a jewel and a tooth passing through one.
    #
    # Centre a stone on the locking radius and it reaches half its length inside the tooth
    # circle. Here the stone was 34 units long against a tooth 21 deep, so it spanned the
    # entire tooth band and then some: at every banking position TWO teeth ran clean
    # through the engaged jewel. On a real lever the stone sits almost entirely outside the
    # path of the teeth and only its locking corner dips in, by a fraction of the tooth.
    #
    # So the design point is the inner face. `wheel_dist` says where the escape wheel's
    # centre is along the lever's own axis, which gives the radial direction to build out
    # along; the stone then extends AWAY from the wheel from there. The contact point keeps
    # the bearing the escapement was solved for, because moving a stone radially does not
    # change its bearing at all.
    if wheel_dist:
        th = tooth_h if tooth_h else 0.22 * wheel_dist
        for sign in (-1, 1):
            a = math.pi / 2 + sign * spread
            c = (cx + arm * math.cos(a), cy + arm * math.sin(a))
            wx, wy = cx, cy + wheel_dist                       # the wheel's centre
            ux, uy = c[0] - wx, c[1] - wy
            n = math.hypot(ux, uy) or 1.0
            ux, uy = ux / n, uy / n                            # radially outward
            px, py = -uy, ux                                   # tangential
            eff = sign * sense
            lean = math.radians(sense * (-13.0 if eff < 0 else 13.0))
            cl, sl = math.cos(lean), math.sin(lean)
            hw, hh = 0.40 * th, 0.62 * th
            j = poly([(c[0] + dx * (px * cl - ux * sl) + dy * (ux * cl + px * sl),
                       c[1] + dx * (py * cl - uy * sl) + dy * (uy * cl + py * sl))
                      for dx, dy in ((-hw, 0.0), (hw, 0.0), (hw, 2 * hh), (-hw, 2 * hh))])
            out += [fill(wash(JEWEL)), {"drawPath": {"path": j}},
                    stroke(JEWEL, 1.2), {"drawPath": {"path": j}}]
    else:
        for sign in (-1, 1):
            a = math.pi / 2 + sign * spread
            c = (cx + arm * math.cos(a), cy + arm * math.sin(a))
            eff = sign * sense
            lean = math.radians(sense * (-14.0 if eff < 0 else 20.0))
            hw, hh = 9.0 * s, 17.0 * s
            ca, sa = math.cos(a + lean), math.sin(a + lean)
            j = poly([(c[0] + x * ca - y * sa, c[1] + x * sa + y * ca)
                      for x, y in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))])
            out += [fill(wash(JEWEL)), {"drawPath": {"path": j}},
                    stroke(JEWEL, 1.2), {"drawPath": {"path": j}}]
    out += [stroke(GOLD, 1.4),
            {"drawPath": {"path": circle_path(cx, cy - tail + 26 * s, 3.4 * s, 20)}},
            fill(), {"drawPath": {"path": circle_path(cx, cy, 13.0 * s, 36)}},
            stroke(LINE, 1.3), {"drawPath": {"path": circle_path(cx, cy, 13.0 * s, 36)}},
            stroke(LINE_DIM, 1.0), {"drawPath": {"path": circle_path(cx, cy, 5.0 * s, 20)}}]
    return out


BALANCE_JEWEL_R = 38.0


def balance_shapes(cx, cy, s=1.0, screws=12, opaque=True):
    """The balance wheel. See `wheel_shapes` for what `opaque` means and why."""
    r_out, r_in, r_hub = 150.0 * s, 130.0 * s, 22.0 * s
    r_roller, r_safety = 46.0 * s, 62.0 * s
    out = []
    if opaque:
        out += [fill(), {"drawPath": {"path": circle_path(cx, cy, r_out, 120)}}]
    out += [stroke(LINE, 1.4), {"drawPath": {"path": circle_path(cx, cy, r_out, 120)}},
            {"drawPath": {"path": circle_path(cx, cy, r_in, 120)}}]
    cuts = crossings(cx, cy, 3, r_hub + 2 * s, r_in, 9.0 * s)
    out.append(fill(BG) if opaque else fill())
    out += [{"drawPath": {"path": d}} for d in cuts]
    out.append(stroke(LINE_DIM, 1.0))
    out += [{"drawPath": {"path": d}} for d in cuts]

    mid = (r_out + r_in) / 2.0
    for k in range(screws):
        a = 2 * math.pi * k / screws + math.pi / screws
        sx, sy = cx + mid * math.cos(a), cy + mid * math.sin(a)
        rr = 10.0 * s
        out += [fill(wash(GOLD)), {"drawPath": {"path": circle_path(sx, sy, rr, 20)}},
                stroke(GOLD, 1.1), {"drawPath": {"path": circle_path(sx, sy, rr, 20)}},
                {"drawPath": {"path": poly(
                    [(sx - 0.6 * rr * math.cos(a), sy - 0.6 * rr * math.sin(a)),
                     (sx + 0.6 * rr * math.cos(a), sy + 0.6 * rr * math.sin(a))],
                    close=False)}}]

    out += [fill(), {"drawPath": {"path": circle_path(cx, cy, r_safety, 72)}},
            stroke(LINE_DIM, 1.1),
            {"drawPath": {"path": circle_path(cx, cy, r_safety, 72)}}]
    cres = [(cx + r_safety * math.cos(math.pi / 2 - 0.42 + 0.84 * k / 16),
             cy + r_safety * math.sin(math.pi / 2 - 0.42 + 0.84 * k / 16))
            for k in range(17)]
    cres += [(cx + (r_safety - 16 * s) * math.cos(math.pi / 2 + 0.42 - 0.84 * k / 16),
              cy + (r_safety - 16 * s) * math.sin(math.pi / 2 + 0.42 - 0.84 * k / 16))
             for k in range(17)]
    if opaque:
        out += [fill(BG), {"drawPath": {"path": poly(cres)}}]
    out += [stroke(LINE_DIM, 1.0), {"drawPath": {"path": poly(cres)}},
            fill(), {"drawPath": {"path": circle_path(cx, cy, r_roller, 60)}},
            stroke(LINE, 1.2), {"drawPath": {"path": circle_path(cx, cy, r_roller, 60)}}]

    jx, jy = cx, cy + BALANCE_JEWEL_R * s
    j = poly([(jx - 7 * s, jy - 13 * s), (jx + 7 * s, jy - 13 * s),
              (jx + 5 * s, jy + 15 * s), (jx - 5 * s, jy + 15 * s)])
    out += [fill(wash(JEWEL, 0x40)), {"drawPath": {"path": j}},
            stroke(JEWEL, 1.3), {"drawPath": {"path": j}},
            fill(), {"drawPath": {"path": circle_path(cx, cy, r_hub, 40)}},
            stroke(LINE, 1.3), {"drawPath": {"path": circle_path(cx, cy, r_hub, 40)}},
            stroke(LINE_DIM, 1.0), {"drawPath": {"path": circle_path(cx, cy, 8.0 * s, 24)}}]
    return out


def wheel_shapes(cx, cy, teeth, module, arms=5, s=1.0, opaque=True, edge=LINE):
    """A train wheel.

    `opaque` picks how the openings between the arms are made. Alone, a wheel can fill its
    whole disc with the wash and then punch the openings back out in the background colour
    — cheap, and it looks right. Stacked, that punch is a hole in everything underneath it,
    which is exactly wrong for an X-ray. So when `opaque` is false nothing is punched: the
    disc is never washed, and only the arms — which are the actual metal — are. The result
    is the same picture with the openings genuinely empty rather than painted over.
    """
    rp = module * teeth / 2.0
    r_in = rp - 3.4 * module
    r_hub = max(16.0 * s, rp * 0.14)
    rim = tooth_wheel(cx, cy, teeth, module)
    # arms=0 means a solid wheel: a barrel, a cannon pinion, an hour wheel. Those are
    # not crossed out, because they are not fighting for lightness the way a train wheel
    # is — the barrel is a drum and the motion work barely moves.
    cuts = crossings(cx, cy, arms, r_hub + 3 * s, r_in, 7.5 * s) if arms > 0 else []
    out = []
    if opaque:
        out += [fill(), {"drawPath": {"path": rim}}]
    out += [stroke(edge, 1.25), {"drawPath": {"path": rim}},
            stroke(LINE_DIM, 1.0), {"drawPath": {"path": circle_path(cx, cy, r_in, 120)}}]
    out.append(fill(BG) if opaque else fill())
    out += [{"drawPath": {"path": d}} for d in cuts]
    out.append(stroke(LINE_DIM, 1.0))
    out += [{"drawPath": {"path": d}} for d in cuts]
    out += [fill(), {"drawPath": {"path": circle_path(cx, cy, r_hub, 40)}},
            stroke(edge, 1.3), {"drawPath": {"path": circle_path(cx, cy, r_hub, 40)}},
            stroke(LINE_DIM, 1.0),
            {"drawPath": {"path": circle_path(cx, cy, r_hub * 0.34, 24)}}]
    return out


def pinion_shapes(cx, cy, leaves, module, s=1.0):
    d = leaf_pinion(cx, cy, leaves, module)
    out = [fill(), {"drawPath": {"path": d}},
           stroke(LINE, 1.3), {"drawPath": {"path": d}}]
    for r in (module * leaves / 2.0 - 1.35 * module, 20.0 * s, 9.0 * s):
        out += [stroke(LINE_DIM, 1.0),
                {"drawPath": {"path": circle_path(cx, cy, r, 48)}}]
    return out
