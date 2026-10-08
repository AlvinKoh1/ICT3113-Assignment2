#!/usr/bin/env bash
# Machine B side of the unattended load-test matrix (playbook Test B).
#
# Machine A runs tools/overnight_switch.sh, which switches the model, warms it,
# and then reports run_id "ready" on /healthz. For each model this waits for
# "<model> ready", then runs run_matrix.sh for that model. Machine A waits for
# the last run of each model before it switches to the next, so nobody has to
# stay up.
#
#   ./run_all_models.sh <service-host> [models...]
#   default: qwen2.5:0.5b llama3.2:1b llama3.2:3b qwen2.5:7b
#
# Keep run_matrix.sh's default RATES and RUNS: Machine A watches for the tag
# <model>_rate0.0667_run3 to know a model is finished.
set -euo pipefail
cd "$(dirname "$0")"

HOST="${1:?usage: run_all_models.sh <service-host> [models...]}"
shift
MODELS=("$@")
[ ${#MODELS[@]} -gt 0 ] || MODELS=(qwen2.5:0.5b llama3.2:1b llama3.2:3b qwen2.5:7b)
PORT="${PORT:-8000}"

for M in "${MODELS[@]}"; do
  echo "$(date '+%F %T') waiting for ${HOST} to report '$M ready' ..."
  until [ "$(curl -sf -m 10 "http://${HOST}:${PORT}/healthz" 2>/dev/null \
      | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["model"],d["run_id"])' 2>/dev/null)" = "$M ready" ]; do
    sleep 30
  done
  echo "$(date '+%F %T') $M is ready -- starting its matrix"
  ./run_matrix.sh "$HOST" "$M"
done

echo "$(date '+%F %T') all models done. Commit results/jtl/."
