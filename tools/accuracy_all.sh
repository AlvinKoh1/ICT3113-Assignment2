#!/usr/bin/env bash
# Accuracy test (playbook Test C) for every candidate, unattended, on Machine A.
#
# For each model, in order:
#   1. Restart the stack on that model (OLLAMA_MODEL=<model>). Only the
#      triage-data volume is removed; the ollama-models volume (pinned digests)
#      and results/logs/requests.jsonl (evidence) are kept.
#   2. Check the model's digest against docs/model_pins.md; abort on mismatch.
#   3. Warm up (tools/warmup.py: 3 non-golden tickets, X-Run-ID: warmup).
#   4. Empty the ticket store again (triage container only; Ollama keeps the
#      model loaded) and start it with RUN_ID=accuracy_<model>, so the service
#      log lines are tagged and /stats counts only golden tickets.
#   5. tools/accuracy_harness.py --digest <digest>: 175 golden tickets, one at
#      a time. Console output -> results/logs/accuracy_<model>.txt,
#      /stats after the run -> results/accuracy/stats_<model>.json.
# Then, as a determinism check, the first model is run once more into
# results/accuracy/repeat/ (RUN_ID=accuracy_repeat_<model>).
# Steps are timestamped in results/logs/model_switch.log; docker stats every
# STATS_SEC into results/logs/dockerstats_accuracy_<model>.txt.
#
#   tools/accuracy_all.sh [models...]
#   default: qwen2.5:0.5b llama3.2:1b llama3.2:3b qwen2.5:7b
set -uo pipefail
cd "$(dirname "$0")/.."

MODELS=("$@")
[ ${#MODELS[@]} -gt 0 ] || MODELS=(qwen2.5:0.5b llama3.2:1b llama3.2:3b qwen2.5:7b)
STATS_SEC="${STATS_SEC:-60}"
BASE="http://localhost:8000"
OLLAMA="http://localhost:11434"
SWLOG="results/logs/model_switch.log"
VOLUME="ict3113-assignment1_triage-data"

say() { echo "$(date '+%F %T %z')  $*" | tee -a "$SWLOG"; }
die() { say "ABORT: $*"; exit 1; }

wait_healthz() {  # $1 = expected model, $2 = expected run_id
  for _ in $(seq 1 150); do
    H=$(curl -sf -m 10 "$BASE/healthz" 2>/dev/null) \
      && [[ "$H" == *"\"model\":\"$1\""* && "$H" == *"\"run_id\":\"$2\""* ]] && return 0
    sleep 2
  done
  return 1
}

STATS_PID=""
stop_stats() { [ -n "$STATS_PID" ] && kill "$STATS_PID" 2>/dev/null; STATS_PID=""; }
trap 'stop_stats; say "accuracy_all.sh stopped"' EXIT

run_model() {  # $1 = model, $2 = outdir, $3 = run tag prefix
  local M="$1" OUTDIR="$2" PREFIX="$3"
  local SAFE="${M//[:\/]/_}"
  local TAG="${PREFIX}_${SAFE}"

  say "[$M] ACCURACY ($TAG): stopping stack and clearing the ticket store"
  docker compose down >/dev/null 2>&1
  docker volume rm "$VOLUME" >/dev/null 2>&1
  docker volume ls -q | grep -qx "ict3113-assignment1_ollama-models" || die "ollama-models volume missing"
  OLLAMA_MODEL="$M" RUN_ID=warming docker compose up -d --build >/dev/null 2>&1 || die "docker compose up failed"
  wait_healthz "$M" warming || die "service did not come up on $M"

  local DIGEST
  DIGEST=$(curl -sf "$OLLAMA/api/tags" | python3 -c "import sys,json;print(next((m['digest'] for m in json.load(sys.stdin)['models'] if m['name']=='$M'),''))")
  [ -n "$DIGEST" ] || die "$M is not in the Ollama model store"
  grep -qF "\`$M\` | \`$DIGEST\`" docs/model_pins.md || die "$M digest $DIGEST does not match docs/model_pins.md"
  say "[$M] digest ok: $DIGEST"

  say "[$M] warming up"
  python3 tools/warmup.py --base "$BASE" --n 3 2>&1 | tee -a "$SWLOG" || die "warm-up failed"

  # Empty the store again so /stats after the run counts golden tickets only.
  docker compose rm -sf triage >/dev/null 2>&1
  docker volume rm "$VOLUME" >/dev/null 2>&1
  OLLAMA_MODEL="$M" RUN_ID="$TAG" docker compose up -d --no-deps triage >/dev/null 2>&1 || die "triage restart failed"
  wait_healthz "$M" "$TAG" || die "service did not report run_id=$TAG"
  say "[$M] ticket store empty, run_id=$TAG; starting accuracy harness"

  ( while true; do
      echo "== $(date '+%F %T %z')"
      docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}' 2>&1
      sleep "$STATS_SEC"
    done ) >> "results/logs/dockerstats_${PREFIX}_${SAFE}.txt" &
  STATS_PID=$!

  mkdir -p "$OUTDIR"
  python3 tools/accuracy_harness.py --base "$BASE" --model "$M" --digest "$DIGEST" --outdir "$OUTDIR" \
    2>&1 | tee "results/logs/${PREFIX}_${SAFE}.txt"
  local RC=${PIPESTATUS[0]}
  stop_stats
  curl -sf "$BASE/stats" > "$OUTDIR/stats_${SAFE}.json"
  [ "$RC" -eq 0 ] || die "accuracy harness failed for $M (exit $RC)"
  say "[$M] DONE: $(grep -m1 '^Overall accuracy' "results/logs/${PREFIX}_${SAFE}.txt")"
}

say "accuracy_all.sh start: models=${MODELS[*]}, then repeat ${MODELS[0]} (determinism)"
for M in "${MODELS[@]}"; do
  run_model "$M" results/accuracy accuracy
done
run_model "${MODELS[0]}" results/accuracy/repeat accuracy_repeat

say "ACCURACY ALL DONE."
