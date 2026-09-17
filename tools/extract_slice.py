#!/usr/bin/env python3
"""Extract this team's 1000 rows from the course CSV.

Team P2-9 -> n=9 -> rows 9000..9999 inclusive.
All labelling and all test traffic must come from these rows.
"""

from __future__ import annotations
import argparse
import csv
import sys

csv.field_size_limit(10 ** 9)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="full course CSV")
    ap.add_argument("--team", type=int, default=9)
    ap.add_argument("--out", default="data/team_slice.csv")
    args = ap.parse_args()

    start = args.team * 1000
    end = start + 999

    with open(args.source, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = [r for r in reader if start <= int(r["row"]) <= end]

    if len(rows) != 1000:
        print(f"WARNING: expected 1000 rows, got {len(rows)}", file=sys.stderr)

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["row", "source_label", "narrative"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"team {args.team}: rows {start}..{end} -> {args.out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
