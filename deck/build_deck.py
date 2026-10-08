#!/usr/bin/env python3
"""Build deck/Group09.pptx (12 slides) from the evidence in this repo.

No measured number is typed by hand: each one is read from results/, golden/,
docs/*.json or docs/model_pins.md. A slide whose inputs do not exist yet shows
a red PENDING box naming the step that produces them. Free text written by the
team lives in deck/*.txt and deck/team.json.

Needs (deck builder only - the rest of the repo is stdlib):
    pip install python-pptx matplotlib
    python3 deck/build_deck.py
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

csv.field_size_limit(10 ** 9)
ROOT = Path(__file__).resolve().parents[1]
RES, DOCS, DECK = ROOT / "results", ROOT / "docs", ROOT / "deck"
BUILD = DECK / "build"
BUILD.mkdir(exist_ok=True)
OUT = DECK / "Group09.pptx"
MODELS = ["qwen2.5:0.5b", "llama3.2:1b", "llama3.2:3b", "qwen2.5:7b"]
CATS = ["Credit reporting", "Debt collection", "Mortgage", "Credit card",
        "Bank account or service", "Consumer loan", "Money transfer or service"]
SHORT = ["CredRep", "DebtCol", "Mortg", "CCard", "BankAcct", "ConsLoan", "MoneyTx"]
LICENCE = {"qwen2.5:0.5b": "Apache-2.0", "llama3.2:1b": "Llama 3.2 Community", "llama3.2:3b": "Llama 3.2 Community",
           "qwen2.5:7b": "Apache-2.0"}
NAVY, TEAL, GREY, RED, GREEN, LIGHT, WHITE = (RGBColor(0x1F, 0x3A, 0x5F), RGBColor(0x2B, 0x7A, 0x78), RGBColor(0x44, 0x4B, 0x55),
                                              RGBColor(0xC0, 0x39, 0x2B), RGBColor(0x2E, 0x7D, 0x32), RGBColor(0xEE, 0xF2, 0xF7),
                                              RGBColor(0xFF, 0xFF, 0xFF))


def safe(m):
    return m.replace(":", "_").replace("/", "_")


def jload(p):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def read_csv(p):
    p = Path(p)
    if not p.exists():
        return None
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def md_tables(path):
    """{section heading: {first cell: second cell}} for every markdown table."""
    out, sec = {}, ""
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            sec = line.lstrip("# ").strip()
        elif line.startswith("|") and not set(line) <= set("|-: "):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2:
                out.setdefault(sec, {})[cells[0]] = cells[1]
    return out


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
        r = p.add_run()
        r.text = line
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), b, color, "Calibri"
        p.space_after = Pt(3)
        if align:
            p.alignment = align
    return tb


def bullets(s, x, y, w, h, items, size=12):
    return text(s, x, y, w, h, [("• " + i[0], i[1]) if isinstance(i, tuple) else "• " + i for i in items], size)


def header(s, n, title, sub=None):
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.9))
    bar.fill.solid(); bar.fill.fore_color.rgb = NAVY; bar.line.fill.background()
    text(s, 0.4, 0.14, 11.6, 0.6, title, 26, True, WHITE)
    text(s, 12.3, 0.25, 0.9, 0.5, str(n), 14, color=RGBColor(0xBB, 0xCC, 0xDD), align=PP_ALIGN.RIGHT)
    if sub:
        text(s, 0.4, 0.95, 12.5, 0.4, sub, 12, color=TEAL)


def table(s, x, y, w, rows, cols, size=10, col_w=None, row_h=0.28, color=None):
    shp = s.shapes.add_table(len(rows) + 1, len(cols), Inches(x), Inches(y), Inches(w), Inches(row_h * (len(rows) + 1)))
    t = shp.table
    for i, cw in enumerate(col_w or []):
        t.columns[i].width = Inches(cw)
    for j, c in enumerate(cols):
        cell = t.cell(0, j); cell.text = str(c); cell.fill.solid(); cell.fill.fore_color.rgb = NAVY
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
                    c = color(i - 1, j, v) if color else None
                    if c:
                        r.font.color.rgb, r.font.bold = c, True
    return shp


def pending(s, x, y, w, h, what):
    b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    b.fill.solid(); b.fill.fore_color.rgb = RGBColor(0xFD, 0xED, 0xEC); b.line.color.rgb = RED
    b.text_frame.word_wrap = True
    r = b.text_frame.paragraphs[0].add_run(); r.text = "PENDING: " + what
    r.font.size, r.font.bold, r.font.color.rgb = Pt(13), True, RED


def box(s, x, y, w, h, label, fill=TEAL, size=11):
    b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    b.fill.solid(); b.fill.fore_color.rgb = fill; b.line.fill.background()
    tf = b.text_frame; tf.word_wrap = True
    for i, line in enumerate(label.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = line
        r.font.size, r.font.color.rgb, r.font.bold = Pt(size if i == 0 else size - 2), WHITE, i == 0


def arrow(s, x1, y1, x2, y2, label=None):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = GREY; c.line.width = Pt(1.75)
    ln = c.line._get_or_add_ln(); ln.append(ln.makeelement(qn("a:tailEnd"), {"type": "triangle"}))
    if label:
        text(s, min(x1, x2), min(y1, y2) - 0.33, abs(x2 - x1) + 0.3, 0.3, label, 9)


def lines_of(path, fallback):
    p = Path(path)
    return p.read_text(encoding="utf-8").strip().splitlines() if p.exists() and p.read_text(encoding="utf-8").strip() else [fallback]


def card(s, x, y, w, h, title, items, accent=TEAL, size=10.5):
    """Light panel with an accent bar, a bold title and bullets. An item
    "**Lead** rest" renders Lead in bold; a tuple (text, True) is a bold line."""
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    bg.fill.solid(); bg.fill.fore_color.rgb = LIGHT; bg.line.fill.background()
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(0.07), Inches(h))
    bar.fill.solid(); bar.fill.fore_color.rgb = accent; bar.line.fill.background()
    text(s, x + 0.18, y + 0.08, w - 0.28, 0.35, title, size + 2, True, accent)
    tb = s.shapes.add_textbox(Inches(x + 0.18), Inches(y + 0.45), Inches(w - 0.3), Inches(h - 0.5))
    tf = tb.text_frame; tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(4)
        whole_bold = isinstance(item, tuple)
        item = item[0] if whole_bold else item
        lead, rest = "", item
        if item.startswith("**") and "**" in item[2:]:
            lead, rest = item[2:].split("**", 1)
        for seg, b in (("• " if not whole_bold else "", False), (lead, True), (rest, whole_bold)):
            if seg:
                r = p.add_run(); r.text = seg
                r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), b, GREY, "Calibri"
    return tb


def sections_of(path):
    """'## Title' starts a card, '- item' adds a bullet; [] if the file is absent."""
    p = Path(path)
    out = []
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("## "):
                out.append((line[3:], []))
            elif line.startswith("- ") and out:
                out[-1][1].append(line[2:])
    return out


def fs(ms):
    return "" if ms is None else f"{ms / 1000:.2f}"


# ------------------------------------------------------------------- data
team = jload(DECK / "team.json") or {}
wl = jload(DOCS / "workload_model.json")
agree = jload(ROOT / "golden" / "agreement.json")
golden = read_csv(ROOT / "golden" / "golden_set.csv")
dis = read_csv(ROOT / "golden" / "disagreements.csv")
pins = md_tables(DOCS / "model_pins.md").get("Model Pins", {})
pins_rows = []
if (DOCS / "model_pins.md").exists():
    for line in (DOCS / "model_pins.md").read_text(encoding="utf-8").splitlines():
        c = [x.strip().strip("`") for x in line.strip().strip("|").split("|")]  # tags/digests are `code` in the md
        if line.startswith("|") and len(c) >= 5 and c[0] in MODELS:
            pins_rows.append(c[:5])
acc = {m: jload(RES / "accuracy" / f"summary_{safe(m)}.json") for m in MODELS}
acc = {m: a for m, a in acc.items() if a}
load, load_redo = {}, {}
# <model>_rate<R>_summary_<redo>.json replaces the plain summary when a run was
# redone (e.g. _summary_run3b.json: run3 lost to a network drop). The original
# files stay in results/ as evidence.
for p in sorted((RES / "jtl").glob("*_summary*.json")):
    j = json.loads(p.read_text(encoding="utf-8"))
    mm = re.match(r"(.+)_rate([\d.]+)_summary(?:_(\w+))?\.json$", p.name)
    if mm and (mm[3] or (mm[1], float(mm[2])) not in load_redo):
        load[(mm[1], float(mm[2]))] = j
        if mm[3]:
            load_redo[(mm[1], float(mm[2]))] = mm[3]
stress = {p.name.replace(".summary.json", ""): json.loads(p.read_text()) for p in sorted((RES / "stress").glob("*.summary.json"))}
env = md_tables(DOCS / "test_environment.md")
reqcheck = jload(RES / "requirements_check.json")
outcomes = DOCS / "prediction_outcomes.md"

# ------------------------------------------------------------------- 1 cover
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
text(s, 0.8, 1.2, 11.7, 1.0, "Routing Complaints On-Premises", 40, True, WHITE)
text(s, 0.8, 2.1, 11.7, 0.8, "CPU-only LLM ticket triage: requirements, measurement and a deployment recommendation", 22, color=RGBColor(0xBB, 0xDD, 0xEE))
text(s, 0.8, 3.2, 11.7, 0.5, "ICT3113 Performance Testing & Optimisation · Assignment 1 · Group P2-9 · dataset rows 9000–9999", 15, color=RGBColor(0xDD, 0xDD, 0xDD))
for i, m in enumerate(team.get("members", [])):
    text(s, 0.8 + (i % 3) * 4.0, 4.2 + (i // 3) * 0.45, 3.9, 0.45, f"{m['name']} · {m['id']}", 15, color=WHITE)
text(s, 0.8, 6.2, 11.7, 0.5, "Repository: " + team.get("repo", "PENDING"), 14, color=RGBColor(0x9F, 0xD8, 0xD6))
text(s, 0.8, 6.6, 11.7, 0.4, "Rebuild: git clone … && cp .env.example .env && docker compose up -d --build", 11, color=RGBColor(0xBB, 0xBB, 0xBB))

# ------------------------------------------------------------------- 2 architecture
s = prs.slides.add_slide(BLANK)
header(s, 2, "Service Architecture", "Baseline is synchronous: POST /tickets waits for one Ollama call. No cache, no queue, no batching, no retries in the service.")
grp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(3.5), Inches(1.45), Inches(9.45), Inches(3.75))
grp.adjustments[0] = 0.04
grp.fill.background(); grp.line.color.rgb = NAVY; grp.line.width = Pt(1.25); grp.line.dash_style = MSO_LINE.DASH
text(s, 3.65, 1.5, 9.2, 0.35, "Machine A · Irfan's PC · Docker Desktop on WSL 2 · CPU-only inference", 11, True, NAVY)
box(s, 0.4, 2.05, 2.35, 1.3, "Machine B · load generator\nApache JMeter 5.6.3, open model\nUwais's laptop, another home", GREY)
box(s, 3.85, 1.95, 3.6, 1.55, "triage-service (container)\nFastAPI · 1 uvicorn worker\nsync def endpoints → threadpool (40)\nOllama call timeout 300 s → HTTP 502", TEAL)
box(s, 8.75, 1.95, 3.9, 1.55, "triage-ollama (container)\nOllama 0.5.7 · one model at a time\n4-CPU quota · 8 GB · 4 parallel slots\ntemperature 0 · seed 42 · ≤ 16 tokens out", NAVY)
box(s, 3.85, 4.05, 3.6, 0.95, "SQLite tickets.db (volume)\nemptied before each test", RGBColor(0x6B, 0x8E, 0x23))
box(s, 8.75, 4.05, 3.9, 0.95, "results/logs/requests.jsonl\none JSON line per request, with run_id", RGBColor(0x8E, 0x6C, 0x23))
arrow(s, 2.75, 2.72, 3.85, 2.72)
text(s, 2.72, 2.12, 0.8, 0.55, ["HTTP via", "Tailscale"], 9)
arrow(s, 7.45, 2.72, 8.75, 2.72, "POST /api/generate")
arrow(s, 5.65, 3.5, 5.65, 4.05)
arrow(s, 7.45, 3.4, 8.75, 4.45)
table(s, 0.4, 5.4, 12.5, [
    ["POST /tickets", "{narrative, row_id?} → classify via Ollama (waits for the answer) → store → {ticket_id, category, model, latency_ms}"],
    ["GET /search?q=&limit=", "stored tickets whose narrative contains q (unindexed SQL LIKE scan), newest first"],
    ["GET /stats", "count of stored tickets per category, including UNPARSED"]], ["Endpoint", "Behaviour"], 11, [2.3, 10.2])
text(s, 0.4, 6.6, 12.5, 0.8, [
    "Prompt: the 7 categories as a numbered list, \"reply with the category number\"; the reply is parsed to 1 of 7 or UNPARSED (scored as wrong).",
    "Concurrency is bounded only by the FastAPI threadpool and Ollama's 4 parallel slots; requests beyond 4 wait inside Ollama, not in the service."], 10)

# ------------------------------------------------------------------- 3 workload
s = prs.slides.add_slide(BLANK)
header(s, 3, "Workload Model", "One large retail bank (Barclays UK scale); timing from CFPB data; lengths measured on our rows")
if wl:
    table(s, 0.4, 1.45, 7.6, [
        ["Tickets / year", f"{wl['annual_tickets']:,}", "Barclays UK H2-2024: 70,569 opened ×2 [3] (E1)"],
        ["Mean rate", f"{wl['mean_per_hour']:.1f}/h ({wl['mean_per_s']} /s)", "derived"],
        ["Busiest weekday / month", "Tue 17.8 % · ×1.08", "CFPB API, Bank of America 2024 [2]"],
        ["Peak day", f"{wl['peak_day']:.0f} tickets", "derived"],
        ["Peak hour (design)", f"{wl['peak_hour']:.0f}/h → {wl['design_peak_per_min']}/min ({wl['design_peak_per_s']}/s)", "E2+E3: 70 % in 08–18 h, peak 1.5× [5]"],
        ["Peak ÷ mean · ÷ off-peak", f"×{wl['peak_over_mean']} · ×{wl['peak_over_offpeak']:.0f}", f"off-peak {wl['offpeak_hour']}/h"],
        ["Surge (throughput target)", f"{wl['surge_per_min']}/min ({wl['surge_per_s']}/s)", "E5: 2× peak"],
        ["Agent searches (peak)", f"{wl['peak_searches_per_min']}/min · ratio {wl['search_ratio']}:1", "E4: 3 per ticket; E6: ~23 agents"],
        ["Cost of a misroute", f"{wl['misroute_hours_per_pct']} agent-h/yr per 1 %", "E7: 5 agent-min + ≥1 day delay"],
    ], ["Quantity", "Value", "Source / method"], 10, [1.9, 2.6, 3.1])
    L = wl["length_chars"]
    text(s, 0.4, 4.6, 7.6, 1.5, [(f"Ticket length (n = {L['n']:,} team rows) [6]", True),
         f"p50 {L['p50']} · p95 {L['p95']} · max {L['max']} chars (mean {L['mean']}); ≈ ÷3.6 tokens",
         "Extract caps at 2,000 chars → production prompts are longer → our latency is optimistic.",
         "E1–E7 are labelled estimates; method for each in docs/workload_model.md."], 11)
    if (DOCS / "workload.png").exists():
        s.shapes.add_picture(str(DOCS / "workload.png"), Inches(8.15), Inches(1.5), width=Inches(5.0))
else:
    pending(s, 0.6, 1.6, 11, 0.9, "python3 tools/workload_model.py")

# ------------------------------------------------------------------- 4 requirements
s = prs.slides.add_slide(BLANK)
header(s, 4, "Performance & Accuracy Requirements", "Position: a misroute costs more than a slow triage → accuracy is primary; latency/throughput are constraints")
table(s, 0.4, 1.45, 12.5, [
    ["R1 POST latency", "p95 ≤ 15 s, p99 ≤ 30 s", "0.0167 tickets/s (1/min) + search 3×; 3 × 10 min; every run", "sync intake holds a connection: p99 inside a 30 s gateway timeout"],
    ["R2 Search latency", "p95 ≤ 1.0 s", "same mixed peak load", "agent waits at a screen; 1 s keeps flow of thought (Nielsen)"],
    ["R3 Throughput", "≥ 120 tickets/h; achieved ≥ 95 % of offered; < 5 in flight at end", "0.0333 tickets/s (surge); 3 × 10 min", "2× peak: bursts, incidents, growth"],
    ["R4 Accuracy", "≥ 85 % overall (Wilson 95 % CI)", "golden set, sequential", "15 % misroutes ≈ 1,764 agent-h/yr ≈ 1 FTE"],
    ["R5 Per category", "recall ≥ 70 % in every category", "golden set", "each category = one team; none starved"],
    ["R6 Reliability", "HTTP errors < 1 %; UNPARSED < 2 %", "surge / golden set", "an unparsed answer is a routing failure"],
], ["ID", "Requirement", "Load condition", "Justification"], 11, [1.8, 3.5, 3.6, 3.6], 0.5)

# ------------------------------------------------------------------- 5 candidates
s = prs.slides.add_slide(BLANK)
header(s, 5, "Candidate Models", "Four models, four size classes (0.5B → 7.6B, ×15), pinned by Ollama tag + digest")
if pins_rows:
    table(s, 0.4, 1.45, 12.5, [r + [LICENCE.get(r[0], "")] for r in pins_rows],
          ["Tag", "Digest", "Params", "Quant", "Size", "Licence"], 9, [1.5, 6.0, 0.9, 1.0, 1.0, 2.1])
else:
    pending(s, 0.4, 1.45, 12.5, 0.8, "tools/pin_models.sh " + " ".join(MODELS) + "  → docs/model_pins.md")
bullets(s, 0.4, 3.3, 12.5, 3.6, [
    "Shape, not a point: four sizes show whether accuracy keeps rising with size or flattens, which decides the recommendation.",
    "Size vs family: Qwen 0.5B vs 7B and Llama 1B vs 3B separate the effect of parameters from the effect of family.",
    "All licences allow commercial on-prem use (Apache-2.0; Llama 3.2 Community, attribution on Slide 12).",
    "Excluded: Qwen2.5-3B/72B (research licences); ≥13B (would fail R1 before queueing on 4 cores); Gemma 3 (needs newer Ollama than the pinned 0.5.7).",
    "Same Ollama image for every model: ollama/ollama:0.5.7, CPU only, 4-CPU limit.",
], 12)

# ------------------------------------------------------------------- 6 golden set
s = prs.slides.add_slide(BLANK)
header(s, 6, "Golden Test Set", "175 candidates stratified 25 per raw label; raw labels withheld from annotators; frozen before any model run")
bullets(s, 0.4, 1.45, 6.2, 3.0, [
    "Protocol: label the product the complained-of CONDUCT attaches to (§2); precedence for ties: Debt collection > Credit reporting > Mortgage > product (§4); edge-case table (§5).",
    "Annotator A (Gabriel) and B (Alvin) labelled independently; two separate commits are the evidence.",
    "Every disagreement adjudicated with a resolution note; protocol revised where a gap showed.",
], 11)
if agree:
    text(s, 6.9, 1.45, 6.0, 1.4, [(f"{agree['statistic']} κ = {agree['kappa']:.3f} ({agree['interpretation']})", True),
         f"raw agreement {agree.get('raw_agreement', 0):.1%} on {agree['n_tickets']} tickets; {agree['n_disagreements']} disagreements",
         f"golden set: {len(golden)} tickets" if golden else "golden_set.csv: PENDING (make merge)"], 14, color=NAVY)
    ex = [r for r in (dis or []) if (r.get("adjudicated_label") or "").strip()][:2]
    if ex:
        a_col = [k for k in ex[0] if k.startswith("label_")]
        table(s, 6.9, 3.0, 6.0, [[r["row"]] + [r[k] for k in a_col] + [r["adjudicated_label"], r["resolution_note"][:110]] for r in ex],
              ["Row"] + [k.replace("label_", "") for k in a_col] + ["Final", "Resolution"], 9, [0.6, 1.15, 1.15, 1.15, 1.95], 0.55)
    pairs = agree.get("confused_pairs", [])[:3]
    text(s, 6.9, 4.6, 6.0, 1.0, [("Most-disputed pairs", True)] + [f"{p['n']} × {' ↔ '.join(p['pair'])}" for p in pairs], 10)
else:
    pending(s, 6.9, 1.5, 6.0, 1.3, "both label sheets → make agree → adjudicate → make merge")
prot = (ROOT / "golden" / "labelling_protocol.md").read_text(encoding="utf-8")
revs = re.findall(r"^### (v[\d.]+ — .+)$", prot, re.M)
text(s, 0.4, 5.75, 12.5, 1.4, [("Protocol revisions", True)] + (revs[:5] or ["(revision history not yet filled in)"]), 10)

# ------------------------------------------------------------------- 7 environment
s = prs.slides.add_slide(BLANK)
header(s, 7, "Test Environment", "JMeter on Machine B, service + Ollama on Machine A: two machines in two homes, joined by Tailscale. Inference CPU-only.")
# Measured figures on this slide are read from the evidence files, not typed.
ping_txt = (RES / "network" / "ping_machineB_to_A_2026-10-07.txt")
ping_ms = [int(x) for x in re.findall(r"time=(\d+)ms", ping_txt.read_text(encoding="utf-8"))] if ping_txt.exists() else []
loss = re.search(r"\((\d+)% loss\)", ping_txt.read_text(encoding="utf-8")) if ping_txt.exists() else None
connect = []
for p in sorted((RES / "jtl").glob("*.jtl")):
    if p.name == "llama3.2_1b_rate0.0667_run3.jtl":   # lost to the network drop; redone as run3b
        continue
    connect += [int(r["Connect"]) for r in read_csv(p) or [] if r.get("success") == "true" and r.get("Connect")]
connect.sort()
q = lambda v, f: v[min(len(v) - 1, int(round(f * (len(v) - 1))))]
busy = []
for line in (RES / "stress" / "dockerstats_stress_llama3.2_3b.txt").read_text(encoding="utf-8").splitlines() \
        if (RES / "stress" / "dockerstats_stress_llama3.2_3b.txt").exists() else []:
    mm = re.match(r"triage-ollama cpu=([\d.]+)%", line)
    if mm and float(mm[1]) > 50:
        busy.append(float(mm[1]))
busy.sort()
stored = {}
if (RES / "logs" / "requests.jsonl").exists():
    for line in (RES / "logs" / "requests.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        if d.get("endpoint") == "POST /tickets" and d.get("status") == 200 and "_rate" in d.get("run_id", ""):
            # one store per model's matrix; a redone run (run3b) had a store of its own
            redo = re.search(r"_run\d+([a-z]+)$", d["run_id"])
            k = d["run_id"].split("_rate")[0] + (redo[1] if redo else "")
            stored[k] = stored.get(k, 0) + 1
S = {m: a["latency_ms"]["p50"] / 1000 for m, a in acc.items()}

card(s, 0.4, 1.4, 4.1, 2.55, "Machine A · system under test", [
    "**CPU** Intel Core i9-10900K, 10 cores / 20 threads, AVX2",
    "**Memory** 48 GB host · WSL 2 VM 12 GB · Ollama container 8 GB",
    "**Software** Windows 11 Pro · WSL 2 Ubuntu 24.04 · Docker Engine 29.8.2 · Ollama 0.5.7",
    f"**Ollama** 4-CPU quota (median {q(busy, .5):.0f} % CPU when busy) · 4 parallel slots · --threads 10" if busy else
    "**Ollama** 4-CPU quota · 4 parallel slots · --threads 10",
    "**GPU** RTX 3090 installed, not used: none mapped to Docker; Ollama log: library=cpu, layers.offload=0",
], NAVY, 9.5)
card(s, 4.62, 1.4, 4.1, 2.55, "Machine B · load generator", [
    "**CPU** AMD Ryzen 7 8845HS, 8 cores / 16 threads · 16 GB",
    "**Software** Windows 11 Home · JMeter 5.6.3 (Git Bash) · Java 21 · 1 GB heap",
    "**Separate machine, separate home:** JMeter never shares a CPU with the service or Ollama",
    "**Evidence:** every .jtl was written on Machine B and targets Machine A's Tailscale address (URL column: 100.88.74.36:8000)",
], GREY, 9.5)
net_items = ["**Link** Tailscale (WireGuard), direct peer-to-peer; both machines wired to home broadband"]
if ping_ms:
    net_items.append(f"**Ping** {len(ping_ms)} packets, {loss[1] if loss else '?'} % loss; RTT min {min(ping_ms)} / avg "
                     f"{sum(ping_ms) / len(ping_ms):.1f} / max {max(ping_ms)} ms")
if connect:
    net_items.append(f"**During tests** TCP connect median {q(connect, .5)} ms, p95 {q(connect, .95)} ms ({len(connect):,} requests)")
if ping_ms and S:
    net_items.append(f"**Share of latency** avg RTT is {sum(ping_ms) / len(ping_ms) / 10 / min(S.values()):.2f} % of the fastest model's "
                     f"single-request p50 ({min(S.values()):.1f} s)")
net_items.append("**One outage** ~2 min on 8 Oct 04:00; the affected run was redone as run3b, the original kept")
card(s, 8.84, 1.4, 4.1, 2.55, "Network", net_items, TEAL, 9.5)

card(s, 0.4, 4.07, 6.2, 3.28, "Scaling to the client's servers", [], GREEN, 10)
if S:
    table(s, 0.58, 4.55, 2.75, [[m, f"{S[m]:.1f}", f"{60 / S[m]:.1f}"] for m in MODELS if m in S],
          ["Model", "S (s)", "μ /min"], 9, [1.25, 0.65, 0.85], 0.27)
    text(s, 0.58, 4.55 + 0.27 * (len(S) + 1) + 0.05, 2.75, 0.6,
         "S = single-request p50 from the accuracy run (sequential). μ = 60 / S per 4-CPU Ollama instance.", 8.5)
else:
    pending(s, 0.58, 4.55, 2.75, 0.9, "accuracy run (S per model)")
bullets(s, 3.45, 4.5, 3.05, 2.85, [
    "Client: commodity CPU servers, no GPU (brief).",
    "Capacity ≈ number of 4-CPU instances × μ; replicas behind a load balancer.",
    "Our cores boost up to 5.3 GHz; server cores are usually slower per core, so S may be higher there (assumption, not measured).",
    "Before sizing: measure S on one client server, then rerun the stress test there.",
], 10.5)
card(s, 6.72, 4.07, 6.21, 3.28, "Limitations and threats to validity", [
    "**Shared desktop:** EA, Razer and Riot Vanguard background services could not be stopped; Chrome was open for part of the accuracy run",
    "**Oversubscribed runner:** Ollama's --threads 10 inside a 4-CPU quota, kept for the baseline (pre-freeze check: 3.1 s vs 2.2 s with 4 threads)",
    "**Data:** narratives capped at 2,000 chars, so latency is optimistic",
    (f"**Search:** measured with at most {max(stored.values()) + 3} stored tickets (store emptied per model); "
     "an unindexed LIKE scan slows at production volume") if stored else "**Search:** measured at a small table size",
    "**Thermal:** CPU temperature not logged; 0.5B–3B show no steady run 1 → 3 slowdown; 7B's rise coincides with backlog between runs",
    "**Docker Desktop** stopped once on 8 Oct between tests; restarted, no run affected",
], RED, 10.5)

# ------------------------------------------------------------------- 8 playbook
s = prs.slides.add_slide(BLANK)
header(s, 8, "Playbook: Testing Procedure", "Full procedure in docs/playbook.md; preconditions P1–P7 before every test")
steps = [("Freeze", "golden set + predictions\ncommitted first"),
         ("B · Load (open loop)", "4 models × 3 rates × 3 runs\n1 / 2 / 4 tickets/min + search 3×"),
         ("C · Accuracy", "golden set × 4 models\nsequential → single-request S"),
         ("D · Stress", "llama3.2:3b, stepped rate\n0.5μ→1.5μ · 300 s steps · 3 ladders")]
for i, (t, d) in enumerate(steps):
    box(s, 0.4 + i * 3.2, 1.4, 2.8, 1.05, f"{t}\n{d}", [GREY, NAVY, GREEN, RED][i], 12)
    if i < len(steps) - 1:
        arrow(s, 3.2 + i * 3.2, 1.92, 3.6 + i * 3.2, 1.92)
card(s, 0.4, 2.75, 4.1, 4.5, "JMeter setup · Machine B", [
    "**Open loop:** Open Model Thread Group, rate(R/sec) random_arrivals(10 min) pause(120 s). Poisson arrivals that never wait for a response",
    "**Mixed load:** POST /tickets at R, GET /search at 3 × R",
    "**Rates:** 1, 2, 4 tickets/min (peak, surge, 2× surge); 3 runs × 10 min each",
    "**Feed:** pre-escaped TSV of our 1,000 rows (tools/prepare_jmeter_data.py)",
    "**Per request:** keep-alive off; X-Run-ID header tags the service log line; seed = run number",
    "**Timeouts:** JMeter 600 s; service → Ollama 300 s (then 502)",
], NAVY, 12)
card(s, 4.62, 2.75, 4.1, 4.5, "Each model, each run", [
    "**Handover:** Machine A restarts on the model with an empty ticket store, sends 3 non-golden warm-ups, reports 'ready'; Machine B waits for it (overnight_switch.sh ↔ run_all_models.sh)",
    "**After every run:** reconcile.py per endpoint (counts and errors vs the service log for that run id); analyze_jtl.py gives p50/p95/p99, throughput, errors, mean ± SD of 3 runs",
    "**Stress:** 7 steps around μ = 60/S from the accuracy run; sustainable ⇔ end-of-step queue ≤ max(5, 15 % of arrivals) and 0 errors; 620 s drain, 60 s settle between ladders",
], TEAL, 12)
card(s, 8.84, 2.75, 4.1, 4.5, "Validity rules", [
    "**Freeze first:** golden set and prediction record committed before any benchmark run",
    "**Separate machines:** JMeter on Machine B, service + Ollama on Machine A",
    "**Reconcile every run:** every gap between the .jtl and the service log is explained in results/logs/reconcile_notes.md",
    "**Harness fault → redo:** a run hit by a test-side fault is repeated under a new run id; the original stays as evidence (e.g. run3b)",
    "**No backlog across models:** Machine A switches only after 300 s with no new log lines",
], RED, 12)

# ------------------------------------------------------------------- 9 load + stress
s = prs.slides.add_slide(BLANK)
header(s, 9, "Load & Stress Test Results", "POST /tickets latency in seconds: mean of 3 runs (± SD); open-loop arrivals; red = misses a requirement threshold")
rows = []
order = {safe(m): i for i, m in enumerate(MODELS)}
for (sm, rate), j in sorted(load.items(), key=lambda kv: (order.get(kv[0][0], 99), kv[0][1])):
    post = j["by_label"].get("POST /tickets", {}).get("across_runs", {})
    srch = j["by_label"].get("GET /search", {}).get("across_runs", {})
    n = len(j["by_label"].get("POST /tickets", {}).get("runs", []))
    if not post:
        continue
    f = lambda k: f"{fs(post[k]['mean'])} ±{fs(post[k]['stdev'])}" if post.get(k) else ""
    rows.append([sm.replace("_", ":", 1), f"{rate * 60:.0f}/min", f("p50_ms"), f("p95_ms"), f("p99_ms"),
                 f"{post['achieved_per_hour']['mean']:.0f}", f"{post['error_rate_pct']['mean']:.1f}",
                 f"{srch['p95_ms']['mean']:.0f}" if srch.get("p95_ms") else "", n])
ROW_H = 0.235
if rows:
    def red(i, j, v):
        try:
            x = float(str(v).split()[0].rstrip("/min"))
        except ValueError:
            return None
        return RED if (j == 3 and x > 15) or (j == 4 and x > 30) or (j == 6 and x >= 1) or (j == 7 and x > 1000) or (j == 8 and x < 3) else None
    table(s, 0.4, 1.35, 8.1, rows, ["Model", "Tickets", "p50", "p95", "p99", "Achieved /h", "Err %", "Search p95 ms", "Runs"], 9,
          [1.2, 0.75, 1.0, 1.0, 1.0, 0.95, 0.6, 1.0, 0.6], ROW_H, red)
    if load_redo:
        text(s, 0.4, 1.35 + ROW_H * (len(rows) + 1) + 0.02, 8.1, 0.3,
             "; ".join(f"{sm.replace('_', ':', 1)} @ {rate * 60:.0f}/min uses {redo} in place of the run lost to a network drop"
                       for (sm, rate), redo in load_redo.items()) + " (results/logs/reconcile_notes.md)", 8.5, color=TEAL)
else:
    pending(s, 0.4, 1.5, 8.1, 1.0, "Test B: jmeter/run_matrix.sh for each model (writes results/jtl/*_summary.json)")
if stress:
    k0 = sorted(stress)[0]
    if (RES / "stress" / f"{k0}.png").exists():
        s.shapes.add_picture(str(RES / "stress" / f"{k0}.png"), Inches(8.75), Inches(1.35), width=Inches(4.25))
    first = next(iter(stress.values()))
    text(s, 8.75, 3.95, 4.25, 0.9, [(f"Stress limit · {first['model']} (chart: ladder 1)", True)] + [
        f"Ladder {k.split('_run')[-1]}: sustainable "
        f"{'≤ ' + str(v['max_sustainable_per_min']) + '/min' if v['max_sustainable_per_min'] else 'at no step'} · "
        f"saturated {v['saturated_throughput_per_min']}/min · {v['total_errors']} errors" for k, v in stress.items()], 9)
else:
    pending(s, 8.75, 1.4, 4.25, 1.0, "Test D: jmeter/run_stress.sh → tools/analyze_stress.py")
cards = sections_of(DECK / "interpretation_slide9.txt")
if cards:
    w = (12.55 - 0.12 * (len(cards) - 1)) / len(cards)
    for i, (title, items) in enumerate(cards):
        card(s, 0.4 + i * (w + 0.12), 4.9, w, 2.45, title, items, [NAVY, TEAL, RED, GREEN][i % 4], 9.5)
else:
    text(s, 0.4, 5.0, 12.5, 1.7, lines_of(DECK / "interpretation_slide9.txt", "Interpretation + diagnosed bottleneck: PENDING (Uwais writes deck/interpretation_slide9.txt from the results)"), 11)

# ------------------------------------------------------------------- 10 accuracy
s = prs.slides.add_slide(BLANK)
header(s, 10, "Accuracy Results (golden set)", "Per-category figure = recall: share of that category's golden tickets routed correctly")
if acc:
    rows = []
    for m, a in acc.items():
        rows.append([m, f"{a['overall_accuracy']:.1%}", a["unparsed"]] +
                    [f"{a['per_category'][c]['recall']:.0%}" if a["per_category"][c]["recall"] is not None else "" for c in CATS])
    def col(i, j, v):
        if j == 1:
            return GREEN if float(v.strip("%")) >= 85 else RED
        if j >= 3 and v:
            return GREEN if float(v.strip("%")) >= 70 else RED
        return None
    table(s, 0.4, 1.45, 12.5, rows, ["Model", "Overall", "Unparsed"] + SHORT, 10, [1.6, 0.9, 0.9] + [1.3] * 7, color=col)
    for i, (m, a) in enumerate(acc.items()):
        cm = a["confusion_matrix"]
        labels = CATS + ["UNPARSED"]
        M = [[cm[g_].get(p_, 0) for p_ in labels] for g_ in CATS]
        fig, ax = plt.subplots(figsize=(4.2, 3.6))
        ax.imshow([[x / max(1, sum(r)) for x in r] for r in M], cmap="Blues", vmin=0, vmax=1)
        for gi in range(7):
            for pi in range(8):
                if M[gi][pi]:
                    ax.text(pi, gi, M[gi][pi], ha="center", va="center", fontsize=7)
        ax.set_xticks(range(8), SHORT + ["UNP"], rotation=50, ha="right", fontsize=7)
        ax.set_yticks(range(7), SHORT, fontsize=7)
        ax.set_xlabel("predicted", fontsize=8); ax.set_ylabel("golden", fontsize=8)
        ax.set_title(f"{m} · {a['overall_accuracy']:.1%}", fontsize=9)
        fig.tight_layout(); png = BUILD / f"cm_{safe(m)}.png"; fig.savefig(png, dpi=160); plt.close(fig)
        s.shapes.add_picture(str(png), Inches(0.4 + i * 3.15), Inches(2.95), height=Inches(2.75))
    tops = []
    for m, a in acc.items():
        cm = a["confusion_matrix"]
        cells = sorted(((cm[g_][p_], g_, p_) for g_ in cm for p_ in cm[g_] if g_ != p_), reverse=True)[:2]
        tops.append(f"{m}: " + "; ".join(f"{g_} → {p_} ({n})" for n, g_, p_ in cells if n))
    text(s, 0.4, 5.85, 12.5, 1.4, [("Largest confusions (golden → predicted)", True)] + tops, 10)
else:
    pending(s, 0.4, 1.5, 12.5, 1.0, "Test C: tools/accuracy_harness.py for each model (after the freeze)")

# ------------------------------------------------------------------- 11 predictions + recommendation
s = prs.slides.add_slide(BLANK)
header(s, 11, "Predictions vs Outcomes · Recommendation", "Predictions committed with the golden set, before the first benchmark")
if outcomes.exists():
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in outcomes.read_text(encoding="utf-8").splitlines()
            if l.startswith("| ") and not l.startswith("| Claim")]
    # keep the claims that matter most: per-model accuracy and p50, then every cross-model claim
    keep = [r for r in rows if r[0].endswith("accuracy") or r[0].endswith("single p50")]
    keep += [r for r in rows if not any(r[0].endswith(t) for t in ("accuracy", "single p50", "single p95"))]
    clip = lambda v: v if len(v) <= 58 else v[:56] + "…"   # full text: docs/prediction_outcomes.md
    table(s, 0.4, 1.45, 7.7, [[clip(c) for c in r[:4]] for r in keep[:14]], ["Claim", "Predicted", "Measured", "Verdict"], 8, [2.1, 1.8, 2.7, 1.1], 0.25,
          lambda i, j, v: (RED if v == "WRONG" else GREEN) if j == 3 else None)
else:
    pending(s, 0.4, 1.5, 7.7, 0.9, "python3 tools/compare_predictions.py")
if reqcheck:
    keys = ["R1", "R2", "R3", "R4", "R5", "R6_http", "R6_unparsed"]
    table(s, 0.4, 5.45, 7.7, [[m] + [reqcheck[m][k][0] for k in keys] for m in reqcheck],
          ["Model vs req.", "R1", "R2", "R3", "R4", "R5", "R6 err", "R6 unp"], 8, [1.6] + [0.87] * 7, 0.25,
          lambda i, j, v: (GREEN if v == "PASS" else RED if v == "FAIL" else None) if j else None)
else:
    pending(s, 0.4, 5.55, 7.7, 0.8, "python3 tools/requirements_check.py")
text(s, 8.3, 1.45, 4.8, 5.8, lines_of(DECK / "recommendation.txt", "Recommendation: PENDING (Muhaimeen writes deck/recommendation.txt from the measured results, defended against R1–R6)"), 11)

# ------------------------------------------------------------------- 12 references
s = prs.slides.add_slide(BLANK)
header(s, 12, "References & Acknowledgements")
text(s, 0.4, 1.15, 12.5, 6.2, [
    "[1] Consumer Financial Protection Bureau (2025). Consumer Response Annual Report, Jan 1 – Dec 31 2024. https://files.consumerfinance.gov/f/documents/cfpb_cr-annual-report_2025-05.pdf",
    "[2] Consumer Financial Protection Bureau. Consumer Complaint Database (and API). https://www.consumerfinance.gov/data-research/consumer-complaints/ (course extract; data CC0; accessed 6 Oct 2026).",
    "[3] Barclays (2025). UK complaints data, July–December 2024. https://home.barclays/sustainability/esg-resource-hub/reporting-and-disclosures/uk-complaints-data/",
    "[4] Financial Conduct Authority (2025). Firm complaints data 2024 H2 (via data.gov.uk).",
    "[5] Brown, L., Gans, N., Mandelbaum, A., et al. (2005). Statistical Analysis of a Telephone Call Center: A Queueing-Science Perspective. JASA 100(469), 36–50.",
    "[6] Nielsen, J. (1993). Usability Engineering, ch. 5 'Response time limits'. Academic Press.",
    "[7] Cohen, J. (1960). A coefficient of agreement for nominal scales. Educational and Psychological Measurement 20(1), 37–46.",
    "[8] Ollama v0.5.7, MIT License. https://github.com/ollama/ollama   ·   Apache JMeter, Apache License 2.0. https://jmeter.apache.org/",
    "[9] Qwen Team (2024). Qwen2.5-0.5B-Instruct and Qwen2.5-7B-Instruct, Apache License 2.0. https://huggingface.co/Qwen",
    "[10] Meta (2024). Llama 3.2 1B and 3B, Llama 3.2 Community License Agreement and Acceptable Use Policy. Built with Llama. https://www.llama.com/llama3_2/license/",
    "Software: FastAPI (MIT), Uvicorn (BSD-3-Clause), httpx (BSD-3-Clause), SQLite (public domain), Docker. An AI coding assistant was used for scaffolding and tooling; labelling, test execution and the recommendation are the team's.",
], 11)

prs.save(OUT)
print(f"wrote {OUT.relative_to(ROOT)} ({len(prs.slides)} slides)")
