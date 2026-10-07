# Candidate Models — ICT3113 Group P2-9

Slide 5. Three to five models, spanning **at least two parameter size classes**,
each pinned by **exact Ollama tag and digest**, with the set justified.

---

## The trade-off the set must make visible

> "Smaller models are faster on CPU and wrong more often; larger models are more
> accurate, slower, and sustain less throughput. Your candidates should make that
> trade-off visible rather than avoid it."

Four models all in the 3–4B range would avoid it. Pick across the range so the
accuracy/latency curve has a shape.

Rough CPU arithmetic to sanity-check your set before you spend a day measuring
it: on commodity CPU, generation runs on the order of tens of tokens/sec for a
1B model and single-digit tokens/sec for a 7B model, and prompt evaluation on a
~500-token complaint is often the larger share of total latency. If a 7B model
at your p95 ticket length is going to take ~30s per ticket, decide *now* whether
that is worth measuring three times at four arrival rates, or whether it belongs
in the set precisely to demonstrate that it is unusable. Both are defensible —
but the second is a finding, so say it deliberately rather than discovering it
at 2am.

## Suggested starting set (replace with your own, and justify)

| Model | Size class | Why it earns a slot |
|---|---|---|
| `qwen2.5:0.5b` | sub-1B | Floor case. Fast enough that inference may stop being the bottleneck — which makes the bottleneck analysis interesting. Likely poor at 7-way discrimination and likely to produce unparsable output. |
| `llama3.2:1b` | 1B | The plausible "ship it" small model. |
| `llama3.2:3b` | 3B | Mid class; the usual accuracy/latency compromise. |
| `qwen2.5:7b` or `mistral:7b` | 7B | Upper bound on accuracy, lower bound on throughput. Establishes what you are giving up by going small. |

Constraints to check before committing to the set:
- **Licence.** Each model's licence must be recorded on Slide 12. Llama models
  carry the Llama Community Licence; Qwen and Mistral carry their own terms. The
  client is a commercial financial institution — an academic-use-only model is
  not deployable and that is a legitimate reason to exclude one.
- **Memory.** A 7B model at Q4 needs roughly 5–6 GB resident. Confirm your
  Ollama host has it, and that loading it does not push the box into swap —
  swapping will make your latency numbers meaningless.
- **Instruction following.** The prompt asks for a bare category number. Some
  base (non-instruct) models will not comply. Check the parse rate on a handful
  of non-golden tickets before committing — this is allowed, they are not golden
  tickets.

## Pinning

Run `tools/pin_models.sh` after pulling. It records tag, digest, parameter count,
quantisation and size into `docs/model_pins.md`. **The same pins must be reported
with your results** — if you re-pull mid-project and the digest changes, your
earlier numbers no longer describe the model you are recommending.

## Our set (confirmed by Gabriel (M3) on 7 Oct 2026, before the freeze)

We adopt the suggested starting set. It spans **four size classes, a 15× range in parameters**, and all four run on the pinned Ollama 0.5.7 image.

| Model | Size class | Licence (Slide 12) | In the set to demonstrate |
|---|---|---|---|
| `qwen2.5:0.5b` | sub-1B | Apache-2.0 | The floor. Is inference still the bottleneck when the model is this small, and how often does it fail to follow the output format (`UNPARSED`)? |
| `llama3.2:1b` | 1B | Llama 3.2 Community Licence + Acceptable Use Policy | The plausible "ship it" small model. Calibrated on Machine A with made-up tickets: about 3.0 s for a typical 320-token ticket (`docs/prediction_record.md`). |
| `llama3.2:3b` | 3B | Llama 3.2 Community Licence + Acceptable Use Policy | The mid-size compromise, and the model we stress-test. |
| `qwen2.5:7b` | 7B | Apache-2.0 | The accuracy ceiling on CPU: what the client gives up by going small. Its capacity is the lower bound on throughput. |

Exact tags, sha256 digests, quantisation and sizes are in `docs/model_pins.md`. Report the same pins with the results.

## Justification for our set

- **Shape of the curve.** The four sizes give the accuracy/latency curve a shape rather than a point. If accuracy rises steeply from 0.5B to 3B and flattens at 7B, the client should buy a mid-size model. If it keeps rising, the client is paying in latency for every point of accuracy.
- **Size against family.** Two families, each at two sizes, separate the effect of size from the effect of family: Qwen 0.5B vs 7B, Llama 1B vs 3B.
- **Deployable licences.** All four permit commercial on-premise use. Apache-2.0 has no conditions. The Llama licence applies only above 700 M monthly users, and needs the "Built with Llama" attribution on Slide 12.
- **Deliberately left out:**
  - **Qwen2.5-3B and Qwen2.5-72B**, which ship under Qwen's *research / non-commercial* licences. However well they scored, the client could not deploy them.
  - **Models of 13B and above.** At roughly 2× the 7B prompt-evaluation cost on the same 4-core limit, they would fail R1 before any queueing.
  - **Gemma 3**, which needs a newer Ollama than the pinned 0.5.7, and re-pinning the engine is not worth it for a fifth point.
