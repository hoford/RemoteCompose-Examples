#!/usr/bin/env python3
"""Compare the browser player against rc2image over a sample of the corpus.

Run with the preview server up:  tools/rcx.py serve --port 8811

How often does the browser player disagree with rc2image on the same document?

Thumbnails are produced by the TypeScript player in the browser. If it renders a document
differently from the reference renderer, no amount of resolution will make the thumbnail
right - so the size of that disagreement is the ceiling on thumbnail quality.
"""
import json, subprocess, glob, base64, io, random
from pathlib import Path
from PIL import Image
import numpy as np

RC2IMAGE = "/Users/john/code/github/rcExperiments/players/cpp/build/tools/rc2image/rc2image"
random.seed(7)
docs = [p for p in sorted(glob.glob("docs/*/*/derived.json"))]
sample = random.sample(docs, 60)
ids = []
for p in sample:
    d = json.load(open(p))
    if d["width"] and d["height"] and max(d["width"], d["height"]) <= 1200:
        ids.append((d["id"], d["width"], d["height"]))
ids = ids[:40]

js = ["<!doctype html><meta charset=utf-8><div id=r>x</div>",
      '<script src="assets/player.js"></script>', '<script type="module">',
      "const out={};",
      f"const list={json.dumps(ids)};",
      """
for (const [id,w,h] of list) {
  try{
    const host=document.createElement('div'); document.body.appendChild(host);
    const p=RC.createPlayer(host,{width:w,height:h});
    const buf=await (await fetch('docs/'+id+'/doc.rc')).arrayBuffer();
    await p.loadFromArrayBuffer(buf); p.player.repaint();
    await new Promise(r=>setTimeout(r,60)); p.player.repaint();
    out[id]=p.canvas.toDataURL('image/png'); p.destroy(); host.remove();
  }catch(e){ out[id]=null; }
}
document.getElementById('r').textContent=JSON.stringify(out);
</script>"""]
Path("_cmp.html").write_text("\n".join(js))

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
out = subprocess.run([CHROME, "--headless=new", "--enable-unsafe-swiftshader",
                      "--window-size=1400,1000", "--virtual-time-budget=120000", "--dump-dom",
                      "http://localhost:8811/_cmp.html"],
                     capture_output=True, text=True, timeout=600).stdout
import re
m = re.search(r'<div id="r">(.*?)</div>', out, re.S)
got = json.loads(m.group(1))

same = diff = failed = 0
worst = []
for did, w, h in ids:
    u = got.get(did)
    if not u:
        failed += 1
        continue
    # Composite onto white before comparing. The TS player leaves the background
    # transparent while rc2image paints it opaque, and .convert("RGB") turns transparent
    # into BLACK - which reports a blank-vs-blank pair as maximally different.
    raw = Image.open(io.BytesIO(base64.b64decode(u.split(",")[1]))).convert("RGBA")
    ts = Image.alpha_composite(Image.new("RGBA", raw.size, (255, 255, 255, 255)), raw).convert("RGB")
    ref_p = "/tmp/_ref.png"
    r = subprocess.run([RC2IMAGE, f"docs/{did}/doc.rc", ref_p, "--time", "0"],
                       capture_output=True)
    if r.returncode != 0:
        failed += 1
        continue
    ref = Image.open(ref_p).convert("RGB")
    if ref.size != ts.size:
        ref = ref.resize(ts.size)
    d = np.abs(np.array(ts).astype(int) - np.array(ref).astype(int)).mean()
    if d > 12:
        diff += 1
        worst.append((d, did))
    else:
        same += 1
worst.sort(reverse=True)
print(f"  compared {same+diff} documents (browser player vs rc2image)")
print(f"    close      : {same}")
print(f"    disagree   : {diff}")
print(f"    could not  : {failed}")
for d, i in worst[:8]:
    print(f"      mean diff {d:6.1f}  {i}")
