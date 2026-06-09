"""Real data access for xFTA dashboard v2.

Reads from xfta.db. Wire point is the LEAK-CLEAN leaderboard:
  player_season_xfta_poss_lb_clean  (4-feature Poisson GLM, OOF).
Provisional tag is DROPPED — the leak is verified gone.

All results are st.cache_data-cached at the module level.
"""

from __future__ import annotations

import os
import gzip
import sqlite3
import pandas as pd
import streamlit as st

from config import DB_PATH


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
@st.cache_resource
def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Open a connection. Cached as a resource (connection is reusable)."""
    if not os.path.exists(db_path):
        gz = db_path + ".gz"
        if os.path.exists(gz):
            with gzip.open(gz, "rb") as f_in, open(db_path, "wb") as f_out:
                f_out.write(f_in.read())
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found at {db_path}. Run build_possession_leaderboard.py."
        )
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA query_only = ON")
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


@st.cache_data(ttl=300, show_spinner=False)
def get_table_names(db_path: str) -> list[str]:
    conn = get_connection(db_path)
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]


@st.cache_data(ttl=300, show_spinner=False)
def get_seasons(db_path: str) -> list[str]:
    conn = get_connection(db_path)
    if not _table_exists(conn, "games"):
        return []
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT season FROM games ORDER BY season"
    ).fetchall()]


# ---------------------------------------------------------------------------
# The leaderboard table  (CLEAN: 4-feature Poisson GLM, OOF)
# ---------------------------------------------------------------------------
LB_TABLE = "player_season_xfta_poss_lb_clean"


@st.cache_data(ttl=300, show_spinner=False)
def get_leaderboard_data(db_path: str) -> pd.DataFrame:
    """Return all player-seasons from player_season_xfta_poss_lb_clean.

    Columns: player_id, season, position, possessions, actual_fta_from_fouls,
    xfta_total, ftaoe, ftaoe_per_100, ftaoe_rank, player_name, pos_bucket.

    ftaoe_per_100 is the headline rate. Provisional tag DROPPED — leak verified
    clean (OOF Poisson deviance lift 0.126% on 4 features).
    """
    conn = get_connection(db_path)
    if not _table_exists(conn, LB_TABLE):
        return pd.DataFrame()

    df = pd.read_sql(
        f"""
        SELECT
            CAST(player_id AS INTEGER) AS player_id,
            season,
            possessions,
            actual_fta_from_fouls,
            xfta_total,
            ftaoe,
            ftaoe_per_100,
            ftaoe_rank,
            player_name,
            position
        FROM {LB_TABLE}
        WHERE ftaoe_per_100 IS NOT NULL
        """,
        conn,
    )
    df["actual_fta_from_fouls"] = df["actual_fta_from_fouls"].astype(float)
    df["xfta_total"] = df["xfta_total"].astype(float)
    df["ftaoe"] = df["ftaoe"].astype(float)
    df["ftaoe_per_100"] = df["ftaoe_per_100"].astype(float)
    df["possessions"] = df["possessions"].astype(int)

    def _bucket(pos: str) -> str:
        if not isinstance(pos, str):
            return "F"
        p = pos.lower()
        if "guard" in p:
            return "G"
        if "center" in p:
            return "C"
        return "F"

    df["pos_bucket"] = df["position"].apply(_bucket)
    return df.sort_values("ftaoe_per_100", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Filtering + percentiles
# ---------------------------------------------------------------------------
def filter_leaderboard(
    df: pd.DataFrame,
    season: str | None = None,
    position_bucket: str | None = None,
    min_possessions: int = 300,
) -> pd.DataFrame:
    """Apply filters. Returns the filtered frame with a 'percentile' column
    computed within the filtered cohort (the inline bar)."""
    out = df.copy()
    if season and season != "All":
        out = out[out["season"] == season]
    if position_bucket and position_bucket != "All":
        out = out[out["pos_bucket"] == position_bucket]
    out = out[out["possessions"] >= min_possessions]

    if len(out) == 0:
        return out.assign(percentile=pd.Series(dtype=float))

    # Percentile within the cohort — rank on ftaoe_per_100, pct = (rank-1)/(n-1)
    out = out.sort_values("ftaoe_per_100", ascending=False).reset_index(drop=True)
    n = len(out)
    out["percentile"] = (1 - out.index / max(1, n - 1)) * 100
    return out


def season_percentile(df: pd.DataFrame, player_id: int, season: str) -> float | None:
    """Percentile of a player within their own season's qualified cohort."""
    cohort = df[(df["season"] == season)].copy()
    if len(cohort) == 0:
        return None
    cohort = cohort.sort_values("ftaoe_per_100", ascending=False).reset_index(drop=True)
    n = len(cohort)
    if n == 1:
        return 100.0
    pos = cohort.index[cohort["player_id"] == player_id]
    if len(pos) == 0:
        return None
    rank = pos[0]
    return round((1 - rank / (n - 1)) * 100, 1)


def robust_domain(values: pd.Series, lo: float = 0.05, hi: float = 0.95) -> tuple[float, float]:
    """Return robust (vmin, vmax) from a series using percentile clipping.

    Outliers beyond p5/p95 are clamped — so one 100%-capture player can't
    flatten the rest of the leaderboard into neutral.
    """
    clean = values.dropna()
    if len(clean) == 0:
        return (-5.0, 10.0)
    vmin = float(clean.quantile(lo))
    vmax = float(clean.quantile(hi))
    # Symmetric around zero if both are far from it; otherwise raw
    if vmin < 0 < vmax:
        # make it visually balanced: use the larger of |vmin|, |vmax|
        m = max(abs(vmin), abs(vmax))
        return (-m, m)
    if vmin >= 0:
        return (0.0, vmax)
    return (vmin, 0.0)


# ---------------------------------------------------------------------------
# Player hero
# ---------------------------------------------------------------------------
def get_player_seasons(db_path: str, player_id: int) -> pd.DataFrame:
    """All seasons for a single player (used by the across-seasons table)."""
    conn = get_connection(db_path)
    if not _table_exists(conn, LB_TABLE):
        return pd.DataFrame()
    df = pd.read_sql(
        f"""
        SELECT
            CAST(player_id AS INTEGER) AS player_id,
            season,
            possessions,
            actual_fta_from_fouls,
            xfta_total,
            ftaoe,
            ftaoe_per_100,
            ftaoe_rank,
            player_name,
            position
        FROM {LB_TABLE}
        WHERE CAST(player_id AS INTEGER) = ?
        ORDER BY season
        """,
        conn,
        params=(player_id,),
    )
    df["actual_fta_from_fouls"] = df["actual_fta_from_fouls"].astype(float)
    df["xfta_total"] = df["xfta_total"].astype(float)
    df["ftaoe"] = df["ftaoe"].astype(float)
    df["ftaoe_per_100"] = df["ftaoe_per_100"].astype(float)
    df["possessions"] = df["possessions"].astype(int)
    return df.reset_index(drop=True)


def get_player_options(db_path: str) -> list[str]:
    """Sorted list of unique player names for the hero selector."""
    df = get_leaderboard_data(db_path)
    if len(df) == 0:
        return []
    return sorted(df["player_name"].dropna().unique().tolist())


def get_marquee_season(db_path: str, player_name: str) -> dict | None:
    """Return the player's highest-possessions season (the default hero)."""
    df = get_leaderboard_data(db_path)
    rows = df[df["player_name"] == player_name]
    if len(rows) == 0:
        return None
    return rows.sort_values("possessions", ascending=False).iloc[0].to_dict()


# ---------------------------------------------------------------------------
# Gate 3 visuals
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def get_player_arc(db_path: str, player_id: int, season: str) -> pd.DataFrame:
    """Cumulative actual-vs-expected arc for a (player, season).

    Returns one row per possession the player finished, ordered by
    (game_id, possession_number), with running sums of (actual − xfta)
    and (actual / xfta) as a rate per 100 possessions.
    """
    conn = get_connection(db_path)
    if not _table_exists(conn, "predictions_poss_clean"):
        return pd.DataFrame()
    df = pd.read_sql(
        """
        SELECT
            p.game_id, p.possession_number, p.sfta, p.xfta,
            pos.period, pos.seconds_remaining_in_period,
            pos.score_margin, pos.in_bonus
        FROM predictions_poss_clean p
        JOIN training_possessions_v2 pos
            ON p.game_id = pos.game_id
            AND p.possession_number = pos.possession_number
        WHERE pos.finisher_player_id = ?
          AND p.season = ?
        ORDER BY p.game_id, p.possession_number
        """,
        conn,
        params=(player_id, season),
    )
    if len(df) == 0:
        return df
    df["delta"] = df["sfta"] - df["xfta"]
    df["cum_delta"] = df["delta"].cumsum()
    df["cum_actual"] = df["sfta"].cumsum()
    df["cum_xfta"] = df["xfta"].cumsum()
    return df.reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def get_player_context_mix(db_path: str, player_id: int, season: str) -> pd.DataFrame:
    """Context-mix subpanel — distribution of the player's possessions
    across the 4 model features, with the model's predicted FTA rate
    and the player's actual FTA rate in each bucket.

    Buckets: period (1, 2, 3, 4+OT), in_bonus (0, 1), score_margin
    (5 bins: <−10, −10..−3, −3..+3, +3..+10, >+10), seconds_remaining
    (early / mid / late / clutch).
    """
    conn = get_connection(db_path)
    if not _table_exists(conn, "predictions_poss_clean"):
        return pd.DataFrame()
    df = pd.read_sql(
        """
        SELECT
            pos.period, pos.seconds_remaining_in_period,
            pos.score_margin, pos.in_bonus,
            p.sfta, p.xfta
        FROM predictions_poss_clean p
        JOIN training_possessions_v2 pos
            ON p.game_id = pos.game_id
            AND p.possession_number = pos.possession_number
        WHERE pos.finisher_player_id = ?
          AND p.season = ?
        """,
        conn,
        params=(player_id, season),
    )
    if len(df) == 0:
        return df
    # Bucket the context features
    def _period_bucket(p):
        if p <= 3:
            return f"Q{p}"
        if p == 4:
            return "Q4"
        return f"OT{p-4}"
    df["period_b"] = df["period"].apply(_period_bucket)

    def _margin_bucket(m):
        if pd.isna(m) or m is None:
            return "unknown"
        if m < -10:
            return "trail 10+"
        if m < -3:
            return "trail 3-10"
        if m <= 3:
            return "close"
        if m <= 10:
            return "lead 3-10"
        return "lead 10+"
    df["margin_b"] = df["score_margin"].apply(_margin_bucket)

    def _clock_bucket(s):
        if pd.isna(s) or s is None:
            return "unknown"
        s = float(s)
        if s >= 360:
            return "early"
        if s >= 120:
            return "mid"
        if s >= 60:
            return "late"
        return "clutch (<1m)"
    df["clock_b"] = df["seconds_remaining_in_period"].apply(_clock_bucket)
    df["bonus_b"] = df["in_bonus"].map({0: "regulation", 1: "in bonus"})

    return df


@st.cache_data(ttl=300, show_spinner=False)
def get_calibration_data(db_path: str) -> pd.DataFrame:
    """Calibration view for the methodology tab.

    Bins possessions by predicted xfta decile, returns mean predicted
    and mean actual per bin. Plot is predicted (x) vs actual (y) on a
    log-friendly scale; a perfect model sits on the y=x line.
    """
    conn = get_connection(db_path)
    if not _table_exists(conn, "predictions_poss_clean"):
        return pd.DataFrame()
    df = pd.read_sql(
        """
        SELECT sfta, xfta FROM predictions_poss_clean
        """,
        conn,
    )
    if len(df) == 0:
        return df
    df["decile"] = pd.qcut(df["xfta"], 10, labels=False, duplicates="drop")
    return (
        df.groupby("decile", observed=True)
          .agg(mean_pred=("xfta", "mean"), mean_actual=("sfta", "mean"), n=("sfta", "size"))
          .reset_index()
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_model_coefficients(db_path: str) -> pd.DataFrame:
    """Read the final-model coefficients from the JSON artifact written
    by train_possession_v3_clean.py."""
    import json
    fp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "model_artifacts", "headline_v3_clean_final.json")
    if not os.path.exists(fp):
        return pd.DataFrame()
    with open(fp) as f:
        d = json.load(f)
    rows = [{"feature": k, "coef": v} for k, v in d["params"].items()]
    return pd.DataFrame(rows)
