#!/usr/bin/env python3
"""Render docs/a2/TEAM_GUIDE.html to TEAM_GUIDE.pdf with real page numbers in the contents.

Two passes with headless Chrome: render with placeholder numbers, find the page
each heading lands on (PyMuPDF), fill the numbers in, render again.

    pip install pymupdf
    python docs/a2/build_team_guide.py [path-to-chrome]
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
SRC, OUT = HERE / "TEAM_GUIDE.html", HERE / "TEAM_GUIDE.pdf"
CHROME = sys.argv[1] if len(sys.argv) > 1 else r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def render(html: str, pdf: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=HERE, delete=False, encoding="utf-8") as fh:
        fh.write(html)
        tmp = Path(fh.name)
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        "--virtual-time-budget=10000", f"--print-to-pdf={pdf}", tmp.as_uri()],
                       check=True, capture_output=True)
    finally:
        tmp.unlink(missing_ok=True)


def main() -> int:
    html = SRC.read_text(encoding="utf-8")
    keys = re.findall(r"\{\{p:(\w+)\}\}", html)
    heads = {}
    for k in keys:
        m = re.search(rf'id="{k}"[^>]*>(.*?)</h[12]>', html, re.S)
        heads[k] = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    render(re.sub(r"\{\{p:\w+\}\}", "00", html), OUT)

    doc = pymupdf.open(OUT)
    lines = [[ln.strip() for ln in page.get_text().splitlines()] for page in doc]
    pages = {}
    for k, title in heads.items():
        hit = next((i + 1 for i, ls in enumerate(lines) if i >= 2 and title in ls), None)
        if hit is None:
            raise SystemExit(f"heading not found in PDF: {title!r}")
        pages[k] = hit
    doc.close()
    render(re.sub(r"\{\{p:(\w+)\}\}", lambda m: str(pages[m.group(1)]), html), OUT)
    print(f"wrote {OUT.name}: " + ", ".join(f"{k}={v}" for k, v in pages.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
