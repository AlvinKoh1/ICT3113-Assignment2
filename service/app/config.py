"""Central configuration. Everything is env-overridable so the same image can be
run against each candidate model without a rebuild."""
import os

# --- Team / dataset -------------------------------------------------------
TEAM_NUMBER = int(os.getenv("TEAM_NUMBER", "9"))
ROW_START = TEAM_NUMBER * 1000
ROW_END = ROW_START + 999  # inclusive

# --- The seven categories, verbatim from the assignment brief -------------
CATEGORIES = [
    "Credit reporting",
    "Debt collection",
    "Mortgage",
    "Credit card",
    "Bank account or service",
    "Consumer loan",
    "Money transfer or service",
]

# Sentinel stored when the model returns something we cannot map to a category.
UNPARSED = "UNPARSED"

# --- Model backend --------------------------------------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
# Read timeout must be generous: CPU inference on a long narrative is slow and
# a client-side timeout would be recorded as an error rather than as latency.
OLLAMA_TIMEOUT_S = float(os.getenv("OLLAMA_TIMEOUT_S", "300"))
# Deterministic decoding: accuracy must be reproducible across the three runs.
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0"))
OLLAMA_SEED = int(os.getenv("OLLAMA_SEED", "42"))
# The answer is one short category name; capping output stops a chatty model
# from spending seconds on an explanation nobody reads.
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "16"))
# Context window. Narratives in the extract cap at 2000 chars (~550 tokens).
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "2048"))

# --- Assignment 2: configuration under test ---------------------------------
# TRIAGE_MODE=single  -> every ticket goes to OLLAMA_MODEL (the Assignment 1 path, unchanged).
# TRIAGE_MODE=cascade -> length rule in app/cascade.py (docs/a2/escalation_rule.md).
TRIAGE_MODE = os.getenv("TRIAGE_MODE", "single").strip().lower()
CASCADE_SMALL_MODEL = os.getenv("CASCADE_SMALL_MODEL", "llama3.2:3b")
CASCADE_LARGE_MODEL = os.getenv("CASCADE_LARGE_MODEL", "qwen2.5:7b")
CASCADE_MAX_CHARS = int(os.getenv("CASCADE_MAX_CHARS", "500"))
# Name returned in the "model" field of POST /tickets. In cascade mode it names
# the configuration, never the model that answered, so the caller cannot tell.
CONFIG_ID = os.getenv("CONFIG_ID") or (
    f"cascade-{CASCADE_SMALL_MODEL}-{CASCADE_LARGE_MODEL}-le{CASCADE_MAX_CHARS}"
    if TRIAGE_MODE == "cascade" else f"single-{OLLAMA_MODEL}")
if TRIAGE_MODE not in ("single", "cascade"):
    raise ValueError(f"TRIAGE_MODE must be single or cascade, not {TRIAGE_MODE!r}")

# --- Storage --------------------------------------------------------------
DB_PATH = os.getenv("DB_PATH", "/data/tickets.db")

# --- Instrumentation ------------------------------------------------------
LOG_PATH = os.getenv("LOG_PATH", "/logs/requests.jsonl")
# Free-text tag written into every log line so a log file can be tied back to
# the JMeter run that produced it.
RUN_ID = os.getenv("RUN_ID", "adhoc")
