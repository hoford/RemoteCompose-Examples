#!/usr/bin/env python3
"""rcgrep - find RemoteCompose documents by what they contain.

    rcgrep --shaders                       documents using a shader
    rcgrep --3d                            documents using the 3D API
    rcgrep --op 'Particle|Mesh'            documents with matching operation classes
    rcgrep --text 'half4\\s+main'           documents whose payload text matches
    rcgrep --shaders --root ~/code/github/Origami --json

Why two detectors, and why not just decode everything:

  * Operation search uses the TypeScript reader, not the C++ rc2json. rc2json keeps its own
    opcode table and fails outright on documents using extension operations - every 3D
    document in this corpus is undecodable by it - so an op search built on rc2json silently
    reports zero for exactly the documents being looked for.

  * Shader search is content-based. A shader is not an operation: its AGSL source travels as a
    text payload and is applied through paint, so no opcode reveals it. Searching operation
    names alone finds no shader documents at all.

Results are cached by content hash, so re-running over a large tree is cheap and the same
document appearing in five checkouts is decoded once.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

TS_PLAYER = Path(os.environ.get(
    "TS_PLAYER", "/Users/john/code/github/rcExperiments/players/typescript"))
CACHE = Path(os.environ.get("RCGREP_CACHE", Path.home() / ".cache" / "rcgrep.json"))
BATCH = 150                      # files per node invocation; node startup dominates otherwise

# AGSL/SkSL signatures. Narrow on purpose: "uniform" or "float2" alone occur in ordinary text.
SHADER_RE = re.compile(rb"half4\s+main\s*\(|gl_FragColor|uniform\s+(?:float|half|shader|int)\b")
# Operation classes the 3D API introduces. These are extension operations - they are not in
# upstream Operations.java, which is why the C++ decoder cannot read documents using them.
THREE_D_RE = re.compile(r"3D|Mesh3|MeshPrimitive")

SKIP_DIRS = {".git", "node_modules", ".gradle", "build", ".cxx", "__pycache__", ".idea"}

OPLIST_JS = r"""
import { readFileSync } from 'fs';
const { RemoteComposeBuffer, CoreDocument } = await import(process.argv[2] + '/build-node/node-entry.js');
const out = {};
for (const file of process.argv.slice(3)) {
  try {
    const d = readFileSync(file);
    const doc = new CoreDocument();
    doc.initFromBuffer(RemoteComposeBuffer.fromArrayBuffer(
      d.buffer.slice(d.byteOffset, d.byteOffset + d.byteLength)));
    const names = new Set();
    const walk = (ops, depth) => {
      if (!ops || depth > 8) return;
      for (const o of ops) {
        if (!o) continue;
        names.add((o.constructor && o.constructor.name || 'Unknown').replace(/^_/, ''));
        for (const k of ['mList', 'mOperations', 'mChildren', 'list'])
          if (Array.isArray(o[k])) walk(o[k], depth + 1);
      }
    };
    walk(doc.getOperations(), 0);
    out[file] = { ok: true, ops: [...names] };
  } catch (e) { out[file] = { ok: false, err: String(e && e.message).slice(0, 120) }; }
}
process.stdout.write(JSON.stringify(out));
"""


def load_cache() -> dict:
    try:
        return json.loads(CACHE.read_text())
    except Exception:
        return {}


def save_cache(c: dict) -> None:
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(c))
    except Exception:
        pass


def find_rc(roots: list[Path]) -> list[Path]:
    out = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for f in filenames:
                if f.endswith(".rc"):
                    out.append(Path(dirpath) / f)
    return sorted(out)


def decode_ops(paths: list[Path], cache: dict, quiet: bool) -> dict[str, list[str]]:
    """{sha: [op class names]} for every path, decoding only what is not cached."""
    js = Path("/tmp/_rcgrep_oplist.mjs")
    js.write_text(OPLIST_JS)
    by_sha: dict[str, Path] = {}
    for p in paths:
        by_sha.setdefault(sha_of(p), p)
    todo = [s for s in by_sha if s not in cache]
    if todo and not quiet:
        print(f"  decoding {len(todo)} new document(s) "
              f"({len(by_sha) - len(todo)} cached)...", file=sys.stderr)
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        args = ["node", str(js), str(TS_PLAYER)] + [str(by_sha[s]) for s in chunk]
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=600)
            got = json.loads(r.stdout or "{}")
        except Exception:
            got = {}
        for s in chunk:
            v = got.get(str(by_sha[s]))
            cache[s] = v["ops"] if (v and v.get("ok")) else None
    return {s: cache.get(s) for s in by_sha}


_sha_memo: dict[Path, str] = {}


def sha_of(p: Path) -> str:
    if p not in _sha_memo:
        _sha_memo[p] = hashlib.sha256(p.read_bytes()).hexdigest()
    return _sha_memo[p]


def main():
    ap = argparse.ArgumentParser(prog="rcgrep", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", action="append", default=[],
                    help="tree to search (repeatable; default ~/code)")
    ap.add_argument("--op", help="regex over operation class names")
    ap.add_argument("--text", help="regex over the raw document bytes")
    ap.add_argument("--shaders", action="store_true", help="documents using a shader")
    ap.add_argument("--3d", dest="three_d", action="store_true",
                    help="documents using the 3D API")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--unique", action="store_true",
                    help="one path per distinct document (the same file often sits in several checkouts)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args()

    if not (args.op or args.text or args.shaders or args.three_d):
        ap.error("give one of --shaders, --3d, --op or --text")

    roots = [Path(r).expanduser() for r in (args.root or [Path.home() / "code"])]
    paths = find_rc(roots)
    if not args.quiet:
        print(f"  scanning {len(paths)} .rc files under "
              f"{', '.join(str(r) for r in roots)}", file=sys.stderr)

    # Byte-level tests first: they need no decode at all.
    text_re = re.compile(args.text.encode()) if args.text else None
    hits: list[tuple[Path, list[str]]] = []
    needs_ops = bool(args.op or args.three_d)

    cache = load_cache()
    ops_by_sha = decode_ops(paths, cache, args.quiet) if needs_ops else {}
    if needs_ops:
        save_cache(cache)

    op_re = re.compile(args.op) if args.op else None
    for p in paths:
        why = []
        data = p.read_bytes() if (args.shaders or text_re) else b""
        if args.shaders and SHADER_RE.search(data):
            why.append("shader-source")
        if text_re and text_re.search(data):
            why.append("text")
        if needs_ops:
            ops = ops_by_sha.get(sha_of(p))
            if ops:
                if args.three_d:
                    m = sorted({o for o in ops if THREE_D_RE.search(o)})
                    if m:
                        why.append("3d:" + ",".join(m[:4]))
                if op_re:
                    m = sorted({o for o in ops if op_re.search(o)})
                    if m:
                        why.append("op:" + ",".join(m[:4]))
        if why:
            hits.append((p, why))

    if args.unique:
        seen, uniq = set(), []
        for p, why in hits:
            s = sha_of(p)
            if s not in seen:
                seen.add(s)
                uniq.append((p, why))
        hits = uniq
    if args.limit:
        hits = hits[:args.limit]

    if args.json:
        print(json.dumps([{"path": str(p), "why": w} for p, w in hits], indent=2))
        return

    bydir = defaultdict(list)
    for p, why in hits:
        bydir[str(p.parent)].append((p.name, why))
    for d in sorted(bydir):
        print(f"\n  {d}  ({len(bydir[d])})")
        for name, why in sorted(bydir[d]):
            print(f"      {name:44} {' '.join(why)}")
    distinct = len({sha_of(p) for p, _ in hits})
    print(f"\n  {len(hits)} file(s), {distinct} distinct document(s), "
          f"in {len(bydir)} director{'y' if len(bydir) == 1 else 'ies'}")
    if needs_ops:
        undec = sum(1 for p in paths if ops_by_sha.get(sha_of(p)) is None)
        if undec:
            print(f"  note: {undec} file(s) could not be decoded and were not searched by operation")


if __name__ == "__main__":
    main()
