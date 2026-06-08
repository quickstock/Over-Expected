"""Build the clean possession-level target: player_season_xfta_poss.

Reads from the new `possessions` table (built by build_possessions_v3.py
via pbpstats' splitter) instead of the old training_possessions table.
Joins games to attach season.
"""
import sqlite3
import pandas as pd
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)

conn.execute("DROP TABLE IF EXISTS player_season_xfta_poss")

sql = """
CREATE TABLE player_season_xfta_poss AS
SELECT
    p.finisher_player_id AS player_id,
    g.season,
    COUNT(*) AS possessions,
    SUM(p.sfta) AS actual_fta_from_fouls
FROM possessions p
JOIN games g ON p.game_id = g.game_id
WHERE p.finisher_player_id IS NOT NULL
GROUP BY p.finisher_player_id, g.season
"""
conn.execute(sql)
conn.execute("CREATE INDEX idx_psxp_player ON player_season_xfta_poss(player_id)")
conn.execute("CREATE INDEX idx_psxp_season ON player_season_xfta_poss(season)")
conn.commit()

n = pd.read_sql("SELECT COUNT(*) AS n FROM player_season_xfta_poss", conn).iloc[0, 0]
print(f"player_season_xfta_poss: {n:,} player-seasons")

top = pd.read_sql("""
    SELECT psp.player_id, ps.player_name, psp.season,
           psp.possessions, psp.actual_fta_from_fouls
    FROM player_season_xfta_poss psp
    LEFT JOIN player_season ps
      ON psp.player_id = ps.player_id AND psp.season = ps.season
    ORDER BY psp.actual_fta_from_fouls DESC
    LIMIT 10
""", conn)
print("\nTop 10 actual_fta_from_fouls:")
print(top.to_string(index=False))

# Coverage vs NBA total FTA
total_target = pd.read_sql(
    "SELECT SUM(actual_fta_from_fouls) AS s FROM player_season_xfta_poss", conn
).iloc[0, 0]
print(f"\nSum actual_fta_from_fouls: {total_target:,}")

# Also rebuild training_possessions (same grain as the model expects)
# For now leave the old training_possessions empty — model retraining is a separate step
conn.close()
print("\nDone.")
