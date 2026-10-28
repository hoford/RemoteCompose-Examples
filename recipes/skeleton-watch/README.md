# Skeleton watch — a recipe you can take apart

A mechanical watch drawn as an X-ray, and the eight documents it is built from. Everything
needed to rebuild it, check it, and change it is in this folder: the generators, three
checkers, and a small expression evaluator. Nothing here reaches outside it.

```
python3 mk_skeleton_watch.py      writes out/skeleton_watch.json
python3 check_skeleton_watch.py   verifies the document it just wrote
python3 check_watch.py --selftest breaks it nineteen ways and proves the checker notices
```

Run every `mk_*.py` and you get the eight documents under `out/`. They are byte-identical
to the ones published in this corpus.

## What it is

| document | what it is |
|---|---|
| `wheel` | a train wheel: 64 fine teeth, thin rim, five crossings |
| `pinion` | 8 fat leaves on a solid body, turning fast and the other way |
| `escape` | 30 club teeth; still for most of a beat, then half a tooth, then still |
| `pallet` | the lever: two jewels, two horns, a guard pin, flat between banking pins |
| `balance` | the oscillator: weighted rim, three arms, 12 timing screws, impulse roller |
| `hairspring` | 12 turns that do not rotate — they wind, unwind and breathe |
| `watch` | the escapement assembled, geometry solved rather than arranged |
| `skeleton_watch` | the whole watch: barrel, train, escapement, motion work, dial, hands |

It tells the real time, and the seconds hand ticks once a second.

## The one idea worth taking

**Everything is a function of one number, and that number is the clock.**

```
t = 3600 * (timeInHr() - 12 * floor(timeInHr() / 12)) + continuousSec()
```

`continuousSec()` is not elapsed time, which is the easy thing to assume. The player
computes it as `minute*60 + second + millis/1000` — the second within the *hour*, accurate
to the millisecond. So a drawing driven by it already shows true seconds and true minutes
with nothing to set. Only the hour hand needs more, because `continuousSec()` wraps hourly
and an hour hand geared off a clock that resets every hour flies back to twelve on the
hour. `timeInHr()` carries it across the wrap; the modulo twelve extends the clock to
0..43200, exactly the span a dial covers.

Every wheel is then that one variable times a constant, and the constants are the ratios
of the teeth actually drawn. Nothing is animated to a rate — change a tooth count and the
hands change with it. That is what `check_skeleton_watch.py` verifies.

Related variables, and why they are not used here: `timeInSec()` is the same
second-within-the-hour but whole seconds, which makes a balance step instead of swing;
`timeInMin()` is the minute within the *day*, and it disagrees with `timeInHr()` under a
pinned clock in at least one player.

## The motions

```
beat    = 2 * f * t                              f = 0.5 Hz, so one tick a second
balance = A * sin(2*pi*f*t)                      a plain sine, +/- 149 degrees
pallet  = B * clamp(-k * sin(2*pi*f*t), -1, 1)   a sine driven hard into its limits, so it
                                                 is flat at +/-B and snaps across
escape  = halfpitch * (floor(beat) + 0.5 - 0.5*cos(pi * clamp(fract(beat)/u, 0, 1)))
```

The escape wheel's expression is the one to keep. `floor(beat)` is the staircase and the
cosine term is the run itself, eased in and out over the fraction `u` of a beat — so the
wheel is stationary for most of every beat and then moves. No state, no keyframes.

**Mind the minus sign on the lever.** It is the difference between the balance pushing the
lever over and the two arriving head-on, and it is not obvious because the parts hang off
their pivots in opposite senses: the impulse jewel is *below* the balance staff, the fork
notch is *above* the lever pivot. Drive both from the same `+sin` and they close on each
other.

## Things that are forced, not chosen

Most of the numbers in this recipe are consequences. Changing one usually changes others,
and the checkers will tell you which.

**Half a tooth per beat, not one.** "One tooth per beat" sounds exactly like what an
escapement does and is twice the truth. The pallets are two and a half pitches apart, so a
release only moves the wheel far enough for the next tooth to reach the *other* pallet.
One whole tooth per oscillation.

**The (n + 1/2) rule is about the angle at the WHEEL centre**, not at the lever pivot —
which is the trap, because the pallets visibly fork at the pivot. Two conditions then fix
the entire escapement and the algebra collapses:

```
r(phi) = sqrt(A^2 + D^2 - 2*A*D*cos(phi))     a jewel's distance from the wheel centre
r(S - B) = r_lock                             it bites the tooth at the right depth
2*gamma  = 2.5 * pitch                        the locking points straddle a gap

  =>   A sin(S - B) = r_lock sin(gamma),   D = A cos(S - B) + r_lock cos(gamma)
  and with the arm equal to the locking radius:  S = B + gamma,  D = 2 r_lock cos(gamma)
```

Because a jewel's distance depends only on its half-angle, rocking the lever raises it for
one jewel and lowers it for the other — one drops in exactly as the other lifts clear.

**The pallet stone is placed by its locking face, not its centre.** Centre it on the
locking radius and it reaches half its length inside the tooth circle; here that meant two
teeth ran clean through the engaged jewel at every banking position. A real stone stands
almost entirely outside the path of the teeth with only its locking corner dipping in.

**The wheel must stop when the lever does.** In a real escapement the wheel's own tooth
drives the lever across, so the run and the crossing are one event. Here they come from two
independent expressions and must be aligned by hand: the unlock fraction is bounded by
`asin(1/steepness) / (pi * f)` over the beat. Leave it longer and the stone is already
sitting in the path with the tooth still on its way.

**The beat rate picks the train.** The seconds hand must advance 1/60 of a turn per tick
and the escape wheel advances half a pitch, which is 1/(2N). Equal at N = 30 — so a
thirty-tooth escape wheel turns once a minute and carries the seconds hand *directly*, with
no fourth wheel. That is what a one-second tick always reduces to.

**The pinions cannot go below ten.** This tooth profile is a raised cosine, not an
involute, so it has no undercut to give a small pinion room: ten leaves clear by 0.22 of a
module, nine by 0.19, eight sits on the knife edge at ±0.05, seven cuts in.

**The directions are not free.** Two meshes separate the escape wheel from the centre, an
even number, so they turn the same way — and the centre carries the minute hand, which must
go clockwise.

**Mesh phase.** Writing each wheel's total angle as theta, rolling gives
`theta_B = C - (NA/NB) theta_A`, and meshing demands a gap facing each tooth on the line of
centres:

```
C    = beta + pi + pi/NB + (NA/NB) * beta
ph_B = C - (NA/NB) * ph_A
```

`ph_A` is the driver's *written* constant, which is not always its phase: one wheel here is
driven off the bare clock variable, whose phase lives inside it, so that mesh takes zero.
An eighth of a pitch out drives four pixels of steel through steel and looks fine.

## Making variations

Start by changing one constant in `parts.py` and running the checkers. They are written to
read the document that ships rather than the code that wrote it, so they will catch a change
that breaks the mechanism even when the picture still looks like a watch.

| you change | what moves with it |
|---|---|
| `FREQ` | the tick rate, and the whole train — the seconds hand stops ticking in step |
| `ESCAPE_TEETH` | the pallet span (derived), the wheel phase, the train ratios |
| `UNLOCK` | how long the run lasts; bounded by the lever's crossing time |
| `PALLET_SPAN_PITCHES` | must stay at n + 1/2 or the wheel is blocked twice over |
| `BRIGHT` | the whole palette; the dial and hands stay bright by design |
| tooth counts | every hand rate, because the hands are geared not animated |

A worked example: to make it tick twice a second, set `FREQ = 1.0`. The checkers will then
tell you the seconds hand no longer advances one mark per tick — the escape wheel has to go
back to 60 teeth to keep `1/(2N) = 1/60`, or the hand needs a wheel of its own.

## The checkers

Three, and they all read the shipped document, never the generator. A generator can be
wrong in a way the generator agrees with.

| | tests |
|---|---|
| `check_watch.py` | the escapement: lock depth, impulse phase, drive direction, the escaping action, mesh clearance, beat rate, the clock |
| `check_hairspring.py` | both ends pinned, the wire inextensible, the coil breathing the right way, turns never touching |
| `check_skeleton_watch.py` | one source of motion, every ratio against the teeth drawn, every mesh clear, the hand rates, the 12:1, the hands set |

Each takes `--selftest`, which breaks the document on purpose first and fails on every
break. That is not ceremony. Writing those breaks found real faults in the checkers
themselves, several times:

- A break that silently matched nothing "passed" a document it had never modified. The
  break helper now refuses to run if it would change nothing.
- Every checker injected its own clock and never looked at what the document said the clock
  *was* — so a movement whose clock had been set to a constant would have passed every test,
  every motion being a correct function of a time that never advances.
- Every geometric test asked where a jewel's *centre* was. That passes happily while a
  tooth runs through the middle of the stone.
- Hands were found by a reach-against-nearest-point rule, which throws out the short
  seconds hand and reports a watch with two hands.
- The "one source" check took the union of variables across all parts, so a hand animated
  directly off the clock contributed no name at all and went unnoticed.

If you add a rule, add the break that proves it bites.

## Drawing conventions

Thin bright edges over fills at low alpha, so where two parts overlap the overlap reads
brighter — a radiograph rather than a pile of stickers. One palette, all derived from
`BRIGHT`, with one deliberate exception: the dial and the hands are *not* dimmed with the
rest. A watch is a thing you read and everything behind it is there to be looked through.
Hands are laid down three times — a wide stroke of the ground to cut them out of whatever
is behind, a fill, then their own edge — because a thin outline disappears into the wheels.

Nothing spells a colour as a hex literal, including the checkers, which find the pallet
stones *by* their colour. Changing `BRIGHT` broke both phase solvers until they were taught
to read the palette instead.
