#!/usr/bin/env python3
"""Assignment 2, Step 4 speed-test analysis. Every figure comes from the raw files:

  results/a2/jtl/a2_<config>_run<N>.jtl          JMeter samples (elapsed = latency)
  results/a2/jtl/a2_<config>_run<N>.jmeter.log   one "A2SENT" line per request sent
  results/a2/runs/a2_<config>_run<N>.stats_*.json  GET /stats before / after
  results/logs/a2_requests.jsonl                 service log (escalation, model, reloads)

Per run: sent, completed, errored, unfinished; p50; throughput; error rate;
escalation fraction from the service log; GET /stats increase; reconciliation.
Per configuration: p50 mean and spread over the 3 runs; p95 on the three runs
pooled (n stated); no p99 (too few samples).

    python3 tools/a2_analyze_speed.py [configs...]     default: every config found
    -> results/a2/speed/<config>.json, results/a2/speed/summary.json, summary.md
"""
from __future__ import annotations

import csv
import json
import os
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

from a2_common import A2, ROOT, iter_log, jdump, jload, pct

JTL_DIR, RUN_DIR, OUT = A2 / "jtl", A2 / "runs", A2 / "speed"
LOG = Path(os.getenv("A2_LOG", str(ROOT / "results" / "logs" / "a2_requests.jsonl")))


def load_jtl(p: Path):
    rows = []
    with open(p, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if "POST /tickets" not in r.get("label", ""):
                continue
            try:
                rows.append({"ts": int(r["timeStamp"]), "elapsed": float(r["elapsed"]),
                             "ok": r.get("success", "").lower() == "true", "code": r.get("responseCode", ""),
                             "msg": r.get("responseMessage", "")})
            except (KeyError, ValueError):
                continue
    return rows


def analyse_run(tag: str, logs_by_run) -> dict:
    jtl = load_jtl(JTL_DIR / f"{tag}.jtl")
    jlog = JTL_DIR / f"{tag}.jmeter.log"
    sent = len(re.findall(r"A2SENT", jlog.read_text(encoding="utf-8", errors="replace"))) if jlog.exists() else None
    ok = [r for r in jtl if r["ok"]]
    err = [r for r in jtl if not r["ok"]]
    lat = [r["elapsed"] / 1000 for r in ok]
    t0 = min((r["ts"] for r in jtl), default=0)
    t1 = max((r["ts"] + r["elapsed"] for r in jtl), default=0)
    window = (t1 - t0) / 1000 if jtl else None
    before, after = jload(RUN_DIR / f"{tag}.stats_before.json"), jload(RUN_DIR / f"{tag}.stats_after.json")
    stored = (after["total"] - before["total"]) if before and after else None

    L = logs_by_run.get(tag, [])
    L200 = [x for x in L if x.get("status") == 200]
    esc = [x for x in L200 if x.get("escalated")]
    loads = [v for x in L for k, v in x.items() if k.endswith("ollama_load_ms") and isinstance(v, (int, float))]
    routes = defaultdict(int)
    for x in L200:
        routes[x.get("route") or x.get("mode")] += 1
    rec = {
        "tag": tag, "sent": sent, "jtl_samples": len(jtl), "completed": len(ok), "errored": len(err),
        "unfinished": (sent - len(jtl)) if sent is not None else None,
        "error_rate_pct": (len(err) / sent * 100) if sent else (len(err) / len(jtl) * 100 if jtl else None),
        "error_codes": dict(sorted(defaultdict(int, {c: sum(r["code"] == c for r in err) for c in {r["code"] for r in err}}).items())),
        "p50_s": pct(lat, 50), "p95_s": pct(lat, 95), "mean_s": st.mean(lat) if lat else None,
        "max_s": max(lat) if lat else None, "latencies_s": lat,
        "window_s": window, "throughput_per_s": (len(ok) / window) if window else None,
        "throughput_per_min": (len(ok) / window * 60) if window else None,
        "service_log_lines": len(L), "service_log_200": len(L200),
        "escalated": len(esc), "escalation_fraction": (len(esc) / len(L200)) if L200 else None,
        "routes": dict(routes), "max_ollama_load_ms": max(loads) if loads else None,
        "stats_before": before and before["total"], "stats_after": after and after["total"], "stored": stored,
    }
    rec["reconcile"] = {
        "jtl_vs_log": len(jtl) == len(L),
        "jtl_ok_vs_log_200": len(ok) == len(L200),
        "stats_delta_vs_log_200": stored == len(L200) if stored is not None else None,
        "sent_vs_jtl": (sent == len(jtl)) if sent is not None else None,
        "reload_during_run": bool(loads) and max(loads) > 1000,
    }
    return rec


def spread(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return None
    return {"mean": st.mean(v), "sd": st.stdev(v) if len(v) > 1 else 0.0, "min": min(v), "max": max(v), "n": len(v)}


def main() -> int:
    tags = sorted(p.stem for p in JTL_DIR.glob("a2_*_run*.jtl"))
    by_cfg = defaultdict(dict)   # config -> run number -> tag; a redo (run3b) replaces run3
    for t in tags:
        m = re.match(r"a2_(.+)_run(\d+)([a-z]?)$", t)
        if m:
            cur = by_cfg[m.group(1)].get(m.group(2))
            if cur is None or t > cur:
                by_cfg[m.group(1)][m.group(2)] = t
    by_cfg = {c: sorted(d.values()) for c, d in by_cfg.items()}
    want = sys.argv[1:] or sorted(by_cfg)
    logs_by_run = defaultdict(list)
    for r in iter_log(LOG):
        if r.get("endpoint") == "POST /tickets":
            logs_by_run[r.get("run_id")].append(r)

    summary, md = {}, ["# Speed test summary (generated by tools/a2_analyze_speed.py)", ""]
    plan = jload(A2 / "calib" / "plan.json")
    if plan:
        md += [f"S = {plan['S_s']} s (timings {plan['timings_s']}, rows {plan['rows']}); schedule `{plan['schedule']}`; "
               f"timeout {plan['timeout_s']} s.", ""]
    for c in want:
        runs = [analyse_run(t, logs_by_run) for t in sorted(by_cfg.get(c, []))]
        if not runs:
            continue
        pooled = [x for r in runs for x in r["latencies_s"]]
        L200 = sum(r["service_log_200"] for r in runs)
        cfg = {
            "config": c, "runs": [{k: v for k, v in r.items() if k != "latencies_s"} for r in runs],
            "n_runs": len(runs),
            "p50_s": spread([r["p50_s"] for r in runs]),
            "p95_pooled_s": pct(pooled, 95), "p95_pooled_n": len(pooled),
            "throughput_per_min": spread([r["throughput_per_min"] for r in runs]),
            "error_rate_pct": spread([r["error_rate_pct"] for r in runs]),
            "escalation_fraction": spread([r["escalation_fraction"] for r in runs]),
            "escalation_pooled": (sum(r["escalated"] for r in runs) / L200) if L200 else None,
            "totals": {k: sum((r[k] or 0) for r in runs) for k in ("sent", "completed", "errored", "unfinished")},
            "all_reconciled": all(all(v in (True, None) for k, v in r["reconcile"].items() if k != "reload_during_run")
                                  and not r["reconcile"]["reload_during_run"] for r in runs),
        }
        jdump(OUT / f"{c}.json", cfg)
        summary[c] = {k: v for k, v in cfg.items() if k != "runs"}
        md += [f"## {c}", "", "| Run | Sent | Done | Err | Unfin. | p50 s | p95 s | Thru /min | Err % | Esc | Stored | Reconciled |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in runs:
            rc = all(v in (True, None) for k, v in r["reconcile"].items() if k != "reload_during_run")
            esc = "" if r["escalation_fraction"] is None else f"{r['escalated']}/{r['service_log_200']}"
            p50 = "" if r["p50_s"] is None else f"{r['p50_s']:.1f}"
            p95 = "" if r["p95_s"] is None else f"{r['p95_s']:.1f}"
            thr = "" if r["throughput_per_min"] is None else f"{r['throughput_per_min']:.2f}"
            er = "" if r["error_rate_pct"] is None else f"{r['error_rate_pct']:.1f}"
            flag = " (reload!)" if r["reconcile"]["reload_during_run"] else ""
            md.append(f"| {r['tag']} | {r['sent']} | {r['completed']} | {r['errored']} | {r['unfinished']} | "
                      f"{p50} | {p95} | {thr} | {er} | {esc} | {r['stored']} | {'yes' if rc else 'NO'}{flag} |")
        p = cfg["p50_s"]
        escp = "n/a" if cfg["escalation_pooled"] is None else f"{cfg['escalation_pooled'] * 100:.0f} %"
        md += ["", f"p50 mean {p['mean']:.1f} s (sd {p['sd']:.1f}, range {p['min']:.1f}-{p['max']:.1f}); "
               f"p95 pooled {cfg['p95_pooled_s']:.1f} s on n = {cfg['p95_pooled_n']}; escalation pooled {escp}.", ""]
    jdump(OUT / "summary.json", summary)
    (OUT / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
