#!/usr/bin/env bash
# Assignment 2 configurations under test. Sourced by the Machine A scripts.
#   top7b        qwen2.5:7b alone (the reference; Assignment 1 code path)
#   cascade400   llama3.2:3b -> qwen2.5:7b, tickets <= 400 chars go to 3b
#   cascade500   llama3.2:3b -> qwen2.5:7b, tickets <= 500 chars go to 3b
#   single-<tag> any other Assignment 1 model alone (only if it passes accuracy)
# The fallback pair (docs/a2/escalation_rule.md section 5) is selected with
# SMALL=llama3.2:1b in the environment; it is only used if the memory check
# shows 3b + 7b cannot stay resident together.

A2_LOG_IN_CONTAINER=/logs/a2_requests.jsonl
A2_LOG=results/logs/a2_requests.jsonl
A2_SMALL="${SMALL:-llama3.2:3b}"
A2_LARGE="qwen2.5:7b"

config_env() {
  case "$1" in
    top7b)        echo "TRIAGE_MODE=single OLLAMA_MODEL=$A2_LARGE" ;;
    cascade400)   echo "TRIAGE_MODE=cascade OLLAMA_MODEL=$A2_LARGE CASCADE_SMALL_MODEL=$A2_SMALL CASCADE_LARGE_MODEL=$A2_LARGE CASCADE_MAX_CHARS=400" ;;
    cascade500)   echo "TRIAGE_MODE=cascade OLLAMA_MODEL=$A2_LARGE CASCADE_SMALL_MODEL=$A2_SMALL CASCADE_LARGE_MODEL=$A2_LARGE CASCADE_MAX_CHARS=500" ;;
    single-*)     echo "TRIAGE_MODE=single OLLAMA_MODEL=${1#single-}" ;;
    *) echo "unknown config '$1' (top7b | cascade400 | cascade500 | single-<tag>)" >&2; return 1 ;;
  esac
}

# Models that must be listed by `ollama ps` before a run of this config starts.
config_models() {
  case "$1" in
    top7b)                 echo "$A2_LARGE" ;;
    cascade400|cascade500) echo "$A2_SMALL $A2_LARGE" ;;
    single-*)              echo "${1#single-}" ;;
  esac
}

# Bring the stack up on a configuration. $1 = config, $2 = RUN_ID to report on /healthz.
# Only the triage container is recreated; Ollama keeps its models and settings.
stack_up() {
  local envs; envs=$(config_env "$1") || return 1
  # shellcheck disable=SC2086
  env $envs LOG_PATH="$A2_LOG_IN_CONTAINER" RUN_ID="$2" docker compose up -d >/dev/null 2>&1
}

healthz_is() {  # $1 = expected run_id
  local h; h=$(curl -sf -m 10 http://localhost:8000/healthz 2>/dev/null) || return 1
  [[ "$h" == *"\"run_id\":\"$1\""* ]]
}

wait_healthz() {
  for _ in $(seq 1 150); do healthz_is "$1" && return 0; sleep 2; done
  return 1
}

wait_ollama() {
  for _ in $(seq 1 90); do curl -sf -m 5 http://localhost:11434/api/tags >/dev/null 2>&1 && return 0; sleep 2; done
  return 1
}

ollama_ps() { docker exec triage-ollama ollama ps 2>&1; }

ps_has_all() {  # $@ = models
  local ps; ps=$(ollama_ps)
  for m in "$@"; do grep -q "^$m " <<<"$ps" || return 1; done
}
