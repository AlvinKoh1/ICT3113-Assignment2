#!/usr/bin/env bash
# Machine A. Record software versions, model digests and Ollama settings, and
# fail if anything differs from the Assignment 1 freeze (docs/model_pins.md).
# Run once before the first A2 run and again before each configuration
# (a2_machineA.sh does the latter itself).
#
#   tools/a2_preflight.sh [label]      -> results/a2/env/preflight_<label>.txt
set -uo pipefail
cd "$(dirname "$0")/.."
LABEL="${1:-$(date +%Y%m%d-%H%M%S)}"
OUT="results/a2/env/preflight_${LABEL}.txt"
mkdir -p results/a2/env
FAIL=0
{
  echo "# A2 preflight  $(date '+%F %T %z')  label=$LABEL  git=$(git rev-parse --short HEAD)"
  echo "## host";            uname -a; nproc; free -h 2>/dev/null | head -2
  echo "## cpu";             (lscpu 2>/dev/null | grep -E "Model name|^CPU\(s\)") || grep -m1 "model name" /proc/cpuinfo
  echo "## docker";          docker --version; docker compose version
  echo "## ollama version";  docker exec triage-ollama ollama --version 2>&1
  echo "## ollama container env (inference settings, recorded once, held constant)"
  docker inspect triage-ollama --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E '^OLLAMA_' | sort
  echo "## ollama container limits"
  docker inspect triage-ollama --format 'NanoCpus={{.HostConfig.NanoCpus}} Memory={{.HostConfig.Memory}} Image={{.Config.Image}}'
  echo "## runner flags last seen in the Ollama log (threads / parallel / ctx-size)"
  docker logs triage-ollama 2>&1 | grep -oE -- '--(threads|parallel|ctx-size) [0-9]+' | sort | uniq -c
  echo "## triage service settings"
  docker inspect triage-service --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E '^(OLLAMA_|TRIAGE_|CASCADE_|LOG_PATH|RUN_ID)' | sort
  echo "## model digests vs docs/model_pins.md"
} > "$OUT" 2>&1

TAGS=$(curl -sf http://localhost:11434/api/tags) || { echo "Ollama not reachable" >> "$OUT"; FAIL=1; }
for M in qwen2.5:0.5b llama3.2:1b llama3.2:3b qwen2.5:7b; do
  D=$(python3 -c "import sys,json;print(next((m['digest'] for m in json.load(sys.stdin)['models'] if m['name']=='$M'),'MISSING'))" <<<"$TAGS")
  if grep -q "\`$M\` | \`$D\`" docs/model_pins.md; then echo "ok    $M $D" >> "$OUT"
  else echo "FAIL  $M $D (does not match docs/model_pins.md)" >> "$OUT"; FAIL=1; fi
done
docker exec triage-ollama ollama --version 2>&1 | grep -q '0.5.7' || { echo "FAIL  Ollama version is not 0.5.7" >> "$OUT"; FAIL=1; }
docker inspect triage-ollama --format '{{.HostConfig.NanoCpus}} {{.HostConfig.Memory}}' | grep -q '^4000000000 8589934592$' \
  || { echo "FAIL  Ollama container limits are not 4 CPUs / 8 GiB" >> "$OUT"; FAIL=1; }
grep -qi "10900K" /proc/cpuinfo 2>/dev/null || echo "WARN  CPU is not the Assignment 1 i9-10900K: single-model accuracy from A1 can only be reused on the same machine" >> "$OUT"
echo "## verdict: $([ $FAIL = 0 ] && echo OK || echo FAIL)" >> "$OUT"
cat "$OUT"
exit $FAIL
