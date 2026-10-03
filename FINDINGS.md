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

## F-003 · `rcj` and the Java oracle disagree on `touchExpression`

**confirmed** · converter · found in set 1 · *cause corrected after first writing*

Minimal repro, three documents of ~175 bytes each:

| document contains | `rcj` | Java | |
| :--- | ---: | ---: | :--- |
| one `textFromFloat` | 176 | 176 | identical |
| one `touchExpression` | 175 | 171 | **differs, 4 B** |
| both | 204 | 200 | differs, 4 B |

**The cause is `touchExpression`, not `textFromFloat`.** My first write-up of this finding
blamed `textFromFloat` on the arithmetic that two documents differed by 4 and 20 bytes with
1 and 4 of them — a tidy 5 bytes each. That was coincidence. Both of those documents also
carried a `touchExpression`, and the rebuilt `ECO-MICR-00002` has two `textFromFloat` and no
touch expression and is byte-identical.

The delta is a flat 4 bytes per `touchExpression` regardless of what else is present, which
suggests one writer emits a field the other omits — a stop mode, a default, or a bound.

**Repro:** a canvas with one `touchExpression` and one `drawCircle` bound to it; 175 against
171 bytes.

Worth remembering as a method note: a per-op byte delta that divides evenly is not evidence
of which op is responsible. Two ops co-occurred and I attributed it to the wrong one.

---

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
