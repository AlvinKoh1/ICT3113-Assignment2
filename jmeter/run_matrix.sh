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
    # A fresh RUN_ID per run lets reconcile.py separate this run's service-log
    # lines from every other run in the same file.
    echo "  (set RUN_ID=$TAG on the service before this run, or filter by time)"

    jmeter -n -t triage_load_test.jmx \
      -Jhost="$HOST" -Jport="$PORT" \
      -JticketRate="$RATE" -JsearchRate="$SEARCH_RATE" \
      -JdurationMin="$DURATION_MIN" \
      -Jseed="$RUN" \
      -Jjtl="$JTL" \
      -j "$LOG"

    echo "  -> $JTL"
    # Let queues drain and the CPU settle so run N+1 does not inherit run N's
    # backlog. Without this the three runs are not independent.
    echo "  cooling down 120s..."
    sleep 120
  done

  echo
  echo "--- aggregate: $MODEL @ ${RATE} req/s ---"
  python3 ../tools/analyze_jtl.py "${OUT}/${SAFE_MODEL}_rate${RATE}_run"*.jtl \
    --config-name "${MODEL} @ ${RATE} req/s" \
    --json-out "${OUT}/${SAFE_MODEL}_rate${RATE}_summary.json"
  echo
done

echo "Matrix complete. Commit results/jtl/ to the repository."
