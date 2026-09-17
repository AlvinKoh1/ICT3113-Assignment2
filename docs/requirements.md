# Performance and Accuracy Requirements — ICT3113 Group P2-9

Slide 4. Every requirement must be **testable**: a number, a percentile where
relevant, and the load condition under which it must hold. Each must trace to a
figure in `docs/workload_model.md`.

> Template for a good requirement:
> **R#** — *<metric>* for *<endpoint>* shall be *< value>* at *<percentile>*,
> measured at *<arrival rate>* sustained for *<duration>*, with error rate below
> *<value>*.
>
> A requirement with no load condition is untestable. A requirement with no
> percentile (for latency) is untestable. Both are worth zero.

---

## R1 — Response time: POST /tickets

> **Statement:** <...>

- **Traces to:** workload model §__
- **Justification:** <Why this number? Intake is machine-to-machine, so no human
  waits on it directly — but classification latency bounds throughput, and a
  ticket not yet classified is a ticket not yet routed. What is the actual
  business consequence of a slow classification? Say it.>
- **Measured by:** JMeter `POST /tickets` p95, three runs, at the rate named above.

## R2 — Response time: GET /search under mixed load

> **Statement:** <...>

- **Traces to:** workload model §4
- **Justification:** <This one *is* human-facing — an agent is waiting at a
  screen. Tie the number to interaction research or to a stated usability
  standard, not to taste.>
- **Measured by:** JMeter `GET /search` p95 while `POST /tickets` runs at the
  peak rate. Search latency measured in isolation proves nothing.

## R3 — Throughput

> **Statement:** <e.g. "The service shall sustain ____ tickets classified per
> hour for 30 minutes with error rate below ____%, without p99 latency growing
> across the run.">

- **Traces to:** workload model §2 and §3 (must cover the **peak**, not the mean)
- **Justification:** <...>
- **Measured by:** achieved throughput from the .jtl, three runs, mean and spread.

> Note the "without p99 growing across the run" clause. Achieved throughput alone
> can look fine while a queue builds — a system that accepts 100 tickets/hour and
> falls one minute further behind every minute is not meeting a throughput
> requirement. Say how you will detect that.

## R4 — Classification accuracy (overall)

> **Statement:** <e.g. "Overall accuracy on the frozen golden test set shall be
> at least ____%.">

- **Traces to:** the cost-of-misroute figure in workload model §6
- **Justification:** <Derive it. If a misroute costs X agent-minutes and volume
  is Y/day, what error rate is affordable against the cost of a human triaging
  everything? The floor is not arbitrary: it should be the point where automation
  stops being worth it. State that point.>
- **Measured by:** `tools/accuracy_harness.py`, golden set, per candidate.

## R5 — Classification accuracy (per category)

> **Statement:** <e.g. "No category shall have recall below ____%.">

- **Justification:** <Why does a per-category floor matter when overall accuracy
  is already constrained? Because a model can hit 75% overall while routing
  almost every Money transfer ticket to the wrong desk — and that category is
  where the fraud losses are. Make that argument concretely.>
- **Measured by:** per-category recall and the confusion matrix.

## R6 — Reliability (optional but recommended)

> **Statement:** <e.g. "Error rate shall remain below ____% at the peak arrival
> rate; no request shall exceed ____s.">

- **Justification:** <An unparsed model output is not an HTTP error but it *is* a
  routing failure. Decide whether UNPARSED counts against R4, R6, or both, and
  say which.>

---

## Summary table (put this on Slide 4)

| # | Requirement | Metric | Threshold | Load condition | Traces to |
|---|---|---|---|---|---|
| R1 | POST /tickets latency | p95 | | | WM §_ |
| R2 | GET /search latency | p95 | | mixed, peak intake | WM §4 |
| R3 | Throughput | tickets/hr | | sustained __ min | WM §2–3 |
| R4 | Overall accuracy | % | | golden set | WM §6 |
| R5 | Per-category recall | % min | | golden set | WM §6 |
| R6 | Error rate | % | | at peak | WM §3 |
