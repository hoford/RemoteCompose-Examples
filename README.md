# RemoteCompose Examples

A browsable corpus of [RemoteCompose](https://developer.android.com/jetpack/androidx/releases/compose-remote)
documents, published as a static GitHub Pages site. Every document is downloadable as compiled
`.rc`, alongside its JSON and generator source where those exist.

Agents: read **[AGENTS.md](AGENTS.md)**. The short version is `catalog/corpus.jsonl`.

## The site ships no thumbnails

Previews are generated **in the browser**. A card fetches the `.rc` it needs anyway, plays one
frame with the TypeScript player, snapshots the canvas, hands the WebGL context back, and caches
the image in IndexedDB.

That is not a micro-optimisation. At ten thousand documents, stored thumbnails would be roughly
120 MB in the repository and would cap preview quality at whatever size was baked in. Rendering
client-side costs nothing extra in the repo, makes preview resolution a choice the *viewer*
makes, and means a second visit costs no network at all.

The `.rc` files themselves are the payload, and most are under 50 KB.

### Preview fidelity has a ceiling

Previews render at the document's **declared** size and the resulting image is scaled down.
Rendering small instead would re-flow the document — `componentWidth`/`componentHeight` change,
so layout, text size and stroke widths are all recomputed for a canvas it was never designed
for, which looks broken rather than merely small.

That fixes clipping, but not everything. The browser player and `rc2image` disagree on roughly
**half** the corpus (19 of a 40-document sample, mean pixel difference over 12). Where they
disagree the thumbnail follows the browser, so some documents will look wrong at any
resolution. `tools/compare_players.py` measures it.

## Querying scales, not just storage

Filtering never touches the documents:

- `catalog/facets.json` — every facet value with a delta+varint postings list of the documents
  that have it. Filtering is set intersection over those lists, so query cost is independent of
  corpus size.
- `catalog/docs-NNN.json` — card metadata in shards of 500, fetched only for the rows about to
  be displayed.
- The grid renders only the visible window, so scrolling costs what is on screen.

Selecting more always narrows. Within a multi-valued facet — API used, Features, Authored in —
values combine with AND, because they are properties a document holds at once: picking
`drawCircle` and `drawPath` gives the 95 documents using both, not the 423 using either.
`Source` is the exception and combines with OR, since a document has exactly one. Each facet
heading says which it is.

Counts are live: every value shows how many documents it would actually yield given what is
already selected, and values that would yield none are greyed and inert. With AND inside a
facet it is otherwise easy to pick a combination nothing satisfies — `shaders` and `particles`
share no document here — and an empty grid does not say whether that is a bug or the answer.

## Full page

A document opens full page from the ⤢ control on its page, the ⤢ action on a card, the `f`
key, or `?full=1` on the URL. Escape leaves it. The mode is a class rather than the Fullscreen
API: the API needs a user gesture and cannot be entered from a link, so it could not be reached
from a card or a shared URL.

## Reading the source

Each document page lists what it was authored from, and those files expand in place rather
than only offering a download. JSON renders as a collapsible tree — objects and arrays past
the top level start closed, and long arrays render a bounded window, because a document's
JSON can run to thousands of nodes. Every file also has its own download button; the compiled
`.rc` is binary, so it is download-only.

Content is fetched on first expand, not with the page.

## Finding your way in

`ops.html` — every operation the engine defines, the documents using it, and the ones with no
example. Each list is ordered smallest-example-first, so the top entry is the least code that
demonstrates the operation. 115 of 176 operations are covered today.

Backed by `catalog/by-op.json` and `catalog/coverage.json`, both derived.

## Curated vs derived

```
docs/<id>/
    doc.rc          the document — always present, the primary artifact
    doc.json        JSON source, when authored that way
    src/*           the .py / .kt that produced it
    entry.json      CURATED — title, description, tags. Never overwritten by a tool.
    derived.json    GENERATED — op histogram, capability tags, sizes. Rebuilt wholesale.
```

This split is what makes the corpus safe to re-catalogue at scale: curation cannot be lost by a
tool run, and derived facts cannot drift from the documents they describe.

IDs are `<collection>/<slug>` — readable, stable across recompiles, and citable. Content hashes
are stored for deduplication but never used as identity.

## Playground

`playground.html` — edit a document's JSON and watch it play. Buttons download the rendered
PNG, the compiled `.rc`, or the JSON. Any document in the corpus that carries JSON can be
loaded into it as a starting point.

Nothing calls a server: `assets/json2rc.js` is the TypeScript converter bundled for the
browser, so the page compiles JSON to wire bytes locally and hands them to the player. It is
the same converter verified byte-identical to `rcj` over the corpus, which is itself verified
against the Java parser — so what the playground compiles is what the toolchain compiles.

## Curating the featured set

```sh
tools/curate.py            # then open http://127.0.0.1:8900/curate
```

`curate.html` is the explore page plus a star on each card and a commit button: star what you
want, then one button rebuilds the catalog and commits as "featured update". Nothing is pushed.

It is the *same page*. Filtering, search, sort, previews and the grid all come from
`assets/gallery.js`, which the explore page uses too — the curation page only adds hooks for an
extra card control and an extra filter predicate. So search and every facet work while curating.

The page is committed and safe to publish. It probes for the local API and falls back to
read-only when it is absent: no stars, no commit button, and a banner saying how to enable
them. In that mode "Featured only" reads the `featured` tag from the catalog, so the published
site still shows the selection. The server binds to 127.0.0.1 only, since it writes
`entry.json` files and runs git.

`featured` lives in `entry.json`'s `tags` rather than in the description text like other
hashtags: it is a curation flag, not a statement about what the document draws. `rcx describe`
preserves existing tags, so it survives a re-describe. On the site it is pinned as the first
filter chip regardless of count — it is deliberately the smallest tag, so ranking it by
document count would bury it.

## Tools

```sh
tools/rcgrep.py --shaders                 # find documents by what they contain
tools/rcgrep.py --3d --unique
tools/rcgrep.py --op 'Particle|Mesh' --root ~/code/github/Origami
tools/rcgrep.py --text 'half4\s+main' --json
```

`rcgrep` searches any tree, not just this corpus, and is how new material gets found. Two
detectors, because one is not enough:

* **Operation search uses the TypeScript reader, not `rc2json`.** `rc2json` keeps its own
  opcode table and fails outright on extension operations — every 3D document is undecodable
  by it — so an op search built on `rc2json` reports zero for exactly the documents you are
  looking for.
* **Shader search is content-based.** A shader is not an operation: its AGSL source travels as
  a text payload, so no opcode reveals it.

Results cache by content hash, so the same document in five checkouts is decoded once.

```sh
tools/rcx.py add <path…> --source NAME [--collection NAME]   # ingest, dedupe, attach sources
tools/rcx.py rm <id>…                                        # remove cleanly
tools/rcx.py catalog                                         # rebuild all derived data
tools/rcx.py verify [--self-test]                            # integrity check
tools/rcx.py serve [--port 8000]                             # preview locally
```

`add` deduplicates by content hash and survives repeated runs. `catalog` is idempotent.
`verify --self-test` breaks the corpus on purpose five ways and asserts each break is caught —
a validator that has never been seen to fail is not evidence of anything.

Cataloguing needs `rc2json` for operation extraction; set `RC2JSON` if it is not at the default
path. Dimensions are parsed natively and do not need it.

## Known limitations

**Some documents cannot be fully decoded** (`derived.json.decoded: false`). They play correctly;
the cataloguing decoder is behind the format. They carry no `apis` and so will not appear under
API filters. Currently 120 of 684.

**`animated` is inferred statically** from the use of expressions, shaders or particles. A
player can answer it exactly at runtime via `CoreDocument.needsRepaint()`.

**Capability tags are a summary.** Several opcodes collapse to one tag. `derived.json.histogram`
has the exact opcodes.
