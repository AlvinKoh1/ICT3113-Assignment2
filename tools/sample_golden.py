#!/usr/bin/env python3
"""Draw the golden-set candidates from the team slice.

Two deliberate choices, both worth stating on Slide 6:

1. Stratified on source_label so every category is represented. The source
   labels are noisy, so this controls *coverage*, not ground truth -- a ticket
   sampled from the "Mortgage" stratum may well be adjudicated as something
   else, and that is expected.
2. The candidate file written for annotators does NOT contain source_label.
   Showing annotators the consumer-selected label would anchor them to it, and
   the whole reason for the golden set is that those labels cannot be trusted.
   The mapping back to source_label is kept separately for later analysis.
"""

from __future__ import annotations
import argparse
import csv
import random
from collections import defaultdict

csv.field_size_limit(10 ** 9)

CATEGORIES = [
    "Credit reporting", "Debt collection", "Mortgage", "Credit card",
    "Bank account or service", "Consumer loan", "Money transfer or service",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", default="data/team_slice.csv")
    ap.add_argument("--n", type=int, default=175,
                    help="total candidates (brief requires 150-200)")
    ap.add_argument("--seed", type=int, default=2026,
                    help="fixed so the sample is reproducible and auditable")
    ap.add_argument("--out", default="golden/candidates.csv")
    ap.add_argument("--keymap", default="golden/candidates_sourcelabels.csv",
                    help="row -> source_label, for post-hoc analysis ONLY; "
                         "annotators must not open this")
    args = ap.parse_args()

    if not 150 <= args.n <= 200:
        raise SystemExit("--n must be between 150 and 200 (assignment brief)")

    with open(args.slice, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    strata = defaultdict(list)
    for r in rows:
        strata[r["source_label"]].append(r)

    rng = random.Random(args.seed)
    per = args.n // len(CATEGORIES)
    remainder = args.n - per * len(CATEGORIES)

    picked = []
    for i, cat in enumerate(CATEGORIES):
        take = per + (1 if i < remainder else 0)
        pool = strata.get(cat, [])
        if len(pool) < take:
            print(f"WARNING: stratum '{cat}' has only {len(pool)} rows")
            take = len(pool)
        picked.extend(rng.sample(pool, take))

    # Shuffle so annotators cannot infer the stratum from position in the file.
    rng.shuffle(picked)

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["row", "narrative"])
        w.writeheader()
        for r in picked:
            w.writerow({"row": r["row"], "narrative": r["narrative"]})

    with open(args.keymap, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["row", "source_label"])
        w.writeheader()
        for r in picked:
            w.writerow({"row": r["row"], "source_label": r["source_label"]})

    print(f"sampled {len(picked)} candidates (seed={args.seed}) -> {args.out}")
    print(f"source labels held back in {args.keymap} -- do not open while labelling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
