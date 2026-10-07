#!/usr/bin/env bash
# Pull each candidate into the Ollama container and record its exact tag + digest.
#
# The digest is what makes a result reproducible: `llama3.2:3b` is a moving
# target, `llama3.2:3b @ sha256:abc...` is not. Re-run this if you ever re-pull,
# and if a digest changes, re-run the measurements or say plainly in the report
# that they describe the earlier build.
#
# Ollama runs inside Docker, so pulls go through `docker exec` and metadata is
# read from Ollama's HTTP API (which also returns the full sha256 digest; the
# CLI's `ollama list` only shows a 12-character prefix).
set -euo pipefail

MODELS=("$@")
if [ ${#MODELS[@]} -eq 0 ]; then
  echo "usage: pin_models.sh qwen2.5:0.5b llama3.2:1b llama3.2:3b qwen2.5:7b"
  exit 1
fi

CONTAINER="${OLLAMA_CONTAINER:-triage-ollama}"
API="${OLLAMA_API:-http://localhost:11434}"
OUT="docs/model_pins.md"

for M in "${MODELS[@]}"; do
  echo "pulling $M ..."
  docker exec "$CONTAINER" ollama pull "$M" >/dev/null
done

VERSION=$(curl -sf "$API/api/version" | python3 -c 'import sys,json;print(json.load(sys.stdin)["version"])')
TAGS=$(curl -sf "$API/api/tags")

python3 - "$OUT" "$VERSION" "${MODELS[@]}" <<PY
import json, sys, datetime
out, version, models = sys.argv[1], sys.argv[2], sys.argv[3:]
tags = {m["name"]: m for m in json.loads('''$TAGS''')["models"]}
lines = [
    "# Model Pins", "",
    f"Generated: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
    f"Ollama version: {version} (container \`$CONTAINER\`)", "",
    "| Tag | Digest (sha256) | Parameters | Quantisation | Size |",
    "|---|---|---|---|---|",
]
missing = []
for m in models:
    t = tags.get(m)
    if not t:
        missing.append(m); continue
    d = t.get("details", {})
    lines.append(f"| \`{m}\` | \`{t['digest']}\` | {d.get('parameter_size','?')} | "
                 f"{d.get('quantization_level','?')} | {t['size']/1e9:.2f} GB |")
lines += ["", "## Licences", "", "Record each model's licence here; Slide 12 needs them.", ""]
lines += [f"- \`{m}\`: <licence, URL>" for m in models]
open(out, "w").write("\n".join(lines) + "\n")
if missing:
    sys.exit(f"ERROR: not found in Ollama after pull: {missing}")
PY

echo
cat "$OUT"
echo
echo "wrote $OUT -- fill in the licence lines, then commit it."
