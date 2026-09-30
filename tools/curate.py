#!/usr/bin/env python3
"""curate - a local UI for marking documents #featured.

    tools/curate.py [--port 8900]   then open http://127.0.0.1:8900/curate.html

Marks documents with the `featured` tag, then rebuilds the catalog and commits in one click.
Intended to be run repeatedly as the corpus grows.

Two deliberate constraints:

  * Bound to 127.0.0.1. This writes entry.json files and runs git commit, so it must not be
    reachable from anywhere else.
  * The page is curate.html in the repo, built on the same gallery engine as the explore
    page, so there is one implementation of filtering and the grid. It detects whether this
    API is reachable and falls back to read-only when it is not, which is what the published
    copy does - so committing the page does not put dead controls on the public site.

`featured` is stored in entry.json's `tags`, not written into the description text like the
other hashtags. It is a curation flag rather than a statement about what the document draws,
and `rcx describe` preserves existing tags, so it survives a re-describe.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
TAG = "featured"

# The page itself is curate.html in the repo, shared with the published site and built on the
# same gallery engine as the explore page. This server only supplies the API it calls.
def entries():
    return sorted(DOCS.glob("*/*/entry.json"))


def read_all():
    docs, feat = [], []
    for ep in entries():
        try:
            e = json.loads(ep.read_text())
        except Exception:
            continue
        did = e.get("id") or f"{ep.parent.parent.name}/{ep.parent.name}"
        docs.append({"id": did, "title": e.get("title") or ep.parent.name})
        if TAG in (e.get("tags") or []):
            feat.append(did)
    return docs, feat


def set_featured(did: str, on: bool) -> bool:
    ep = DOCS / did / "entry.json"
    if not ep.exists():
        return False
    e = json.loads(ep.read_text())
    tags = set(e.get("tags") or [])
    tags.add(TAG) if on else tags.discard(TAG)
    e["tags"] = sorted(tags)
    ep.write_text(json.dumps(e, indent=2) + "\n")
    return True


def do_commit() -> dict:
    """Rebuild the catalog, then commit. Nothing is pushed."""
    cat = subprocess.run([sys.executable, str(ROOT / "tools" / "rcx.py"), "catalog"],
                         cwd=ROOT, capture_output=True, text=True)
    if cat.returncode != 0:
        return {"ok": False, "error": "catalog failed: " + cat.stderr[-300:]}
    subprocess.run(["git", "add", "-A"], cwd=ROOT, capture_output=True)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    if not status:
        return {"ok": False, "error": "nothing to commit"}
    c = subprocess.run(["git", "commit", "-m", "featured update"],
                       cwd=ROOT, capture_output=True, text=True)
    if c.returncode != 0:
        return {"ok": False, "error": c.stdout[-300:] or c.stderr[-300:]}
    h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True).stdout.strip()
    _, feat = read_all()
    return {"ok": True, "commit": h, "featured": len(feat)}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
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
        if path == "/api/list":
            docs, feat = read_all()
            return self._json({"docs": docs, "featured": feat})
        return super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        n = int(self.headers.get("content-length") or 0)
        payload = json.loads(self.rfile.read(n) or b"{}") if n else {}
        if path == "/api/toggle":
            ok = set_featured(payload.get("id", ""), bool(payload.get("on")))
            return self._json({"ok": ok})
        if path == "/api/commit":
            return self._json(do_commit())
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
    _, feat = read_all()
    print(f"  curate  http://127.0.0.1:{args.port}/curate.html")
    print(f"  {len(entries())} documents, {len(feat)} currently featured")
    print("  localhost only; it writes entry.json and runs git commit")
    with srv:
        srv.serve_forever()


if __name__ == "__main__":
    main()
