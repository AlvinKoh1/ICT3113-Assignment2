# Slide Outline — Group P2-9.pptx (max 12 slides)

File name on submission: `GroupP2-9.pptx` — check xSiTe for whether your group
identifier should be formatted `Group09.pptx` instead; the brief's example is
`Group01.pptx`.

| # | Slide | Must contain | Source in this repo |
|---|---|---|---|
| 1 | Cover | Group number, all names + student IDs, project title, **GitHub repo link** (must rebuild with `docker compose`) | — |
| 2 | Service Architecture | Component diagram (triage service, Ollama, storage, load generator), the three endpoints, explicit confirmation baseline is **synchronous, no caching, no queuing** | `service/app/main.py` docstring |
| 3 | Workload Model | Volumes, search rates, peak vs non-peak, ticket length distribution, **a citation per figure**, estimates flagged as estimates | `docs/workload_model.md` |
| 4 | Requirements | R1–R6 as testable statements: number + percentile + load condition; justification from the workload model | `docs/requirements.md` |
| 5 | Candidate Models | 3–5 models, **tag + digest each**, size classes, justification for the set | `docs/candidate_models.md`, `docs/model_pins.md` |
| 6 | Golden Test Set | Protocol summary + revisions, **inter-annotator agreement statistic**, disagreement count, 1–2 worked examples | `golden/labelling_protocol.md`, `agreement.py` output |
| 7 | Test Environment | Hardware/software per machine, **confirmation load generator was separate**, scaling to client, limitations | `docs/test_environment.md` |
| 8 | Playbook | Step-by-step per test, the open-loop JMeter config, diagram/flowchart | `docs/playbook.md` |
| 9 | Load + Stress Results | p50/p95/p99, throughput, error rate, per rate, per model, **across three runs**; the stress limit; interpretation + diagnosed bottleneck | `analyze_jtl.py` output |
| 10 | Accuracy Results | Overall + per-category accuracy per model, confusion matrix highlights | `results/accuracy/summary_*.json` |
| 11 | Predictions, Recommendation, Defence | Predictions vs outcomes + **where you were wrong and why**, recommended model defended against R1–R6, any requirement **no** candidate meets | `docs/prediction_record.md` |
| 12 | References | CFPB database, Ollama, **each model's licence**, every workload source | — |

## Things that lose marks

- A number on a slide that is not in a `.jtl` or a service log. Treated as
  unsupported, and fabrication is an **academic integrity matter**, not a
  deduction.
- Closed-loop results presented against a throughput or latency requirement —
  explicitly not accepted.
- A recommendation that contradicts your own stated requirements. Automatic fail
  on that component regardless of which model you pick.
- Single-run results. "A single run is not a measurement."
- A golden set with suspiciously perfect agreement and no recorded resolutions.
- A prediction record so vague it cannot be wrong.

## Things that gain marks

- "No candidate meets R__" — measured carefully, argued clearly. The brief calls
  this a **strong result**.
- A specific prediction that turned out wrong, with a good account of *why* your
  mental model was off.
- Threats to validity you found yourself and stated before the marker did.
