# ICT3113 Assignment 1 — Ticket Triage Service

**Group P2-9** · Team number **9** → dataset rows **9000–9999**

> If your registered team number is not 9, change `TEAM` in the `Makefile` and
> `TEAM_NUMBER` in `.env`, then re-run `make slice`. Everything downstream
> follows from those two values.

A CPU-only, on-premise complaint triage service: `POST /tickets` classifies a
complaint narrative into one of seven categories using a local Ollama model, and
`GET /search` / `GET /stats` expose what has been stored. This repository is both
the system under test and the evidence base for the report.

## Quick start

```bash
cp .env.example .env
make slice                       # rows 9000-9999 out of the course CSV
make golden                      # 175 candidates, source labels withheld
make sheets                      # blank sheets for two annotators
# ... label independently, commit one sheet per annotator ...
make agree                       # kappa + disagreement worklist
# ... adjudicate every disagreement ...
make merge                       # golden/golden_set.csv
make freeze                      # pre-flight, then commit — Step 5 is now unlocked
```

Service:

```bash
make up MODEL=llama3.2:1b
docker exec triage-ollama ollama pull llama3.2:1b
make check
```

## Layout

```
service/            FastAPI triage service + Dockerfile (the baseline)
tools/              dataset, golden-set, accuracy and analysis tooling
jmeter/             open-model load test plan + run matrix script
golden/             labelling protocol, label sheets, frozen golden set
docs/               workload model, requirements, prediction record, playbook
results/            .jtl files, service logs, accuracy output — EVIDENCE, commit these
data/              team slice + JMeter feed files
```

## The one rule that governs the schedule

**Step 5 cannot begin until Steps 1–4 are complete and committed.** The golden
test set and the prediction record must exist in git *before* the first
benchmark run. `tools/accuracy_harness.py` refuses to run against an uncommitted
golden set, and `make freeze` checks the rest.

This is not bureaucracy. Labelling after you have seen model output drags labels
toward whatever the model said, and quietly destroys the accuracy measurement.

## What is deliberately not optimised

`POST /tickets` is synchronous: it does not return until Ollama answers. There is
no caching, no queuing, no batching, no retries. `GET /search` is an unindexed
`LIKE` scan. All of this is intentional — the baseline exists to be measured, and
optimisation is Assignment 2. Do not improve it before you have measured it.

## What this scaffold does NOT do for you

Deliberately, because these are what the assignment actually assesses:

1. **Labelling.** Two team members must label all ~175 tickets independently.
   No tool here generates labels, and generating them would defeat Step 1.
2. **The workload model figures.** `docs/workload_model.md` has the structure and
   the derivations; the numbers and citations are research you must do.
3. **The predictions.** `docs/prediction_record.md` is a form. The guesses are
   yours, and vague guesses score zero.
4. **Running the tests.** Real CPU inference, on your hardware, three runs per
   configuration, load generator on a separate machine.
5. **The recommendation.** It has to follow from your measurements and hold
   against your own requirements.

## Evidence discipline

Every number in the deck must be traceable to a `.jtl` file or a line in
`results/logs/requests.jsonl`. After each run:

```bash
python3 tools/reconcile.py --jtl results/jtl/<tag>.jtl \
    --log results/logs/requests.jsonl --run-id <tag>
```

Do not report a run that does not reconcile until you can explain the gap —
though the gap itself is often a finding worth a line on Slide 9.
