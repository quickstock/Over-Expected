"""Correct training_fga.fta_from_shot using basketball-reference season totals.

For each player-season:
  - Compute PBP-derived FTA total from training_fga.
  - Compare to actual_fta_from_fouls in player_season_xfta (BR sourced).
  - If PBP total > 0: scale every shot's fta_from_shot linearly.
  - If PBP total == 0 but actual > 0: distribute actual FTA uniformly across shots.

Writes the full table back via pandas to_sql for speed.
"""

import sqlite3
import pandas as pd
import numpy as np
from config import DB_PATH


def fix_training_targets():
    conn = sqlite3.connect(DB_PATH)

    # Load full training_fga
    print("Loading training_fga...")
    tf = pd.read_sql("SELECT * FROM training_fga", conn)
    print(f"  {len(tf):,} rows loaded")

    # PBP totals per player-season
    pbp_totals = (
        tf.groupby(["player_id", "season"])
        .agg(pbp_fta=("fta_from_shot", "sum"), fga=("fta_from_shot", "count"))
        .reset_index()
    )

    # BR actual totals
    psx = pd.read_sql(
        "SELECT player_id, season, actual_fta_from_fouls FROM player_season_xfta",
        conn,
    )

    # Merge
    merged = pbp_totals.merge(psx, on=["player_id", "season"], how="left")
    merged["actual_fta_from_fouls"] = merged["actual_fta_from_fouls"].fillna(0)

    # Compute per-player-season scale factor
    merged["scale"] = np.where(
        merged["pbp_fta"] > 0,
        merged["actual_fta_from_fouls"] / merged["pbp_fta"],
        np.where(
            merged["actual_fta_from_fouls"] > 0,
            merged["actual_fta_from_fouls"] / merged["fga"],
            1.0,
        ),
    )

    # Map to training_fga via merge
    tf = tf.merge(
        merged[["player_id", "season", "scale"]],
        on=["player_id", "season"],
        how="left",
    )
    tf["scale"] = tf["scale"].fillna(1.0)

    # Apply correction
    print("Applying correction...")
    tf["fta_from_shot"] = tf["fta_from_shot"] * tf["scale"]

    # Drop helper
    tf = tf.drop(columns=["scale"])

    # Summary
    before = pbp_totals["pbp_fta"].sum()
    after = tf["fta_from_shot"].sum()
    print(f"  Total FTA before: {before:,.0f}")
    print(f"  Total FTA after:  {after:,.0f}")
    scaled = (merged["pbp_fta"] > 0).sum()
    uniform = ((merged["pbp_fta"] == 0) & (merged["actual_fta_from_fouls"] > 0)).sum()
    print(f"  Player-seasons scaled: {scaled}")
    print(f"  Player-seasons with zero PBP but positive actual: {uniform}")

    # Write back — replace entire table (pandas to_sql is fast enough for ~600k rows)
    print("Writing back to database...")
    tf.to_sql("training_fga", conn, if_exists="replace", index=False)
    print("Done.")
    conn.close()


if __name__ == "__main__":
    fix_training_targets()
