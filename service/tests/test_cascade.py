"""Offline tests for the Assignment 2 cascade (no Ollama needed).

    cd service && python -m pytest -q tests     (or: python tests/test_cascade.py)

classifier.classify is replaced by a stub, so these check the routing rule,
what the caller sees, and what the log records -- not model behaviour.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

TMP = tempfile.mkdtemp()
os.environ.update({"TRIAGE_MODE": "cascade", "CASCADE_MAX_CHARS": "500",
                   "DB_PATH": f"{TMP}/t.db", "LOG_PATH": f"{TMP}/log.jsonl"})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import classifier, main  # noqa: E402

CALLS = []


def fake(narrative, model):
    CALLS.append(model)
    if "garbage" in narrative and model == "llama3.2:3b":
        return "UNPARSED", "I cannot", {"ollama_total_ms": 1.0}
    return ("Mortgage" if model == "llama3.2:3b" else "Credit card"), "3", {"ollama_total_ms": 1.0}


classifier.classify = fake


def log_lines():
    return [json.loads(x) for x in Path(f"{TMP}/log.jsonl").read_text().splitlines() if x.strip()]


def test_cascade():
    with TestClient(main.app) as c:
        short, edge, long_ = "a" * 10, "b" * 500, "c" * 501
        for text, want_cat, want_calls in ((short, "Mortgage", ["llama3.2:3b"]),
                                           (edge, "Mortgage", ["llama3.2:3b"]),
                                           (long_, "Credit card", ["qwen2.5:7b"]),
                                           ("garbage " * 3, "Credit card", ["llama3.2:3b", "qwen2.5:7b"])):
            CALLS.clear()
            r = c.post("/tickets", json={"narrative": text, "row_id": "t"}, headers={"X-Run-ID": "unit"})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["category"] == want_cat
            assert body["model"] == "cascade-llama3.2:3b-qwen2.5:7b-le500"   # caller cannot see who answered
            assert CALLS == want_calls, CALLS
        L = [x for x in log_lines() if x["endpoint"] == "POST /tickets"]
        assert [x["route"] for x in L] == ["short->small:accepted", "short->small:accepted", "long->large",
                                           "short->small:unparsed->large"]
        assert [x["escalated"] for x in L] == [False, False, True, True]
        assert [x["final_model"] for x in L] == ["llama3.2:3b", "llama3.2:3b", "qwen2.5:7b", "qwen2.5:7b"]
        assert all(x["run_id"] == "unit" and x["config"] == body["model"] for x in L)
        # /search must not reveal the answering model either
        s = c.get("/search", params={"q": "a"}).json()
        assert {x["model"] for x in s["results"]} == {body["model"]}
        # X-Model still forces a single model (used for single-model accuracy runs)
        CALLS.clear()
        r = c.post("/tickets", json={"narrative": short}, headers={"X-Model": "qwen2.5:7b"})
        assert CALLS == ["qwen2.5:7b"] and r.json()["model"] == "qwen2.5:7b"
        assert log_lines()[-1]["mode"] == "single"
        h = c.get("/healthz").json()
        assert h["mode"] == "cascade" and h["config"] == body["model"]


if __name__ == "__main__":
    test_cascade()
    print("ok")
