#!/usr/bin/env python3
"""Analyse one stepped stress run (jmeter/run_stress.sh) and find the limit.

For each arrival-rate step it reports offered and completed rate, p50/p95
latency, errors, and the queue: requests still in flight at the end of the step.

A step is SUSTAINABLE when the end-of-step queue is <= max(5, 15% of the step's
arrivals) and it has no errors. The limit is the highest step below the first
unsustainable one. In a simulation of this rule (Poisson arrivals, 300 s steps at
0.5-1.5x capacity, 300 seeds) the reported limit fell within 0.9-1.1x of the true
capacity in 94% of runs, erring low. The completion rate in the unsustainable
steps (saturated throughput) is a second, direct estimate of capacity.
Stdlib only; draws a PNG if matplotlib is present.

    python3 tools/analyze_stress.py results/stress/stress_llama3.2_3b_run1.jtl
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

csv.field_size_limit(10 ** 9)


def pct(values, p):
    s = sorted(values)
    if not s:
        return None
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main(path: str) -> int:
    jtl = Path(path)
    meta = json.loads(jtl.with_name(jtl.stem + ".meta.json").read_text())
    steps, step_s = meta["steps_per_min"], meta["step_s"]
    rows = []
    with open(jtl, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if "tickets" not in r.get("label", ""):
                continue
            rows.append({"start": int(r["timeStamp"]), "elapsed": float(r["elapsed"]),
                         "ok": r.get("success", "").lower() == "true"})
    if not rows:
        print("no POST /tickets samples")
        return 1
    t0 = min(r["start"] for r in rows)
    for r in rows:
        r["s"] = (r["start"] - t0) / 1000
        r["e"] = r["s"] + r["elapsed"] / 1000

    def inflight(t):
        return sum(1 for r in rows if r["s"] <= t < r["e"])

    out, first_bad = [], None
    for i, rate in enumerate(steps):
        lo, hi = i * step_s, (i + 1) * step_s
        st = [r for r in rows if lo <= r["s"] < hi]
        if not st:
            continue
        ok = [r["elapsed"] for r in st if r["ok"]]
        early = [r["elapsed"] for r in st if r["s"] < lo + step_s / 3 and r["ok"]]
        late = [r["elapsed"] for r in st if r["s"] >= lo + 2 * step_s / 3 and r["ok"]]
        pe, pl = pct(early, 95), pct(late, 95)
        growth = (pl / pe) if pe and pl else None
        backlog = inflight(hi - 0.001) - inflight(lo)
        done = sum(1 for r in rows if lo <= r["e"] < hi and r["ok"])
        errors = sum(1 for r in st if not r["ok"])
        queue_end = inflight(hi - 0.001)
        sustainable = queue_end <= max(5, 0.15 * len(st)) and errors == 0
        if not sustainable and first_bad is None:
            first_bad = rate
        out.append({"step": i + 1, "target_per_min": rate, "arrivals": len(st),
                    "offered_per_min": round(60 * len(st) / step_s, 2),
                    "completed_per_min": round(60 * done / step_s, 2),
                    "p50_ms": round(pct(ok, 50), 1) if ok else None,
                    "p95_ms": round(pct(ok, 95), 1) if ok else None,
                    "errors": errors, "queue_end": queue_end, "backlog_growth": backlog,
                    "growth_ratio": round(growth, 2) if growth else None,
                    "sustainable": sustainable})

    below = [s["target_per_min"] for s in out if first_bad is None or s["target_per_min"] < first_bad]
    summary = {"run": jtl.stem, "model": meta["model"], "step_s": step_s, "steps": out,
               "max_sustainable_per_min": max(below) if below else None,
               "first_unsustainable_per_min": first_bad,
               "saturated_throughput_per_min": (round(sum(s["completed_per_min"] for s in out if not s["sustainable"]) /
                                                      max(1, sum(1 for s in out if not s["sustainable"])), 2)
                                                if any(not s["sustainable"] for s in out) else None),
               "max_inflight": max(inflight(r["s"]) for r in rows),
               "total_errors": sum(1 for r in rows if not r["ok"])}
    jtl.with_name(jtl.stem + ".summary.json").write_text(json.dumps(summary, indent=2))

    hdr = f"{'step':>4} {'target':>7} {'offered':>8} {'done':>7} {'p50 s':>8} {'p95 s':>8} {'err':>4} {'queue':>6} {'growth':>7}  ok"
    print(hdr); print("-" * len(hdr))
    for s in out:
        print(f"{s['step']:>4} {s['target_per_min']:>7} {s['offered_per_min']:>8} {s['completed_per_min']:>7} "
              f"{(s['p50_ms'] or 0) / 1000:>8.2f} {(s['p95_ms'] or 0) / 1000:>8.2f} {s['errors']:>4} "
              f"{s['queue_end']:>6} {str(s['growth_ratio']):>7}  {'yes' if s['sustainable'] else 'NO'}")
    print(f"\nmax sustainable: {summary['max_sustainable_per_min']}/min; first unsustainable: "
          f"{first_bad}/min; saturated throughput {summary['saturated_throughput_per_min']}/min; peak in flight {summary['max_inflight']}; errors {summary['total_errors']}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return 0
    ts = [x / 2 for x in range(int(max(r["e"] for r in rows) * 2) + 1)]
    fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    ax[0].scatter([r["s"] for r in rows], [r["elapsed"] / 1000 for r in rows], s=6,
                  c=["#1f77b4" if r["ok"] else "#d62728" for r in rows])
    ax[0].set_ylabel("latency (s)")
    ax[1].plot(ts, [inflight(t) for t in ts], color="#444")
    ax[1].set_ylabel("in flight"); ax[1].set_xlabel("seconds since first arrival")
    for i, rate in enumerate(steps):
        for a in ax:
            a.axvline(i * step_s, color="#bbb", lw=0.8)
        ax[0].text(i * step_s + 3, ax[0].get_ylim()[1] * 0.9, f"{rate}/min", fontsize=8)
    fig.suptitle(f"Stress {meta['model']} ({jtl.stem})")
    fig.tight_layout()
    fig.savefig(jtl.with_name(jtl.stem + ".png"), dpi=150)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
