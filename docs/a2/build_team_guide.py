#!/usr/bin/env python3
"""Render docs/a2/TEAM_GUIDE.html to TEAM_GUIDE.pdf (A4) with headless Chrome.

Same design as docs/remaining_work.html -> docs/REMAINING_WORK.pdf from Assignment 1:
the <head> (CSS, fonts, print rules) is copied from it unchanged.

    python docs/a2/build_team_guide.py [path-to-chrome]
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHROME = sys.argv[1] if len(sys.argv) > 1 else r"C:\Program Files\Google\Chrome\Application\chrome.exe"
subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=10000",
                f"--print-to-pdf={HERE / 'TEAM_GUIDE.pdf'}", (HERE / "TEAM_GUIDE.html").as_uri()],
               check=True, capture_output=True)
print("wrote", HERE / "TEAM_GUIDE.pdf")
