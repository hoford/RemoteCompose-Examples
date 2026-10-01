# Using this corpus from an agent

Everything here is static and same-origin. There is no API to call and no key to obtain: fetch
the files.

## AI authoring recipe

To create a new RemoteCompose document:

1. Read `catalog/schema.json` — what exists, and the four argument-order traps.
2. Read `catalog/by-command.json` and find 1–3 examples using the commands you need.
3. Fetch their `doc.json` where `jsonReproduces == "yes"` — those are known to rebuild.
4. Modify one of those rather than starting from scratch.
5. Open `playground.html?agent=1#doc=<base64url of your JSON>`.
6. Wait for `status` to reach `ready` in `#agent-output`.
7. If `valid` is false, fix the listed errors — each carries a JSON path — and retry.
8. If `valid` is true, look at `#preview-image`, and read `warnings`: a silently dropped key
   leaves `valid` true while the document quietly does less than you asked.
9. Iterate until it is visually correct, then take `#download-json` and `#download-rc`.

Check the interface itself first with `playground.html?agent=1&test=1`. If you cannot run
scripts in a page, use `node tools/rc.mjs validate` instead — same converter, same verdicts.

## Start here

`catalog/corpus.jsonl` — one JSON object per line, one line per document. This is the file to
read if you want to search the corpus.

```jsonc
{
  "id": "iot-panels/01-smart-bulb",
  "title": "01 smart bulb",
  "description": "",
  "source": "rcjson",              // origin collection
  "authoring": ["json"],           // what produced it: json | py | kt
  "apis": ["drawCircle", "expressions", "layout", "paint", "text"],
  "flags": ["animated", "expressions"],
  "tags": ["iot", "widget"],       // hashtags, from #tags written in the description
  "bytes": 1938,
  "ops": 214,                      // total operations
  "width": 360, "height": 360,
  "hasJson": true,
  "jsonReproduces": "yes",         // yes | differs | unsupported | null
  "src": [],                       // generator sources, if any
  "rc": "docs/iot-panels/01-smart-bulb/doc.rc",
  "json": "docs/iot-panels/01-smart-bulb/doc.json"
}
```

The site's filter combines multiple `apis` values with AND. `apis` is the field to filter on. It is **derived from the compiled document**, not written by
hand, so it cannot drift from what the document actually does.

## Descriptions and hashtags

`description` is prose about what the document draws. `descriptionSource` records where it came
from, which is also a quality signal:

| source | meaning |
| :--- | :--- |
| `json:…` | taken from the document's own JSON — authoritative |
| `rc:contentDescription` | embedded in the compiled document itself — authoritative |
| `rendered` | written by looking at the rendered output, because no source had one |
| absent | hand-written |

Hashtags are written **inside the description** — `"… #iot #widget"` — and lifted into `tags`
during catalog, so there is one place to edit and the tag sits next to the text explaining it.
Filter on them with the `tag` facet.

## Finding an example of a specific operation

`catalog/by-op.json` maps every operation to documents that use it:

```jsonc
{ "DRAW_ARC": { "opcode": 62, "documents": 86,
                "examples": ["render/a-donut-chart-…", "…"] } }
```

Examples are ordered **fewest operations first**, so `examples[0]` is the smallest document
that demonstrates the operation — usually what you want when the question is "how do I use X".

`catalog/coverage.json` lists operations with no example at all, which is how you tell "this
corpus has no example" apart from "this operation does not exist". Both are browsable at
`ops.html`.

`by-op.json` is keyed on **wire opcodes** — `DRAW_ARC`, `DATA_PATH` — which is the wrong end
if you are writing JSON, because nothing you type is spelled that way. `catalog/by-command.json`
is keyed on **what you actually write**:

```jsonc
{ "loop": { "documents": 223, "examples": ["…", "…"] },
  "conditionalOperations": { "documents": 29, "examples": ["…"] },
  "textFromFloat": { "documents": 6, "examples": ["…"] } }
```

438 keys, 124 KB — fetch it instead of the 537 KB `corpus.jsonl` when the question is "show me
a document that uses X".

## The JSON surface — catalog/schema.json

Generated from the converter's own tables by `tools/mkschema.py`, so it cannot drift from what
is actually accepted: 62 commands, 43 expression functions, 107 system variables, the four
argument-order traps, and the cost model. Fetch it before authoring; it is the only complete
list that is not the minified bundle.

### Pick one dialect and stay in it

Several spellings are accepted, which is why corpus documents disagree with each other. The
form below is the one to generate — not because the others fail, but because mixing them is
how an author ends up debugging a difference that was never the problem:

| | Write this | Not this |
|---|---|---|
| root | an object — `"root": { "canvas": … }` | a list of components |
| command | keyed by name — `{ "drawCircle": {…} }` | `{ "type": "drawCircle", … }` |
| paint | `{ "paint": { "ops": [ {"color": …}, {"style": …} ] } }` | direct keys on the paint object |

In this corpus the object root outnumbers the list root 256 to 237, and 332 documents use
`paint.ops` against 154 using direct keys. 21 are additionally wrapped in
`{name, description, json}`; that wrapper is unwrapped automatically, so keep it or drop it.

**The paint row is not a style preference.** The two forms differ in what they accept and in
how they fail:

| | `paint: { ops: [ … ] }` | `paint: { … }` direct |
|---|---|---|
| properties | all 11, including `alpha`, `linearGradient`, `pathEffect` | 8 — those three are rejected |
| applied | in the order you wrote them | in a fixed internal order, whatever you wrote |
| unknown key | **raises** — you find out at once | **compiles and is silently dropped** |

So the direct form can quietly ignore `antiAlias`, `typeface`, `fontWeight`, `blendMode` or a
typo like `styl`, while still reporting `valid: true`. In the `ops` form the same key is an
error. Use `ops` and that whole class of bug becomes impossible; the playground warns
(`PG2030`, with a did-you-mean) if you use the direct form anyway.

`strokeWidth` and `runtimeShader` are accepted spellings of `width` and `shader` in both forms.

### What it will not do

Four of these cost a redesign if you find them late, so they are worth reading before you start
rather than after:

* **`textMerge`** — no data-driven text composition. Labels are literals; a number next to a
  label is `textFromFloat` as a separate draw.
* **AGSL/SkSL shader source in JSON** — the shader documents in this corpus carry their source
  in `DATA_TEXT`, placed by a different tool.
* **Themed (light/dark pair) colours on canvas paint.**
* **`typeface`, `fontWeight`, `fontStyle` on canvas paint** — text size is settable, the face
  is not. In the direct-key form these vanish silently; in `ops` they raise.

Note what is *not* on that list. `alpha`, `linearGradient` and `pathEffect` all work — in the
`ops` form. As direct keys they are rejected, with an error that tells you to move them into an
`ops` array. Opacity and gradients are available; only the direct spelling of them is not.

`antiAlias`, `blendMode` and `colorFilter` are the reverse trap: no form implements them, and
the direct form drops them without a word.

## Without a browser — tools/rc.mjs

The playground needs a page that can run scripts. An agent that can only fetch URLs cannot use
it at all, because a `#doc=` fragment is never sent to a server. `tools/rc.mjs` gives that agent
the same loop from the same bundled converter, so the two cannot disagree:

```
node tools/rc.mjs validate docs/render/bar-vertical/doc.json
node tools/rc.mjs compile  mydoc.json out.rc
node tools/rc.mjs inspect  mydoc.json
node tools/rc.mjs encode   mydoc.json     # a gzipped #doc= fragment
```

Node only, no `npm install` — the browser bundle is run in a `vm` context. Validation takes
about 25 ms and `compile` is byte-identical to the committed `.rc`. Exit status is 0 for valid
and 1 for invalid, so it drops straight into a shell loop.

`encode` gzips before base64url because uncompressed fragments get long. Over 40 sampled corpus
documents the fragment comes out at 7–51% of the plain base64 length — a median of 14%, and the
bigger the document the better it does, because RemoteCompose JSON is highly repetitive. The
playground sniffs the gzip magic bytes, so both forms load from `#doc=`.

## Authoring and checking a document — playground.html

`playground.html` is a machine interface as well as a human one. It compiles, validates and
renders entirely in the browser, so a web AI can author RemoteCompose with no install, no
shell and no server.

### Check the interface first

```
playground.html?agent=1&test=1
```

Loads a small built-in document, validates, renders and reports:

```jsonc
{ "status": "ready", "valid": true, "test": "agent-interface", "result": "pass",
  "rendered": true, "previewAvailable": true, "errors": [], "warnings": [] }
```

`"result": "pass"` means the whole path worked — not merely that the document compiled, but
that it rendered and produced a preview. The test document uses no clock, no randomness, no
network and no external font, so it gives the same answer every run.

### Give it a document

| URL | meaning |
| :--- | :--- |
| `playground.html#doc=<base64url>` | document inline in the fragment — **no CORS, always works** |
| `playground.html#doc=<uri-encoded-json>` | same, plainer encoding |
| `playground.html?src=<URL>` | fetch a document (the source must send CORS headers) |
| `?agent=1` | machine-oriented view; the engine is identical |
| `?action=validate` | parse, validate, do not render |
| `?action=render` | validate and render (the default) |
| `?action=inspect` | validate and report structure |
| `?t=<seconds>` | render at a fixed document time instead of live |
| `?geometry=1` | also report evaluated draw coordinates (implied by `action=inspect`) |

The fragment is gzip-aware: base64url of gzipped JSON is detected by its magic bytes, which
keeps long documents inside URL limits. `node tools/rc.mjs encode` produces one.

**`?t=` is what makes an animated document reviewable.** Without it the preview is captured at
whatever moment the render finished, so a document that moves gives a different image every run
and you cannot tell a fix from noise. `?t=0` is the first frame; `?t=2.5` is two and a half
seconds in. The pin reaches all three places a frame reads time from, so `continuousSec()`,
`timeInSec()`, `animationTime` and anything derived from them agree within the frame, and the
same `?t=` gives byte-identical PNGs across runs.

Two limits worth knowing. `continuousSec()` is minute·60 + second *within the hour*, so `?t=`
wraps at 3600 — `?t=3601` renders as `?t=1`. And the result echoes back `pinnedAtSeconds`: if
that is `null` the pin did not take and the frame is live, so do not treat the image as
reproducible. Capture two or three times to review an animation rather than once.

### Read the result

Everything is ordinary visible text under `<main id="agent-interface">` — headed STATUS,
VALIDATION, DOCUMENT, PREVIEW, DOWNLOADS. Nothing that matters is hidden, console-only, or
reachable only by running script.

The result lands in one element with a stable id:

```html
<pre id="agent-output">{ … }</pre>
```

```jsonc
{
  "status": "ready",              // loading|parsing|validating|compiling|rendering|ready|error
  "valid": true,
  "width": 300, "height": 300,
  "operationCount": 3,
  "operations": { "canvas": 1, "paint": 1, "drawCircle": 1 },
  "features": ["animation", "expressions"],
  "bytes": 122,                   // size of the compiled .rc
  "errors": [], "warnings": [],
  "previewImage": "#preview-image (4898 chars, image/png)",
  "source": "inline",             // inline | src | test | editor
  "rendered": true,
  "previewAvailable": true,
  "downloads": { "json": true, "rc": true, "png": true }
}
```

`status` reaches **`ready`** whenever the document was read, whether or not it validated —
check `valid`. `status: "error"` means the document could not be obtained or decoded at all
(a failed fetch, an undecodable fragment), so there is nothing to be valid or invalid about.

Wait for `status: "ready"` or `"error"` — or listen for the event, which fires only after
load, validation, render and `#agent-output` are all current:

```js
window.addEventListener('remotecompose-ready', (e) => { e.detail; /* same object */ });
```

Errors carry a code, a JSON path and, where the converter named one, the operation:

```jsonc
{ "code": "PG1030", "path": "root.canvas.commands[0]",
  "operation": "totallyMadeUpCommand", "message": "canvas command '…' is not supported" }
```

`PG1xxx` are errors, `PG2xxx` warnings. They are **this page's codes**, not an upstream
RemoteCompose registry.

### Stable ids

`#agent-interface` `#agent-output` `#validation-errors` `#validation-warnings`
`#preview-image` `#geometry` `#download-json` `#download-rc` `#download-png` `#document-editor`
`#document-status` `#document-width` `#document-height` `#operation-count` `#render-status`
`#document-state`

The three downloads are real `<a download>` links carrying object URLs, so they can be read
and followed straight from the DOM. `#validation-errors` and `#validation-warnings` always
carry text — `(no errors)` when there are none — rather than being hidden.

`#preview-image` is a PNG data URL of exactly what the player is showing, so the rendered
result can be looked at directly.

### Geometry — where it actually put things

A PNG answers "does this look right". It cannot answer "where did it put things", and that is
the question when a loop draws twelve bars and two land on top of each other: the image shows
ten bars and says nothing about why. `?action=inspect` (or `?geometry=1` alongside any action)
adds the coordinates the player received:

```jsonc
{ "op": "drawRect", "args": { "left": 76, "top": 124, "right": 116, "bottom": 180 },
  "device": { "x": 76, "y": 124 },
  "extent": { "left": 76, "top": 124, "right": 116, "bottom": 180 } }
{ "op": "text", "text": "5 bars", "args": { "x": 134.99, "y": 36.3 },
  "measured": { "width": 50.03, "ascent": 12.96, "descent": 0.36 } }
```

These are **evaluated** values, read where every draw passes through the paint context. A
`"left": "20 + i * 56"` in your JSON comes back as 20, 76, 132, 188, 244 — one record per loop
iteration, which is what makes a loop debuggable. `device` is the same point after the current
matrix, so a draw inside a `rotate` or `translate` reports where it actually landed. Text is
read lower still, at `fillText`, so the string is the real one and `measured` comes from the
browser's own text metrics rather than an estimate.

`extent` is the drawn box, not the anchor. `bounds` in the summary unions every draw, so
comparing it against the document's own width and height tells you whether something is being
drawn off-canvas — a common cause of "my chart is missing a bar".

A summary (`drawCount`, `bounds`, `truncated`) goes in `#agent-output`; the full list is in
`#geometry`, split so 500 draws of JSON do not bury the status. The list caps at 500 and says
so in `truncated` and `note` when it does — `bounds` still covers everything. Pair it with
`?t=` for an animated document, or the numbers are whatever instant the frame landed on;
`recordedAtSeconds` reports what was pinned.

### Or drive it from JavaScript

```js
const P = window.RemoteComposePlayground;
await P.validate(json);   // { valid, errors, warnings }
await P.inspect(json);    // + width, height, operationCount, operations, features
await P.compile(json);    // Uint8Array of .rc bytes; throws if invalid
await P.render(json);     // full result, preview updated
await P.geometry(json, 0) // evaluated draw coordinates at t=0 seconds
P.previewPng();           // data:image/png;base64,…
await P.shareUrl(json);   // a #doc= URL carrying the document, gzipped
```

These call the same pipeline the editor uses — there is no second implementation to drift.

### Worth knowing

**Compiling is the validation.** The converter refuses anything outside the implemented
surface rather than guessing, so `valid: true` means the bytes exist and the player loaded
them. It is not a promise that the document looks right — check `#preview-image`.

**A document that compiles can still draw nothing.** `operationCount: 0` and a blank preview
are the signals.

## Searching beyond the corpus

`tools/rcgrep.py` finds documents by content across any tree — `--shaders`, `--3d`,
`--op REGEX`, `--text REGEX`, `--json`. Use it to answer "is there an example of X anywhere"
before concluding the corpus has none.

## Per document

| path | contents |
| :--- | :--- |
| `docs/<id>/doc.rc` | the compiled document — always present |
| `docs/<id>/doc.json` | JSON source, when the document was authored that way |
| `docs/<id>/src/*` | the `.py` / `.kt` that generated it, when known |
| `docs/<id>/entry.json` | curated: title, description, tags, provenance |
| `docs/<id>/derived.json` | generated: full op histogram, sizes, dimensions |

`derived.json` carries the complete operation histogram, which is more precise than the `apis`
summary when you need to know exactly which opcodes a document uses.

## Caveats worth knowing

**`apis` is a capability summary, not an opcode list.** Several opcodes map to one tag —
`DRAW_TEXT_ANCHOR`, `TEXT_MERGE` and `DATA_TEXT` all become `text`. Read
`derived.json.histogram` for exact opcodes.

**`shaders` is detected from content, not opcodes.** A shader is carried as AGSL source inside a
`DATA_TEXT` payload and applied through paint; there is no shader opcode to look for. Tagging
purely from opcode names finds no shader documents at all.

**Coverage is measured only over decodable documents.** `coverage.uncovered` may overstate
what is missing, because operations used solely by the documents in `undecodableDocuments`
are invisible to it.

**Some documents cannot be fully decoded.** `derived.json.decoded` is `false` for those, and
their histogram is empty, so they carry no `apis`. They are still valid documents that play
correctly — the decoder used for cataloguing is simply behind the format. Dimensions are still
correct for them, being read from the header directly.

**`jsonReproduces` tells you whether the JSON is trustworthy as a source.** `yes` means it
recompiles to byte-identical output, so it genuinely reconstructs the document — filter on the
`json-rebuilds` flag to get only those (421 of 1023 today). `unsupported` means the reference
compiler cannot read it: 141 of those are Origami's `pythonRcCreation` dialect, which uses
`header`/`ops` rather than `root`, and needs that project's own compiler. `differs` means the
JSON is stale or belongs to a different variant of the document.

**`animated` is a static inference**, true when a document uses expressions, shaders or
particles. A player can answer this exactly at runtime via `CoreDocument.needsRepaint()`.
