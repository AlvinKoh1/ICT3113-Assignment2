#!/usr/bin/env bash
# Machine A side of the unattended load-test matrix (playbook Test B).
# Machine B runs jmeter/run_all_models.sh at the same time.
#
# For each model, in order:
#   1. Restart the stack on that model with an empty ticket store. Only the
#      triage-data volume is removed: the ollama-models volume (pinned digests)
#      and results/logs/requests.jsonl (evidence) are kept. Never use
#      `docker compose down -v` here -- it would delete the models too.
#   2. Check the model's digest against docs/model_pins.md; abort on mismatch.
#   3. Warm up (tools/warmup.py: 3 non-golden tickets tagged X-Run-ID: warmup).
#   4. Recreate only the triage container with RUN_ID=ready, which /healthz
#      reports. Machine B waits for "<model> ready" before it starts JMeter.
#   5. Wait until Machine B's last run for this model
#      (<model>_rate<LAST_RATE>_run<RUNS>) appears in the service log and the
#      log has then been quiet for IDLE_SEC, so no backlog is left over.
# Steps are timestamped in results/logs/model_switch.log; `docker stats` goes to
# results/logs/dockerstats_load_<model>.txt every STATS_SEC.
#
#   tools/overnight_switch.sh [models...]
#   default: qwen2.5:0.5b llama3.2:1b llama3.2:3b qwen2.5:7b
#
# LAST_RATE and RUNS must match what run_matrix.sh uses on Machine B.
set -uo pipefail
cd "$(dirname "$0")/.."

MODELS=("$@")
[ ${#MODELS[@]} -gt 0 ] || MODELS=(qwen2.5:0.5b llama3.2:1b llama3.2:3b qwen2.5:7b)
LAST_RATE="${LAST_RATE:-0.0667}"
RUNS="${RUNS:-3}"
IDLE_SEC="${IDLE_SEC:-300}"
STATS_SEC="${STATS_SEC:-60}"
KEEPWARM_SEC="${KEEPWARM_SEC:-600}"
BASE="http://localhost:8000"
OLLAMA="http://localhost:11434"
LOG="results/logs/requests.jsonl"
SWLOG="results/logs/model_switch.log"
VOLUME="ict3113-assignment1_triage-data"

say() { echo "$(date '+%F %T %z')  $*" | tee -a "$SWLOG"; }
die() { say "ABORT: $*"; exit 1; }

healthz() { curl -sf -m 10 "$BASE/healthz" 2>/dev/null; }

wait_healthz() {  # $1 = expected model, $2 = expected run_id
  for _ in $(seq 1 150); do
    H=$(healthz) && [[ "$H" == *"\"model\":\"$1\""* && "$H" == *"\"run_id\":\"$2\""* ]] && return 0
    sleep 2
  done
  return 1
}

STATS_PID=""
stop_stats() { [ -n "$STATS_PID" ] && kill "$STATS_PID" 2>/dev/null; STATS_PID=""; }
trap 'stop_stats; say "stopped (signal or exit)"' EXIT

say "start: models=${MODELS[*]} last_rate=$LAST_RATE runs=$RUNS idle=${IDLE_SEC}s"

for M in "${MODELS[@]}"; do
  SAFE="${M//[:\/]/_}"
  LAST_TAG="${SAFE}_rate${LAST_RATE}_run${RUNS}"

  # 1. Restart on this model, empty ticket store, models + log kept.
  say "[$M] stopping stack and clearing the ticket store ($VOLUME)"
  docker compose down >/dev/null 2>&1
  docker volume rm "$VOLUME" >/dev/null 2>&1
  docker volume ls -q | grep -qx "ict3113-assignment1_ollama-models" || die "ollama-models volume missing"
  say "[$M] starting stack (RUN_ID=warming)"
  OLLAMA_MODEL="$M" RUN_ID=warming docker compose up -d --build >/dev/null 2>&1 || die "docker compose up failed"
  wait_healthz "$M" warming || die "service did not come up on $M"

  # 2. Digest must match the frozen pin.
  DIGEST=$(curl -sf "$OLLAMA/api/tags" | python3 -c "import sys,json;print(next((m['digest'] for m in json.load(sys.stdin)['models'] if m['name']=='$M'),''))")
  [ -n "$DIGEST" ] || die "$M is not in the Ollama model store"
  grep -q "\`$M\` | \`$DIGEST\`" docs/model_pins.md || die "$M digest $DIGEST does not match docs/model_pins.md"
  say "[$M] digest ok: $DIGEST"

  # 3. Warm up.
  say "[$M] warming up"
  python3 tools/warmup.py --base "$BASE" --n 3 2>&1 | tee -a "$SWLOG" || die "warm-up failed"

  # 4. Tell Machine B it can start. Only the triage container is recreated;
  #    Ollama keeps the model loaded.
  OLLAMA_MODEL="$M" RUN_ID=ready docker compose up -d --no-deps triage >/dev/null 2>&1 || die "triage restart failed"
  wait_healthz "$M" ready || die "service did not report ready"
  say "[$M] READY -- /healthz reports model=$M run_id=ready"

  ( while true; do
      echo "== $(date '+%F %T %z')"
      docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}' 2>&1
      sleep "$STATS_SEC"
    done ) >> "results/logs/dockerstats_load_${SAFE}.txt" &
  STATS_PID=$!

  # Keep the model loaded (OLLAMA_KEEP_ALIVE=30m) until Machine B's first run
  # for this model shows up. A load-only request (no prompt) does no inference
  # and is not logged by the service.
  LAST_KEEP=$(date +%s)
  until grep -qF "\"run_id\": \"${SAFE}_rate" "$LOG" 2>/dev/null; do
    if [ $(( $(date +%s) - LAST_KEEP )) -ge "$KEEPWARM_SEC" ]; then
      curl -sf -m 60 "$OLLAMA/api/generate" -d "{\"model\":\"$M\",\"keep_alive\":\"30m\"}" >/dev/null \
        && say "[$M] still waiting for Machine B; kept model loaded"
      LAST_KEEP=$(date +%s)
    fi
    sleep 15
  done
  say "[$M] Machine B started (first ${SAFE}_rate* line in the log)"

  # 5. Wait for the last run, then for the log to go quiet.
  until grep -qF "\"run_id\": \"${LAST_TAG}\"" "$LOG" 2>/dev/null; do sleep 30; done
  say "[$M] last run $LAST_TAG started; waiting for ${IDLE_SEC}s of log silence"
  while [ $(( $(date +%s) - $(stat -c %Y "$LOG") )) -lt "$IDLE_SEC" ]; do sleep 15; done
  stop_stats
  say "[$M] DONE -- $(grep -cF "\"run_id\": \"${SAFE}_rate" "$LOG") log lines for this model"
done

say "ALL MODELS DONE. Stack left running on ${MODELS[-1]}."
