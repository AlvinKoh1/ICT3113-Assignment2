# Prediction Record — ICT3113 Group P2-9

**FROZEN BEFORE FIRST BENCHMARK RUN. NOT REVISABLE.**

Committed together with `golden/golden_set.csv`, before any model has been run
against the golden set. The commit history is the evidence.

> Marks are awarded for **specificity** and for the quality of your later
> account of where you were wrong — not for being right. A vague prediction that
> cannot fail earns nothing.
>
> Rule of thumb while filling this in: *could a marker look at our results and
> say "that prediction was wrong"?* If not, it is not specific enough.
> Every number below should be a number, not a range so wide it cannot fail.

**Committed:** <date, time>
**Commit hash:** <filled in by the commit itself>
**Authors:** <names>

---

## 1. Where we expect the bottleneck to be under load, and why

**Prediction:**

> <Name one component: Ollama CPU inference / the service's threadpool /
> SQLite write contention / the /search full-table scan / network.
> Then say what you expect to observe that would confirm it.>

Fill in each:

- **Bottleneck component:** <...>
- **Why:** <the mechanism, not just the name. e.g. "one Ollama instance with
  OLLAMA_NUM_PARALLEL=N on M cores; a 500-token prompt at ~X tok/s means each
  request occupies a slot for ~Y seconds, so the service saturates at ~Z req/s.">
- **What we expect to see at saturation:** <e.g. "p99 grows without bound while
  achieved throughput plateaus at Z req/s; CPU pinned at 100% on the Ollama
  host; the service's own latency (service log) tracks client latency (.jtl)
  closely, showing the queue is inside Ollama, not in our accept queue.">
- **The observation that would prove us wrong:** <e.g. "throughput plateaus well
  below Z with CPU under 60%" — which would point at the threadpool or at
  connection handling instead.>

**Predicted saturation point (baseline, largest candidate):** ____ tickets/sec
**Predicted saturation point (baseline, smallest candidate):** ____ tickets/sec

---

## 2. Per-candidate predictions

One row per candidate. Both columns must be committed **before** any run.

| Candidate (tag) | Params | Predicted accuracy on golden set | Predicted single-request latency (p50, ms) | Predicted p95 (ms) |
|---|---|---|---|---|
| <tag> | <n>B | ____ % | ____ | ____ |
| <tag> | <n>B | ____ % | ____ | ____ |
| <tag> | <n>B | ____ % | ____ | ____ |
| <tag> | <n>B | ____ % | ____ | ____ |

Single-request latency = one request at a time, no concurrent load, measured on
the hardware described in `docs/test_environment.md`, on the median-length
narrative in our slice.

**Reasoning for the accuracy ordering:** <2–3 sentences. Why do you expect this
ranking? What is it about the task — seven fine-grained categories, long
narratives, heavy redaction — that you think separates the models?>

**Reasoning for the latency ordering:** <2–3 sentences. State the rough
tokens/sec you expect per size class on your CPU, and how you got that figure.>

---

## 3. Categories we expect to be hardest

Rank all seven from hardest to easiest, and give a reason for the top three.

| Rank | Category | Predicted accuracy (recall) | Why |
|---|---|---|---|
| 1 (hardest) | <...> | ____ % | <...> |
| 2 | <...> | ____ % | <...> |
| 3 | <...> | ____ % | <...> |
| 4 | <...> | ____ % | |
| 5 | <...> | ____ % | |
| 6 | <...> | ____ % | |
| 7 (easiest) | <...> | ____ % | |

**Specific confusion we predict:** <name the ordered pair, e.g. "we expect
Debt collection tickets to be misclassified as Credit reporting more often than
the reverse, because collection complaints usually also mention the tradeline">

**Predicted unparsed rate (model returns something outside the seven
categories), per size class:** small ____ % / large ____ %

---

## 4. Requirements we expect to fail

Which of your own requirements in `docs/requirements.md` do you expect **no**
candidate to meet? Naming one here and being right is a strong result; naming
none and then missing three is not.

- <...>

---

## Freeze checklist

- [ ] Every blank above is filled with a specific value
- [ ] `golden/golden_set.csv` is final (150–200 tickets)
- [ ] `golden/labels_*.csv` committed as separate commits, one per annotator
- [ ] `golden/disagreements.csv` has an adjudicated label and a note on every row
- [ ] `golden/labelling_protocol.md` has its revision history filled in
- [ ] No model has been run against golden-set tickets
- [ ] `git commit` done — **then** Step 5 may begin
