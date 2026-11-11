#!/usr/bin/env bash
# Machine A. Accuracy test for the cascade at both settings (Step 4).
# Single models are NOT re-run: their Assignment 1 records are reused, test rows
# only (tools/a2_limits.py), which the brief allows when digest, prompt, Ollama
# version and machine are unchanged -- tools/a2_preflight.sh records that.
#
#   tools/a2_accuracy_all.sh                 # cascade400 + cascade500, test set
#   SETS="test tune" tools/a2_accuracy_all.sh   # also the tuning set (comparison only)
#   tools/a2_accuracy_all.sh top7b           # optional reproducibility check of the 7b on the test set
set -uo pipefail
cd "$(dirname "$0")/.."
source tools/a2_config.sh
CONFIGS=("$@"); [ ${#CONFIGS[@]} -gt 0 ] || CONFIGS=(cascade400 cascade500)
SETS="${SETS:-test}"
mkdir -p results/a2/accuracy results/a2/env
for C in "${CONFIGS[@]}"; do
  tools/a2_preflight.sh "accuracy_$C" >/dev/null || { echo "preflight failed for $C"; exit 1; }
  stack_up "$C" "acc-$C" && docker restart triage-ollama >/dev/null && wait_ollama && wait_healthz "acc-$C" \
    || { echo "stack did not come up for $C"; exit 1; }
  python3 tools/a2_send.py --rows data/a2_warmup_rows.csv --run-id "warmup-acc-$C" || exit 1
  # shellcheck disable=SC2046
  ps_has_all $(config_models "$C") || { ollama_ps; echo "models not resident for $C"; exit 1; }
  ollama_ps > "results/a2/accuracy/${C}.ollama_ps.txt"
  for S in $SETS; do
    python3 tools/a2_accuracy.py --config "$C" --set "$S" | tee "results/a2/accuracy/${C}_${S}.txt"
  done
  ollama_ps >> "results/a2/accuracy/${C}.ollama_ps.txt"
done
