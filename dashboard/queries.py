"""SQL query functions for the xFTA dashboard."""

from __future__ import annotations

import sqlite3
import pandas as pd

from config import DB_PATH


def get_connection(db_path: str = DB_PATH):
    return sqlite3.connect(db_path)


def get_table_names(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [r[0] for r in cur.fetchall()]


def get_table_schema(conn: sqlite3.Connection, table: str) -> pd.DataFrame:
    return pd.read_sql(f"PRAGMA table_info('{table}')", conn)


def get_table_data(conn: sqlite3.Connection, table: str, limit: int = 5000) -> pd.DataFrame:
    return pd.read_sql(f"SELECT * FROM '{table}' LIMIT {limit}", conn)


def get_table_row_count(conn: sqlite3.Connection, table: str) -> int:
    cur = conn.execute(f"SELECT COUNT(*) FROM '{table}'")
    return cur.fetchone()[0]


def run_query(conn: sqlite3.Connection, query: str) -> pd.DataFrame:
    return pd.read_sql(query, conn)


# Leaderboard query
def get_leaderboard(
    conn: sqlite3.Connection,
    season: str | None = None,
    min_fga: int = 100,
    position_filter: str = "All",
) -> pd.DataFrame:
    """Get the leaderboard data from player_season_xfta (real model) or fallback."""
    tables = get_table_names(conn)

    # Use real xfta leaderboard if available
    if "player_season_xfta" in tables:
        query = "SELECT * FROM player_season_xfta WHERE fga >= ?"
        params: list = [min_fga]

        if season:
            query += " AND season = ?"
            params.append(season)

        df = pd.read_sql(query, conn, params=params)

        if len(df) == 0:
            return df

        # Apply position filter via player_season
        if position_filter != "All":
            ps = pd.read_sql("SELECT player_id, position FROM player_season", conn)
            df = df.merge(ps, on="player_id", how="left")
            if position_filter == "G":
                df = df[df["position"].str.contains("Guard", na=False)]
            elif position_filter == "F":
                df = df[df["position"].str.contains("Forward", na=False)]
            elif position_filter == "C":
                df = df[df["position"].str.contains("Center", na=False)]
            df = df.drop(columns=["position"], errors="ignore")

        return df.sort_values("ftaoe_per_100_fga", ascending=False)

    # Fallback: raw foul-drawing rate before model
    if "training_fga" not in tables or "player_season" not in tables:
        return pd.DataFrame()

    query = """
    SELECT
        ps.player_name,
        ps.position,
        tf.season,
        COUNT(*) as fga,
        SUM(CASE WHEN tf.fta_from_shot > 0 THEN tf.fta_from_shot ELSE 0 END) as actual_fta_from_fouls,
        AVG(tf.fta_from_shot) as avg_fta_per_fga
    FROM training_fga tf
    LEFT JOIN player_season ps ON tf.player_id = ps.player_id AND tf.season = ps.season
    WHERE tf.fta_from_shot IS NOT NULL
    """
    params = []
    if season:
        query += " AND tf.season = ?"
        params.append(season)

    query += """
    GROUP BY tf.player_id, tf.season
    HAVING fga >= ?
    """
    params.append(min_fga)

    df = pd.read_sql(query, conn, params=params)

    if len(df) == 0:
        return df

    if position_filter != "All":
        if position_filter == "G":
            df = df[df["position"].str.contains("Guard", na=False)]
        elif position_filter == "F":
            df = df[df["position"].str.contains("Forward", na=False)]
        elif position_filter == "C":
            df = df[df["position"].str.contains("Center", na=False)]

    df["ftaoe_per_100_fga"] = (df["actual_fta_from_fouls"] / df["fga"]) * 100
    df["ftaoe"] = df["actual_fta_from_fouls"]
    df["xfta_total"] = 0.0

    return df.sort_values("ftaoe_per_100_fga", ascending=False)


# Player list for autocomplete
def get_player_list(conn: sqlite3.Connection) -> pd.DataFrame:
    tables = get_table_names(conn)
    if "player_season" in tables:
        return pd.read_sql(
            "SELECT DISTINCT player_id, player_name FROM player_season WHERE player_name IS NOT NULL",
            conn,
        )
    if "training_fga" in tables:
        return pd.read_sql(
            "SELECT DISTINCT player_id FROM training_fga",
            conn,
        )
    return pd.DataFrame()


# Shot chart data for a player
def get_player_shots(
    conn: sqlite3.Connection, player_id: int, season: str | None = None
) -> pd.DataFrame:
    """Get shot data for a specific player."""
    tables = get_table_names(conn)
    if "training_fga" not in tables:
        return pd.DataFrame()

    query = """
    SELECT tf.*, s.shot_x, s.shot_y, s.shot_made, s.shot_zone_basic, s.shot_zone_area
    FROM training_fga tf
    JOIN shots s ON tf.game_id = s.game_id AND tf.event_id = s.event_id
    WHERE tf.player_id = ?
    """
    params = [player_id]
    if season:
        query += " AND tf.season = ?"
        params.append(season)

    return pd.read_sql(query, conn, params=params)


# Season list
def get_seasons(conn: sqlite3.Connection) -> list[str]:
    tables = get_table_names(conn)
    if "games" in tables:
        cur = conn.execute("SELECT DISTINCT season FROM games ORDER BY season")
        return [r[0] for r in cur.fetchall()]
    return []
