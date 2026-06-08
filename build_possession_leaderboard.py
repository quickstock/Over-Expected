"""Build the clean possession-level leaderboard: player_season_xfta_poss_lb.

Per the EXACT Fix: no PACE_SCALE, no fudge factors. Possession counts come
straight from pbpstats' splitter (Step 3) and are already at NBA pace
(98.3/team/game, in the 96-102 acceptance band).

Columns:
  - possessions          (raw, from pbpstats — already at NBA pace)
  - actual_fta_from_fouls (sum sfta, integer, non-negative)
  - xfta_total           (sum of OOF predictions, may be float)
  - ftaoe                (actual - xfta)
  - ftaoe_per_100        (per 100 league-possessions)
  - ftaoe_rank           (within season)
"""
import sqlite3
import pandas as pd
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)

# Pull player-season aggregates from the new target
roll = pd.read_sql("""
    SELECT
        player_id,
        season,
        possessions,
        actual_fta_from_fouls
    FROM player_season_xfta_poss
""", conn)

# Sum OOF xfta predictions to the finisher of each possession.
# predictions_poss is keyed on (game_id, possession_number); the `possessions`
# table is the source of truth for who finished each possession.
oof = pd.read_sql("SELECT game_id, possession_number, xfta FROM predictions_poss", conn)
fin = pd.read_sql(
    "SELECT p.game_id, p.possession_number, p.finisher_player_id, g.season "
    "FROM possessions p JOIN games g ON p.game_id = g.game_id",
    conn,
)
fin = fin.dropna(subset=["finisher_player_id"])
fin["finisher_player_id"] = fin["finisher_player_id"].astype(int)
oof = oof.merge(fin, on=["game_id", "possession_number"], how="inner")
xfta_by_player_season = (
    oof.groupby(["finisher_player_id", "season"])["xfta"].sum()
    .reset_index()
    .rename(columns={"finisher_player_id": "player_id", "xfta": "xfta_total"})
)
roll = roll.merge(xfta_by_player_season, on=["player_id", "season"], how="left")
roll["xfta_total"] = roll["xfta_total"].fillna(0.0)

roll["ftaoe"] = roll["actual_fta_from_fouls"] - roll["xfta_total"]
roll["ftaoe_per_100"] = roll["ftaoe"] / roll["possessions"].replace(0, pd.NA) * 100
roll["ftaoe_rank"] = roll.groupby("season")["ftaoe"].rank(
    ascending=False, method="min"
).fillna(0).astype(int)

ps = pd.read_sql("SELECT player_id, season, player_name, position FROM player_season", conn)
roll = roll.merge(ps, on=["player_id", "season"], how="left")

conn.execute("DROP TABLE IF EXISTS player_season_xfta_poss_lb")
roll.to_sql("player_season_xfta_poss_lb", conn, if_exists="replace", index=False)
conn.execute("CREATE INDEX idx_lb_player ON player_season_xfta_poss_lb(player_id, season)")
conn.execute("CREATE INDEX idx_lb_season ON player_season_xfta_poss_lb(season)")
conn.commit()

# Spot read
print("Top 10 by actual_fta_from_fouls (no scaling, pbpstats pace):")
print(roll.sort_values("actual_fta_from_fouls", ascending=False).head(10)[
    ["player_name", "season", "possessions", "actual_fta_from_fouls",
     "xfta_total", "ftaoe", "ftaoe_per_100", "ftaoe_rank"]
].to_string(index=False))

print("\nGiannis 2024-25:")
print(roll[(roll["player_name"] == "Giannis Antetokounmpo") &
           (roll["season"] == "2024-25")][
    ["possessions", "actual_fta_from_fouls", "xfta_total", "ftaoe", "ftaoe_per_100"]
].to_string(index=False))

print("\nPace spot-check (mean possessions per team per game):")
n_games = pd.read_sql("SELECT COUNT(*) AS n FROM games", conn).iloc[0, 0]
mean_poss = roll["possessions"].sum() / n_games / 2
print(f"  {mean_poss:.1f} possessions/team/game (spec: 96-102)")

conn.close()
print("\nDone.")
