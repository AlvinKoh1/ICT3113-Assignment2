#!/usr/bin/env python3
"""PDF copies of the three supporting files the brief asks to submit with the deck
(xSiTe accepted PDF only in Assignment 1):

  docs/a2/escalation_rule.md     -> docs/a2/supporting/Group09_A2_escalation_rule.pdf
  docs/a2/prediction_record.md   -> docs/a2/supporting/Group09_A2_prediction_record.pdf
  data/a2_speed_rows.csv         -> docs/a2/supporting/Group09_A2_speed_test_rows.pdf

The .md / .csv files in git stay the source of truth (their commit dates are the
evidence they came before measurement); these PDFs are only the submission copies.
Same design as the team guide. Needs Chrome; no Python packages.

    python docs/a2/build_supporting_pdfs.py [path-to-chrome]
"""
from __future__ import annotations

import csv
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "supporting"
CHROME = sys.argv[1] if len(sys.argv) > 1 else r"C:\Program Files\Google\Chrome\Application\chrome.exe"
HEAD = (ROOT / "docs" / "remaining_work.html").read_text(encoding="utf-8")
HEAD = HEAD[: HEAD.index("<body>")].replace("</style>", """
.doc > * + * { margin-top: 12px; }
.doc h1 { margin-top: 6px; } .doc h2 { margin-top: 22px; } .doc ul, .doc ol { margin: 6px 0; padding-left: 1.3rem; }
</style>""")


def inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*([^*]+)\*(?!\w)", r"<i>\1</i>", t)
    return t


def md_to_html(md: str) -> str:
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append("<pre><code>" + html.escape("\n".join(lines[i + 1:j])) + "</code></pre>")
            i = j + 1
            continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                is_separator = all(set(c) <= set("-: ") for c in cells) and any("-" in c for c in cells)
                if not is_separator:
                    rows.append(cells)
                i += 1
            t = ['<div class="tbl"><table><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in rows[0]) + "</tr></thead><tbody>"]
            t += ["<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:]]
            out.append("".join(t) + "</tbody></table></div>")
            continue
        m = re.match(r"^(#{1,3}) (.*)", ln)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if re.match(r"^\s*([*-]|\d+\.) ", ln):
            ordered = bool(re.match(r"^\s*\d+\.", ln))
            items = []
            while i < len(lines) and (re.match(r"^\s*([*-]|\d+\.) ", lines[i]) or (lines[i].startswith("   ") and lines[i].strip())):
                if re.match(r"^\s*([*-]|\d+\.) ", lines[i]):
                    items.append(re.sub(r"^\s*([*-]|\d+\.) ", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f'<{tag} class="tight">' + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        if not ln.strip():
            i += 1
            continue
        para = [ln]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||```|\s*([*-]|\d+\.) )", lines[i]):
            para.append(lines[i])
            i += 1
        out.append("<p>" + inline(" ".join(para)) + "</p>")
    return "\n".join(out)


def page(title_eyebrow: str, body: str) -> str:
    return (HEAD + '<body><main class="page"><header class="stack">'
            f'<div class="eyebrow">{title_eyebrow}</div></header>'
            '<div class="doc">' + body + "</div></main></body></html>")


def render(html_text: str, pdf: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=HERE, delete=False, encoding="utf-8") as fh:
        fh.write(html_text)
        tmp = Path(fh.name)
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=10000",
                        f"--print-to-pdf={pdf}", tmp.as_uri()], check=True, capture_output=True)
    finally:
        tmp.unlink(missing_ok=True)


def commit_of(path: str) -> str:
    r = subprocess.run(["git", "log", "-1", "--format=%h, %ad", "--date=format:%d %b %Y %H:%M", "--", path],
                       cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() or "uncommitted"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    eyebrow = "ICT3113 Assignment 2 · Group P2-9 · supporting file"
    for src, name in (("docs/a2/escalation_rule.md", "Group09_A2_escalation_rule.pdf"),
                      ("docs/a2/prediction_record.md", "Group09_A2_prediction_record.pdf")):
        md = (ROOT / src).read_text(encoding="utf-8")
        body = md_to_html(md) + f'<p class="small">Source: <code>{src}</code>, last committed {commit_of(src)} (git).</p>'
        render(page(eyebrow, body), OUT / name)
        print("wrote", OUT / name)
    rows = list(csv.DictReader(open(ROOT / "data" / "a2_speed_rows.csv", encoding="utf-8")))
    warm = list(csv.DictReader(open(ROOT / "data" / "a2_warmup_rows.csv", encoding="utf-8")))
    cal = list(csv.DictReader(open(ROOT / "data" / "a2_calib_rows.csv", encoding="utf-8")))
    tbl = ('<div class="tbl"><table><thead><tr><th>Order</th><th>Dataset row</th><th>Characters</th>'
           '<th>Order</th><th>Dataset row</th><th>Characters</th></tr></thead><tbody>')
    half = (len(rows) + 1) // 2
    for a, b in zip(rows[:half], rows[half:] + [None] * (2 * half - len(rows))):
        right = f"<td>{b['order']}</td><td>{b['row']}</td><td>{b['chars']}</td>" if b else "<td></td><td></td><td></td>"
        tbl += f"<tr><td>{a['order']}</td><td>{a['row']}</td><td>{a['chars']}</td>{right}</tr>"
    tbl += "</tbody></table></div>"
    body = ("<h1>Speed-test workload: dataset rows</h1>"
            "<p>The fixed tickets every speed-test run sends, in this order, for every configuration (JMeter recycles the list; "
            "a run of about 30 arrivals uses the first 30). All are team rows 9000–9999 <b>outside</b> the golden set, chosen at "
            "even length quantiles so the list carries the rows' own mix of typical and long tickets, then put in a fixed order "
            "(seed 3113) so length does not trend through a run.</p>" + tbl +
            f"<p><b>Warm-up tickets</b> (sent before every run, timings discarded): rows {', '.join(r['row'] + ' (' + r['chars'] + ' chars)' for r in warm)}. "
            "The short one reaches the small model in the cascade; the long ones reach the large model.</p>"
            f"<p><b>S calibration tickets</b> (three different tickets of typical length, sent once to qwen2.5:7b): rows "
            f"{', '.join(r['row'] + ' (' + r['chars'] + ' chars)' for r in cal)}.</p>"
            f'<p class="small">Source: <code>data/a2_speed_rows.csv</code>, <code>data/a2_warmup_rows.csv</code>, '
            f"<code>data/a2_calib_rows.csv</code>, last committed {commit_of('data/a2_speed_rows.csv')} (git); "
            "generated by <code>tools/a2_workload.py</code>.</p>")
    render(page(eyebrow, body), OUT / "Group09_A2_speed_test_rows.pdf")
    print("wrote", OUT / "Group09_A2_speed_test_rows.pdf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
