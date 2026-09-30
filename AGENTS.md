# Using this corpus from an agent

Everything here is static and same-origin. There is no API to call and no key to obtain: fetch
the files.

## AI authoring recipe

To create a new RemoteCompose document:

1. Read `catalog/corpus.jsonl`.
2. Find 1–3 similar examples.
3. Fetch their `doc.json` where `jsonReproduces == "yes"` — those are known to rebuild.
4. Modify one of those rather than starting from scratch.
5. Open `playground.html?agent=1#doc=<base64url of your JSON>`.
6. Wait for `status` to reach `ready` in `#agent-output`.
7. If `valid` is false, fix the listed errors — each carries a JSON path — and retry.
8. If `valid` is true, look at `#preview-image`.
9. Iterate until it is visually correct, then take `#download-json` and `#download-rc`.

Check the interface itself first with `playground.html?agent=1&test=1`.

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

The fragment is gzip-aware: base64url of gzipped JSON is detected by its magic bytes, which
keeps long documents inside URL limits.

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
`#preview-image` `#download-json` `#download-rc` `#download-png` `#document-editor`
`#document-status` `#document-width` `#document-height` `#operation-count` `#render-status`
`#document-state`

The three downloads are real `<a download>` links carrying object URLs, so they can be read
and followed straight from the DOM. `#validation-errors` and `#validation-warnings` always
carry text — `(no errors)` when there are none — rather than being hidden.

`#preview-image` is a PNG data URL of exactly what the player is showing, so the rendered
result can be looked at directly.

### Or drive it from JavaScript

```js
const P = window.RemoteComposePlayground;
await P.validate(json);   // { valid, errors, warnings }
await P.inspect(json);    // + width, height, operationCount, operations, features
await P.compile(json);    // Uint8Array of .rc bytes; throws if invalid
await P.render(json);     // full result, preview updated
P.previewPng();           // data:image/png;base64,…
P.shareUrl(json);         // a #doc= URL carrying the document
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
