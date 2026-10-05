# Sets 9 to 12 — built overnight, awaiting review

Four sets, 64 documents, staged in `work/set-09` … `work/set-12`. **Nothing is landed.**
Each directory has its `make_setNN.py`, the compiled `.rc` files, `render/` and a
`contact-sheet.png`.

To review: `cd ~/code/github/droidkaigi26/tools/jsonViewr && ./run.sh <dir>`

## Gates

| set | oracle (2D) | gate3d | node validator | device |
|---|---|---|---|---|
| 9  | 12 identical, 2 F-003 | 2 of 2 | 16 of 16 | **not run** |
| 10 | 11 identical, 1 F-003 | 4 of 4 | 16 of 16 | **not run** |
| 11 | 11 identical, 2 F-003 | 3 of 3 | 16 of 16 | **not run** |
| 12 | 11 identical, 2 F-003 | 3 of 3 | 16 of 16 | **not run** |

Every oracle difference is the known F-003 touch delta (4 bytes per RPN token). Nothing
unexplained anywhere.

## The device gate did not run

The phone is attached, awake, unlocked, the app is installed and the files push fine, but
`DocPlayerActivity` starts and immediately finishes for **every** document - including set 7
documents that ran successfully earlier in the session. Force-stopping the app did not help,
and `adb logcat` shows the activity launching with `result code=3` and no RemoteCompose
error. It is environmental rather than a property of these documents, but they are **not
device-verified** and should not be described as such.

That is worth clearing before landing any of these, since it is the gate that catches
over-long expressions and anything else the desktop players tolerate.

## What I fixed while building, and what I left

Fixed after looking at the renders:

* set 9 bacteria - the bacilli ran off the right edge
* set 9 magnetic field - `surface_ribbon` normalises every point to one radius, which
  collapsed the dipole lines into a single arc. Field lines are not on a sphere, so that
  document builds its own strip from the real `r = L sin^2(theta)` points
* set 9 protozoa - captions overlapped their neighbours; now wrapped
* set 10 catalysis pathway, pendulum surface, migration globe - all three were too flat or
  too thin to read

Left for your pass, not broken but not good:

* **set 11 gyroscope** - the wheel and the two vectors read as three separate objects rather
  than one mechanism
* **set 12 clouds** - the left-hand altitude panel is cruder than the right-hand table
* **set 12 cardiovascular** - the live pressure markers are small against the bars

## Conventions these were built against

All four carry the post-fix helper block from set 8, so: sphere winding correct, routes as
ribbons, bitmaps embedded as base64, `clipRect` treated as permanent, `textFromFloat` given
strings, expressions kept under 32 RPN tokens, and every render pinned with `--clock` **and**
`--seed`.

## Review pass, set 9

Rebuild one document after an edit with `python3 tools/buildset.py 9 CSC-DS-00009`. The
generator only writes JSON; the `.rc` and the render are two further steps, and doing them by
hand is how a stale `.rc` ends up beside a fresh `.json` - the generator reports success and
the picture does not change. All three documents below are byte-identical to the Java oracle
and clean under the node validator.

* **CSC-DS-00009 graphs** - the drawings were not the shapes they claimed. The edge set had
  no Hamiltonian cycle, so "drawn as a ring" was seven dots sitting on a circle with chords
  cutting across it, and the grid and tree were worse. Replaced with a seven-cycle plus two
  chords - still seven nodes and nine edges - so the cycle can walk the perimeter, snake
  along the grid rows and hang as tree branches. The tree is now laid out by BFS depth with
  each node under the parent that reached it; placing it by hand around the cycle made the
  perimeter dominant and the panel came out looking like the ring again. The line panel is
  an arc diagram, because a straight edge between distant nodes on a line is drawn straight
  through the nodes in between.
* **ENG-EE-00009 adder** - each bit is now its own box, and a box flashes white when the
  stage reads it and red when the stage writes it, which is what the "watch the carry walk"
  subtitle had been promising without showing. One variable drives both: `floor(t * 2)`
  numbers the half-beats, so stage p reads on 2p and writes on 2p+1. The carry arrows used
  to point **right**, directly contradicting the body text under them; they run right to
  left now, lighting one segment per stage, and the carry out leaves at the left.
* **MTH-GEOM-00009 euclid** - five panels in one row ran the captions together and pushed
  the fifth off the right edge. Now 1-4 in a 2x2 block with the fifth given the whole
  right-hand side, which puts the document's claim into the layout. Postulate 4 draws two
  right angles at different orientations instead of one, since one cannot show that right
  angles are equal to each other.

## Review pass, set 10

`python3 tools/buildset.py 10 <DOC>` rebuilds one document. Two new tools came out of this
pass: `tools/camsweep.py` renders one 3D document under several cameras side by side, and the
camera searches below are in the session log rather than checked in - they are a few dozen
lines of projection arithmetic each.

Edge-clipping was checked across all 16 renders by looking for ink in the outermost columns.
Two had it; nothing else does.

* **PHY-CM-00031** - "height" and "speed" were right-aligned at x=24 and ran off the left as
  "eight" and "peed". Bars narrowed and shifted right to leave a margin.
* **PHY-CM-00034** - the plot ran to x=540 on a 580-wide page while each curve is named at
  its end, so "Sphere, hollow" had 34px for 65px of text. Plot pulled in to 442. Also
  `a = g sin0` was meant to be `sinθ`.
* **CHM-CR-00010** - both routes were invisible and the surface painted over its own legend.
  Three separate faults. The ridge peaked at a **68 degree** flank, and a height field is
  back-facing wherever its slope away from the camera exceeds the camera's elevation, so no
  viewpoint short of straight down showed all of it; broadened to 41 degrees. The routes were
  lifted 0.045 along **+y**, which on a steep flank puts them back inside the surface -
  `drape_ribbon` lifts along the surface normal instead. And the catalyst's dip was wide
  enough in v to still have depth at both ends, so the two routes started 0.06 apart and
  finished 0.06 apart while the legend claimed "Same ends, both times"; narrowing sigma_v to
  0.24 closes that to 0.0055. The two end heights are now drawn, in the colour of that legend
  entry, so the claim can be checked instead of taken on trust.
* **PHY-CM-00033** - the surface rises toward large length, so an eye on the +x side was
  looking at the underside of the rising half and the sheet was culled away; raising the eye
  until the top face showed again flattened the climb to **zero screen pixels**, which is the
  sliver that was there. Moving to -x fixes both at once. Contour lines in each direction
  were added because one flat-shaded sheet gives the eye nothing to read height from, and
  each line is the colour of the legend entry it demonstrates.
* **SOC-ANTH-00010** - the globe was an untextured blue ball, so "Out of Africa" had no
  Africa in it. Now carries set 8's embedded NASA Blue Marble, same `uv_sphere`. Alignment
  was checked by projecting London, Cairo, Lagos, Cape Town and Mumbai and overlaying the
  markers on the render - each lands on its own coastline.

Gates: all five valid under the node validator. The two 2D fixes are byte-identical to the
Java oracle. The three 3D documents are gate3d-only - the oracle has no 3D command at all and
emits a 2D stub (1.6 KB against 133 KB), which is F-014 and not a failure. gate3d passes all
three, and its `--self-test` was run first to confirm it still fails a document with its
`drawMesh3D` calls stripped. **Device: still not run.**

### drape_ribbon

New helper in set 10's block, worth carrying forward. A ribbon laid on a height field and
lifted along the surface normal. Two traps it encodes, both paid for here: lifting along +y
alone sinks the ribbon back into any steep slope, and the side vector must be `normal x
tangent` - taking it as `tangent x normal` reverses it, which swaps two corners of every quad
and leaves the index winding describing a downward-facing strip. Culled, and silently.

### MTH-GEOM-00010 and MTH-GEOM-00012, after review

* **MTH-GEOM-00010 solids** - the drawing illustrated no claim the document makes. It drew
  `min(faces, 8)` copies of one face sliding apart in a ring, which gave the cube four
  squares and the icosahedron eight triangles; neither is a vertex figure, and nothing
  folded. The body text has been arguing about **corners** the whole time. Each panel is now
  the vertex figure - the polygons that meet at one corner, gathering to share it and
  separating again - and the angle they fail to cover is drawn and labelled. A sixth panel
  was added for three hexagons: they close the full 360 and leave nothing, which is why
  there is no sixth solid, and it turns "there cannot be a sixth" from an assertion into
  something on the page.
* **MTH-GEOM-00012 tessellations** - drag replaced by five buttons, and the tiles now pull
  apart and close again. Closing is the claim, so it was checked rather than eyeballed: 20000
  random interior samples per tiling, each landing in exactly one tile, no sample in none and
  none in two. The two that cannot close show the ring at one vertex with the leftover wedge
  drawn and its size printed.

**Buttons are new to this corpus.** Nothing else in sets 1-12 uses `onClick`; all 28 prior
interactions are `touchExpression`. The shape is an exported float variable plus `onClick`
with a `valueFloatChange` action, and invisible `box` hit targets stacked over the canvas in
a `box` root - the canvas draws the buttons so the selected one can be tinted from
underneath, which a child's own `background` would cover. Two things to know:

* `spacedBy` is in SYNTAX.md but **rcj does not implement it**; use explicit spacers, or the
  hit targets drift by the gap width per button.
* `textFromFloat` is not a canvas command in this position - it fails conversion.

A probe document was converted and oracle-checked before any of this was written into the
set, and the finished document is byte-identical to the Java oracle. That gate covers the
encoding only. **Whether a tap actually latches has not been tested - it needs the device.**

### Why the buttons did not work, and what fixed them

The first attempt put **empty** `box` components over the canvas with `offset` and an
`onClick` on each. An empty box measures to nothing, so there was no area to hit and the taps
went nowhere. Copying `36_droidkaigi.json`, which has run on a phone, fixes it:

* the clickable carries **real, sized children** - the hit area is whatever the component
  actually lays out, not what you draw underneath it;
* the buttons sit in **normal layout flow**, not floated over a full-page canvas, with the
  canvas a sibling below them in its own coordinate space;
* the selected state is an underline box with a `visibility` modifier, as that document
  marks its chosen day.

Two further traps found on the way:

* `spacedBy` is in SYNTAX.md but **rcj does not implement it** - use explicit spacers.
* `visibility` must be given a **bare variable reference**, with the expression declared in
  `resources.variables`. Written inline it is sent through `parseIntegerExpression`, so a
  float literal (`0.0`) throws `NumberFormatException` and the document is refused outright;
  with integer literals it parses, but rcj emits a **float** expression op where the
  reference writer emits an **integer** one - 4 bytes different per button. That is an rcj
  divergence, not a formatting delta, and only the oracle catches it. A bare reference is
  byte-identical.

Verified by driving the real web player: served the compiled `.rc` on a scratch page with
`vendor/rc-player.js`, dispatched pointer events at the buttons, and watched the selection
change - Pentagon, then Hexagon, each redrawing the panel, the caption and the underline.

One note on method: synthetic `PointerEvent`s were needed. Automated clicks through the
browser-automation tool never reached the page at all - no `pointerdown`, no `mousedown`,
nothing on a capture-phase listener - so an automated click showing "no change" proves
nothing here. The reference document looked just as broken under automated clicks as the
broken version did, which is what made it clear the test rig was at fault rather than the
document.

## Review pass, set 11 — clipping

Found by scanning the outermost columns of all 16 renders for ink. Four had it; nothing else
does, before or after.

* **CSC-CA-00011 pipeline** - the worst of them, and not really a clipping bug. Ten columns
  at the old `x0`/`cw` made the grid **870px wide on a 620px page**, so columns 7, 8 and 9
  were drawn entirely off the right-hand edge. That is the whole drain phase, which the
  caption underneath is about. Regrid to fit. The clock line is drawn one cell to the right
  of `@clk`, so its clamp came down from 10 to 9 as well, or it lands past the last column.
* **MED-MP-00009 surgery** - the notes column started at x=430 with 150px to the page edge
  and the last note needed 240. Columns pulled left and that note shortened.
* **MED-PHAR-00007 drug mechanisms** - "resting activity" was right-aligned at x=26, so it
  began at about x=-44. Panels narrowed and pushed right to make a margin it fits in.
* **GEO-PG-00001 mountains** - the terrain ran off the left edge and across all four legend
  entries: F-013 again, a 3D scene painted over the whole document with no card to hold it.
  Reframed. The camera was checked **at every value of `@age`**, not just the rendered
  frame - the mesh is scaled in y as the range grows, so a camera that fits the young range
  can still overflow the old one. Terrain ink in the gap above the legend is now 0 at the
  extremes and 171px at mid-growth, all of it still above the legend row.

Gates: all four valid under the node validator. The three 2D ones are byte-identical to the
oracle; GEO-PG-00001 is gate3d-only, as the oracle has no 3D and emits a 1.6 KB stub against
50 KB (F-014). gate3d passes it. **Device: still not run.**

Measuring the gap needed one correction worth recording: a band ending at y=400 includes the
first legend swatch, which is drawn at y-9. The first measurement reported a constant 115px
of "overlap" at every age - constant being the tell, since the terrain changes shape as it
grows and an overlap could not have been identical three times.

## Set 12, and two more clipping bugs in set 9

Set 12 has **no** edge clipping. Sweeping set 9 again - it was reviewed before that check
existed - turned up two it had missed:

* **PHY-QM-00027** - the panel notes were drawn unwrapped at 8.5pt into 136px panels, so
  every one overlapped its neighbour's note and the fourth ran off the page. Wrapped to 30
  characters, two lines each.
* **EAR-GEOP-00009** - the outer dipole field lines crossed both page edges. The scene turns
  on the clock, so **the overflow moves with the rotation and one rendered frame does not
  show it**: 1.25x back looked clean over 8 sampled frames and still crossed by 88px
  somewhere in the turn. 1.65x is the first distance clean across 24 samples, re-checked at
  41. Any future "is it on the page" check on a rotating scene has to sample the whole
  revolution, and densely - the first sampling was too coarse and gave a false pass.

## ENG-CE-00012 — the suspension bridge

Wrong in three ways at once, and the drawing showed all three. `cable_y(0)` came out at
**-0.06**, so the main cable sagged *under* the deck; outside the towers it was clamped flat
at tower-top height instead of descending, so each tower read as an upside-down L with a bar
sticking out sideways; and there were no hangers, which are the one feature that says
"suspension" rather than "arch with poles". Now a parabola slung between the tower tops
sagging to just above the deck, straight back-stays down to anchorages at deck level, and the
deck hung from the cable.

The three bridges were also drawn on top of each other, with the beam's piers running into
the legend. Reframed from above-front so they sit as three separate rows, and the spin swing
cut from 0.42 to 0.22 rad because the new framing is tighter.

One thing tried and reverted: putting the bridges in **legend order** front to back, so the
page and the list read the same way. It looks right written down and is wrong in the picture
- the suspension bridge is the only tall one, so in front its towers stand over the other two
and hide them. Flat thing in front, tall thing behind.

Gates: all three valid; PHY-QM-00027 byte-identical to the oracle, the two 3D ones gate3d-
only and passing. **Device: still not run.**

## The device gate, run

The phone came back and `DocPlayerActivity` behaves again - the overnight "starts and
immediately finishes for every document" was environmental and has cleared on its own.

Gate self-tested first, as it has to be: a document carrying a 40-term float expression was
pushed and the player refused it with `RuntimeException: Float expression too long`. That is
F-022, the exact class this gate exists to catch and the one every desktop check passes. The
gate discriminates.

### 2D — 52 of 52 pass on device

Six of them initially read as failures and had **not reached the phone at all**: `rcdev`
refuses to push when rcj and the oracle disagree, and those six carry the known F-003 touch
delta (4 bytes, one per RPN token). Pushed with `--oracle` they all load; pushed as rcj's own
`.rc` they *also* all load. So F-003 is benign at load time on this build - worth knowing,
because "6 failures" and "6 documents the harness declined to test" are very different
reports and the first one is wrong.

  BIO-MICR-00026 · FIN-ACCO-00009 · EAR-METE-00011 · GEO-PG-00003 · ECO-FE-00019 ·
  MTH-TRIG-00014

### 3D — 12 of 12 cannot be tested here, and it is not the documents

Every 3D document is refused with `Unknown operation encountered 114`. 114 is
`PAINT_3D_STATE`, which `clearDepth3D` emits and every 3D document in the corpus opens with.
Stripping `clearDepth3D` just moves the error to **111**, `SET_CAMERA_3D`.

The reason is upstream of all of it: **`androidx-main3` contains no 3D whatsoever** - no 3D
opcodes in `Operations.java`, no 3D operation classes anywhere in the tree. The installed APK
(2026-09-29) is the newest build on disk and matches that source, so rebuilding or
reinstalling it cannot help. This is the same gap as F-014, which was recorded as "the oracle
has no 3D": the oracle and the player are both built from this checkout, so it was never only
a converter gap. rcj implements 3D ahead of this tree.

**Consequence for the corpus:** the 12 3D documents in sets 9-12 have no engine verification
available at all, on any gate here. `gate3d` passing them means the C++ renderer draws them;
it cannot mean the engine accepts them. They should not be described as device-verified, and
that will stay true until a checkout with 3D exists.

  set 9  BIO-MICR-00024 · EAR-GEOP-00009
  set 10 BIO-MICR-00028 · CHM-CR-00010 · PHY-CM-00033 · SOC-ANTH-00010
  set 11 CHM-CR-00011 · GEO-PG-00001 · PHY-CM-00035
  set 12 BIO-ANAT-00031 · ENG-CE-00012 · FIN-ACCO-00011
