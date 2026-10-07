# Prediction Record — ICT3113 Group P2-9

**FROZEN BEFORE FIRST BENCHMARK RUN. NOT REVISABLE.**

Committed together with `golden/golden_set.csv`, before any model has been run against the golden set. The commit history is the evidence.

> **DRAFT: owner Muhaimeen (M5).** M5 must review every number, change anything the team disagrees with, and then sign below. Nothing in this file may change after the freeze commit.
>
> **What the draft is based on:**
> - Machine A moved from the MacBook to Irfan's Windows PC (i9-10900K, Docker on WSL 2) on 7 Oct, so the latency rows were re-derived on the PC.
> - The earlier basis (the MacBook's repeated `make check` smoke request, 126 tokens in 204 ms, about 620 tok/s) was a **prompt-cache artefact**. Repeating an identical prompt lets Ollama reuse its cached evaluation. On the PC the same repeated request showed about 1,500 tok/s warm, but only about 84 tok/s cold. Real tickets are all different, so the latency rows are not based on it.
> - New basis: 16 sequential `POST /tickets` with **distinct, made-up narratives** (no dataset rows, no golden tickets), `llama3.2:1b`, 236–609 prompt tokens, kept in `results/logs/prefreeze_calibration_pc.jsonl` (`row_id` `probe-00`…`probe-15`). Least-squares fit: latency ≈ −1,285 ms + 13.5 ms × prompt tokens, so **3.0 s at 320 tokens** and **6.7 s at 595 tokens**. Median prefill rate is 109 tok/s and median generation is 151 ms.
> - Ollama runs with a 4-CPU limit (`OLLAMA_CPUS=4`), but its runner starts `--threads 10` (the host's physical core count). The team decided to leave this in the baseline (no pre-optimisation). A direct-to-Ollama check with made-up prompts gave 3.1 s with the default 10 threads and 2.2 s with `num_thread=4`.

**Committed:** <date, time>
**Commit hash:** <filled in by the commit itself>
**Authors:** <names> — signed off by M5: <name>

---

## 1. Where we expect the bottleneck to be under load, and why

- **Bottleneck component:** Ollama CPU inference, specifically **prompt evaluation (prefill)**. It is not the FastAPI threadpool, SQLite, the `/search` scan, or the network.
- **Why:**
  - A median ticket is about 216 narrative tokens plus about 105 template tokens, roughly 320 prompt tokens, while the answer is 1–2 tokens. Prefill therefore dominates each request.
  - Ollama runs on 4 CPU cores. Prefill is compute-bound, so extra parallel slots (`OLLAMA_NUM_PARALLEL`, auto-set to 4 on this machine) share the same 4 cores and add no throughput.
  - Ollama's runner uses 10 threads inside a 4-CPU quota, so part of each request is spent throttled rather than computing. We expect this oversubscription to make prefill slower and per-request latency more variable than a 4-thread runner would.
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

**Predicted saturation point (baseline, largest candidate, qwen2.5:7b):** **3.3 tickets/min (0.056 tickets/s)**. This is below the 2× surge test rate (4/min), so the 7B queue grows without bound in that run.
**Predicted saturation point (baseline, smallest candidate, qwen2.5:0.5b):** **50 tickets/min (0.83 tickets/s)**
**Stress test (llama3.2:3b), max sustainable rate:** **7.4 tickets/min ±25 %**. Failure mode: unbounded latency, **not** errors. Below Ollama's queue limit and the 600 s timeout, nothing is refused.

---

## 2. Per-candidate predictions

Single-request latency is the accuracy harness's sequential latency (one request at a time) on Machine A, over the golden set.

| Candidate (tag) | Params | Predicted accuracy on golden set | Predicted single-request latency (p50, ms) | Predicted p95 (ms) |
|---|---|---|---|---|
| `qwen2.5:0.5b` | 0.5B | **45 %** | **1,200** | **2,700** |
| `llama3.2:1b` | 1.2B | **58 %** | **3,000** | **6,700** |
| `llama3.2:3b` | 3.2B | **70 %** | **8,100** | **18,000** |
| `qwen2.5:7b` | 7.6B | **82 %** | **18,000** | **40,000** |

**Reasoning for the accuracy ordering:**
- Accuracy rises strictly with size. The task needs fine distinctions that depend on *whose conduct* is complained about (protocol §2): a collection account on a credit report, or a wire scam out of a checking account.
- Small models latch onto the most salient product word instead.
- We expect Qwen 7B to beat Llama 3B by more than size alone would suggest, because Qwen 2.5 is stronger at structured, instruction-following output.

**Reasoning for the latency ordering:**
- On Machine A (the PC), 16 distinct made-up tickets through `POST /tickets` on `llama3.2:1b` fit latency ≈ −1,285 ms + 13.5 ms per prompt token. Prefill is about 109 tok/s on the 4-CPU quota and is about 93 % of each request.
- A median golden prompt (about 320 tokens) therefore takes about 3.0 s at p50.
- Cost per token rises with length (7.4 ms/token at 236 tokens, 10.5 ms/token at 609), so the p95 ticket (about 595 tokens, 2.3× longer) takes about 6.7 s, **2.2× p50** with no queueing at all.
- Prefill cost scales roughly with parameter count: ×0.4 for 0.5B, ×2.7 for 3B, ×6 for 7B, applied to the 1B p50 and p95.

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
- **R1 (POST p95 ≤ 15 s at peak): fails for `llama3.2:3b` (p95 about 18 s) and `qwen2.5:7b` (p95 about 40 s, p99 also above 30 s).** At the peak rate (1/min) utilisation is low (3B about 14 %, 7B about 30 %), so the failure comes from single-request latency, not queueing. 0.5B and 1B pass.
- **R2 and R3 are met by all four.** 7B runs at about 60 % utilisation at the 2/min surge rate, which is enough for R3 but leaves visibly higher latency than at peak.

---

## Freeze checklist

- [ ] Every blank above is filled with a specific value, reviewed by M5
- [ ] `golden/golden_set.csv` is final (150–200 tickets)
- [ ] `golden/labels_*.csv` committed as separate commits, one per annotator
- [ ] `golden/disagreements.csv` has an adjudicated label and a note on every row
- [ ] `golden/labelling_protocol.md` has its revision history filled in
- [ ] No model has been run against golden-set tickets
- [ ] `git commit` done — **then** Step 5 may begin
