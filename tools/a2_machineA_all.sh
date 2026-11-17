#!/usr/bin/env bash
# Machine A, everything in ONE command (Irfan). Start it, leave the PC on.
#
#   tools/a2_machineA_all.sh
#
# Runs, in order, committing and pushing after each stage:
#   1. rebuild the service on the A2 code, preflight (versions, digests, settings)
#   2. single-model accuracy test on THIS machine: qwen2.5:7b, llama3.2:3b,
#      llama3.2:1b, qwen2.5:0.5b on the 87 test tickets (~2 h), then the limits
#      from this machine's 7b run (tools/a2_limits.py --source a2). The A1
#      Machine A was not available, and Step 4 only allows reusing A1
#      single-model records on the same machine (docs/a2/machine_change.md).
#   3. memory check: llama3.2:3b + qwen2.5:7b; if they do not fit, the fallback
#      pair llama3.2:1b + qwen2.5:7b (docs/a2/escalation_rule.md section 5);
#      if neither fits, the cascade is reported infeasible and only 7b alone runs
#   4. accuracy test of the cascade at T=400 and T=500 (87 test tickets, ~2 h)
#   5. S calibration with Machine B          (Uwais's script does its side by itself)
#   6. speed test: 7b alone, cascade 400, cascade 500, 3 runs each (~7 h)
# Machine B (jmeter/a2_machineB_all.sh) can be started before or after this.
# Re-running after an interruption skips every stage and run already done.
# Total: about 12 hours. Keep the PC awake, plugged in and wired.
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p results/a2/env
LOG="results/a2/env/machineA_all.log"
exec > >(tee -a "$LOG") 2>&1
say() { echo "$(date '+%F %T %z')  $*"; }
die() { say "STOPPED: $*"; say "Screenshot this and send it to Alvin. Re-running the same command resumes."; exit 1; }
push() { tools/a2_push.sh "$@" || say "WARNING: push failed; results are committed locally"; }

say "=== A2 Machine A: start ($(git rev-parse --short HEAD))"
git pull -q --no-rebase --no-edit || say "WARNING: git pull failed; continuing on the local copy"

# 1. stack + preflight
say "1/6 rebuilding the service"
docker compose up -d --build >/dev/null 2>&1 || die "docker compose up --build failed"
tools/a2_preflight.sh initial >/dev/null || die "preflight failed: see results/a2/env/preflight_initial.txt"
say "1/6 preflight OK"

# 2. single-model accuracy on this machine (7b first: it sets the limits), then the limits
for M in qwen2.5:7b llama3.2:3b llama3.2:1b qwen2.5:0.5b; do
  F="single-${M//:/_}"
  if [ -f "results/a2/accuracy/${F}_test.json" ]; then say "2/6 accuracy $M alone already done"; continue; fi
  say "2/6 accuracy test $M alone on this machine"
  tools/a2_accuracy_all.sh "single-$M" >/dev/null 2>&1
  [ -f "results/a2/accuracy/${F}_test.json" ] || die "accuracy test $M alone did not finish: see results/a2/accuracy/${F}_test.txt"
  say "2/6 $(tail -n 2 "results/a2/accuracy/${F}_test.txt" | head -n 1)"
done
python3 tools/a2_limits.py --source a2 > results/a2/accuracy/limits_a2.txt 2>&1 \
  || die "limits from this machine's 7b run failed: see results/a2/accuracy/limits_a2.txt"
say "2/6 $(sed -n 2,3p results/a2/accuracy/limits_a2.txt | tr '\n' ' ')"
grep -q "^WARNING" results/a2/accuracy/limits_a2.txt && say "2/6 $(grep '^WARNING' results/a2/accuracy/limits_a2.txt) -- tell Alvin; the speed test below still runs"
push "A2 single-model accuracy re-run on the A2 machine; limits from its 7b run" \
  results/a2/accuracy docs/a2/limits.json results/a2/env results/logs/a2_requests.jsonl

# 3. memory check (with the pre-declared fallback)
verdict() { python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['verdict'])" "$1" 2>/dev/null; }
PRIMARY="results/a2/memory/memory_check_llama3.2_3b+qwen2.5_7b.json"
FALLBACK="results/a2/memory/memory_check_llama3.2_1b+qwen2.5_7b.json"
[ -f "$PRIMARY" ] || { say "3/6 memory check: 3b + 7b"; tools/a2_memory_check.sh >/dev/null 2>&1; }
CASCADE=yes
if [ "$(verdict "$PRIMARY")" = "FIT" ]; then
  export SMALL=llama3.2:3b
  say "3/6 memory check: 3b + 7b FIT"
else
  say "3/6 memory check: 3b + 7b $(verdict "$PRIMARY" || echo 'FAILED TO RUN'); trying the fallback pair 1b + 7b"
  [ -f "$FALLBACK" ] || SMALL=llama3.2:1b tools/a2_memory_check.sh >/dev/null 2>&1
  if [ "$(verdict "$FALLBACK")" = "FIT" ]; then
    export SMALL=llama3.2:1b
    say "3/6 fallback 1b + 7b FIT: the cascade runs with llama3.2:1b"
  else
    CASCADE=no
    say "3/6 no pair fits: the cascade is not feasible on this machine; only qwen2.5:7b alone will be speed-tested"
  fi
fi
push "A2 memory check (Machine A)" results/a2/memory results/a2/env results/logs/a2_requests.jsonl

# 4. cascade accuracy test
if [ "$CASCADE" = yes ]; then
  for C in cascade400 cascade500; do
    if [ -f "results/a2/accuracy/${C}_test.json" ]; then say "4/6 accuracy $C already done"; continue; fi
    say "4/6 accuracy test $C (about 1 h)"
    tools/a2_accuracy_all.sh "$C" >/dev/null 2>&1
    [ -f "results/a2/accuracy/${C}_test.json" ] || die "accuracy test $C did not finish: see results/a2/accuracy/${C}_test.txt"
    say "4/6 $(tail -n 3 "results/a2/accuracy/${C}_test.txt" | head -n 1)"
  done
  push "A2 accuracy test: cascade T=400 and T=500 on the test set" results/a2/accuracy results/a2/env results/logs/a2_requests.jsonl
fi

# 5. calibration (waits for Machine B)
say "5/6 S calibration: waiting for Machine B (jmeter/a2_machineB_all.sh) if it is not running yet"
tools/a2_machineA.sh calib >/dev/null 2>&1 || die "calibration failed: see results/a2/env/machineA.log"
say "5/6 calibration done"
push "A2 calibration (Machine A side)" results/a2/env results/logs/a2_requests.jsonl

# 6. speed test
if [ "$CASCADE" = yes ]; then CONFIGS=(top7b cascade400 cascade500); else CONFIGS=(top7b skip:cascade400 skip:cascade500); fi
say "6/6 speed test: ${CONFIGS[*]} (about 7 h; progress in results/a2/env/machineA.log)"
tools/a2_machineA.sh "${CONFIGS[@]}" >/dev/null 2>&1 || die "speed test stopped: see results/a2/env/machineA.log"
push "A2 speed test: service log + env (Machine A)" results/a2/env results/a2/runs results/logs/a2_requests.jsonl
[ -f results/a2/accuracy/singles_needing_speed_test.json ] \
  && say "NOTE: $(cat results/a2/accuracy/singles_needing_speed_test.json | tr -d '\n ') also passed both limits on this machine and still need a speed test -- tell Alvin"
say "=== ALL DONE on Machine A. Post 'Machine A done' in the group chat."
