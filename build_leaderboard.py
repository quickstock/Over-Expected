"""xFTA Phase 2 — Build predictions table and player-season leaderboard.

Reads cross-fit predictions from model_artifacts/cross_fit_predictions.csv,
writes predictions table and player_season_xfta to xfta.db, and adds xfta
column to training_fga.
"""

import sqlite3

import numpy as np
import pandas as pd

from config import DB_PATH

PREDICTIONS_PATH = "model_artifacts/cross_fit_predictions.csv"


def build_predictions():
    """Load cross-fit predictions, write to DB."""
    preds = pd.read_csv(PREDICTIONS_PATH)
    conn = sqlite3.connect(DB_PATH)

    # Normalize game_id: stored in DB as text with leading zeros ("0022200001"),
    # but CSV round-trip may have stripped them. Pad to 10 chars.
    preds["game_id"] = preds["game_id"].astype(str).str.zfill(10)

    # Write predictions table (game_id, event_id, xfta)
    preds_table = preds[["game_id", "event_id", "xfta"]].copy()
    preds_table.to_sql("predictions", conn, if_exists="replace", index=False)
    print(f"predictions table: {len(preds_table):,} rows")

    # Add xfta column to training_fga
    # Drop any stale xfta columns from prior runs
    training = pd.read_sql("SELECT * FROM training_fga", conn)
    stale = [c for c in training.columns if c.startswith("xfta") and c != "xfta_from_shot"]
    training = training.drop(columns=stale, errors="ignore")

    # Merge xfta onto training_fga (coerce types for merge)
    training["game_id"] = training["game_id"].astype(str).str.zfill(10)
    preds["game_id"] = preds["game_id"].astype(str).str.zfill(10)
    training["event_id"] = training["event_id"].astype(int)
    preds["event_id"] = preds["event_id"].astype(int)
    merged = training.merge(
        preds[["game_id", "event_id", "xfta"]],
        on=["game_id", "event_id"],
        how="left",
    )
    # Overwrite training_fga with xfta column added
    merged.to_sql("training_fga", conn, if_exists="replace", index=False)
    print(f"training_fga: added xfta column ({merged['xfta'].notna().sum():,} matched)")

    # Build player_season_xfta
    player = pd.read_sql("SELECT player_id, player_name, season, possessions FROM player_season", conn)

    lb = preds.merge(player, on=["player_id", "season"], how="left")

    leaderboard = (
        lb.groupby(["player_id", "season"])
        .agg(
            player_name=("player_name", "first"),
            fga=("fta_from_shot", "count"),
            actual_fta_from_fouls=("fta_from_shot", "sum"),
            xfta_total=("xfta", "sum"),
        )
        .reset_index()
    )

    leaderboard["ftaoe"] = leaderboard["actual_fta_from_fouls"] - leaderboard["xfta_total"]
    leaderboard["ftaoe_per_100_fga"] = leaderboard["ftaoe"] / leaderboard["fga"] * 100

    # Center per season
    season_means = leaderboard.groupby("season")["ftaoe"].mean()
    leaderboard["ftaoe_centered"] = leaderboard.apply(
        lambda r: r["ftaoe"] - season_means[r["season"]], axis=1
    )

    # Per-100 possessions (where available)
    leaderboard = leaderboard.merge(
        player[["player_id", "season", "possessions"]],
        on=["player_id", "season"],
        how="left",
    )
    leaderboard["ftaoe_per_100_poss"] = np.where(
        leaderboard["possessions"].notna() & (leaderboard["possessions"] > 0),
        leaderboard["ftaoe"] / leaderboard["possessions"] * 100,
        np.nan,
    )

    # Reorder columns
    leaderboard = leaderboard[[
        "player_id", "player_name", "season", "fga",
        "actual_fta_from_fouls", "xfta_total", "ftaoe",
        "ftaoe_centered", "ftaoe_per_100_fga", "ftaoe_per_100_poss",
        "possessions",
    ]]

    leaderboard.to_sql("player_season_xfta", conn, if_exists="replace", index=False)
    print(f"player_season_xfta: {len(leaderboard):,} rows")

    conn.close()
    return leaderboard


if __name__ == "__main__":
    lb = build_predictions()

    # Print top-30 leaderboard
    top = lb[lb["fga"] >= 100].sort_values("ftaoe_per_100_fga", ascending=False).head(30)
    print("\nLEADERBOARD TOP-30 (min 100 FGA, by FTAOE per 100 FGA)")
    print(top[["player_name", "season", "fga", "actual_fta_from_fouls", "xfta_total",
               "ftaoe", "ftaoe_centered", "ftaoe_per_100_fga"]].to_string(index=False))

    # Print season centering stats
    print("\nSEASON CENTERING (mean FTAOE per shot):")
    for season in sorted(lb["season"].unique()):
        mean = lb[lb["season"] == season]["ftaoe"].mean()
        n = len(lb[lb["season"] == season])
        print(f"  {season}: {mean:+.6f} (n={n:,})")