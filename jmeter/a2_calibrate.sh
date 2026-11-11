#!/usr/bin/env bash
# Machine B. Measure S and derive the speed-test plan (brief, Step 4 "Set-up").
# Machine A must be running:  tools/a2_machineA.sh calib
#
#   jmeter/a2_calibrate.sh <service-host>
#
# 1. Wait until Machine A reports ready-a2_calib (Ollama restarted, warmed up, top model).
# 2. Send the 3 calibration tickets (data/a2_calib_rows.csv: three DIFFERENT tickets of
#    typical length, never repeated -- Ollama caches prompts it has seen) to the top
#    model, one at a time. S = the middle client-side time, in seconds.
# 3. Write results/a2/calib/S.json and results/a2/calib/plan.json:
#       rate      = one ticket every 2*S seconds  -> 60 / (2*S) tickets per minute
#       duration  = S minutes, minimum 5 (rounded to whole minutes)
#       timeout   = max(10*S, 300) s             (HTTP sampler response timeout)
#       pause     = timeout + 60 s, rounded up to a whole minute (outlasts the timeout)
# 4. Tell Machine A it is done (GET /stats tagged a2_calib:done).
set -euo pipefail
# First Python that actually runs (on Windows "python3" can be the Microsoft Store placeholder).
PY=""; for c in python3 python py; do command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys" >/dev/null 2>&1 && { PY="$c"; break; }; done
cd "$(dirname "$0")/.."
HOST="${1:?usage: jmeter/a2_calibrate.sh <service-host>}"
PORT="${PORT:-8000}"
BASE="http://${HOST}:${PORT}"
mkdir -p results/a2/calib

echo "waiting for Machine A (ready-a2_calib) ..."
until curl -sf -m 10 "$BASE/healthz" | grep -q '"run_id":"ready-a2_calib"'; do sleep 10; done
curl -sf "$BASE/healthz"; echo

"$PY" tools/a2_send.py --base "$BASE" --rows data/a2_calib_rows.csv --run-id a2_calib \
  --model qwen2.5:7b --json-out results/a2/calib/S.json
curl -sf -H "X-Run-ID: a2_calib:done" "$BASE/stats" > /dev/null

"$PY" - <<'PY'
import json, math
s = json.load(open("results/a2/calib/S.json"))
times = [t["client_ms"] / 1000 for t in s["tickets"]]
S = sorted(times)[1]
rate_per_min = 60 / (2 * S)
duration_min = max(5, round(S))
timeout_s = max(10 * S, 300)
pause_s = math.ceil((timeout_s + 60) / 60) * 60
plan = {"S_s": round(S, 2), "timings_s": [round(t, 2) for t in times],
        "rows": [t["row"] for t in s["tickets"]],
        "rate_per_min": round(rate_per_min, 4), "interval_s": round(2 * S, 2),
        "duration_min": duration_min, "timeout_s": math.ceil(timeout_s), "pause_s": pause_s,
        "expected_arrivals": round(rate_per_min * duration_min, 1),
        "schedule": f"rate({rate_per_min:.4f}/min) random_arrivals({duration_min} min) pause({pause_s} sec)"}
json.dump(plan, open("results/a2/calib/plan.json", "w"), indent=2)
print(json.dumps(plan, indent=2))
# The first short ticket (<= 400 chars) is 12th in the speed list; if 12 x 2S passes Ollama's
# 30 min keep-alive, the small model may unload before it and reload mid-run.
if 12 * 2 * S > 25 * 60:
    print("WARNING: S is long enough that llama3.2 may unload between short tickets; reloads will show as 'reload!' in the analysis.")
PY
echo "Commit results/a2/calib/ before the first speed run."
