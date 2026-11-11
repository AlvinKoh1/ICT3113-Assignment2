#!/usr/bin/env python3
"""Assignment 2, Step 1: split the frozen golden set into tuning and test halves.

Rule from the brief: sort the golden-set tickets by row number; odd rows are
the tuning set, even rows are the test set. "Odd/even rows" is read as the
1-based position in the sorted list (1st, 3rd, 5th ... = tuning), which gives
88 tuning / 87 test tickets out of 175.

Writes golden/a2_split.csv (row, position, set, label). Committed on its own,
before any Assignment 2 analysis, so the commit history shows the split came
first. Never edit it afterwards.

    python3 tools/a2_split.py
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

csv.field_size_limit(10 ** 9)
ROOT = Path(__file__).resolve().parents[1]
SRC, OUT = ROOT / "golden" / "golden_set.csv", ROOT / "golden" / "a2_split.csv"


def main() -> int:
    with open(SRC, newline="", encoding="utf-8") as fh:
        rows = sorted(csv.DictReader(fh), key=lambda r: int(r["row"]))
    out = []
    for pos, r in enumerate(rows, 1):
        out.append({"row": r["row"], "position": pos,
                    "set": "tune" if pos % 2 == 1 else "test", "label": r["label"]})
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    for s in ("tune", "test"):
        part = [r for r in out if r["set"] == s]
        print(f"{s}: {len(part)} tickets  " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(r['label'] for r in part).items())))
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
