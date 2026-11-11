# Escalation rule — Assignment 2 cascade (Group P2-9)

Frozen before the first Assignment 2 benchmark run. Not revised after measurement.
Implemented in `service/app/cascade.py`; selected with `TRIAGE_MODE=cascade`.

## 1. The rule

| | |
|---|---|
| Small model | `llama3.2:3b` (digest `a80c4f17…5b8b72`, Assignment 1 candidate) |
| Large model | `qwen2.5:7b` (digest `845dbda0…0b697e`, Assignment 1 top model) |
| Signal | `n` = length of the ticket narrative in characters, exactly as received in the JSON body (Python `len()` of the decoded string; the same figure the Assignment 1 log records as `narrative_chars`) |
| Setting | cut-off `T` in characters, `CASCADE_MAX_CHARS` |
| Settings tested | **T = 400** (conservative) and **T = 500** (aggressive) |

For every ticket received by `POST /tickets`:

1. If `n > T`: send the ticket to the **large** model. Its category is final. *(escalated, route `long->large`)*
2. Otherwise send it to the **small** model.
   * If the small model's reply parses to one of the seven categories, that category is final. *(not escalated, route `short->small:accepted`)*
   * If it parses to `UNPARSED`, send the ticket to the large model; its category is final. *(escalated, route `short->small:unparsed->large`)*

Both models receive the unchanged Assignment 1 prompt (`PROMPT_VERSION v1`, `classifier.build_prompt`) and the same Ollama options (temperature 0, seed 42, `num_predict` 16, `num_ctx` 2048). The reply is parsed by the unchanged Assignment 1 parser. There is no other input to the decision: no category list, no second prompt, no confidence score, no cache.

**Escalation** means "the final answer came from the large model". The escalation fraction is the share of completed tickets whose log line has `"escalated": true`.

## 2. What the caller and the log see

* The endpoint still accepts one ticket and returns one category. The response's `model` field (and the `model` column `GET /search` returns) holds the configuration name, e.g. `cascade-llama3.2:3b-qwen2.5:7b-le500`, never the model that answered.
* The service log (`results/logs/a2_requests.jsonl`, one JSON line per request) records for each ticket: `final_model`, `escalated`, `route`, `narrative_chars`, `cascade_max_chars`, and, for each model called, its category, latency and Ollama timings (`small_*`, `large_*`). The escalation fraction in every result is computed from these lines.

## 3. Why this rule (tuning set only — `docs/a2/tuning_analysis.md`)

All rules were replayed over the Assignment 1 records of the 88 tuning tickets (temperature 0, fixed seed, so a model's answer in a cascade is its Assignment 1 answer).

* **Length predicts where the small model is wrong.** On tickets ≤ 500 characters the 3b is right on 12/24 and the 7b on 13/24; above 500 characters, 27/64 vs 47/64. Short tickets are where the cheap model gives up almost nothing.
* **Length escalation costs nothing extra.** A long ticket goes straight to 7b, so the cascade never pays for a small-model call it then throws away. Every other rule calls the small model first on every ticket.
* **The 3b costs about 46 % of a 7b call** (17.6 s vs 37.9 s mean on the tuning set). A rule that calls 3b on every ticket must escalate fewer than about half of them to break even. The category rule (escalate when 3b predicts an unreliable category) escalates 66 % at its fastest passing setting: modelled +16 % slower than 7b alone.
* **The smaller models cannot carry any traffic.** `qwen2.5:0.5b` answers `Consumer loan` for 71/88 tuning tickets and `llama3.2:1b` answers `Money transfer or service` for 58/88. Every length or category rule with either of them fails the per-category check at any setting that saves time; an agreement rule between them is meaningless (they agree on 0/88).
* **Self-reported confidence** needs a second call on every ticket and these models show no sign of calibration.

## 4. Why these two settings

| Setting | Tuning: correct | Escalated | Worst category vs 7b | Modelled mean (no load) |
|---|---|---|---|---|
| 7b alone (reference) | 60/88 | 100 % | — | 37.9 s |
| **T = 400** | 59/88 | 81 % | −10 pts (Debt collection) | 36.3 s (−4 %) |
| **T = 500** | 59/88 | 73 % | −14 pts (Credit reporting) | 35.2 s (−7 %) |
| T = 550 (not tested) | 57/88 | 68 % | −24 pts (Credit reporting) | 34.6 s |

T = 500 is the largest cut-off that passes the tuning-set check; 550 already fails Credit reporting. T = 400 keeps 5 points of headroom on the binding category, because the test-set categories hold only 10–19 tickets each and one ticket moves a category by 5–10 points.

## 5. Memory pre-condition and fallback

The cascade is only measured with **both models resident** (`tools/a2_memory_check.sh`: `ollama ps` lists both after every ticket, no reloads, no OOM, no slowdown), in the unchanged Ollama container (4 CPUs, 8 GiB, `OLLAMA_NUM_PARALLEL=4`).

If `llama3.2:3b` + `qwen2.5:7b` do not fit, the same rule is run with the next-smaller pair, `llama3.2:1b` + `qwen2.5:7b` (`SMALL=llama3.2:1b`), at the same two cut-offs. The tuning set predicts that pair fails the per-category limit (Bank account or service, −27 to −36 points); it is measured and reported as not passing accuracy. If no pair fits, the cascade is reported as not feasible on this machine with the `ollama ps` evidence, and the recommendation is a single model.

## 6. Reproducing it elsewhere

Any team can implement this from the description above: compute the character length of the incoming narrative; if it exceeds T, classify with the large model; otherwise classify with the small model and accept its answer unless it is unparseable, in which case classify with the large model. Use the same prompt and decoding options for both.
