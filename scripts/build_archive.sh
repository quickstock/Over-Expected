#!/bin/bash
# Build the NBA archive (1997-98 to 2019-20) into xfta_archive.db and export it
# to site/public-archive/, with the same scripts the Monday job runs on the
# live window. A one-off: the Monday job never rebuilds the archive. Rerun it
# after changing a model, or after scripts/pull_archive.sh fills a gap.
#
# Base lenses only (decided 2026-10-22): the layers extend back once the
# play-by-play-only stints have passed their own gate.
#
#   scripts/build_archive.sh                 every step
#   scripts/build_archive.sh "train xFTA"    resume from a named step
set -eu
cd "$(dirname "$0")/.."
export OE_ERA=archive
PY="/opt/homebrew/bin/python3.9"
FROM="${1:-}"
step() {
  if [ -n "$FROM" ] && [ "$1" != "$FROM" ]; then echo "--- $1 (skipped)"; return; fi
  FROM=""
  echo "--- $1 $(date '+%H:%M:%S')"; shift; "$@"
}
step "build tables"        $PY build_tables.py
step "game meta"           $PY scripts/pull_game_meta.py
step "tracking exposures"  $PY scripts/pull_tracking_exposures.py
step "possessions"         $PY build_possessions_v3.py
step "possession target"   $PY build_possession_target_v3.py
step "training features"   $PY build_training_possessions_v2.py
step "score margin"        $PY backfill_score_margin.py
step "train xFTA"          $PY train_possession_v4_context.py
step "diet expectation"    $PY build_diet_expected.py
step "FTAOE board"         $PY build_possession_leaderboard_clean.py
step "style baseline"      $PY build_style_adjusted.py
step "player FT%"          $PY build_player_ft.py
step "shot value"          $PY shot_value.py
step "per-shot xFG"        $PY build_shots_xfg.py
step "export"              $PY export_site_data.py
step "EXPORT GATE"         $PY scripts/validate_export.py
step "shot sample"         $PY export_shots.py
step "game pages"          $PY export_games.py
echo "=== archive built $(date '+%H:%M:%S')"
