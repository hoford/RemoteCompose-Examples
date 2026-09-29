# Using this corpus from an agent

Everything here is static and same-origin. There is no API to call and no key to obtain: fetch
the files.

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
