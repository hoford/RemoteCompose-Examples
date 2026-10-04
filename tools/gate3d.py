#!/usr/bin/env python3
"""gate3d - verify 3D documents, which neither byte-identity gate can reach.

The corpus's primary gate is byte-identity against the Java writer. That gate is VACUOUS for
3D: RemoteComposeJsonParser.java contains no 3D command at all, silently drops every one, and
emits a document byte-identical to an empty canvas (F-014). The obvious fallback, round-
tripping through the C++ reader rc2json, is also unusable: it decodes only SET_LIGHTS_3D and
MATRIX_3D_OP, and loses stream sync on the rest, reporting stray opcode-0 ops (F-015).

So one in five documents in this catalog has no structural verifier at all. What is left is
the C++ RENDERER, which does handle 3D, and the device. This gate uses the renderer and is
explicit that it is not a device run:

  ink      the 3D must actually mark the canvas, and not merely fill it
  motion   a document whose scene is time-driven must differ between two frames
  device   always reported as outstanding unless a phone is attached

A pass here means "rcj wrote something the C++ renderer draws". It does NOT mean the engine
accepts it. Per CLAUDE.md, anything load-bearing still needs tools/rcdev.py phone.

  gate3d.py DOC.json ...        check documents
  gate3d.py --self-test DOC     prove the gate can fail, by removing the 3D from a document
"""
import json, subprocess, sys, pathlib, io, contextlib, shutil

RC2IMG = "/Users/john/code/github/rcExperiments/players/cpp/build/tools/rc2image/rc2image"
KEYS_3D = ("camera3D", "lights3D", "matrix3D", "defineMesh3D", "drawMesh3D",
           "meshPrimitive3D", "clearDepth3D", "texture3D", "cube3D")
# Only these make a document move on the clock. touchExpression does NOT: a touch-driven
# scene is identical at every time sample, and treating it as animated failed BIO-CB-00011
# for standing still when standing still is what it should do.
TIME_MARKERS = ("animationTime",)        # the only clock --anim can drive
WALLCLOCK_MARKERS = ("continuousSec",)   # animates on a player, unpinnable here
TOUCH_MARKERS = ("touchExpression",)


def has_3d(obj):
    if isinstance(obj, dict):
        return any(k in KEYS_3D for k in obj) or any(has_3d(v) for v in obj.values())
    if isinstance(obj, list):
        return any(has_3d(v) for v in obj)
    return False


def strip_3d(obj):
    """The document with every 3D command removed - the self-test's broken control."""
    if isinstance(obj, dict):
        return {k: strip_3d(v) for k, v in obj.items() if k not in KEYS_3D}
    if isinstance(obj, list):
        return [strip_3d(v) for v in obj
                if not (isinstance(v, dict) and any(k in KEYS_3D for k in v))]
    return obj


def compile_rc(doc, out, base_dir):
    sys.path.insert(0, "/Users/john/code/github/rcJson")
    import rcj
    with contextlib.redirect_stdout(io.StringIO()):
        b = rcj.convert_doc(doc, base_dir=base_dir)
    pathlib.Path(out).write_bytes(b)
    return len(b)


# The clock is PINNED for every render here. Without --clock, every date and time variable
# reads the wall clock, two renders of the same document differ, and a motion measurement
# is really a measurement of how long the two runs were apart (F-019). --anim moves
# animationTime; --clock moves everything else, and a document may use either.
# A fixed instant, given in epoch millis so the step can be sub-second. The step must not
# be a whole multiple of a document's period or the comparison aliases to zero and the gate
# reports a moving document as static - which it did at a 4 s step against a 0.25 Hz scene.
# 1300 ms is not a round fraction of any period used in this corpus, and two different steps
# are tried before anything is called static.
CLOCK_MS = 1773066600000
CLOCK_BASE = "@%d" % CLOCK_MS
CLOCK_LATE = "@%d" % (CLOCK_MS + 1300)
CLOCK_LATE2 = "@%d" % (CLOCK_MS + 2900)


# --seed as well as --clock: the clock does not pin rand(), so a particle document renders
# differently every run and its "motion" measurement is really measuring the dice (F-023).
SEED = "7"


def render(rc, png, t, clock=CLOCK_BASE):
    subprocess.run([RC2IMG, rc, png, "--anim", str(t), "--clock", clock, "--seed", SEED],
                   capture_output=True)
    from PIL import Image
    return Image.open(png).convert("RGB")


def ink_and_motion(doc, base_dir, tmp, animated, same=False, alt=False):
    """Returns (ink fraction at t=0, pixels changed between frames, width, height)."""
    rc = str(tmp / "g.rc")
    compile_rc(doc, rc, base_dir)
    a = render(rc, str(tmp / "a.png"), 0.0, CLOCK_BASE)
    # background = the most common colour; ink = everything else
    hist = {}
    for p in a.getdata():
        hist[p] = hist.get(p, 0) + 1
    bg, bgn = max(hist.items(), key=lambda kv: kv[1])
    ink = 1.0 - bgn / float(a.width * a.height)
    moved = 0
    if animated:
        b = render(rc, str(tmp / "b.png"), 0.0 if same else 2.5,
                   CLOCK_BASE if same else (CLOCK_LATE2 if alt else CLOCK_LATE))
        moved = sum(1 for p, q in zip(a.getdata(), b.getdata()) if p != q)
    return ink, moved, a.width, a.height


def check(path, verbose=True):
    path = pathlib.Path(path)
    doc = json.loads(path.read_text())
    name = path.stem
    if not has_3d(doc):
        if verbose:
            print("  %-20s 2D - the oracle gate applies instead" % name)
        return True
    src = path.read_text()
    wallclock = any(m in src for m in WALLCLOCK_MARKERS)
    # with --clock pinned, a continuousSec() document is measurable like any other:
    # advance the pinned instant and the scene must move
    animated = any(m in src for m in TIME_MARKERS) or wallclock
    touch = any(m in src for m in TOUCH_MARKERS)
    tmp = pathlib.Path("/Users/john/.claude/jobs/168469d6/tmp") / ("gate_" + name)
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        ink, moved, width, height = ink_and_motion(doc, str(path.parent), tmp, animated)
        # run-to-run noise at identical settings: nonzero only for a wall-clock document,
        # and the floor any motion claim has to clear
        _, noise, _, _ = ink_and_motion(doc, str(path.parent), tmp, True, same=True)
        # the same document with its 3D removed, as the floor to beat
        base_ink, _, _, _ = ink_and_motion(strip_3d(doc), str(path.parent), tmp, False)
    except Exception as e:
        print("  %-20s FAILED: %s" % (name, e))
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    gained = ink - base_ink
    gained_px = int(gained * width * height)
    bad = []
    # An absolute floor, not a fraction. A wireframe cage is a few hundred pixels of line
    # and nothing is wrong with it; ENG-ME-00004 contributes 0.5% and is correct.
    if gained_px < 300:
        bad.append("the 3D adds only %d px over the same document without it" % gained_px)
    if ink > 0.97:
        bad.append("the 3D covers %.0f%% of the canvas - probably a camera inside the mesh"
                   % (100 * ink))
    if animated and moved - noise < 50:
        # a second, differently-spaced step, in case the first aliased with the period
        try:
            _, moved2, _, _ = ink_and_motion(doc, str(path.parent), tmp, True, alt=True)
            moved = max(moved, moved2)
        except Exception:
            pass
    if animated and moved - noise < 50:
        bad.append("time-driven but only %d px change when the clock advances 4 s "
                   "(noise at a fixed clock is %d px)" % (moved, noise))
    if verbose:
        how = ("moved %6d px" % moved) if animated else (
              "touch-driven " if touch else "static       ")
        print("  %-20s ink %5.1f%% (+%6d px from 3D)  %s  %s"
              % (name, 100 * ink, gained_px, how, "ok" if not bad else "FAIL"))
        for b in bad:
            print("      %s" % b)
    return not bad


def device_state():
    r = subprocess.run(["python3", "/Users/john/code/github/rcJson/tools/rcdev.py", "devices"],
                       capture_output=True, text=True)
    return "no device" not in (r.stdout + r.stderr)


def strip_draws(obj):
    """Keep the camera, lights and meshes; remove only the draw calls.

    This is the break the self-test needs. Removing ALL the 3D would make the document read
    as 2D and the gate would rightly skip it - which looks like a pass and proves nothing.
    Removing only the draws leaves a document that still claims 3D and still compiles, but
    puts nothing on the canvas: exactly the shape of a writer bug worth catching.
    """
    if isinstance(obj, dict):
        return {k: strip_draws(v) for k, v in obj.items() if k != "drawMesh3D"}
    if isinstance(obj, list):
        return [strip_draws(v) for v in obj
                if not (isinstance(v, dict) and "drawMesh3D" in v)]
    return obj


def self_test(path):
    path = pathlib.Path(path)
    print("self-test on %s" % path.name)
    if not check(path):
        print("  ABORT: the unmodified document already fails; fix that before trusting a pass")
        return False
    doc = json.loads(path.read_text())
    st = pathlib.Path("/Users/john/.claude/jobs/168469d6/tmp") / "st"
    shutil.rmtree(st, ignore_errors=True)
    shutil.copytree(path.parent, st)
    broken = st / "selftest.json"
    broken.write_text(json.dumps(strip_draws(doc)))
    print("  the same document with its drawMesh3D calls removed (scene still declared):")
    failed = not check(broken)
    shutil.rmtree(st, ignore_errors=True)
    if failed:
        print("  the gate FAILS it - it discriminates")
        return True
    print("  the gate PASSED a document that draws no 3D - it is not discriminating, "
          "do not trust it")
    return False


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--self-test":
        sys.exit(0 if self_test(args[1]) else 1)
    ok = all([check(a) for a in args])
    print("\n  device: %s" % ("attached - run tools/rcdev.py phone to confirm on the engine"
                              if device_state() else
                              "NONE ATTACHED - these are renderer results, not engine results"))
    sys.exit(0 if ok else 1)
