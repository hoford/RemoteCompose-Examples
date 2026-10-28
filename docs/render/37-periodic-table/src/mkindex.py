#!/usr/bin/env python3
"""Build index.html — a contact sheet of every loading panel with its build status.

Deliberately shows failures as cards rather than omitting them: a document that stopped
compiling should be visible next to the ones that still work, not silently absent.
"""
import glob
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

rows = []
for j in sorted(glob.glob(os.path.join(HERE, "src", "*.json"))):
    name = os.path.basename(j)[:-5]
    rc = os.path.join(HERE, "out", f"{name}.rc")
    png = os.path.join(HERE, "preview", f"{name}.png")
    try:
        doc = json.load(open(j))
        desc = doc.get("header", {}).get("contentDescription", "")
    except Exception as e:
        desc = f"unreadable JSON: {e}"
    rows.append({
        "name": name,
        "desc": desc,
        "png": os.path.relpath(png, HERE) if os.path.exists(png) else None,
        "rc_size": os.path.getsize(rc) if os.path.exists(rc) else None,
        "json_size": os.path.getsize(j),
    })

ok = sum(1 for r in rows if r["rc_size"])
cards = []
for r in rows:
    if r["png"]:
        art = f'<img src="{html.escape(r["png"])}" alt="{html.escape(r["name"])}">'
    elif r["rc_size"]:
        art = '<div class="ph">compiled,<br>no preview</div>'
    else:
        art = '<div class="ph bad">does not<br>compile</div>'
    size = (f'{r["rc_size"]:,} B' if r["rc_size"] else "—")
    cards.append(f"""    <figure class="card{'' if r['rc_size'] else ' failed'}">
      {art}
      <figcaption>
        <b>{html.escape(r["name"])}</b>
        <span class="meta">{html.escape(size)} &middot; json {r["json_size"]:,} B</span>
        <span class="desc">{html.escape(r["desc"])}</span>
      </figcaption>
    </figure>""")

doc = f"""<!doctype html>
<meta charset="utf-8">
<title>Loading panels &middot; {ok}/{len(rows)}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 14px/1.45 system-ui, sans-serif; margin: 0; padding: 24px;
         background: Canvas; color: CanvasText; }}
  h1 {{ font-size: 18px; margin: 0 0 4px; }}
  .sub {{ opacity: .65; margin-bottom: 20px; }}
  .grid {{ display: grid; gap: 18px;
           grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }}
  .card {{ margin: 0; border: 1px solid color-mix(in srgb, CanvasText 18%, transparent);
           border-radius: 10px; overflow: hidden; background:
           color-mix(in srgb, CanvasText 4%, transparent); }}
  .card.failed {{ border-color: color-mix(in srgb, #e5484d 55%, transparent); }}
  .card img {{ display: block; width: 100%; aspect-ratio: 1; object-fit: contain;
               background: #111; }}
  .ph {{ display: grid; place-items: center; aspect-ratio: 1; text-align: center;
         opacity: .55; font-size: 12px; background: color-mix(in srgb, CanvasText 6%, transparent); }}
  .ph.bad {{ color: #e5484d; opacity: .85; }}
  figcaption {{ padding: 9px 11px; display: grid; gap: 2px; }}
  .meta {{ font-size: 11px; opacity: .6; font-variant-numeric: tabular-nums; }}
  .desc {{ font-size: 11px; opacity: .75; }}
</style>
<h1>Loading panels</h1>
<div class="sub">{ok} of {len(rows)} compiled &middot; source in <code>src/</code>,
built documents in <code>out/</code> &middot; rebuild with <code>./build.sh [name]</code></div>
<div class="grid">
{chr(10).join(cards)}
</div>
"""
open(os.path.join(HERE, "index.html"), "w").write(doc)
print(f"  index.html: {ok}/{len(rows)} compiled")
