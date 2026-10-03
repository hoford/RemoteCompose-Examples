# The visualization programme

A months-long effort to build an even, deliberately broad catalogue of RemoteCompose
visualizations. 507 documents, 32 sets of 16, one set at a time.

It has three goals, and they are ordered. When they conflict, the earlier one wins:

1. **Find problems in RemoteCompose.** The catalogue is a test harness that happens to be
   useful. A set that builds perfectly and teaches us nothing is a worse day than a set where
   four documents expose an engine bug.
2. **Learn to author with RemoteCompose.** Whatever we discover about expressing an idea in
   this format belongs in `../remotecompose-notes/` so the next person starts ahead of us.
3. **Give agents something to work from.** Every document lands in the corpus with its
   metadata, so an agent asking "how do I show a cycle" has twenty answers.

Nothing here is urgent. The programme is designed to be interrupted — see
**[Pausing and resuming](#pausing-and-resuming)**, which is the part to read first if you are
returning to this after a gap.

---

## The three axes

The taxonomy lives in `catalog/vis-taxonomy.md`. Three axes intersect, and a document is one
cell of the product.

### WHAT — knowledge domain

507 leaf topics across 21 domains, parsed straight from the taxonomy. Both depths are
addressable: some domains go three levels deep (`Physics / Atomic Physics / Electron
orbitals`) and eight go only two (`Astronomy / Exoplanets`). Treating only the deep ones as
targets would silently drop 84 topics, including every one in Astronomy, Technology and
Transportation.

### HOW — technique, which is to say engine subsystem

Eight values. This axis is **not a list of visual styles** — each value names a part of the
engine, so "evenly distributed across HOW" and "even pressure on every subsystem" are the
same sentence. That equivalence is what makes the programme find bugs instead of producing
500 more static diagrams of the kind the corpus already has 900 of.

| HOW | the subsystem it obliges you to use | corpus today |
| :--- | :--- | ---: |
| `static-diagram` | paint, the draw primitives, anchored text | ~900 docs |
| `annotated-layout` | `box` `row` `column` `flow` `fitBox`, collapsibles | 925 |
| `data-plot` | `resources` arrays, `loop`, `arraySpline`, `textFromFloat` | — |
| `path-form` | `pathCreate`, `drawPath`, `pathExpression`, clipping | 180 |
| `expression-animation` | time-driven expressions, matrix transforms | 596 |
| `particle-system` | `createParticles`, `particlesLoop`, `impulse` | **3** |
| `interactive` | `touchExpression`, `conditionalOperations` | 46 |
| `raster-and-text` | bitmaps, textures, text-on-path, text styling | **5** |

The last column is why the axis is shaped this way. `particle-system` and `raster-and-text`
are nearly untouched after 1,101 documents; a flat "build good visualizations" instruction
would never reach them.

### WHY — communication purpose

`explain` · `explore` · `compare` · `demonstrate` · `simulate` · `analyze`

Taken verbatim from the taxonomy. The purpose is a real constraint on the document, not a
label applied afterwards: a `compare` document needs two things side by side and a shared
scale; an `analyze` document needs readable values, not just a shape.

### Visual identity — vary it on purpose

**Pick a palette per document, deterministically from its id.** Three sets in, every
document shared one navy ground and one blue accent, and the catalogue had started to look
like one author's taste rather than a demonstration of what the format can do. For a corpus
whose job is to be a source of examples, that is a real weakness.

`work/set-03/make_set03.py` carries six — `midnight`, `carbon`, `paper`, `plum`, `forest`,
`ember` — each supplying the same nine roles so no document needs to know which one it got.
Include a **light** ground: a light document differs from a dark one far more than two dark
documents differ from each other.

Two rules about how the pick is made:

* **Hash the document id, never call `random`.** Generators must be deterministic — the
  corpus stores compiled bytes, and a rebuild that produced different colours would turn
  every re-run into a false diff.
* **Vary the palette, not the structure.** The axis obligations, the layout conventions and
  the authoring rules stay fixed. Only the colour identity moves.

Sets 1 and 2 predate this and are uniformly `midnight`. They can be re-palettised later;
doing so rewrites their bytes, so it is a deliberate re-landing rather than a touch-up.

### Dimension — 2D or 3D, as a delivery constraint

**80% 2D, 20% 3D** (101 of 507). This is not an aesthetic ratio.

- 3D costs more to run everywhere.
- Some devices will never run the 3D pipeline at all — a watch face, for one. A `2D` document
  here uses **nothing** from the 3D pipeline, so it is the tier that runs anywhere.
- 2D often simply looks better. Flattening is frequently the better explanatory choice, not a
  compromise.
- The corpus already has 16 documents exercising all 11 3D commands, so 3D is covered
  breadth-wise. This programme keeps it represented without over-spending on it.

Tune it with `THREE_D_IN` in `tools/visplan.py` — but keep it **coprime with 6**, or a
quarter of the joint space becomes unreachable (the reason is in that function's docstring,
and the audit will catch you).

Each set of 16 carries **2 to 4** 3D documents, so the running cost of a day is predictable.

**Twin rule.** When a 3D document covers a topic that constrained devices also need, record a
2D counterpart in the schedule's `twin` field. Twins are also the cleanest cost comparison we
can make: same subject, same purpose, two pipelines.

---

## The schedule

Pre-generated, balanced, and auditable rather than asserted.

**Every command in this document runs from the repository root**, which is
`/Users/john/code/github/RemoteCompose-Examples` — not from `rcJson`, where the taxonomy
originally came from. `cd` there first or the tool paths will not resolve.

```sh
cd /Users/john/code/github/RemoteCompose-Examples
python3 tools/visplan.py build     # (re)generate the schedule and the state file
python3 tools/visplan.py audit     # prove the balance claims
python3 tools/visplan.py status    # where we are, and the next set
python3 tools/visplan.py set 7     # set 7 as a work order
```

`catalog/vis-schedule.json` holds all 32 sets. Current balance, from `audit`:

```
507 documents in 32 sets, 507 unique topics, 0 duplicates
HOW   63-64 each        (spread 1)
WHY   84-85 each        (spread 1)
DIM   406 2D / 101 3D   (80% / 20%)
HOW x WHY           48 of 48 cells
WHY x DIM           12 of 12 cells
HOW x WHY x DIM     96 of 96 cells
every set of 16: all 8 subsystems, all 6 purposes, <=4 from any one domain
```

**Every set is itself a full-spectrum probe of the engine.** That is the property worth
protecting. It means a day's work pressures all eight subsystems, so when three documents
fail you learn *which subsystem* rather than "something broke"; and it means coverage stays
even no matter which set we stop after.

### The schedule is a proposal, not a contract

The axis assignment is mechanical, so some pairings are absurd. Set 1 really does ask for
*Elasticity* as a particle system and *Consumer behavior* in 3D.

**The curation rule: permute topics between slots within the set. Never change the set's
technique or purpose multiset.** The 16 slots and 16 topics are both fixed; which topic sits
in which slot is yours to choose. That keeps every balance property exactly intact while
letting each technique land on a subject it suits.

Resist the urge to soften every odd pairing, though. *Supply and demand* as an
`expression-animation` sounds wrong and is probably the most informative document in set 1 —
forcing a technique onto an unnatural subject is how we find out what the technique cannot
express.

---

## What one document is

Laid out as the corpus expects, under `docs/<collection>/<id>/`:

| file | what it is |
| :--- | :--- |
| `doc.json` | the document, in the canonical dialect — object root, commands keyed by name, `paint: {ops: [...]}` |
| `doc.rc` | compiled, byte-identical to the Java oracle |
| `entry.json` | **curated** metadata — title, description with `#hashtags`, the axis values |
| `src/make.py` | the generator, when geometry warrants one (loops, repeated structure) |
| `derived.json` | generated by `rcx catalog`; never hand-edited |

Write `entry.json` to the taxonomy's own metadata shape (`catalog/vis-taxonomy.md`, "Typical
Meta data"), carrying at least:

```jsonc
{
  "id": "PHY-FPP-00001",
  "title": "Quarks Inside a Proton",
  "subject": ["Physics", "Fundamental / Particle Physics", "Standard Model"],
  "concepts": ["proton", "quark", "gluon", "strong force"],
  "how": "static-diagram", "why": "explain", "dimension": "2D",
  "representation": "explanatory-model",
  "time": "static",                   // static | animated
  "interaction": [],                  // rotatable, zoomable, selectable
  "scale": "10^-15 m",
  "accuracy": "conceptual",           // conceptual | schematic | quantitative
  "audience": ["high-school", "undergraduate"],
  "dataSource": "theoretical-model",
  "description": "… #physics #particles"
}
```

**Authoring rules worth having in front of you.** Read `AGENTS.md` for the full set; the ones
that bite most often:

- `clamp(min, max, value)` — value **last**. `clamp(x, 0, 1)` evaluates to 0.
- Expressions cap at **32 RPN tokens**, enforced by the *reader*, not the writer. An over-long
  expression builds, passes on desktop, and fails to load on a device.
- A variable is textual substitution re-evaluated at every `@reference`, not a computed-once
  binding. Two references to a variable holding `rand()` give two different numbers.
- Paint: use the `ops` array form. Unknown keys in the direct form compile and are **silently
  dropped**.
- One `FloatExpression` per expression *field*, not per command — a `drawCircle` with four
  computed arguments is four operations.

---

## The daily loop

One set of 16. Expect a day, and expect some days to produce four documents and three bug
reports instead.

### 1. Take the work order

```sh
python3 tools/visplan.py status            # confirms the set number after any gap
python3 tools/visplan.py set N
```

Permute topics across slots if the pairings need it. Record what you swapped in the set's
notes — a swap that keeps happening is telling us something about the technique.

### 2. Build into a staging directory

```sh
mkdir -p work/set-07
```

Build all 16 before validating any. Staging matters: nothing enters `docs/` until the whole
set passes, so a half-landed set cannot exist.

### 3. Compile and check — but 2D and 3D take different gates

**3D does not run on the Android engine in this tree, and that is expected.** The 3D opcodes
come from ag/4108133, still in review; the C++ and TypeScript players implement them, the APK
does not. A phone refusing a 3D document with `Unknown operation encountered 114` is F-017 and
needs no diagnosis. The one-in-five 3D cadence continues regardless, because both desktop
players render these documents properly. To verify 3D on a device, pull ag/4108133 into
androidx-main3 and rebuild the player-view-demos APK.

**The oracle gate does not apply to 3D.** `RemoteComposeJsonParser.java` contains no 3D
command at all and drops every one silently, emitting a document byte-identical to an empty
canvas (F-014). Comparing a 3D document against it compares it against nothing. Sets 1-5 were
landed without this distinction and their 16 3D documents were effectively ungated; do not
repeat that.

```sh
cd work/set-07
K='camera3D|lights3D|matrix3D|defineMesh3D|drawMesh3D|meshPrimitive3D|clearDepth3D|texture3D|cube3D'
for f in *.json; do
  python3 -c "import sys,json;sys.path.insert(0,'/Users/john/code/github/rcJson');import rcj;\
open('${f%.json}.rc','wb').write(rcj.convert_doc(json.load(open('$f'))))"
  if grep -qE "\"($K)\"" "$f"; then continue; fi          # 3D: see below
  ORACLE_QUIET=1 /Users/john/code/github/rcJson/oracle/oracle.sh "$f" "/tmp/${f%.json}.oracle.rc"
  cmp "${f%.json}.rc" "/tmp/${f%.json}.oracle.rc" || echo "ORACLE MISMATCH: $f"
done

# 3D documents, which the oracle cannot see:
python3 ../../tools/gate3d.py --self-test <one 3D doc>   # prove it fails before trusting it
python3 ../../tools/gate3d.py *.json

node ../../tools/rc.mjs validate <each>.json     # the converter the playground uses
```

An oracle mismatch is a **finding**, not a chore — with one known exception. A document using
`touchExpression` with a string `expression` is expected to be longer than the oracle's by
4 bytes per RPN token, because the Java parser wants a pre-compiled float array and silently
drops the string (F-003). Check that the delta matches the token count before investigating.

`gate3d.py` gates on rendered evidence, not structure: the obvious alternative — round-tripping
through the C++ reader — does not work either, since `rc2json` decodes only two of seven 3D
ops and loses stream sync (F-015). A gate3d pass means the C++ renderer draws it. It does
**not** mean the engine accepts it, and the tool says so when no phone is attached.

**Rebuild the oracle classes when the library is synced.** `oracle/build-mesh` shadows the
jars class-for-class and does not rebuild itself; stale classes make the oracle drop opcodes
it does not know and "pass" everything. Run `oracle/build-mesh-classes.sh` after any sync.

### 4. Render, in both players — with the clock pinned

```sh
# C++ reference. ALWAYS pass --clock: without it every date and time variable reads the
# wall clock, so two renders of the same document differ and nothing can be compared.
rc2image doc.rc out.png --clock 2026-03-09T14:30:00
rc2image doc.rc out.png --clock @1773066600000     # or raw epoch millis, for sub-second steps
# --anim pins animationTime, which is a SEPARATE clock; a document may use either.

# browser player, pinned so an animated document is reproducible
# playground.html?agent=1&action=inspect&t=0#doc=<base64url>
```

`--clock` accepts `HH:MM[:SS]`, `YYYY-MM-DD`, `YYYY-MM-DDTHH:MM[:SS]` or `@MILLIS`, and pins
`continuousSec`, seconds, minutes, hour, month, weekday, day of month, day of year and year
together from one instant.

Two things to know when choosing the instant:

* **Pick one that shows the document well.** A scene whose opening phase is empty will be
  captured empty. The instant is part of how the document presents itself; keep it with the
  document.
* **Do not step by a whole multiple of the document's period.** Comparing two instants exactly
  one cycle apart aliases to zero motion and makes a moving document look static. `gate3d.py`
  tries two differently-spaced steps for this reason.

Compare them. **A disagreement between the two players is one of the most valuable things
this programme can produce** — that is how the gradient/shader-clear bug surfaced. Use
`?action=inspect` to get evaluated draw coordinates when "it looks wrong" needs to become a
number.

Count RPN tokens on every expression field here, before a device ever sees it.

### 5. Hand the set to the human — `smart edit`

```sh
/Users/john/code/github/droidkaigi26/tools/jsonViewr/run.sh \
    /Users/john/code/github/RemoteCompose-Examples/work/set-07 &
curl -s localhost:7654/list          # every document with ok / size / error, no browser needed
/Users/john/code/github/droidkaigi26/tools/jsonViewr/where.sh --path   # which one is on screen
```

This is the validation gate that matters. **Compiling is not rendering**: `rcj` will happily
compile a document that draws nothing, draws one colour where eight were wanted, or flings
every shape off-canvas, and report success. The human browses, names a document, we edit, the
window redraws.

Ask `where.sh` which document is on screen. Do not infer it from a filename — there are three
`02_loop.json` across these repos.

### 6. Land it

```sh
python3 tools/rcx.py add work/set-07/*.rc --source rcjson --collection vis-set-07
python3 tools/rcx.py catalog
python3 tools/rcx.py verify
```

Then update `catalog/program-state.json` — set status `landed`, bump the counters, append any
findings. Commit the set as one commit.

Anything load-bearing gets a device run via `rcJson/tools/rcdev.py phone`. **A desktop pass is
not a pass.** If no phone is attached, say so rather than presenting a desktop result as
confirmation.

---

## Pausing and resuming

We will step away from this constantly — to fix an engine bug the programme found, to update
the libraries, to do something else entirely. The design assumes that.

**`catalog/program-state.json` is the only source of truth for where we are.** Read it first,
before the schedule, before this document.

```sh
python3 tools/visplan.py status
```

### The rules that make a pause cheap

1. **A set is atomic.** Nothing enters `docs/` until all 16 pass. If we stop mid-set, the work
   sits in `work/set-NN/` and `setStatus` says `building`. Nothing is half-landed, ever.
2. **Stopping to fix a bug is success, not interruption.** That is goal 1. Record it:
   `pausedFor` gets a one-line reason and the finding id.
3. **Never re-run `visplan.py build` to "refresh" the schedule.** It is deterministic, so it
   would regenerate identically — but if the taxonomy has been edited in between, ids shift
   and already-landed documents no longer match their slots. Edit the taxonomy only between
   sets, and re-run `audit` after.
4. **After a library update, re-validate the last landed set before building a new one.**
   Cheap, and it tells you whether the update changed rendering. Any change there is a
   finding.
5. **Leave the next set unopened.** Resuming should mean reading `status` and starting, not
   reconstructing what past-you intended.

### Returning after a long gap

```sh
python3 tools/visplan.py status          # where we are, what is next, what we paused for
python3 tools/rcx.py verify              # is the corpus still intact
git log --oneline -5                     # what landed last
```

Then re-render the last landed set and compare against what was approved. The engine moves
underneath us; the libraries were a month stale once already.

---

## Findings

The output we actually care about. Each goes in `catalog/program-state.json` under `findings`,
and anything confirmed gets written up in `../remotecompose-notes/ISSUES.md`.

```jsonc
{ "id": "F-012", "set": 7, "document": "BIO-MB-00003",
  "kind": "player-divergence",     // oracle-mismatch | player-divergence | silent-drop |
                                   // device-only | converter-gap | authoring-trap
  "summary": "particlesLoop ignores the emitter rate in the browser player",
  "repro": "work/set-07/BIO-MB-00003.json, rc2image vs browser at t=0",
  "status": "confirmed" }
```

A finding needs a **minimal reproduction**, not the document that happened to expose it.
"19 of 40 documents differ somehow" sat untouched for weeks; "a gradient rect, then
`{\"shader\": 0}` and a solid colour" was fixed the same day.

---

## Fix first

Three things are worth doing before set 1, because they shape everything after it.

1. **`coverage.json` is blind to 3D.** The cataloguer's opcode table has 176 names and not one
   of them is a 3D operation — only `ADD_MESH_2D`, `DRAW_MESH_2D`, `MATRIX_FROM_MESH_2D`.
   Sixteen documents use `drawMesh3D`, `camera3D` and `lights3D` right now and the coverage
   report cannot see any of it. We are about to use coverage to steer a 507-document
   programme, so it needs to see the whole engine.
2. **59 operations have no example at all.** `MACRO_DEFINE`, `FUNCTION_CALL`, `DRAW_BITMAP`,
   `DRAW_TEXT_ON_CIRCLE`, `PATH_COMBINE`, `TEXT_STYLE`, `PARTICLE_LOOP`… Add a standing quota:
   **at least 2 documents per set must exercise a previously-uncovered operation.** The
   backlog drains as a side effect of work we were doing anyway, and these are where bugs
   will be densest — nothing has ever run them.
3. **Decide where generators live.** 369 corpus documents ship their source under `src/`. Keep
   that, and prefer a generator whenever a document has repeated structure: twelve clock ticks
   from a loop beats twelve hand-written draws, and the generator is the thing a reader learns
   from.

---

## Done, and what follows

Pass 1 is done when all 32 sets are landed: every one of the 507 topics has a document, every
subsystem has ~63, every purpose ~84, and all 96 joint cells are occupied. At one set a day
that is about seven working weeks; it will take longer, because fixing what we find is the
point.

Pass 1 gives **breadth** — one document per topic. What it does not give is depth, and three
follow-ons are already visible:

- **Twins.** 2D counterparts for the 3D documents, so constrained devices are not short a
  topic, and so we can measure what the third dimension actually costs.
- **Second passes on dense domains.** Physics has 99 topics and gets 99 documents; a few of
  them deserve three treatments rather than one.
- **The uncovered-operation backlog**, if the per-set quota has not finished it off.

Do not start pass 2 while pass 1 is open. Breadth first: an even catalogue with gaps in depth
is far more useful to an agent than a deep one with holes in the middle.
