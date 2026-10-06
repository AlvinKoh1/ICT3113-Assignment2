# Prediction Record — ICT3113 Group P2-9

**FROZEN BEFORE FIRST BENCHMARK RUN. NOT REVISABLE.**

Committed together with `golden/golden_set.csv`, before any model has been run against the golden set. The commit history is the evidence.

> **DRAFT: owner Muhaimeen (M5).** M5 must review every number, change anything the team disagrees with, and then sign below. Nothing in this file may change after the freeze commit.
>
> **What the draft is based on:**
> - The only measurement available before the freeze: Irfan's warm smoke request on Machine A (README §3). That was `llama3.2:1b`, 126 prompt tokens evaluated in 204 ms, 2 tokens generated in 122 ms, 354 ms in total.
> - Ollama runs with a 4-CPU limit (`OLLAMA_CPUS=4`).
> - **If Machine A or `OLLAMA_CPUS` changes before the freeze, re-derive the latency rows.**

**Committed:** <date, time>
**Commit hash:** <filled in by the commit itself>
**Authors:** <names> — signed off by M5: <name>

---

## 1. Where we expect the bottleneck to be under load, and why

- **Bottleneck component:** Ollama CPU inference, specifically **prompt evaluation (prefill)**. It is not the FastAPI threadpool, SQLite, the `/search` scan, or the network.
- **Why:**
  - A median ticket is about 216 narrative tokens plus about 105 template tokens, roughly 320 prompt tokens, while the answer is 1–2 tokens. Prefill therefore dominates each request.
  - Ollama runs on 4 CPU cores. Prefill is compute-bound, so extra parallel slots (`OLLAMA_NUM_PARALLEL`) share the same 4 cores and add no throughput.
  - Each request therefore occupies the backend for about S seconds (the single-request latency below). The service saturates at μ ≈ 60/S tickets/min.
- **What we expect to see at saturation:**
  - Achieved throughput plateaus at μ (±10 %) while offered load keeps rising.
  - p95 and p99 grow without bound across a stress step.
  - The Ollama container's CPU is pinned at about 400 % (4 cores) in `docker stats`, while the triage container stays below 10 % of one core.
  - Service-side `latency_ms` tracks JMeter `elapsed` within about 50 ms. The queue is behind the service, in Ollama, not in our accept queue.
  - `ollama_prompt_eval_ms` is **≥ 70 %** of `ollama_total_ms` for every model.
- **The observation that would prove us wrong:**
  - Throughput plateaus well below 60/S while Ollama CPU is under 60 %. That would point at the threadpool, connection handling (keep-alive is off) or SQLite instead.
  - Or `GET /search` p95 exceeds 1 s at peak load, which would mean the shared threadpool, not Ollama, is the first constraint.

**Predicted saturation point (baseline, largest candidate, qwen2.5:7b):** **15 tickets/min (0.25 tickets/s)**
**Predicted saturation point (baseline, smallest candidate, qwen2.5:0.5b):** **200 tickets/min (3.3 tickets/s)**
**Stress test (llama3.2:3b), max sustainable rate:** **32 tickets/min ±25 %**. Failure mode: unbounded latency, **not** errors. Below Ollama's queue limit and the 600 s timeout, nothing is refused.

---

## 2. Per-candidate predictions

Single-request latency is the accuracy harness's sequential latency (one request at a time) on Machine A, over the golden set.

| Candidate (tag) | Params | Predicted accuracy on golden set | Predicted single-request latency (p50, ms) | Predicted p95 (ms) |
|---|---|---|---|---|
| `qwen2.5:0.5b` | 0.5B | **45 %** | **300** | **550** |
| `llama3.2:1b` | 1.2B | **58 %** | **700** | **1,250** |
| `llama3.2:3b` | 3.2B | **70 %** | **1,900** | **3,400** |
| `qwen2.5:7b` | 7.6B | **82 %** | **4,000** | **7,200** |

**Reasoning for the accuracy ordering:**
- Accuracy rises strictly with size. The task needs fine distinctions that depend on *whose conduct* is complained about (protocol §2): a collection account on a credit report, or a wire scam out of a checking account.
- Small models latch onto the most salient product word instead.
- We expect Qwen 7B to beat Llama 3B by more than size alone would suggest, because Qwen 2.5 is stronger at structured, instruction-following output.

**Reasoning for the latency ordering:**
- Irfan's warm 1B request evaluated 126 prompt tokens in 204 ms, about 620 tokens/s on 4 cores.
- A median golden prompt (about 320 tokens) then costs about 0.52 s of prefill, plus about 0.12 s to generate the answer, so about 0.7 s at p50.
- Prefill cost scales roughly with parameter count: ×0.4 for 0.5B, ×2.7 for 3B, ×6 for 7B.
- p95 tickets are 2.3× longer than p50 (about 595 vs 320 prompt tokens), so p95 latency is about 1.8× p50 with no queueing at all.

---

## 3. Categories we expect to be hardest

Recall below is predicted for `llama3.2:3b`. The ranking is predicted to hold for every model.

| Rank | Category | Predicted recall (3b) | Why |
|---|---|---|---|
| 1 (hardest) | Debt collection | 50 % | Collection complaints nearly always mention the credit report ("this collection is on my report"). Models follow the report vocabulary, while our protocol's §4 precedence gives the golden label to Debt collection |
| 2 | Money transfer or service | 55 % | P2P and wire complaints also describe the bank account the money left. Models answer "Bank account or service" when the transfer product (Zelle, Cash App, wire) is the grievance |
| 3 | Consumer loan | 62 % | Heterogeneous (student, auto, personal, payday). Student-loan narratives are often about delinquencies on a report, which pulls them to Credit reporting |
| 4 | Bank account or service | 70 % | |
| 5 | Credit reporting | 78 % | Over-predicted, which helps its recall and hurts its precision |
| 6 | Credit card | 82 % | |
| 7 (easiest) | Mortgage | 90 % | Distinctive vocabulary: escrow, servicer, foreclosure, modification |

**Specific confusion we predict:** **golden Debt collection → predicted Credit reporting** will be the single largest off-diagonal cell for every model. It will be larger than Credit reporting → Debt collection.

**Predicted unparsed rate (model returns something outside the seven categories), per size class:**
- small (`qwen2.5:0.5b`): **8 %**
- `llama3.2:1b`: **3 %**
- large (3B and 7B): **< 1 %**

---

## 4. Requirements we expect to fail

- **R4 (≥ 85 % overall): no candidate meets it.** `qwen2.5:7b` comes closest at about 82 %.
- **R5 (≥ 70 % recall in every category): fails for 0.5B, 1B and 3B.** Debt collection and Money transfer fall below 70 %. 7B narrowly passes.
- **R6 unparsed < 2 %: fails for `qwen2.5:0.5b`.**
- **R1, R2 and R3 are met by all four.** Even 7B runs at only about 13 % utilisation at the 2/min surge rate.

---

## Freeze checklist

- [ ] Every blank above is filled with a specific value, reviewed by M5
- [ ] `golden/golden_set.csv` is final (150–200 tickets)
- [ ] `golden/labels_*.csv` committed as separate commits, one per annotator
- [ ] `golden/disagreements.csv` has an adjudicated label and a note on every row
- [ ] `golden/labelling_protocol.md` has its revision history filled in
- [ ] No model has been run against golden-set tickets
- [ ] `git commit` done — **then** Step 5 may begin
