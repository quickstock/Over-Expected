"""xFTA Dashboard — Streamlit app with 4 tabs.

Usage: streamlit run dashboard/app.py
"""

import sys
import os

# Ensure repo root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from dashboard.queries import (
    get_connection, get_table_names, get_table_schema, get_table_data,
    get_table_row_count, run_query, get_leaderboard, get_player_list,
    get_player_shots, get_seasons,
)
from dashboard.court import draw_half_court

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_artifacts")

st.set_page_config(
    page_title="xFTA Dashboard",
    page_icon="",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap');

    .stApp {
        background-color: #0e1117;
    }
    section[data-testid="stSidebar"] {
        background-color: #1a1c23;
    }
    section[data-testid="stSidebar"] * {
        color: #e0e0e0;
    }
    .stTabs [data-baseweb="tab"] {
        color: #888;
    }
    .stTabs [aria-selected="true"] {
        color: #E8600A !important;
        border-bottom-color: #E8600A !important;
    }
    .stDataFrame {
        font-family: 'IBM Plex Mono', monospace;
    }
    .positive {
        color: #2ecc71;
    }
    .negative {
        color: #e74c3c;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("xFTA")
st.sidebar.markdown("**Expected Free Throw Attempts**")
st.sidebar.markdown(
    "xFTA quantifies how many free throws a field-goal attempt "
    "*should* produce based on shot context, then measures which "
    "players draw more shooting fouls than their shot profile predicts."
)
st.sidebar.markdown("[Methodology (coming soon)]()")
st.sidebar.divider()

# Check database
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "xfta.db")
db_exists = os.path.exists(db_path)

if not db_exists:
    st.warning("No database found. Run `python pull.py --game 0022300001` then `python build_tables.py` first.")
    st.stop()

conn = get_connection(db_path)
tables = get_table_names(conn)
seasons = get_seasons(conn)
players = get_player_list(conn)

st.sidebar.metric("Database", f"{len(tables)} tables" if tables else "empty")
if seasons:
    st.sidebar.metric("Seasons", ", ".join(seasons))

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "Raw Tables",
    "Leaderboard",
    "Shot Chart",
    "Calibration",
])

# ===========================================================================
# Tab 1: Raw Tables
# ===========================================================================
with tab1:
    st.header("Database Explorer")

    if not tables:
        st.info("No tables in database yet.")
    else:
        col1, col2 = st.columns([1, 3])
        with col1:
            selected_table = st.selectbox("Table", tables)

        if selected_table:
            schema = get_table_schema(conn, selected_table)
            row_count = get_table_row_count(conn, selected_table)

            with col1:
                st.metric("Rows", f"{row_count:,}")
                st.caption("Columns")
                st.dataframe(
                    schema[["name", "type"]].rename(columns={"name": "Column", "type": "Type"}),
                    hide_index=True, width="stretch",
                )

            with col2:
                df = get_table_data(conn, selected_table)
                st.dataframe(df, width="stretch", height=400)

        st.divider()
        st.subheader("SQL Query")
        query = st.text_area("Enter SQL query (reads from xfta.db)", height=80,
                             placeholder="SELECT * FROM training_fga LIMIT 10")
        if st.button("Run Query") and query.strip():
            try:
                result = run_query(conn, query)
                st.dataframe(result, width="stretch")
                st.caption(f"{len(result)} rows")
            except Exception as e:
                st.error(f"Query error: {e}")

# ===========================================================================
# Tab 2: Leaderboard
# ===========================================================================
with tab2:
    st.header("FTA Over Expected Leaderboard")

    has_xfta = "player_season_xfta" in tables

    col1, col2, col3 = st.columns(3)
    with col1:
        season_sel = st.selectbox("Season", ["All"] + seasons, key="lb_season")
    with col2:
        min_fga = st.slider("Min FGA", 10, 500, 100, 10, key="lb_min_fga")
    with col3:
        pos_filter = st.selectbox("Position", ["All", "G", "F", "C"], key="lb_pos")

    lb = get_leaderboard(
        conn,
        season=None if season_sel == "All" else season_sel,
        min_fga=min_fga,
        position_filter=pos_filter,
    )

    if len(lb) == 0:
        st.info("No players meet the criteria.")
    elif not has_xfta:
        st.caption("Showing raw foul-drawing rate (model predictions not yet available).")
        display_cols = {
            "player_name": "Player",
            "season": "Season",
            "fga": "FGA",
            "actual_fta_from_fouls": "FTA (Shooting)",
            "ftaoe_per_100_fga": "FTA/100FGA",
        }
        display_df = lb[list(display_cols.keys())].rename(columns=display_cols)
        display_df = display_df.sort_values("FTA/100FGA", ascending=False)
        styled = display_df.style.background_gradient(
            subset=["FTA/100FGA"], cmap="RdYlGn",
            vmin=0, vmax=display_df["FTA/100FGA"].quantile(0.95),
        )
        st.dataframe(styled, width="stretch", height=500, hide_index=True)
    else:
        display_cols = {
            "player_name": "Player",
            "season": "Season",
            "fga": "FGA",
            "actual_fta_from_fouls": "FTA",
            "xfta_total": "xFTA",
            "ftaoe": "FTAOE",
            "ftaoe_centered": "FTAOE*",
            "ftaoe_per_100_fga": "FTAOE/100",
        }
        display_df = lb[list(display_cols.keys())].rename(columns=display_cols)
        display_df = display_df.sort_values("FTAOE/100", ascending=False)
        styled = display_df.style.background_gradient(
            subset=["FTAOE/100"], cmap="RdYlGn",
            vmin=-1, vmax=display_df["FTAOE/100"].quantile(0.95),
        )
        st.dataframe(styled, width="stretch", height=500, hide_index=True)
        st.caption("FTAOE = actual FTA from fouls - xFTA. FTAOE* = season-centered. FTAOE/100 = per 100 FGA.")

# ===========================================================================
# Tab 3: Shot Chart
# ===========================================================================
with tab3:
    st.header("Player Shot Chart")

    if len(players) == 0:
        st.info("No player data available yet.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            player_names = players["player_name"].dropna().tolist() if "player_name" in players.columns else []
            if player_names:
                selected_name = st.selectbox("Player", sorted(player_names), key="sc_player")
                player_row = players[players["player_name"] == selected_name]
                if len(player_row) > 0:
                    selected_player_id = int(player_row.iloc[0]["player_id"])
                else:
                    selected_player_id = None
            else:
                player_ids = players["player_id"].tolist()
                selected_player_id = st.selectbox("Player ID", sorted(player_ids), key="sc_player_id")
                selected_name = str(selected_player_id)

        with col2:
            sc_season = st.selectbox("Season", ["All"] + seasons, key="sc_season")

        view_mode = st.radio("View", ["All Shots", "Foul Rate by Zone"], horizontal=True)

        if selected_player_id:
            shots = get_player_shots(
                conn,
                selected_player_id,
                season=None if sc_season == "All" else sc_season,
            )

            if len(shots) == 0:
                st.info(f"No shot data for {selected_name}")
            else:
                # Flip Y coordinate for court orientation (NBA API y=0 is baseline)
                shots["court_x"] = shots["shot_x"]
                shots["court_y"] = shots["shot_y"]

                if view_mode == "All Shots":
                    fig = go.Figure()
                    draw_half_court(fig)

                    # Hexbin of shot locations
                    fig.add_trace(go.Histogram2dContour(
                        x=shots["court_x"].dropna(),
                        y=shots["court_y"].dropna(),
                        colorscale="Reds",
                        showscale=True,
                        colorbar=dict(title="Frequency"),
                        contours=dict(showlabels=True),
                        name="shots",
                        nbinsx=20,
                        nbinsy=20,
                    ))

                    fig.update_layout(
                        title=f"{selected_name} — All Shots ({len(shots)} FGA)",
                        template="plotly_dark",
                        height=500,
                        margin=dict(l=20, r=20, t=40, b=20),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                else:
                    # Foul rate by zone
                    shots["zone"] = shots["shot_zone_basic"].fillna("Unknown")
                    zone_stats = shots.groupby("zone").agg(
                        FGA=("fta_from_shot", "count"),
                        FTA=("fta_from_shot", "sum"),
                    ).reset_index()
                    zone_stats["foul_rate"] = zone_stats["FTA"] / zone_stats["FGA"].replace(0, np.nan)
                    zone_stats = zone_stats.dropna(subset=["foul_rate"])

                    if len(zone_stats) > 0:
                        fig = px.bar(
                            zone_stats.sort_values("foul_rate", ascending=False),
                            x="zone",
                            y="foul_rate",
                            color="foul_rate",
                            color_continuous_scale="Reds",
                            title=f"{selected_name} — FTA Rate by Zone",
                            labels={"foul_rate": "FTA per FGA", "zone": "Shot Zone"},
                        )
                        fig.update_layout(template="plotly_dark", height=400)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No foul data for this player's zones.")

                # Show sample data
                with st.expander("Shot data sample"):
                    st.dataframe(shots.head(50).loc[:, ~shots.columns.duplicated()], width="stretch")

# ===========================================================================
# Tab 4: Calibration
# ===========================================================================
with tab4:
    st.header("Model Calibration")

    # Feature importance chart
    fi_path = os.path.join(MODEL_DIR, "feature_importance.csv")
    if os.path.exists(fi_path):
        fi = pd.read_csv(fi_path)
        st.subheader("Feature Importance (Gain)")
        fig = px.bar(fi, x="gain", y="feature", orientation="h",
                     title="Feature Importance", template="plotly_dark")
        fig.update_layout(yaxis=dict(categoryorder="total ascending"), height=400)
        st.plotly_chart(fig, use_container_width=True)

    # Calibration plots
    cal_global = os.path.join(MODEL_DIR, "calibration_global.png")
    cal_zone = os.path.join(MODEL_DIR, "calibration_per_zone.png")
    cal_compare = os.path.join(MODEL_DIR, "calibration_poisson_vs_multiclass.png")

    if os.path.exists(cal_global):
        st.subheader("Global Calibration (Gate A)")
        st.image(cal_global)

    if os.path.exists(cal_zone):
        st.subheader("Per-Zone Calibration")
        st.image(cal_zone)

    if os.path.exists(cal_compare):
        st.subheader("Poisson vs Multiclass Calibration")
        st.image(cal_compare)

    # Per-player-season residual histogram
    if "player_season_xfta" in tables:
        st.subheader("FTAOE Residual Distribution")
        ps = pd.read_sql("SELECT * FROM player_season_xfta WHERE fga >= 100", conn)
        if len(ps) > 0:
            fig = go.Figure()
            for season in sorted(ps["season"].unique()):
                s = ps[ps["season"] == season]
                fig.add_trace(go.Histogram(
                    x=s["ftaoe_per_100_fga"],
                    name=season,
                    opacity=0.6,
                    nbinsx=50,
                ))
            fig.update_layout(
                title="FTAOE/100 FGA Distribution by Season",
                xaxis_title="FTAOE per 100 FGA",
                template="plotly_dark",
                barmode="overlay",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

    # Gate A metrics
    metrics_path = os.path.join(MODEL_DIR, "metrics_gate_a.json")
    if os.path.exists(metrics_path):
        import json
        with open(metrics_path) as f:
            metrics = json.load(f)
        st.subheader("Gate A Metrics")
        col1, col2, col3 = st.columns(3)
        col1.metric("Poisson Deviance", f"{metrics['test_poisson_deviance']:,.0f}")
        col2.metric("Baseline Deviance", f"{metrics['baseline_poisson_deviance']:,.0f}")
        col3.metric("Lift vs Baseline", f"{metrics['lift_vs_baseline_pct']:.1f}%")

    if not os.path.exists(fi_path) and not os.path.exists(cal_global):
        st.info("Run `python train_model.py` and `python evaluate.py` to populate this tab.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.sidebar.divider()
st.sidebar.caption("xFTA Phase 2 — Model, Predictions & Leaderboard")
st.sidebar.caption(f"Database: {db_path}")

conn.close()