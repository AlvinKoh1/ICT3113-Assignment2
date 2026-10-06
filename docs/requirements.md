# Performance and Accuracy Requirements — ICT3113 Group P2-9

Slide 4. Owner: **Alvin (M2)**. Every requirement is testable (a number, a percentile where relevant, and a load condition) and traces to a figure in `docs/workload_model.md` (WM).

**Position the requirements take** (WM §6): a misrouted ticket costs the client more than a slow one.
- About 5 agent-minutes plus at least a working day of delay per misroute, against a classification delay nobody sees.
- So accuracy (R4, R5) is the primary requirement. Latency and throughput (R1–R3, R6) are constraints set as loose as the intake and the agents can tolerate, but no looser.

**Common load conditions:**
- **Peak:** open-loop Poisson `POST /tickets` at **0.0167 tickets/s (1/min)**, with `GET /search` at **3× that rate** (`SEARCH_RATIO=3`, 0.05/s).
- **Surge:** **0.0333 tickets/s (2/min)**, same search ratio.
- **Runs:** each configuration is run **3 times, 10 minutes each** (`jmeter/run_matrix.sh`), and a requirement passes only if it holds **in every run**.

---

## R1 — Response time: POST /tickets

> **Statement:** At the peak load, `POST /tickets` latency shall be **p95 ≤ 15 s and p99 ≤ 30 s** in each of 3 ten-minute runs.

- **Traces to:** WM §3 (peak 1/min), §6 (latency budget).
- **Justification:**
  - No customer waits on classification. The customer gets an acknowledgement either way, and routing is measured in days (Barclays closes 56 % of complaints within 3 days, WM [3]).
  - But the endpoint is synchronous: the intake system holds a connection open until triage returns. p99 must stay inside a common 30 s gateway/HTTP-client timeout, or tickets start failing at intake.
  - p95 ≤ 15 s leaves a 2× margin to that cliff.
- **Measured by:** JMeter `POST /tickets` `elapsed`, p95 and p99 per run (`tools/analyze_jtl.py`). Cross-checked against service `latency_ms` (`tools/reconcile.py`).

## R2 — Response time: GET /search under mixed load

> **Statement:** At the peak load (searches at 3× the ticket rate, running concurrently with classification), `GET /search` latency shall be **p95 ≤ 1.0 s** in each run.

- **Traces to:** WM §4 (3 searches per ticket, 2.7/min at peak).
- **Justification:** search is human-facing: an agent is waiting at a screen. 1.0 s is the limit for keeping a user's flow of thought uninterrupted (Nielsen 1993, *Usability Engineering*, ch. 5).
  - It must hold while `POST /tickets` is running, because agents search during the peak.
  - The baseline runs both endpoints on one FastAPI threadpool, so a slow classifier can starve search.
- **Measured by:** JMeter `GET /search` p95 in the R1 runs (`analyze_jtl.py`, label "search").

## R3 — Throughput

> **Statement:** The service shall sustain **120 tickets/hour** (surge load, 0.0333 tickets/s) for each 10-minute run, with achieved throughput **≥ 95 % of offered**, error rate **< 1 %**, and **no queue build-up**: fewer than 5 requests in flight when arrivals stop.

- **Traces to:** WM §3 (surge = 2× design peak; covers Poisson bursts inside the peak hour, incident surges, and about a year of volume growth).
- **Justification:** the service must cover the peak, not the mean (3.4× the mean). Achieved throughput alone can look fine while a queue builds, which is why the in-flight clause is there.
  - In-flight count is computed from the `.jtl` (each sample's start time + elapsed) by `tools/requirements_check.py`.
- **Measured by:** `.jtl` at 0.0333 tickets/s, 3 runs.

## R4 — Classification accuracy (overall)

> **Statement:** Overall accuracy on the frozen golden test set shall be **≥ 85 %**, reported with its Wilson 95 % confidence interval. `UNPARSED` and `ERROR` responses count as misroutes.

- **Traces to:** WM §6 (cost of a misroute).
- **Justification:**
  - Every 1 % of misrouting costs about 118 agent-hours a year at this volume. 15 % costs about 1,764 h, roughly one full-time agent spent re-triaging.
  - That is the most we will accept. Beyond it the automation stops saving the effort it was bought to save, because today's manual triage is already done by people.
- **Measured by:** `tools/accuracy_harness.py`, golden set, per candidate (`overall_accuracy`).

## R5 — Classification accuracy (per category)

> **Statement:** **Every category's recall shall be ≥ 70 %** on the golden test set.

- **Justification:** each category routes to one team.
  - A model can reach 80 % overall while sending half of one category elsewhere, and that team is then starved while another drowns.
  - Money transfer or service is where scam and fraud losses sit (wire recalls, P2P scams). Misrouting those delays a time-critical recovery.
  - A per-category floor stops overall accuracy from hiding this.
- **Measured by:** `per_category[*].recall` from the accuracy harness and the confusion matrix.

## R6 — Reliability

> **Statement:** At the surge load, the HTTP error rate (non-200 or no response within the 600 s timeout) shall be **< 1 %** in every run. In the accuracy run, the `UNPARSED` rate shall be **< 2 %**.

- **Justification:** an `UNPARSED` answer is not an HTTP error, but it is a routing failure: a human has to triage it. It counts against R4/R5 *and* is reported separately here, because a high unparsed rate is fixable (prompt, output format) while a wrong category is not.
- **Measured by:** `error_rate_pct` (`analyze_jtl.py`); `unparsed` in the accuracy summary.

---

## Summary table (Slide 4)

| # | Requirement | Metric | Threshold | Load condition | Traces to |
|---|---|---|---|---|---|
| R1 | POST /tickets latency | p95 / p99 | ≤ 15 s / ≤ 30 s | 0.0167 tickets/s + search 3×, 3 × 10 min | WM §3, §6 |
| R2 | GET /search latency | p95 | ≤ 1.0 s | mixed, peak intake | WM §4 |
| R3 | Throughput | tickets/hr | ≥ 120 (≥ 95 % of offered, < 5 in flight at end) | 0.0333 tickets/s, 3 × 10 min | WM §2–3 |
| R4 | Overall accuracy | % | ≥ 85 % | golden set | WM §6 |
| R5 | Per-category recall | % min | ≥ 70 % each | golden set | WM §6 |
| R6 | Error / unparsed rate | % | < 1 % / < 2 % | surge / golden set | WM §3 |

**Test rates for `run_matrix.sh`:** `"0.0167 0.0333 0.0667"`, i.e. peak (R1, R2), surge (R3, R6) and 2× surge (headroom: where the curve starts to bend).
