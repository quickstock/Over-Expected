"""The week's best and worst shooting games -> site/public/weekly-NBA.json.

One row per player-game, ranked by field-goal points over expected: points
scored from the field minus what those shots were worth (player_game_shot_value,
the same xFG cross-fit as the shot-making lens). Weeks run Monday to Sunday and
are keyed by their Monday; only finished weeks are written, so the Monday run
publishes the week that just ended. From 2025-26 on, top 3 each way per week.

The combined site assembles every league's file into its weekly pages
(site/scripts/sync_data.py).
"""
import datetime as dt
import json
import sqlite3
from pathlib import Path

import pandas as pd

from config import DB_PATH, TEAM_ABBREV

FROM_SEASON = "2025-26"
TOP = 3
OUT = Path(__file__).parent / "site" / "public" / "weekly-NBA.json"


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    g = pd.read_sql(
        """SELECT p.player_id, p.game_id, p.season, p.fga, p.fgm,
                  p.act_fg_pts, p.exp_fg_pts, g.GAME_DATE AS date,
                  g.home_team_id, g.away_team_id
           FROM player_game_shot_value p JOIN games g ON g.GAME_ID = p.game_id
           WHERE p.season >= ?""", conn, params=(FROM_SEASON,))
    team = pd.read_sql(
        """SELECT game_id, player_id, team_id, COUNT(*) AS n FROM shots
           WHERE game_id IN (SELECT GAME_ID FROM games WHERE season >= ?)
           GROUP BY game_id, player_id, team_id""", conn, params=(FROM_SEASON,))
    team = team.sort_values("n").drop_duplicates(["game_id", "player_id"], keep="last")
    names = pd.read_sql(
        "SELECT player_id, season, player_name FROM player_season "
        "WHERE season >= ?", conn, params=(FROM_SEASON,))
    conn.close()

    g = g.merge(team[["game_id", "player_id", "team_id"]],
                on=["game_id", "player_id"], how="inner")
    g = g.merge(names, on=["player_id", "season"], how="left")
    g["date"] = pd.to_datetime(g["date"]).dt.date
    g["week"] = g["date"].map(lambda d: d - dt.timedelta(days=d.weekday()))
    g = g[g["week"] + dt.timedelta(days=6) < dt.date.today()]
    g["home"] = g["team_id"] == g["home_team_id"]
    g["opp_id"] = g["away_team_id"].where(g["home"], g["home_team_id"])
    g["oe"] = g["act_fg_pts"] - g["exp_fg_pts"]

    def row(r):
        return {"id": str(int(r.player_id)), "name": r.player_name,
                "team": TEAM_ABBREV[int(r.team_id)],
                "opp": TEAM_ABBREV[int(r.opp_id)], "home": bool(r.home),
                "date": r.date.isoformat(), "fgm": int(r.fgm),
                "fga": int(r.fga), "pts": int(r.act_fg_pts),
                "xpts": round(float(r.exp_fg_pts), 1),
                "oe": round(float(r.oe), 1),
                "gid": str(r.game_id), "season": r.season}

    weeks = {}
    for week, w in g.groupby("week"):
        w = w.sort_values("oe", ascending=False)
        weeks[week.isoformat()] = {
            "games": int(w["game_id"].nunique()),
            "over": [row(r) for r in w.head(TOP).itertuples()],
            "under": [row(r) for r in w.tail(TOP)[::-1].itertuples()],
        }
    OUT.write_text(json.dumps({"league": "NBA", "weeks": weeks},
                              separators=(",", ":"), ensure_ascii=False))
    print(f"weekly-NBA.json: {len(weeks)} weeks, latest {max(weeks) if weeks else '-'}")


if __name__ == "__main__":
    main()
