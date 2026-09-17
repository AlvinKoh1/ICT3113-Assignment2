"""One JSON line per request, appended to LOG_PATH.

This file is the evidence base for the report: every number on a slide must be
derivable from it, and it must reconcile with the JMeter .jtl for the same run.
Writes are flushed per line so a killed container does not lose the tail.
"""
import json
import os
import threading
from typing import Any

from . import config

_lock = threading.Lock()
_fh = None


def init() -> None:
    global _fh
    os.makedirs(os.path.dirname(config.LOG_PATH), exist_ok=True)
    _fh = open(config.LOG_PATH, "a", buffering=1, encoding="utf-8")


def log_request(record: dict[str, Any]) -> None:
    if _fh is None:
        return
    record.setdefault("run_id", config.RUN_ID)
    line = json.dumps(record, ensure_ascii=False)
    with _lock:
        _fh.write(line + "\n")


def close() -> None:
    if _fh is not None:
        _fh.close()
