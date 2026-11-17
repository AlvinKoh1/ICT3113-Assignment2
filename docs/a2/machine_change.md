# Machine A changed for Assignment 2 — Group P2-9

Recorded 16 Nov 2026, **before any Assignment 2 measurement**. The brief (Scope: "If you must change machines, report it and explain why") allows the change but requires this record. The machine facts the tools read are in `docs/a2/machine_a2.json`.

## Why

The Assignment 1 Machine A (Irfan's i9-10900K PC, Tailscale `100.88.74.36`) is no longer available to the team. Assignment 2 runs on Irfan's other PC. Machine B (Uwais's laptop) is unchanged.

## What is the same

| | A1 Machine A | A2 Machine A |
|---|---|---|
| Ollama image / build | `ollama/ollama:0.5.7` (`0.5.7-0-ga420a45-dirty`) | same |
| Ollama container limits | 4-CPU quota, 8 GiB | same (`NanoCpus=4000000000`, `Memory=8589934592`) |
| Model tags and digests | `docs/model_pins.md` | identical, all four (checked against the Ollama registry and by `tools/a2_preflight.sh`) |
| Prompt, decoding | v1, temperature 0, seed 42, `num_predict` 16, `num_ctx` 2048 | same |
| `OLLAMA_NUM_PARALLEL` | 4 (auto in A1) | 4 (pinned) |
| GPU | RTX 3090 present, not mapped | RTX 4070 present, not mapped (Ollama log: `library=cpu`) |

## What differs

| | A1 Machine A | A2 Machine A |
|---|---|---|
| CPU | Intel i9-10900K, 10C/20T | AMD Ryzen 7 7700, 8C/16T |
| Host RAM | 48 GB DDR4 | 32 GB |
| WSL 2 VM | capped at 12 GB (`.wslconfig`) | default (no `.wslconfig`), ~15.2 GiB; the Ollama container is capped at 8 GiB either way |
| OS | Windows 11 Pro 26200 | Windows 11 IoT Enterprise LTSC 2024 (26100), Ubuntu 24.04 in WSL 2 |
| Docker Engine | 29.8.2 | 29.9.3 |
| Ollama runner threads | 10 (auto = physical cores) | 8 (auto = physical cores) |
| Tailscale address | `100.88.74.36` | new address (given to Machine B) |

The container limits are what the client constrains (no extra CPU or RAM for Ollama), and they are unchanged. The thread count follows the host's core count automatically; it is recorded once and held constant for every A2 configuration, as the brief requires.

## Consequences, and what we did

1. **Single-model accuracy is re-measured, not reused.** Step 4 allows reusing A1 single-model records only when the machine is unchanged. All four single models are re-run on the 87 test tickets on the A2 machine (`tools/a2_accuracy_all.sh single-<tag>`, stage 2 of `tools/a2_machineA_all.sh`).
2. **The limits come from this machine's 7b run.** Step 1 defines them from the top model's test-set accuracy, so `tools/a2_limits.py --source a2` recomputes `docs/a2/limits.json` from the re-run. The A1-record scores are kept alongside for comparison (`a1_records_comparison` in `limits.json`, and in `docs/a2/accuracy_notes.md`).
3. **The design is not changed.** The split, the escalation rule, the cut-offs (400, 500) and the prediction record were committed before this change and before any measurement, and stay as they are. They were built from A1 records and A1 timings; where a prediction misses because the machine is faster or slower, the prediction account says so instead of revising it.
4. **The memory check's slowdown test** compares each model's prompt-eval speed with the same model running alone on this machine (its single-model re-run), not with the A1 CPU.
5. **Speed figures** were never going to be reused from A1; everything is measured on the A2 machine under the A2 conditions.
6. **Run order** on Machine A: preflight → single-model accuracy + limits → memory check → cascade accuracy → S calibration → speed test (about 12 h).
