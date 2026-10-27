#!/usr/bin/env python3
"""curate - a local UI for tagging and describing documents, one at a time.

    tools/curate.py [--port 8900]   then open http://127.0.0.1:8900/curate.html

A workbench rather than a gallery: one document on screen, its description editable, its
tags one click each, and the next document a keypress away. Rebuilds the catalog and
commits when you are done.

Two deliberate constraints, unchanged from the first version:

  * Bound to 127.0.0.1. This writes entry.json files and runs git commit, so it must not
    be reachable from anywhere else.
  * The page is curate.html in the repo, shared with the published site. It detects
    whether this API is reachable and falls back to read-only when it is not, so
    committing the page does not put dead controls on the public site.

**What is written where.** Only `description` and `tags` in entry.json are touched, and
the file is rewritten key by key so nothing else in it is disturbed - entry.json is the
CURATED half of a document's metadata and `rcx catalog` will not regenerate what is lost.
derived.json is the generated half and is never written here.

**Tags are stored lower-case.** The corpus already holds `3d`, `clock`, `iot` and the
rest in lower case, and a tag that differs only in case is a second facet with a separate
count, not the same one - which looks like data loss from the gallery. The page's labels
are free to be prettier than the stored value.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# A tag is stored as lower-case, no '#', no spaces. Anything the page sends is put through
# this before it reaches disk, so a typed "#3D " and a clicked "3d" are the same tag.
TAG_RE = re.compile(r"[^a-z0-9+_-]+")


def norm_tag(raw: str) -> str:
    t = TAG_RE.sub("-", str(raw).strip().lstrip("#").lower()).strip("-")
    return t[:40]


def entry_paths():
    return sorted(DOCS.glob("*/*/entry.json"))


def read_entry(ep: Path):
    try:
        e = json.loads(ep.read_text())
    except Exception:
        return None
    did = e.get("id") or f"{ep.parent.parent.name}/{ep.parent.name}"
    return {
        "id": did,
        "title": e.get("title") or ep.parent.name,
        "description": e.get("description") or "",
        "tags": sorted({norm_tag(t) for t in (e.get("tags") or []) if norm_tag(t)}),
        "source": e.get("source") or "",
    }


def read_all():
    out = []
    for ep in entry_paths():
        e = read_entry(ep)
        if e:
            out.append(e)
    return out


def vocabulary(docs):
    """Every tag already in use, with its count, so the page can show the whole palette."""
    counts = {}
    for d in docs:
        for t in d["tags"]:
            counts[t] = counts.get(t, 0) + 1
    return counts


def save_doc(did: str, description, tags) -> dict:
    ep = DOCS / did / "entry.json"
    if not ep.exists():
        return {"ok": False, "error": "no such document: %s" % did}
    e = json.loads(ep.read_text())
    if description is not None:
        e["description"] = str(description)
    if tags is not None:
        clean = sorted({norm_tag(t) for t in tags if norm_tag(t)})
        e["tags"] = clean
    ep.write_text(json.dumps(e, indent=2) + "\n")
    return {"ok": True, "tags": e.get("tags", []), "description": e.get("description", "")}


def git_dirty() -> int:
    out = subprocess.run(["git", "status", "--porcelain", "docs"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    return len([l for l in out.splitlines() if l.strip()])


def do_commit(message: str) -> dict:
    """Rebuild the catalog, then commit. Nothing is pushed."""
    cat = subprocess.run([sys.executable, str(ROOT / "tools" / "rcx.py"), "catalog"],
                         cwd=ROOT, capture_output=True, text=True)
    if cat.returncode != 0:
        return {"ok": False, "error": "catalog failed: " + cat.stderr[-300:]}
    subprocess.run(["git", "add", "-A", "docs", "catalog"], cwd=ROOT, capture_output=True)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    if not status:
        return {"ok": False, "error": "nothing to commit"}
    msg = (message or "").strip() or "curate: tags and descriptions"
    c = subprocess.run(["git", "commit", "-m", msg], cwd=ROOT,
                       capture_output=True, text=True)
    if c.returncode != 0:
        return {"ok": False, "error": c.stdout[-300:] or c.stderr[-300:]}
    h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True).stdout.strip()
    return {"ok": True, "commit": h}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/curate", "/curate/"):
            self.send_response(302)
            self.send_header("location", "/curate.html")
            self.end_headers()
            return
        if path == "/api/docs":
            docs = read_all()
            return self._json({"docs": docs, "vocab": vocabulary(docs),
                               "dirty": git_dirty()})
        return super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        n = int(self.headers.get("content-length") or 0)
        try:
            payload = json.loads(self.rfile.read(n) or b"{}") if n else {}
        except Exception:
            return self._json({"ok": False, "error": "bad JSON"}, 400)

        if path == "/api/save":
            r = save_doc(payload.get("id", ""), payload.get("description"),
                         payload.get("tags"))
            r["dirty"] = git_dirty()
            return self._json(r)
        if path == "/api/commit":
            return self._json(do_commit(payload.get("message", "")))
        self.send_error(404)


def main():
    ap = argparse.ArgumentParser(prog="curate", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8900)
    args = ap.parse_args()

    class Server(ThreadingHTTPServer):
        allow_reuse_address = True

    try:
        srv = Server(("127.0.0.1", args.port), Handler)
    except OSError as e:
        print(f"  cannot bind port {args.port}: {e}")
        print(f"  try: tools/curate.py --port {args.port + 1}")
        sys.exit(1)

    docs = read_all()
    vocab = vocabulary(docs)
    untagged = sum(1 for d in docs if not d["tags"])
    nodesc = sum(1 for d in docs if not d["description"].strip())
    print(f"  curate  http://127.0.0.1:{args.port}/curate.html")
    print(f"  {len(docs)} documents, {len(vocab)} tags in use")
    print(f"  {untagged} with no tag, {nodesc} with no description")
    print("  localhost only; it writes entry.json and runs git commit")
    with srv:
        srv.serve_forever()


if __name__ == "__main__":
    main()
