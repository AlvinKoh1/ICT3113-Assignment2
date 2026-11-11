# Prediction record — Assignment 2 (Group P2-9)

Committed **before the first Assignment 2 benchmark run** (memory check, accuracy test, S calibration or speed test). The commit history is the evidence. Not revised afterwards; `docs/a2/prediction_account.md` is written after the results and explains every miss.

Sources: Assignment 1 records only — the tuning-set replay (`docs/a2/tuning_analysis.md`), per-model latency-vs-length fits on the tuning rows, and a processor-sharing queue model (`tools/a2_predict.py` → `docs/a2/prediction_inputs.json`). Test-set results of the cascade were **not** computed before writing this.

Already known when this was written (not predictions): the accuracy limits and the single-model test-set scores from the reused Assignment 1 records (`docs/a2/limits.json`): `qwen2.5:7b` 68/87 = 78.2 % (limit 68.2 %, ≥ 60/87); `llama3.2:3b` 44.8 %, `llama3.2:1b` 21.8 %, `qwen2.5:0.5b` 13.8 % all fail. So the speed test covers `qwen2.5:7b` alone and the cascade at T = 400 and T = 500.

## P1 — Memory

| # | Prediction |
|---|---|
| P1.1 | `llama3.2:3b` + `qwen2.5:7b` **fit together** in the 8 GiB Ollama container: `ollama ps` lists both after every ticket, no reload, no OOM kill. Weights 2.0 + 4.7 GB plus KV cache for 4 slots × 2,048 tokens each (~0.9 + 0.5 GB) ≈ 8.1 GB is close to the limit, so we expect `memory.current` above 90 % of `memory.max` and the check to be the tightest part of the experiment. |
| P1.2 | If it does not fit, the symptom will be a reload (`ollama_load_ms` > 1 s on a later call) rather than an OOM kill, because Ollama sizes against the VM's memory, not the container's. |

## P2 — Which configuration is fastest within the limits

| # | Prediction | Reason |
|---|---|---|
| P2.1 | **Cascade T = 500 is the fastest qualifying configuration**, then T = 400, then `qwen2.5:7b` alone. | It removes 7b work on the 25 % of speed-test tickets ≤ 500 chars, at a 3b cost of about 47 % of the 7b cost on those tickets. |
| P2.2 | The gain is **small: about 10 % on p50** (58 s vs 65 s), and **smaller than the run-to-run spread**: at least one T = 500 run will have a higher p50 than at least one 7b-alone run. | Queue model: per-run p50 ranges 45–77 s (T = 500) and 50–91 s (7b), 10th–90th percentile of simulated runs, with ~30 arrivals per run. |
| P2.3 | If the cascade loses, the cause will be CPU contention between the two runners, not escalation: escalation fraction will match prediction (P3) but service time per ticket will be higher than the single-request fits. | Both runners use `--threads 10` inside one 4-CPU quota. |

## P3 — Cascade at each setting

| Quantity | T = 400 | T = 500 | 7b alone (reference) | How |
|---|---|---|---|---|
| Escalation, accuracy test (87 test tickets) | **81 %** (≈ 70/87) | **73 %** (≈ 64/87) | 100 % | tuning-set share > T |
| Escalation, speed test (fixed 40-ticket list) | **85 %** | **75 %** | 100 % | share of list > T |
| Test-set accuracy | **67/87 = 77.0 %** | **67/87 = 77.0 %** | 68/87 = 78.2 % (known) | tuning drop of 1 ticket, applied to the test set |
| Passes overall limit (≥ 60/87) | yes, by 7 tickets | yes, by 7 tickets | — | |
| Passes per-category limits | **yes** | **yes, but with ≤ 1 ticket to spare in Credit reporting and Debt collection** | — | tuning gaps −10 / −14 points |
| Accuracy of escalated (7b) tickets | ≈ 80 % | ≈ 80 % | | 7b on long tickets (tuning 47/64 = 73 %, test-set 7b is higher) |
| Accuracy of non-escalated (3b) tickets | ≈ 50 % (≈ 8–9 of 17) | ≈ 50 % (≈ 12 of 24) | | tuning: 8/17 and 12/24 accepted 3b answers right |
| Median latency, single request, no load | **35 s** (same as 7b) | **35 s** (same as 7b) | 35 s | no-load replay: the rule only touches tickets below the median length, so the median does not move; the **mean** falls 4 % / 7 % |
| p50 under load (mean of 3 runs) | **61 s** | **58 s** | **65 s** | queue model at one ticket per 2S |
| p95 pooled over 3 runs (n ≈ 90) | **215 s** | **207 s** | **226 s** | queue model |
| Errors / unfinished | 0 / 0 | 0 / 0 | 0 / 0 | ρ ≈ 0.5, timeout ≥ 10 S |

## P4 — Which categories lose the most when the small model's answer is accepted

| # | Prediction |
|---|---|
| P4.1 | **Credit reporting loses the most** (tuning: −2 tickets at T = 400, −3 at T = 500), then **Debt collection** (−1) and **Money transfer or service** (−1). |
| P4.2 | **Consumer loan, Mortgage and Credit card gain** a ticket or two (the 3b gets some short tickets the 7b misses). |
| P4.3 | The wrong answers that slip through will mostly be 3b's habit of answering **Bank account or service** for short complaints (it put 50/88 tuning tickets there). |

## P5 — Speed-test set-up

| # | Prediction |
|---|---|
| P5.1 | S (middle of three typical 778-character tickets on `qwen2.5:7b`) = **35 s** (fit: 4.7 s + 38.5 s per 1,000 characters), so the rate is about **0.87 tickets/min**, runs last **35 min**, about 30 arrivals each, timeout 350 s, pause 7 min. |
| P5.2 | This rate is **below the client's Assignment 1 peak of 1.0 ticket/min**, so the result compares configurations but does not show the recommended one can carry the peak. |

## Recommendation we expect to make

Cascade `llama3.2:3b` → `qwen2.5:7b` at T = 500, roughly 10 % faster at the median than `qwen2.5:7b` alone, giving up about one test ticket (1.2 points) overall and up to 3 tickets in Credit reporting — and we expect to have to say the gain is within run-to-run noise.
