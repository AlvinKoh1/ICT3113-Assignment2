#!/usr/bin/env bash
# Machine A. Accuracy test (Step 4): every test-set ticket through POST /tickets,
# once per configuration.
#
# The A1 Machine A was not available for A2 (docs/a2/machine_change.md). Step 4
# only allows reusing A1 single-model records on the SAME machine, so on the A2
# machine the single models are re-run here too, and tools/a2_limits.py --source a2
# then derives the limits from this machine's qwen2.5:7b run.
#
#   tools/a2_accuracy_all.sh single-qwen2.5:7b single-llama3.2:3b single-llama3.2:1b single-qwen2.5:0.5b
#   tools/a2_accuracy_all.sh                 # cascade400 + cascade500, test set
#   SETS="test tune" tools/a2_accuracy_all.sh   # also the tuning set (comparison only)
set -uo pipefail
cd "$(dirname "$0")/.."
source tools/a2_config.sh
CONFIGS=("$@"); [ ${#CONFIGS[@]} -gt 0 ] || CONFIGS=(cascade400 cascade500)
SETS="${SETS:-test}"
mkdir -p results/a2/accuracy results/a2/env
for C in "${CONFIGS[@]}"; do
  F="${C//:/_}"   # file-name form: no colon (Windows checkouts)
  tools/a2_preflight.sh "accuracy_$F" >/dev/null || { echo "preflight failed for $C"; exit 1; }
  stack_up "$C" "acc-$C" && docker restart triage-ollama >/dev/null && wait_ollama && wait_healthz "acc-$C" \
    || { echo "stack did not come up for $C"; exit 1; }
  python3 tools/a2_send.py --rows data/a2_warmup_rows.csv --run-id "warmup-acc-$C" || exit 1
  # shellcheck disable=SC2046
  ps_has_all $(config_models "$C") || { ollama_ps; echo "models not resident for $C"; exit 1; }
  ollama_ps > "results/a2/accuracy/${F}.ollama_ps.txt"
  for S in $SETS; do
    python3 tools/a2_accuracy.py --config "$C" --set "$S" | tee "results/a2/accuracy/${F}_${S}.txt"
  done
  ollama_ps >> "results/a2/accuracy/${F}.ollama_ps.txt"
done
