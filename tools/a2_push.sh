#!/usr/bin/env bash
# Commit the given paths and push, retrying through a pull --rebase if the other
# machine pushed in the meantime (the two machines write different files).
#   tools/a2_push.sh "<message>" <path>...
MSG="$1"; shift
cd "$(dirname "$0")/.."
git add -- "$@" 2>/dev/null
git diff --cached --quiet && { echo "(nothing new to commit for: $MSG)"; exit 0; }
git commit -q -m "$MSG" || exit 1
for i in 1 2 3 4 5 6; do
  git pull -q --rebase && git push -q && { echo "pushed: $MSG"; exit 0; }
  echo "push attempt $i failed; retrying in 30 s"; sleep 30
done
echo "COULD NOT PUSH: $MSG -- the commit is kept locally; run 'git pull --rebase && git push' later."
exit 1
