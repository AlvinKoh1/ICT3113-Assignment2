#!/usr/bin/env bash
# Pull each candidate and record its exact tag + digest.
#
# The digest is what makes a result reproducible: `llama3.2:3b` is a moving
# target, `llama3.2:3b @ sha256:abc...` is not. Re-run this if you ever re-pull,
# and if a digest changes, re-run the measurements or say plainly in the report
# that they describe the earlier build.
set -euo pipefail

MODELS=("$@")
if [ ${#MODELS[@]} -eq 0 ]; then
  echo "usage: pin_models.sh qwen2.5:0.5b llama3.2:1b llama3.2:3b qwen2.5:7b"
  exit 1
fi

OUT="docs/model_pins.md"
{
  echo "# Model Pins"
  echo
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "Ollama version: $(ollama --version 2>&1 | head -1)"
  echo
  echo "| Tag | Digest | Parameters | Quantisation | Size |"
  echo "|---|---|---|---|---|"
} > "$OUT"

for M in "${MODELS[@]}"; do
  echo "pulling $M ..."
  ollama pull "$M" >/dev/null

  SHOW=$(ollama show "$M" 2>/dev/null || true)
  PARAMS=$(echo "$SHOW" | grep -i "parameters" | head -1 | awk '{print $NF}')
  QUANT=$(echo "$SHOW"  | grep -i "quantization" | head -1 | awk '{print $NF}')
  LINE=$(ollama list | awk -v m="$M" '$1==m {print $2, $3, $4}')
  DIGEST=$(echo "$LINE" | awk '{print $1}')
  SIZE=$(echo "$LINE"   | awk '{print $2, $3}')

  echo "| \`$M\` | \`$DIGEST\` | ${PARAMS:-?} | ${QUANT:-?} | ${SIZE:-?} |" >> "$OUT"
done

{
  echo
  echo "## Licences"
  echo
  echo "Record each model's licence here; Slide 12 needs them."
  echo
  for M in "${MODELS[@]}"; do echo "- \`$M\`: <licence, URL>"; done
} >> "$OUT"

echo
cat "$OUT"
echo
echo "wrote $OUT -- commit it."
