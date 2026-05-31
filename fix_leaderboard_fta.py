"""Fix player_season_xfta actual FTA using basketball-reference data."""

import sqlite3
import pandas as pd
from basketball_reference_web_scraper import client
from config import DB_PATH


def fetch_br_fta(season_end_year: int) -> pd.DataFrame:
    """Fetch player season totals from basketball-reference."""
    stats = client.players_season_totals(season_end_year=season_end_year)
    df = pd.DataFrame(stats)
    df["name"] = df["name"].str.strip()
    df["attempted_free_throws"] = df["attempted_free_throws"].astype(int)
    # Keep only name and FTA, aggregate in case of duplicates (player traded)
    return df.groupby("name", as_index=False)["attempted_free_throws"].sum()


def fix_leaderboard():
    conn = sqlite3.connect(DB_PATH)

    # Map our seasons to basketball-reference season_end_year
    season_map = {
        "2022-23": 2023,
        "2023-24": 2024,
        "2024-25": 2025,
    }

    # Load current player_season_xfta
    psx = pd.read_sql("SELECT * FROM player_season_xfta", conn)

    # For each season, fetch BR data and merge
    for our_season, br_year in season_map.items():
        print(f"Fetching BR data for {our_season} (end_year={br_year}) ...")
        br = fetch_br_fta(br_year)
        br = br.rename(columns={"attempted_free_throws": "br_fta"})

        mask = psx["season"] == our_season
        season_df = psx[mask].copy()
        season_df = season_df.merge(br, left_on="player_name", right_on="name", how="left")

        matched = season_df["br_fta"].notna().sum()
        total = len(season_df)
        print(f"  Matched {matched}/{total} players")

        # Update actual_fta_from_fouls where we have BR data
        season_df["actual_fta_from_fouls"] = season_df["br_fta"].fillna(
            season_df["actual_fta_from_fouls"]
        )

        # Recompute derived columns
        season_df["ftaoe"] = season_df["actual_fta_from_fouls"] - season_df["xfta_total"]
        season_df["ftaoe_per_100_fga"] = season_df["ftaoe"] / season_df["fga"] * 100

        # Update in the main dataframe
        psx.loc[mask, "actual_fta_from_fouls"] = season_df["actual_fta_from_fouls"].values
        psx.loc[mask, "ftaoe"] = season_df["ftaoe"].values
        psx.loc[mask, "ftaoe_per_100_fga"] = season_df["ftaoe_per_100_fga"].values

    # Recompute season-centered FTAOE
    season_means = psx.groupby("season")["ftaoe"].mean()
    psx["ftaoe_centered"] = psx.apply(
        lambda r: r["ftaoe"] - season_means[r["season"]], axis=1
    )

    # Per-100 possessions (where available)
    player = pd.read_sql("SELECT player_id, season, possessions FROM player_season", conn)
    psx = psx.drop(columns=["possessions"], errors="ignore")
    psx = psx.merge(player[["player_id", "season", "possessions"]], on=["player_id", "season"], how="left")
    psx["possessions"] = pd.to_numeric(psx["possessions"], errors="coerce")
    psx["ftaoe_per_100_poss"] = psx.apply(
        lambda r: r["ftaoe"] / r["possessions"] * 100
        if pd.notna(r["possessions"]) and r["possessions"] > 0
        else pd.NA,
        axis=1,
    )

    # Write back
    psx = psx[[
        "player_id", "player_name", "season", "fga",
        "actual_fta_from_fouls", "xfta_total", "ftaoe",
        "ftaoe_centered", "ftaoe_per_100_fga", "ftaoe_per_100_poss",
        "possessions",
    ]]
    psx.to_sql("player_season_xfta", conn, if_exists="replace", index=False)
    print(f"\nplayer_season_xfta updated: {len(psx):,} rows")

    # Print top-30 for sanity check
    top = psx[psx["fga"] >= 100].sort_values("ftaoe_per_100_fga", ascending=False).head(30)
    print("\nTOP-30 LEADERBOARD (min 100 FGA)")
    print(top[["player_name", "season", "fga", "actual_fta_from_fouls",
               "xfta_total", "ftaoe", "ftaoe_centered", "ftaoe_per_100_fga"]].to_string(index=False))

    # Print season centering stats
    print("\nSEASON CENTERING (mean FTAOE per shot):")
    for season in sorted(psx["season"].unique()):
        mean = psx[psx["season"] == season]["ftaoe"].mean()
        n = len(psx[psx["season"] == season])
        print(f"  {season}: {mean:+.6f} (n={n:,})")

    conn.close()


if __name__ == "__main__":
    fix_leaderboard()
