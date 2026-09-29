#!/usr/bin/env python3
"""rcx - manage the RemoteCompose example corpus.

    rcx add <path...> --source NAME [--collection NAME]   ingest documents
    rcx rm <id>...                                        remove documents
    rcx catalog                                           rebuild all derived data
    rcx verify [--self-test]                              check the corpus is intact
    rcx serve [--port 8000]                               preview the site locally

Two kinds of data live under docs/<id>/, and the difference is the point of the design:

  entry.json    CURATED. Title, description, manual tags. Written once at ingest, edited by
                hand afterwards, and never overwritten by any command here.
  derived.json  GENERATED. Op histogram, capability tags, sizes, dimensions. Thrown away and
                rebuilt wholesale by `catalog`.

That split is what makes re-cataloguing ten thousand documents safe: curation cannot be lost
by a tool run, and derived facts cannot drift from the documents they describe.

The primary artifact is always the .rc. JSON is optional metadata, because a good example whose
JSON no longer compiles is still a good example.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
from collections import Counter
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CATALOG = ROOT / "catalog"
SHARD_SIZE = 500

RC2JSON = os.environ.get(
    "RC2JSON",
    "/Users/john/code/github/rcExperiments/players/cpp/build/tools/rc2json/rc2json",
)

# ── Capability tags ───────────────────────────────────────────────────────────
#
# Raw opcodes are too fine-grained to filter on: nobody looks for DRAW_TEXT_ANCHOR, they look
# for "text". This maps the wire-level op names onto the vocabulary the filter bar exposes.
# Exact names first, then prefixes; an op matching nothing is still recorded in the histogram,
# it just does not become a facet.
API_EXACT = {
    "DRAW_CIRCLE": "drawCircle",
    "DRAW_LINE": "drawLine",
    "DRAW_RECT": "drawRect",
    "DRAW_ROUND_RECT": "drawRoundRect",
    "DRAW_OVAL": "drawOval",
    "DRAW_ARC": "drawArc",
    "DRAW_PATH": "drawPath",
    "DRAW_SECTOR": "drawArc",
    "DRAW_BITMAP": "images",
    "DRAW_BITMAP_INT": "images",
    "DRAW_BITMAP_SCALED": "images",
    "DRAW_TWEEN_PATH": "drawPath",
    "CLIP_PATH": "clip",
    "CLIP_RECT": "clip",
    "MATRIX_ROTATE": "transforms",
    "MATRIX_SCALE": "transforms",
    "MATRIX_TRANSLATE": "transforms",
    "MATRIX_SKEW": "transforms",
    "MATRIX_SAVE": "transforms",
    "MATRIX_FROM_PATH": "transforms",
    "CONDITIONAL_OPERATIONS": "conditionals",
    "ANIMATED_FLOAT": "expressions",
    "FLOAT_EXPRESSION": "expressions",
    "COLOR_EXPRESSIONS": "expressions",
    "TEXT_LOOKUP": "text",
    "TEXT_MERGE": "text",
    "TEXT_FROM_FLOAT": "text",
    "DATA_TEXT": "text",
    "THEME": "theming",
    "HAPTIC_FEEDBACK": "interaction",
}
API_PREFIX = [
    ("DRAW_TEXT", "text"),
    ("TEXT_", "text"),
    ("SHADER", "shaders"),
    ("PAINT_", "paint"),
    ("PARTICLE", "particles"),
    ("MESH_2D", "mesh"),
    ("DRAW_MESH", "mesh"),
    ("ADD_MESH", "mesh"),
    ("MATRIX_FROM_MESH", "mesh"),
    ("LOOP", "loop"),
    ("TOUCH", "interaction"),
    ("CLICK", "interaction"),
    ("ON_", "interaction"),
    ("MODIFIER_", "layout"),
    ("COMPONENT", "layout"),
    ("CONTAINER", "layout"),
    ("LAYOUT", "layout"),
    ("IMPULSE", "animation"),
    ("ANIMATION", "animation"),
    ("PATH_", "drawPath"),
    ("BITMAP", "images"),
    ("CLIP", "clip"),
    ("MATRIX", "transforms"),
]


def api_tags(op_names) -> list[str]:
    out = set()
    for n in op_names:
        if n in API_EXACT:
            out.add(API_EXACT[n])
            continue
        for pre, tag in API_PREFIX:
            if n.startswith(pre):
                out.add(tag)
                break
    return sorted(out)


# ── Reading a .rc ─────────────────────────────────────────────────────────────

HEADER_MAGIC = 0x048C0000
TAG_DOC_WIDTH, TAG_DOC_HEIGHT = 5, 6
TAG_CONTENT_DESCRIPTION = 9


def parse_header_tags(data: bytes) -> dict[int, object]:
    """The header's tag map, decoded from the bytes.

    Done natively rather than via rc2json, which mislabels this op - it reports fixed
    `width`/`height` fields that are really the tag count and the first tag pair, so a
    1040x700 document comes back as 4x327684.

    Wire layout (Header.apply, apiLevel >= 7): opcode byte, then MAGIC|MAJOR, MINOR, PATCH and
    a tag count as big-endian ints, then that many entries of short(tag | dataType << 10),
    short(size), payload.

    The payload is `size` bytes for every type. A STRING writes size = len + 4 because its
    payload is a four-byte length prefix followed by the bytes - so advancing by size - 4
    leaves the cursor four bytes short and every subsequent tag decodes as garbage. That is
    only visible on documents where a string tag precedes the size tags.
    """
    import struct
    out: dict[int, object] = {}
    try:
        if len(data) < 17 or data[0] != 0:
            return out
        magic, _minor, _patch, ntags = struct.unpack_from(">iiii", data, 1)
        if (magic & 0xFFFF0000) != HEADER_MAGIC:
            return out
        off = 17
        for _ in range(ntags):
            if off + 4 > len(data):
                break
            raw, size = struct.unpack_from(">HH", data, off)
            off += 4
            tag, dtype = raw & 0x3FF, raw >> 10
            if off + size > len(data):
                break
            if dtype == 3:                                  # STRING: int length, then bytes
                (ln,) = struct.unpack_from(">i", data, off)
                out[tag] = data[off + 4:off + 4 + max(0, ln)].decode("utf-8", "replace")
            elif dtype == 1:                                # FLOAT
                (out[tag],) = struct.unpack_from(">f", data, off)
            else:
                (out[tag],) = struct.unpack_from(">i", data, off)
            off += size
        return out
    except Exception:
        return out


def parse_header(data: bytes) -> tuple[int, int]:
    """Document width/height. (0, 0) when the header declares neither."""
    t = parse_header_tags(data)
    w = t.get(TAG_DOC_WIDTH); h = t.get(TAG_DOC_HEIGHT)
    return (int(w) if isinstance(w, int) else 0, int(h) if isinstance(h, int) else 0)


def header_description(data: bytes) -> str:
    v = parse_header_tags(data).get(TAG_CONTENT_DESCRIPTION)
    return v.strip() if isinstance(v, str) else ""




def decode(rc_path: Path) -> tuple[list[str], int, int, set[str]] | None:
    """(op names, width, height, content tags) for a compiled document, via rc2json.

    One decode per document: at ten thousand documents a second pass would mean twenty
    thousand subprocess spawns, and rc2json is the slowest step in a catalog run by far.

    Returns None if the document cannot be decoded, which is recorded rather than treated as
    fatal - an undecodable file is still worth reporting.
    """
    if not Path(RC2JSON).exists():
        return None
    tmp = Path("/tmp/_rcx_decode.json")
    try:
        r = subprocess.run([RC2JSON, "rc2json", str(rc_path), str(tmp)],
                           capture_output=True, text=True)
        if r.returncode != 0 or not tmp.exists():
            return None
        d = json.loads(tmp.read_text())
        ops = d["rc"]["ops"]
        # Every entry, not just kind == "op".
        #
        # rc2json emits two kinds. "op" entries are decoded and named in SCREAMING_SNAKE;
        # "opaque" entries are carried through undecoded and named after the C++ class in
        # CamelCase - PathData, RootContentBehavior. Filtering to kind == "op" drops them
        # silently, and the result looks plausible: 147 documents reported DRAW_PATH while
        # DATA_PATH appeared in none, because a path payload is always opaque.
        #
        # Both kinds carry `opcode`, so names resolve through Operations.java rather than from
        # two different conventions. PathData and DATA_PATH are the same opcode 123.
        names = []
        for o in ops:
            if o.get("kind") not in ("op", "opaque"):
                continue
            n = opcode_names().get(o.get("opcode")) or o.get("name")
            if n:
                names.append(n)
        w = h = 0
        content = set()
        for o in ops:
            # A shader is not an opcode. Its AGSL source is carried as a DATA_TEXT payload and
            # applied through paint, so op names alone can never reveal one - tagging purely
            # from opcodes leaves the "shaders" facet permanently empty.
            if o.get("name") == "DATA_TEXT":
                for f in o.get("fields", []):
                    v = f.get("value")
                    if isinstance(v, str) and SHADER_RE.search(v):
                        content.add("shaders")
                        break
        return names, w, h, content
    except Exception:
        return None
    finally:
        tmp.unlink(missing_ok=True)


# ── Descriptions and hashtags ─────────────────────────────────────────────────
#
# Descriptions are CURATED data: `describe` only ever fills in a blank one, never overwrites
# text already there, so hand-editing is safe and re-running is idempotent.
#
# Hashtags live inside the description itself - "#iot #validation" - rather than in a separate
# field, so there is one place to edit and the tag is visible in the text that explains it.
# `catalog` lifts them into the `tag` facet.

# Leading digit allowed: "#3d" is a tag people actually write, and requiring a letter first
# silently made it display as prose while never becoming a tag. A letter must appear somewhere,
# so "#12" is not mistaken for a tag.
HASHTAG_RE = re.compile(r"#([A-Za-z0-9][\w-]{1,30})")

# Descriptions that say nothing. Matched case-insensitively against the whole string; a
# description that merely repeats the document's own name is rejected the same way.
GENERIC = {
    "demo", "demos", "test", "tests", "sample", "samples", "example", "examples",
    "untitled", "document", "rc document", "remote compose", "remotecompose",
    "none", "n/a", "todo", "placeholder", "content description",
}

# Hashtags seeded from the collection a document came from. Deliberately a small explicit
# table rather than something inferred: a wrong auto-tag is worse than a missing one, because
# it makes the filter quietly lie.
COLLECTION_TAGS = {
    "iot-panels": ["iot"], "iot-panels-light": ["iot"],
    "charts3d": ["graph", "3d"], "d3": ["graph"],
    "python-samples": ["python"], "androidx-demos": ["androidx"],
    "games": ["game"], "layout": ["layout"], "events": ["events"],
    "loading-panels": ["loading"], "probes": ["validation"], "probe": ["validation"],
}


def _usable(text: str, slug: str) -> str:
    """A description worth keeping, or ''."""
    t = " ".join((text or "").split())
    if len(t) < 8:
        return ""
    low = t.lower().strip(" .")
    if low in GENERIC:
        return ""
    # "area_chart" as the description of area-chart tells a reader nothing they cannot see.
    if re.sub(r"[^a-z0-9]", "", low) == re.sub(r"[^a-z0-9]", "", slug.lower()):
        return ""
    return t


def _from_json(doc_json: Path) -> tuple[str, str]:
    """(description, where it came from) for the richest prose in a doc.json."""
    try:
        j = json.loads(doc_json.read_text())
    except Exception:
        return "", ""
    if not isinstance(j, dict):
        return "", ""
    cands = []
    for k in ("description", "_comment", "summary", "doc"):
        if isinstance(j.get(k), str):
            cands.append((j[k], f"json:{k}"))
    hdr = j.get("header")
    if isinstance(hdr, dict):
        for k in ("contentDescription", "description", "_comment"):
            if isinstance(hdr.get(k), str):
                cands.append((hdr[k], f"json:header.{k}"))
    # Longest wins: these fields range from a one-word title to a real sentence.
    cands.sort(key=lambda c: -len(c[0]))
    return (cands[0] if cands else ("", ""))


DOCSTRING_RE = re.compile(r'^\s*(?:"""|\x27\x27\x27)(.+?)(?:"""|\x27\x27\x27)', re.S)
KDOC_RE = re.compile(r"^\s*/\*\*(.+?)\*/", re.S)
LINE_COMMENTS_RE = re.compile(r"^\s*(?:#|//)\s?(.*)$")


def _from_source(path: Path) -> str:
    """Leading docstring, KDoc block, or run of line comments from a generator source."""
    try:
        text = path.read_text(errors="replace")
    except Exception:
        return ""
    m = DOCSTRING_RE.search(text) or KDOC_RE.search(text)
    if m:
        body = re.sub(r"^\s*\*\s?", "", m.group(1), flags=re.M)
        return " ".join(body.split())
    out = []
    for line in text.splitlines()[:40]:
        if not line.strip():
            if out:
                break
            continue
        if line.lstrip().startswith("#!"):          # shebang, not prose
            continue
        c = LINE_COMMENTS_RE.match(line)
        if c:
            out.append(c.group(1))
        elif out:
            break
        elif line.lstrip().startswith(("import", "from", "package", "@")):
            continue
        else:
            break
    return " ".join(" ".join(out).split())


def _neighbour_sources(provenance: str, stem: str) -> list[Path]:
    """Generator sources named after this document, near where it came from.

    Exact stem matches only. A looser rule - any .py in the folder - attached rcj's own module
    docstring to 135 unrelated documents, all of them then "described" as a Python
    implementation of RemoteCompose. A description shared by 135 documents describes none of
    them, and unlike a missing description it is not obviously wrong to a reader.
    """
    if not provenance:
        return []
    d = (CODE_ROOT / provenance).parent
    if not d.exists():
        return []
    folders = [d]
    if d.parent.exists():
        try:
            folders += [x for x in d.parent.iterdir() if x.is_dir() and x != d]
        except Exception:
            pass
    out = []
    for folder in folders:
        for suf in (".py", ".kt", ".kts"):
            f = folder / (stem + suf)
            if f.exists():
                out.append(f)
    return out


# ── JSON round-trip ───────────────────────────────────────────────────────────
#
# A doc.json is only useful as a reconstruction source if it actually rebuilds the document.
# That is checked rather than assumed, and the answer is recorded per document so it can be
# filtered on: "show me examples whose JSON I can trust".
#
# Three outcomes, and they mean different things:
#   yes          recompiles byte-identically - the JSON is the document
#   differs      recompiles, but to different bytes - stale, or a different variant
#   unsupported  the compiler cannot read it - a different JSON dialect, or an op it lacks
#
# rcj is optional; without it the field is absent rather than wrong.
RCJ_PATH = os.environ.get("RCJ_PATH", "/Users/john/code/github/rcJson")
_rcj = None


def _load_rcj():
    global _rcj
    if _rcj is None:
        try:
            if RCJ_PATH not in sys.path:
                sys.path.insert(0, RCJ_PATH)
            import rcj as _m
            _rcj = _m
        except Exception:
            _rcj = False
    return _rcj or None


def json_roundtrip(json_path, rc_bytes):
    m = _load_rcj()
    if not m:
        return None
    import contextlib, io
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            out = m.convert_doc(json.loads(json_path.read_text()))
    except Exception:
        return "unsupported"
    return "yes" if out == rc_bytes else "differs"


# ── Ingest ────────────────────────────────────────────────────────────────────

# AGSL/SkSL signatures. Deliberately narrow: "uniform" or "float2" alone appear in ordinary
# text payloads, so require a construct that only occurs in shader source.
SHADER_RE = re.compile(r"half4\s+main\s*\(|gl_FragColor|uniform\s+(float|half|shader|int)\b")

SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    return SLUG_RE.sub("-", name.lower()).strip("-") or "doc"


SIDECAR_SUFFIXES = (".py", ".kt", ".kts")


def _affinity(a: str, b: str) -> int:
    """Shared qualifier tokens between two directory names.

    `out-light` and `src-light` share "light"; `out-light` and `src` share nothing. The first
    token is ignored because it names the role (out/src/rc), not the variant.
    """
    ta = re.split(r"[-_]", a.lower())[1:]
    tb = re.split(r"[-_]", b.lower())[1:]
    return len(set(ta) & set(tb))


def find_sidecars(rc: Path) -> dict[str, Path]:
    """Source files that plausibly produced this document.

    Exact stem matches only. A looser rule (any .py in the folder) attaches one generator to
    fifty documents and makes the 'authoring' facet meaningless.

    Searched in the document's own directory first, then in sibling directories, because this
    corpus keeps compiled output apart from source: `out-light/x.rc` pairs with
    `src-light/x.json`, and `rc/x.rc` with `src/x.json`. Directories holding rendered previews
    are skipped so a .png beside a .json cannot be mistaken for a source file.
    """
    out: dict[str, Path] = {}
    wanted = (".json",) + SIDECAR_SUFFIXES

    def take(d: Path):
        for suf in wanted:
            kind = suf.lstrip(".")
            if kind in out:
                continue
            p = d / (rc.stem + suf)
            if p.exists() and p != rc:
                out[kind] = p

    take(rc.parent)
    parent = rc.parent.parent
    if parent.exists():
        # The parent directory itself, not just its subdirectories: a common layout puts
        # compiled output one level below the source, so samples/output/x.rc pairs with
        # samples/x.json. Checking only sibling directories misses that entirely.
        take(parent)
        # Sibling directories, most-related first. Alphabetical order is actively wrong here:
        # a document in `out-light` finds `src` before `src-light` and silently pairs every
        # light-theme document with its DARK source. The files are the same size and both
        # parse, so nothing complains - it only shows up as a failed round-trip.
        sibs = [x for x in parent.iterdir()
                if x.is_dir() and x != rc.parent
                and not x.name.startswith(("preview", "out", "build", "web"))]
        sibs.sort(key=lambda x: (-_affinity(rc.parent.name, x.name), x.name))
        for sib in sibs:
            take(sib)
    return out


CODE_ROOT = Path(os.environ.get("RCX_CODE_ROOT", Path.home() / "code"))


def shorten(p: Path) -> str:
    """Path relative to the code root when possible, else just the file name."""
    try:
        return str(Path(p).resolve().relative_to(CODE_ROOT.resolve()))
    except Exception:
        return Path(p).name


def cmd_add(args):
    DOCS.mkdir(exist_ok=True)
    # Dedupe index keyed on content hash. Read from entry.json, not derived.json: derived data
    # only exists after `catalog`, so keying on it would re-import the whole sweep on any `add`
    # run that happened before the first catalog.
    seen_hashes = {}
    for e in sorted(DOCS.glob("*/*/entry.json")):
        try:
            h = json.loads(e.read_text()).get("sha256")
            if h:
                seen_hashes[h] = e.parent
        except Exception:
            pass

    candidates: list[Path] = []
    for raw in args.paths:
        p = Path(raw).expanduser()
        if p.is_dir():
            candidates += sorted(p.rglob("*.rc"))
        elif p.suffix == ".rc":
            candidates.append(p)
    # Skip build output and scratch trees: they hold duplicates and half-written files.
    # NOT "/out/" - in this corpus `out/` is where the compiled documents live, so excluding it
    # silently ingests nothing from the largest collections and reports success.
    skip = ("/build/", "/node_modules/", "/.git/", "/dist/", "/.gradle/")
    candidates = [c for c in candidates if not any(s in str(c) for s in skip)]

    added = dupe = bad = 0
    for rc in candidates:
        data = rc.read_bytes()
        if len(data) < 16:
            bad += 1
            continue
        sha = hashlib.sha256(data).hexdigest()
        if sha in seen_hashes:
            dupe += 1
            continue

        collection = args.collection or slugify(rc.parent.name)
        base = slugify(rc.stem)
        did = f"{collection}/{base}"
        n = 2
        while (DOCS / did).exists():
            did = f"{collection}/{base}-{n}"
            n += 1

        dest = DOCS / did
        (dest / "src").mkdir(parents=True, exist_ok=True)
        shutil.copy2(rc, dest / "doc.rc")

        authoring = []
        for kind, path in find_sidecars(rc).items():
            if kind == "json":
                shutil.copy2(path, dest / "doc.json")
                authoring.append("json")
            else:
                shutil.copy2(path, dest / "src" / path.name)
                authoring.append(kind)
        if not any((dest / "src").iterdir()):
            (dest / "src").rmdir()

        entry = {
            "id": did,
            "title": rc.stem.replace("_", " ").replace("-", " ").strip(),
            "description": "",
            "source": args.source,
            "authoring": sorted(set(authoring)),
            "tags": [],
            "sha256": sha,
            # Relative to the code root, not absolute: this file is published, and an absolute
            # path leaks the maintainer's home directory layout onto a public site.
            "provenance": shorten(rc),
        }
        (dest / "entry.json").write_text(json.dumps(entry, indent=2) + "\n")
        seen_hashes[sha] = dest
        added += 1

    print(f"  added {added}, skipped {dupe} duplicate, {bad} unreadable "
          f"(of {len(candidates)} .rc found)")


def cmd_rm(args):
    for did in args.ids:
        d = DOCS / did
        if not d.exists():
            print(f"  no such document: {did}")
            continue
        shutil.rmtree(d)
        parent = d.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
        print(f"  removed {did}")


# ── Catalog ───────────────────────────────────────────────────────────────────

def varint_delta_b64(ids: list[int]) -> str:
    """Sorted ids -> delta + LEB128 varint -> base64.

    Postings dominate the index at scale. Storing them as JSON arrays of integers costs about
    6 bytes per id; delta-varint costs 1 for almost all of them, because ids within a tag are
    dense and ascending.
    """
    out = bytearray()
    prev = 0
    for i in ids:
        v = i - prev
        prev = i
        while v >= 0x80:
            out.append((v & 0x7F) | 0x80)
            v >>= 7
        out.append(v)
    return base64.b64encode(bytes(out)).decode()


def cmd_catalog(args):
    entries = sorted(DOCS.glob("*/*/entry.json"))
    if not entries:
        print("  no documents; nothing to catalog")
        return

    CATALOG.mkdir(exist_ok=True)
    records = []
    for ep in entries:
        d = ep.parent
        did = f"{d.parent.name}/{d.name}"
        entry = json.loads(ep.read_text())
        rc = d / "doc.rc"
        data = rc.read_bytes()

        dec = decode(rc)
        ops = dec[0] if dec else None
        # No fallback to rc2json here. It mislabels the HEADER op (see parse_header), so using
        # it when the native parse finds nothing just substitutes garbage - a document with no
        # size tags was reported as 2 x 917508. Not every document declares DOC_WIDTH and
        # DOC_HEIGHT; for those the honest answer is "unknown", recorded as 0 and rendered as
        # a dash. The player sizes them from their root layout at playback.
        w, h = parse_header(data)
        content = dec[3] if dec else set()
        hist = {}
        for n in ops or []:
            hist[n] = hist.get(n, 0) + 1

        apis = sorted(set(api_tags(hist.keys())) | content)
        flags = []
        if "expressions" in apis:
            flags.append("expressions")
        if "shaders" in apis:
            flags.append("shaders")
        if "particles" in apis:
            flags.append("particles")
        if "mesh" in apis:
            flags.append("mesh")
        # "animated" is asserted by the player at runtime via needsRepaint(); statically we can
        # only say a document *can* animate, which is what an expression or a shader implies.
        if {"expressions", "shaders", "particles"} & set(apis):
            flags.append("animated")

        authoring = list(entry.get("authoring") or [])
        if (d / "doc.json").exists() and "json" not in authoring:
            authoring.append("json")

        derived = {
            "id": did,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "ops": sum(hist.values()),
            "distinctOps": len(hist),
            "width": w,
            "height": h,
            "histogram": hist,
            "apis": apis,
            "flags": sorted(set(flags)),
            "decoded": ops is not None,
            # Mirrored here so the document page needs one fetch, not a directory listing
            # (GitHub Pages serves no index for a directory).
            "hasJson": (d / "doc.json").exists(),
            "jsonReproduces": (json_roundtrip(d / "doc.json", data)
                               if (d / "doc.json").exists() else None),
            "src": sorted(x.name for x in (d / "src").glob("*")) if (d / "src").exists() else [],
        }
        (d / "derived.json").write_text(json.dumps(derived, indent=2) + "\n")

        records.append({
            "id": did,
            "title": entry.get("title") or d.name,
            "description": entry.get("description", ""),
            "source": entry.get("source", "unknown"),
            "authoring": sorted(set(authoring)),
            "apis": apis,
            "flags": derived["flags"],
            "tags": entry.get("tags", []),
            "bytes": len(data),
            "ops": derived["ops"],
            "width": w,
            "height": h,
            "hasJson": (d / "doc.json").exists(),
            "jsonReproduces": derived["jsonReproduces"],
            "_hist": hist,
            "_decoded": ops is not None,
            "src": sorted(p.name for p in (d / "src").glob("*")) if (d / "src").exists() else [],
        })

    records.sort(key=lambda r: r["id"])
    for i, r in enumerate(records):
        r["i"] = i

    write_op_index(records)

    # Facets: tag -> {count, postings}. One file drives the whole filter bar.
    facets: dict[str, dict[str, list[int]]] = {
        "source": {}, "api": {}, "flag": {}, "authoring": {}, "tag": {},
    }

    def push(kind, value, idx):
        facets[kind].setdefault(value, []).append(idx)

    for r in records:
        push("source", r["source"], r["i"])
        for a in r["apis"]:
            push("api", a, r["i"])
        for f in r["flags"]:
            push("flag", f, r["i"])
        for a in r["authoring"]:
            push("authoring", a, r["i"])
        if r.get("jsonReproduces") == "yes":
            push("flag", "json-rebuilds", r["i"])
        for t in r["tags"]:
            push("tag", t, r["i"])

    facet_out = {
        kind: {v: {"n": len(ids), "p": varint_delta_b64(ids)} for v, ids in sorted(vals.items())}
        for kind, vals in facets.items()
    }
    (CATALOG / "facets.json").write_text(
        json.dumps({"total": len(records), "shardSize": SHARD_SIZE, "facets": facet_out},
                   separators=(",", ":")) + "\n")

    # Display shards: only the visible window is fetched, so card cost is independent of corpus
    # size. Field names are short because this is the payload that scales.
    for s in range(0, len(records), SHARD_SIZE):
        shard = [{
            "i": r["i"], "id": r["id"], "t": r["title"], "w": r["width"], "h": r["height"],
            "b": r["bytes"], "o": r["ops"], "s": r["source"], "a": r["authoring"],
            "f": r["flags"], "j": r["hasJson"], "d": r["description"], "g": r["tags"],
        } for r in records[s:s + SHARD_SIZE]]
        (CATALOG / f"docs-{s // SHARD_SIZE:03d}.json").write_text(
            json.dumps(shard, separators=(",", ":")) + "\n")

    # The agent-facing dump: one self-contained line per document.
    with (CATALOG / "corpus.jsonl").open("w") as fh:
        for r in records:
            fh.write(json.dumps({
                # Skip "i" (a shard-local index) and any _private field: the full operation
                # histogram is carried on the record for the coverage pass and would otherwise
                # be duplicated into every line here.
                **{k: v for k, v in r.items() if k != "i" and not k.startswith("_")},
                "rc": f"docs/{r['id']}/doc.rc",
                "json": f"docs/{r['id']}/doc.json" if r["hasJson"] else None,
            }, separators=(",", ":")) + "\n")

    rt = {}
    for r in records:
        if r.get("jsonReproduces"):
            rt[r["jsonReproduces"]] = rt.get(r["jsonReproduces"], 0) + 1
    if rt:
        print("  json round-trip: " + ", ".join(f"{k}={v}" for k, v in sorted(rt.items())))

    shards = (len(records) + SHARD_SIZE - 1) // SHARD_SIZE
    fsize = (CATALOG / "facets.json").stat().st_size
    undec = sum(1 for r in records if not (DOCS / r["id"] / "derived.json").exists())
    print(f"  cataloged {len(records)} documents into {shards} shard(s)")
    print(f"  facets.json {fsize/1024:.1f} KB  "
          f"({sum(len(v) for v in facet_out.values())} distinct facet values)")
    if undec:
        print(f"  WARNING: {undec} documents could not be decoded")



# ── Operation index and coverage ──────────────────────────────────────────────

OPERATIONS_JAVA = os.environ.get(
    "OPERATIONS_JAVA",
    "/Users/john/code/androidx-main3/frameworks/support/compose/remote/remote-core/"
    "src/main/java/androidx/compose/remote/core/Operations.java",
)
OP_CONST_RE = re.compile(r"public static final int ([A-Z0-9_]+)\s*=\s*(-?\d+)")
EXAMPLES_PER_OP = 25


_OPCODE_NAMES = None


def opcode_names() -> dict[int, str]:
    """opcode -> canonical Operations.java name, cached for the run."""
    global _OPCODE_NAMES
    if _OPCODE_NAMES is None:
        _OPCODE_NAMES = {v: k for k, v in known_operations().items()}
    return _OPCODE_NAMES


def known_operations() -> dict[str, int]:
    """Every operation the engine defines, from upstream Operations.java.

    Read from source rather than hardcoded so the coverage report tracks the format as it
    grows; a new opcode upstream shows up as uncovered instead of silently not existing.
    """
    try:
        return {m.group(1): int(m.group(2))
                for m in OP_CONST_RE.finditer(Path(OPERATIONS_JAVA).read_text())}
    except Exception:
        return {}


def write_op_index(records: list[dict]) -> None:
    """catalog/by-op.json and catalog/coverage.json.

    by-op maps each operation to documents that use it, fewest-operations first, so the head
    of each list is the smallest thing that demonstrates it - which is what you want when the
    question is "show me how to use X".

    coverage names the operations with no example at all. That matters in both directions: it
    tells a contributor where to aim, and stops a reader concluding an operation does not
    exist merely because nothing here uses it.
    """
    known = known_operations()
    usage: dict[str, list[tuple[int, str]]] = {}
    undecodable = 0
    for r in records:
        hist = r.get("_hist") or {}
        if not r.get("_decoded"):
            undecodable += 1
            continue
        for op in hist:
            usage.setdefault(op, []).append((r["ops"], r["id"]))

    by_op = {}
    for op, lst in sorted(usage.items()):
        lst.sort()                       # fewest total operations first = simplest example
        by_op[op] = {
            "opcode": known.get(op),
            "documents": len(lst),
            "examples": [i for _, i in lst[:EXAMPLES_PER_OP]],
        }
    (CATALOG / "by-op.json").write_text(json.dumps(by_op, separators=(",", ":")) + "\n")

    seen = set(usage)
    uncovered = sorted(set(known) - seen)
    unknown = sorted(seen - set(known))
    coverage = {
        "knownOperations": len(known),
        "covered": len(seen & set(known)),
        "uncovered": uncovered,
        # Names the decoder emits that are not opcode constants - structural markers rather
        # than operations. Listed so they are not mistaken for undocumented features.
        "notOpcodeConstants": unknown,
        # Operations used by these documents are invisible to this report, so a name listed as
        # uncovered may still have an example among them.
        "undecodableDocuments": undecodable,
        "operationsSource": OPERATIONS_JAVA,
    }
    (CATALOG / "coverage.json").write_text(json.dumps(coverage, indent=2) + "\n")
    if known:
        pct = len(seen & set(known)) / len(known) * 100
        print(f"  operation coverage: {len(seen & set(known))}/{len(known)} ({pct:.0f}%), "
              f"{len(uncovered)} with no example")
    else:
        print("  operation coverage: Operations.java not found, coverage.json is empty")


# ── Verify ────────────────────────────────────────────────────────────────────

def _checks() -> list[tuple[str, bool, str]]:
    out = []
    ids = set()
    for ep in sorted(DOCS.glob("*/*/entry.json")):
        d = ep.parent
        did = f"{d.parent.name}/{d.name}"
        out.append((f"{did}: doc.rc present", (d / "doc.rc").exists(), "missing doc.rc"))
        if (d / "doc.rc").exists():
            out.append((f"{did}: doc.rc non-trivial",
                        (d / "doc.rc").stat().st_size >= 16, "doc.rc too small"))
        out.append((f"{did}: id unique", did not in ids, "duplicate id"))
        ids.add(did)
        try:
            e = json.loads(ep.read_text())
            out.append((f"{did}: entry has source", bool(e.get("source")), "no source"))
        except Exception as ex:
            out.append((f"{did}: entry.json parses", False, str(ex)))

    if (CATALOG / "facets.json").exists():
        f = json.loads((CATALOG / "facets.json").read_text())
        out.append(("catalog total matches disk", f.get("total") == len(ids),
                    f"catalog says {f.get('total')}, disk has {len(ids)}"))
        jl = CATALOG / "corpus.jsonl"
        n = sum(1 for _ in jl.open()) if jl.exists() else -1
        out.append(("corpus.jsonl matches disk", n == len(ids),
                    f"jsonl has {n}, disk has {len(ids)}"))
    else:
        out.append(("catalog exists", False, "run `rcx catalog`"))
    return out


def cmd_verify(args):
    if args.self_test:
        return self_test()
    checks = _checks()
    bad = [c for c in checks if not c[1]]
    print(f"  {len(checks) - len(bad)}/{len(checks)} checks passed")
    for name, _, why in bad:
        print(f"    FAIL  {name}: {why}")
    sys.exit(1 if bad else 0)


def self_test():
    """Break the corpus on purpose and confirm verify notices.

    A validator that has never been seen to fail is not evidence of anything. Each case below
    introduces one real defect, asserts it is caught, and restores the corpus.
    """
    import tempfile
    entries = sorted(DOCS.glob("*/*/entry.json"))
    if not entries:
        print("  self-test needs at least one document")
        sys.exit(2)
    victim = entries[0].parent
    results = []

    def run_case(name, break_fn, restore_fn):
        before = [c for c in _checks() if not c[1]]
        break_fn()
        after = [c for c in _checks() if not c[1]]
        restore_fn()
        restored = [c for c in _checks() if not c[1]]
        caught = len(after) > len(before)
        clean = len(restored) == len(before)
        results.append((name, caught, clean))

    rc = victim / "doc.rc"
    backup = rc.read_bytes()
    run_case("removed doc.rc", lambda: rc.unlink(), lambda: rc.write_bytes(backup))
    run_case("truncated doc.rc",
             lambda: rc.write_bytes(b"\x00\x01"), lambda: rc.write_bytes(backup))

    ep = victim / "entry.json"
    ebak = ep.read_text()
    run_case("entry.json corrupted", lambda: ep.write_text("{not json"),
             lambda: ep.write_text(ebak))
    run_case("entry.json missing source",
             lambda: ep.write_text(json.dumps({"id": "x", "title": "t"})),
             lambda: ep.write_text(ebak))

    fp = CATALOG / "facets.json"
    if fp.exists():
        fbak = fp.read_text()
        def skew():
            d = json.loads(fbak); d["total"] = d.get("total", 0) + 7
            fp.write_text(json.dumps(d))
        run_case("catalog count skewed", skew, lambda: fp.write_text(fbak))

    print("  self-test - each case must be CAUGHT and leave the corpus CLEAN:")
    ok = True
    for name, caught, clean in results:
        flag = "ok " if (caught and clean) else "BAD"
        print(f"    [{flag}] {name:28} caught={caught} restored-clean={clean}")
        ok &= caught and clean
    print("  self-test PASSED" if ok else "  self-test FAILED")
    sys.exit(0 if ok else 1)



def cmd_describe(args):
    """Fill in blank descriptions from whatever source can be found, and seed hashtags.

    Never overwrites an existing description: curation wins, and re-running is safe.
    """
    filled = Counter()
    blank = []
    for ep in sorted(DOCS.glob("*/*/entry.json")):
        d = ep.parent
        entry = json.loads(ep.read_text())
        did = entry.get("id") or f"{d.parent.name}/{d.name}"
        slug = d.name
        collection = d.parent.name

        # Hashtags: keep any already written by hand, add the collection's seeds.
        tags = set(entry.get("tags") or [])
        tags |= {t.lower() for t in HASHTAG_RE.findall(entry.get("description") or "")
                 if re.search(r"[A-Za-z]", t)}
        tags |= set(COLLECTION_TAGS.get(collection, []))

        desc = (entry.get("description") or "").strip()
        prior_src = entry.get("descriptionSource", "")
        if desc and not args.force:
            entry["tags"] = sorted(tags)
            ep.write_text(json.dumps(entry, indent=2) + "\n")
            filled["already had one"] += 1
            continue

        # Best available, in order of how much it is likely to say.
        desc, src = "", ""
        cand, where = _from_json(d / "doc.json") if (d / "doc.json").exists() else ("", "")
        if _usable(cand, slug):
            desc, src = _usable(cand, slug), where
        if not desc:
            for f in sorted((d / "src").glob("*")) if (d / "src").exists() else []:
                t = _usable(_from_source(f), slug)
                if t:
                    desc, src = t, f"src:{f.name}"
                    break
        if not desc:
            t = _usable(header_description((d / "doc.rc").read_bytes()), slug)
            if t:
                desc, src = t, "rc:contentDescription"
        if not desc:
            for f in _neighbour_sources(entry.get("provenance", ""), slug):
                t = _usable(_from_source(f), slug)
                if t:
                    desc, src = t, f"neighbour:{f.name}"
                    break

        if desc:
            entry["description"] = desc
            entry["descriptionSource"] = src
            tags |= {t.lower() for t in HASHTAG_RE.findall(desc) if re.search(r"[A-Za-z]", t)}
            filled[src.split(":")[0]] += 1
        else:
            # Nothing found. Clear a previously DERIVED description - leaving it behind would
            # keep a stale auto-generated line forever with no recorded origin, which is how
            # a wrong blurb survives a re-run that was meant to remove it. A hand-written
            # description has no descriptionSource and is never touched.
            if prior_src:
                entry["description"] = ""
            entry.pop("descriptionSource", None)
            blank.append(did)
            filled["none found"] += 1

        entry["tags"] = sorted(tags)
        ep.write_text(json.dumps(entry, indent=2) + "\n")

    # A description derived from a file not named after the document is a guess. If the same
    # guess lands on many documents it is a module-level blurb, not a description of any of
    # them - drop it. Descriptions carried inside the document (rc:) or in its own JSON are
    # authoritative even when they repeat, so they are left alone.
    SPECULATIVE = ("neighbour", "src")
    REPEAT_LIMIT = 5
    counts = Counter()
    for ep in DOCS.glob("*/*/entry.json"):
        e = json.loads(ep.read_text())
        if (e.get("descriptionSource", "").split(":")[0] in SPECULATIVE) and e.get("description"):
            counts[e["description"]] += 1
    dropped = 0
    for ep in DOCS.glob("*/*/entry.json"):
        e = json.loads(ep.read_text())
        if (e.get("descriptionSource", "").split(":")[0] in SPECULATIVE
                and counts.get(e.get("description", ""), 0) > REPEAT_LIMIT):
            src = e.pop("descriptionSource", "")
            e["description"] = ""
            ep.write_text(json.dumps(e, indent=2) + "\n")
            filled[src.split(":")[0]] -= 1
            filled["none found"] += 1
            blank.append(e["id"])
            dropped += 1
    if dropped:
        print(f"  dropped {dropped} descriptions shared by more than {REPEAT_LIMIT} documents")

    total = sum(filled.values())
    print(f"  {total} documents")
    for k, v in filled.most_common():
        print(f"    {k:22} {v}")
    if blank:
        Path("/tmp/rcx_no_description.txt").write_text("\n".join(blank) + "\n")
        print(f"  {len(blank)} still without a description "
              f"(ids written to /tmp/rcx_no_description.txt)")



def cmd_generators(args):
    """Attach a collection's generator sources to its documents, as illustrative context.

    `add` only attaches sources whose stem matches the document, which is right for a strict
    provenance claim but leaves most collections with nothing: a directory of forty documents
    is usually produced by one make.py, not forty. These are educational - "this is the kind
    of code that produced this" - so they are attached to every document from the same source
    directory and flagged illustrative:true, keeping them distinguishable from an exact match.

    A directory with more than GENERATOR_LIMIT candidate sources is skipped: at that point the
    files are probably a library rather than the thing that generated these documents.
    """
    GENERATOR_LIMIT = 6
    # A file only counts as a generator if it actually builds documents. Proximity alone is
    # not enough: searching by location attached verify.py to 391 documents, verify_samples.py
    # to 141, and two unrelated widget helpers to documents that already carried their exact
    # Kotlin. A verifier sitting beside the generator is not the code that produced anything.
    # Accepted by NAME, not by content.
    #
    # Content is the wrong discriminator here and two attempts proved it. Matching files that
    # mention ".rc" accepted verify.py onto 391 documents, because reading .rc files is what a
    # verifier does. Requiring a creation-API call then rejected the real generators, because
    # several of them emit JSON and never touch that API - charts2d/make.py and
    # surface_plot3d/make.py both build documents without importing anything RemoteCompose.
    #
    # What actually identifies one in this corpus is its name sitting beside the output.
    GENERATOR_NAME = re.compile(
        r"^(make|gen|generate\d*|build|create|emit|mk)[\w-]*$", re.I)

    def is_generator(f: Path) -> bool:
        return bool(GENERATOR_NAME.match(f.stem))

    by_dir: dict[Path, list[Path]] = {}
    attached = coll = 0
    for ep in sorted(DOCS.glob("*/*/entry.json")):
        d = ep.parent
        entry = json.loads(ep.read_text())
        prov = entry.get("provenance") or ""
        if not prov:
            continue
        srcdir = (CODE_ROOT / prov).parent
        if srcdir not in by_dir:
            # Nearest first: the document's own directory, then its parent, then siblings.
            # Compiled documents usually sit in an out/ or rc/ directory with the generator a
            # level up, so searching only the document's directory finds nothing for most
            # collections.
            # Own directory, then parent, then ONLY siblings that are plainly source
            # directories. An arbitrary sibling is a different sample, and taking its
            # generator is actively wrong: architecture3d and shapes3d were both handed
            # charts2d's make.py that way, byte-identical, from next door. But iot-panels
            # keeps its documents in out/ and its generators in the sibling gen/, so siblings
            # cannot be dropped entirely.
            SOURCE_DIRS = {"gen", "src", "source", "sources", "tools", "scripts", "make"}
            places = [srcdir, srcdir.parent]
            if srcdir.parent.exists():
                try:
                    places += [x for x in sorted(srcdir.parent.iterdir())
                               if x.is_dir() and x != srcdir and x.name.lower() in SOURCE_DIRS]
                except Exception:
                    pass
            chosen = []
            for place in places:
                try:
                    cands = sorted([f for suf in ("*.py", "*.kt", "*.kts")
                                    for f in place.glob(suf)]) if place.exists() else []
                except Exception:
                    cands = []
                # Skip a location holding more than the limit: at that size it is a library,
                # and attaching all of it to every document would say nothing about any of them.
                cands = [c for c in cands if is_generator(c)]
                if 0 < len(cands) <= GENERATOR_LIMIT:
                    chosen = cands
                    break
            by_dir[srcdir] = chosen
            if chosen:
                coll += 1
        gens = by_dir[srcdir]
        if not gens:
            continue
        # A document with an exact, stem-matched source already says precisely what produced
        # it; adding neighbouring files can only dilute that.
        if (d / "src").exists() and any(
                f.name not in (entry.get("illustrativeSources") or [])
                for f in (d / "src").glob("*")):
            continue
        existing = {f.name for f in (d / "src").glob("*")} if (d / "src").exists() else set()
        added_here = []
        for g in gens:
            if g.name in existing:
                continue
            (d / "src").mkdir(exist_ok=True)
            shutil.copy2(g, d / "src" / g.name)
            added_here.append(g.name)
        if added_here:
            kinds = {g.suffix.lstrip(".").replace("kts", "kt") for g in gens}
            entry["authoring"] = sorted(set(entry.get("authoring") or []) | kinds)
            entry["illustrativeSources"] = sorted(
                set(entry.get("illustrativeSources") or []) | set(added_here))
            ep.write_text(json.dumps(entry, indent=2) + "\n")
            attached += 1
    print(f"  attached generators to {attached} documents from {coll} source director(y/ies)")


def cmd_serve(args):
    os.chdir(ROOT)
    import http.server, socketserver

    class Server(socketserver.TCPServer):
        allow_reuse_address = True

    try:
        srv = Server(("", args.port), http.server.SimpleHTTPRequestHandler)
    except OSError as e:
        # Worth naming explicitly: a busy port otherwise looks like a broken site, because
        # requests fall through to whatever else is already listening there.
        print(f"  cannot bind port {args.port}: {e}")
        print(f"  something else is already listening. Try: rcx serve --port {args.port + 1}")
        sys.exit(1)
    with srv:
        print(f"  serving {ROOT} at http://localhost:{args.port}/  (ctrl-c to stop)")
        srv.serve_forever()


def main():
    ap = argparse.ArgumentParser(prog="rcx", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="ingest .rc documents")
    a.add_argument("paths", nargs="+")
    a.add_argument("--source", required=True, help="origin repo, e.g. androidx, droidkaigi26")
    a.add_argument("--collection", help="id prefix; defaults to the containing directory name")
    a.set_defaults(fn=cmd_add)

    r = sub.add_parser("rm", help="remove documents")
    r.add_argument("ids", nargs="+")
    r.set_defaults(fn=cmd_rm)

    c = sub.add_parser("catalog", help="rebuild derived data")
    c.set_defaults(fn=cmd_catalog)

    v = sub.add_parser("verify", help="check corpus integrity")
    v.add_argument("--self-test", action="store_true",
                   help="break the corpus on purpose and confirm the checks notice")
    v.set_defaults(fn=cmd_verify)

    de = sub.add_parser("describe", help="fill blank descriptions, seed hashtags")
    de.add_argument("--force", action="store_true",
                    help="re-derive even where a description already exists")
    de.set_defaults(fn=cmd_describe)

    g = sub.add_parser("generators",
                       help="attach collection generator sources as illustrative context")
    g.set_defaults(fn=cmd_generators)

    s = sub.add_parser("serve", help="preview the site")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(fn=cmd_serve)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
