#!/usr/bin/env python3
"""Build the frozen golden test set.

Takes the annotator sheets plus the adjudicated disagreements and emits
golden/golden_set.csv: one row per ticket with the final agreed label.
Refuses to produce a file if any disagreement is still unadjudicated -- a
half-resolved golden set is worse than none.
"""

from __future__ import annotations
import argparse
import csv
from collections import Counter

csv.field_size_limit(10 ** 9)

CATEGORIES = [
    "Credit reporting", "Debt collection", "Mortgage", "Credit card",
    "Bank account or service", "Consumer loan", "Money transfer or service",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheets", nargs="+", required=True)
    ap.add_argument("--disagreements", default="golden/disagreements.csv")
    ap.add_argument("--candidates", default="golden/candidates.csv")
    ap.add_argument("--out", default="golden/golden_set.csv")
    args = ap.parse_args()

    sheets = []
    for p in args.sheets:
        with open(p, newline="", encoding="utf-8") as fh:
            sheets.append({r["row"]: (r.get("label") or "").strip()
                           for r in csv.DictReader(fh)})

    adjudicated, notes = {}, {}
    with open(args.disagreements, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            adjudicated[r["row"]] = (r.get("adjudicated_label") or "").strip()
            notes[r["row"]] = (r.get("resolution_note") or "").strip()

    with open(args.candidates, newline="", encoding="utf-8") as fh:
        candidates = list(csv.DictReader(fh))

    final, unresolved = [], []
    for c in candidates:
        row = c["row"]
        labels = {s.get(row, "") for s in sheets}
        if len(labels) == 1:
            label, origin, note = labels.pop(), "unanimous", ""
        else:
            label = adjudicated.get(row, "")
            origin, note = "adjudicated", notes.get(row, "")
            if not label or label not in CATEGORIES:
                unresolved.append(row)
                continue
        final.append({"row": row, "label": label, "origin": origin,
                      "resolution_note": note, "narrative": c["narrative"]})

    if unresolved:
        print(f"ERROR: {len(unresolved)} disagreement(s) not adjudicated: "
              f"{unresolved[:10]}")
        print(f"Fill adjudicated_label in {args.disagreements} first.")
        return 1

    if not 150 <= len(final) <= 200:
        print(f"ERROR: golden set has {len(final)} tickets; brief requires "
              f"150-200.")
        return 1

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["row", "label", "origin",
                                           "resolution_note", "narrative"])
        w.writeheader()
        w.writerows(final)

    dist = Counter(r["label"] for r in final)
    adj = sum(1 for r in final if r["origin"] == "adjudicated")
    print(f"Golden set: {len(final)} tickets -> {args.out}")
    print(f"  unanimous: {len(final) - adj}   adjudicated: {adj}")
    print("  label distribution:")
    for c in CATEGORIES:
        print(f"    {dist.get(c, 0):4d}  {c}")
    print("\nFREEZE NOW: commit this file before any model sees it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
