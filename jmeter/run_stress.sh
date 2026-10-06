#!/usr/bin/env bash
# Stress test (playbook Test D): one model, stepped Poisson arrival rate, to find
# the highest rate the system sustains before latency grows without bound.
# Run ON THE LOAD GENERATOR MACHINE.
#
#   ./run_stress.sh <service-host> <model-tag> "<steps in tickets/MIN>"
#   e.g. ./run_stress.sh 192.168.1.10 llama3.2:3b "10 15 20 25 30 40"
#
# All steps run inside ONE JMeter run with no restart between them, so a backlog
# built in one step carries into the next (the playbook's requirement). No
# search traffic, response timeout 600 s, so queueing shows up as latency rather
# than being hidden by timeouts. Pick steps around mu = 60 / S, where S is the
# single-request latency (s) from the accuracy run: tools/stress_steps.py does it.
# 300 s steps: shorter steps hold too few arrivals and the limit becomes noise.
# The whole ladder is repeated RUNS times (default 3) - the limit is a measurement too.
set -euo pipefail
HOST="${1:?usage: run_stress.sh <service-host> <model-tag> \"<steps/min>\"}"
MODEL="${2:?model tag}"
STEPS="${3:?steps in tickets per minute, e.g. \"10 15 20 25 30\"}"
STEP_S="${STEP_S:-300}"; RUNS="${RUNS:-3}"; PORT="${PORT:-8000}"
SAFE_MODEL="${MODEL//[:\/]/_}"
cd "$(dirname "$0")"
OUT="../results/stress"; mkdir -p "$OUT"

ACTUAL=$(curl -sf "http://${HOST}:${PORT}/healthz" | python3 -c 'import sys,json;print(json.load(sys.stdin)["model"])')
[[ "$ACTUAL" == "$MODEL" ]] || { echo "ABORT: service runs '$ACTUAL', expected '$MODEL'"; exit 1; }

SCHED=""
for r in $STEPS; do SCHED="$SCHED rate(${r}/min) random_arrivals(${STEP_S} sec) rate(${r}/min)"; done
SCHED="${SCHED# } pause(620 sec)"

for RUN in $(seq 1 "$RUNS"); do
  TAG="stress_${SAFE_MODEL}_run${RUN}"
  echo "=== $TAG  steps/min: $STEPS  (${STEP_S}s each)"
  printf '{"model":"%s","steps_per_min":[%s],"step_s":%s,"schedule":"%s"}\n' \
    "$MODEL" "$(echo $STEPS | tr ' ' ',')" "$STEP_S" "$SCHED" > "$OUT/$TAG.meta.json"
  jmeter -n -t triage_stress.jmx \
    -Jhost="$HOST" -Jport="$PORT" -Jschedule="$SCHED" \
    -JsearchRate=0 -JdurationMin=1 -JdrainSec=1 \
    -Jseed="$RUN" -JrunId="$TAG" -Jjtl="$OUT/$TAG.jtl" -j "$OUT/$TAG.jmeter.log"
  python3 ../tools/analyze_stress.py "$OUT/$TAG.jtl"
  echo "  settling 60s..."; sleep 60
done
echo "Stress complete. Commit results/stress/ (and docker stats snapshots) to the repository."
