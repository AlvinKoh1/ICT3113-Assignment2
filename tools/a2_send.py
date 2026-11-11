#!/usr/bin/env python3
"""Send fixed tickets to POST /tickets one at a time (stdlib only).

Used for the warm-up before every run, the memory check, and the S calibration.

    python3 tools/a2_send.py --rows data/a2_warmup_rows.csv --run-id warmup-<tag> [--base URL]
    python3 tools/a2_send.py --rows data/a2_calib_rows.csv  --run-id calib --model qwen2.5:7b --json-out results/a2/calib/S.json
    python3 tools/a2_send.py --row-ids 9027,9002 --run-id memcheck --ps   (print `ollama ps` after each; Machine A only)

--model sends X-Model (forces that single model); leave it off to exercise the
configuration the service is running (e.g. the cascade).
"""
from __future__ import annotations

import argparse
import json
import statistics
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from a2_common import ROOT, read_csv


def post(base, narrative, row, run_id, model=None, timeout=900):
    body = json.dumps({"narrative": narrative, "row_id": row}).encode()
    h = {"Content-Type": "application/json", "X-Run-ID": run_id}
    if model:
        h["X-Model"] = model
    req = urllib.request.Request(f"{base}/tickets", data=body, method="POST", headers=h)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out = json.load(resp)
        return out, (time.perf_counter() - t0) * 1000, None
    except Exception as exc:  # noqa: BLE001
        return None, (time.perf_counter() - t0) * 1000, f"{type(exc).__name__}: {exc}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--rows", help="CSV with a 'row' column (data/a2_*_rows.csv)")
    ap.add_argument("--row-ids", help="comma-separated row ids instead of --rows")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--ps", action="store_true", help="print `docker exec triage-ollama ollama ps` after each ticket")
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()

    team = {r["row"]: r["narrative"] for r in read_csv(ROOT / "data" / "team_slice.csv")}
    rows = [r["row"] for r in read_csv(a.rows)] if a.rows else a.row_ids.split(",")
    results, fail = [], 0
    for row in rows:
        out, ms, err = post(a.base, team[row], row, a.run_id, a.model)
        rec = {"row": row, "chars": len(team[row]), "client_ms": round(ms, 1),
               "category": out and out.get("category"), "request_id": out and out.get("request_id"),
               "server_ms": out and out.get("latency_ms"), "error": err,
               "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        results.append(rec)
        fail += bool(err)
        print(f"row {row} ({rec['chars']} chars): {rec['category'] or err}  client {ms/1000:.1f} s", flush=True)
        if a.ps:
            docker = shutil.which("docker") or "docker"   # resolves docker.exe / wrappers on any OS
            ps = subprocess.run([docker, "exec", "triage-ollama", "ollama", "ps"], capture_output=True, text=True).stdout
            rec["ollama_ps"] = ps
            print(ps, flush=True)
    if a.json_out:
        ok = [r["client_ms"] for r in results if not r["error"]]
        summary = {"run_id": a.run_id, "model_header": a.model, "base": a.base, "tickets": results,
                   "middle_ms": statistics.median(ok) if len(ok) == 3 else None}
        Path(a.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json_out).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {a.json_out}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
