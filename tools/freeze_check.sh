#!/usr/bin/env bash
# Pre-flight for the Step 4 -> Step 5 gate.
#
# Step 5 cannot begin until the golden set and the prediction record are
# committed. This checks the things that are checkable; the rest is on you.
set -uo pipefail
cd "$(dirname "$0")/.."

FAIL=0
ok()   { echo "  [ok]   $1"; }
bad()  { echo "  [FAIL] $1"; FAIL=1; }
warn() { echo "  [warn] $1"; }

echo "Freeze pre-flight"
echo

echo "Golden set:"
if [ -f golden/golden_set.csv ]; then
  N=$(( $(wc -l < golden/golden_set.csv) - 1 ))
  if [ "$N" -ge 150 ] && [ "$N" -le 200 ]; then ok "$N tickets (150-200 required)"
  else bad "$N tickets -- brief requires 150-200"; fi
else bad "golden/golden_set.csv missing -- run 'make merge'"; fi

echo
echo "Independent labelling:"
SHEETS=$(ls golden/labels_*.csv 2>/dev/null | wc -l | tr -d ' ')
if [ "$SHEETS" -ge 2 ]; then ok "$SHEETS annotator sheets present"
else bad "found $SHEETS label sheet(s); at least two annotators must label every ticket"; fi

for f in golden/labels_*.csv; do
  [ -e "$f" ] || continue
  BLANK=$(python3 - "$f" <<'PY'
import csv,sys
csv.field_size_limit(10**9)
rows=list(csv.DictReader(open(sys.argv[1],newline='',encoding='utf-8')))
print(sum(1 for r in rows if not (r.get('label') or '').strip()))
PY
)
  if [ "$BLANK" = "0" ]; then ok "$(basename "$f"): fully labelled"
  else bad "$(basename "$f"): $BLANK unlabelled row(s)"; fi
done

echo
echo "Adjudication:"
if [ -f golden/disagreements.csv ]; then
  UNRES=$(python3 - <<'PY'
import csv
csv.field_size_limit(10**9)
rows=list(csv.DictReader(open('golden/disagreements.csv',newline='',encoding='utf-8')))
print(len(rows), sum(1 for r in rows if not (r.get('adjudicated_label') or '').strip()),
      sum(1 for r in rows if not (r.get('resolution_note') or '').strip()))
PY
)
  set -- $UNRES
  TOTAL=$1; NOLABEL=$2; NONOTE=$3
  if [ "$TOTAL" = "0" ]; then
    warn "zero disagreements recorded -- the brief says a golden set with implausibly perfect agreement will be examined closely"
  else
    ok "$TOTAL disagreement(s) recorded"
    [ "$NOLABEL" = "0" ] && ok "all adjudicated" || bad "$NOLABEL without an adjudicated label"
    [ "$NONOTE"  = "0" ] && ok "all have resolution notes" || bad "$NONOTE without a resolution note"
  fi
else bad "golden/disagreements.csv missing -- run 'make agree'"; fi

echo
echo "Protocol:"
if [ -f golden/labelling_protocol.md ]; then
  grep -q "<DATE>" golden/labelling_protocol.md \
    && bad "revision history still has <DATE> placeholders" \
    || ok "revision history filled in"
else bad "golden/labelling_protocol.md missing"; fi

echo
echo "Prediction record:"
if [ -f docs/prediction_record.md ]; then
  BLANKS=$(grep -c "____" docs/prediction_record.md || true)
  PLACE=$(grep -c "<\.\.\.>" docs/prediction_record.md || true)
  if [ "$BLANKS" -eq 0 ] && [ "$PLACE" -eq 0 ]; then ok "no placeholders left"
  else bad "$BLANKS numeric blank(s) and $PLACE placeholder(s) remain -- a vague prediction earns nothing"; fi
else bad "docs/prediction_record.md missing"; fi

echo
echo "Git freeze:"
if git rev-parse --git-dir >/dev/null 2>&1; then
  for f in golden/golden_set.csv docs/prediction_record.md; do
    if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
      if git diff --quiet HEAD -- "$f" 2>/dev/null; then ok "$f committed and clean"
      else bad "$f has uncommitted changes"; fi
    else bad "$f is not committed"; fi
  done
else bad "not a git repository"; fi

echo
echo "No model has seen the golden set:"
if ls results/accuracy/predictions_*.csv >/dev/null 2>&1; then
  warn "results/accuracy/ already contains predictions. If these predate the freeze, the golden set is contaminated."
else ok "no accuracy results present yet"; fi

echo
if [ "$FAIL" = "0" ]; then
  echo "READY TO FREEZE."
  echo "  git add golden/ docs/prediction_record.md docs/model_pins.md"
  echo "  git commit -m 'Freeze golden test set and prediction record (pre-benchmark)'"
  echo "  git push"
  echo "Then, and only then, begin Step 5."
else
  echo "NOT READY -- fix the [FAIL] items above."
fi
exit $FAIL
