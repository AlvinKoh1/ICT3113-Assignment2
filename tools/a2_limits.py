#!/usr/bin/env python3
"""Assignment 2, Step 1: accuracy limits from the top model's TEST-set score.

The top Assignment 1 model (qwen2.5:7b) is scored on the test half only. The
same is done for every other Assignment 1 candidate, which is the single-model
accuracy test. Where the per-ticket answers come from depends on the machine:

  --source a2  (the A2 machine, docs/a2/machine_a2.json)
      The A1 Machine A was not available, and Step 4 only allows reusing A1
      single-model records on the same machine. Every single model is therefore
      re-run on the 87 test tickets on the A2 machine first
      (tools/a2_accuracy_all.sh single-<tag>, written to
      results/a2/accuracy/single-<model>_test_predictions.csv), and the limits
      come from THAT qwen2.5:7b run. The A1-record scores are kept alongside for
      comparison only.

  --source a1  (the original plan; only valid on the unchanged A1 machine)
      Reuses the Assignment 1 prediction records, test rows only.

    python3 tools/a2_limits.py --source a2

Writes
    docs/a2/limits.json                            the limits (read by every other A2 tool)
    results/a2/accuracy/single_<model>_test.json   test-set score of each single model
"""
from __future__ import annotations

import argparse
import sys

from a2_common import (A2, ROOT, CATEGORY_MARGIN_PTS, CATS, DOCS_A2, MACHINE, MODELS, OVERALL_MARGIN_PTS,
                       SMALL_CATEGORY_N, TOP_MODEL, UNPARSED, a1_predictions, a2_single_predictions,
                       a2_single_predictions_path, check_limits, jdump, score, split_rows, wilson)


def rel(path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_preds(model: str, source: str, test: list[str]) -> tuple[dict[str, str], str]:
    """row -> predicted category for the test rows, and a description of where it came from."""
    if source == "a1":
        p = a1_predictions(model)
        return {r: p[r]["predicted"] for r in test}, \
            f"results/accuracy/predictions_{model.replace(':', '_')}.csv (Assignment 1 records, reused)"
    path = a2_single_predictions_path(model)
    if not path.exists():
        raise SystemExit(f"MISSING: {rel(path)} -- run tools/a2_accuracy_all.sh single-{model} first")
    p = a2_single_predictions(model)
    missing = [r for r in test if r not in p]
    if missing:
        raise SystemExit(f"INCOMPLETE: {path.name} lacks {len(missing)} test rows (e.g. {missing[:3]}); re-run single-{model}")
    return {r: p[r]["predicted"] for r in test}, \
        f"{rel(path)} (re-run on the A2 machine)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["a1", "a2"], default="a1",
                    help="a2 = single models re-run on the A2 machine (required after the machine change); "
                         "a1 = reuse Assignment 1 records (only valid on the unchanged A1 machine)")
    a = ap.parse_args()

    test = split_rows("test")
    top_pred, top_src = load_preds(TOP_MODEL, a.source, test)
    sc = score(top_pred, test)
    top_pct = sc["acc"] * 100
    limits = {
        "top_model": TOP_MODEL,
        "source": f"{top_src}, test rows of golden/a2_split.csv",
        "source_kind": "a2_rerun" if a.source == "a2" else "a1_records",
        "machine": (MACHINE or {}).get("machine_a", {}).get("short") if a.source == "a2" else "A1 Machine A (i9-10900K)",
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

    # After the machine change: how the A2-machine answers compare with the A1 records (comparison only).
    if a.source == "a2":
        cmp_ = {}
        for m in MODELS:
            a1 = a1_predictions(m)
            a2p, _ = load_preds(m, "a2", test)
            a1p = {r: a1[r]["predicted"] for r in test}
            cmp_[m] = {"a2_correct": score(a2p, test)["correct"], "a1_records_correct": score(a1p, test)["correct"],
                       "answers_changed": sum(a2p[r] != a1p[r] for r in test),
                       "changed_rows": [r for r in test if a2p[r] != a1p[r]]}
        limits["a1_records_comparison"] = cmp_
    jdump(DOCS_A2 / "limits.json", limits)

    lo, hi = wilson(sc["correct"], sc["n"])
    print(f"Source: {'single models re-run on the A2 machine' if a.source == 'a2' else 'Assignment 1 records (reused)'}")
    print(f"Top model {TOP_MODEL} on the test set: {sc['correct']}/{sc['n']} = {top_pct:.1f} % "
          f"(Wilson 95 % CI {lo*100:.1f}-{hi*100:.1f} %)")
    print(f"Overall limit: {limits['overall_limit_pct']:.1f} %  (>= {limits['overall_min_correct']}/{sc['n']} correct)")
    print(f"{'category':28s}{'top':>10}{'limit':>9}{'min ok':>9}  small?")
    for c in CATS:
        k, n = limits["top_category_counts"][c]
        print(f"{c:28s}{k:>4}/{n:<3}{limits['top_category_pct'][c]:>5.1f}%{limits['category_limit_pct'][c]:>8.1f}%"
              f"{limits['category_min_correct'][c]:>6}/{n:<3} {'yes' if c in limits['small_categories'] else ''}")

    print(f"\nSingle-model accuracy test ({'A2 machine re-run' if a.source == 'a2' else 'Assignment 1 records'}, test rows only):")
    others_pass = []
    for m in MODELS:
        pred, src = load_preds(m, a.source, test)
        s = score(pred, test)
        chk = check_limits(s, limits)
        s.update({"config": f"single:{m}", "model": m, "set": "test", "source": src,
                  "source_kind": limits["source_kind"], "limits": chk})
        if a.source == "a2":
            s["a1_records_comparison"] = {k: v for k, v in limits["a1_records_comparison"][m].items() if k != "changed_rows"}
        jdump(A2 / "accuracy" / f"single_{m.replace(':', '_')}_test.json", s)
        extra = ""
        if a.source == "a2":
            c = limits["a1_records_comparison"][m]
            extra = f"   (A1 records {c['a1_records_correct']}/{s['n']}; {c['answers_changed']} answers differ)"
        if s["unparsed"] or s["errors"]:
            extra += f"   [{s['unparsed']} {UNPARSED}, {s['errors']} ERROR]"
        print(f"  {m:14s} {s['correct']:>3}/{s['n']} = {s['acc']*100:5.1f} %   "
              f"{'PASS' if chk['pass'] else 'FAIL'}"
              + (f"  (fails: {', '.join(chk['failed_categories']) or 'overall'})" if not chk["pass"] else "") + extra)
        if m != TOP_MODEL and chk["pass"]:
            others_pass.append(m)
    if others_pass:
        # Step 4: every single model that passes both limits must also be speed-tested.
        print("\nWARNING: these single models now PASS both limits and must also be speed-tested "
              f"(not in the default top7b/cascade400/cascade500 list): {', '.join(others_pass)}")
        jdump(A2 / "accuracy" / "singles_needing_speed_test.json", others_pass)
    return 0


if __name__ == "__main__":
    sys.exit(main())
