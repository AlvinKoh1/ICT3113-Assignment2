#!/usr/bin/env bash
# Machine A. Step 2 memory check: can the small and the large model stay
# resident TOGETHER inside the unchanged Ollama container (4 CPUs, 8 GiB)?
# Run this BEFORE any other Assignment 2 measurement.
#
#   tools/a2_memory_check.sh                    # llama3.2:3b + qwen2.5:7b (primary pair)
#   SMALL=llama3.2:1b tools/a2_memory_check.sh  # fallback pair (only if the primary fails)
#
# Restarts Ollama (nothing loaded), puts the service in cascade mode, then sends
# 10 tickets alternating short (-> small model) and long (-> large model),
# capturing `ollama ps`, `docker stats` and the container's cgroup memory
# counters. Verdict (tools/a2_memcheck_eval.py): FIT only if
#   * `ollama ps` lists BOTH models after every ticket from the 2nd onwards,
#   * no ticket after each model's first call shows a reload (ollama_load_ms > 1 s),
#   * the cgroup oom / oom_kill counters do not move,
#   * prompt-eval speed stays >= 70 % of the same model running alone on THIS machine
#     (its A2 single-model accuracy run; the A1 run is only the fallback, different CPU)
#     (a slowdown would mean the weights are being paged out and back in),
#   * no request fails.
# Output: results/a2/memory/memory_check_<small>+<large>.txt / .json / .sends.json
set -uo pipefail
cd "$(dirname "$0")/.."
source tools/a2_config.sh
PAIR="${A2_SMALL}+${A2_LARGE}"
SAFE="${PAIR//[:\/]/_}"
OUT="results/a2/memory/memory_check_${SAFE}.txt"
RUN_ID="memcheck-${SAFE}"
mkdir -p results/a2/memory
exec > >(tee "$OUT") 2>&1

cg() {
  docker exec triage-ollama sh -c 'for f in memory.max memory.current memory.peak memory.events memory.swap.current; do if [ -f /sys/fs/cgroup/$f ]; then echo "--- $f"; cat /sys/fs/cgroup/$f; fi; done' 2>&1
}

echo "# A2 memory check  pair=$PAIR  $(date '+%F %T %z')  git=$(git rev-parse --short HEAD)"
stack_up cascade500 "$RUN_ID" || { echo "ABORT: compose up failed"; exit 1; }
docker restart triage-ollama >/dev/null && wait_ollama || { echo "ABORT: Ollama did not come back"; exit 1; }
wait_healthz "$RUN_ID" || { echo "ABORT: service not ready"; exit 1; }
echo "## container limits"
docker inspect triage-ollama --format 'NanoCpus={{.HostConfig.NanoCpus}} Memory={{.HostConfig.Memory}}'
echo "## ollama ps after restart (expect nothing loaded)"
ollama_ps
echo "## cgroup BEFORE"
cg

# 5 short (<= 400 chars: small model at either cut-off) and 5 long (> 500: large
# model) tickets from the speed list, interleaved short,long,short,long,...
ROWS=$(python3 tools/a2_pick_rows.py --short 5 --long 5)
echo "## tickets (short,long alternating): $ROWS"
python3 tools/a2_send.py --row-ids "$ROWS" --run-id "$RUN_ID" --ps \
  --json-out "results/a2/memory/memory_check_${SAFE}.sends.json"
echo "## docker stats"
docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}} ({{.MemPerc}})'
echo "## cgroup AFTER"
cg
echo "## ollama ps at end"
ollama_ps
echo "## Ollama log lines about memory / unloading during the check"
docker logs --since 30m triage-ollama 2>&1 | grep -iE 'unload|evict|out of memory|oom|insufficient|memory' | tail -20
python3 tools/a2_memcheck_eval.py --run-id "$RUN_ID" --small "$A2_SMALL" --large "$A2_LARGE" \
  --sends "results/a2/memory/memory_check_${SAFE}.sends.json" --cgroup-log "$OUT" \
  --json-out "results/a2/memory/memory_check_${SAFE}.json"
