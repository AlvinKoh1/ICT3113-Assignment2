#!/usr/bin/env python3
"""Accuracy test: drive the frozen golden set through POST /tickets.

Sequential and single-threaded on purpose -- this measures accuracy, not
throughput, and concurrent requests would contend for the same CPU and blur
the single-request latency figures it also records.

Refuses to run if golden_set.csv is not committed to git, because the brief
requires the golden set to predate the first benchmark run and the commit
history is the evidence.
"""

from __future__ import annotations
import argparse
import csv
import json
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict

import urllib.request
import urllib.error

csv.field_size_limit(10 ** 9)

CATEGORIES = [
    "Credit reporting", "Debt collection", "Mortgage", "Credit card",
    "Bank account or service", "Consumer loan", "Money transfer or service",
]
UNPARSED = "UNPARSED"


def git_committed(path: str) -> bool:
    try:
        out = subprocess.run(["git", "ls-files", "--error-unmatch", path],
                             capture_output=True, text=True)
        if out.returncode != 0:
            return False
        dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", path])
        return dirty.returncode == 0
    except FileNotFoundError:
        return False


def post_ticket(base: str, narrative: str, row: str, model: str | None,
                timeout: float):
    body = json.dumps({"narrative": narrative, "row_id": row}).encode()
    req = urllib.request.Request(f"{base}/tickets", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if model:
        req.add_header("X-Model", model)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read())
        return payload, (time.perf_counter() - t0) * 1000, None
    except Exception as exc:
        return None, (time.perf_counter() - t0) * 1000, f"{type(exc).__name__}: {exc}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--golden", default="golden/golden_set.csv")
    ap.add_argument("--model", required=True,
                    help="Ollama tag, sent as X-Model and recorded in results")
    ap.add_argument("--digest", default="",
                    help="model digest; recorded alongside results so the "
                         "numbers stay pinned to an exact model build")
    ap.add_argument("--outdir", default="results/accuracy")
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--allow-uncommitted", action="store_true",
                    help="escape hatch for a dry run; NEVER use for a reported run")
    args = ap.parse_args()

    if not git_committed(args.golden) and not args.allow_uncommitted:
        print(f"REFUSING TO RUN: {args.golden} is not committed (or has "
              f"uncommitted changes).")
        print("The golden set must be frozen in git before any model sees it.")
        print("  git add golden/ docs/prediction_record.md")
        print("  git commit -m 'Freeze golden test set and prediction record'")
        return 1

    with open(args.golden, newline="", encoding="utf-8") as fh:
        golden = list(csv.DictReader(fh))

    safe_model = args.model.replace(":", "_").replace("/", "_")
    pred_path = f"{args.outdir}/predictions_{safe_model}.csv"
    summary_path = f"{args.outdir}/summary_{safe_model}.json"

    print(f"Model: {args.model}   tickets: {len(golden)}")
    results, latencies, errors = [], [], 0

    for i, t in enumerate(golden, 1):
        payload, latency_ms, err = post_ticket(
            args.base, t["narrative"], t["row"], args.model, args.timeout)
        if err:
            errors += 1
            predicted, server_latency = "ERROR", None
            print(f"  [{i}/{len(golden)}] row {t['row']}: {err}", file=sys.stderr)
        else:
            predicted = payload["category"]
            server_latency = payload.get("latency_ms")
            latencies.append(latency_ms)
        results.append({
            "row": t["row"], "gold": t["label"], "predicted": predicted,
            "correct": int(predicted == t["label"]),
            "client_latency_ms": round(latency_ms, 2),
            "server_latency_ms": server_latency,
            "narrative_chars": len(t["narrative"]),
        })
        if i % 10 == 0 or i == len(golden):
            done = [r for r in results if r["predicted"] != "ERROR"]
            acc = sum(r["correct"] for r in done) / max(len(done), 1)
            print(f"  [{i}/{len(golden)}] running accuracy {acc:.3f}")

    with open(pred_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)

    scored = [r for r in results if r["predicted"] != "ERROR"]
    overall = sum(r["correct"] for r in scored) / max(len(scored), 1)

    per_cat = {}
    for c in CATEGORIES:
        gold_c = [r for r in scored if r["gold"] == c]
        pred_c = [r for r in scored if r["predicted"] == c]
        tp = sum(r["correct"] for r in gold_c)
        recall = tp / len(gold_c) if gold_c else None
        precision = tp / len(pred_c) if pred_c else None
        f1 = (2 * precision * recall / (precision + recall)
              if precision and recall else None)
        per_cat[c] = {"support": len(gold_c), "correct": tp,
                      "recall": recall, "precision": precision, "f1": f1}

    labels = CATEGORIES + [UNPARSED]
    matrix = {g: {p: 0 for p in labels} for g in CATEGORIES}
    for r in scored:
        if r["predicted"] in matrix[r["gold"]]:
            matrix[r["gold"]][r["predicted"]] += 1

    summary = {
        "model": args.model,
        "digest": args.digest,
        "golden_set": args.golden,
        "n_tickets": len(golden),
        "n_scored": len(scored),
        "errors": errors,
        "unparsed": sum(1 for r in scored if r["predicted"] == UNPARSED),
        "overall_accuracy": round(overall, 4),
        "per_category": per_cat,
        "confusion_matrix": matrix,
        "latency_ms": {
            "n": len(latencies),
            "mean": round(statistics.mean(latencies), 2) if latencies else None,
            "p50": round(pct(latencies, 50), 2) if latencies else None,
            "p95": round(pct(latencies, 95), 2) if latencies else None,
            "p99": round(pct(latencies, 99), 2) if latencies else None,
            "max": round(max(latencies), 2) if latencies else None,
        },
        "git_commit": git_head(),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    print(f"\nOverall accuracy : {overall:.4f}  ({sum(r['correct'] for r in scored)}/{len(scored)})")
    print(f"Unparsed         : {summary['unparsed']}   Errors: {errors}")
    print(f"Single-request latency p50/p95/p99 (ms): "
          f"{summary['latency_ms']['p50']} / {summary['latency_ms']['p95']} / "
          f"{summary['latency_ms']['p99']}")
    print("\nPer-category recall:")
    for c in CATEGORIES:
        r = per_cat[c]["recall"]
        print(f"  {c:28s} {r:.3f}" if r is not None else f"  {c:28s}  n/a")
    print(f"\nWrote {pred_path}\n      {summary_path}")
    return 0


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    if not s:
        return 0.0
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True).stdout.strip()
    except FileNotFoundError:
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
