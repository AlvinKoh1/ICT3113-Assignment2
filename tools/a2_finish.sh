#!/usr/bin/env bash
# Everything after the measurements, in one command (any machine with Python).
# Run it once Irfan and Uwais have pushed the speed test.
#
#   git pull && tools/a2_finish.sh
#
#   1. speed analysis              -> results/a2/speed/summary.md
#   2. accuracy-file check         -> docs/a2/accuracy_notes.md
#   3. prediction account          -> docs/a2/prediction_account.md, deck/a2_text.json
#   4. deck                        -> deck/Group09_A2.pptx
#   5. raw-file cross-check        -> results/a2/crosscheck.md (also checks the deck has nothing PENDING)
# Then read the three .md files and the deck, and commit.
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null || PY=python
"$PY" -c "import pptx, matplotlib" 2>/dev/null || "$PY" -m pip install -q python-pptx matplotlib
export PYTHONIOENCODING=utf-8
status=0
step() { echo; echo "=== $1"; shift; "$@" || { echo "!!! $1 reported a problem (see above)"; status=1; }; }
step "1/5 speed analysis"       "$PY" tools/a2_analyze_speed.py
step "2/5 accuracy-file check"  "$PY" tools/a2_verify_accuracy.py
step "3/5 prediction account"   "$PY" tools/a2_prediction_account.py
step "4/5 deck"                 "$PY" deck/build_deck_a2.py
step "5/5 raw-file cross-check" "$PY" tools/a2_crosscheck.py
echo
if [ $status = 0 ]; then
  echo "DONE. Read docs/a2/accuracy_notes.md, docs/a2/prediction_account.md, results/a2/crosscheck.md and the deck, then:"
  echo "  git add results/a2 docs/a2 deck && git commit -m \"A2 analysis, prediction account and deck\" && git push"
else
  echo "Finished WITH PROBLEMS. Fix what is flagged above (or explain it in results/a2/reconcile_notes.md) before submitting."
fi
exit $status
