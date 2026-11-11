#!/usr/bin/env python3
"""Assignment 2, Step 4 accuracy test: every ticket of one golden half through
POST /tickets, once, on whatever configuration the service is running.

Sequential, from Machine A (accuracy, not speed). No X-Model header, so the
service's own configuration (e.g. the cascade) answers. Which model produced
each answer, and whether the ticket was escalated, is read back from the
service log by request_id -- the caller-facing response does not reveal it.

    python3 tools/a2_accuracy.py --config cascade500            # test set (the one that counts)
    python3 tools/a2_accuracy.py --config cascade500 --set tune # optional, for comparison only

Refuses to run unless the split, the escalation rule and the prediction record
are committed and unmodified (the commit history is the evidence they came first).

Writes results/a2/accuracy/<config>_<set>.json and <config>_<set>_predictions.csv
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request

from a2_common import (A2, ROOT, UNPARSED, check_limits, golden, iter_log, jdump, jload, score, split_rows,
                       write_csv, DOCS_A2)

MUST_BE_COMMITTED = ["golden/a2_split.csv", "docs/a2/escalation_rule.md", "docs/a2/prediction_record.md"]


def committed(path: str) -> bool:
    r = subprocess.run(["git", "ls-files", "--error-unmatch", path], cwd=ROOT, capture_output=True)
    return r.returncode == 0 and subprocess.run(["git", "diff", "--quiet", "HEAD", "--", path], cwd=ROOT).returncode == 0


def post(base, text, row, run_id, timeout):
    req = urllib.request.Request(f"{base}/tickets", method="POST",
                                 data=json.dumps({"narrative": text, "row_id": row}).encode(),
                                 headers={"Content-Type": "application/json", "X-Run-ID": run_id})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp), (time.perf_counter() - t0) * 1000, None
    except Exception as exc:  # noqa: BLE001
        return None, (time.perf_counter() - t0) * 1000, f"{type(exc).__name__}: {exc}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="cascade400 | cascade500 | top7b | single-<tag>")
    ap.add_argument("--set", default="test", choices=["test", "tune"])
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--log", default=str(ROOT / "results" / "logs" / "a2_requests.jsonl"))
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--allow-uncommitted", action="store_true", help="dry runs only; never for a reported run")
    a = ap.parse_args()

    missing = [p for p in MUST_BE_COMMITTED if not committed(p)]
    if missing and not a.allow_uncommitted:
        print("REFUSING TO RUN: not committed or modified since the last commit:", ", ".join(missing))
        return 1

    with urllib.request.urlopen(f"{a.base}/healthz", timeout=10) as r:
        health = json.load(r)
    print(f"service: {health}")
    gold = golden()
    rows = split_rows(a.set)
    run_id = f"a2acc_{a.config}_{a.set}"
    recs = []
    for i, row in enumerate(rows, 1):
        out, ms, err = post(a.base, gold[row]["narrative"], row, run_id, a.timeout)
        recs.append({"row": row, "gold": gold[row]["label"], "predicted": out["category"] if out else "ERROR",
                     "request_id": out["request_id"] if out else None, "client_ms": round(ms, 1),
                     "chars": len(gold[row]["narrative"]), "error": err})
        if i % 10 == 0 or i == len(rows):
            ok = sum(r["predicted"] == r["gold"] for r in recs)
            print(f"  [{i}/{len(rows)}] {ok}/{i} correct", flush=True)

    time.sleep(1)
    by_id = {r.get("request_id"): r for r in iter_log(a.log) if r.get("run_id") == run_id}
    for r in recs:
        L = by_id.get(r["request_id"], {})
        r.update({"final_model": L.get("final_model"), "escalated": L.get("escalated"), "route": L.get("route"),
                  "small_category": L.get("small_category"), "large_category": L.get("large_category"),
                  "server_ms": L.get("latency_ms"), "in_log": bool(L)})
    pred = {r["row"]: r["predicted"] for r in recs}
    sc = score(pred, rows, gold)
    limits = jload(DOCS_A2 / "limits.json")
    esc = [r for r in recs if r["escalated"]]
    acc_ = [r for r in recs if r["escalated"] is False]
    part = lambda rs: {"n": len(rs), "correct": sum(r["predicted"] == r["gold"] for r in rs),
                       "acc": (sum(r["predicted"] == r["gold"] for r in rs) / len(rs)) if rs else None}
    sc.update({
        "config": a.config, "set": a.set, "run_id": run_id, "service": health,
        "limits": check_limits(sc, limits) if a.set == "test" else None,
        "escalation": {"escalated": part(esc), "not_escalated": part(acc_),
                       "fraction": len(esc) / len(recs) if recs else None,
                       "routes": {k: sum(r["route"] == k for r in recs) for k in sorted({r["route"] for r in recs if r["route"]})},
                       "missing_from_log": sum(not r["in_log"] for r in recs)},
        "client_ms_median": sorted(r["client_ms"] for r in recs)[len(recs) // 2],
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "unparsed": sum(r["predicted"] == UNPARSED for r in recs),
    })
    jdump(A2 / "accuracy" / f"{a.config}_{a.set}.json", sc)
    write_csv(A2 / "accuracy" / f"{a.config}_{a.set}_predictions.csv", recs)

    print(f"\n{a.config} on {a.set}: {sc['correct']}/{sc['n']} = {sc['acc']*100:.1f} %")
    e = sc["escalation"]
    if e["fraction"] is not None and any(r["escalated"] is not None for r in recs):
        print(f"escalated {e['escalated']['n']}/{len(recs)} ({e['fraction']*100:.0f} %): "
              f"escalated {e['escalated']['correct']}/{e['escalated']['n']} correct, "
              f"kept {e['not_escalated']['correct']}/{e['not_escalated']['n']} correct; routes {e['routes']}")
    if sc["limits"]:
        print("limits:", "PASS" if sc["limits"]["pass"] else f"FAIL {sc['limits']['failed_categories'] or 'overall'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
