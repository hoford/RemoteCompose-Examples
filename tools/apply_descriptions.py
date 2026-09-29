#!/usr/bin/env python3
"""Write descriptions into entry.json from a JSON map of {id: description}.

Used for documents where no description could be harvested from any source and the only way
to say what they are is to look at them. Marks descriptionSource as "rendered" so it is clear
these were written from the rendered output rather than taken from a generator or the
document's own metadata.

Never overwrites a description that already has text.
"""
import json, sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
import re
HASHTAG = re.compile(r"#([A-Za-z0-9][\w-]{1,30})")

data = json.loads(Path(sys.argv[1]).read_text())
wrote = skipped = missing = 0
for did, desc in data.items():
    ep = DOCS / did / "entry.json"
    if not ep.exists():
        missing += 1
        continue
    e = json.loads(ep.read_text())
    if (e.get("description") or "").strip():
        skipped += 1
        continue
    e["description"] = desc
    e["descriptionSource"] = "rendered"
    e["tags"] = sorted(set(e.get("tags") or []) | {t.lower() for t in HASHTAG.findall(desc)})
    ep.write_text(json.dumps(e, indent=2) + "\n")
    wrote += 1
print(f"  wrote {wrote}, skipped {skipped} already described, {missing} not found")
