#!/usr/bin/env python3
"""Produce one blank label sheet per annotator from the candidate file.

Each annotator fills in `label` (and optionally `notes` / `confidence`) without
conferring, then commits their own sheet. Sheets are separate files so the git
history shows two independent acts of labelling.
"""

from __future__ import annotations
import argparse
import csv

csv.field_size_limit(10 ** 9)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default="golden/candidates.csv")
    ap.add_argument("--annotators", nargs="+", default=["A", "B"])
    ap.add_argument("--outdir", default="golden")
    args = ap.parse_args()

    with open(args.candidates, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    for who in args.annotators:
        path = f"{args.outdir}/labels_{who}.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(
                fh,
                fieldnames=["row", "label", "confidence", "notes", "narrative"],
            )
            w.writeheader()
            for r in rows:
                w.writerow({
                    "row": r["row"], "label": "", "confidence": "",
                    "notes": "", "narrative": r["narrative"],
                })
        print(f"wrote {path} ({len(rows)} rows to label)")

    print("\nValid labels (copy exactly):")
    for c in ["Credit reporting", "Debt collection", "Mortgage", "Credit card",
              "Bank account or service", "Consumer loan",
              "Money transfer or service"]:
        print(f"  {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
