"""Ollama client and the prompt/parse layer.

One synchronous HTTP call per ticket. No batching, no caching, no retries --
a retry would hide backend failure from the error rate we are trying to measure.
"""
import re
import httpx

from . import config

# Numbered list: small models follow "reply with the number" far more reliably
# than "reply with the exact label", and it makes parsing unambiguous.
_NUMBERED = "\n".join(
    f"{i + 1}. {c}" for i, c in enumerate(config.CATEGORIES)
)

PROMPT_TEMPLATE = f"""You are a complaint routing assistant at a financial services company.

Classify the customer complaint below into exactly one of these categories:
{_NUMBERED}

Reply with the category number and nothing else. No explanation.

Complaint:
\"\"\"{{narrative}}\"\"\"

Category number:"""

# Prompt version tag. Bump this whenever PROMPT_TEMPLATE changes; it is written
# to every log line so accuracy numbers stay attributable to a specific prompt.
PROMPT_VERSION = "v1"

_LOWER_CATEGORIES = {c.lower(): c for c in config.CATEGORIES}


def build_prompt(narrative: str) -> str:
    return PROMPT_TEMPLATE.format(narrative=narrative)


def parse_completion(text: str) -> str:
    """Map a raw completion onto one of the seven categories.

    Strict-ish: a leading number wins, then an exact name match anywhere in the
    text. Anything else is UNPARSED -- counted as a miss rather than guessed at,
    because silently defaulting to a category would inflate that category's
    recall.
    """
    stripped = text.strip()

    m = re.search(r"\d+", stripped)
    if m:
        idx = int(m.group()) - 1
        if 0 <= idx < len(config.CATEGORIES):
            return config.CATEGORIES[idx]

    lowered = stripped.lower()
    for name_lower, name in _LOWER_CATEGORIES.items():
        if name_lower in lowered:
            return name

    return config.UNPARSED


def classify(narrative: str, model: str) -> tuple[str, str, dict]:
    """Return (category, raw_completion, backend_metrics).

    backend_metrics carries Ollama's own timings so the report can separate
    time spent in the model from time spent in our service.
    """
    payload = {
        "model": model,
        "prompt": build_prompt(narrative),
        "stream": False,
        "options": {
            "temperature": config.OLLAMA_TEMPERATURE,
            "seed": config.OLLAMA_SEED,
            "num_predict": config.OLLAMA_NUM_PREDICT,
            "num_ctx": config.OLLAMA_NUM_CTX,
        },
    }

    with httpx.Client(timeout=config.OLLAMA_TIMEOUT_S) as client:
        resp = client.post(f"{config.OLLAMA_URL}/api/generate", json=payload)
        resp.raise_for_status()
        body = resp.json()

    raw = body.get("response", "")
    metrics = {
        # Ollama reports durations in nanoseconds.
        "ollama_total_ms": _ns_to_ms(body.get("total_duration")),
        "ollama_load_ms": _ns_to_ms(body.get("load_duration")),
        "ollama_prompt_eval_ms": _ns_to_ms(body.get("prompt_eval_duration")),
        "ollama_eval_ms": _ns_to_ms(body.get("eval_duration")),
        "prompt_eval_count": body.get("prompt_eval_count"),
        "eval_count": body.get("eval_count"),
    }
    return parse_completion(raw), raw, metrics


def _ns_to_ms(value) -> float | None:
    return round(value / 1e6, 2) if isinstance(value, (int, float)) else None


def backend_ready() -> bool:
    try:
        with httpx.Client(timeout=5) as client:
            return client.get(f"{config.OLLAMA_URL}/api/tags").status_code == 200
    except Exception:
        return False
