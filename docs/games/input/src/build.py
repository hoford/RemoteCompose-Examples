#!/usr/bin/env python3
"""build.py — compile every game and emit the web harness.

    python3 games/build.py              # build all games in games/src
    python3 games/build.py pulse_push   # just one

Each `games/src/<name>.json` is compiled by the official androidx parser
(`oracle/oracle.sh`) into `games/rc/<name>.rc`, because that is the only compiler that
supports particles — the repo's fast Python converter (`rcj`) does not implement them.

The harness is `games/web/index.html`: one self-contained page with every game inlined
as base64 alongside the whole TypeScript player, so it runs from `file://` with no
server. That matters because these documents are driven by touch, and the only way to
know a touch-driven document actually works is to play it — the Node tracer reports
`touchX = 0` with a frozen clock, so it can verify motion and collisions but never input.
"""

import base64
import html
import json
import rpncheck
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
ORACLE = REPO / "oracle" / "oracle.sh"
PLAYER = Path("/Users/john/code/github/rcExperiments/players/typescript/web-player/bundle.js")
SRC, RC, WEB = ROOT / "src", ROOT / "rc", ROOT / "web"

# Games that are playable, in the order they should appear. Anything in src/ that is not
# listed here is treated as a probe document and left out of the page.
GAMES = [
    ("pulse_push", "Pulse Push", "Tap to send a shockwave. It pushes the ball — you never touch the ball directly. Reach the ring, avoid the red hazards."),
    ("gravity_beacon", "Gravity Beacon", "Each tap drops a gravity well that pulls everything toward it for about a second. Steer by placing wells, not by pushing."),
    ("chain_reaction", "Chain Reaction", "Tap to detonate. Every mote the blast touches detonates too. One tap, one chain — set off as many as you can."),
    ("polarity", "Polarity", "Tap to flip between attract and repel. Blue pulls you toward the magnets, red pushes you away. Ride the field to the goal."),
    ("orbit_hop", "Orbit Hop", "You orbit a planet automatically. Tap to let go and fly straight; you are captured by whatever planet you reach. Get to the green one."),
    ("one_tap_pinball", "One-Tap Pinball", "The ball falls and bounces on its own. Every tap fires all three bumpers at once — hit the rings in order and never let it drain."),
    ("bubble_drop", "Bubble Drop", "Each tap releases one bubble from the spout. They fall, bounce and shove each other. Land all three in the bin."),
    ("safe_zone", "Safe Zone", "Two drifters cross while projectiles hunt them. Tap to raise a shield — whatever is inside it is untouchable while it lasts."),
    ("wall_bounce", "Wall Bounce", "The ball never stops. Each tap drops a short-lived bumper; use them to steer it through all three checkpoints."),
    ("particle_shepherd", "Particle Shepherd", "Tap to make a repelling field and herd all three sparks into the pen. You push them — you can never pull."),
]

PROBES = {"skeleton", "input", "order"}


def compile_game(name: str) -> bytes:
    src, out = SRC / f"{name}.json", RC / f"{name}.rc"
    # The writer does not enforce MAX_EXPRESSION_SIZE; only the reader does. Without this
    # check an over-long expression compiles cleanly, runs in the TypeScript player, and
    # then throws on the Java engine at load time -- healthy on the desktop, dead on the
    # device. Two games shipped that way before this check existed.
    doc = json.loads(src.read_text())
    over = [(w, rpncheck.rpn_len(e)) for w, e in rpncheck.expressions(doc)
            if rpncheck.rpn_len(e) > rpncheck.LIMIT]
    if over:
        detail = "\n".join(f"    {n} tokens  {w}" for w, n in over)
        raise SystemExit(f"{name}: {len(over)} expression(s) over the "
                         f"{rpncheck.LIMIT}-token limit\n{detail}")
    RC.mkdir(exist_ok=True)
    r = subprocess.run(["bash", str(ORACLE), str(src), str(out)],
                       capture_output=True, text=True, cwd=REPO)
    if r.returncode != 0 or not out.exists():
        msg = "\n".join(l for l in (r.stdout + r.stderr).splitlines()
                        if re.search(r"exception|error|caused", l, re.I))
        raise SystemExit(f"{name}: compile failed\n{msg or r.stderr[-800:]}")
    return out.read_bytes()


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>RemoteCompose Games</title>
<style>
  :root{{--bg:#0b0f14;--panel:#141b24;--fg:#d7dee8;--muted:#8b95a5;--accent:#3ddc84;
        --line:#2a3644;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--fg);
       font:14px/1.55 system-ui,-apple-system,sans-serif;
       -webkit-user-select:none;user-select:none;overscroll-behavior:none}}
  header{{padding:26px 20px 14px;text-align:center}}
  h1{{margin:0 0 6px;font-size:20px;font-weight:600}}
  h1 b{{color:var(--accent);font-weight:600}}
  header p{{margin:0;color:var(--muted);font-size:13px}}
  nav{{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;padding:10px 16px 18px}}
  nav button{{background:#1b2330;color:var(--fg);border:1px solid var(--line);
              border-radius:999px;padding:7px 15px;font:inherit;font-size:13px;cursor:pointer}}
  nav button:hover{{border-color:var(--accent);color:var(--accent)}}
  nav button[aria-current="true"]{{background:var(--accent);color:#08110b;border-color:var(--accent)}}
  main{{display:flex;flex-direction:column;align-items:center;gap:12px;padding:0 16px 40px}}
  #frame{{background:var(--panel);border-radius:14px;padding:10px;line-height:0;
          box-shadow:0 10px 40px rgba(0,0,0,.55)}}
  canvas{{display:block;border-radius:8px;touch-action:none;cursor:pointer}}
  #how{{max-width:46ch;text-align:center;color:var(--muted);font-size:13px;min-height:3em}}
  .row{{display:flex;gap:8px}}
  .row button{{background:#1b2330;color:var(--fg);border:1px solid var(--line);
               border-radius:8px;padding:7px 16px;font:inherit;cursor:pointer}}
  .row button:hover{{border-color:var(--accent);color:var(--accent)}}
  footer{{color:var(--muted);font-family:var(--mono);font-size:11px;text-align:center;
          padding:0 16px 30px;line-height:1.7}}
</style>
</head>
<body>
<header>
  <h1>RemoteCompose <b>Games</b></h1>
  <p>Ten games, each a single RemoteCompose document. No JavaScript game loop and no
     host-side state — the document is the game.</p>
</header>
<nav id="tabs"></nav>
<main>
  <div id="frame"><canvas id="c" width="400" height="400"></canvas></div>
  <p id="how"></p>
  <div class="row"><button id="restart">Restart</button></div>
</main>
<footer id="status">loading…</footer>

<script>{player}</script>
<script>
(function () {{
  var GAMES = {games};
  var tabs = document.getElementById("tabs");
  var how = document.getElementById("how");
  var status = document.getElementById("status");
  var canvas = document.getElementById("c");
  var player = null, current = 0;

  if (!window.RC || !window.RC.RcdPlayer) {{ status.textContent = "player failed to load"; return; }}

  function bytes(s) {{
    var b = atob(s), a = new Uint8Array(b.length);
    for (var i = 0; i < b.length; i++) a[i] = b.charCodeAt(i);
    return a.buffer;
  }}

  // Each game gets a fresh player on a fresh canvas. Reusing one player across
  // documents leaks state between them, and reusing the canvas leaks the WebGL context.
  function play(i) {{
    current = i;
    var g = GAMES[i];
    how.textContent = g.how;
    Array.prototype.forEach.call(tabs.children, function (b, n) {{
      b.setAttribute("aria-current", n === i ? "true" : "false");
    }});
    if (player) {{ try {{ player.destroy ? player.destroy() : player.stop && player.stop(); }} catch (e) {{}} }}
    var fresh = canvas.cloneNode(false);
    canvas.parentNode.replaceChild(fresh, canvas);
    canvas = fresh;
    player = new window.RC.RcdPlayer(canvas);
    try {{ player.setTheme("dark"); }} catch (e) {{}}
    var buf = bytes(g.rc);
    player.loadFromArrayBuffer(buf).then(function () {{
      status.textContent = g.title + " · " + buf.byteLength + " bytes · " + g.src;
    }}).catch(function (e) {{ status.textContent = "failed to play: " + e; }});
    ["touchstart", "touchmove", "gesturestart"].forEach(function (t) {{
      canvas.addEventListener(t, function (e) {{ e.preventDefault(); }}, {{passive: false}});
    }});
  }}

  GAMES.forEach(function (g, i) {{
    var b = document.createElement("button");
    b.textContent = g.title;
    b.addEventListener("click", function () {{ play(i); }});
    tabs.appendChild(b);
  }});
  document.getElementById("restart").addEventListener("click", function () {{ play(current); }});
  play(0);
}})();
</script>
</body>
</html>
"""


def main() -> None:
    only = sys.argv[1:]
    if not PLAYER.exists():
        raise SystemExit(f"missing player bundle: {PLAYER}\n"
                         f"build it with: cd {PLAYER.parents[1]} && npm run bundle")

    # Probes are compiled too — they are the documents that pin down engine semantics,
    # and a probe that stops compiling is a real signal.
    for p in sorted(SRC.glob("*.json")):
        if p.stem in PROBES and (not only or p.stem in only):
            compile_game(p.stem)
            print(f"  probe   {p.stem}")

    entries = []
    for name, title, how in GAMES:
        if only and name not in only:
            continue
        if not (SRC / f"{name}.json").exists():
            print(f"  skip    {name} (not written yet)")
            continue
        rc = compile_game(name)
        print(f"  game    {name:16s} {len(rc):>6,} bytes")
        entries.append({"title": title, "how": how, "src": f"games/src/{name}.json",
                        "rc": base64.b64encode(rc).decode()})

    if not entries:
        print("nothing to publish"); return

    WEB.mkdir(exist_ok=True)
    out = WEB / "index.html"
    out.write_text(PAGE.format(player=PLAYER.read_text(),
                               games=json.dumps(entries)))
    print(f"\n  {out}  {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
