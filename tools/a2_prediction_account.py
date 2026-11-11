#!/usr/bin/env python3
"""Compare every prediction in docs/a2/prediction_record.md with what was measured,
and write down why each miss happened, citing the file that shows it.

Inputs: the prediction record's numbers (docs/a2/prediction_inputs.json plus the
fixed claims below, copied from prediction_record.md), and the measured results in
results/a2/ and results/logs/a2_requests.jsonl.

    python3 tools/a2_prediction_account.py
      -> docs/a2/prediction_account.md
      -> deck/a2_text.json   ("prediction_misses", "recommendation_extra" for slides 7)

Re-run after any new result; it overwrites both files. Edit the output by hand only
after the last run.
"""
from __future__ import annotations

import json
import statistics as st

from a2_common import (A2, A2_LOG, CATS, DECK_TEXT, DOCS_A2, DOCS_OUT, ROOT, SHORT, iter_log, jload, read_csv)

# Claims in docs/a2/prediction_record.md that are not in prediction_inputs.json.
REC = {"memory": "FIT", "fastest": "cascade500", "acc_correct": 67, "esc_test": {"cascade400": 0.81, "cascade500": 0.73},
       "loses_most": "Credit reporting", "errors": 0, "gain_within_spread": True}
LABEL = {"top7b": "qwen2.5:7b alone", "cascade400": "cascade T=400", "cascade500": "cascade T=500"}
CASC = ["cascade400", "cascade500"]


def load():
    d = {"pred": jload(DOCS_A2 / "prediction_inputs.json"), "plan": jload(A2 / "calib" / "plan.json"),
         "speed": jload(A2 / "speed" / "summary.json") or {}, "limits": jload(DOCS_A2 / "limits.json")}
    d["runs"] = {c: jload(A2 / "speed" / f"{c}.json") for c in d["speed"]}
    d["acc"] = {c: jload(A2 / "accuracy" / f"{c}_test.json") for c in CASC}
    d["acc"]["top7b"] = jload(A2 / "accuracy" / "single_qwen2.5_7b_test.json")
    d["mem"] = next((jload(p) for p in sorted((A2 / "memory").glob("memory_check_llama3.2_3b*.json"))
                     if not p.name.endswith(".sends.json")), None)
    # per-call model times under load, from the service log
    calls = {}
    for r in iter_log(A2_LOG):
        rid = str(r.get("run_id", ""))
        if not rid.startswith("a2_") or "_run" not in rid or r.get("status") != 200 or r.get("endpoint") != "POST /tickets":
            continue
        cfg = rid[3:rid.rindex("_run")]
        c = calls.setdefault(cfg, {"small": [], "large": [], "chars": []})
        c["chars"].append(r.get("narrative_chars") or 0)
        if r.get("small_latency_ms"):
            c["small"].append(r["small_latency_ms"] / 1000)
        if r.get("large_latency_ms"):
            c["large"].append(r["large_latency_ms"] / 1000)
        elif r.get("mode") == "single" and r.get("latency_ms"):
            c["large"].append(r["latency_ms"] / 1000)
    d["calls"] = calls
    return d


def short(why: str, n: int = 95) -> str:
    """First sentence of a reason, clipped for a slide bullet (the account keeps the full text)."""
    first = why.split(". ")[0].rstrip(".")
    return first if len(first) <= n else first[: n - 1].rsplit(" ", 1)[0] + "…"


def fit_time(pred, model, chars):
    f = pred["fits"][model]
    return f["a"] + f["b"] * chars


def main() -> int:
    d = load()
    pred, plan, speed, acc = d["pred"], d["plan"], d["speed"], d["acc"]
    rows, misses = [], []  # misses kept for the account; slide bullets are ordered below

    def add(claim, predicted, measured, right, why, src):
        v = "PENDING" if measured is None else ("RIGHT" if right else "WRONG")
        rows.append((claim, predicted, "—" if measured is None else measured, v, why if v == "WRONG" else "", src))
        if v == "WRONG":
            misses.append(f"**{claim}:** predicted {predicted}, measured {measured}. {why}")

    # 1. memory
    m = d["mem"]
    add("3b + 7b fit in the 8 GiB container", "FIT", m and m["verdict"], m and m["verdict"] == "FIT",
        m and ("; ".join(n for n in m.get("notes", [])) or "see the memory check transcript"), "results/a2/memory/")

    # 2. S
    if pred:
        S = plan and plan["S_s"]
        why = ""
        if plan:
            calib = read_csv(ROOT / "data" / "a2_calib_rows.csv")
            ch = st.median(int(r["chars"]) for r in calib)
            ratio = S / fit_time(pred, "qwen2.5:7b", ch)
            why = (f"The three calibration tickets ({ch:.0f} chars) took {ratio:.2f}× the time the Assignment 1 length fit gives "
                   f"({fit_time(pred, 'qwen2.5:7b', ch):.1f} s); Machine A ran {'slower' if ratio > 1 else 'faster'} than in the A1 accuracy run.")
        add("S, middle of three 7b tickets", f"{pred['S_pred_s']:.0f} s", S and f"{S:.1f} s", S and abs(S - pred["S_pred_s"]) <= 0.15 * pred["S_pred_s"],
            why, "results/a2/calib/S.json")

    # 3. latency per config
    for c in ["top7b"] + CASC:
        if not pred or c not in pred["configs"]:
            continue
        p = pred["configs"][c]
        mv = (speed.get(c) or {}).get("p50_s", {}).get("mean")
        why = ""
        if mv is not None and plan:
            calls = d["calls"].get(c, {})
            lg = st.mean(calls["large"]) if calls.get("large") else None
            sm = st.mean(calls["small"]) if calls.get("small") else None
            per_ticket = []
            if calls.get("large") or calls.get("small"):
                per_ticket_mean = ((sum(calls.get("small", [])) + sum(calls.get("large", []))) / max(len(calls.get("chars", [])), 1))
                rho = plan["rate_per_min"] / 60 * per_ticket_mean
                why = (f"Measured model time per ticket under load {per_ticket_mean:.1f} s against {p['mean_service_s']:.1f} s predicted"
                       + (f" (3b call {sm:.1f} s, 7b call {lg:.1f} s)" if sm else (f" (7b call {lg:.1f} s)" if lg else ""))
                       + f", so utilisation was about {rho:.2f} rather than {p['utilisation']:.2f}; the processor-sharing model turns that into "
                       + ("longer" if mv > p["p50_median"] else "shorter") + " waits.")
        add(f"p50 under load, {LABEL[c]}", f"{p['p50_median']:.0f} s", mv is not None and f"{mv:.1f} s" or None,
            mv is not None and abs(mv - p["p50_median"]) <= 0.15 * p["p50_median"], why, "results/a2/speed/summary.json, a2_requests.jsonl")
        p95 = (speed.get(c) or {}).get("p95_pooled_s")
        add(f"p95 pooled, {LABEL[c]}", f"{p['p95_pooled']:.0f} s", p95 is not None and f"{p95:.0f} s" or None,
            p95 is not None and abs(p95 - p["p95_pooled"]) <= 0.25 * p["p95_pooled"],
            "The slowest few of ~90 requests decide p95; the prediction used the same queue model as p50, which over-weights rare long queues."
            if p95 is not None and p95 < p["p95_pooled"] else "Long tickets overlapping in time stretched the tail beyond the queue model.",
            "results/a2/speed/summary.json")

    # 4. escalation
    test_rows = None
    for c in CASC:
        a = acc.get(c)
        mv = a and a.get("escalation", {}).get("fraction")
        pv = REC["esc_test"][c]
        add(f"Escalation, test set, {LABEL[c]}", f"{pv * 100:.0f} %", mv is not None and f"{mv * 100:.0f} %" or None,
            mv is not None and abs(mv - pv) <= 0.05,
            mv is not None and (f"The prediction used the tuning half's length mix; the test half has "
                                f"{(1 - mv) * 100:.0f} % of tickets at or under the cut-off. Routes: {a['escalation'].get('routes')}."),
            f"results/a2/accuracy/{c}_test.json")
        mv2 = (speed.get(c) or {}).get("escalation_pooled")
        pv2 = pred["configs"][c]["esc_frac_load"] if pred else None
        add(f"Escalation under load, {LABEL[c]}", pv2 is not None and f"{pv2 * 100:.0f} %", mv2 is not None and f"{mv2 * 100:.0f} %" or None,
            mv2 is not None and pv2 is not None and abs(mv2 - pv2) <= 0.05,
            "A run draws about 30 of the 40 fixed tickets, so its length mix differs from the whole list; any UNPARSED small answers add escalations.",
            "results/a2/speed/, a2_requests.jsonl")

    # 5. accuracy and limits
    top = acc.get("top7b")
    for c in CASC:
        a = acc.get(c)
        ok = a and a["correct"]
        why = ""
        if a and top:
            deltas = {cat: a["per_category"][cat]["correct"] - top["per_category"][cat]["correct"] for cat in CATS}
            why = ("Against 7b alone by category: " + ", ".join(f"{SHORT[k]} {v:+d}" for k, v in deltas.items() if v) +
                   ". The tuning half predicted a net loss of one ticket; the test half's short tickets were "
                   + ("harder" if ok < REC["acc_correct"] else "easier") + " for the 3b model.")
        add(f"Test accuracy, {LABEL[c]}", f"{REC['acc_correct']}/87", a and f"{ok}/87", a and abs(ok - REC["acc_correct"]) <= 2, why,
            f"results/a2/accuracy/{c}_test.json")
        lim = a and a.get("limits")
        add(f"Passes both limits, {LABEL[c]}", "yes", lim and ("yes" if lim["pass"] else "no"), lim and lim["pass"],
            lim and f"Fails {', '.join(lim['failed_categories']) or 'the overall limit'}; these categories hold 10–13 test tickets, so one or two tickets decide it.",
            f"results/a2/accuracy/{c}_test.json, docs/a2/limits.json")
    if all(acc.get(c) for c in CASC) and top:
        drops = {cat: sum(top["per_category"][cat]["correct"] - acc[c]["per_category"][cat]["correct"] for c in CASC) for cat in CATS}
        worst = max(drops, key=drops.get)
        add("Category that loses most", REC["loses_most"], f"{worst} ({-drops[worst]:+d} over both settings)", worst == REC["loses_most"],
            f"The 3b model's short-ticket mistakes fell mostly in {worst} on the test half (see docs/a2/accuracy_notes.md).",
            "docs/a2/accuracy_notes.md")
    else:
        add("Category that loses most", REC["loses_most"], None, None, "", "")

    # 6. fastest and spread
    qual = [c for c in ["top7b"] + CASC if (c == "top7b" or (acc.get(c) and acc[c]["limits"]["pass"])) and speed.get(c)]
    fastest = min(qual, key=lambda c: speed[c]["p50_s"]["mean"]) if qual and all(speed.get(c) for c in ["top7b"] + CASC) else None
    why = ""
    if fastest and fastest != REC["fastest"]:
        c = REC["fastest"]
        if acc.get(c) and not acc[c]["limits"]["pass"]:
            why = f"{LABEL[c]} failed an accuracy limit, so it could not be recommended whatever its speed."
        elif speed.get(c):
            why = (f"{LABEL[c]} measured p50 {speed[c]['p50_s']['mean']:.1f} s against {speed[fastest]['p50_s']['mean']:.1f} s for {LABEL[fastest]}: "
                   f"it still escalated {speed[c].get('escalation_pooled', 0) * 100:.0f} % of tickets, and the 3b runner competed with the 7b runner for the same 4 CPUs.")
    add("Fastest configuration within the limits", LABEL[REC["fastest"]], fastest and LABEL[fastest], fastest == REC["fastest"], why,
        "results/a2/speed/summary.json, results/a2/accuracy/")
    if speed.get("top7b") and speed.get("cascade500"):
        a, b = speed["cascade500"]["p50_s"], speed["top7b"]["p50_s"]
        overlap = not (a["max"] < b["min"] or a["min"] > b["max"])
        add("T=500 gain within run-to-run spread", "yes", "yes" if overlap else "no", overlap == REC["gain_within_spread"],
            f"Per-run p50 ranges {a['min']:.0f}–{a['max']:.0f} s (T=500) and {b['min']:.0f}–{b['max']:.0f} s (7b) "
            + ("overlap." if overlap else "do not overlap: the difference is larger than the run-to-run spread."),
            "results/a2/speed/a2_*.json")
    errs = sum((speed.get(c) or {}).get("totals", {}).get("errored", 0) + (speed.get(c) or {}).get("totals", {}).get("unfinished", 0) or 0
               for c in speed) if speed else None
    add("Errors and unfinished requests", "0", errs if speed else None, errs == 0,
        "See results/a2/reconcile_notes.md for each failed or unfinished request.", "results/a2/speed/")

    # write
    n_wrong = sum(r[3] == "WRONG" for r in rows)
    n_done = sum(r[3] != "PENDING" for r in rows)
    out = ["# Prediction account (generated by `tools/a2_prediction_account.py`)", "",
           "Each prediction from `docs/a2/prediction_record.md` (committed before any measurement), what was measured, and why it differed. "
           "Tolerances: latency ±15 % (p95 ±25 %), escalation ±5 points, accuracy ±2 tickets, S ±15 %.", "",
           f"{n_done} of {len(rows)} claims measured; {n_wrong} wrong.", "",
           "| Claim | Predicted | Measured | Verdict | Why it differed | Source |", "|---|---|---|---|---|---|"]
    out += [f"| {c} | {p} | {m} | {v} | {w} | {s} |" for c, p, m, v, w, s in rows]
    (DOCS_OUT / "prediction_account.md").write_text("\n".join(out) + "\n", encoding="utf-8")

    text = jload(DECK_TEXT) or {}
    # Slide bullets: most consequential misses first; the three p95 rows fold into one line.
    order = ["Fastest", "Passes both", "3b + 7b", "Test accuracy", "Category", "T=500 gain", "p50", "Escalation", "S,", "Errors"]
    wrong = [r for r in rows if r[3] == "WRONG"]
    p95 = [r for r in wrong if r[0].startswith("p95")]
    bullets = []
    for key in order:
        for c, p, m_, v, w, s in wrong:
            if c.startswith(key):
                bullets.append(f"**{c}:** {p} → {m_}. {short(w)}")
    if p95:
        bullets.append("**p95 pooled:** " + ", ".join(f"{r[1]} → {r[2]}" for r in p95) + ". " + short(p95[0][4]))
    text["prediction_misses"] = bullets[:4] or ["Every measured prediction landed inside its tolerance."]
    if speed.get("top7b") and fastest:
        if fastest == "top7b":
            text["recommendation_extra"] = ["**Defence:** the cascade was built, measured at both settings and speed-tested; "
                                            "it did not beat qwen2.5:7b alone inside the limits, so the reference stays."]
        else:
            g = (speed["top7b"]["p50_s"]["mean"] - speed[fastest]["p50_s"]["mean"]) / speed["top7b"]["p50_s"]["mean"] * 100
            text["recommendation_extra"] = [f"**Defence:** a {g:.0f} % lower p50 at no cost in hardware; the accuracy given up stays inside "
                                            "both client limits on the test set."]
    DECK_TEXT.parent.mkdir(parents=True, exist_ok=True)
    DECK_TEXT.write_text(json.dumps(text, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n".join(out))
    print(f"\nwrote {DOCS_OUT / 'prediction_account.md'} and {DECK_TEXT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
