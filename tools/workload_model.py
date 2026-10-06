#!/usr/bin/env python3
"""Recompute every derived figure in docs/workload_model.md.

Cited inputs and labelled estimates are constants below; ticket lengths come
from data/team_slice.csv. Writes docs/workload_model.json and, if matplotlib is
installed, docs/workload.png for Slide 3.

    python3 tools/workload_model.py
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

csv.field_size_limit(10 ** 9)
ROOT = Path(__file__).resolve().parents[1]

# cited [3], [2]
H2_2024_COMPLAINTS = 70_569
WEEKDAY_SHARE = {"Sun": .060, "Mon": .154, "Tue": .178, "Wed": .176, "Thu": .173, "Fri": .165, "Sat": .094}
BUSIEST_MONTH_FACTOR = 1290 / (14_323 / 12)
# estimates E2-E6 (docs/workload_model.md)
BUSINESS_HOURS_SHARE, BUSINESS_HOURS, PEAK_HOUR_FACTOR = 0.70, 10, 1.5
SEARCHES_PER_TICKET, SURGE_FACTOR = 3, 2.0
TICKETS_PER_AGENT_DAY, WORKING_DAYS = 25, 250
MISROUTE_AGENT_MIN = 5


def pct(s, p):
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main() -> int:
    annual = 2 * H2_2024_COMPLAINTS
    weekly = annual / 52.18
    days = {d: weekly * s for d, s in WEEKDAY_SHARE.items()}
    peak_day = max(days.values()) * BUSIEST_MONTH_FACTOR
    quiet_day = min(days.values())
    mean_hour = annual / 8760
    peak_hour = peak_day * BUSINESS_HOURS_SHARE / BUSINESS_HOURS * PEAK_HOUR_FACTOR
    offpeak_hour = quiet_day * (1 - BUSINESS_HOURS_SHARE) / (24 - BUSINESS_HOURS)
    design_peak_min = math.ceil(peak_hour / 60 * 10) / 10
    with open(ROOT / "data" / "team_slice.csv", newline="", encoding="utf-8") as fh:
        lengths = sorted(len(r["narrative"]) for r in csv.DictReader(fh))
    m = {
        "annual_tickets": annual, "weekly_mean": round(weekly, 1), "daily_mean": round(annual / 365, 1),
        "mean_per_hour": round(mean_hour, 2), "mean_per_s": round(mean_hour / 3600, 5),
        "peak_day": round(peak_day, 1), "quiet_day": round(quiet_day, 1),
        "peak_hour": round(peak_hour, 1), "offpeak_hour": round(offpeak_hour, 2),
        "peak_over_mean": round(peak_hour / mean_hour, 2), "peak_over_offpeak": round(peak_hour / offpeak_hour, 1),
        "design_peak_per_min": design_peak_min, "design_peak_per_s": round(design_peak_min / 60, 4),
        "surge_per_min": design_peak_min * SURGE_FACTOR, "surge_per_s": round(design_peak_min * SURGE_FACTOR / 60, 4),
        "agents": round(annual / WORKING_DAYS / TICKETS_PER_AGENT_DAY, 1),
        "peak_searches_per_min": round(peak_hour * SEARCHES_PER_TICKET / 60, 2), "search_ratio": SEARCHES_PER_TICKET,
        "misroute_hours_per_pct": round(annual * 0.01 * MISROUTE_AGENT_MIN / 60, 1),
        "misroute_hours_at_15pct": round(annual * 0.15 * MISROUTE_AGENT_MIN / 60, 0),
        "length_chars": {"n": len(lengths), "min": lengths[0], "p50": round(pct(lengths, 50)), "p95": round(pct(lengths, 95)),
                         "max": lengths[-1], "mean": round(sum(lengths) / len(lengths))},
    }
    (ROOT / "docs" / "workload_model.json").write_text(json.dumps(m, indent=2))
    print(json.dumps(m, indent=2))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return 0
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.4))
    ax[0].hist(lengths, bins=40, color="#2b6cb0")
    for p, ls in ((50, "-"), (95, "--")):
        v = pct(lengths, p)
        ax[0].axvline(v, color="#c53030", ls=ls, lw=1)
        ax[0].text(v, ax[0].get_ylim()[1] * .92, f" p{p}={v:.0f}", fontsize=8, color="#c53030")
    ax[0].set(xlabel="narrative length (characters)", ylabel="tickets")
    ax[0].set_title(f"Ticket length, team rows (n={len(lengths):,})", fontsize=10)
    prof = [(1 - BUSINESS_HOURS_SHARE) / 14] * 24
    shape = [0.8, 1.0, 1.5, 1.4, 1.0, 1.3, 1.5, 1.2, 0.8, 0.5]
    for h, w in enumerate(shape):
        prof[8 + h] = w / sum(shape) * BUSINESS_HOURS_SHARE
    ax[1].bar(range(24), [p * peak_day for p in prof], color="#2f855a")
    ax[1].axhline(peak_hour, color="#c53030", ls="--", lw=1)
    ax[1].text(0, peak_hour * 1.03, f"design peak {peak_hour:.0f}/h", fontsize=8, color="#c53030")
    ax[1].set(xlabel="hour of day", ylabel="tickets / hour")
    ax[1].set_title("Peak-day profile (illustrative, estimates E2-E3)", fontsize=10)
    fig.tight_layout()
    fig.savefig(ROOT / "docs" / "workload.png", dpi=170)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
