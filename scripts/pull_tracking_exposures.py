"""Pull player-season tracking exposure counts (drives, paint touches,
post touches) for the style-adjusted baseline. Exposure COUNTS only;
the player's own FT outcomes from these endpoints are deliberately not
used as features anywhere.

Writes table tracking_exposures(player_id, season, drives, paint_touches,
post_touches, gp).
"""
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from config import DB_PATH, SEASONS  # noqa: E402

from nba_api.stats.endpoints import leaguedashptstats  # noqa: E402


def pull(measure: str, season: str) -> pd.DataFrame:
    for attempt in range(3):
        try:
            df = leaguedashptstats.LeagueDashPtStats(
                season=season,
                pt_measure_type=measure,
                per_mode_simple="Totals",
                player_or_team="Player",
                timeout=60,
            ).get_data_frames()[0]
            time.sleep(0.8)
            return df
        except Exception:  # noqa: BLE001
            if attempt == 2:
                raise
            time.sleep(3)
    raise RuntimeError("unreachable")


def main() -> None:
    frames = []
    for season in SEASONS:
        drives = pull("Drives", season)[["PLAYER_ID", "GP", "DRIVES"]]
        paint = pull("PaintTouch", season)[["PLAYER_ID", "PAINT_TOUCHES"]]
        post = pull("PostTouch", season)[["PLAYER_ID", "POST_TOUCHES"]]
        df = drives.merge(paint, on="PLAYER_ID", how="outer").merge(
            post, on="PLAYER_ID", how="outer"
        )
        df["season"] = season
        frames.append(df)
        print(f"{season}: {len(df)} players")
    out = pd.concat(frames, ignore_index=True).fillna(0)
    out = out.rename(
        columns={
            "PLAYER_ID": "player_id",
            "GP": "gp",
            "DRIVES": "drives",
            "PAINT_TOUCHES": "paint_touches",
            "POST_TOUCHES": "post_touches",
        }
    )
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS tracking_exposures")
    out.to_sql("tracking_exposures", conn, if_exists="replace", index=False)
    conn.execute(
        "CREATE INDEX idx_te ON tracking_exposures(player_id, season)"
    )
    conn.commit()
    print(f"tracking_exposures: {len(out)} rows across {len(SEASONS)} seasons")


if __name__ == "__main__":
    main()
