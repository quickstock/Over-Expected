"""Build the clean possession-level target: player_season_xfta_poss.

Target definition (no BR, no FGA grain, no scaling):
  actual_fta_from_fouls = integer count of shooting-foul FT trip M-values
                          in offensive possessions where the player was
                          the finisher, per (player_id, season).
  possessions            = integer count of offensive possessions where
                          the player was the finisher, per (player_id,
                          season). Includes zero-FTA possessions.

Source: training_possessions (cleanly derived from pbpstats V3 PBP).
Output: player_season_xfta_poss in xfta.db.
"""

import sqlite3
import pandas as pd

from config import DB_PATH

conn = sqlite3.connect(DB_PATH)

# Drop and rebuild — clean replacement, no write to legacy FGA-era tables
conn.execute("DROP TABLE IF EXISTS player_season_xfta_poss")

sql = """
CREATE TABLE player_season_xfta_poss AS
SELECT
    finisher_player_id AS player_id,
    season,
    COUNT(*) AS possessions,
    SUM(sfta) AS actual_fta_from_fouls
FROM training_possessions
WHERE finisher_player_id IS NOT NULL
GROUP BY finisher_player_id, season
"""

conn.execute(sql)
conn.execute("CREATE INDEX idx_psxp_player ON player_season_xfta_poss(player_id)")
conn.execute("CREATE INDEX idx_psxp_season ON player_season_xfta_poss(season)")
conn.commit()

# Sanity: integer, non-negative
df = pd.read_sql(
    "SELECT * FROM player_season_xfta_poss WHERE actual_fta_from_fouls IS NULL",
    conn,
)
assert len(df) == 0, f"NULL actual_fta found: {len(df)} rows"

# Join to player_name from player_season for readable reports
n = pd.read_sql("SELECT COUNT(*) AS n FROM player_season_xfta_poss", conn).iloc[0, 0]
print(f"player_season_xfta_poss: {n:,} player-seasons")
print(df.head(20).to_string(index=False) if len(df) else "(no NULLs)")

# Quick top
print()
print("Top 10 actual_fta_from_fouls:")
top = pd.read_sql("""
    SELECT psp.player_id, ps.player_name, psp.season,
           psp.possessions, psp.actual_fta_from_fouls
    FROM player_season_xfta_poss psp
    LEFT JOIN player_season ps
      ON psp.player_id = ps.player_id AND psp.season = ps.season
    ORDER BY psp.actual_fta_from_fouls DESC
    LIMIT 10
""", conn)
print(top.to_string(index=False))

conn.close()
print("\nDone.")
