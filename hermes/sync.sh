#!/bin/bash
# j-space upstream sync + Hermes build/deploy (cron no_agent job).
# Zero output + exit 0 = already current (silent). Output = change summary (delivered).
# Non-zero = error.
set -euo pipefail

REPO="$HOME/code/j-space-cognition-suite"
cd "$REPO"

# --- fetch upstream --------------------------------------------------------
git fetch origin main --quiet 2>/dev/null || { echo "ERROR: git fetch failed"; exit 1; }

# --- quick path: already current AND built at current HEAD -----------------
LOCAL=$(git rev-parse --short HEAD)
META_UPSTREAM=""
if [ -f hermes/out/j-space/.build-meta.json ]; then
  META_UPSTREAM=$(python3 -c "import json;print(json.load(open('hermes/out/j-space/.build-meta.json'))['upstream_commit'])" 2>/dev/null || true)
fi
if git merge-base --is-ancestor origin/main HEAD && [ "$META_UPSTREAM" = "$LOCAL" ]; then
  exit 0   # silent: nothing changed since last build
fi

# --- rebase our local hermes/ adaptation onto upstream main (if needed) ----
PRE_UPSTREAM=$(git rev-parse --short origin/main)
if ! git merge-base --is-ancestor origin/main HEAD; then
  if ! git rebase origin/main; then
    git rebase --abort
    echo "ERROR: rebase conflict on j-space upstream update. Manual resolution needed:"
    echo "  cd $REPO && git rebase origin/main"
    exit 1
  fi
fi
NEW_SHA=$(git rev-parse --short HEAD)

# --- build Hermes layout ---------------------------------------------------
BUILD_OUT=$(python3 hermes/build_hermes_skill.py)
echo "$BUILD_OUT"

# --- verify built skill ----------------------------------------------------
if ! python3 hermes/out/j-space/scripts/verify_suite_hermes.py >/dev/null 2>&1; then
  echo "ERROR: verify_suite_hermes.py failed after build — inspect $REPO/hermes/out/j-space"
  exit 1
fi

# --- deployed via symlink ~/.hermes/skills/j-space -> hermes/out/j-space ----
LINK="$HOME/.hermes/skills/j-space"
if [ -L "$LINK" ]; then
  TARGET=$(readlink "$LINK" || true)
  if [ "$TARGET" = "$REPO/hermes/out/j-space" ]; then
    echo "deployed: skill symlink content refreshed (upstream $PRE_UPSTREAM -> $NEW_SHA)"
  else
    echo "WARN: $LINK points to $TARGET not the build output; check manually"
  fi
else
  echo "WARN: $LINK is not a symlink to the build output; deploy manually:"
  echo "  mv $LINK $LINK.bak && ln -s $REPO/hermes/out/j-space $LINK"
fi
echo "note: new skill content takes effect in the NEXT Hermes session (loader caches at session start)."
