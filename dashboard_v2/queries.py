"""SQL query functions for the xFTA dashboard v2."""

from __future__ import annotations

import sqlite3
import pandas as pd

from config import DB_PATH


@pd.api.extensions.register_dataframe_accessor("xfta")
class XFTAAccessor:
    """Custom pandas accessor for xFTA formatting."""

    def __init__(self, pandas_obj: pd.DataFrame):
        self._obj = pandas_obj

    def fmt_num(self, col: str, decimals: int = 1) -> pd.Series:
        return self._obj[col].apply(lambda x: f"{x:,.{decimals}f}" if pd.notna(x) else "—")

    def fmt_pct(self, col: str) -> pd.Series:
        return self._obj[col].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")


def get_connection(db_path: str = DB_PATH):
    return sqlite3.connect(db_path)


def get_table_names(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [r[0] for r in cur.fetchall()]


def get_seasons(conn: sqlite3.Connection) -> list[str]:
    tables = get_table_names(conn)
    if "games" in tables:
        cur = conn.execute("SELECT DISTINCT season FROM games ORDER BY season")
        return [r[0] for r in cur.fetchall()]
    return []


def get_leaderboard(
    conn: sqlite3.Connection,
    season: str | None = None,
    min_fga: int = 300,
    position_filter: str = "All",
) -> pd.DataFrame:
    tables = get_table_names(conn)
    if "player_season_xfta" not in tables:
        return pd.DataFrame()

    query = "SELECT * FROM player_season_xfta WHERE fga >= ?"
    params: list = [min_fga]

    if season:
        query += " AND season = ?"
        params.append(season)

    df = pd.read_sql(query, conn, params=params)
    if len(df) == 0:
        return df

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


def get_player_list(conn: sqlite3.Connection) -> pd.DataFrame:
    tables = get_table_names(conn)
    if "player_season" in tables:
        return pd.read_sql(
            "SELECT DISTINCT player_id, player_name FROM player_season WHERE player_name IS NOT NULL ORDER BY player_name",
            conn,
        )
    return pd.DataFrame()


def get_player_shots(
    conn: sqlite3.Connection, player_id: int, season: str | None = None
) -> pd.DataFrame:
    tables = get_table_names(conn)
    if "training_fga" not in tables:
        return pd.DataFrame()

    query = """
    SELECT
        tf.game_id, tf.event_id, tf.player_id, tf.season,
        tf.shot_distance, tf.action_type, tf.shot_type, tf.period,
        tf.seconds_remaining_in_period, tf.score_margin, tf.in_bonus,
        tf.home_or_away, tf.shooter_height, tf.shooter_position,
        tf.prior_season_ftr, tf.prior_season_drive_rate,
        tf.fta_from_shot, tf.xfta,
        s.shot_x, s.shot_y, s.shot_made, s.shot_zone_basic, s.shot_zone_area
    FROM training_fga tf
    JOIN shots s ON tf.game_id = s.game_id AND tf.event_id = s.event_id
    WHERE tf.player_id = ?
    """
    params = [player_id]
    if season:
        query += " AND tf.season = ?"
        params.append(season)

    return pd.read_sql(query, conn, params=params)


def get_xfta_heatmap_bins(conn: sqlite3.Connection, bins: int = 30) -> pd.DataFrame:
    """Precompute binned xFTA averages for the hero heatmap."""
    if "training_fga" not in get_table_names(conn):
        return pd.DataFrame()

    query = f"""
    SELECT
        CAST(ROUND((s.shot_x + 25) / 50.0 * {bins}) AS INTEGER) AS x_bin,
        CAST(ROUND(s.shot_y / 47.0 * {bins}) AS INTEGER) AS y_bin,
        AVG(tf.xfta) AS avg_xfta,
        COUNT(*) AS n
    FROM training_fga tf
    JOIN shots s ON tf.game_id = s.game_id AND tf.event_id = s.event_id
    WHERE s.shot_x IS NOT NULL AND s.shot_y IS NOT NULL
      AND s.shot_x BETWEEN -25 AND 25
      AND s.shot_y BETWEEN 0 AND 47
    GROUP BY x_bin, y_bin
    HAVING n >= 20
    """
    df = pd.read_sql(query, conn)
    # Clip to valid bin range
    df = df[(df["x_bin"] >= 0) & (df["x_bin"] <= bins) & (df["y_bin"] >= 0) & (df["y_bin"] <= bins)]
    return df


def get_player_season_summary(conn: sqlite3.Connection, player_id: int, season: str) -> dict:
    """Plain-language summary stats for a player season."""
    query = """
    SELECT
        fga,
        actual_fta_from_fouls,
        xfta_total,
        ftaoe,
        ftaoe_per_100_fga,
        ftaoe_rank
    FROM player_season_xfta
    WHERE player_id = ? AND season = ?
    """
    row = pd.read_sql(query, conn, params=[player_id, season])
    if len(row) == 0:
        return {}
    return row.iloc[0].to_dict()


def get_calibration_data(conn: sqlite3.Connection) -> pd.DataFrame:
    """Global calibration: predicted xFTA deciles vs actual FTA."""
    if "training_fga" not in get_table_names(conn):
        return pd.DataFrame()

    query = """
    WITH ranked AS (
        SELECT xfta, fta_from_shot,
               NTILE(10) OVER (ORDER BY xfta) AS decile
        FROM training_fga
        WHERE xfta IS NOT NULL AND fta_from_shot IS NOT NULL
    )
    SELECT
        decile,
        AVG(xfta) AS predicted,
        AVG(fta_from_shot) AS actual,
        COUNT(*) AS n
    FROM ranked
    GROUP BY decile
    ORDER BY decile
    """
    return pd.read_sql(query, conn)


def get_zone_calibration(conn: sqlite3.Connection) -> pd.DataFrame:
    """Per-zone calibration data."""
    if "training_fga" not in get_table_names(conn):
        return pd.DataFrame()

    query = """
    WITH ranked AS (
        SELECT tf.xfta, tf.fta_from_shot, s.shot_zone_basic,
               NTILE(10) OVER (PARTITION BY s.shot_zone_basic ORDER BY tf.xfta) AS decile
        FROM training_fga tf
        JOIN shots s ON tf.game_id = s.game_id AND tf.event_id = s.event_id
        WHERE tf.xfta IS NOT NULL AND tf.fta_from_shot IS NOT NULL
          AND s.shot_zone_basic IS NOT NULL
    )
    SELECT
        shot_zone_basic AS zone,
        decile,
        AVG(xfta) AS predicted,
        AVG(fta_from_shot) AS actual,
        COUNT(*) AS n
    FROM ranked
    GROUP BY zone, decile
    ORDER BY zone, decile
    """
    return pd.read_sql(query, conn)
