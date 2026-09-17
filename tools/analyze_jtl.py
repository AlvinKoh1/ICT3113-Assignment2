#!/usr/bin/env python3
"""Aggregate JMeter .jtl files into the numbers Slide 9 asks for.

Give it the three runs of one configuration and it reports p50/p95/p99 latency,
achieved throughput, and error rate per run, then the mean and spread across
runs. "A single run is not a measurement" -- so it warns if you pass fewer
than three.

Percentiles are computed over the raw sample set, not over JMeter's per-run
summary, so the numbers are reproducible from the committed .jtl files.
"""

from __future__ import annotations
import argparse
import csv
import json
import statistics
from collections import defaultdict

csv.field_size_limit(10 ** 9)


def pct(values, p):
    s = sorted(values)
    if not s:
        return None
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def load_run(path, label_filter=None):
    samples = defaultdict(list)
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            label = r.get("label", "")
            if label_filter and label_filter not in label:
                continue
            try:
                ts = int(r["timeStamp"])
                elapsed = float(r["elapsed"])
            except (KeyError, ValueError):
                continue
            samples[label].append({
                "ts": ts,
                "elapsed": elapsed,
                "success": r.get("success", "").lower() == "true",
                "code": r.get("responseCode", ""),
            })
    return samples


def summarise(rows):
    if not rows:
        return None
    lat = [r["elapsed"] for r in rows]
    ok = [r for r in rows if r["success"]]
    start = min(r["ts"] for r in rows)
    end = max(r["ts"] + r["elapsed"] for r in rows)
    duration_s = (end - start) / 1000 or 1
    return {
        "samples": len(rows),
        "errors": len(rows) - len(ok),
        "error_rate_pct": round((len(rows) - len(ok)) / len(rows) * 100, 3),
        "p50_ms": round(pct(lat, 50), 1),
        "p95_ms": round(pct(lat, 95), 1),
        "p99_ms": round(pct(lat, 99), 1),
        "mean_ms": round(statistics.mean(lat), 1),
        "max_ms": round(max(lat), 1),
        "duration_s": round(duration_s, 1),
        "achieved_tps": round(len(rows) / duration_s, 3),
        "achieved_per_hour": round(len(rows) / duration_s * 3600, 1),
    }


def spread(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return {
        "mean": round(statistics.mean(vals), 2),
        "min": round(min(vals), 2),
        "max": round(max(vals), 2),
        "stdev": round(statistics.stdev(vals), 2) if len(vals) > 1 else 0.0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jtl", nargs="+", help="the .jtl files for ONE configuration")
    ap.add_argument("--label", default=None, help="only samples whose label contains this")
    ap.add_argument("--config-name", default="unnamed",
                    help="e.g. 'llama3.2:1b @ 0.5 req/s'")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    if len(args.jtl) < 3:
        print(f"WARNING: {len(args.jtl)} run(s) given. The brief requires three "
              f"runs per configuration.\n")

    per_run, all_labels = [], set()
    for path in args.jtl:
        samples = load_run(path, args.label)
        all_labels.update(samples)
        per_run.append({lbl: summarise(rows) for lbl, rows in samples.items()})

    report = {"config": args.config_name, "files": args.jtl, "by_label": {}}

    for lbl in sorted(all_labels):
        print(f"=== {args.config_name} | {lbl} ===")
        runs = [r.get(lbl) for r in per_run]
        header = f"{'run':<6}{'n':>8}{'p50':>10}{'p95':>10}{'p99':>10}{'tps':>10}{'err%':>8}"
        print(header)
        print("-" * len(header))
        for i, (path, s) in enumerate(zip(args.jtl, runs), 1):
            if s is None:
                print(f"{i:<6}{'-- no samples --':>46}")
                continue
            print(f"{i:<6}{s['samples']:>8}{s['p50_ms']:>10.1f}"
                  f"{s['p95_ms']:>10.1f}{s['p99_ms']:>10.1f}"
                  f"{s['achieved_tps']:>10.3f}{s['error_rate_pct']:>8.2f}")

        valid = [s for s in runs if s]
        agg = {k: spread([s[k] for s in valid])
               for k in ("p50_ms", "p95_ms", "p99_ms", "mean_ms",
                         "achieved_tps", "achieved_per_hour", "error_rate_pct")}
        print("-" * len(header))
        for k in ("p50_ms", "p95_ms", "p99_ms", "achieved_tps", "error_rate_pct"):
            a = agg[k]
            if a:
                print(f"  {k:<18} mean={a['mean']:<12} "
                      f"range=[{a['min']}, {a['max']}]  sd={a['stdev']}")
        print()
        report["by_label"][lbl] = {"runs": runs, "across_runs": agg}

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
