# Test Playbook — ICT3113 Group P2-9

Slide 8. The bar: *"described in sufficient detail that a competent software
tester could carry it out without seeking or inventing further information from
your team."*

Test that claim. Hand this to someone outside the team and watch where they stop.
Every place they ask a question is a gap.

---

## 0. Preconditions (all tests)

| # | Check | How |
|---|---|---|
| P1 | Golden set + prediction record committed | `git log --oneline -- golden/ docs/prediction_record.md` |
| P2 | Load generator on a **separate machine** from service + Ollama | `docs/test_environment.md` |
| P3 | Service starts empty | `docker compose down -v && docker compose up -d` |
| P4 | Model pinned and loaded | `curl -s http://<svc>:8000/healthz` reports the intended tag |
| P5 | Model warm | Send 3 throwaway tickets from **non-golden** rows. Ollama's first request pays a multi-second model load; measuring it as steady-state latency is a lie. Discard these and note it. |
| P6 | Feed files regenerated | `python3 tools/prepare_jmeter_data.py` |
| P7 | Nothing else running on either host | `top` — record it |

## 1. Test A — Single-request latency baseline

**Purpose:** establish uncontended per-ticket latency per candidate; the
denominator for every queueing claim later.

1. Preconditions P1–P7.
2. `python3 tools/accuracy_harness.py --base http://<svc>:8000 --model <tag> --digest <sha>`
   (sequential, one request at a time — this is also Test C).
3. Record p50/p95/p99 from the harness summary.
4. Repeat three times. Report mean and spread.

**Pass/fail:** compare against R1.

## 2. Test B — Open-loop load test

**Purpose:** latency and throughput versus offered load; locate the knee.

1. Preconditions P1–P7. Set `RUN_ID=<model>_rate<R>_run<N>` on the service and
   restart it so its log lines carry the run tag.
2. On the load generator:
   ```
   cd jmeter && ./run_matrix.sh <svc-host> <model-tag> "<rates>"
   ```
   Rates come from your workload model: at minimum mean, peak, and one rate
   above peak.
3. Each configuration runs **three times**, 10 minutes each, 120s cooldown
   between runs so run N+1 does not inherit run N's backlog.
4. After each run:
   ```
   python3 tools/reconcile.py --jtl results/jtl/<tag>.jtl \
       --log results/logs/requests.jsonl --run-id <tag>
   ```
   A run that does not reconcile is not reported until the discrepancy is
   explained.
5. Aggregate:
   ```
   python3 tools/analyze_jtl.py results/jtl/<model>_rate<R>_run*.jtl \
       --config-name "<model> @ <R> req/s"
   ```

**Record per configuration:** p50, p95, p99, achieved throughput, error rate —
each as mean and range across the three runs.

**Pass/fail:** R1, R2, R3, R6.

## 3. Test C — Accuracy

**Purpose:** overall and per-category accuracy against the frozen golden labels.

1. Preconditions P1–P5. Service must be **empty** — `/stats` totals are part of
   the evidence.
2. For each candidate:
   ```
   python3 tools/accuracy_harness.py --base http://<svc>:8000 \
       --model <tag> --digest <sha>
   ```
   The harness refuses to run if `golden/golden_set.csv` is uncommitted.
3. Outputs: `results/accuracy/predictions_<model>.csv` and `summary_<model>.json`
   (overall accuracy, per-category precision/recall/F1, confusion matrix).

**Determinism note:** `temperature=0, seed=42` are set in the service, so a rerun
should reproduce the same labels. Verify this once and say so — if it does not
reproduce, every accuracy number needs an error bar and you must say why.

**Pass/fail:** R4, R5.

## 4. Test D — Stress test (one candidate)

**Purpose:** find a limit of the system under test.

**Define the failure condition before running.** Pick one and write it down:

- (a) achieved throughput stops rising as offered load rises (saturation), or
- (b) p99 grows without bound across the run — fit latency against elapsed time
  within the run and show a positive slope that does not flatten, or
- (c) error rate exceeds 1% (connection refused, timeouts, 5xx), or
- (d) Ollama or the service dies (OOM kill, crash).

**Our chosen condition:** (b) + (c). A step is *unsustainable* when requests are still queueing at its end: more than max(5, 15 % of the step's arrivals) in flight, or any error. The limit is the highest step below the first unsustainable one. We also report the **saturated throughput**, the completion rate inside the unsustainable steps, which measures capacity directly. In a simulation of this rule (Poisson arrivals, 300 s steps from 0.5× to 1.5× capacity, 300 seeds), the reported limit fell within 0.9–1.1× the true capacity in 94 % of runs, erring low.

**Procedure:**

1. Preconditions P1–P7. Candidate: `llama3.2:3b`, the mid-size model and the most likely recommendation. Optionally repeat for `qwen2.5:7b`.
2. Steps come from Test C's single-request p50 latency S: capacity μ ≈ 60/S tickets/min, with steps at 0.5, 0.75, 0.9, 1.0, 1.1, 1.25 and 1.5 × μ.
   ```
   python3 tools/stress_steps.py llama3.2:3b          # prints e.g. "16 24 29 32 35 40 48"
   ```
3. On the load generator:
   ```
   cd jmeter && ./run_stress.sh <svc-host> llama3.2:3b "<steps>"
   ```
   - All steps run inside **one** JMeter run (`triage_stress.jmx`, schedule from `-Jschedule`), 300 s each, with no restart between them, so a backlog carries forward.
   - There is no search traffic, and the response timeout is 600 s, so queueing shows up as latency rather than being hidden by timeouts.
   - The ladder is repeated **3 times**, because the limit is a measurement too.
4. On the SUT during each ladder: `docker stats --no-stream` every 5 s into `results/stress/dockerstats_<tag>.txt` (Ollama CPU should pin at about 400 %), plus `docker logs triage-ollama` at the end.
5. `run_stress.sh` calls `tools/analyze_stress.py` after each ladder. It writes `results/stress/<tag>.summary.json` (per-step table, limit, saturated throughput) and `<tag>.png` (latency scatter and in-flight count over time).

**Report:** the limiting rate, **which** condition tripped, and the diagnosed
mechanism. "It got slow" is not a finding; "the Ollama request queue grew without
bound because one instance serves N concurrent requests and service time exceeded
inter-arrival time above X req/s" is.

## 5. Evidence kept per run

| Artefact | Path |
|---|---|
| JMeter raw results | `results/jtl/<tag>.jtl` |
| JMeter run log | `results/jtl/<tag>.jmeter.log` |
| Service request log | `results/logs/requests.jsonl` (filter `run_id`) |
| Accuracy predictions | `results/accuracy/predictions_<model>.csv` |
| Accuracy summary | `results/accuracy/summary_<model>.json` |
| Reconciliation output | `results/logs/reconcile_<tag>.txt` |
| Resource snapshot | `results/logs/dockerstats_<tag>.txt` |

Every number on a slide must be reachable from this table.
