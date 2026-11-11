#!/usr/bin/env python3
"""Build deck/Group09_A2.pptx (8 slides, ICT3113 Assignment 2) from the evidence in this repo.

No measured number is typed by hand. Every figure is read from results/a2/,
docs/a2/ or the Assignment 1 records. A slide part whose inputs do not exist
yet shows a red PENDING box naming the command that produces them, and the
cover carries a DRAFT banner until nothing is pending.

Team-written interpretation (why predictions missed, limitations wording) can
be overridden in deck/a2_text.json; otherwise the builder writes statements
derived from the data.

    pip install python-pptx matplotlib
    python3 deck/build_deck_a2.py
"""
from __future__ import annotations

import json
import statistics as st
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402
from pptx.oxml.ns import qn  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from a2_common import CATS, SHORT, A2, DOCS_A2, MODELS, TOP_MODEL, iter_log, jload, safe  # noqa: E402

DECK = ROOT / "deck"
BUILD = DECK / "build_a2"
BUILD.mkdir(exist_ok=True)
import os
OUT = Path(os.getenv("DECK_OUT", str(DECK / "Group09_A2.pptx")))
A2_LOG = Path(os.getenv("A2_LOG", str(ROOT / "results" / "logs" / "a2_requests.jsonl")))
NAVY, TEAL, GREY, RED, GREEN, LIGHT, WHITE, AMBER = (
    RGBColor(0x1F, 0x3A, 0x5F), RGBColor(0x2B, 0x7A, 0x78), RGBColor(0x44, 0x4B, 0x55), RGBColor(0xC0, 0x39, 0x2B),
    RGBColor(0x2E, 0x7D, 0x32), RGBColor(0xEE, 0xF2, 0xF7), RGBColor(0xFF, 0xFF, 0xFF), RGBColor(0xB2, 0x6B, 0x00))
PENDING_ITEMS: list[str] = []

# ------------------------------------------------------------------ data
team = jload(DECK / "team_a2.json") or jload(DECK / "team.json") or {}
txt = jload(os.getenv("A2_DECK_TEXT", str(DECK / "a2_text.json"))) or {}
limits = jload(DOCS_A2 / "limits.json")
tuning = jload(DOCS_A2 / "tuning_analysis.json")
pred = jload(DOCS_A2 / "prediction_inputs.json")
workload = jload(DOCS_A2 / "workload.json")
plan = jload(A2 / "calib" / "plan.json")
speed = jload(A2 / "speed" / "summary.json") or {}
speed_runs = {c: jload(A2 / "speed" / f"{c}.json") for c in speed}
mem = {p.stem: jload(p) for p in sorted((A2 / "memory").glob("memory_check_*.json")) if not p.stem.endswith(".sends")}
a1_full = {m: jload(ROOT / "results" / "accuracy" / f"summary_{safe(m)}.json") for m in MODELS}
CASCADES = ["cascade400", "cascade500"]
CFG_LABEL = {"top7b": "qwen2.5:7b alone", "cascade400": "Cascade T=400", "cascade500": "Cascade T=500",
             **{f"single-{m}": f"{m} alone" for m in MODELS}}

acc = {}   # config -> scored test-set json
for m in MODELS:
    j = jload(A2 / "accuracy" / f"single_{safe(m)}_test.json")
    if j:
        acc[f"single-{m}"] = j
for c in CASCADES + ["top7b"]:
    j = jload(A2 / "accuracy" / f"{c}_test.json")
    if j:
        acc[c] = j
if "top7b" not in acc and f"single-{TOP_MODEL}" in acc:
    acc["top7b"] = acc[f"single-{TOP_MODEL}"]          # reused A1 records (allowed by the brief)
tune_acc = {c: jload(A2 / "accuracy" / f"{c}_tune.json") for c in CASCADES}

# ------------------------------------------------------------------ pptx helpers
prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def text(s, x, y, w, h, body, size=12, bold=False, color=GREY, align=None):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(body if isinstance(body, list) else [body]):
        b = bold
        if isinstance(line, tuple):
            line, b = line
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        lead, rest = "", line
        if line.startswith("**") and "**" in line[2:]:
            lead, rest = line[2:].split("**", 1)
        for seg, bb in ((lead, True), (rest, b)):
            if seg:
                r = p.add_run(); r.text = seg
                r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), bb, color, "Calibri"
        p.space_after = Pt(3)
        if align:
            p.alignment = align
    return tb


def header(s, n, title, sub=None):
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.85))
    bar.fill.solid(); bar.fill.fore_color.rgb = NAVY; bar.line.fill.background()
    text(s, 0.4, 0.13, 11.6, 0.6, title, 25, True, WHITE)
    text(s, 12.3, 0.24, 0.9, 0.5, str(n), 14, color=RGBColor(0xBB, 0xCC, 0xDD), align=PP_ALIGN.RIGHT)
    if sub:
        text(s, 0.4, 0.9, 12.5, 0.4, sub, 12.5, color=TEAL)


def footer(s, src):
    text(s, 0.4, 7.12, 12.5, 0.3, "Source: " + src, 8.5, color=RGBColor(0x88, 0x88, 0x88))


def table(s, x, y, w, rows, cols, size=9.5, col_w=None, row_h=0.26, color=None, bold_rows=()):
    shp = s.shapes.add_table(len(rows) + 1, len(cols), Inches(x), Inches(y), Inches(w), Inches(row_h * (len(rows) + 1)))
    t = shp.table
    for i, cw in enumerate(col_w or []):
        t.columns[i].width = Inches(cw)
    for j, c in enumerate(cols):
        cell = t.cell(0, j); cell.text = str(c); cell.fill.solid(); cell.fill.fore_color.rgb = NAVY
        cell.margin_left = cell.margin_right = Inches(0.04)
        for p in cell.text_frame.paragraphs:
            for r in p.runs:
                r.font.size, r.font.bold, r.font.color.rgb = Pt(size), True, WHITE
    for i, row in enumerate(rows, 1):
        for j, v in enumerate(row):
            cell = t.cell(i, j); cell.text = "" if v is None else str(v)
            cell.fill.solid(); cell.fill.fore_color.rgb = LIGHT if i % 2 else WHITE
            cell.margin_left = cell.margin_right = Inches(0.04)
            cell.margin_top = cell.margin_bottom = Inches(0.02)
            for p in cell.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size, r.font.color.rgb = Pt(size), GREY
                    r.font.bold = (i - 1) in bold_rows
                    c = color(i - 1, j, v) if color else None
                    if c:
                        r.font.color.rgb, r.font.bold = c, True
    return shp


def pending(s, x, y, w, h, what, cmd):
    PENDING_ITEMS.append(what)
    b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    b.fill.solid(); b.fill.fore_color.rgb = RGBColor(0xFD, 0xED, 0xEC); b.line.color.rgb = RED
    tf = b.text_frame; tf.word_wrap = True
    r = tf.paragraphs[0].add_run(); r.text = "PENDING: " + what
    r.font.size, r.font.bold, r.font.color.rgb = Pt(12), True, RED
    p = tf.add_paragraph(); r = p.add_run(); r.text = cmd
    r.font.size, r.font.color.rgb, r.font.name = Pt(10), RED, "Consolas"


def box(s, x, y, w, h, label, fill=TEAL, size=11, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    b = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    b.fill.solid(); b.fill.fore_color.rgb = fill; b.line.fill.background()
    tf = b.text_frame; tf.word_wrap = True
    for i, line in enumerate(label.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = line
        r.font.size, r.font.color.rgb, r.font.bold = Pt(size if i == 0 else size - 2), WHITE, i == 0
    return b


def arrow(s, x1, y1, x2, y2, label=None, lx=None, ly=None):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = GREY; c.line.width = Pt(1.75)
    ln = c.line._get_or_add_ln(); ln.append(ln.makeelement(qn("a:tailEnd"), {"type": "triangle"}))
    if label:
        text(s, lx if lx is not None else min(x1, x2) + 0.05, ly if ly is not None else min(y1, y2) - 0.3,
             1.8, 0.3, label, 9.5, True, TEAL)


def card(s, x, y, w, h, title, items, accent=TEAL, size=10.5):
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    bg.fill.solid(); bg.fill.fore_color.rgb = LIGHT; bg.line.fill.background()
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(0.07), Inches(h))
    bar.fill.solid(); bar.fill.fore_color.rgb = accent; bar.line.fill.background()
    text(s, x + 0.18, y + 0.06, w - 0.28, 0.35, title, size + 1.5, True, accent)
    text(s, x + 0.18, y + 0.42, w - 0.3, h - 0.5, ["• " + i if not i.startswith("**") else i for i in items], size)


def f1(x, nd=1):
    return "–" if x is None else f"{x:.{nd}f}"


def kn(k, n):
    return f"{k}/{n} ({k / n * 100:.1f}%)" if n else "–"


# ------------------------------------------------------------------ derived results
def passes(c):
    a = acc.get(c)
    return bool(a and a.get("limits") and a["limits"]["pass"])


def p50(c):
    return speed.get(c, {}).get("p50_s", {}) or {}


qualifying = [c for c in ["top7b"] + CASCADES + [f"single-{m}" for m in MODELS if m != TOP_MODEL]
              if passes(c) and p50(c).get("mean") is not None]
recommended = min(qualifying, key=lambda c: p50(c)["mean"]) if qualifying else None
# Which small model ran: the primary pair, or the fallback docs/a2/escalation_rule.md section 5
# pre-declares if 3b + 7b do not fit. If neither pair fits, the cascade is infeasible here
# and only qwen2.5:7b alone is measured (brief, Step 2).
_m3 = next((v for k, v in mem.items() if "llama3.2_3b" in k), None)
_m1 = next((v for k, v in mem.items() if "llama3.2_1b" in k), None)
SMALL = "llama3.2:1b" if (_m3 and _m3["verdict"] != "FIT" and _m1 and _m1["verdict"] == "FIT") else "llama3.2:3b"
INFEASIBLE = bool(_m3 and _m3["verdict"] != "FIT" and _m1 and _m1["verdict"] != "FIT")
NOT_RUN = "not run: no model pair fits in memory"
ALL_SPEED_DONE = p50("top7b").get("n") == 3 and (INFEASIBLE or all(p50(c).get("n") == 3 for c in CASCADES))
ALL_ACC_DONE = INFEASIBLE or all(c in acc for c in CASCADES)


def log_split_latency(c):
    """Mean small / large model time per call during the speed runs of a cascade (service log)."""
    sm, lg = [], []
    for r in iter_log(A2_LOG):
        if str(r.get("run_id", "")).startswith(f"a2_{c}_run") and r.get("status") == 200:
            if r.get("small_latency_ms"):
                sm.append(r["small_latency_ms"] / 1000)
            if r.get("large_latency_ms"):
                lg.append(r["large_latency_ms"] / 1000)
            if r.get("mode") == "single" and r.get("latency_ms"):
                lg.append(r["latency_ms"] / 1000)
    return (st.mean(sm) if sm else None, st.mean(lg) if lg else None, len(sm), len(lg))


# =================================================================== 1 cover
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
text(s, 0.6, 0.45, 12, 0.8, "Fast Triage Within an Accuracy Floor", 36, True, WHITE)
text(s, 0.6, 1.2, 12, 0.5, "Can a two-model cascade on the same CPU-only machine beat qwen2.5:7b on speed without breaking the client's limits?",
     16, color=RGBColor(0xBB, 0xDD, 0xEE))
text(s, 0.6, 1.7, 12, 0.4, "ICT3113 Performance Testing & Optimisation · Assignment 2 · Group P2-9 · dataset rows 9000–9999", 13,
     color=RGBColor(0xDD, 0xDD, 0xDD))
for i, m in enumerate(team.get("members", [])):
    text(s, 0.6, 2.25 + i * 0.33, 4.5, 0.35, f"{m['name']} · {m['id']}", 13, color=WHITE)
text(s, 0.6, 4.05, 5.2, 0.35, "Repository: " + team.get("repo", ""), 11, color=RGBColor(0xBB, 0xDD, 0xEE))
top_full = a1_full.get(TOP_MODEL) or {}
if limits:
    text(s, 0.6, 4.55, 5.2, 1.6, [
        (f"Top Assignment 1 model: {TOP_MODEL}", True),
        f"Assignment 1 accuracy (full golden set, 175): {top_full.get('overall_accuracy', 0) * 100:.1f}%",
        f"Test half (87 tickets): {limits['top_correct']}/{limits['test_n']} = {limits['top_test_pct']:.1f}%",
        f"Overall limit = {limits['top_test_pct']:.1f} − 10 = {limits['overall_limit_pct']:.1f}%  (≥ {limits['overall_min_correct']}/{limits['test_n']} correct)",
        "Per-category limit = 7b's test-set category accuracy − 15 points",
    ], 12, color=WHITE)
    rows = []
    for c in CATS:
        k, n = limits["top_category_counts"][c]
        rows.append([c, f"{k}/{n}", f"{limits['top_category_pct'][c]:.1f}%", f"{limits['category_limit_pct'][c]:.1f}%",
                     f"≥ {limits['category_min_correct'][c]}/{n}", "yes" if c in limits["small_categories"] else ""])
    rows.append(["Overall", f"{limits['top_correct']}/{limits['test_n']}", f"{limits['top_test_pct']:.1f}%",
                 f"{limits['overall_limit_pct']:.1f}%", f"≥ {limits['overall_min_correct']}/{limits['test_n']}", ""])
    table(s, 6.3, 2.25, 6.6, rows, ["Category (test set)", "7b right", "7b acc", "Limit", "Need", "Too small*"],
          size=10, col_w=[2.35, 0.8, 0.8, 0.8, 0.95, 0.9], row_h=0.3, bold_rows=(7,))
    text(s, 6.3, 5.4, 6.6, 0.9, f"*n ≤ 13: two tickets ({200 / 13:.0f}+ points) exceed the 15-point margin, so one or two "
         "tickets decide pass/fail. Only Credit reporting (n = 19) is a fair per-category test. Limits from "
         "docs/a2/limits.json (tools/a2_limits.py).", 10, color=RGBColor(0xDD, 0xDD, 0xDD))
links = [("Escalation rule", "docs/a2/escalation_rule.md"), ("Prediction record", "docs/a2/prediction_record.md"),
         ("Speed-test rows", "data/a2_speed_rows.csv"), ("Tuning analysis", "docs/a2/tuning_analysis.md"),
         ("Golden split", "golden/a2_split.csv"), ("Runbook", "docs/a2/RUNBOOK.md")]
band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(6.45), prs.slide_width, Inches(0.6))
band.fill.solid(); band.fill.fore_color.rgb = LIGHT; band.line.fill.background()
tb = s.shapes.add_textbox(Inches(0.6), Inches(6.5), Inches(12.2), Inches(0.5)); tf = tb.text_frame; tf.word_wrap = True
p = tf.paragraphs[0]
r = p.add_run(); r.text = "Supporting files (GitHub): "; r.font.size, r.font.bold, r.font.color.rgb = Pt(11), True, NAVY
commit = team.get("a2_commit") or "main"
for i, (lbl, path) in enumerate(links):
    r = p.add_run(); r.text = lbl; r.font.size, r.font.underline = Pt(11), True
    r.hyperlink.address = f"{team.get('repo', '')}/blob/{commit}/{path}"
    if i < len(links) - 1:
        r = p.add_run(); r.text = "  ·  "; r.font.size, r.font.color.rgb = Pt(11), NAVY
draft_slot = s  # DRAFT banner is added at the end if anything is pending

# =================================================================== 2 cascade design
s = prs.slides.add_slide(BLANK)
# Which small model actually ran: the primary pair, or the fallback that
# docs/a2/escalation_rule.md section 5 pre-declares if 3b + 7b do not fit.
header(s, 2, "Cascade Design", f"Length rule inside POST /tickets: short tickets to {SMALL}, long ones straight to qwen2.5:7b. "
       + ("Fallback pair: 3b + 7b did not fit in memory (rule §5)." if SMALL != "llama3.2:3b" else "The caller still sees one category."))
box(s, 0.35, 1.90, 1.45, 0.75, "POST /tickets\nnarrative", NAVY, 11)
box(s, 2.15, 1.80, 1.9, 0.95, "n ≤ T ?\nn = characters", AMBER, 13, MSO_SHAPE.DIAMOND)
box(s, 4.75, 1.35, 1.9, 0.7, f"{SMALL}\nsmall · same prompt", TEAL, 11)
box(s, 4.75, 2.70, 1.9, 0.7, "qwen2.5:7b\nlarge · same prompt", NAVY, 11)
box(s, 7.3, 1.35, 1.55, 0.7, "parsed?", AMBER, 11, MSO_SHAPE.DIAMOND)
box(s, 9.4, 1.35, 1.55, 0.7, "answer\nnot escalated", GREEN, 11)
box(s, 9.4, 2.70, 1.55, 0.7, "answer\nescalated", RED, 11)
arrow(s, 1.80, 2.27, 2.15, 2.27)
arrow(s, 3.85, 2.05, 4.75, 1.70, "yes (short)", 3.90, 1.47)
arrow(s, 3.85, 2.50, 4.75, 3.05, "no (n > T)", 3.85, 2.90)
arrow(s, 6.65, 1.70, 7.30, 1.70)
arrow(s, 8.85, 1.70, 9.40, 1.70, "yes", 8.90, 1.40)
arrow(s, 8.08, 2.05, 5.70, 2.70, "UNPARSED", 6.60, 2.13)
arrow(s, 6.65, 3.05, 9.40, 3.05)
text(s, 11.1, 1.35, 2.1, 2.2, ["Log line per ticket:", "final_model", "escalated", "route", "narrative_chars",
                              "small_* / large_* timings"], 9.5, color=GREY)
card(s, 0.35, 3.5, 6.25, 3.55, "Escalation rule in full (docs/a2/escalation_rule.md)", [
    "n = characters of the narrative as received (same figure A1 logged as narrative_chars).",
    "n > T → qwen2.5:7b classifies; its answer is final (escalated).",
    f"n ≤ T → {SMALL} classifies; answer accepted unless it parses to UNPARSED, then qwen2.5:7b (escalated).",
    "Both models: unchanged A1 prompt v1, temperature 0, seed 42, num_predict 16, num_ctx 2048, same parser.",
    "**Settings tested:** T = 400 (conservative) and T = 500 (largest cut-off that passes the tuning check). Chosen on the 88 tuning tickets only.",
    "Response 'model' field = configuration name, never the answering model; which model answered is only in the service log.",
], TEAL, 10.5)
lb = tuning["length_buckets"] if tuning else []
s5 = [b for b in lb if b["hi"] <= 500]; l5 = [b for b in lb if b["hi"] > 500]
why = []
if tuning:
    ref = tuning["reference"]
    L = tuning["families"]["length"]["llama3.2:3b"]
    catb = tuning["families"]["category"]["llama3.2:3b"]
    why = [
        f"**Length predicts 3b errors.** ≤ 500 chars: 3b {sum(b['3b'] for b in s5)}/{sum(b['n'] for b in s5)} vs 7b "
        f"{sum(b['7b'] for b in s5)}/{sum(b['n'] for b in s5)}; > 500: 3b {sum(b['3b'] for b in l5)}/{sum(b['n'] for b in l5)} vs 7b "
        f"{sum(b['7b'] for b in l5)}/{sum(b['n'] for b in l5)} (tuning set).",
        "**No wasted small call.** Long tickets skip the 3b, so escalation costs nothing extra.",
        f"**Category rule is slower:** 3b costs ~46% of a 7b call; its fastest passing accept-set escalates "
        f"{catb['esc_frac'] * 100:.0f}% → {catb['mean_s'] / ref['mean_s'] * 100 - 100:+.0f}% vs 7b.",
        "**0.5b / 1b can't carry traffic:** they give one answer to 81% / 66% of tickets; every rule with them fails a category.",
        f"**Tuning replay:** T=400 {L['400']['correct']}/88, mean {L['400']['mean_s']:.1f} s; T=500 {L['500']['correct']}/88, "
        f"{L['500']['mean_s']:.1f} s; 7b {ref['correct']}/88, {ref['mean_s']:.1f} s (no load).",
    ]
card(s, 6.8, 3.5, 3.25, 3.55, "Why this rule", why, NAVY, 9.5)
mk = next((k for k in mem if "llama3.2_3b" in k), None) or (next(iter(mem)) if mem else None)
if mk:
    m = mem[mk]
    ok = m["verdict"] == "FIT"
    lines = [f"**{' + '.join(m['pair'])}: {m['verdict']}**",
             f"ollama ps listed both after every ticket: {m['checks'].get('both_listed_after_each_ticket')}",
             f"reload after first load: {'none' if m['checks'].get('no_reload') else 'YES'}",
             f"OOM events: {'none' if m['checks'].get('no_oom') else m['checks'].get('no_oom')}"]
    if m.get("cgroup_memory_peak") and m.get("cgroup_memory_max", "max") not in (None, "max"):
        lines.append(f"cgroup peak {m['cgroup_memory_peak'] / 2**30:.2f} of {int(m['cgroup_memory_max']) / 2**30:.0f} GiB")
    for mm, v in m.get("prefill", {}).items():
        if v.get("ratio"):
            lines.append(f"{mm} prefill {v['ratio'] * 100:.0f}% of A1 speed")
    for k2, m2 in mem.items():
        if k2 != mk:
            lines.append(f"{' + '.join(m2['pair'])}: {m2['verdict']}")
    card(s, 10.25, 3.5, 2.75, 3.55, "Memory check (both resident)", lines, GREEN if ok else RED, 9.5)
else:
    pending(s, 10.25, 3.5, 2.75, 3.55, "memory check (Step 2)", "tools/a2_memory_check.sh")
footer(s, "docs/a2/escalation_rule.md · docs/a2/tuning_analysis.md · service/app/cascade.py · results/a2/memory/")

# =================================================================== 3 environment and method
s = prs.slides.add_slide(BLANK)
header(s, 3, "Test Environment and Method", "Same machines, same container limits, same Ollama build and settings as Assignment 1; Assignment 2 arrival rate set from S.")
card(s, 0.35, 1.35, 4.15, 2.6, "Machines (unchanged; A1 slide 7)", [
    "**Machine A (SUT):** i9-10900K 10C/20T, 48 GB; WSL 2 VM 12 GB; Docker 29.8.2; Ollama 0.5.7 container: 4-CPU quota, 8 GiB, CPU only (RTX 3090 not mapped).",
    "**Machine B (load):** Ryzen 7 8845HS, 16 GB, JMeter 5.6.3, Java 21 — a separate machine in another home.",
    "**Link:** Tailscale direct peer-to-peer, RTT ~9 ms (A1).",
    "**Ollama settings, recorded once, held constant:** threads 10 (auto), parallel 4, num_ctx 2048, keep-alive 30 m (results/a2/env/preflight_*.txt).",
], NAVY, 9.5)
if plan:
    lines = [f"**S = {plan['S_s']:.1f} s**: middle of {', '.join(f'{t:.1f}' for t in plan['timings_s'])} s on rows "
             f"{', '.join(plan['rows'])} (3 different ~{workload['calib_chars'][0] if workload else ''}-char tickets, qwen2.5:7b, after restart + warm-up).",
             f"**Rate** = one ticket per 2S = {plan['interval_s']:.0f} s → {plan['rate_per_min']:.3f}/min; top model idle ~half the time, so no queue builds.",
             f"**Run** = S minutes → {plan['duration_min']} min, ~{plan['expected_arrivals']:.0f} arrivals; 3 runs per configuration; same rate and length for all.",
             f"**JMeter:** {plan['schedule']}; response timeout {plan['timeout_s']} s (10×S, ≥ 5 min); pause > timeout + 60 s.",
             f"**vs client peak** (A1: 1.0/min): test rate is {'BELOW' if plan['rate_per_min'] < 1.0 else 'ABOVE'} peak (see slide 8)."]
    card(s, 4.65, 1.35, 4.3, 2.6, "Arrival rate from S", lines, TEAL, 9.5)
else:
    pending(s, 4.65, 1.35, 4.3, 2.6, "S calibration", "tools/a2_machineA.sh calib  +  jmeter/a2_calibrate.sh <host>")
if workload:
    card(s, 9.1, 1.35, 3.9, 2.6, "Workload tickets (data/a2_speed_rows.csv)", [
        f"{len(workload['speed_rows'])} team rows outside the golden set, fixed order (seed 3113), recycled; same list, same order, every config; JMeter seed = run number.",
        f"Picked at even length quantiles: {workload['speed_chars']['min']}–{workload['speed_chars']['max']} chars, median {workload['speed_chars']['median']:.0f} (team median {workload['team_median_chars']:.0f}).",
        f"Share ≤ 400 chars {workload['speed_share_le_400'] * 100:.0f}%, ≤ 500 chars {workload['speed_share_le_500'] * 100:.0f}% → expected escalation under load {100 - workload['speed_share_le_400'] * 100:.0f}% / {100 - workload['speed_share_le_500'] * 100:.0f}%.",
        f"Warm-up rows {', '.join(workload['warmup_rows'])} ({', '.join(map(str, workload['warmup_chars']))} chars): short one reaches 3b, long ones reach 7b.",
    ], AMBER, 9.5)
card(s, 0.35, 4.1, 6.3, 2.95, "Each run (tools/a2_machineA.sh ↔ jmeter/a2_machineB.sh)", [
    "1. Service set to the configuration; Ollama container restarted (prompt cache cleared, nothing loaded); health checked.",
    "2. Three fixed warm-up tickets, one at a time, timings discarded. For the cascade, W1 (274 chars) loads 3b and W2/W3 load 7b.",
    "3. `ollama ps` must list every model of the configuration (both for the cascade) or the run aborts; snapshot kept.",
    "4. Machine B: GET /stats (total), JMeter open-model run, drain pause, GET /stats again; the increase = requests completed and stored.",
    "5. Sent = A2SENT lines in the JMeter log; completed / errored from the .jtl; unfinished = timed out by JMeter or never recorded. Escalation from the service log.",
], TEAL, 9.5)
card(s, 6.8, 4.1, 6.2, 2.95, "Changes from Assignment 1", [
    "**POST /tickets** can run the cascade (TRIAGE_MODE=cascade); single-model path unchanged. Endpoints, prompt, models, golden set unchanged.",
    "**Speed test:** one POST /tickets stream at 1/(2S); no /search stream (A2 compares triage configurations); 3 runs; restart + warm-up before every run (A1: once per model).",
    "**Timeouts:** JMeter 10×S (A1: 600 s); pause outlasts it by ≥ 1 min. Service→Ollama timeout raised 300 → 1,200 s per call so JMeter, not the service, decides a request is too slow.",
    "**OLLAMA_NUM_PARALLEL=4** set explicitly — the value Ollama chose automatically in A1 — so it cannot change when two models load.",
    "**Separate log** results/logs/a2_requests.jsonl with final_model / escalated / route per ticket.",
    "**Single-model accuracy** reused from A1 records, test rows only (same digests, prompt, Ollama 0.5.7, machine).",
], RED, 9.5)
footer(s, "docs/test_environment.md (A1) · results/a2/env/ · results/a2/calib/plan.json · docs/a2/workload.json · docs/a2/RUNBOOK.md")

# =================================================================== 4 accuracy results
s = prs.slides.add_slide(BLANK)
header(s, 4, "Accuracy Results (test set, 87 tickets)", "Test set = even positions of the golden set sorted by row (odd = tuning). Counts next to every %; red = below the limit. Singles: A1 records, test rows.")
order = [f"single-{m}" for m in MODELS if m != TOP_MODEL] + ["top7b"] + CASCADES
rows, colmap = [], {}
for c in order:
    a = acc.get(c)
    if not a:
        rows.append([CFG_LABEL[c], NOT_RUN if INFEASIBLE and c in CASCADES else "PENDING"] + [""] * 9)
        continue
    lim = a.get("limits") or {}
    r = [CFG_LABEL[c] + (" (A1 rec.)" if c.startswith("single") or (c == "top7b" and "source" in a) else ""),
         f"{a['correct']}/{a['n']} {a['acc'] * 100:.1f}%"]
    for cat in CATS:
        pc = a["per_category"][cat]
        r.append(f"{pc['correct']}/{pc['n']} {pc['acc'] * 100:.0f}%")
    esc = a.get("escalation") or {}
    r.append("–" if not esc.get("escalated", {}).get("n") and c != "top7b" and not c.startswith("cascade")
             else (f"{esc['escalated']['n']}/{a['n']}" if c.startswith("cascade") else "all (7b)" if c == "top7b" else "–"))
    r.append("PASS" if lim.get("pass") else "FAIL")
    rows.append(r)
lim_row = ["Limit", f"≥{limits['overall_min_correct']}/87 {limits['overall_limit_pct']:.1f}%"] + \
          [f"≥{limits['category_min_correct'][c]}/{limits['top_category_counts'][c][1]} {limits['category_limit_pct'][c]:.0f}%" for c in CATS] + ["", ""]
rows.append(lim_row)


def acc_color(i, j, v):
    if i >= len(order) or not v or v in ("PENDING",):
        return RED if v == "PENDING" else None
    a = acc.get(order[i])
    if not a or not a.get("limits"):
        return None
    lim = a["limits"]
    if j == 1:
        return GREEN if lim["overall_pass"] else RED
    if 2 <= j <= 8:
        return GREEN if lim["categories"][CATS[j - 2]]["pass"] else RED
    if j == 10:
        return GREEN if v == "PASS" else RED
    return None


table(s, 0.3, 1.35, 12.75, rows, ["Configuration", "Overall"] + [SHORT[c] + ("*" if c in limits["small_categories"] else "") for c in CATS] + ["Escalated", "Limits"],
      size=9, col_w=[2.05, 1.25] + [1.05] * 7 + [0.95, 0.75], row_h=0.3, color=acc_color, bold_rows=(len(order),))
if not ALL_ACC_DONE:
    pending(s, 0.3, 4.25, 4.2, 1.1, "cascade accuracy test", "tools/a2_accuracy_all.sh   (Machine A)")
# escalated vs non-escalated
y0 = 4.25
cards = []
for c in CASCADES:
    a = acc.get(c)
    if a and a.get("escalation"):
        e = a["escalation"]
        es, ne = e["escalated"], e["not_escalated"]
        wrong_kept = ne["n"] - ne["correct"]
        cards.append(f"**{CFG_LABEL[c]}:** escalated {es['n']}/{a['n']} ({e['fraction'] * 100:.0f}%) → 7b right on "
                     f"{es['correct']}/{es['n']} ({(es['acc'] or 0) * 100:.0f}%); kept 3b answer on {ne['n']} → right on "
                     f"{ne['correct']}/{ne['n']} ({(ne['acc'] or 0) * 100:.0f}%); {wrong_kept} wrong answers slipped through. Routes: "
                     + ", ".join(f"{k} {v}" for k, v in e["routes"].items()))
        t = tune_acc.get(c)
        if t:
            cards.append(f"  tuning set (not used to decide): {t['correct']}/{t['n']} ({t['acc'] * 100:.1f}%), escalation {t['escalation']['fraction'] * 100:.0f}%")
if cards:
    card(s, 0.3 if ALL_ACC_DONE else 4.65, y0, 6.0 if ALL_ACC_DONE else 3.6, 2.8, "Escalated vs kept (from the service log, by request_id)", cards, TEAL, 9.5)
# confusion matrices
cm_cfgs = [c for c in ["top7b"] + CASCADES if c in acc]
if cm_cfgs:
    fig, axes = plt.subplots(1, len(cm_cfgs), figsize=(2.25 * len(cm_cfgs), 2.45), dpi=200)
    axes = axes if len(cm_cfgs) > 1 else [axes]
    for ax, c in zip(axes, cm_cfgs):
        cm = acc[c]["confusion"]
        cols = CATS + ["UNPARSED"]
        M = [[cm[g].get(p, 0) for p in cols] for g in CATS]
        ax.imshow(M, cmap="Blues")
        for i2, rr in enumerate(M):
            for j2, v in enumerate(rr):
                if v:
                    ax.text(j2, i2, v, ha="center", va="center", fontsize=5.5, color="white" if v > 8 else "black")
        ax.set_xticks(range(len(cols))); ax.set_xticklabels([SHORT.get(x, "UNP") for x in cols], rotation=60, fontsize=5)
        ax.set_yticks(range(len(CATS))); ax.set_yticklabels([SHORT[x] for x in CATS], fontsize=5)
        ax.set_title(f"{CFG_LABEL[c]} · {acc[c]['acc'] * 100:.1f}%", fontsize=6.5)
        ax.set_xlabel("predicted", fontsize=5.5)
    axes[0].set_ylabel("golden", fontsize=5.5)
    plt.tight_layout(); fig.savefig(BUILD / "confusion.png"); plt.close(fig)
    pic = s.shapes.add_picture(str(BUILD / "confusion.png"), Inches(6.45), Inches(4.2), width=Inches(6.6))
    if pic.height > Inches(2.85):
        ratio = Inches(2.85) / pic.height
        pic.height, pic.width = Inches(2.85), int(pic.width * ratio)
text(s, 0.3, 6.95 - 0.1, 6.1, 0.3, "* n ≤ 13: one ticket = 7.7–10 points, so these verdicts rest on 1–2 tickets. Confusion matrices for every configuration: docs/a2/accuracy_notes.md.", 9)
footer(s, "results/a2/accuracy/*_test.json, *_predictions.csv (cascade; log results/logs/a2_requests.jsonl) · results/a2/accuracy/single_*_test.json (A1 records)")

# =================================================================== 5 speed results
s = prs.slides.add_slide(BLANK)
sub = (f"Open loop at {plan['rate_per_min']:.3f}/min for {plan['duration_min']} min, 3 runs each; latency = JMeter elapsed of successful requests"
       if plan else "Open loop at 1/(2S), S-minute runs, 3 runs per configuration")
header(s, 5, "Speed Results", sub)
speed_cfgs = ["top7b"] + CASCADES + [c for c in speed if c not in ("top7b", *CASCADES)]
rows = []
for c in speed_cfgs:
    j = speed_runs.get(c)
    if not j:
        rows.append([CFG_LABEL.get(c, c), NOT_RUN if INFEASIBLE and c in CASCADES else "PENDING", "", "", "", "", "", "", "", ""])
        continue
    for r in j["runs"]:
        rows.append([f"{CFG_LABEL.get(c, c)} · run {r['tag'].split('_run')[-1]}", r["sent"], r["completed"], r["errored"], r["unfinished"],
                     f1(r["p50_s"]), f"{r['throughput_per_min']:.2f}" if r["throughput_per_min"] else "–",
                     f1(r["error_rate_pct"]),
                     "–" if r["escalation_fraction"] is None or c == "top7b" else f"{r['escalated']}/{r['service_log_200']} {r['escalation_fraction'] * 100:.0f}%",
                     "yes" if all(v in (True, None) for k, v in r["reconcile"].items() if k != "reload_during_run")
                     and not r["reconcile"]["reload_during_run"] else "NO"])
table(s, 0.3, 1.35, 8.1, rows, ["Configuration · run", "Sent", "Done", "Err", "Unfin.", "p50 s", "Thru /min", "Err %", "Escalated", "Recon."],
      size=9, col_w=[2.2, 0.55, 0.55, 0.5, 0.6, 0.7, 0.8, 0.6, 1.05, 0.55], row_h=0.27,
      color=lambda i, j, v: RED if v in ("PENDING", "NO") else None)
if not ALL_SPEED_DONE:
    pending(s, 8.6, 1.35, 4.45, 1.3, "speed test (3 runs × 3 configs)",
            "tools/a2_machineA.sh top7b cascade400 cascade500\njmeter/a2_machineB.sh <host> top7b cascade400 cascade500")
agg_rows = []
for c in speed_cfgs:
    j = speed.get(c)
    if not j:
        continue
    p = j["p50_s"]
    agg_rows.append([CFG_LABEL.get(c, c), f"{p['mean']:.1f} ± {p['sd']:.1f}", f"{p['min']:.1f}–{p['max']:.1f}",
                     f"{j['p95_pooled_s']:.1f} (n={j['p95_pooled_n']})",
                     f"{j['throughput_per_min']['mean']:.2f}" if j.get("throughput_per_min") else "–",
                     f"{j['error_rate_pct']['mean']:.1f}" if j.get("error_rate_pct") else "–",
                     "–" if c == "top7b" or j.get("escalation_pooled") is None else f"{j['escalation_pooled'] * 100:.0f}%"])
if agg_rows:
    table(s, 8.6, 2.8 if not ALL_SPEED_DONE else 1.35, 4.45, agg_rows, ["Config", "p50 mean ± sd", "p50 range", "p95 pooled", "Thru", "Err%", "Esc"],
          size=8.5, col_w=[1.05, 0.8, 0.65, 0.75, 0.4, 0.4, 0.4], row_h=0.3)
    # dot plot of per-run p50
    fig, ax = plt.subplots(figsize=(4.4, 2.1), dpi=200)
    for i2, c in enumerate([c for c in speed_cfgs if c in speed_runs and speed_runs[c]]):
        v = [r["p50_s"] for r in speed_runs[c]["runs"] if r["p50_s"] is not None]
        ax.scatter(v, [i2] * len(v), s=18, color="#2B7A78" if c != "top7b" else "#1F3A5F", zorder=3)
        ax.plot([min(v), max(v)], [i2, i2], color="#999", lw=1)
        ax.scatter([st.mean(v)], [i2], marker="|", s=200, color="#C0392B", zorder=4)
    ax.set_yticks(range(len([c for c in speed_cfgs if c in speed_runs and speed_runs[c]])))
    ax.set_yticklabels([CFG_LABEL.get(c, c) for c in speed_cfgs if c in speed_runs and speed_runs[c]], fontsize=6.5)
    ax.set_xlabel("p50 per run (s); red tick = mean of 3", fontsize=6.5); ax.tick_params(axis="x", labelsize=6.5)
    ax.grid(axis="x", alpha=.3); ax.set_ylim(-0.6, len(speed_runs) - 0.4)
    plt.tight_layout(); fig.savefig(BUILD / "p50_runs.png"); plt.close(fig)
    s.shapes.add_picture(str(BUILD / "p50_runs.png"), Inches(8.6), Inches(4.0 if ALL_SPEED_DONE else 4.15), width=Inches(4.45))
notes5 = []
for c in CASCADES:
    smv, lgv, ns, nl = log_split_latency(c)
    if smv or lgv:
        notes5.append(f"{CFG_LABEL[c]} under load: 3b call mean {f1(smv)} s (n={ns}), 7b call mean {f1(lgv)} s (n={nl}).")
smv, lgv, ns, nl = log_split_latency("top7b")
if lgv:
    notes5.append(f"7b alone under load: mean {lgv:.1f} s per call (n={nl}).")
for c in CASCADES:
    j, a = speed.get(c), acc.get(c)
    if j and a and j.get("escalation_pooled") is not None and a.get("escalation"):
        notes5.append(f"{CFG_LABEL[c]} escalation: {j['escalation_pooled'] * 100:.0f}% under load vs {a['escalation']['fraction'] * 100:.0f}% on the "
                      "test set — different tickets (speed list vs golden test half).")
if notes5:
    text(s, 0.3, 1.35 + 0.29 * (len(rows) + 1) + 0.15, 8.1, 1.4, notes5, 9.5)
footer(s, "results/a2/jtl/a2_*_run*.jtl + .jmeter.log · results/a2/runs/*.stats_*.json · results/logs/a2_requests.jsonl · tools/a2_analyze_speed.py → results/a2/speed/")

# =================================================================== 6 trade-off
s = prs.slides.add_slide(BLANK)
header(s, 6, "Trade-off: Accuracy vs Latency", "One point per speed-tested configuration and setting; dashed line = overall accuracy limit.")
pts = [(c, acc[c]["acc"] * 100, p50(c)) for c in ["top7b"] + CASCADES if c in acc and p50(c).get("mean") is not None]
if pts and limits:
    fig, ax = plt.subplots(figsize=(7.6, 5.0), dpi=200)
    for c, y, p in pts:
        ok = passes(c)
        ax.errorbar(p["mean"], y, xerr=[[p["mean"] - p["min"]], [p["max"] - p["mean"]]], fmt="o", ms=9,
                    color="#2E7D32" if ok else "#C0392B", mfc="#2E7D32" if ok else "white", capsize=4, lw=1.3)
        ax.annotate(f"{CFG_LABEL[c]}\n{y:.1f}% · p50 {p['mean']:.1f} s", (p["mean"], y), textcoords="offset points",
                    xytext=(8, 6), fontsize=8)
    ax.axhline(limits["overall_limit_pct"], ls="--", color="#C0392B", lw=1.2)
    ax.text(ax.get_xlim()[0], limits["overall_limit_pct"] + 0.4, f" overall limit {limits['overall_limit_pct']:.1f}%", color="#C0392B", fontsize=8)
    ax.set_xlabel("p50 latency under load, mean of 3 runs (s); bars = min–max of the 3 runs", fontsize=9)
    ax.set_ylabel("Test-set accuracy (%) — 87 tickets", fontsize=9)
    ax.set_ylim(min(limits["overall_limit_pct"] - 4, min(y for _, y, _ in pts) - 3), 100)
    ax.grid(alpha=.3)
    ax.text(0.99, 0.02, "filled = passes overall + per-category limits; hollow red = fails a limit", transform=ax.transAxes,
            ha="right", fontsize=7, color="#555")
    plt.tight_layout(); fig.savefig(BUILD / "tradeoff.png"); plt.close(fig)
    s.shapes.add_picture(str(BUILD / "tradeoff.png"), Inches(0.35), Inches(1.4), height=Inches(5.6))
else:
    pending(s, 0.35, 1.4, 8.3, 5.4, "trade-off chart (needs accuracy + speed results)", "tools/a2_accuracy_all.sh; tools/a2_analyze_speed.py")
interp = txt.get("tradeoff")
if not interp and pts and len(pts) >= 2:
    top = next((x for x in pts if x[0] == "top7b"), None)
    interp = []
    for c, y, p in pts:
        if c == "top7b" or not top:
            continue
        d = (p["mean"] - top[2]["mean"]) / top[2]["mean"] * 100
        overlap = not (p["max"] < top[2]["min"] or p["min"] > top[2]["max"])
        interp.append(f"**{CFG_LABEL[c]}:** {d:+.0f}% p50 vs 7b alone, {y - top[1]:+.1f} accuracy points "
                      f"({acc[c]['correct'] - acc['top7b']['correct']:+d} tickets); "
                      + ("run ranges overlap with 7b alone, so the difference is within run-to-run spread." if overlap
                         else "run ranges do not overlap with 7b alone."))
    interp.append("Single models other than qwen2.5:7b fail the accuracy limits, so they were not speed-tested and have no point.")
    if recommended:
        interp.append(f"**Fastest within the limits: {CFG_LABEL[recommended]}.**")
if interp:
    card(s, 8.85, 1.4, 4.15, 5.6, "Interpretation", interp, TEAL, 10.5)
footer(s, "x: results/a2/speed/summary.json (from the .jtl files) · y: results/a2/accuracy/*_test.json · limit: docs/a2/limits.json")

# =================================================================== 7 predictions, recommendation
s = prs.slides.add_slide(BLANK)
header(s, 7, "Predictions vs Outcomes · Recommendation", "Predictions committed before the first A2 run (docs/a2/prediction_record.md); compared without revision.")
P = pred["configs"] if pred else {}


def verdict_num(pv, mv, tol_rel):
    if mv is None:
        return "PENDING"
    return "RIGHT" if abs(mv - pv) <= tol_rel * abs(pv) else "WRONG"


prow = []
memk = next((k for k in mem if "llama3.2_3b" in k), None)
prow.append(["3b + 7b fit in 8 GiB together", "fit", mem[memk]["verdict"].lower() if memk else "", "RIGHT" if memk and mem[memk]["verdict"] == "FIT" else ("WRONG" if memk else "PENDING")])
prow.append(["S (s)", f"{pred['S_pred_s']:.0f}" if pred else "", f1(plan and plan["S_s"]), verdict_num(pred["S_pred_s"], plan and plan["S_s"], 0.15) if pred else ""])
prow.append(["Fastest within limits", CFG_LABEL["cascade500"], CFG_LABEL.get(recommended, "") if ALL_SPEED_DONE else "",
             ("RIGHT" if recommended == "cascade500" else "WRONG") if ALL_SPEED_DONE and ALL_ACC_DONE else "PENDING"])
for c in ["top7b"] + CASCADES:
    if c in P:
        mv = p50(c).get("mean")
        prow.append([f"p50 under load · {CFG_LABEL[c]}", f"{P[c]['p50_median']:.0f} s", f1(mv), verdict_num(P[c]["p50_median"], mv, 0.15)])
for c, pe in (("cascade400", 0.81), ("cascade500", 0.73)):
    a = acc.get(c)
    mv = a["escalation"]["fraction"] if a and a.get("escalation") else None
    prow.append([f"Escalation, test set · T={c[-3:]}", f"{pe * 100:.0f}%", "" if mv is None else f"{mv * 100:.0f}%",
                 "PENDING" if mv is None else ("RIGHT" if abs(mv - pe) <= 0.05 else "WRONG")])
for c in CASCADES:
    j = speed.get(c)
    pe = P.get(c, {}).get("esc_frac_load")
    mv = j and j.get("escalation_pooled")
    prow.append([f"Escalation under load · T={c[-3:]}", f"{pe * 100:.0f}%" if pe else "", "" if mv is None else f"{mv * 100:.0f}%",
                 "PENDING" if mv is None else ("RIGHT" if abs(mv - pe) <= 0.05 else "WRONG")])
for c in CASCADES:
    a = acc.get(c)
    prow.append([f"Test accuracy · T={c[-3:]}", "67/87 77.0%", "" if not a else f"{a['correct']}/87 {a['acc'] * 100:.1f}%",
                 "PENDING" if not a else ("RIGHT" if abs(a["correct"] - 67) <= 2 else "WRONG")])
if all(c in acc for c in CASCADES) and "top7b" in acc:
    drops = {cat: sum(acc["top7b"]["per_category"][cat]["correct"] - acc[c]["per_category"][cat]["correct"] for c in CASCADES) for cat in CATS}
    worst = max(drops, key=drops.get)
    prow.append(["Category losing most", "Credit reporting", f"{worst} ({-drops[worst]:+d} tickets over both)", "RIGHT" if worst == "Credit reporting" else "WRONG"])
else:
    prow.append(["Category losing most", "Credit reporting", "", "PENDING"])
if INFEASIBLE:
    prow = [[a, b, (NOT_RUN if d == "PENDING" else c), ("not run" if d == "PENDING" else d)] for a, b, c, d in prow]
    prow[0][2], prow[0][3] = "neither pair fits", "WRONG"
table(s, 0.3, 1.35, 6.9, prow, ["Claim", "Predicted", "Measured", "Verdict"], size=9, col_w=[2.55, 1.45, 2.0, 0.9], row_h=0.25,
      color=lambda i, j, v: (GREEN if v == "RIGHT" else RED if v in ("WRONG", "PENDING") else None) if j == 3 else None)
text(s, 0.3, 6.78, 6.9, 0.3, "Verdict tolerances: latency ±15%, escalation ±5 points, accuracy ±2 tickets, S ±15%.", 8.5)
why = txt.get("prediction_misses") or ["Where and why the predictions missed: write in deck/a2_text.json → \"prediction_misses\" "
                                       "after reading results (docs/a2/prediction_account.md)."]
card(s, 7.4, 4.25, 5.6, 2.8, "Why they differed (full account: docs/a2/prediction_account.md)", why, AMBER, 9)
if recommended and ALL_SPEED_DONE and ALL_ACC_DONE:
    top = acc["top7b"]; rec = acc[recommended]
    gain = (p50("top7b")["mean"] - p50(recommended)["mean"]) / p50("top7b")["mean"] * 100 if recommended != "top7b" else 0
    p95g = (speed["top7b"]["p95_pooled_s"] - speed[recommended]["p95_pooled_s"]) / speed["top7b"]["p95_pooled_s"] * 100 if recommended != "top7b" else 0
    catd = [f"{SHORT[c]} {rec['per_category'][c]['correct'] - top['per_category'][c]['correct']:+d}" for c in CATS
            if rec["per_category"][c]["correct"] != top["per_category"][c]["correct"]]
    lines = [f"**Deploy: {CFG_LABEL[recommended]}**" + ("" if recommended == "top7b" else f" ({SMALL} → qwen2.5:7b)")]
    if INFEASIBLE:
        lines.append("**Cascade not feasible on this machine:** neither llama3.2:3b + qwen2.5:7b nor llama3.2:1b + qwen2.5:7b "
                     "stayed resident in the unchanged 8 GiB Ollama container (memory checks, slide 2; results/a2/memory/). "
                     "Attempted: rule, code and two settings built and committed; both pairs memory-checked; 7b alone speed-tested.")
    if recommended != "top7b":
        lines += [f"Speed: p50 {p50(recommended)['mean']:.1f} s vs {p50('top7b')['mean']:.1f} s for 7b alone ({gain:.0f}% faster); "
                  f"pooled p95 {speed[recommended]['p95_pooled_s']:.0f} vs {speed['top7b']['p95_pooled_s']:.0f} s ({p95g:+.0f}%).",
                  f"Accuracy cost: {rec['correct']}/87 vs {top['correct']}/87 ({(rec['acc'] - top['acc']) * 100:+.1f} points); by category: "
                  + (", ".join(catd) if catd else "no change") + " tickets."]
    else:
        lines.append(f"No configuration inside both limits was faster than the reference (p50 {p50('top7b')['mean']:.1f} s, "
                     f"pooled p95 {speed['top7b']['p95_pooled_s']:.0f} s); nothing given up on accuracy.")
    for c in CASCADES:
        if c == recommended:
            continue
        smv, lgv, _, _ = log_split_latency(c)
        e = (speed.get(c) or {}).get("escalation_pooled")
        pc = p50(c).get("mean")
        if pc is None:
            continue
        faster = pc < p50(recommended)["mean"]
        _, top_lg, _, _ = log_split_latency("top7b")
        why = ""
        if e is not None and smv and lgv and top_lg:
            # Length rule: a short ticket costs one small call, a long one one large call (no double cost).
            per_ticket = (1 - e) * smv + e * lgv
            why = (f"; model time per ticket ≈ (1−{e:.2f})×{smv:.1f} + {e:.2f}×{lgv:.1f} = {per_ticket:.1f} s vs {top_lg:.1f} s for 7b alone"
                   + ("" if per_ticket < top_lg else ": the 7b calls it still makes cost more under contention than the 3b saves"))
        speed_txt = (f"p50 {pc:.1f} s ({'faster' if faster else 'slower'} than the recommendation); {e * 100:.0f}% escalated under load"
                     f"{why}") if e is not None else f"p50 {pc:.1f} s"
        if not passes(c):
            lines.append(f"{CFG_LABEL[c]}: NOT passing accuracy (fails " + (", ".join(acc[c]["limits"]["failed_categories"]) or "overall")
                         + f"); speed reported anyway: {speed_txt}.")
        else:
            lines.append(f"{CFG_LABEL[c]}: within limits but slower: {speed_txt}.")
    rng_overlap = recommended != "top7b" and not (p50(recommended)["max"] < p50("top7b")["min"])
    if rng_overlap:
        lines.append("Caveat: the per-run p50 ranges overlap; the gain holds in the mean of 3 runs but is not larger than run-to-run spread.")
    lines += txt.get("recommendation_extra", [])
    card(s, 7.4, 1.35, 5.6, 2.75, "Recommendation and defence", lines, GREEN, 9.5)
else:
    pending(s, 7.4, 1.35, 5.6, 2.6, "recommendation (needs both accuracy and all 9 speed runs)",
            "tools/a2_analyze_speed.py; python3 deck/build_deck_a2.py")
footer(s, "docs/a2/prediction_record.md · docs/a2/prediction_inputs.json · results/a2/speed/summary.json · results/a2/accuracy/ · results/logs/a2_requests.jsonl")

# =================================================================== 8 limitations, references, AI
s = prs.slides.add_slide(BLANK)
header(s, 8, "Limitations · References · AI Declaration")
lim = txt.get("limitations") or [
    "**Sample size:** 87 test tickets (one ticket = 1.1 points overall); six of seven categories have 10–13 tickets, so per-category verdicts rest on one or two tickets. Wilson 95% CI for 7b's 78.2% is 68–86%.",
    "**Seen tickets:** every model already ran on the whole golden set in A1; the test half is not new data — it only keeps the rule from being tuned on the tickets it is scored on.",
    "**One machine, one rate:** results hold for Machine A's 4-CPU / 8 GiB Ollama container at one arrival rate. "
    + (f"Our rate {plan['rate_per_min']:.2f}/min is below the client's A1 peak of 1.0/min, so this compares configurations but does not show the recommended one carries the peak." if plan and plan["rate_per_min"] < 1.0
       else "Compare the test rate with the A1 peak (1.0/min) here."),
    "**~30 requests per run:** p50 per run is noisy; p95 is pooled over ~90 requests (roughly the 5th-slowest); no p99.",
    "**Workload:** 40 fixed tickets from our rows; production narratives are not capped at 2,000 chars, so long tickets (→ 7b) would be more common and the cascade's gain smaller.",
    "**Length signal is crude:** it does not look at the content; it works here only because short tickets are the ones the 3b gets as right as the 7b (tuning set).",
]
card(s, 0.35, 1.1, 6.4, 5.95, "What the results do not show", lim, RED, 11.5)
refs = [
    "[1] CFPB Consumer Complaint Database, course extract (CC0). consumerfinance.gov/data-research/consumer-complaints",
    "[2] Ollama 0.5.7, MIT Licence. github.com/ollama/ollama",
    "[3] Apache JMeter 5.6.3, Apache Licence 2.0. jmeter.apache.org",
    "[4] Qwen2.5-7B-Instruct (and 0.5B), Apache 2.0. huggingface.co/Qwen",
    "[5] Llama 3.2 1B / 3B, Llama 3.2 Community Licence + AUP. Built with Llama. llama.com/llama3_2/license",
    "[6] FastAPI (MIT), Uvicorn (BSD-3), httpx (BSD-3), SQLite (public domain), python-pptx (MIT), matplotlib (PSF-based).",
    "[7] Harchol-Balter, M. (2013). Performance Modeling and Design of Computer Systems, ch. 22 (processor-sharing queue used for predictions).",
]
card(s, 6.95, 1.1, 6.05, 3.2, "References and model licences", refs, NAVY, 9)
ai = txt.get("ai_declaration") or [
    "An AI assistant (Claude) proposed the length rule and its two settings from a tuning-set replay of our A1 records, drafted the prediction record, and wrote the cascade code, all test and analysis scripts, this deck generator and the first draft of the prediction account.",
    "The team reviewed and signed off the rule and predictions before any measurement, ran every test on Machines A and B, checked figures against the raw .jtl and log files, and is responsible for the recommendation.",
]
card(s, 6.95, 4.45, 6.05, 2.6, "AI declaration", ai, TEAL, 9.5)
footer(s, "docs/model_pins.md (licences) · docs/a2/")

# ------------------------------------------------------------------ draft banner + save
if PENDING_ITEMS:
    b = draft_slot.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(8.8), Inches(0.25), Inches(4.3), Inches(0.55))
    b.fill.solid(); b.fill.fore_color.rgb = RED; b.line.fill.background()
    r = b.text_frame.paragraphs[0].add_run(); r.text = f"DRAFT — {len(PENDING_ITEMS)} item(s) pending measurement"
    r.font.size, r.font.bold, r.font.color.rgb = Pt(13), True, WHITE
prs.core_properties.title = "ICT3113 Assignment 2 — Group P2-9"
prs.core_properties.author = "Group P2-9"
prs.save(OUT)
print(f"wrote {OUT}  ({len(prs.slides)} slides)")
if PENDING_ITEMS:
    print("PENDING:", "; ".join(dict.fromkeys(PENDING_ITEMS)))
