"""Build the FTAOE leaderboard: actual shooting-foul FTs minus the shot-diet
expectation (diet_game, from build_diet_expected.py). Writes
player_season_xfta_poss_lb_clean.

Until 2026-10-22 the expectation was the sum of the context model's
per-possession predictions (predictions_poss_clean), which left FTAOE r 0.995
with the raw rate. That model still feeds the team and referee views.
"""
import sqlite3
import pandas as pd
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)

roll = pd.read_sql("""
    SELECT player_id, season, possessions, actual_fta_from_fouls
    FROM player_season_xfta_poss
""", conn)

xfta_by_player_season = pd.read_sql(
    "SELECT player_id, season, SUM(xft) AS xfta_total FROM diet_game "
    "GROUP BY player_id, season",
    conn,
)
roll = roll.merge(xfta_by_player_season, on=["player_id", "season"], how="left")
roll["xfta_total"] = roll["xfta_total"].fillna(0.0)

roll["ftaoe"] = roll["actual_fta_from_fouls"] - roll["xfta_total"]
roll["ftaoe_per_100"] = roll["ftaoe"] / roll["possessions"].replace(0, pd.NA) * 100
roll["ftaoe_rank"] = roll.groupby("season")["ftaoe"].rank(
    ascending=False, method="min"
).fillna(0).astype(int)

ps = pd.read_sql(
    "SELECT player_id, season, player_name, position FROM player_season", conn
)
roll = roll.merge(ps, on=["player_id", "season"], how="left")

conn.execute("DROP TABLE IF EXISTS player_season_xfta_poss_lb_clean")
roll.to_sql(
    "player_season_xfta_poss_lb_clean", conn, if_exists="replace", index=False
)
conn.execute(
    "CREATE INDEX idx_lbclean_player "
    "ON player_season_xfta_poss_lb_clean(player_id, season)"
)
conn.execute(
    "CREATE INDEX idx_lbclean_season "
    "ON player_season_xfta_poss_lb_clean(season)"
)
conn.commit()

# Sanity read — top 10 by ftaoe (min 300 possessions)
lb = roll[roll["possessions"] >= 300].copy()
print("Top 10 by ftaoe (clean, min 300 possessions):")
print(
    lb.sort_values("ftaoe", ascending=False).head(10)[
        ["player_name", "season", "possessions", "actual_fta_from_fouls",
         "xfta_total", "ftaoe", "ftaoe_per_100", "ftaoe_rank"]
    ].to_string(index=False)
)

print("\nGiannis 2024-25 (clean):")
print(
    roll[(roll["player_name"] == "Giannis Antetokounmpo") &
          (roll["season"] == "2024-25")][
        ["possessions", "actual_fta_from_fouls", "xfta_total",
         "ftaoe", "ftaoe_per_100"]
    ].to_string(index=False)
)

print("\nPace spot-check (mean possessions per team per game):")
n_games = pd.read_sql("SELECT COUNT(*) AS n FROM games", conn).iloc[0, 0]
mean_poss = roll["possessions"].sum() / n_games / 2
print(f"  {mean_poss:.1f} possessions/team/game (spec: 96-102)")

conn.close()
print("\nDone.")
