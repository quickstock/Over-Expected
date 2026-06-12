#!/bin/bash
# FTAOE weekly self-update: pull new games, rebuild everything, deploy
# only if the validation gate passes, email on any failure. Designed to
# run unattended for years; exits in seconds when there is nothing new
# (all offseason, and any week without new games).
set -u
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p "$ROOT/logs"
exec >> "$ROOT/logs/weekly.log" 2>&1

echo ""
echo "=== $(date '+%Y-%m-%d %H:%M:%S') weekly update ==="

LOCK="/tmp/ftaoe_weekly.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "another run in progress; exiting"
  exit 0
fi
trap 'rmdir "$LOCK"' EXIT

PY="python3"
SEASON="$($PY -c 'from config import SEASONS; print(SEASONS[-1])')"
echo "current season: $SEASON"

notify_fail() {
  curl -s -X POST "https://formsubmit.co/ajax/kevinkrajnc@gmail.com" \
    -H "Content-Type: application/json" \
    -d "{\"_subject\":\"FTAOE weekly update FAILED\",\"message\":\"Step failed: $1 (season $SEASON, $(date '+%Y-%m-%d %H:%M')). The site was NOT redeployed; it keeps serving the last good build. Check logs/weekly.log on $(hostname).\"}" \
    > /dev/null || true
}

run() {
  local name="$1"; shift
  echo "--- $name $(date '+%H:%M:%S')"
  if ! "$@"; then
    echo "FAILED: $name"
    notify_fail "$name"
    exit 1
  fi
}

# Gatekeeper: refreshes the game-list cache and counts un-pulled games.
NEW="$($PY scripts/check_new_games.py)" || { notify_fail "check_new_games"; exit 1; }
echo "new completed games: $NEW"
if [ "${NEW:-0}" = "0" ] && [ "${1:-}" != "--force" ]; then
  echo "nothing to do"
  exit 0
fi

run "pull pbp+shots"     $PY pull.py --season "$SEASON"
run "build tables"       $PY build_tables.py
run "pull game meta"     $PY scripts/pull_game_meta.py
run "pull tracking"      $PY scripts/pull_tracking_exposures.py
run "build possessions"  $PY build_possessions_v3.py
run "build target"       $PY build_possession_target_v3.py
run "training features"  $PY build_training_possessions_v2.py
run "train v4"           $PY train_possession_v4_context.py
run "leaderboard"        $PY build_possession_leaderboard_clean.py
run "style baseline"     $PY build_style_adjusted.py
run "export"             $PY export_site_data.py
run "VALIDATION GATE"    $PY scripts/validate_export.py
run "deploy"             bash -c "cd site && vercel deploy --prod --yes"

# Keep the data history in git (non-fatal if the push fails).
git add site/public > /dev/null 2>&1
if ! git diff --cached --quiet; then
  git commit -m "data: weekly update $(date '+%Y-%m-%d')" > /dev/null \
    && git push origin HEAD > /dev/null 2>&1 \
    || echo "git push failed (non-fatal)"
fi

echo "=== done $(date '+%H:%M:%S') ==="
