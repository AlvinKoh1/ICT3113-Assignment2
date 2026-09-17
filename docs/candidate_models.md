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

## Justification for our set

<Write 3–5 sentences. Cover: why these size classes, why these families, what
each candidate is in the set to *demonstrate*, and what you deliberately left
out and why.>
