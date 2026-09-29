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


def parse_header(data: bytes) -> tuple[int, int]:
    """Document width/height, read straight from the bytes.

    Done natively rather than via rc2json for two reasons. rc2json mislabels this op - it
    reports fixed `width`/`height` fields that are really the tag count and the first tag pair,
    so a 1040x700 document comes back as 4x327684. And it cannot decode every document in the
    corpus, whereas the header is the first op in the file and always readable.

    Wire layout (Header.apply, apiLevel >= 7): opcode byte, then MAGIC|MAJOR, MINOR, PATCH and
    a tag count as big-endian ints, then that many entries of
    short(tag | dataType << 10), short(size), payload. INT and FLOAT payloads are 4 bytes;
    a STRING writes size = len + 4 and then len bytes.
    """
    import struct
    try:
        if len(data) < 17 or data[0] != 0:
            return (0, 0)
        magic, _minor, _patch, ntags = struct.unpack_from(">iiii", data, 1)
        if (magic & 0xFFFF0000) != HEADER_MAGIC:
            return (0, 0)
        off = 17
        w = h = 0
        for _ in range(ntags):
            if off + 4 > len(data):
                break
            raw, size = struct.unpack_from(">HH", data, off)
            off += 4
            tag, dtype = raw & 0x3FF, raw >> 10
            if dtype == 3:                       # STRING
                off += max(0, size - 4)
                continue
            if off + 4 > len(data):
                break
            (val,) = struct.unpack_from(">i", data, off)
            off += 8 if dtype == 2 else 4        # LONG is 8 bytes
            if tag == TAG_DOC_WIDTH:
                w = val
            elif tag == TAG_DOC_HEIGHT:
                h = val
        return (w, h)
    except Exception:
        return (0, 0)



def decode(rc_path: Path) -> tuple[list[str], int, int, set[str]] | None:
    """(op names, width, height, content tags) for a compiled document, via rc2json.

    One decode per document, not two. At ten thousand documents a second pass to re-read the
    header would mean twenty thousand subprocess spawns, and rc2json is the slowest step in a
    catalog run by a wide margin.

    Returns None if the document cannot be decoded at all - which is recorded rather than
    treated as fatal, since an undecodable file is still worth reporting.
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
        names = [o["name"] for o in ops if o.get("kind") == "op"]
        w = h = 0
        content = set()
        for o in ops:
            n = o.get("name")
            if n == "HEADER" and not w:
                f = {x["name"]: x["value"] for x in o.get("fields", [])}
                w, h = int(f.get("width", 0)), int(f.get("height", 0))
            # A shader is not an opcode. Its AGSL source is carried as a DATA_TEXT payload and
            # applied through paint, so op names alone can never reveal one - tagging purely
            # from opcodes leaves the "shaders" facet permanently empty while shader documents
            # sit in the corpus. Detect it from the text itself.
            elif n == "DATA_TEXT":
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


# ── Ingest ────────────────────────────────────────────────────────────────────

# AGSL/SkSL signatures. Deliberately narrow: "uniform" or "float2" alone appear in ordinary
# text payloads, so require a construct that only occurs in shader source.
SHADER_RE = re.compile(r"half4\s+main\s*\(|gl_FragColor|uniform\s+(float|half|shader|int)\b")

SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    return SLUG_RE.sub("-", name.lower()).strip("-") or "doc"


SIDECAR_SUFFIXES = (".py", ".kt", ".kts")


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
        for sib in sorted(x for x in parent.iterdir() if x.is_dir()):
            if sib == rc.parent or sib.name.startswith(("preview", "out", "build", "web")):
                continue
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
            "src": sorted(p.name for p in (d / "src").glob("*")) if (d / "src").exists() else [],
        })

    records.sort(key=lambda r: r["id"])
    for i, r in enumerate(records):
        r["i"] = i

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
            "f": r["flags"], "j": r["hasJson"], "d": r["description"],
        } for r in records[s:s + SHARD_SIZE]]
        (CATALOG / f"docs-{s // SHARD_SIZE:03d}.json").write_text(
            json.dumps(shard, separators=(",", ":")) + "\n")

    # The agent-facing dump: one self-contained line per document.
    with (CATALOG / "corpus.jsonl").open("w") as fh:
        for r in records:
            fh.write(json.dumps({
                **{k: v for k, v in r.items() if k != "i"},
                "rc": f"docs/{r['id']}/doc.rc",
                "json": f"docs/{r['id']}/doc.json" if r["hasJson"] else None,
            }, separators=(",", ":")) + "\n")

    shards = (len(records) + SHARD_SIZE - 1) // SHARD_SIZE
    fsize = (CATALOG / "facets.json").stat().st_size
    undec = sum(1 for r in records if not (DOCS / r["id"] / "derived.json").exists())
    print(f"  cataloged {len(records)} documents into {shards} shard(s)")
    print(f"  facets.json {fsize/1024:.1f} KB  "
          f"({sum(len(v) for v in facet_out.values())} distinct facet values)")
    if undec:
        print(f"  WARNING: {undec} documents could not be decoded")


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

    s = sub.add_parser("serve", help="preview the site")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(fn=cmd_serve)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
