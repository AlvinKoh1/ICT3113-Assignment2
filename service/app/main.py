"""Ticket Triage Service -- Assignment 1 baseline + Assignment 2 cascade.

Assignment 2 change (the only one): POST /tickets can run a two-model cascade
(TRIAGE_MODE=cascade, see app/cascade.py and docs/a2/escalation_rule.md). With
TRIAGE_MODE=single (the default) the code path is the Assignment 1 one.

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

from . import cascade, classifier, config, db, logging_setup

app = FastAPI(title="Ticket Triage Service", version="2.0.0-a2")


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


def _run_id(request: Request | None) -> str:
    """Run tag for the log line: the load generator's X-Run-ID header if sent,
    else the RUN_ID env var. Lets every JMeter run carry its own tag without a
    service restart (a restart via `make reset` would delete the log)."""
    if request is not None:
        hdr = request.headers.get("X-Run-ID")
        if hdr:
            return hdr
    return config.RUN_ID


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
    use_cascade = config.TRIAGE_MODE == "cascade" and not x_model
    model = x_model or config.OLLAMA_MODEL
    # What the caller (and GET /search) sees as "model": the model in single
    # mode, the configuration name in cascade mode -- never the answering model.
    public_model = config.CONFIG_ID if use_cascade else model
    received_at = _now_iso()
    t0 = time.perf_counter()

    record = {
        "ts": received_at,
        "request_id": request_id,
        "endpoint": "POST /tickets",
        "config": public_model if use_cascade else f"single-{model}",
        "model": model if not use_cascade else None,
        "prompt_version": classifier.PROMPT_VERSION,
        "row_id": ticket.row_id,
        "narrative_chars": len(ticket.narrative),
        "client": request.client.host if request.client else None,
        "run_id": _run_id(request),
    }

    try:
        if use_cascade:
            fields: dict = {}
            try:
                category, raw, fields = cascade.classify(ticket.narrative)
            except Exception:
                record.update({"mode": "cascade", "route_at_failure": cascade.route(ticket.narrative)})
                raise
            record.update(fields)
            record["model"] = fields["final_model"]
            metrics = {}
        else:
            category, raw, metrics = classifier.classify(ticket.narrative, model)
            record.update({"mode": "single", "final_model": model, "escalated": False})
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
        model=public_model,
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
        "model": public_model,
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
        "run_id": _run_id(request),
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
def get_stats(request: Request):
    """Counts of stored tickets by category."""
    request_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    payload = db.stats()
    latency_ms = (time.perf_counter() - t0) * 1000

    logging_setup.log_request({
        "ts": _now_iso(),
        "request_id": request_id,
        "endpoint": "GET /stats",
        "run_id": _run_id(request),
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
            "model": config.OLLAMA_MODEL, "mode": config.TRIAGE_MODE,
            "config": config.CONFIG_ID, "run_id": config.RUN_ID}
