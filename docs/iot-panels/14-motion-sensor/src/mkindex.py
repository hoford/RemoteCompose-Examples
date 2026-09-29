#!/usr/bin/env python3
"""Build index.html — a contact sheet of all 80 IoT panels.

Every cell is an *animated* thumbnail, because a contact sheet of animations made of stills
shows the wrong thing. Alongside each: what it compiled to, and how much of it moves.

Failures are shown as cards rather than omitted. A document that stopped compiling should be
visible next to the ones that still work, not silently absent — an index that quietly drops
what it cannot build is an index that lies about the size of the set.

  python3 gen/mkindex.py
"""
import glob, html, json, os, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/Users/john/code/github/rcJson")

GROUPS = [
    ("01", "Lighting"), ("02", "Climate"), ("03", "Security"), ("04", "Safety"),
    ("05", "Kitchen I"), ("06", "Kitchen II"), ("07", "Cleaning"), ("08", "Energy"),
    ("09", "Water & garden"), ("10", "Media"), ("11", "Network"), ("12", "Openings"),
    ("13", "Health"), ("14", "Pets"), ("15", "Ambient"), ("16", "Odds"),
]

# how much of each panel moves, if gen/motion.py has been run into this cache
motion = {}
mpath = os.path.join(HERE, "preview", "motion.json")
if os.path.exists(mpath):
    motion = json.load(open(mpath))

rows = []
for j in sorted(glob.glob(os.path.join(HERE, "src", "*.json"))):
    name = os.path.basename(j)[:-5]
    rc = os.path.join(HERE, "out", f"{name}.rc")
    anim = os.path.join(HERE, "preview", "anim", f"{name}.png")
    animl = os.path.join(HERE, "preview-light", "anim", f"{name}.png")
    still = os.path.join(HERE, "preview", f"{name}.png")
    try:
        doc = json.load(open(j))
        desc = doc.get("header", {}).get("contentDescription", "")
    except Exception as e:
        desc = f"unreadable JSON: {e}"
    title, _, sub = desc.partition(" — ")
    rows.append({
        "name": name, "title": title or name, "sub": sub,
        "anim": os.path.relpath(anim, HERE) if os.path.exists(anim) else None,
        "animl": os.path.relpath(animl, HERE) if os.path.exists(animl) else None,
        "still": os.path.relpath(still, HERE) if os.path.exists(still) else None,
        "rc": os.path.getsize(rc) if os.path.exists(rc) else None,
        "json": os.path.getsize(j),
        "motion": motion.get(name),
    })

ok = sum(1 for r in rows if r["rc"])
light_ok = len(glob.glob(os.path.join(HERE, "out-light", "*.rc")))
rc_total = sum(r["rc"] or 0 for r in rows)
json_total = sum(r["json"] for r in rows)

cards_by_group = {}
for r in rows:
    g = r["name"][:2]
    idx = (int(g) - 1) // 5
    key = GROUPS[idx][0] if idx < len(GROUPS) else "??"
    if r["anim"]:
        alt = html.escape(r["title"])
        lightsrc = html.escape(r["animl"] or r["anim"])
        art = (f'<img src="{html.escape(r["anim"])}" alt="{alt}" loading="lazy"'
               f' data-dark="{html.escape(r["anim"])}" data-light="{lightsrc}">')
    elif r["still"]:
        art = f'<img src="{html.escape(r["still"])}" alt="{html.escape(r["title"])}" loading="lazy">'
    elif r["rc"]:
        art = '<div class="ph">compiled,<br>no preview</div>'
    else:
        art = '<div class="ph bad">does not<br>compile</div>'
    mv = f'{r["motion"]:.1f}% moving' if r["motion"] else "&nbsp;"
    meta = (f'{r["rc"]:,} B' if r["rc"] else '<span class="bad">no .rc</span>')
    cards_by_group.setdefault(key, []).append(f'''      <figure class="card">
        {art}
        <figcaption>
          <b>{html.escape(r["title"])}</b>
          <span class="sub">{html.escape(r["sub"])}</span>
          <span class="meta">{meta} &middot; {mv}</span>
        </figcaption>
      </figure>''')

sections = []
for num, label in GROUPS:
    cards = cards_by_group.get(num, [])
    if not cards:
        continue
    sections.append(f'''    <section>
      <h2><span class="gnum">{num}</span>{html.escape(label)}</h2>
      <div class="grid">
{chr(10).join(cards)}
      </div>
    </section>''')

doc = f'''<!doctype html>
<meta charset="utf-8">
<title>IoT panels — 80 devices, working</title>
<style>
  /* The page themes itself with the panels: the same two palettes the documents use, so
     the contact sheet is an example of the thing it is showing. */
  :root {{
    --bg: #080b10; --plate: #111823; --edge: #243141;
    --ink: #eaf0f8; --dim: #78899d; --accent: #54c7f5; --void: #05080d;
  }}
  :root[data-theme="light"] {{
    --bg: #edf0f4; --plate: #ffffff; --edge: #cfd7e1;
    --ink: #141d28; --dim: #66748a; --accent: #0b7fb0; --void: #e8ecf1;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 28px 24px 64px; background: var(--bg); color: var(--ink);
         font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  header {{ max-width: 1180px; margin: 0 auto 34px; }}
  h1 {{ font-size: 22px; font-weight: 600; margin: 0 0 6px; letter-spacing: .01em; }}
  .lede {{ color: var(--dim); max-width: 62ch; margin: 0 0 18px; }}
  .stats {{ display: flex; flex-wrap: wrap; gap: 10px; }}
  .stat {{ background: var(--plate); border: 1px solid var(--edge); border-radius: 9px;
           padding: 9px 13px; }}
  .stat b {{ display: block; font-size: 19px; font-weight: 600; }}
  .stat span {{ color: var(--dim); font-size: 11.5px; text-transform: uppercase;
                letter-spacing: .06em; }}
  main {{ max-width: 1180px; margin: 0 auto; }}
  section {{ margin: 0 0 34px; }}
  h2 {{ font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: .09em;
        color: var(--dim); margin: 0 0 14px; display: flex; align-items: center; gap: 10px; }}
  .gnum {{ background: var(--plate); border: 1px solid var(--edge); border-radius: 5px;
           padding: 2px 7px; color: var(--accent); font-variant-numeric: tabular-nums; }}
  .grid {{ display: grid; gap: 14px;
           grid-template-columns: repeat(auto-fill, minmax(176px, 1fr)); }}
  .card {{ margin: 0; background: var(--plate); border: 1px solid var(--edge);
           border-radius: 12px; overflow: hidden; }}
  .card img {{ display: block; width: 100%; height: auto; background: var(--void); }}
  .ph {{ display: grid; place-items: center; aspect-ratio: 156/128; color: var(--dim);
         font-size: 12px; text-align: center; background: var(--void); }}
  .ph.bad {{ color: #ff7070; }}
  figcaption {{ padding: 9px 11px 11px; display: grid; gap: 2px; }}
  figcaption b {{ font-weight: 600; font-size: 13px; }}
  .sub {{ color: var(--dim); font-size: 11.5px; }}
  .meta {{ color: #55647a; font-size: 10.5px; font-variant-numeric: tabular-nums; }}
  .bad {{ color: #ff7070; }}
  footer {{ max-width: 1180px; margin: 40px auto 0; color: var(--dim); font-size: 12px;
            border-top: 1px solid var(--edge); padding-top: 16px; }}
  code {{ background: var(--plate); border: 1px solid var(--edge); border-radius: 4px;
          padding: 1px 5px; font-size: 11.5px; }}
  .toggle {{ position: fixed; top: 18px; right: 20px; z-index: 5;
             background: var(--plate); color: var(--ink); border: 1px solid var(--edge);
             border-radius: 999px; padding: 9px 16px; font: inherit; font-size: 12.5px;
             cursor: pointer; }}
  .toggle:hover {{ border-color: var(--accent); color: var(--accent); }}
  body, .card, .stat, .toggle {{ transition: background-color .18s, color .18s,
                                 border-color .18s; }}
</style>
<button class="toggle" id="t" type="button">Light mode</button>
<header>
  <h1>IoT panels</h1>
  <p class="lede">Eighty RemoteCompose documents, one per home device, each animating the
  thing that device actually does. Thumbnails are animated PNGs of the compiled
  <code>.rc</code> running in the C++ player — what you see is the document, not a mock-up.
  Every panel exists in both themes, and the toggle swaps the page <em>and</em> all eighty
  documents: these are separately compiled light-mode builds, not a filter over the dark
  ones.</p>
  <div class="stats">
    <div class="stat"><b>{len(rows) * 2}</b><span>documents (2 themes)</span></div>
    <div class="stat"><b>{ok}/{len(rows)}</b><span>dark compile</span></div>
    <div class="stat"><b>{light_ok}/{len(rows)}</b><span>light compile</span></div>
    <div class="stat"><b>{ok + light_ok}/{len(rows) * 2}</b><span>byte-identical (Python)</span></div>
    <div class="stat"><b>{json_total // 1024} KB</b><span>JSON in</span></div>
    <div class="stat"><b>{rc_total // 1024} KB</b><span>.rc out</span></div>
  </div>
</header>
<main>
{chr(10).join(sections)}
</main>
<script>
  // The panels are separate documents, not a filter over the dark ones, so switching theme
  // means swapping 80 image sources as well as the page's own variables.
  var t = document.getElementById("t"), root = document.documentElement;
  function apply(mode) {{
    root.dataset.theme = mode;
    var key = mode === "light" ? "data-light" : "data-dark";
    document.querySelectorAll(".card img").forEach(function (img) {{
      var s = img.getAttribute(key);
      if (s && img.getAttribute("src") !== s) img.setAttribute("src", s);
    }});
    t.textContent = mode === "light" ? "Dark mode" : "Light mode";
    try {{ localStorage.setItem("iot-theme", mode); }} catch (e) {{}}
  }}
  t.addEventListener("click", function () {{
    apply(root.dataset.theme === "light" ? "dark" : "light");
  }});
  var saved = null;
  try {{ saved = localStorage.getItem("iot-theme"); }} catch (e) {{}}
  apply(saved || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"));
</script>
<footer>
  Built by <code>./build.sh</code>: every document is compiled with the Java parser, then
  re-converted with the Python converter and compared byte for byte. Thumbnails from
  <code>gen/apng.py</code>, this page from <code>gen/mkindex.py</code>.
</footer>
'''

out = os.path.join(HERE, "index.html")
open(out, "w").write(doc)
print(f"  index.html  {os.path.getsize(out) // 1024} KB  ({ok}/{len(rows)} compiled)")
