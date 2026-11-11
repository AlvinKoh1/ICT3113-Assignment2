#!/usr/bin/env bash
# Machine A side of the Assignment 2 speed test. Machine B runs
# jmeter/a2_machineB.sh with the same CONFIG and RUNS at the same time.
#
#   tools/a2_machineA.sh <config> [runs]       config: top7b | cascade400 | cascade500 | calib
#   tools/a2_machineA.sh top7b cascade400 cascade500    (several configs back to back, 3 runs each)
#   RUN_LIST=3b tools/a2_machineA.sh cascade500         (redo run 3 as run3b; Machine B must use the same RUN_LIST)
#
# For every run (brief, Step 4 "Each run"):
#   1. Bring the service up on the configuration (triage container only).
#   2. Restart the Ollama container -> prompt cache cleared, nothing loaded. Check it is up.
#   3. Preflight: versions, digests, Ollama settings unchanged (once per config).
#   4. Warm-up: the same 3 tickets every time (data/a2_warmup_rows.csv), tagged
#      warmup-<tag>, timings thrown away. W1 is short (-> small model in a cascade),
#      W2/W3 are long (-> large model), so a cascade warms BOTH models.
#   5. `ollama ps` must list every model of the configuration; abort otherwise.
#   6. Recreate the triage container with RUN_ID=ready-<tag>: /healthz now tells
#      Machine B it may call GET /stats and start JMeter.
#   7. Wait for Machine B's closing GET /stats (X-Run-ID <tag>:stats-after) in the
#      service log, then save `ollama ps`, docker stats samples and move on.
# "calib" prepares one S measurement instead: top7b, restart, warm-up, ready-calib,
# then waits for Machine B's jmeter/a2_calibrate.sh to finish.
set -uo pipefail
cd "$(dirname "$0")/.."
source tools/a2_config.sh

RUNS="${RUNS:-3}"
CONFIGS=()
for a in "$@"; do [[ "$a" =~ ^[0-9]+$ ]] && RUNS="$a" || CONFIGS+=("$a"); done
[ ${#CONFIGS[@]} -gt 0 ] || { echo "usage: tools/a2_machineA.sh <config...> [runs]"; exit 1; }
STATS_SEC="${STATS_SEC:-30}"
SWLOG="results/a2/env/machineA.log"
mkdir -p results/a2/env results/a2/runs
touch "$A2_LOG"

say() { echo "$(date '+%F %T %z')  $*" | tee -a "$SWLOG"; }
die() { say "ABORT: $*"; exit 1; }
STATS_PID=""
stop_stats() { [ -n "$STATS_PID" ] && kill "$STATS_PID" 2>/dev/null; STATS_PID=""; }
trap 'stop_stats' EXIT

prepare() {  # $1 config (real), $2 tag
  local C="$1" TAG="$2"
  say "[$TAG] service -> $C ($(config_env "$C"))"
  stack_up "$C" "prep-$TAG" || die "compose up failed"
  say "[$TAG] restarting Ollama (clears prompt cache; no model loaded)"
  docker restart triage-ollama >/dev/null || die "docker restart failed"
  wait_ollama || die "Ollama not up"
  wait_healthz "prep-$TAG" || die "service not up"
  ollama_ps > "results/a2/runs/${TAG}.ollama_ps_before_warmup.txt"
  say "[$TAG] warm-up (3 fixed tickets, timings discarded)"
  python3 tools/a2_send.py --rows data/a2_warmup_rows.csv --run-id "warmup-$TAG" 2>&1 | tee -a "$SWLOG" \
    || die "warm-up failed"
  local want; want=$(config_models "$C")
  # shellcheck disable=SC2086
  ps_has_all $want || { ollama_ps | tee -a "$SWLOG"; die "ollama ps does not list: $want"; }
  ollama_ps > "results/a2/runs/${TAG}.ollama_ps_ready.txt"
  say "[$TAG] ollama ps lists: $want"
  stack_up "$C" "ready-$TAG" || die "triage restart failed"
  wait_healthz "ready-$TAG" || die "service did not report ready"
  say "[$TAG] READY (/healthz run_id=ready-$TAG)"
}

done_tag() { grep -qF "\"run_id\": \"$1\"" "$A2_LOG" 2>/dev/null; }

for C in "${CONFIGS[@]}"; do
  if [[ "$C" == skip:* ]]; then
    # Tell Machine B this configuration will not run (cascade not feasible), and
    # wait until it acknowledges, so its loop moves on instead of waiting forever.
    S="${C#skip:}"
    done_tag "${S}:skip-ack" && { say "[$S] skip already acknowledged"; continue; }
    stack_up top7b "skip-$S" && wait_healthz "skip-$S" || die "could not signal skip for $S"
    say "[$S] signalled SKIP; waiting for Machine B to acknowledge"
    until done_tag "${S}:skip-ack"; do sleep 10; done
    say "[$S] skip acknowledged"
    continue
  fi
  if [ "$C" = "calib" ]; then
    TAG="a2_calib"
    done_tag "${TAG}:done" && { say "[$TAG] already done, skipping"; continue; }
    prepare top7b "$TAG"
    say "[$TAG] waiting for Machine B to finish the S calibration"
    until grep -qF "\"run_id\": \"${TAG}:done\"" "$A2_LOG"; do sleep 10; done
    say "[$TAG] calibration done"
    continue
  fi
  config_env "$C" >/dev/null || exit 1
  tools/a2_preflight.sh "$C" >/dev/null || die "preflight failed for $C (see results/a2/env/preflight_$C.txt)"
  say "[$C] preflight ok"
  # RUN_LIST="3b" redoes one run under a new tag (keep the original files).
  for RUN in ${RUN_LIST:-$(seq 1 "$RUNS")}; do
    TAG="a2_${C}_run${RUN}"
    done_tag "${TAG}:stats-after" && { say "[$TAG] already done, skipping"; continue; }
    prepare "$C" "$TAG"
    ( while true; do
        echo "== $(date '+%F %T %z')"
        docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}' 2>&1
        sleep "$STATS_SEC"
      done ) > "results/a2/runs/${TAG}.dockerstats.txt" &
    STATS_PID=$!
    say "[$TAG] waiting for Machine B (closing GET /stats tagged ${TAG}:stats-after)"
    until grep -qF "\"run_id\": \"${TAG}:stats-after\"" "$A2_LOG"; do sleep 15; done
    stop_stats
    ollama_ps > "results/a2/runs/${TAG}.ollama_ps_after.txt"
    say "[$TAG] DONE: $(grep -cF "\"run_id\": \"${TAG}\"" "$A2_LOG") log lines tagged $TAG"
  done
done
say "ALL DONE: ${CONFIGS[*]}"
