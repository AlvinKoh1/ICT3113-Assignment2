#!/usr/bin/env python3
"""Inter-annotator agreement + disagreement worklist.

Reports raw percent agreement and Cohen's kappa (two annotators) or Fleiss'
kappa (three or more). Pure stdlib -- no sklearn, so it runs anywhere and the
arithmetic is auditable by the marker.

Also writes a disagreement file: every ticket the annotators did not agree on,
ready for adjudication. The brief expects disagreements; this is the artefact
that proves you worked through them.
"""

from __future__ import annotations
import argparse
import csv
import json
from collections import Counter
from itertools import combinations

csv.field_size_limit(10 ** 9)

CATEGORIES = [
    "Credit reporting", "Debt collection", "Mortgage", "Credit card",
    "Bank account or service", "Consumer loan", "Money transfer or service",
]


def load(path: str) -> dict[str, str]:
    with open(path, newline="", encoding="utf-8") as fh:
        out = {}
        for r in csv.DictReader(fh):
            label = (r.get("label") or "").strip()
            out[r["row"]] = label
    return out


def cohen_kappa(a: list[str], b: list[str]) -> tuple[float, float]:
    n = len(a)
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum((ca[c] / n) * (cb[c] / n) for c in set(ca) | set(cb))
    kappa = (observed - expected) / (1 - expected) if expected != 1 else 1.0
    return observed, kappa


def fleiss_kappa(ratings: list[list[str]]) -> float:
    """ratings: one list of labels per item (same number of raters per item)."""
    n_items = len(ratings)
    n_raters = len(ratings[0])
    cats = sorted({lbl for item in ratings for lbl in item})

    p_i = []
    cat_totals = Counter()
    for item in ratings:
        counts = Counter(item)
        cat_totals.update(counts)
        agree = sum(v * (v - 1) for v in counts.values())
        p_i.append(agree / (n_raters * (n_raters - 1)))

    p_bar = sum(p_i) / n_items
    p_j = [cat_totals[c] / (n_items * n_raters) for c in cats]
    p_e = sum(p * p for p in p_j)
    return (p_bar - p_e) / (1 - p_e) if p_e != 1 else 1.0


def interpret(k: float) -> str:
    for threshold, word in [(0.81, "almost perfect"), (0.61, "substantial"),
                            (0.41, "moderate"), (0.21, "fair"), (0.0, "slight")]:
        if k >= threshold:
            return word
    return "poor (worse than chance)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheets", nargs="+", required=True,
                    help="e.g. golden/labels_A.csv golden/labels_B.csv")
    ap.add_argument("--candidates", default="golden/candidates.csv")
    ap.add_argument("--out-disagreements", default="golden/disagreements.csv")
    ap.add_argument("--json-out", default="golden/agreement.json",
                    help="machine-readable copy of the statistic (Slide 6, submission)")
    args = ap.parse_args()

    sheets = {p: load(p) for p in args.sheets}
    names = list(sheets)

    narratives = {}
    with open(args.candidates, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            narratives[r["row"]] = r["narrative"]

    common = set.intersection(*(set(s) for s in sheets.values()))
    blank = {row for row in common
             if any(not sheets[p][row] for p in names)}
    if blank:
        print(f"ERROR: {len(blank)} ticket(s) unlabelled by at least one "
              f"annotator, e.g. rows {sorted(blank)[:5]}")
        print("Every annotator must label every ticket before running this.")
        return 1

    bad = {(p, row, sheets[p][row]) for p in names for row in common
           if sheets[p][row] not in CATEGORIES}
    if bad:
        print(f"ERROR: {len(bad)} label(s) are not one of the seven categories:")
        for p, row, lbl in sorted(bad)[:10]:
            print(f"  {p} row {row}: {lbl!r}")
        return 1

    rows = sorted(common, key=int)
    print(f"Annotators: {', '.join(names)}")
    print(f"Tickets labelled by all: {len(rows)}\n")

    if len(names) == 2:
        a = [sheets[names[0]][r] for r in rows]
        b = [sheets[names[1]][r] for r in rows]
        obs, k = cohen_kappa(a, b)
        stat = {"statistic": "Cohen's kappa", "raw_agreement": round(obs, 4), "kappa": round(k, 4)}
        print(f"Raw agreement : {obs:.4f}  ({int(obs * len(rows))}/{len(rows)})")
        print(f"Cohen's kappa : {k:.4f}  -- {interpret(k)}")
    else:
        for x, y in combinations(names, 2):
            obs, k = cohen_kappa([sheets[x][r] for r in rows],
                                 [sheets[y][r] for r in rows])
            print(f"  {x} vs {y}: raw={obs:.4f} kappa={k:.4f}")
        k = fleiss_kappa([[sheets[p][r] for p in names] for r in rows])
        stat = {"statistic": "Fleiss' kappa", "kappa": round(k, 4)}
        print(f"\nFleiss' kappa : {k:.4f}  -- {interpret(k)}")

    disagreements = [r for r in rows
                     if len({sheets[p][r] for p in names}) > 1]
    print(f"\nDisagreements : {len(disagreements)} "
          f"({len(disagreements) / len(rows) * 100:.1f}%)")

    with open(args.out_disagreements, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=(
            ["row"] + [f"label_{p.split('_')[-1].split('.')[0]}" for p in names]
            + ["adjudicated_label", "resolution_note", "protocol_updated",
               "narrative"]))
        w.writeheader()
        for r in disagreements:
            rec = {"row": r, "adjudicated_label": "", "resolution_note": "",
                   "protocol_updated": "", "narrative": narratives.get(r, "")}
            for p in names:
                rec[f"label_{p.split('_')[-1].split('.')[0]}"] = sheets[p][r]
            w.writerow(rec)

    print(f"Worklist written to {args.out_disagreements} -- fill in "
          f"adjudicated_label and resolution_note for every row.")

    pairs = Counter()
    for r in disagreements:
        pairs[tuple(sorted({sheets[p][r] for p in names}))] += 1
    if pairs:
        print("\nMost confused category pairs (useful for Slide 6):")
        for pair, n in pairs.most_common(5):
            print(f"  {n:3d}  {' <-> '.join(pair)}")

    stat.update({"interpretation": interpret(stat["kappa"]), "annotators": names,
                 "n_tickets": len(rows), "n_disagreements": len(disagreements),
                 "confused_pairs": [{"pair": list(p), "n": n} for p, n in pairs.most_common(5)]})
    with open(args.json_out, "w", encoding="utf-8") as fh:
        json.dump(stat, fh, indent=2)
    print(f"Statistic written to {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
