# ICT3113 Assignment 1 & 2 — Ticket Triage Service

> **Assignment 2 (due Fri 27 Nov, 23:59): who does what is in [`docs/a2/TEAM_GUIDE.pdf`](docs/a2/TEAM_GUIDE.pdf); commands in [`docs/a2/RUNBOOK.md`](docs/a2/RUNBOOK.md).**
> Cascade `llama3.2:3b` → `qwen2.5:7b` by ticket length (T = 400 and 500 chars), inside `POST /tickets`
> (`service/app/cascade.py`, rule in `docs/a2/escalation_rule.md`). Golden split, limits, tuning analysis and the
> prediction record are committed before any A2 measurement. Deck: `python3 deck/build_deck_a2.py` → `deck/Group09_A2.pptx`.
>
> | A2 file | What |
> |---|---|
> | `golden/a2_split.csv` | tuning (odd positions) / test (even) split |
> | `docs/a2/limits.json` | overall + per-category accuracy limits from 7b's test-set score |
> | `docs/a2/tuning_analysis.md` | every candidate rule replayed on the tuning set; why the length rule |
> | `docs/a2/escalation_rule.md` | the rule, settings, memory fallback (supporting file) |
> | `docs/a2/prediction_record.md` | predictions, committed before testing (supporting file) |
> | `data/a2_speed_rows.csv` | speed-test workload rows, fixed order (supporting file) |
> | `tools/a2_*.py, tools/a2_*.sh, jmeter/a2_*` | memory check, accuracy, S calibration, speed runs, analysis |
> | `results/a2/` | all A2 evidence (`.jtl`, run files, accuracy, memory, env); service log `results/logs/a2_requests.jsonl` |

**Group P2-9** · team number **9** → dataset rows **9000–9999**
Repo (A2): https://github.com/AlvinKoh1/ICT3113-Assignment2 · A1: https://github.com/gemokay/ICT3113-Assignment1

> **Status 6 Oct (merged from `alvin/continue`):** the team's step-by-step guide to everything left is in
> `docs/REMAINING_WORK.pdf` (source `docs/remaining_work.html`). Changes on this branch:
> - **JMeter drain fix:** the plan now pauses after the last arrival. Without it, JMeter cut off in-flight requests at the end of every run and logged them as errors (3–4 per 1-minute test run).
> - **Run tagging:** the service logs an `X-Run-ID` header, so `run_matrix.sh` tags every run without a restart.
> - **Stress test:** scripted, in `jmeter/run_stress.sh` and `tools/analyze_stress.py`.
> - **Labelling page:** `golden/labeller.html`.
> - **κ saved:** `golden/agreement.json`.
> - **Docs drafted:** workload model, requirements and prediction record, for M2/M3/M5 sign-off.
> - **Checks and slides:** `tools/requirements_check.py` and the deck generator `deck/build_deck.py`.

A CPU-only, on-premise complaint triage service. `POST /tickets` classifies a
complaint narrative into one of seven categories using a local Ollama model;
`GET /search` and `GET /stats` expose what has been stored.

This repository is **both** the system under test **and** the evidence base for
the report. Every number that ends up on a slide must be traceable to a file in
`results/`.

---

## Team and ownership

| | Name | Role | Owns | Slides |
|---|---|---|---|---|
| **M1** | **Irfan** | System Architecture & SUT Lead | **Machine A** (service + Ollama), logging, repo admin | 2, 7 |
| **M2** | **Alvin** | Workload Analyst & **Annotator B** | Workload model, requirements (SLAs) | 3, 4 |
| **M3** | **Gabriel** | Data Integrity & Protocol Lead, **Annotator A** | Labelling protocol, κ, candidate model picks | 5, 6 |
| **M4** | **Uwais** | JMeter Performance & Load Lead | **Machine B** (load generator), load + stress tests | 8, 9 |
| **M5** | **Muhaimeen** | Evaluation & Recommendation Lead | Prediction record, accuracy runs, final defence | 10, 11 |

Slide 1 (cover) and Slide 12 (references) are everyone's.

**Machine A is Irfan's, Machine B is Uwais's.** They must be two separate hosts on
the same LAN — this is a hard requirement, not a preference.

## Start here — pick your job

Steps 1–3 of the assignment run **in parallel**. Find your row and go.

| You are doing | Who | Read | Need Docker? |
|---|---|---|---|
| **Labelling** the golden set (Step 1) | Gabriel (A), Alvin (B) | [§1](#1-labelling-the-golden-set-step-1) | No |
| **Workload model + requirements** (Steps 3–4) | Alvin | [§2](#2-workload-model-and-candidate-models-steps-34) | No |
| **Candidate models + protocol** (Steps 1, 4) | Gabriel | [§1](#1-labelling-the-golden-set-step-1), [§2](#2-workload-model-and-candidate-models-steps-34) | No |
| **Prediction record** (Step 4) | Muhaimeen | [§5](#5-the-freeze-gate--the-one-rule-that-governs-the-schedule) | No |
| **Running the service** (Step 2) | Irfan | [§3](#3-running-the-service-step-2) | Yes |
| **Load testing** (Step 5) | Uwais | [§4](#4-load-testing-step-5) | Yes + JMeter |
| **Accuracy runs** (Step 5) | Muhaimeen | [§6](#6-accuracy-runs) | Yes |

Everyone should read [§5 The freeze gate](#5-the-freeze-gate--the-one-rule-that-governs-the-schedule)
and [§7 Do / Don't](#7-do--dont) before touching anything.

## Milestones

Two kinds of deadline below. Keep them straight.

### Imposed by the assignment

| When | What |
|---|---|
| ~~Fri 11 Sep~~ | Team registration on xSiTe — **done** |
| **Fri 9 Oct, 23:59** | **Submission.** `GroupXX.pptx` (max 12 slides) + golden test set + prediction record + labelling protocol with revisions + independent label sheets + agreement statistic |

Late work is penalised 15% per day and refused after four days.

The brief sets **no date** for the freeze. What it requires is an **ordering**:
the golden test set and prediction record must be committed *before* your first
benchmark run, and the commit history is the evidence. Freezing late costs you
schedule, not marks. Measuring before you freeze costs you the component.

### Our own targets (from `comprehensive_project_plan.html`)

Self-imposed. Missing one is a planning problem, not a rule breach — but
everything in Step 5 is blocked behind the first row.

| Target | What | Who |
|---|---|---|
| **Sun 20 Sep** | Freeze: golden set + κ + prediction record committed | Gabriel, Alvin, Muhaimeen |
| Sat 4 Oct | Three-run load tests, stress test, accuracy runs | Irfan, Uwais, Muhaimeen |
| Thu 8 Oct | Every figure reconciled, deck built, clean `docker compose` rebuild tested | All |

> **Note on week numbers:** the project plan's week labels are off by one against
> the brief. The brief anchors the calendar twice — registration at "end of Week 2
> (Friday 11 September 2026)" and submission at "Friday 9 October 2026 (Week 6)" —
> which puts **Week 3 at Sep 14–18**, Week 4 at Sep 21–25, Week 5 at Sep 28–Oct 2,
> Week 6 at Oct 5–9. The plan calls Sep 14–20 "Week 2"; it is Week 3. The plan's
> *dates* are fine, only its labels are wrong. Use dates, not week numbers.

```bash
git clone https://github.com/gemokay/ICT3113-Assignment1.git
cd ICT3113-Assignment1
```

---

## 1. Labelling the golden set (Step 1)

You need **nothing installed**. No Docker, no Ollama, no Python. Everything is
already in the repo.

1. **Read `golden/labelling_protocol.md` first**, all of it. If the team
   disagrees with the §4 precedence order, settle that *before* anyone labels —
   changing it afterwards invalidates every label already assigned.
2. Open **your own** sheet — **Gabriel → `golden/labels_A.csv`** (Annotator A),
   **Alvin → `golden/labels_B.csv`** (Annotator B). 175 rows each.
3. Fill the `label` column with one of the seven categories, copied **exactly**.
   `tools/agreement.py` rejects anything else. Use `confidence` (`high`/`low`)
   and `notes` freely — good notes make the adjudication meeting fast.
4. Label **every** row. Do not confer with the other annotator.
5. Commit and push **only when you are completely finished**:
   ```bash
   git add golden/labels_A.csv && git commit -m "Independent labels: Gabriel (Annotator A)" && git push
   ```
   Alvin does the same with `labels_B.csv`. **Two separate commits, one per
   annotator** — that is the evidence that the labelling was independent.

### Opening the CSV without destroying it

Each row holds a complaint up to 2,000 characters with embedded newlines and
quotes. **Do not double-click the file into Excel.** Excel rewrites quoting and
line endings on save and can break row alignment silently, taking your labels
with it.

Use one of:
- **Google Sheets** → File → Import → Upload → comma-separated, and turn **off**
  "Convert text to numbers, dates, and formulas". Export back as CSV.
- **LibreOffice Calc** → set character set to **UTF-8**, separator comma,
  "Quoted field as text" **on**.
- A plain text editor, if you can stand it.

Afterwards, confirm the file still has 175 data rows:
```bash
python3 -c "import csv,sys;csv.field_size_limit(10**9);print(len(list(csv.DictReader(open('golden/labels_A.csv')))))"
```

### Then, as a team

```bash
make agree     # inter-annotator agreement + golden/disagreements.csv
```
Adjudicate **every** row in `golden/disagreements.csv`: fill `adjudicated_label`
and a real `resolution_note`. Where a disagreement exposed a gap in the
protocol, add a rule to `golden/labelling_protocol.md` under a new version
heading and set `protocol_updated: yes`.

```bash
make merge     # builds golden/golden_set.csv — refuses if anything is unresolved
make freeze    # pre-flight checks; see §5
```

---

## 2. Workload model and candidate models (Steps 3–4)

No tooling needed. Fill in these files — they are structured, with the
derivations already laid out:

- `docs/workload_model.md` — ticket volumes, search rates, peak multiplier,
  length distribution. **Every figure needs a citation or a stated estimation
  method.** Primary source: the CFPB *Consumer Response Annual Report*.
- `docs/requirements.md` — R1–R6, each a number + a percentile + a load
  condition. A requirement with no load condition is untestable and scores zero.
- `docs/candidate_models.md` — 3–5 models spanning ≥2 size classes.
- `docs/prediction_record.md` — see §5. Must be specific enough to be **wrong**.

The measured ticket-length distribution for our slice (from
`tools/prepare_jmeter_data.py`) is: min 202, p50 **779**, p95 **1768**, max 1998
characters. That is real data — use it in the workload model rather than
estimating it.

Pin the models once chosen:
```bash
tools/pin_models.sh qwen2.5:0.5b llama3.2:1b llama3.2:3b qwen2.5:7b
```
This writes `docs/model_pins.md` with tag + digest for each. Commit it.

---

## 3. Running the service (Step 2)

### Prerequisites

- **Docker Desktop**, running. Launch it and **wait for the whale icon to stop
  animating** before running anything — the daemon accepts connections well
  after the app window appears, and commands fail confusingly in between.
- ~6 GB free disk for models.

### Bring it up

```bash
cp .env.example .env
make up MODEL=llama3.2:1b
```

First run builds the image (~1 min) and pulls the Ollama image (~1 min). It
waits for `/healthz` and prints a status line when ready.

**The model is not included.** Ollama starts empty — pull it separately:

```bash
docker exec triage-ollama ollama pull llama3.2:1b
```

### Smoke test

```bash
make check
```

Posts a mortgage complaint, searches for it, shows `/stats`. Expect a category,
a `latency_ms`, and `total: 1`.

**Run it twice.** The first request after a pull is cold and costs ~10× more.
Measured on this project's hardware:

| | model load | prompt eval (126 tok) | generate (2 tok) | total |
|---|---|---|---|---|
| cold | 793 ms | 2757 ms | 166 ms | **3972 ms** |
| warm | 12 ms | 204 ms | 122 ms | **354 ms** |

Note the cold penalty is **not** confined to model load — prompt eval on the
identical 126 tokens was 13× slower cold. This is why the playbook discards
whole warm-up requests rather than subtracting `load_duration`.

### Everyday commands

```bash
make check      # smoke test the three endpoints
make logs       # tail the request log
make down       # stop containers, keep data
make reset      # stop AND wipe stored tickets + logs — service starts empty
```

Switching models means restarting the stack:
```bash
make down && make up MODEL=llama3.2:3b
docker exec triage-ollama ollama pull llama3.2:3b
```
(Or pass `X-Model:` per request — but only the accuracy harness should do that.
Load tests must pin the model via `OLLAMA_MODEL` so `/healthz` reports what is
actually under test.)

---

## 4. Load testing (Step 5)

### Prerequisites

- **JMeter 5.5 or newer** (`Open Model Thread Group` was added in 5.5).
  Check: `jmeter --version`.
- JMeter runs on a **different machine** from the service and Ollama. This is a
  hard assignment requirement — a co-hosted load generator steals CPU from the
  service and the latency numbers become fiction.
- Python 3.9+ for the tools. They are **stdlib only** — no pip, no venv. Verified
  on 3.9, 3.11 and 3.14.

### Before the first run

```bash
python3 tools/prepare_jmeter_data.py
```

**Not optional.** Narratives contain commas, quotes and embedded newlines, and
JMeter's CSV Data Set Config is line-based with no real CSV parser — pointing it
at the raw CSV silently mangles tickets and you load-test on garbage. This
script emits a tab-delimited file with JSON-pre-escaped narratives.

Then open `jmeter/triage_load_test.jmx` **in the JMeter GUI once** and confirm
both thread groups load as *Open Model Thread Group*. The file is hand-written;
JMeter's XML serialisation shifts between versions and the GUI is the
authoritative check.

### Run

```bash
cd jmeter
./run_matrix.sh <service-host> llama3.2:1b      # rates default to 0.0167 0.0333 0.0667 (peak, surge, 2x surge)
```

- Three runs per rate, 10 minutes each, then a 120 s drain with no new arrivals.
- The rates come from `docs/workload_model.md`, and searches run at 3× the ticket rate.
- Every request carries `X-Run-ID=<model>_rate<R>_run<N>`, so `reconcile.py --run-id` separates runs **without restarting the service**.

### After every run

```bash
python3 tools/analyze_jtl.py results/jtl/<model>_rate<R>_run*.jtl --config-name "<model> @ <R> req/s"
python3 tools/reconcile.py --jtl results/jtl/<tag>.jtl --log results/logs/requests.jsonl --run-id <tag>
```

A run that does not reconcile is not reported until you can explain the gap —
though the gap itself is often a finding worth a line on Slide 9.

Full procedure, including the stress test, is in `docs/playbook.md`.

---

## 5. The freeze gate — the one rule that governs the schedule

**Step 5 cannot begin until Steps 1–4 are complete and committed.** The golden
test set and the prediction record must exist in git *before* the first
benchmark run. The commit history is the evidence that your labels and
predictions predate your measurements.

```bash
make freeze     # checks everything checkable
git add golden/ docs/prediction_record.md docs/model_pins.md
git commit -m "Freeze golden test set and prediction record (pre-benchmark)"
git push
```

`tools/accuracy_harness.py` **refuses to run** against an uncommitted golden set.
That guard is deliberate; do not reach for `--allow-uncommitted` on a run you
intend to report.

This is not bureaucracy. Labelling after you have seen model output drags labels
toward whatever the model said and quietly destroys the accuracy measurement.

It is a constraint on **order, not a deadline**. The brief attaches no date to the
freeze — only the requirement that it precede your first benchmark run. Our
Sun 20 Sep target is a team decision (see [Milestones](#milestones)).

---

## 6. Accuracy runs

After the freeze, per candidate model:

```bash
make reset
make up MODEL=<tag>
docker exec triage-ollama ollama pull <tag>
# send 3 throwaway tickets from NON-golden rows to warm the model, then:
python3 tools/accuracy_harness.py --base http://<svc>:8000 --model <tag> --digest <sha256:...>
```

Outputs `results/accuracy/predictions_<model>.csv` and `summary_<model>.json`
(overall + per-category precision/recall/F1, confusion matrix, latency
percentiles). Commit both.

---

## 7. Do / Don't

### Do

- **Warm the model** before any measurement. Discard whole warm-up requests.
- **Start the service empty** (`make reset`) before any reported run. `/stats`
  totals are part of the evidence.
- **Commit `results/`.** The `.jtl` files and service logs are evidence.
- **Archive `results/logs/requests.jsonl`** between reported runs, or set a
  distinct `RUN_ID` so `reconcile.py --run-id` can separate them. `make reset`
  deletes this file — fine for smoke traffic, not for a run you are reporting.
- **Three runs per configuration.** "A single run is not a measurement."
- **Record the negative results.** "No candidate meets R4", measured carefully
  and argued clearly, is explicitly called a strong result in the brief.

### Don't

- **Don't open `golden/candidates_sourcelabels.csv`** before labelling. It holds
  the consumer-selected labels, deliberately withheld from the candidate file.
  Seeing them anchors you to labels the assignment says are noisy.
- **Don't look at the other annotator's sheet** until yours is finished and
  pushed. Independence is on the honour system once both files are in the repo.
- **Don't open the CSVs in Excel by double-clicking.** See §1.
- **Don't optimise the baseline.** `POST /tickets` is synchronous, uncached,
  unqueued, unbatched, with no retries; `GET /search` is an unindexed `LIKE`
  scan. All deliberate. The baseline exists to be measured — optimisation is
  Assignment 2.
- **Don't tune the prompt against golden tickets.** Use non-golden rows from
  `data/team_slice.csv` if you need to sanity-check a model's output format.
- **Don't run the load generator on the same machine as the service.**
- **Don't report a closed-loop result.** Regular Thread Groups self-throttle;
  the brief will not accept them as evidence.
- **Don't invent a number.** Fabricated or irreconcilable measurements are
  treated as an academic integrity matter, not a marking deduction.

---

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop is opening but the daemon is not up yet. Wait for the whale icon to settle, then retry. |
| `/healthz` shows `"ollama": false` | Ollama container not up yet. `docker compose ps`, then `docker logs triage-ollama`. |
| `POST /tickets` returns 502 | Model not pulled. `docker exec triage-ollama ollama pull <tag>`. |
| Category comes back `UNPARSED` | The model ignored "reply with the number only". Check `raw_completion` in `results/logs/requests.jsonl`. Some base (non-instruct) models will never comply — that is a finding, and a reason to exclude a candidate. |
| First request takes ~4 s, later ones ~0.35 s | Expected. Cold model load + cold prompt eval. Warm up and discard. |
| `TypeError: unsupported operand type(s) for \|` | Tools need Python 3.9+. If you see this you are on something older, or a tool lost its `from __future__ import annotations` header. |
| JMeter: thread group fails to load | JMeter older than 5.5. Upgrade. |
| Tickets look truncated in JMeter | You fed it the raw CSV. Run `tools/prepare_jmeter_data.py` and point at the `.tsv`. |
| `reconcile.py` says NOT RECONCILED | Sample counts differ. Usually the log was not cleared or filtered between runs — use `--run-id`. |
| Harness says "REFUSING TO RUN" | The golden set is not committed. That is the freeze gate working. Commit it. |

---

## 9. Already built — do not rewrite

The project plan assigns some scripting that this repo already provides and that
has been tested. Check here before writing anything:

| Plan subtask | Owner | Already in the repo |
|---|---|---|
| 4.4 Log reconciliation script | Uwais | `tools/reconcile.py` — matches `.jtl` against the service log, flags count and error-rate mismatches |
| 5.2 Accuracy + confusion matrix | Muhaimeen | `tools/accuracy_harness.py` — per-category precision/recall/F1 + confusion matrix, **stdlib only, no sklearn needed** |
| 3.2 Cohen's kappa | Gabriel | `tools/agreement.py` — κ, raw agreement, disagreement worklist, confused-pair report |
| 4.2 Three-run benchmarks | Uwais | `jmeter/run_matrix.sh` + `tools/analyze_jtl.py` — p50/p95/p99, throughput, error rate, mean and spread across runs |
| 1.1–1.3 Service + logging | Irfan | `service/` — built, containerised, and smoke-tested end to end |
| 3.3 Model pinning | Gabriel | `tools/pin_models.sh` — writes tag + digest to `docs/model_pins.md` |

What is genuinely still to be written is **content**, not code: the labels, the
cited workload figures, the predictions, and the recommendation.

## 10. On the SLA numbers in the project plan

The plan proposes p95 < 3.0 s at 1.5 req/s, 3,000 tickets/hour, and 80% overall /
70% per-category accuracy. **Treat those as placeholders.** The brief requires
each requirement to be *derived from your workload model* — a number asserted up
front and not traceable to §2–§6 of `docs/workload_model.md` will not defend.

One early signal: a warm `llama3.2:1b` classified a short ticket in **354 ms**.
If that scales as expected, a p95 < 3.0 s target may be met so easily that it
proves nothing. A requirement that cannot fail is as weak as a prediction that
cannot fail. Set the numbers once Alvin's workload model exists.

## 11. Layout

```
service/       FastAPI triage service + Dockerfile  (the baseline — do not optimise)
tools/         dataset, golden-set, accuracy and analysis tooling (stdlib only)
jmeter/        open-model load test plan + run matrix script
golden/        labelling protocol, label sheets, frozen golden set
docs/          workload model, requirements, prediction record, playbook, slide outline
results/       .jtl files, service logs, accuracy output — EVIDENCE, commit these
data/          team slice (rows 9000–9999) + JMeter feed files
```

`docs/slides_outline.md` maps all twelve required slides to the file in this
repo that supplies each one.

## 12. If the team number is not 9

Change `TEAM` in the `Makefile` and `TEAM_NUMBER` in `.env`, then re-run
`make slice` and regenerate the golden candidates. Everything downstream follows
from those two values.
