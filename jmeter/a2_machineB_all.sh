#!/usr/bin/env bash
# Machine B, everything in ONE command (Uwais). Start it, leave the laptop on.
#
#   jmeter/a2_machineB_all.sh 100.88.74.36
#
# Can be started before Machine A: it waits for Machine A at every step.
#   1. self-check: JMeter 5.6.x, Python, the service address answers (waits if Machine A is still starting)
#   2. S calibration (when Machine A is ready for it), commit + push the run plan
#   3. Machine B side of all 9 speed runs; skips any configuration Machine A says is not feasible
#   4. commit + push the .jtl files and run files
# Re-running after an interruption skips every run already done.
set -uo pipefail
# First Python that actually runs (on Windows "python3" can be the Microsoft Store placeholder).
PY=""; for c in python3 python py; do command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys" >/dev/null 2>&1 && { PY="$c"; break; }; done
HOST="${1:-100.88.74.36}"
PORT="${PORT:-8000}"
cd "$(dirname "$0")/.."
mkdir -p results/a2/runs
LOG="results/a2/runs/machineB_all.log"
exec > >(tee -a "$LOG") 2>&1
say() { echo "$(date '+%F %T %z')  $*"; }
die() { say "STOPPED: $*"; say "Screenshot this and send it to Alvin. Re-running the same command resumes."; exit 1; }

say "=== A2 Machine B: start, service at $HOST:$PORT ($(git rev-parse --short HEAD))"
git pull -q --no-rebase --no-edit || say "WARNING: git pull failed; continuing on the local copy"

# 1. self-check
command -v jmeter >/dev/null || die "jmeter is not on PATH"
jmeter --version 2>/dev/null | grep -q "5\.6" || say "WARNING: JMeter is not 5.6.x (A1 used 5.6.3)"
[ -n "$PY" ] || die "python not found in Git Bash"
say "1/4 waiting for the service at http://$HOST:$PORT (Machine A may still be starting)"
until curl -sf -m 10 "http://$HOST:$PORT/healthz" >/dev/null; do sleep 30; done
say "1/4 service reachable"
{ echo "# Machine B software, recorded $(date '+%F %T %z')"; uname -a; jmeter --version 2>&1 | grep -iE "version|[0-9]+\.[0-9]+\.[0-9]+" | head -5
  java -version 2>&1; "$PY" --version 2>&1; git --version; } > results/a2/runs/machineB_env.txt
say "1/4 software versions recorded in results/a2/runs/machineB_env.txt"
say "     Reminder: power plan 'never sleep', Windows Update paused, Ethernet, until this finishes."

# 2. calibration
if [ -f results/a2/calib/plan.json ]; then
  say "2/4 calibration already done: $("$PY" -c "import json;p=json.load(open('results/a2/calib/plan.json'));print(f\"S={p['S_s']} s, rate {p['rate_per_min']}/min\")")"
else
  say "2/4 S calibration: waiting for Machine A to be ready (after its memory check and accuracy test, ~2.5 h)"
  bash jmeter/a2_calibrate.sh "$HOST" > results/a2/runs/calibrate.out 2>&1 || die "calibration failed: see results/a2/runs/calibrate.out"
  say "2/4 $("$PY" -c "import json;p=json.load(open('results/a2/calib/plan.json'));print(f\"S={p['S_s']} s, rate {p['rate_per_min']}/min, {p['duration_min']} min per run\")")"
  tools/a2_push.sh "A2 S calibration (Machine B)" results/a2/calib results/a2/runs || say "WARNING: push failed; committed locally"
fi

# 3. speed test
say "3/4 speed test: 9 runs (about 7 h); progress in results/a2/runs/machineB.log"
bash jmeter/a2_machineB.sh "$HOST" top7b cascade400 cascade500 > results/a2/runs/machineB.out 2>&1 \
  || die "speed test stopped: see results/a2/runs/machineB.out"

# 4. push
tools/a2_push.sh "A2 speed test: jtl + run files (Machine B)" results/a2/jtl results/a2/runs || say "WARNING: push failed; committed locally"
say "=== ALL DONE on Machine B. Post 'Machine B done' in the group chat."
