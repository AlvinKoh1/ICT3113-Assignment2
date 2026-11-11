# Assignment 2 runbook — Group P2-9

Everything below runs on the **Assignment 1 machines, unchanged**: Machine A (Irfan's PC, service + Ollama, WSL 2) and Machine B (Uwais's laptop, JMeter, Git Bash). Nothing in this list may be skipped or reordered; the order is what the brief marks.

Budget: ~1 h set-up and memory check, ~2 h accuracy, ~15 min calibration, **~7 h speed test** (9 runs × ~45 min). Run the speed test overnight. Deadline: **Fri 27 Nov 2026, 23:59** (`Group09_A2.pptx` on xSiTe).

## 0. Already done and committed (do not redo)

| Commit | What |
|---|---|
| 1 | `golden/a2_split.csv` — odd positions = tuning (88), even = test (87). Committed first. |
| 2 | `docs/a2/limits.json` — 7b test set 68/87 = 78.2 % → overall limit 68.2 % (≥ 60/87); per-category limits. Single-model test-set scores from A1 records. |
| 3 | Escalation rule, prediction record, tuning analysis, speed-test row list, cascade code, all A2 tooling. **Must be on `main` before step 2 below.** |

## 1. Before anything (both machines)

```bash
git pull                        # both machines on the same commit
git log --oneline -5            # the prediction-record commit must be there
```

Machine A: `cp .env.example .env` if missing; `.env` must still say `OLLAMA_CPUS=4`, `OLLAMA_MEM=8g`. Do **not** change Docker Desktop / WSL memory or CPU. Same power settings as A1 (sleep off, Windows Update paused).

## 2. Machine A — rebuild, preflight, memory check (Step 2) — FIRST MEASUREMENT

```bash
docker compose up -d --build                     # rebuilds the service with the cascade code
tools/a2_preflight.sh initial                    # versions, digests, Ollama settings; must end "verdict: OK"
tools/a2_memory_check.sh                         # llama3.2:3b + qwen2.5:7b together
```

* `VERDICT: FIT` → continue with this pair.
* `DOES NOT FIT` → run `SMALL=llama3.2:1b tools/a2_memory_check.sh`, and from here on prefix **every** Machine A command with `SMALL=llama3.2:1b` (fallback in `docs/a2/escalation_rule.md` §5). If that also fails, the cascade is not feasible: keep the `ollama ps` evidence, skip to step 5 for `top7b` only, and say so on slide 2.

Commit: `git add results/a2/memory results/a2/env results/logs/a2_requests.jsonl && git commit -m "A2 memory check"`

## 3. Machine A — accuracy test (Step 4, first half) — ~2 h

```bash
tools/a2_accuracy_all.sh                          # cascade400 + cascade500 on the 87 test tickets
# optional, comparison only:  SETS="tune" tools/a2_accuracy_all.sh
```

Single models are not re-run (A1 records reused, test rows only — `results/a2/accuracy/single_*_test.json`); the preflight files are the evidence that digest, prompt, Ollama version and machine are unchanged.

Commit `results/a2/accuracy`, `results/logs/a2_requests.jsonl`.

## 4. S calibration (both machines) — ~10 min

Machine A: `tools/a2_machineA.sh calib`
Machine B: `jmeter/a2_calibrate.sh 100.88.74.36`

Writes `results/a2/calib/S.json` (three timings + rows) and `plan.json` (rate = 60/(2S) per min, run = S min (≥ 5), timeout = max(10S, 300 s), pause = timeout + 60 s rounded up). Commit `results/a2/calib` **before** the first speed run.

## 5. Speed test (both machines) — 3 configs × 3 runs, ~7 h

Start both at the same time; they hand over through `/healthz` and the service log.

Machine A:
```bash
tools/a2_machineA.sh top7b cascade400 cascade500
```
Machine B:
```bash
jmeter/a2_machineB.sh 100.88.74.36 top7b cascade400 cascade500
```

Per run, Machine A restarts Ollama, warms up with the same three tickets, checks `ollama ps` lists every model of the configuration (both for the cascade), then sets `/healthz` to `ready-<tag>`; Machine B calls `GET /stats`, runs JMeter at the planned rate for S minutes with the pause, calls `GET /stats` again. Only configurations that pass both accuracy limits are speed-tested, plus the cascade in all cases — so `top7b cascade400 cascade500` is the complete list (no other single model passes).

If a run is hit by a test-side fault (network drop, laptop sleep): **keep the files**, re-run it under a new tag (`RUNS=1` and rename to `run3b`, as in A1), and write it up in `results/a2/reconcile_notes.md`.

Commit `results/a2/jtl`, `results/a2/runs`, `results/a2/env`, `results/logs/a2_requests.jsonl`.

## 6. Analysis and deck (any machine with Python)

```bash
python3 tools/a2_analyze_speed.py                 # -> results/a2/speed/summary.md / .json
pip install python-pptx matplotlib
python3 deck/build_deck_a2.py                     # -> deck/Group09_A2.pptx (8 slides)
```

* Read `results/a2/speed/summary.md`: every run must say `Reconciled yes`. Any `NO` → explain it (unfinished requests, reload, etc.) in `results/a2/reconcile_notes.md` before using the number.
* Write `docs/a2/prediction_account.md` (where each prediction was wrong and why) and put a 3–5 bullet version in `deck/a2_text.json` under `"prediction_misses"` (template: `deck/a2_text.example.json`). Rebuild the deck.
* The deck's DRAFT banner disappears when nothing is pending. Open it, read every slide, and check one number per slide by hand against the raw `.jtl` / log.
* Save as `Group09_A2.pptx`; submit with the supporting files: `docs/a2/prediction_record.md`, `docs/a2/escalation_rule.md`, `data/a2_speed_rows.csv`.

## Things that void a result

* Two models not both listed in `ollama ps` before a cascade run (the script aborts).
* Any change to Ollama threads / parallel / context, container CPU or memory between configurations.
* A `.jtl` or log line that is deleted or edited. Redo under a new tag instead.
* Tuning the rule on test-set results. The cut-offs are fixed at 400 and 500.
