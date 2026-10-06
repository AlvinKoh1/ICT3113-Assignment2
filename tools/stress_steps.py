#!/usr/bin/env python3
"""Stress-test steps from the measured single-request latency of one model.

mu = 60 / S tickets/min, S = p50 single-request latency (s) from
results/accuracy/summary_<model>.json (the accuracy harness runs sequentially,
so its latency is uncontended). Steps at 0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5 x mu,
rounded to whole tickets/min. Prints the steps string for run_stress.sh.

    python3 tools/stress_steps.py llama3.2:3b
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

model = sys.argv[1]
path = Path(__file__).resolve().parents[1] / "results" / "accuracy" / f"summary_{model.replace(':', '_').replace('/', '_')}.json"
S = json.loads(path.read_text())["latency_ms"]["p50"] / 1000
mu = 60 / S
steps = []
for f in (0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5):
    r = max(1, round(mu * f))
    if r not in steps:
        steps.append(r)
print(" ".join(map(str, steps)))
print(f"# {model}: single-request p50 {S:.2f}s -> capacity mu ~ {mu:.1f}/min", file=sys.stderr)
