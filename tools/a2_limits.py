#!/usr/bin/env python3
"""Assignment 2, Step 1: accuracy limits from the top model's TEST-set score.

The top Assignment 1 model (qwen2.5:7b) is scored on the test half only, by
reusing its Assignment 1 prediction records (allowed by Step 4 when digest,
prompt, Ollama version and machine are unchanged -- confirmed by
tools/a2_preflight.sh before any A2 run). The same is done for every other
Assignment 1 candidate, which is the single-model accuracy test.

    python3 tools/a2_limits.py

Writes
    docs/a2/limits.json                            the limits (read by every other A2 tool)
    results/a2/accuracy/single_<model>_test.json   test-set score of each single model
"""
from __future__ import annotations

import sys

from a2_common import (A2, CATEGORY_MARGIN_PTS, CATS, DOCS_A2, MODELS, OVERALL_MARGIN_PTS,
                       SMALL_CATEGORY_N, TOP_MODEL, a1_predictions, check_limits, jdump, score,
                       split_rows, wilson)


def main() -> int:
    test = split_rows("test")
    top = a1_predictions(TOP_MODEL)
    sc = score({r: top[r]["predicted"] for r in test}, test)
    top_pct = sc["acc"] * 100
    limits = {
        "top_model": TOP_MODEL,
        "source": "results/accuracy/predictions_qwen2.5_7b.csv (Assignment 1 records), test rows of golden/a2_split.csv",
        "test_n": sc["n"],
        "top_correct": sc["correct"],
        "top_test_pct": top_pct,
        "overall_limit_pct": top_pct - OVERALL_MARGIN_PTS,
        "top_category_pct": {c: sc["per_category"][c]["acc"] * 100 for c in CATS},
        "top_category_counts": {c: [sc["per_category"][c]["correct"], sc["per_category"][c]["n"]] for c in CATS},
        "category_limit_pct": {c: sc["per_category"][c]["acc"] * 100 - CATEGORY_MARGIN_PTS for c in CATS},
        "small_categories": [c for c in CATS if sc["per_category"][c]["n"] <= SMALL_CATEGORY_N],
        "small_category_rule": f"n <= {SMALL_CATEGORY_N}: two tickets are worth more than the {CATEGORY_MARGIN_PTS:.0f}-point margin",
    }
    # Smallest number of correct answers that passes, so the limits can be quoted as counts.
    limits["overall_min_correct"] = next(k for k in range(sc["n"] + 1) if k / sc["n"] * 100 >= limits["overall_limit_pct"] - 1e-9)
    limits["category_min_correct"] = {
        c: next(k for k in range(sc["per_category"][c]["n"] + 1)
                if k / sc["per_category"][c]["n"] * 100 >= limits["category_limit_pct"][c] - 1e-9)
        for c in CATS}
    jdump(DOCS_A2 / "limits.json", limits)

    lo, hi = wilson(sc["correct"], sc["n"])
    print(f"Top model {TOP_MODEL} on the test set: {sc['correct']}/{sc['n']} = {top_pct:.1f} % "
          f"(Wilson 95 % CI {lo*100:.1f}-{hi*100:.1f} %)")
    print(f"Overall limit: {limits['overall_limit_pct']:.1f} %  (>= {limits['overall_min_correct']}/{sc['n']} correct)")
    print(f"{'category':28s}{'top':>10}{'limit':>9}{'min ok':>9}  small?")
    for c in CATS:
        k, n = limits["top_category_counts"][c]
        print(f"{c:28s}{k:>4}/{n:<3}{limits['top_category_pct'][c]:>5.1f}%{limits['category_limit_pct'][c]:>8.1f}%"
              f"{limits['category_min_correct'][c]:>6}/{n:<3} {'yes' if c in limits['small_categories'] else ''}")

    print("\nSingle-model accuracy test (Assignment 1 records, test rows only):")
    for m in MODELS:
        p = a1_predictions(m)
        s = score({r: p[r]["predicted"] for r in test}, test)
        chk = check_limits(s, limits)
        s.update({"config": f"single:{m}", "model": m, "set": "test",
                  "source": f"results/accuracy/predictions_{m.replace(':', '_')}.csv (Assignment 1, reused)",
                  "limits": chk})
        jdump(A2 / "accuracy" / f"single_{m.replace(':', '_')}_test.json", s)
        print(f"  {m:14s} {s['correct']:>3}/{s['n']} = {s['acc']*100:5.1f} %   "
              f"{'PASS' if chk['pass'] else 'FAIL'}"
              + (f"  (fails: {', '.join(chk['failed_categories']) or 'overall'})" if not chk["pass"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
