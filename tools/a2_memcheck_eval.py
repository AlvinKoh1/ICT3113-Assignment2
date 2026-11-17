#!/usr/bin/env python3
"""Verdict for tools/a2_memory_check.sh (see that script for the criteria)."""
from __future__ import annotations

import argparse
import json
import re
import statistics as st
from pathlib import Path

from a2_common import ROOT, iter_log


def prefill_rate(r, prefix=""):
    n, ms = r.get(f"{prefix}prompt_eval_count"), r.get(f"{prefix}ollama_prompt_eval_ms")
    return n / ms * 1000 if n and ms else None


def a1_rate(model):
    """Median prompt-eval tokens/s of the model in its Assignment 1 accuracy run (sequential, alone)."""
    v = [prefill_rate(r) for r in iter_log(ROOT / "results/logs/requests.jsonl")
         if r.get("endpoint") == "POST /tickets" and r.get("model") == model
         and str(r.get("run_id", "")).startswith("accuracy_") and r.get("status") == 200]
    v = [x for x in v if x]
    return st.median(v) if v else None


def banded_median(pairs, lo=None, hi=None, min_n=5):
    """Median rate over (prompt tokens, rate) pairs whose token count lies in [lo, hi].

    Prompt-eval tokens/s depends on prompt length (A1 records: short tickets prefill ~1.4x
    faster per token than long ones), and the memory check sends only SHORT tickets to the
    small model and only LONG ones to the large model. Comparing with the model's median over
    all lengths would bias the ratio (7b: ~0.82 before any paging, against a 0.7 cut-off), so
    the reference uses the same token range. Falls back to all lengths if fewer than min_n match."""
    pairs = [(n, x) for n, x in pairs if x]
    band = [x for n, x in pairs if lo is not None and lo <= n <= hi]
    if len(band) >= min_n:
        return st.median(band), f"{len(band)} tickets of {lo}-{hi} prompt tokens"
    return (st.median(x for _, x in pairs), f"all {len(pairs)} tickets (too few in {lo}-{hi} tokens)") if pairs else (None, "")


def same_machine_pairs(model):
    """(prompt tokens, prompt-eval tokens/s) of the model alone in its A2 single-model accuracy run
    on THIS machine (tools/a2_accuracy_all.sh single-<tag>, run before the memory check). The A1
    rate was measured on a different CPU (docs/a2/machine_change.md), so it is only the fallback."""
    return [(r.get("prompt_eval_count") or 0, prefill_rate(r)) for r in iter_log(ROOT / "results/logs/a2_requests.jsonl")
            if r.get("endpoint") == "POST /tickets" and r.get("model") == model
            and r.get("run_id") == f"a2acc_single-{model}_test" and r.get("status") == 200]


def a1_pairs(model):
    return [(r.get("prompt_eval_count") or 0, prefill_rate(r)) for r in iter_log(ROOT / "results/logs/requests.jsonl")
            if r.get("endpoint") == "POST /tickets" and r.get("model") == model
            and str(r.get("run_id", "")).startswith("accuracy_") and r.get("status") == 200]


def reference_rate(model, lo=None, hi=None):
    r, how = banded_median(same_machine_pairs(model), lo, hi)
    if r:
        return r, f"A2 single-model run, this machine; {how}"
    r, how = banded_median(a1_pairs(model), lo, hi)
    return r, f"A1 accuracy run (different machine); {how}"


def kv(block):
    return {k: int(v) for k, v in (ln.split() for ln in block.strip().splitlines())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--small", required=True)
    ap.add_argument("--large", required=True)
    ap.add_argument("--sends", required=True)
    ap.add_argument("--cgroup-log", required=True)
    ap.add_argument("--json-out", required=True)
    a = ap.parse_args()

    logs = [r for r in iter_log(ROOT / "results/logs/a2_requests.jsonl")
            if r.get("run_id") == a.run_id and r.get("endpoint") == "POST /tickets"]
    sends = json.loads(Path(a.sends).read_text(encoding="utf-8"))["tickets"]
    checks, notes = {}, []

    # 1. both models listed after every ticket from the 2nd on
    listed = [all(re.search(rf"^{re.escape(m)}\s", s.get("ollama_ps") or "", re.M) for m in (a.small, a.large))
              for s in sends[1:]]
    checks["both_listed_after_each_ticket"] = bool(listed) and all(listed)
    notes.append(f"`ollama ps` listed both models after {sum(listed)}/{len(listed)} tickets (from the 2nd on)")

    # 2. no reload after each model's first call; collect prefill speeds
    seen, reloads, per_model = set(), [], {a.small: [], a.large: []}
    for r in logs:
        for pfx, m in (("small_", a.small), ("large_", a.large)):
            load = r.get(f"{pfx}ollama_load_ms")
            if load is None:
                continue
            first = m not in seen
            if not first and load > 1000:
                reloads.append((r.get("row_id"), m, load))
            seen.add(m)
            rate = prefill_rate(r, pfx)
            if rate and not first:
                per_model[m].append((r.get(f"{pfx}prompt_eval_count") or 0, rate))
    checks["no_reload"] = not reloads and len(seen) == 2
    notes.append(f"reloads after first load: {reloads or 'none'}; models called: {sorted(seen)}")

    # 3. OOM counters unchanged
    txt = Path(a.cgroup_log).read_text(encoding="utf-8", errors="replace")
    ev = re.findall(r"--- memory\.events\n((?:\w+ \d+\n)+)", txt)
    if len(ev) >= 2:
        b, e = kv(ev[0]), kv(ev[-1])
        moved = {k: e.get(k, 0) - b.get(k, 0) for k in set(b) | set(e) if e.get(k, 0) != b.get(k, 0)}
        checks["no_oom"] = not any(k in moved for k in ("oom", "oom_kill"))
        notes.append(f"cgroup memory.events change: {moved or 'none'}")
    else:
        checks["no_oom"] = None
        notes.append("cgroup memory.events not readable -- check `docker events --filter event=oom` by hand")
    peak = re.findall(r"--- memory\.peak\n(\d+)", txt)
    cur = re.findall(r"--- memory\.current\n(\d+)", txt)
    mx = re.findall(r"--- memory\.max\n(\S+)", txt)

    # 4. prefill speed vs the model running alone (paging would show up as a slowdown)
    speed = {}
    for m, pv in per_model.items():
        v = [x for _, x in pv]
        lo, hi = (min(n for n, _ in pv), max(n for n, _ in pv)) if pv else (None, None)
        (ref, ref_src), med = reference_rate(m, lo, hi), (st.median(v) if v else None)
        speed[m] = {"memcheck_tok_s": med, "ref_tok_s": ref, "ref_source": ref_src, "a1_tok_s": a1_rate(m), "prompt_tokens": [lo, hi],
                    "ratio": (med / ref) if med and ref else None, "n": len(v)}
    checks["no_slowdown"] = all(s["ratio"] is None or s["ratio"] >= 0.7 for s in speed.values())
    notes.append("prefill tok/s, memory check vs the same model alone: " + ", ".join(
        f"{m} {s['memcheck_tok_s'] and round(s['memcheck_tok_s'], 1)} vs {s['ref_tok_s'] and round(s['ref_tok_s'], 1)} ({s['ref_source']})"
        for m, s in speed.items()))
    checks["no_errors"] = not [r for r in logs if r.get("status") != 200]

    fit = checks["both_listed_after_each_ticket"] and all(v is not False for v in checks.values())
    out = {"pair": [a.small, a.large], "verdict": "FIT" if fit else "DOES NOT FIT", "checks": checks,
           "notes": notes, "prefill": speed, "cgroup_memory_max": mx[-1] if mx else None,
           "cgroup_memory_current_end": int(cur[-1]) if cur else None,
           "cgroup_memory_peak": int(peak[-1]) if peak else None, "tickets_logged": len(logs)}
    Path(a.json_out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print("\n## VERDICT:", out["verdict"])
    for n in notes:
        print(" -", n)
    for k, v in checks.items():
        print(f"   {k}: {v}")
    return 0 if fit else 2


if __name__ == "__main__":
    raise SystemExit(main())
