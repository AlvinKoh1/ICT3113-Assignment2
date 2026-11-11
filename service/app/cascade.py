"""Assignment 2: two-model cascade behind POST /tickets.

Escalation rule (docs/a2/escalation_rule.md, frozen before any A2 benchmark run):

    n = len(narrative)                       # characters, as received
    if n > CASCADE_MAX_CHARS:                # long ticket
        answer = LARGE(narrative)            # straight to the large model ("escalated")
    else:                                    # short ticket
        answer = SMALL(narrative)            # small model classifies
        if answer == UNPARSED:               # safety net: never accept an unusable answer
            answer = LARGE(narrative)        # ("escalated")

Both models get the unchanged Assignment 1 prompt (classifier.build_prompt) and
the same Ollama options. The caller only ever sees the category; which model
answered is written to the service log (final_model, escalated, route).
"""
from __future__ import annotations

import time

from . import classifier, config


def route(narrative: str) -> str:
    """'small' or 'large' for the first call. Pure function of the ticket text."""
    return "large" if len(narrative) > config.CASCADE_MAX_CHARS else "small"


def classify(narrative: str) -> tuple[str, str, dict]:
    """Return (category, raw_completion_of_final_model, log_fields)."""
    fields: dict = {
        "mode": "cascade",
        "small_model": config.CASCADE_SMALL_MODEL,
        "large_model": config.CASCADE_LARGE_MODEL,
        "cascade_max_chars": config.CASCADE_MAX_CHARS,
        "small_called": False,
        "large_called": False,
    }
    first = route(narrative)
    if first == "small":
        t0 = time.perf_counter()
        fields["stage"] = "small"
        cat, raw, m = classifier.classify(narrative, config.CASCADE_SMALL_MODEL)
        fields.update({
            "small_called": True,
            "small_category": cat,
            "small_latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            **{f"small_{k}": v for k, v in m.items()},
        })
        if cat != config.UNPARSED:
            fields.update({"final_model": config.CASCADE_SMALL_MODEL, "escalated": False,
                           "route": "short->small:accepted"})
            fields.pop("stage")
            return cat, raw, fields
        reason = "short->small:unparsed->large"
    else:
        reason = "long->large"

    t0 = time.perf_counter()
    fields["stage"] = "large"
    cat, raw, m = classifier.classify(narrative, config.CASCADE_LARGE_MODEL)
    fields.update({
        "large_called": True,
        "large_category": cat,
        "large_latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        **{f"large_{k}": v for k, v in m.items()},
        "final_model": config.CASCADE_LARGE_MODEL, "escalated": True, "route": reason,
    })
    fields.pop("stage")
    return cat, raw, fields
