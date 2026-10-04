# Findings

Problems in the players, the corpus and the JSON→RC converters, found while building the
visualization programme. Addressed **between** build sessions, not during them — a set is
atomic and stopping mid-set to chase a bug is how sets end up half-landed.

Each finding needs a **minimal reproduction**, not the document that happened to expose it.
"19 of 40 documents differ somehow" sat untouched for weeks; "a gradient rect, then
`{"shader": 0}` and a solid colour" was fixed the same day.

Status: `open` · `confirmed` · `fixed` · `wontfix` · `authoring` (not a bug — a trap that
belongs in the authoring guide instead).

---

## F-001 · `rc2json` cannot read documents containing 3D operations

**confirmed** · C++ tooling · found in set 1

```sh
rc2json rc2json work/set-01/PHY-FPP-00003.rc /tmp/out.json
#   Unknown opcode 91 at index 328
```

`rc2image` renders the same file without complaint, so the document is valid — it is the
JSON dumper's opcode table that is incomplete. This matters beyond inspection: `rc2json` is
how we diff two compilers' output, so **any 3D document is currently undiffable**, which is
exactly the class of document we most need to diff.

Related to F-002, which is the divergence this tool would have characterised.

---

## F-002 · `rcj` and the Java oracle disagree on 3D documents, and the renders differ

**confirmed** · converter · found in set 1 · *escalated after rebuilding ECO-MICR-00001*

| document | `rcj` | Java oracle | ratio |
| :--- | ---: | ---: | ---: |
| `PHY-FPP-00003` — 4 sphere primitives | 1,160 | 730 | 1.6× |
| `BIO-MB-00003` — 28 spheres + particles | 3,681 | 1,334 | 2.8× |
| `ECO-MICR-00001` — 81 cube primitives | 11,972 | 2,688 | 4.5× |
| `ECO-MICR-00001` — **one `defineMesh3D`**, 289 verts | 16,479 | **883** | **19×** |

The `defineMesh3D` case is the one to chase. **883 bytes cannot hold the geometry**: 289
vertices alone are 867 floats, which is 3,468 bytes before normals, uvs or 1,536 indices. So
the Java writer is not merely encoding it more compactly, it is dropping most of it.

And the outputs render differently. Playing both through `rc2image`:

```
rcj    33,917 surface pixels
java    4,987 surface pixels
```

Both draw *something*, so this is not a clean "one writer omits the mesh" — it is worse than
that, because a document that silently renders a different shape depending on which writer
compiled it will not announce itself. **The same JSON is not the same document.**

This is the most serious finding so far. Byte-identity against the Java writer is the check
the whole corpus rests on, and for 3D it is both failing and masking a visual difference.

**Repro:** `work/set-01/ECO-MICR-00001.json` through `rcj.convert_doc` and
`rcJson/oracle/oracle.sh`, then render both with `rc2image --time 0` and compare.

**Blocked on F-001** for the op-stream diff that would say exactly what is dropped.

**And the corpus flag does not catch it.** `jsonReproduces` asks whether *`rcj`* rebuilds the
stored `.rc`, not whether the Java writer agrees. All five divergent documents in set 1 are
catalogued `jsonReproduces: "yes"`, which is true and still misleading: an agent told to copy
only from `yes` documents will happily copy a 3D document that compiles to something else
entirely on the Android path. The flag needs either a second field for oracle agreement, or a
name that says what it actually measures.

---

## F-003 · RESOLVED · touchExpression's mapping is dropped by the Java parser

**resolved** · converter dialect · found in set 1, explained in set 5

Earlier entries here guessed at this twice and were wrong both times - first blaming
`textFromFloat`, then calling it a flat 4 bytes per `touchExpression`. It is neither. The
delta is **4 bytes per RPN token of the touch expression**, and it is a dialect mismatch, not
a writer bug.

`RemoteComposeJsonParser.java:1759`:

```java
JSONArray expArr = command.optJSONArray("expression");
float[] exp = new float[expArr != null ? expArr.length() : 0];
```

The Java parser expects `expression` to be a JSON **array of pre-compiled RPN floats**. This
corpus writes it as a **string** - `"touchX() / 480"` - so `optJSONArray` returns null, `exp`
becomes empty, and the touch mapping is silently discarded. rcj compiles the string and emits
the RPN, so rcj's document is longer by exactly one 4-byte token per RPN token:

| expression | tokens | delta |
|---|---|---|
| `touchX()` | 1 | 4 B |
| `touchX() / 480` | 3 | 12 B |
| `touchY() / 380 * 36` | 5 | 20 B |
| `1 - touchY() / 360` | 5 | 20 B |

Verified against all eight 2D documents in sets 1-5 that mismatch; every one matches.

**Which side is right.** rcj is. A document through the Java path keeps the touch *variable*
but loses the mapping, so the drag runs raw instead of through the expression - it still
moves, which is why this never looked like a failure. The byte difference is the only symptom
at rest.

**Consequence for the gate.** These eight documents are NOT writer bugs and should not be
chased. They are the expected cost of writing `expression` as a string. The oracle gate should
compare them with the expression removed, or the corpus should emit RPN arrays.

## F-004 · `alpha` on a 3D mesh does not blend in the C++ player

**open** · C++ player · found in set 1

A mesh painted with `{"alpha": 0.30}` renders fully opaque, so anything behind it is hidden.

```jsonc
// shell drawn first, quarks inside it drawn after
{"paint": {"ops": [{"color": "#FF27385C"}, {"style": "fill"}, {"alpha": 0.30}]}},
{"drawMesh3D": {"mesh": 1, "mode": "software-smooth"}}
```

Measured: a pixel where a quark sits read `(41,63,111)` against the shell's own
`(38,60,106)` — indistinguishable. With the shell switched to `wireframe: true` the same
pixel reads `(12,18,32)`, the background, so the quarks are genuinely occluded rather than
mis-coloured.

Unknown whether this is a missing depth-sorted blend pass or whether mesh alpha is simply
not wired up. **Not yet checked in the browser player** — if the two disagree that is a
second finding.

Worked around in `PHY-FPP-00003` by drawing the confining volume as a wireframe, which is
arguably the better diagram anyway.

---

## F-005 · The corpus teaches syntax that `rcj` cannot compile

**confirmed** · corpus · found in set 1

`docs/layout/k04-text-maxlines-3/doc.json` writes a text component as:

```jsonc
{"type": "text", "text": "Handgloves quickly vexed the wizard", "fontSize": 18}
```

`rcj` requires `value`, not `text`, and rejects the above with *"text without value or
textFromFloat"*. `k04` is marked `jsonReproduces: "unsupported"`, so the corpus knows — but
nothing stops an author (or an agent) reading it as an example and copying the wrong key. I
did exactly that, and it cost two documents in this set.

**Suggested fix:** the document page and `/list` should carry the `jsonReproduces` flag
visibly, and `AGENTS.md` already says to copy only from `yes` — the corpus browser should
make that difficult to get wrong rather than relying on the instruction being read.

201 of 636 JSON documents are `unsupported`, so this is a third of what a reader might copy.

---

## F-006 · `panX: 0.0` centres text, which reads as "no offset"

**authoring** · not a bug · found in set 1

`drawTextAnchored`'s `panX` anchors the text box: `-1` puts its left edge at `x`, `0` centres
it on `x`, `+1` puts its right edge at `x`. Writing `0.0` for a left-aligned title centres it
on the left margin and puts half the text off-canvas.

Every title in set 1 was built this way and the renders still looked plausible — the text was
*there*, just clipped, which is the kind of thing that survives a quick look. Caught by
sampling pixels at `x=0` rather than by eye.

Belongs in `../remotecompose-notes/AUTHORING.md` next to the `clamp` argument-order trap: a
default that reads like "none" but means "centre".

---

## F-007 · `coverage.json` is blind to the 3D surface

**open** · corpus tooling · known before set 1

The cataloguer's opcode table has 176 names and not one is a 3D operation — only
`ADD_MESH_2D`, `DRAW_MESH_2D` and `MATRIX_FROM_MESH_2D`. Sixteen corpus documents use
`drawMesh3D`, `camera3D` and `lights3D` today and the coverage report cannot see any of it.

The programme steers 507 documents by coverage, so this needs fixing before the numbers are
used to make decisions. Same root cause as F-001: an incomplete opcode table, in two
different tools.

---

## F-008 · A wrongly wound mesh is invisible, with no error from anywhere

**authoring** · not a bug · found in set 1

`defineMesh3D` triangles are backface-culled by **winding order alone**. Get it backwards and
the mesh renders as nothing at all — no converter error, no player warning, no partial
output. The document compiles, `rcj` reports success, `rc2image` reports success, and the
canvas is empty where the surface should be.

Measured on the same 17x17 grid, four combinations:

| winding | normals | surface pixels |
| :--- | :--- | ---: |
| `a, a+N, a+N+1` | as computed | **0** |
| `a, a+N, a+N+1` | flipped | **0** |
| `a, a+N+1, a+N` | as computed | 11,395 |
| `a, a+N+1, a+N` | flipped | 11,395 |

Two things worth keeping from that table. Winding decides visibility; **normals make no
difference to it**, so a mesh can be lit wrongly and still show, but wound wrongly and it is
simply gone. And the failure is total rather than partial, which is what makes it hard to
diagnose: an empty canvas looks like a camera problem, a scale problem, or a missing draw.

Cost me a build round on `ECO-MICR-00001` and I only found it by brute-forcing all four
combinations.

Belongs in `../remotecompose-notes/AUTHORING.md`. A cheap engine-side improvement would be a
warning when a `drawMesh3D` culls 100% of its triangles — that is never what anyone wanted.

---

## F-009 · A wireframe mesh writes depth across its whole faces, not just its lines

**open** · C++ player · found in set 1

`{"wireframe": true}` draws only the triangle edges, but still writes the depth buffer for
the **entire triangle area**. So a wireframe sphere drawn around something occludes it
completely, while showing nothing itself except thin lines.

Measured on `PHY-FPP-00003`, counting quark-coloured pixels:

| draw order | quark pixels visible |
| :--- | ---: |
| wireframe shell first, contents after | 256 |
| shell removed entirely | 678 |
| **shell drawn last** | **664** |

The shell was costing 62% of its own contents while appearing to be a transparent cage. The
symptom reads as "nothing inside is rendering", which sends you looking at mesh ids, camera
placement and transforms — none of which are the cause.

**Workaround:** draw a containing wireframe *last*. Its lines then pass the depth test in
front of the contents and the contents survive, which is also the correct look.

Whether this is intended is a fair question — a wireframe pass that wrote depth only along
the lines it actually draws would behave the way everyone will expect. Related to F-004: both
are cases where a mesh you can see through still blocks what is behind it.

---

## F-010 · A texture is invisible on a wireframe mesh, and nothing says so

**authoring** · not a bug · found in set 2

`texture3D` sets a bitmap on the paint state, but a mesh drawn with `wireframe: true` draws
only its edges, so the texture never appears. The document compiles, renders, and shows a
wireframe cage — looking exactly like a document that has no texture at all.

This is a sharp edge because the two features pull in opposite directions. F-009 says draw a
containing wireframe *last* so it does not occlude its contents; F-010 says a wireframe
cannot show a texture. A textured containing shell therefore cannot work at all: filled, it
hides everything inside it (F-004, since alpha does not blend); wireframe, it loses the
texture.

`BIO-CB-00008` shipped its first version claiming "membrane is a bitmap texture" in its own
caption while showing none. Fixed by moving the texture onto the nucleus, a filled mesh, and
leaving the membrane an untextured cage. Verified by counting distinct colours across the
nucleus: 2,421, where a flat fill gives a handful.

Worth noting for the authoring guide as a rule rather than three separate facts: **in this
engine a 3D surface can be seen through, or textured, but not both.**

---

## F-011 · The cataloguer could not resolve a document's own asset paths

**fixed** · corpus tooling · found in set 2

`rcx catalog`'s round-trip check called `convert_doc(doc)` without `base_dir`, so a `file:`
bitmap reference — which is relative to the document — never resolved. The converter raised,
the check caught the exception, and the document was recorded `jsonReproduces: "unsupported"`.

`BIO-CB-00008` recompiles byte-for-byte from its own directory, so the label was simply
wrong. The exception was swallowed, which is why it looked like an unsupported construct
rather than a path problem.

Fixed by passing `base_dir=str(json_path.parent)`. Only one corpus document was affected
today because images are the thinnest part of the corpus — 5 documents use them at all — but
the programme is about to add many more, and every one would have been mislabelled.

Compounds F-002's point about `jsonReproduces` being trusted more than it earns: here it was
reporting failure for a document that works.

---

## F-012 · A sized `canvas` does not clip its own drawing

**confirmed** · engine or authoring · found in set 5

A `canvas` component with `{"width": 120}, {"height": 80}` inside a layout takes 120x80 of
space, and its siblings are positioned as though it did. But anything it draws beyond those
bounds is still drawn, over whatever comes next.

Minimal repro: a 120x80 canvas drawing a radius-200 circle, followed by a green box.

| canvas content | pixels escaping into the box below |
| :--- | ---: |
| 2D `drawCircle`, no clip | 1,250 |
| 3D `drawMesh3D`, no clip | 1,262 |
| either, with `clipRect` first | **0** |

Two things worth separating. It is **not a 3D problem** - plain 2D drawing escapes exactly
as readily, which I had assumed otherwise until the probe said so. And the layout is not
confused: the box sits where it should, so this is purely a drawing-bounds question.

`ENG-ME-00005` shipped a first version where a turbine rotor drew across all four stage
cards beneath it, which looked like a layout bug and was not.

**Workaround:** begin any sized canvas inside a layout with
`{"clipRect": {"left": 0, "top": 0, "right": W, "bottom": H}}` matching its modifiers. Cheap
and total.

Whether the engine *should* clip is a fair question - an unclipped canvas is occasionally
useful for deliberate overflow - but the default surprises, and nothing warns. At minimum it
belongs in the authoring guide beside the other silent-failure traps.

---

## F-013 · Nested 3D projects into the document's viewport, offset by the component

**confirmed** · engine · found in set 5

A `camera3D` scene inside a sized `canvas` component does not project into that component.
The viewport appears to take the DOCUMENT's dimensions, translated to the component's
origin, so the scene centres at roughly `component offset + document size / 2` — usually
well outside the component, and often off the document entirely.

Minimal repro: a 300x400 document, a column holding a 280x250 box then a 140x100 canvas
containing a sphere at the world origin.

```
canvas component occupies   y 250..350,  x 0..140
sphere actually drawn at    y 386..399,  x 122..178   (centre 150, 392)
document centre             150, 200
canvas centre                70, 300
```

392 is neither. It is the canvas's y-offset of 250 plus half the document height, 200 —
clipped at the document edge, so only a sliver shows.

**Consequence.** The set 3 Higgs card and the set 5 turbine card both put a 3D scene in a
layout card. Both appeared to "work" only because their cards happened to sit near enough to
the middle; the turbine's card sits lower, so its rotor was cut in half and its hub was never
visible at all. Combined with F-012 — a canvas does not clip — the two failure modes mask
each other: clip it and the scene is cut off, do not clip it and the scene draws over its
neighbours.

**Workaround:** give 3D a canvas that fills the document, and use layout components for the
surrounding material, stacking the two in a `box`. The 3D then centres predictably at the
document centre and can be positioned by translating the scene in world space.

This supersedes the advice implied by set 3's Higgs document, which got away with it.

---

## F-014 · The Java oracle has no 3D at all, and drops it silently

**confirmed** · oracle · found in set 5

`RemoteComposeJsonParser.java` contains **zero** references to any 3D command - no `camera3D`,
`lights3D`, `matrix3D`, `defineMesh3D`, `drawMesh3D`, `meshPrimitive3D`, `clearDepth3D`,
`texture3D` or `cube3D`. Every one is silently skipped, with no warning on stderr.

Probed one command at a time into an otherwise empty 200x200 canvas:

```
             rcj     oracle
cleardepth    109      100
matrix        134      100
lights        133      100
camera        165      100
prim_sphere   150      100
mesh_define   229      100
mesh_draw     238      100
empty canvas    -      100   <- identical to every row above
```

The oracle's output for a document full of 3D is **byte-identical to an empty canvas**.

**Consequence, and a correction.** Byte-identity against the Java writer is this program's
primary gate, and it has been vacuous for every 3D document: 16 of the 80 landed so far,
exactly the one-in-five 3D cadence. Those documents were never gated. My earlier reports that
sets landed "byte-identical to the oracle" were true only of their 2D documents; I did not
separate the two, and should have.

The 2D half does still hold: 56 of 64 are byte-identical, and all 8 exceptions are F-003.

**Replacement:** `tools/gate3d.py`, which renders instead. See F-015 for why the obvious
alternative does not work.

---

## F-015 · rc2json cannot decode most 3D ops and loses stream sync

**confirmed** · C++ reader · found in set 5

The natural stand-in for the oracle is a round-trip through the C++ reader, which is an
independent implementation. It does not work. Of the seven 3D commands probed, `rc2json`
decodes two:

```
lights       SET_LIGHTS_3D     ok
matrix       MATRIX_3D_OP      ok
mesh_draw    DEFINE_MESH_3D    then 6 stray opcode-0 "HEADER" ops; DrawMesh3D never appears
cleardepth / camera / prim_sphere / mesh_define    readback fails outright
```

After `DEFINE_MESH_3D` the reader loses sync and reports the remaining stream as repeated
opcode-0 HEADER ops. Note the C++ **renderer** (rc2image) draws all of these correctly, so
this is specific to the rc2json path, not to the C++ player in general.

**Consequence:** no structural verifier exists for 3D on the desktop. `tools/gate3d.py`
therefore gates on rendered evidence - that the 3D adds real ink over the same document with
its 3D stripped, that it does not swallow the canvas, and that a time-driven scene moves -
and reports the device step as outstanding, because rendered evidence is not engine evidence.

---

## F-016 · stopMode is a no-op in rcj; the Java parser wants touchMode

**confirmed** · converter · found in set 5

Every touch document in this corpus writes `"stopMode": "gently"`. rcj's output is
byte-identical with the key present and absent, so it does nothing. The Java parser does not
read `stopMode` either - it reads an integer `touchMode`, and its output *does* change when
that is set.

So the key is dead on both sides: the corpus has been asking for a stop behaviour it never
gets. Harmless today, but it means none of the drag documents have had their deceleration
exercised, and anyone reading these as examples would copy a key that does nothing.

---

## F-017 · The 3D opcodes are an unlanded CL; no 3D document runs on a device

**confirmed on device** · engine · found in set 6

Every 3D document in this catalog is refused by the engine:

```
java.lang.RuntimeException: Unknown operation encountered 114
```

114 is `PAINT_3D_STATE` in `rcj/writer.py`, under a comment that says what is going on:

```python
# ---- 3D (in review as ag/4108133) ----
```

The 3D opcodes come from a change still **in review**. The engine in this checkout does not
have it: `remote-core` contains no 3D operation class at all, and `Operations.java` has no
3D opcode. The numbers are not merely unknown, they are **taken**: opcode 110, which rcj
writes as `DEFINE_MESH_3D`, is `EVENT_ACTION` in the shipped engine. A 3D document is
therefore misread before it fails, and it fails at the first opcode with no assignment at all.

**Measured on an X4000, Android 14, with the player-view-demos app:**

| | ran | refused |
|---|---|---|
| set 6, 2D (13) | 13 | 0 |
| sets 1-5, 3D (16) | 0 | 16 |
| set 6, 3D (3) | 0 | 3 |

So the device path works; the failure is specific to 3D, and total.

**What this means for the programme.** One document in five is 3D by design — the schedule
uses `THREE_D_IN = 5`. That cadence is building against a change that has not landed. Those
documents render in the C++ renderer and in the TypeScript player, so every desktop check
passes; the engine is where they stop. Nineteen documents are in this state now, and a 32-set
pass would reach about 96.

**Decided (2026-10-03): the one-in-five 3D cadence continues.** The C++ and TypeScript players
both implement 3D, so these documents are real, reviewable and useful today; only the Android
engine in this checkout lacks the ops. Device verification of a 3D document requires pulling
ag/4108133 into the tree and rebuilding the APK, and until that happens a 3D document's gates
are: compile, gate3d on the C++ renderer, and the browser player. A refusal with
`Unknown operation encountered 114` on a phone is expected, not a regression - do not spend
time rediagnosing it.

**Corrected claim.** Two of the sixteen first appeared to run. They did not: rcj had failed on
a texture path and `rcdev` fell back to the oracle, which drops 3D, so what reached the phone
was a 2D remnant of the document. See F-018. With that fixed, the score is 0 of 16.

---

## F-018 · rcdev's oracle fallback silently shipped a different document

**confirmed, fixed** · tooling · found in set 6

`rcdev.py build_one` falls back to the Java parser whenever rcj raises, so that authoring is
never blocked by converter coverage. That is reasonable for a 2D construct rcj lacks. For a
3D document it is not: the Java parser has no 3D commands, so the fallback ships a document
with all the 3D removed - and reported `OK`.

Two documents were recorded as running on the device that way. What ran was their 2D remnant.
The trigger was unrelated: `convert(src)` was called without `base_dir`, so relative texture
paths resolved against the working directory, every textured document raised, and the
fallback took over. (Same class of bug as F-011 in rcx.py, in a second tool.)

Fixed both halves: `base_dir` now comes from the document's own directory, and a fallback that
drops 3D says `[3D DROPPED: the oracle cannot see it]` instead of a quiet `oracle`.

Also added `rcdev.py --no-check`, because the byte-check otherwise refuses to ship any
document with a `touchExpression` (the expected F-003 delta) and any 3D document at all - the
two kinds of document most worth putting in front of the engine.

**Engine result for F-003.** With the check bypassed, both touch documents run on the engine
using rcj's bytes. The engine accepts the RPN mapping the Java parser discards, which confirms
rcj is the correct side of that divergence.

---

## F-019 · CORRECTED · the clock can be pinned; --time 0 silently did not

**resolved, tooling fixed** · player · found in set 6

What is true: `--anim` pins `animationTime` only, and without a clock flag every date and time
variable reads the wall clock, so a document using `continuousSec()` renders differently every
run.

**What I got wrong.** I reported that `continuousSec()` "cannot be pinned by any flag rc2image
offers". It could: `--time <epoch_ms>` already pinned the whole set. The real defect was
narrower and nastier - both `rc2image` and `CoreDocument` tested `fixedTimeMs > 0`, so the one
value a person is most likely to pass for "the beginning", `--time 0`, silently did not pin
anything and left the wall clock running. Every render I had made used `--time 0`, which is
why the clock appeared unpinnable.

Two further conclusions downstream of that error are also corrected:

* The "3D renderer non-determinism" (7,572 px between identical runs) was the wall clock
  moving, not the rasterizer. With the clock pinned, repeated renders are byte-identical.
* gate3d's "moved N px" column compared two `--time` values that both failed the `> 0` test,
  so it measured drift rather than animation.

**Fixed.** The guard now tracks whether a flag was *given*, not whether its value is nonzero
(`mFixedTimeMs = -1` means unset, so epoch 0 is pinnable), and there is a readable flag:

```
--clock HH:MM[:SS]              today at that local time
--clock YYYY-MM-DD              that date at midnight
--clock YYYY-MM-DDTHH:MM[:SS]   that date and time
--clock @MILLIS                 raw epoch milliseconds
```

It pins the whole set from one instant - `continuousSec`, seconds, minutes, hour, month,
weekday, day of month, day of year, year, epoch second - so they stay mutually consistent. An
unparseable spec is an error rather than a silent fall-back to "now".

Verified, with the negative control the project asks for:

```
--clock 14:30:05 vs 14:30:35   30.00 s apart   (exactly the 30 s asked for)
--clock 09:15:00, three runs   -0.11, -0.11, -0.11   (pinned)
no flag, three runs            10.50, 11.68, 12.86   (drifts, so the test can fail)
```

**Authoring consequence that still stands.** A document whose opening phase is empty will be
captured empty unless the clock is set to a later instant. Pick a `--clock` that shows the
document at its most legible, and keep it with the document.

---

## F-020 · textFromFloat renders 0 for a numeric literal, silently

**confirmed** · converter · found in set 6

`textFromFloat`'s `value` must be a string - an expression, or a number written as one. Given
an actual JSON number it emits `0`, with no warning:

```
{"type": "textFromFloat", "value": 78.0,   "whole": 2, "decimal": 0}  ->  "0"
{"type": "textFromFloat", "value": "78.0", "whole": 2, "decimal": 0}  ->  "78"
{"type": "textFromFloat", "value": 78.0,   "whole": 3, "decimal": 1}  ->  "0.0"
```

The failure is the worst shape available: the document renders, the layout is right, and a
confident wrong number appears where the right one should be. `SOC-PSYC-00005` shipped in this
set claiming "0% of it does not make the next step" about three different stages before this
was caught - and it was caught by reading the picture, not by any gate.

No check in this programme would have found it. Byte-identity passes, the renderer is happy,
and the number is plausible. Worth remembering when a figure in a generated document looks
suspiciously round.

---

## F-021 · clipRect intersects and can never be widened

**confirmed** · engine semantics · found in set 6

`clipRect` narrows the clip and nothing in a canvas's command list can widen it again. There
is no save/restore, and re-issuing a full-canvas `clipRect` does nothing:

```
no clip                              40000 px   (200x200)
clipRect 100x100                     10000 px
clipRect 100x100 then clipRect full  10000 px   <- the "reset" is a no-op
```

A clip is therefore permanent for the remainder of that canvas. It IS scoped to the canvas
component, though - a nested canvas that clips does not affect a sibling drawn afterwards:

```
clipped child    2500 px   (clip held inside the child)
sibling after   10000 px   (full size; no leak)
```

**This broke three documents in one set, all the same way.** BIO-GENE-00019, MTH-ALGE-00006
and FIN-MARK-00004 each clipped something mid-document and then "reset". Everything after the
clip - titles, a bar, axis labels, a whole discriminant readout - was silently confined to a
small rectangle. Each document still rendered, and still looked deliberate; the missing title
was the only visible hint, and on a contact sheet that reads as a design choice.

**Rule.** Either draw clipped content last, or give it its own nested canvas. And note how
this composes with F-012: a sized canvas does not clip its own drawing, so the fix for F-012
is a `clipRect` - which is exactly the irreversible thing described here. The safe pattern is
a nested canvas whose first command is its clip and which draws nothing it does not want
clipped.

---

## F-022 · rcj writes over-long expressions that the engine will refuse

**confirmed** · converter · found in set 7

A `FloatExpression` is capped at 32 RPN tokens and the cap is enforced by the **reader**. The
Java writer checks it at write time and refuses:

```
java.lang.RuntimeException: 300.0 0.14 [45] 290.0 - 104.55 / 5.0 pow * 0.9 [45] 290.0 -
104.55 / 3.0 pow * - 1.1 [45] 290.0 - 104.55 / * + 30.0 * - [48] sin 3.0 * +  to long
  at FloatExpression.apply(FloatExpression.java:332)
```

rcj does not check. It wrote the same expression without complaint - 787 bytes more than the
oracle produced - and the C++ renderer drew the result correctly. A device would have refused
the document.

**This is the trap CLAUDE.md names explicitly**, and it is worth noting how close it came to
shipping. The document compiled, rendered, looked right, and passed every visual check. The
only thing that caught it was the oracle byte comparison showing a difference too large to be
F-003 - an unexplained 787 B, in a set where every other difference was 4.

**Consequence:** treat any oracle delta that is not a multiple of 4 matching the touch
expression's token count as a hard failure, not a curiosity. And when an expression starts
needing `pow` and nested parentheses, count the tokens: the budget is per expression FIELD,
so the fix is usually to compute constants in the generator rather than in the document.

rcj should enforce the cap at write time. Until it does, the oracle is the only thing standing
between a long expression and a device.

---

## F-023 · rand() is not pinned by the clock, so particle documents never reproduce

**confirmed, tooling fixed** · player · found in set 7

`--clock` pins every date and time variable, and with it a 3D document renders twice at 0 px
difference (F-019). It does **not** pin `rand()`. A document whose particles draw their
initial values from `rand()` therefore lands somewhere different on every run:

```
particles with rand() in initialValues
  no clock flag        3188 px between two runs
  --clock pinned       3030 px between two runs     <- the clock does not help
  rand() replaced by constants, --clock pinned   0 px
```

This is by design in the player, not a bug: `JavaRandom` seeds arbitrarily on first use,
matching the reference's lazy `new Random()`, and a document that seeds itself gets a
repeatable stream on every player. But it means a pixel baseline cannot include any particle
document unless the seed is fixed from outside.

**Fixed** with `rc2image --seed N`, which seeds the stream before the first paint - the point
that matters, because particle initial values are drawn once when the system is created.
A document that seeds itself still wins.

```
--clock only          3099 px between two runs
--clock --seed 7         0 px between two runs
--seed 7 vs --seed 8  3140 px differ   (so the flag is doing something)
```

**Use both flags together.** `--clock` alone looks like it is enough right up until the
document has particles in it, and then it quietly is not.

Reach of this: sets 1-7 contain particle documents in every set bar one. None of them were
pixel-reproducible before this.
