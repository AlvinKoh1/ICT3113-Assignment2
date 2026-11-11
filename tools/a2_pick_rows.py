#!/usr/bin/env python3
"""Print speed-list rows for the memory check: N short (<= 400 chars) and N long
(> 500 chars), interleaved short,long,short,long,... (comma-separated)."""
import argparse

from a2_common import ROOT, read_csv

ap = argparse.ArgumentParser()
ap.add_argument("--short", type=int, default=5)
ap.add_argument("--long", type=int, default=5)
a = ap.parse_args()
rows = read_csv(ROOT / "data" / "a2_speed_rows.csv")
s = [r["row"] for r in rows if int(r["chars"]) <= 400][: a.short]
l = [r["row"] for r in rows if int(r["chars"]) > 500][: a.long]
out = [x for pair in zip(s, l) for x in pair]
print(",".join(out))
