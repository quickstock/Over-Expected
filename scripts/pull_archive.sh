#!/bin/bash
# One-off pull of the archive seasons (1997-98 to 2019-20), oldest first, for
# the historical backfill. pull.py caches finished seasons permanently, so this
# resumes where it stopped if rerun. Runs detached under caffeinate; keep the
# lid open (nothing holds off clamshell sleep on battery).
#
#   scripts/pull_archive.sh [FIRST_START_YEAR] [LAST_START_YEAR]
set -u
cd "$(dirname "$0")/.."
PY="/opt/homebrew/bin/python3.9"
FIRST="${1:-1997}"
LAST="${2:-2019}"
for y in $(seq "$FIRST" "$LAST"); do
  season="$y-$(printf '%02d' $(( (y + 1) % 100 )))"
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') $season"
  $PY pull.py --season "$season" || echo "WARNING: $season pull exited non-zero; rerun to resume"
  $PY scripts/pull_game_meta.py --season "$season" || echo "WARNING: $season game meta incomplete; rerun to resume"
done
echo "=== $(date '+%Y-%m-%d %H:%M:%S') archive pull done"
