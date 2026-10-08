#!/usr/bin/env bash
# Machine A side of the stress test (playbook Test D). Machine B runs
# jmeter/run_stress.sh at the same time.
#
#   1. Restart the stack on the model with an empty ticket store (only the
#      triage-data volume is removed; models volume and service log kept),
#      check the digest against docs/model_pins.md, warm up, empty the store
#      again, and report run_id "ready" on /healthz.
#   2. `docker stats` every STATS_SEC (playbook: 5 s) into
#      results/stress/dockerstats_stress_<model>.txt, until Machine B's last
#      ladder (stress_<model>_run<RUNS>) has appeared in the service log and
#      the log has then been quiet for IDLE_SEC.
#   3. Save `docker logs triage-ollama` to results/stress/ollama_log_stress_<model>.txt.
# Steps are timestamped in results/logs/model_switch.log.
#
#   tools/stress_monitor.sh [model]     default: llama3.2:3b
set -uo pipefail
cd "$(dirname "$0")/.."

M="${1:-llama3.2:3b}"
SAFE="${M//[:\/]/_}"
RUNS="${RUNS:-3}"
STATS_SEC="${STATS_SEC:-5}"
IDLE_SEC="${IDLE_SEC:-900}"        # longer than the ladder's 620 s end pause
KEEPWARM_SEC="${KEEPWARM_SEC:-600}"
BASE="http://localhost:8000"
OLLAMA="http://localhost:11434"
LOG="results/logs/requests.jsonl"
SWLOG="results/logs/model_switch.log"
VOLUME="ict3113-assignment1_triage-data"
OUT="results/stress"
mkdir -p "$OUT"

say() { echo "$(date '+%F %T %z')  $*" | tee -a "$SWLOG"; }
die() { say "ABORT: $*"; exit 1; }
wait_healthz() {
  for _ in $(seq 1 150); do
    H=$(curl -sf -m 10 "$BASE/healthz" 2>/dev/null) \
      && [[ "$H" == *"\"model\":\"$M\""* && "$H" == *"\"run_id\":\"$1\""* ]] && return 0
    sleep 2
  done
  return 1
}
STATS_PID=""
stop_stats() { [ -n "$STATS_PID" ] && kill "$STATS_PID" 2>/dev/null; STATS_PID=""; }
trap 'stop_stats; say "stress_monitor.sh stopped"' EXIT

say "[$M] STRESS: stopping stack and clearing the ticket store"
docker info >/dev/null 2>&1 || die "Docker daemon not reachable"
docker compose down >/dev/null 2>&1
docker volume rm "$VOLUME" >/dev/null 2>&1
docker volume ls -q | grep -qx "ict3113-assignment1_ollama-models" || die "ollama-models volume missing"
OLLAMA_MODEL="$M" RUN_ID=warming docker compose up -d --build >/dev/null 2>&1 || die "docker compose up failed"
wait_healthz warming || die "service did not come up on $M"

DIGEST=$(curl -sf "$OLLAMA/api/tags" | python3 -c "import sys,json;print(next((m['digest'] for m in json.load(sys.stdin)['models'] if m['name']=='$M'),''))")
grep -qF "\`$M\` | \`$DIGEST\`" docs/model_pins.md || die "$M digest '$DIGEST' does not match docs/model_pins.md"
say "[$M] digest ok: $DIGEST"

say "[$M] warming up"
python3 tools/warmup.py --base "$BASE" --n 3 2>&1 | tee -a "$SWLOG" || die "warm-up failed"
docker compose rm -sf triage >/dev/null 2>&1
docker volume rm "$VOLUME" >/dev/null 2>&1
OLLAMA_MODEL="$M" RUN_ID=ready docker compose up -d --no-deps triage >/dev/null 2>&1 || die "triage restart failed"
wait_healthz ready || die "service did not report ready"
say "[$M] READY for stress -- ticket store empty, /healthz model=$M run_id=ready"

( while true; do
    echo "== $(date '+%F %T %z')"
    docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}' 2>&1
    sleep "$STATS_SEC"
  done ) >> "$OUT/dockerstats_stress_${SAFE}.txt" &
STATS_PID=$!

LAST_KEEP=$(date +%s)
until grep -qF "\"run_id\": \"stress_${SAFE}_run" "$LOG" 2>/dev/null; do
  if [ $(( $(date +%s) - LAST_KEEP )) -ge "$KEEPWARM_SEC" ]; then
    curl -sf -m 60 "$OLLAMA/api/generate" -d "{\"model\":\"$M\",\"keep_alive\":\"30m\"}" >/dev/null \
      && say "[$M] still waiting for Machine B; kept model loaded"
    LAST_KEEP=$(date +%s)
  fi
  sleep 10
done
say "[$M] Machine B started the stress test (first stress_${SAFE}_run* line in the log)"

until grep -qF "\"run_id\": \"stress_${SAFE}_run${RUNS}\"" "$LOG" 2>/dev/null; do sleep 30; done
say "[$M] last ladder stress_${SAFE}_run${RUNS} started; waiting for ${IDLE_SEC}s of log silence"
while [ $(( $(date +%s) - $(stat -c %Y "$LOG") )) -lt "$IDLE_SEC" ]; do sleep 15; done
stop_stats
docker logs triage-ollama > "$OUT/ollama_log_stress_${SAFE}.txt" 2>&1
say "[$M] STRESS DONE -- $(grep -cF "\"run_id\": \"stress_${SAFE}_run" "$LOG") log lines; docker stats and Ollama log in $OUT/"
