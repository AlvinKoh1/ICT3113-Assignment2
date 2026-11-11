#!/usr/bin/env bash
# Commit the given paths and push, retrying through a pull if the other machine
# pushed in the meantime.
#   tools/a2_push.sh "<message>" <path>...
# * Merge, not rebase: the two machines write different files, so a merge never
#   touches anything this machine is still writing (the service log, this script's
#   own progress log). A rebase has to rewrite the working tree and fails when a
#   file changes under it -- found in the end-to-end rehearsal.
# * Paths that do not exist yet are skipped (git add would otherwise stage nothing).
# * Also pushes any earlier commit that failed to push (e.g. after a network blip).
MSG="$1"; shift
cd "$(dirname "$0")/.."
for p in "$@"; do [ -e "$p" ] && git add -- "$p"; done
if git diff --cached --quiet; then
  echo "(nothing new to commit for: $MSG)"
else
  git commit -q -m "$MSG" || { echo "COMMIT FAILED: $MSG"; exit 1; }
fi
for i in 1 2 3 4 5 6; do
  git fetch -q && [ -z "$(git log --oneline '@{u}..HEAD' 2>/dev/null)" ] && { echo "up to date: $MSG"; exit 0; }
  git pull -q --no-rebase --no-edit && git push -q && { echo "pushed: $MSG"; exit 0; }
  echo "push attempt $i failed; retrying in 30 s"; sleep 30
done
echo "COULD NOT PUSH: $MSG -- the commit is kept locally; run 'git pull --no-rebase && git push' later."
exit 1
