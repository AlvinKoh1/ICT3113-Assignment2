"""Ticket Triage Service -- Assignment 1 baseline.

BASELINE CONTRACT (do not "improve" this before Assignment 2):
  * POST /tickets is SYNCHRONOUS -- it does not return until Ollama has
    classified the ticket.
  * No caching of any kind. Identical narratives are re-classified.
  * No queue, no batching, no retries, no rate limiting.
  * Endpoints are declared with `def` (not `async def`), so FastAPI runs them in
    its threadpool. Concurrency is therefore bounded by the threadpool and by
    Ollama's own parallelism, not by an event loop. Record this in the report:
    it is central to the bottleneck argument.
"""
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import classifier, config, db, logging_setup

app = FastAPI(title="Ticket Triage Service", version="1.0.0-baseline")


@app.on_event("startup")
def _startup() -> None:
    db.init()
    logging_setup.init()


@app.on_event("shutdown")
def _shutdown() -> None:
    logging_setup.close()


class TicketIn(BaseModel):
    narrative: str = Field(..., min_length=1)
    # Optional: lets the load generator and the accuracy harness carry the
    # dataset row number through, so a stored ticket can be traced back to the
    # CSV row it came from. Not used for classification.
    row_id: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.post("/tickets")
def create_ticket(
    ticket: TicketIn,
    request: Request,
    x_model: str | None = Header(default=None, alias="X-Model"),
):
    """Classify one ticket, store it, return the assigned category.

    X-Model optionally overrides the configured model for this request. It
    exists so the accuracy harness can sweep candidate models without a restart;
    load tests should leave it unset and pin the model via OLLAMA_MODEL.
    """
    request_id = str(uuid.uuid4())
    model = x_model or config.OLLAMA_MODEL
    received_at = _now_iso()
    t0 = time.perf_counter()

    record = {
        "ts": received_at,
        "request_id": request_id,
        "endpoint": "POST /tickets",
        "model": model,
        "prompt_version": classifier.PROMPT_VERSION,
        "row_id": ticket.row_id,
        "narrative_chars": len(ticket.narrative),
        "client": request.client.host if request.client else None,
    }

    try:
        category, raw, metrics = classifier.classify(ticket.narrative, model)
    except Exception as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        record.update({
            "status": 502,
            "latency_ms": round(latency_ms, 2),
            "error": f"{type(exc).__name__}: {exc}",
        })
        logging_setup.log_request(record)
        return JSONResponse(
            status_code=502,
            content={"request_id": request_id, "error": "model backend failure"},
        )

    latency_ms = (time.perf_counter() - t0) * 1000
    ticket_id = db.insert_ticket(
        request_id=request_id,
        row_id=ticket.row_id,
        narrative=ticket.narrative,
        category=category,
        raw_completion=raw,
        model=model,
        latency_ms=latency_ms,
        created_at=received_at,
    )

    record.update({
        "status": 200,
        "latency_ms": round(latency_ms, 2),
        "ticket_id": ticket_id,
        "category": category,
        "raw_completion": raw.strip()[:200],
        "parsed": category != config.UNPARSED,
        **metrics,
    })
    logging_setup.log_request(record)

    return {
        "ticket_id": ticket_id,
        "request_id": request_id,
        "category": category,
        "model": model,
        "latency_ms": round(latency_ms, 2),
    }


@app.get("/search")
def search_tickets(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=200),
    request: Request = None,
):
    """Return stored tickets whose narrative contains q."""
    request_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    results = db.search(q, limit)
    latency_ms = (time.perf_counter() - t0) * 1000

    logging_setup.log_request({
        "ts": _now_iso(),
        "request_id": request_id,
        "endpoint": "GET /search",
        "status": 200,
        "latency_ms": round(latency_ms, 2),
        "query": q,
        "limit": limit,
        "result_count": len(results),
    })

    # Narratives are long; return a snippet so /search response size does not
    # dominate the measured transfer time.
    for r in results:
        r["snippet"] = r.pop("narrative")[:300]
    return {"request_id": request_id, "query": q, "count": len(results),
            "results": results}


@app.get("/stats")
def get_stats():
    """Counts of stored tickets by category."""
    request_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    payload = db.stats()
    latency_ms = (time.perf_counter() - t0) * 1000

    logging_setup.log_request({
        "ts": _now_iso(),
        "request_id": request_id,
        "endpoint": "GET /stats",
        "status": 200,
        "latency_ms": round(latency_ms, 2),
        "total": payload["total"],
    })
    return {"request_id": request_id, **payload}


@app.get("/healthz")
def healthz():
    """Readiness probe. Not part of the client-facing specification; used by
    docker compose and by the test scripts to wait for a warm backend."""
    return {"service": "ok", "ollama": classifier.backend_ready(),
            "model": config.OLLAMA_MODEL, "run_id": config.RUN_ID}
