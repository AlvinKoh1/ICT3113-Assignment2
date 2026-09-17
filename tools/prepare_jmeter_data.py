#!/usr/bin/env python3
"""Turn the team slice into a JMeter-safe feed file.

Why this exists: JMeter's CSV Data Set Config is line-based and has no real CSV
parser. Complaint narratives contain embedded newlines, commas and double
quotes, so feeding team_slice.csv to JMeter directly silently truncates and
mangles tickets -- and you would be load testing on garbage without noticing.

Fix: emit a TAB-delimited file whose narrative column is already JSON-escaped
(newlines -> \\n, tabs -> \\t, quotes -> \\"). The escaped form contains no
literal tab and no literal newline, so one ticket is exactly one line, and it
drops straight into a JSON request body as ${narrative_json}.

Also emits a search-terms file for the GET /search side of the mixed load.
"""

from __future__ import annotations
import argparse
import csv
import json
import random
import re
from collections import Counter

csv.field_size_limit(10 ** 9)

# Words that say nothing about a ticket and make useless search terms.
STOPWORDS = set("""the a an and or but if then than that this these those i me my we our you your
he she it they them his her its their was were is are be been being have has had do does did
of to in on at for with from by as not no so all any can will would could should may might must
about into over under out up down off very just only also more most some such other same
xx xxxx xxxxxxxx""".split())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", default="data/team_slice.csv")
    ap.add_argument("--out", default="data/jmeter_tickets.tsv")
    ap.add_argument("--search-out", default="data/jmeter_search_terms.tsv")
    ap.add_argument("--exclude-golden", default="golden/golden_set.csv",
                    help="optional: keep load-test traffic disjoint from the "
                         "golden set so accuracy and load runs stay separable")
    ap.add_argument("--no-exclude", action="store_true")
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    excluded = set()
    if not args.no_exclude:
        try:
            with open(args.exclude_golden, newline="", encoding="utf-8") as fh:
                excluded = {r["row"] for r in csv.DictReader(fh)}
        except FileNotFoundError:
            print(f"note: {args.exclude_golden} not found; using all rows")

    with open(args.slice, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["row"] not in excluded]

    rng = random.Random(args.seed)
    rng.shuffle(rows)

    suspicious = 0
    with open(args.out, "w", encoding="utf-8", newline="") as fh:
        fh.write("row\tnarrative_json\n")
        for r in rows:
            text = r["narrative"]
            # JSON-escape, then drop the surrounding quotes: what remains is a
            # safe JSON string *body* to splice into the request template.
            escaped = json.dumps(text, ensure_ascii=True)[1:-1]
            # JMeter would try to evaluate ${...} inside the payload.
            if "${" in escaped:
                escaped = escaped.replace("${", "$｛")
                suspicious += 1
            assert "\t" not in escaped and "\n" not in escaped
            fh.write(f"{r['row']}\t{escaped}\n")

    lengths = sorted(len(r["narrative"]) for r in rows)
    n = len(lengths)
    print(f"wrote {args.out}: {n} tickets "
          f"({len(excluded)} golden rows excluded)")
    if suspicious:
        print(f"  note: neutralised '${{' in {suspicious} ticket(s) so JMeter "
              f"does not evaluate them as expressions")
    print(f"  narrative length chars: min={lengths[0]} "
          f"p50={lengths[n // 2]} p95={lengths[int(n * .95)]} max={lengths[-1]}")
    print("  ^ this is your measured ticket-length distribution for Slide 3")

    # Search terms: mid-frequency words, so /search returns a realistic,
    # non-empty result set rather than everything or nothing.
    freq = Counter()
    for r in rows:
        freq.update({w for w in re.findall(r"[a-z]{4,}", r["narrative"].lower())
                     if w not in STOPWORDS})
    mid = [w for w, c in freq.items() if 0.02 * len(rows) <= c <= 0.25 * len(rows)]
    mid.sort()
    rng.shuffle(mid)
    terms = mid[:200]
    with open(args.search_out, "w", encoding="utf-8", newline="") as fh:
        fh.write("search_term\n")
        for t in terms:
            fh.write(t + "\n")
    print(f"wrote {args.search_out}: {len(terms)} search terms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
