"""Weekly-update gatekeeper: fetch a FRESH game list for the current
season (bypassing and refreshing the parquet cache that pull.py reads),
compare against cached play-by-play, print the number of new games.

Prints a single integer. 0 = nothing to do.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from config import CACHE_DIR, SEASONS  # noqa: E402

from nba_api.stats.endpoints import leaguegamefinder  # noqa: E402

season = SEASONS[-1]

for attempt in range(3):
    try:
        lgf = leaguegamefinder.LeagueGameFinder(
            season_nullable=season,
            season_type_nullable="Regular Season",
            timeout=60,
        )
        df = lgf.get_data_frames()[0]
        break
    except Exception:  # noqa: BLE001
        if attempt == 2:
            raise
        time.sleep(5)

games = df[["GAME_ID", "GAME_DATE"]].drop_duplicates()
games = games.sort_values("GAME_DATE").reset_index(drop=True)

# Refresh the cache pull.py consumes, otherwise it never sees new games.
out = ROOT / CACHE_DIR / "seasons" / f"games_{season}.parquet"
out.parent.mkdir(parents=True, exist_ok=True)
games.to_parquet(out, index=False)

pbp_dir = ROOT / CACHE_DIR / "pbp"
cached = {p.stem for p in pbp_dir.glob("*.parquet")} if pbp_dir.exists() else set()
new = sum(1 for gid in games["GAME_ID"] if str(gid) not in cached)
print(new)
