"""Shared helpers for the Assignment 2 tools (stdlib only).

Everything that scores, splits or checks limits goes through here so every
script, and the deck, uses the same definitions.
"""
from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path

csv.field_size_limit(10 ** 9)

ROOT = Path(__file__).resolve().parents[1]
# A2_RESULTS lets a dry run write somewhere other than the evidence folder.
A2 = Path(os.getenv("A2_RESULTS", str(ROOT / "results" / "a2")))
DOCS_A2 = ROOT / "docs" / "a2"
# Generated write-ups (accuracy notes, prediction account, deck text) can be redirected for dry runs.
DOCS_OUT = Path(os.getenv("A2_DOCS_OUT", str(DOCS_A2)))
DECK_TEXT = Path(os.getenv("A2_DECK_TEXT", str(ROOT / "deck" / "a2_text.json")))
A2_LOG = Path(os.getenv("A2_LOG", str(ROOT / "results" / "logs" / "a2_requests.jsonl")))

CATS = ["Credit reporting", "Debt collection", "Mortgage", "Credit card",
        "Bank account or service", "Consumer loan", "Money transfer or service"]
SHORT = dict(zip(CATS, ["CredRep", "DebtCol", "Mortg", "CCard", "BankAcct", "ConsLoan", "MoneyTx"]))
UNPARSED = "UNPARSED"
MODELS = ["qwen2.5:0.5b", "llama3.2:1b", "llama3.2:3b", "qwen2.5:7b"]
TOP_MODEL = "qwen2.5:7b"          # most accurate Assignment 1 model (73.1 % on the full golden set)

OVERALL_MARGIN_PTS = 10.0         # brief, Step 1
CATEGORY_MARGIN_PTS = 15.0        # brief, Step 1
# A category is flagged "too small for a fair test" when two tickets are worth
# more than the 15-point margin, i.e. n <= 13 (2/13 = 15.4 points).
SMALL_CATEGORY_N = 13


def safe(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


def read_csv(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows: list[dict]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def jdump(path, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def jload(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def golden() -> dict[str, dict]:
    """row -> {label, narrative} from the frozen Assignment 1 golden set."""
    return {r["row"]: r for r in read_csv(ROOT / "golden" / "golden_set.csv")}


def split_rows(which: str) -> list[str]:
    """Row ids of the 'tune' or 'test' half, in row order (golden/a2_split.csv)."""
    assert which in ("tune", "test")
    return [r["row"] for r in read_csv(ROOT / "golden" / "a2_split.csv") if r["set"] == which]


def a1_predictions(model: str) -> dict[str, dict]:
    """Assignment 1 accuracy-run records for one model, keyed by row."""
    return {r["row"]: r for r in read_csv(ROOT / "results" / "accuracy" / f"predictions_{safe(model)}.csv")}


def score(pred: dict[str, str], rows: list[str], gold: dict[str, dict] | None = None) -> dict:
    """Overall + per-category accuracy (recall) with counts, and a confusion matrix.

    pred: row -> predicted category (ERROR / UNPARSED count as wrong).
    """
    gold = gold or golden()
    n = len(rows)
    correct = sum(1 for r in rows if pred.get(r) == gold[r]["label"])
    per = {}
    for c in CATS:
        rs = [r for r in rows if gold[r]["label"] == c]
        k = sum(1 for r in rs if pred.get(r) == c)
        per[c] = {"correct": k, "n": len(rs), "acc": k / len(rs) if rs else None}
    labels = CATS + [UNPARSED, "ERROR"]
    cm = {g: {p: 0 for p in labels} for g in CATS}
    for r in rows:
        p = pred.get(r, "ERROR")
        cm[gold[r]["label"]][p if p in labels else UNPARSED] += 1
    return {"correct": correct, "n": n, "acc": correct / n if n else None,
            "per_category": per, "confusion": cm,
            "unparsed": sum(1 for r in rows if pred.get(r) == UNPARSED),
            "errors": sum(1 for r in rows if pred.get(r, "ERROR") == "ERROR")}


def check_limits(sc: dict, limits: dict) -> dict:
    """Pass/fail of a scored configuration against the Step 1 limits."""
    overall_ok = sc["acc"] * 100 >= limits["overall_limit_pct"] - 1e-9
    cats = {}
    for c in CATS:
        lim = limits["category_limit_pct"][c]
        acc = sc["per_category"][c]["acc"] * 100
        cats[c] = {"acc_pct": acc, "limit_pct": lim, "pass": acc >= lim - 1e-9,
                   "gap_pts": acc - limits["top_category_pct"][c]}
    return {"overall_pass": overall_ok, "category_pass": all(v["pass"] for v in cats.values()),
            "pass": overall_ok and all(v["pass"] for v in cats.values()), "categories": cats,
            "failed_categories": [c for c, v in cats.items() if not v["pass"]]}


def pct(values, p):
    """Linear-interpolated percentile (same definition as Assignment 1's analyze_jtl.py)."""
    s = sorted(values)
    if not s:
        return None
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def iter_log(path):
    """Yield JSON records from a service log (results/a2/logs/requests.jsonl)."""
    p = Path(path)
    if not p.exists():
        return
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
