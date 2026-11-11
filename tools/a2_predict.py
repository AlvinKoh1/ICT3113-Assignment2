#!/usr/bin/env python3
"""Assignment 2, Step 3: numbers behind the prediction record (run BEFORE any A2 measurement).

Inputs are Assignment 1 data only:
  * per-model latency vs narrative length: least-squares fit on the TUNING rows of
    the Assignment 1 accuracy run (sequential, single request);
  * the fixed speed-test ticket list (data/a2_speed_rows.csv) and its lengths;
  * the tuning-set replay of the rule (docs/a2/tuning_analysis.json).

Latency under load is predicted with a processor-sharing queue: Ollama gives every
in-flight request an equal share of the 4-CPU quota, so k requests in flight each
run k times slower. Arrivals are Poisson at one per 2*S. The model is first checked
against Assignment 1's measured qwen2.5:7b at 1 ticket/min (p50 70.0 s).

    python3 tools/a2_predict.py   -> docs/a2/prediction_inputs.json
"""
from __future__ import annotations

import random
import statistics as st

from a2_common import DOCS_A2, ROOT, a1_predictions, golden, jdump, jload, pct, read_csv, split_rows

G = golden()
TUNE = split_rows("tune")
CUTS = (400, 500)


def fit(model):
    P = a1_predictions(model)
    xs = [len(G[r]["narrative"]) for r in TUNE]
    ys = [float(P[r]["server_latency_ms"]) / 1000 for r in TUNE]
    mx, my = st.mean(xs), st.mean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    return {"a": a, "b": b, "r2": 1 - sum(e * e for e in resid) / sum((y - my) ** 2 for y in ys)}


F = {m: fit(m) for m in ("llama3.2:3b", "qwen2.5:7b")}


def svc(model, chars):
    f = F[model]
    return max(0.5, f["a"] + f["b"] * chars)


def service_time(config, chars):
    if config == "top7b":
        return svc("qwen2.5:7b", chars)
    cut = int(config.replace("cascade", ""))
    return svc("llama3.2:3b", chars) if chars <= cut else svc("qwen2.5:7b", chars)


def simulate_ps(lam, works, duration_s, seed):
    """Processor sharing, Poisson arrivals at rate lam for duration_s; ticket works cycled in order.
    Returns response times of all arrivals (run to completion)."""
    rng = random.Random(seed)
    t, arrivals = 0.0, []
    while True:
        t += rng.expovariate(lam)
        if t > duration_s:
            break
        arrivals.append(t)
    jobs = [{"arr": a, "rem": works[i % len(works)], "done": None} for i, a in enumerate(arrivals)]
    now, active, i = 0.0, [], 0
    while i < len(jobs) or active:
        nxt_arr = jobs[i]["arr"] if i < len(jobs) else float("inf")
        if active:
            k = len(active)
            j = min(active, key=lambda x: x["rem"])
            fin = now + j["rem"] * k
        else:
            fin = float("inf")
        if nxt_arr <= fin:
            dt = nxt_arr - now
            for x in active:
                x["rem"] -= dt / len(active)
            now = nxt_arr
            active.append(jobs[i]); i += 1
        else:
            dt = fin - now
            for x in active:
                x["rem"] -= dt / len(active)
            now = fin
            j["done"] = now
            active.remove(j)
    return [j["done"] - j["arr"] for j in jobs]


def run_many(lam, works, duration_s, n=400):
    p50s, pooled = [], []
    for s in range(n):
        r = simulate_ps(lam, works, duration_s, s)
        if r:
            p50s.append(st.median(r)); pooled += r
    return {"p50_median": st.median(p50s), "p50_q10": pct(p50s, 10), "p50_q90": pct(p50s, 90), "p95_pooled": pct(pooled, 95)}


def main() -> int:
    speed = read_csv(ROOT / "data" / "a2_speed_rows.csv")
    chars = [int(r["chars"]) for r in speed]
    calib = [int(r["chars"]) for r in read_csv(ROOT / "data" / "a2_calib_rows.csv")]
    S = st.median(svc("qwen2.5:7b", c) for c in calib)
    lam = 1 / (2 * S)
    dur = max(5, round(S)) * 60

    # Check the queue model against Assignment 1: 7b at 1/min, 10-min runs, A1 ticket feed lengths.
    a1_feed = [len(r["narrative"]) for r in read_csv(ROOT / "data" / "team_slice.csv")]
    check = run_many(1 / 60, [svc("qwen2.5:7b", c) for c in a1_feed[:60]], 600, 200)

    out = {"fits": F, "S_pred_s": S, "rate_per_min": 60 * lam, "duration_min": dur / 60,
           "queue_model_check_a1_7b_1pm": {"predicted_p50": check["p50_median"], "measured_p50": 70.0,
                                           "predicted_p95": check["p95_pooled"], "measured_p95": 150.6},
           "configs": {}}
    tune = jload(DOCS_A2 / "tuning_analysis.json")
    for cfg in ("top7b", "cascade400", "cascade500"):
        works = [service_time(cfg, c) for c in chars]
        rho = lam * st.mean(works)
        sim = run_many(lam, works, dur)
        d = {"mean_service_s": st.mean(works), "median_service_s": st.median(works), "utilisation": rho, **sim}
        if cfg != "top7b":
            cut = int(cfg.replace("cascade", ""))
            t = tune["families"]["length"]["llama3.2:3b"][str(cut)]
            d.update({"esc_frac_load": sum(c > cut for c in chars) / len(chars),
                      "esc_frac_tune": t["esc_frac"], "tune_correct": t["correct"], "tune_acc": t["acc"],
                      "tune_per_category": t["per_category"]})
        out["configs"][cfg] = d
    out["tune_reference"] = tune["reference"]["per_category"]
    jdump(DOCS_A2 / "prediction_inputs.json", out)
    print(f"S predicted {S:.1f} s -> rate {60*lam:.3f}/min, run {dur/60:.0f} min")
    print(f"fits: " + "; ".join(f"{m}: {f['a']:.1f} + {f['b']*1000:.1f} s/1000 chars (R2 {f['r2']:.2f})" for m, f in F.items()))
    print(f"queue-model check (A1 7b @ 1/min): p50 {check['p50_median']:.0f} s predicted vs 70.0 measured; "
          f"p95 {check['p95_pooled']:.0f} vs 150.6")
    for c, d in out["configs"].items():
        print(f"{c:11s} mean svc {d['mean_service_s']:.1f} s  rho {d['utilisation']:.2f}  p50 {d['p50_median']:.0f} s "
              f"(10-90 % of runs {d['p50_q10']:.0f}-{d['p50_q90']:.0f})  p95 {d['p95_pooled']:.0f} s"
              + (f"  esc(load) {d['esc_frac_load']*100:.0f} %" if "esc_frac_load" in d else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
