#!/usr/bin/env bash
# Run the load-test matrix: every arrival rate x three runs, for one model.
#
# Run this ON THE LOAD GENERATOR MACHINE. The service and Ollama must be on a
# different host -- a co-hosted load generator steals CPU from the service and
# the latency numbers become fiction.
#
# Usage:
#   ./run_matrix.sh <service-host> <model-tag> "0.25 0.5 1.0 2.0"
set -euo pipefail

HOST="${1:?usage: run_matrix.sh <service-host> <model-tag> [rates]}"
MODEL="${2:?model tag, e.g. llama3.2:1b -- must already be set as OLLAMA_MODEL on the service}"
RATES="${3:-0.25 0.5 1.0 2.0}"

DURATION_MIN="${DURATION_MIN:-10}"
SEARCH_RATIO="${SEARCH_RATIO:-0.2}"   # search rate as a fraction of ticket rate
RUNS="${RUNS:-3}"
# Seconds with no new arrivals at the end of each run so in-flight requests
# finish instead of being cut off (JMeter closes open sockets when the schedule
# ends, which shows up as fake errors). Doubles as the cooldown between runs.
DRAIN_SEC="${DRAIN_SEC:-120}"
PORT="${PORT:-8000}"

SAFE_MODEL="${MODEL//[:\/]/_}"
OUT="../results/jtl"
mkdir -p "$OUT"

echo "Service host : $HOST:$PORT"
echo "Model        : $MODEL"
echo "Rates        : $RATES req/s"
echo "Duration     : ${DURATION_MIN} min   Runs: $RUNS"
echo

# Confirm the service is actually running the model we are about to attribute
# results to. Mislabelled runs are unrecoverable after the fact.
ACTUAL=$(curl -sf "http://${HOST}:${PORT}/healthz" | python3 -c 'import sys,json;print(json.load(sys.stdin)["model"])')
if [[ "$ACTUAL" != "$MODEL" ]]; then
  echo "ABORT: service reports model '$ACTUAL' but you asked for '$MODEL'."
  echo "Set OLLAMA_MODEL=$MODEL and restart the stack before running."
  exit 1
fi

for RATE in $RATES; do
  SEARCH_RATE=$(python3 -c "print(round($RATE * $SEARCH_RATIO, 4))")
  for RUN in $(seq 1 "$RUNS"); do
    TAG="${SAFE_MODEL}_rate${RATE}_run${RUN}"
    JTL="${OUT}/${TAG}.jtl"
    LOG="${OUT}/${TAG}.jmeter.log"
    rm -f "$JTL"

    echo "=== $TAG ==="
    # The plan sends X-Run-ID=$TAG on every request and the service writes it
    # into each log line, so `reconcile.py --run-id $TAG` separates this run
    # from every other run in the same log. No service restart needed.

    jmeter -n -t triage_load_test.jmx \
      -Jhost="$HOST" -Jport="$PORT" \
      -JticketRate="$RATE" -JsearchRate="$SEARCH_RATE" \
      -JdurationMin="$DURATION_MIN" \
      -Jseed="$RUN" -JrunId="$TAG" -JdrainSec="$DRAIN_SEC" \
      -Jjtl="$JTL" \
      -j "$LOG"

    echo "  -> $JTL"
    # Queues drained during the plan's pause(); a short settle on top so run
    # N+1 does not inherit run N's backlog.
    sleep 10
  done

  echo
  echo "--- aggregate: $MODEL @ ${RATE} req/s ---"
  python3 ../tools/analyze_jtl.py "${OUT}/${SAFE_MODEL}_rate${RATE}_run"*.jtl \
    --config-name "${MODEL} @ ${RATE} req/s" \
    --json-out "${OUT}/${SAFE_MODEL}_rate${RATE}_summary.json"
  echo
done

echo "Matrix complete. Commit results/jtl/ to the repository."
