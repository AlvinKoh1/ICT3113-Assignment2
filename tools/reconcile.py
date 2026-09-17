#!/usr/bin/env python3
"""Reconcile a JMeter .jtl against the service request log.

The brief: "every number in your final document must reconcile with them; a
number that cannot be traced to a log entry is treated as unsupported."
Run this after every reported run and keep the output.

Checks: sample counts match, error counts match, and client-observed latency
sits above server-observed latency (the difference is network + queueing, and a
negative difference means the two files are not from the same run).
"""

from __future__ import annotations
import argparse
import csv
import json
import statistics

csv.field_size_limit(10 ** 9)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jtl", required=True)
    ap.add_argument("--log", required=True, help="results/logs/requests.jsonl")
    ap.add_argument("--run-id", default=None,
                    help="only log lines with this run_id")
    ap.add_argument("--endpoint", default="POST /tickets")
    ap.add_argument("--jtl-label", default=None)
    args = ap.parse_args()

    jtl = []
    with open(args.jtl, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if args.jtl_label and args.jtl_label not in r.get("label", ""):
                continue
            try:
                jtl.append({"elapsed": float(r["elapsed"]),
                            "ok": r.get("success", "").lower() == "true"})
            except (KeyError, ValueError):
                continue

    logs = []
    with open(args.log, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("endpoint") != args.endpoint:
                continue
            if args.run_id and rec.get("run_id") != args.run_id:
                continue
            logs.append(rec)

    jtl_errors = sum(1 for r in jtl if not r["ok"])
    log_errors = sum(1 for r in logs if r.get("status", 200) >= 400)

    print(f"JMeter samples      : {len(jtl)}")
    print(f"Service log entries : {len(logs)}")
    print(f"JMeter errors       : {jtl_errors}")
    print(f"Service log errors  : {log_errors}")

    ok = True
    if len(jtl) != len(logs):
        print(f"\nMISMATCH: {abs(len(jtl) - len(logs))} request(s) unaccounted for.")
        print("  Common causes: the log file was not cleared between runs "
              "(filter with --run-id), a connection was reset before the "
              "service logged it, or JMeter aborted mid-run.")
        ok = False
    if jtl_errors != log_errors:
        print("\nMISMATCH: error counts differ. Client-side errors (timeouts, "
              "connection refused) will appear in the .jtl but not in the "
              "service log -- that gap is itself a finding worth reporting.")
        ok = False

    if jtl and logs:
        cl = statistics.median(r["elapsed"] for r in jtl)
        sv = statistics.median(r["latency_ms"] for r in logs if "latency_ms" in r)
        print(f"\nMedian client-side latency : {cl:.1f} ms")
        print(f"Median server-side latency : {sv:.1f} ms")
        print(f"Difference (network+queue) : {cl - sv:.1f} ms")
        if cl < sv:
            print("  WARNING: client latency below server latency. These two "
                  "files are probably not from the same run.")
            ok = False

    print("\nRECONCILED" if ok else "\nNOT RECONCILED -- resolve before reporting these numbers")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
