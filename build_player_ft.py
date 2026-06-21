"""build_player_ft.py — per-player-season free-throw conversion.

Pulls FTM/FTA/FT_PCT from LeagueDashPlayerStats (Totals) for every configured
season and writes `player_season_ft`. The shot-value suite uses each player's
own FT% to value the free throws his shooting fouls actually generate, instead
of a flat league rate — so a 65% Giannis and a 90% guard get credited for the
points they really bank at the line.

Network-only; run when seasons refresh. Safe to re-run (replaces the table).
"""
import sqlite3
import time

import pandas as pd
from nba_api.stats.endpoints import leaguedashplayerstats

from config import SEASONS, DB_PATH


def fetch_season(season: str) -> pd.DataFrame:
    df = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season, timeout=60, per_mode_detailed="Totals"
    ).get_data_frames()[0]
    out = df[["PLAYER_ID", "PLAYER_NAME", "FTM", "FTA", "FT_PCT"]].copy()
    out.columns = ["player_id", "player_name", "ftm", "fta", "ft_pct"]
    out["season"] = season
    return out


def main() -> None:
    frames = []
    for s in SEASONS:
        t0 = time.monotonic()
        f = fetch_season(s)
        frames.append(f)
        print(f"  {s}: {len(f):,} players ({time.monotonic() - t0:.0f}s)")
    ft = pd.concat(frames, ignore_index=True)
    ft["player_id"] = ft["player_id"].astype(int)

    conn = sqlite3.connect(DB_PATH)
    ft[["player_id", "player_name", "season", "ftm", "fta", "ft_pct"]].to_sql(
        "player_season_ft", conn, if_exists="replace", index=False
    )
    conn.close()
    print(f"\nwrote player_season_ft: {len(ft):,} player-seasons")


if __name__ == "__main__":
    main()
