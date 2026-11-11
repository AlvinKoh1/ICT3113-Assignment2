#!/usr/bin/env bash
# Machine B (load generator). Assignment 2 speed test, three runs per configuration.
# Machine A runs tools/a2_machineA.sh with the same configs and runs at the same time.
#
#   jmeter/a2_machineB.sh <service-host> <config...> [runs]
#   e.g. jmeter/a2_machineB.sh 100.88.74.36 top7b cascade400 cascade500
#
# Reads the rate / run length / timeout / pause from results/a2/calib/plan.json
# (jmeter/a2_calibrate.sh), so every configuration runs under identical conditions.
# Per run (tag a2_<config>_run<N>; JMeter seed = N, so run N of every config has
# the same arrival times and the same tickets in the same order):
#   1. wait for /healthz run_id == ready-<tag>  (Machine A restarted Ollama and warmed up)
#   2. GET /stats  (X-Run-ID <tag>:stats-before)  -> results/a2/runs/<tag>.stats_before.json
#   3. JMeter open-model run                      -> results/a2/jtl/<tag>.jtl, .jmeter.log
#   4. GET /stats  (X-Run-ID <tag>:stats-after)   -> results/a2/runs/<tag>.stats_after.json
#      (this request is also Machine A's signal that the run is over)
set -euo pipefail
cd "$(dirname "$0")"
HOST="${1:?usage: a2_machineB.sh <service-host> <config...> [runs]}"; shift
PORT="${PORT:-8000}"
BASE="http://${HOST}:${PORT}"
RUNS=3
CONFIGS=()
for a in "$@"; do [[ "$a" =~ ^[0-9]+$ ]] && RUNS="$a" || CONFIGS+=("$a"); done
PLAN=../results/a2/calib/plan.json
[ -f "$PLAN" ] || { echo "no $PLAN -- run jmeter/a2_calibrate.sh first"; exit 1; }
get() { python3 -c "import json;print(json.load(open('$PLAN'))['$1'])"; }
RATE=$(get rate_per_min); DUR=$(get duration_min); TIMEOUT=$(get timeout_s); PAUSE=$(get pause_s)
echo "plan: rate ${RATE}/min, ${DUR} min, timeout ${TIMEOUT} s, pause ${PAUSE} s, runs $RUNS"
mkdir -p ../results/a2/jtl ../results/a2/runs

for C in "${CONFIGS[@]}"; do
  # RUN_LIST="3b" redoes one run under a new tag; the JMeter seed stays the run number.
  for RUN in ${RUN_LIST:-$(seq 1 "$RUNS")}; do
    TAG="a2_${C}_run${RUN}"
    SEED="${RUN//[!0-9]/}"
    echo "=== $TAG: waiting for Machine A (ready-$TAG) ==="
    until curl -sf -m 10 "$BASE/healthz" | grep -q "\"run_id\":\"ready-$TAG\""; do sleep 10; done
    curl -sf "$BASE/healthz" | tee "../results/a2/runs/${TAG}.healthz.json"; echo
    curl -sf -H "X-Run-ID: ${TAG}:stats-before" "$BASE/stats" > "../results/a2/runs/${TAG}.stats_before.json"
    JTL="../results/a2/jtl/${TAG}.jtl"; rm -f "$JTL"
    echo "$(date '+%F %T %z') start $TAG" | tee -a ../results/a2/runs/machineB.log
    jmeter -n -t a2_speed.jmx \
      -Jhost="$HOST" -Jport="$PORT" \
      -JticketRatePerMin="$RATE" -JdurationMin="$DUR" -JpauseSec="$PAUSE" -JtimeoutMs="$((TIMEOUT * 1000))" \
      -Jseed="$SEED" -JrunId="$TAG" -JdataFile=../data/a2_speed_tickets.tsv \
      -Jjtl="$JTL" -j "../results/a2/jtl/${TAG}.jmeter.log"
    curl -sf -H "X-Run-ID: ${TAG}:stats-after" "$BASE/stats" > "../results/a2/runs/${TAG}.stats_after.json"
    echo "$(date '+%F %T %z') end   $TAG  samples=$(($(wc -l < "$JTL") - 1))  sent=$(grep -c 'A2SENT' "../results/a2/jtl/${TAG}.jmeter.log" || true)" \
      | tee -a ../results/a2/runs/machineB.log
  done
done
echo "Machine B done. Commit results/a2/jtl and results/a2/runs."
