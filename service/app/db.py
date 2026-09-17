"""SQLite storage. Deliberately plain: one table, one connection per request,
no pooling and no cache. The baseline exists to be measured, not to be fast."""
import sqlite3
import os
from typing import Optional

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id     TEXT    NOT NULL,
    row_id         TEXT,
    narrative      TEXT    NOT NULL,
    category       TEXT    NOT NULL,
    raw_completion TEXT,
    model          TEXT    NOT NULL,
    latency_ms     REAL    NOT NULL,
    created_at     TEXT    NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def insert_ticket(
    request_id: str,
    row_id: Optional[str],
    narrative: str,
    category: str,
    raw_completion: str,
    model: str,
    latency_ms: float,
    created_at: str,
) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO tickets (request_id, row_id, narrative, category, "
            "raw_completion, model, latency_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (request_id, row_id, narrative, category, raw_completion, model,
             latency_ms, created_at),
        )
        return cur.lastrowid


def search(query: str, limit: int) -> list[dict]:
    """Substring match over stored narratives. No index, no full-text search --
    this is the straightforward implementation and one of the things
    Assignment 2 may want to revisit."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, row_id, category, model, created_at, narrative "
            "FROM tickets WHERE narrative LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
    return [dict(r) for r in rows]


def stats() -> dict:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT category, COUNT(*) AS n FROM tickets GROUP BY category"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS n FROM tickets").fetchone()["n"]
    by_category = {c: 0 for c in config.CATEGORIES}
    by_category[config.UNPARSED] = 0
    for r in rows:
        by_category[r["category"]] = r["n"]
    return {"total": total, "by_category": by_category}
