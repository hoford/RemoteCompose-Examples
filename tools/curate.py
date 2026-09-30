#!/usr/bin/env python3
"""curate - a local UI for marking documents #featured.

    tools/curate.py [--port 8900]   then open http://127.0.0.1:8900/curate

Marks documents with the `featured` tag, then rebuilds the catalog and commits in one click.
Intended to be run repeatedly as the corpus grows.

Two deliberate constraints:

  * Bound to 127.0.0.1. This writes entry.json files and runs git commit, so it must not be
    reachable from anywhere else.
  * The UI is served from this file, not added to the site. Publishing a page whose buttons
    POST to a server that only exists locally would put dead controls on the public site.

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

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Curate — featured</title>
<link rel="stylesheet" href="/assets/app.css">
<script src="/assets/player.js"></script>
<style>
  body { overflow: hidden; }
  .cbar { height: 58px; flex: none; display: flex; align-items: center; gap: 14px;
          padding: 0 18px; background: var(--panel); border-bottom: 1px solid var(--line); }
  .cbar h1 { font-size: 15.5px; margin: 0; }
  .cbar .spacer { flex: 1; }
  .cbar input[type=search] { width: 320px; background: var(--bg); border: 1px solid var(--line);
                             border-radius: 9px; padding: 7px 11px; font-size: 13.5px; }
  .seg { display: flex; border: 1px solid var(--line); border-radius: 9px; overflow: hidden; }
  .seg button { background: none; border: none; padding: 6px 12px; cursor: pointer;
                color: var(--dim); font-size: 13px; }
  .seg button.on { background: var(--accent-soft); color: var(--accent); }
  .commit { background: var(--accent); color: #fff; border: none; border-radius: 9px;
            padding: 8px 14px; cursor: pointer; font-size: 13.5px; font-weight: 600; }
  .commit[disabled] { opacity: .45; cursor: default; }
  .pending { font-size: 12.5px; color: var(--dim); }
  #wrap { flex: 1; overflow-y: auto; padding: 16px; }
  .cgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 14px; }
  .cc { border: 1px solid var(--line); border-radius: 10px; background: var(--panel);
        overflow: hidden; position: relative; }
  .cc.on { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
  .cc .th { height: 140px; background: var(--bg); display: flex; align-items: center;
            justify-content: center; overflow: hidden; }
  .cc .th img { max-width: 100%; max-height: 100%; }
  .cc .nm { padding: 7px 9px; font-size: 12px; white-space: nowrap; overflow: hidden;
            text-overflow: ellipsis; }
  .cc .id { padding: 0 9px 8px; font-size: 10.5px; color: var(--dim);
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .star { position: absolute; top: 7px; right: 7px; width: 30px; height: 30px; border-radius: 50%;
          border: none; cursor: pointer; background: rgba(20,26,36,.7); color: #fff; font-size: 15px; }
  .cc.on .star { background: var(--accent); }
  .cc .open { position: absolute; top: 7px; left: 7px; width: 30px; height: 30px; border-radius: 50%;
              background: rgba(20,26,36,.7); color: #fff; font-size: 12px; line-height: 30px;
              text-align: center; text-decoration: none; }
  .toast { position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%);
           background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
           padding: 10px 16px; font-size: 13px; box-shadow: 0 6px 24px rgba(0,0,0,.18); }
</style></head>
<body>
<div class="cbar">
  <h1>Curate <span class="dim" style="font-weight:400">— featured</span></h1>
  <div class="seg">
    <button id="f-all" class="on">All</button>
    <button id="f-feat">Featured only</button>
  </div>
  <input id="q" type="search" placeholder="Search…" autocomplete="off">
  <span class="pending" id="pending"></span>
  <div class="spacer"></div>
  <a class="pending" href="/index.html" target="_blank">open site ↗</a>
  <button class="commit" id="commit" disabled>Commit “featured update”</button>
</div>
<div id="wrap"><div class="cgrid" id="grid"></div></div>
<script type="module">
import { preview } from '/assets/preview.js';
let all = [], featured = new Set(), dirty = new Set(), mode = 'all', q = '';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

async function load() {
  const r = await (await fetch('/api/list')).json();
  all = r.docs; featured = new Set(r.featured);
  render();
}

function visible() {
  const ql = q.toLowerCase();
  return all.filter(d =>
    (mode === 'all' || featured.has(d.id)) &&
    (!ql || d.id.toLowerCase().includes(ql) || (d.title||'').toLowerCase().includes(ql)));
}

function render() {
  const list = visible().slice(0, 400);
  const g = document.getElementById('grid');
  g.innerHTML = list.map(d => `
    <div class="cc ${featured.has(d.id) ? 'on' : ''}" data-id="${esc(d.id)}">
      <div class="th"><img alt=""></div>
      <a class="open" href="/doc.html?id=${encodeURIComponent(d.id)}&full=1" target="_blank" title="Open">⤢</a>
      <button class="star" title="Toggle featured">${featured.has(d.id) ? '★' : '☆'}</button>
      <div class="nm">${esc(d.title || d.id)}</div>
      <div class="id">${esc(d.id)}</div>
    </div>`).join('');
  g.querySelectorAll('.cc').forEach((el, i) => {
    preview(list[i].id, el.querySelector('img'), 320);
    el.querySelector('.star').onclick = () => toggle(list[i].id, el);
  });
  document.getElementById('pending').textContent =
    `${featured.size} featured` + (dirty.size ? ` · ${dirty.size} unsaved` : '');
  document.getElementById('commit').disabled = dirty.size === 0;
}

async function toggle(id, el) {
  const on = !featured.has(id);
  on ? featured.add(id) : featured.delete(id);
  dirty.add(id);
  el.classList.toggle('on', on);
  el.querySelector('.star').textContent = on ? '★' : '☆';
  await fetch('/api/toggle', { method: 'POST',
    headers: {'content-type':'application/json'}, body: JSON.stringify({ id, on }) });
  document.getElementById('pending').textContent =
    `${featured.size} featured · ${dirty.size} unsaved`;
  document.getElementById('commit').disabled = false;
}

function toast(msg) {
  const t = document.createElement('div');
  t.className = 'toast'; t.textContent = msg; document.body.appendChild(t);
  setTimeout(() => t.remove(), 6000);
}

document.getElementById('commit').onclick = async () => {
  const b = document.getElementById('commit');
  b.disabled = true; b.textContent = 'Committing…';
  const r = await (await fetch('/api/commit', { method: 'POST' })).json();
  b.textContent = 'Commit “featured update”';
  toast(r.ok ? `Committed ${r.commit} — ${r.featured} featured` : `Failed: ${r.error}`);
  if (r.ok) { dirty.clear(); render(); }
};
document.getElementById('f-all').onclick = (e) => {
  mode = 'all'; e.target.classList.add('on');
  document.getElementById('f-feat').classList.remove('on'); render();
};
document.getElementById('f-feat').onclick = (e) => {
  mode = 'feat'; e.target.classList.add('on');
  document.getElementById('f-all').classList.remove('on'); render();
};
let t; document.getElementById('q').oninput = (e) => {
  clearTimeout(t); const v = e.target.value.trim();
  t = setTimeout(() => { q = v; render(); }, 150);
};
load();
</script></body></html>
"""


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
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
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
    print(f"  curate  http://127.0.0.1:{args.port}/curate")
    print(f"  {len(entries())} documents, {len(feat)} currently featured")
    print("  localhost only; it writes entry.json and runs git commit")
    with srv:
        srv.serve_forever()


if __name__ == "__main__":
    main()
