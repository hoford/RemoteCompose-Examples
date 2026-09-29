#!/usr/bin/env python3
"""Write a group's JSON.

  emit.py g01_lighting [g02_...]            -> ../src        (dark)
  emit.py --light g01_lighting [g02_...]    -> ../src-light  (light)

The theme is set on `style` *before* the group modules are imported, because a group builds
its panels at import time.
"""
import importlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style

args = sys.argv[1:]
light = "--light" in args
if light:
    args.remove("--light")
    style.THEME = "light"
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                   "src-light" if light else "src")
os.makedirs(SRC, exist_ok=True)
total = 0
for mod_name in args:
    mod = importlib.import_module(mod_name)
    for name, doc in mod.PANELS:
        path = os.path.join(SRC, name + ".json")
        with open(path, "w") as fh:
            json.dump(doc, fh, indent=1)
            fh.write("\n")
        print(f"  {name}.json  ({os.path.getsize(path)} B)")
        total += 1
print(f"  {total} document(s) written")
