#!/usr/bin/env python3
"""Assignment 2, Step 4 set-up: the fixed ticket lists, all from team rows OUTSIDE the golden set.

  data/a2_warmup_rows.csv      3 warm-up tickets, same three before every run.
                               W1 is short (200-300 chars) so the cascade sends it to
                               the small model at either cut-off; W2 and W3 are long
                               (1000-1300 chars) so they reach the large model.
  data/a2_calib_rows.csv       3 different tickets of typical length (closest to the
                               team-row median), used once to measure S on the top model.
  data/a2_speed_rows.csv       40 speed-test tickets in their fixed send order.
  data/a2_speed_tickets.tsv    the same 40, pre-escaped for JMeter (same format as A1).

Speed tickets are picked at evenly spaced length quantiles of the remaining pool,
so the list carries the pool's own mix of typical and long tickets, then put in a
fixed pseudo-random order (seed 3113) so length does not trend through a run.
A run at ~30 arrivals uses the first ~30; the file recycles if a run draws more.

    python3 tools/a2_workload.py
"""
from __future__ import annotations

import json
import random
import statistics as st

from a2_common import DOCS_A2, ROOT, read_csv, write_csv

N_SPEED = 40
SEED = 3113


def main() -> int:
    team = read_csv(ROOT / "data" / "team_slice.csv")
    golden_cands = {r["row"] for r in read_csv(ROOT / "golden" / "candidates.csv")}
    pool = sorted((r for r in team if r["row"] not in golden_cands), key=lambda r: int(r["row"]))
    L = lambda r: len(r["narrative"])
    team_median = st.median(L(r) for r in team)

    w1 = next(r for r in pool if 200 <= L(r) <= 300)
    longs = [r for r in pool if 1000 <= L(r) <= 1300][:2]
    warm = [w1] + longs
    used = {r["row"] for r in warm}

    calib = sorted((r for r in pool if r["row"] not in used), key=lambda r: (abs(L(r) - team_median), int(r["row"])))[:3]
    used |= {r["row"] for r in calib}

    rest = sorted((r for r in pool if r["row"] not in used), key=lambda r: (L(r), int(r["row"])))
    idx = [round((i + 0.5) * len(rest) / N_SPEED - 0.5) for i in range(N_SPEED)]
    speed = [rest[i] for i in idx]
    random.Random(SEED).shuffle(speed)

    def rec(rs, kind):
        return [{"row": r["row"], "chars": L(r), "role": kind} for r in rs]

    write_csv(ROOT / "data" / "a2_warmup_rows.csv", rec(warm, "warmup"))
    write_csv(ROOT / "data" / "a2_calib_rows.csv", rec(calib, "calibration"))
    write_csv(ROOT / "data" / "a2_speed_rows.csv", [dict(order=i + 1, **d) for i, d in enumerate(rec(speed, "speed"))])
    with open(ROOT / "data" / "a2_speed_tickets.tsv", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("row\tnarrative_json\n")
        for r in speed:
            esc = json.dumps(r["narrative"], ensure_ascii=True)[1:-1].replace("${", "$\\u007b")
            assert "\t" not in esc and "\n" not in esc
            fh.write(f"{r['row']}\t{esc}\n")

    lens = [L(r) for r in speed]
    first30 = lens[:30]
    summary = {
        "pool": "team rows 9000-9999 minus the 175 golden candidates",
        "pool_size": len(pool), "team_median_chars": team_median,
        "warmup_rows": [r["row"] for r in warm], "warmup_chars": [L(r) for r in warm],
        "calib_rows": [r["row"] for r in calib], "calib_chars": [L(r) for r in calib],
        "speed_rows": [r["row"] for r in speed],
        "speed_chars": {"min": min(lens), "median": st.median(lens), "max": max(lens), "mean": round(st.mean(lens))},
        "speed_share_le_400": sum(x <= 400 for x in lens) / len(lens),
        "speed_share_le_500": sum(x <= 500 for x in lens) / len(lens),
        "first30_share_le_400": sum(x <= 400 for x in first30) / 30,
        "first30_share_le_500": sum(x <= 500 for x in first30) / 30,
    }
    (DOCS_A2 / "workload.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
