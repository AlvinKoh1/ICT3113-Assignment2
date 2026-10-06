#!/usr/bin/env python3
"""Warm the model before a measured run (playbook precondition P5).

Posts N tickets from team rows that are NOT golden candidates, tagged
X-Run-ID: warmup so they can be excluded from every analysis. Golden tickets
are never sent, so this is safe before and after the freeze.

    python3 tools/warmup.py --base http://<svc>:8000 [--n 3]
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request

csv.field_size_limit(10 ** 9)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--n", type=int, default=3)
    args = ap.parse_args()
    with open("golden/candidates.csv", newline="", encoding="utf-8") as fh:
        golden = {r["row"] for r in csv.DictReader(fh)}
    with open("data/team_slice.csv", newline="", encoding="utf-8") as fh:
        pool = [r for r in csv.DictReader(fh) if r["row"] not in golden][: args.n]
    for r in pool:
        body = json.dumps({"narrative": r["narrative"], "row_id": f"warmup-{r['row']}"}).encode()
        req = urllib.request.Request(f"{args.base}/tickets", data=body, method="POST",
                                     headers={"Content-Type": "application/json", "X-Run-ID": "warmup"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=600) as resp:
            out = json.load(resp)
        print(f"warm-up row {r['row']}: {out['category']} in {(time.perf_counter() - t0) * 1000:.0f} ms ({out['model']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
