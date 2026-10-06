#!/usr/bin/env python3
"""PASS / FAIL for every candidate against R1-R6 (docs/requirements.md).

Reads the raw evidence directly, so every verdict traces to a committed file:
  results/jtl/<model>_rate<R>_run<N>.jtl        (jmeter/run_matrix.sh)
  results/accuracy/summary_<model>.json         (tools/accuracy_harness.py)
A latency/throughput requirement passes only if it holds in EVERY run.
Writes results/requirements_check.json and .md (used on Slide 11).

    python3 tools/requirements_check.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(10 ** 9)
ROOT = Path(__file__).resolve().parents[1]
RES = Path(os.environ.get("RESULTS_DIR", ROOT / "results"))
MODELS = ["qwen2.5:0.5b", "llama3.2:1b", "llama3.2:3b", "qwen2.5:7b"]
PEAK, SURGE = 0.0167, 0.0333          # tickets/s, docs/requirements.md
CATEGORIES = ["Credit reporting", "Debt collection", "Mortgage", "Credit card",
              "Bank account or service", "Consumer loan", "Money transfer or service"]


def pct(v, p):
    s = sorted(v)
    if not s:
        return None
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def run_stats(path: Path) -> dict:
    post, search = [], []
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            rec = {"t": int(r["timeStamp"]) / 1000, "ms": float(r["elapsed"]),
                   "ok": r.get("success", "").lower() == "true"}
            (post if "tickets" in r["label"] else search if "search" in r["label"] else []).append(rec)
    ok = [r["ms"] for r in post if r["ok"]]
    t0, t_last = min(r["t"] for r in post), max(r["t"] for r in post)
    window = max(t_last - t0, 1)
    end = max(r["t"] + r["ms"] / 1000 for r in post)
    return {
        "n": len(post), "errors": sum(not r["ok"] for r in post),
        "err_pct": 100 * sum(not r["ok"] for r in post) / len(post),
        "p95": pct(ok, 95), "p99": pct(ok, 99),
        "search_p95": pct([r["ms"] for r in search if r["ok"]], 95),
        "offered_per_h": 3600 * len(post) / window,
        "achieved_per_h": 3600 * len(ok) / max(end - t0, 1),
        # requests still in flight at the moment arrivals stopped (queue build-up)
        "inflight_at_end": sum(1 for r in post if r["t"] <= t_last < r["t"] + r["ms"] / 1000),
    }


def verdict(ok, runs=3):
    if runs < 3:
        return "INCOMPLETE"  # the brief: a single run is not a measurement; we require all 3
    return "PASS" if ok else "FAIL"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    runs = defaultdict(list)
    for p in sorted((RES / "jtl").glob("*_rate*_run*.jtl")):
        m = re.match(r"(.+)_rate([\d.]+)_run\d+\.jtl$", p.name)
        if m:
            runs[(m[1], float(m[2]))].append(run_stats(p))
    out = {}
    for model in MODELS:
        safe = model.replace(":", "_").replace("/", "_")
        row = {}
        pk, sg = runs.get((safe, PEAK), []), runs.get((safe, SURGE), [])
        if pk:
            w95, w99, werr = max(r["p95"] or 0 for r in pk), max(r["p99"] or 0 for r in pk), max(r["err_pct"] for r in pk)
            row["R1"] = (verdict(w95 <= 15000 and w99 <= 30000 and werr < 1, len(pk)),
                         f"worst run p95 {w95 / 1000:.2f}s, p99 {w99 / 1000:.2f}s, err {werr:.1f}% ({len(pk)} runs)")
            ws = max(r["search_p95"] or 0 for r in pk)
            row["R2"] = (verdict(ws <= 1000, len(pk)), f"worst run search p95 {ws:.0f} ms")
        if sg:
            ratio = min(r["achieved_per_h"] / r["offered_per_h"] for r in sg)
            qmax, werr = max(r["inflight_at_end"] for r in sg), max(r["err_pct"] for r in sg)
            row["R3"] = (verdict(ratio >= 0.95 and qmax < 5 and werr < 1, len(sg)),
                         f"worst achieved/offered {ratio:.0%}, max in flight at end {qmax}, err {werr:.1f}%")
            row["R6_http"] = (verdict(werr < 1, len(sg)), f"worst error rate {werr:.2f}% at surge ({len(sg)} runs)")
        sp = RES / "accuracy" / f"summary_{safe}.json"
        if sp.exists():
            a = json.loads(sp.read_text(encoding="utf-8"))
            n, acc = a["n_tickets"], a["overall_accuracy"]
            k = round(acc * a["n_scored"])
            lo, hi = wilson(k, n)
            acc_all = k / n  # ERROR rows count as misroutes
            row["R4"] = (verdict(acc_all >= 0.85), f"{acc_all:.1%} (Wilson 95% CI {lo:.0%}-{hi:.0%}, n={n})")
            low = [(c, a["per_category"][c]["recall"]) for c in CATEGORIES
                   if (a["per_category"][c]["recall"] or 0) < 0.70]
            row["R5"] = (verdict(not low), "all >= 70%" if not low else ", ".join(f"{c} {r:.0%}" for c, r in low))
            ur = a["unparsed"] / max(a["n_scored"], 1)
            row["R6_unparsed"] = (verdict(ur < 0.02), f"unparsed {ur:.1%}")
        for key in ("R1", "R2", "R3", "R4", "R5", "R6_http", "R6_unparsed"):
            row.setdefault(key, ("NO DATA", ""))
        row["all_pass"] = all(v[0] == "PASS" for v in row.values())
        out[model] = row
    (RES / "requirements_check.json").write_text(json.dumps(out, indent=2))
    md = ["| Model | R1 POST p95/p99 | R2 search | R3 throughput | R4 overall | R5 per-category | R6 errors | R6 unparsed | All |",
          "|---|---|---|---|---|---|---|---|---|"]
    for m, r in out.items():
        cells = [f"{r[k][0]} ({r[k][1]})" if r[k][1] else r[k][0]
                 for k in ("R1", "R2", "R3", "R4", "R5", "R6_http", "R6_unparsed")]
        md.append(f"| {m} | " + " | ".join(cells) + f" | {'YES' if r['all_pass'] else 'no'} |")
    (RES / "requirements_check.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
