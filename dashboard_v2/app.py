"""xFTA Dashboard v2 — educational Streamlit app.

Usage: streamlit run dashboard_v2/app.py
"""

import sys
import os

# Ensure repo root is on path so config resolves
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import gzip

from config import DB_PATH
from dashboard_v2.styles import CSS
from dashboard_v2 import queries as q
from dashboard_v2 import court

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="xFTA",
    page_icon="🏀",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Inject design system
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
{CSS}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Database connection + validation
# ---------------------------------------------------------------------------
_db_path = os.path.join(_REPO_ROOT, DB_PATH)

# On Streamlit Cloud the uncompressed DB may not exist; decompress if needed
_gz_path = _db_path + ".gz"
if not os.path.exists(_db_path) and os.path.exists(_gz_path):
    with st.spinner("Decompressing database for first use..."):
        with gzip.open(_gz_path, "rb") as f_in, open(_db_path, "wb") as f_out:
            f_out.write(f_in.read())

if not os.path.exists(_db_path):
    st.warning("Database not found. Run `python build_tables.py` first.")
    st.stop()

_conn = q.get_connection(_db_path)
_tables = q.get_table_names(_conn)
_seasons = q.get_seasons(_conn)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="xfta-logo">xFTA</div>', unsafe_allow_html=True)
    st.markdown('<div class="xfta-tagline">Expected Free Throw Attempts</div>', unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:0.8125rem; color:var(--text-secondary); line-height:1.6;'>"
        "xFTA measures how many free throws a player's shot profile <em>should</em> produce. "
        "The gap between actual and expected is foul-drawing craft."
        "</p>",
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown(
        f"<p style='font-size:0.6875rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.06em; font-weight:600;'>"
        f"{len(_seasons)} seasons  |  {len(_tables)} tables"
        f"</p>",
        unsafe_allow_html=True,
    )
    if _seasons:
        st.caption(
            f"<span style='color:var(--text-muted);'>{', '.join(_seasons)}</span>",
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_explainer, tab_leaderboard, tab_shotchart, tab_methodology = st.tabs([
    "What is xFTA?",
    "Leaderboard",
    "Shot Chart",
    "Methodology",
])

# ---------------------------------------------------------------------------
# Cached data
# ---------------------------------------------------------------------------
@st.cache_data(ttl=None, show_spinner=False)
def _load_heatmap_bins(db_path: str):
    conn = q.get_connection(db_path)
    try:
        return q.get_xfta_heatmap_bins(conn, bins=30)
    finally:
        conn.close()

_heatmap_bins = _load_heatmap_bins(_db_path)

# ===========================================================================
# Tab 1: What is xFTA?  (explainer + hero heatmap)
# ===========================================================================
with tab_explainer:
    # ---- Hero heatmap ------------------------------------------------------
    st.markdown(
        "<h1 style='font-size:2.5rem; margin-bottom:0.25rem;'>Where do free throws come from?</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:var(--text-muted); font-size:1rem; margin-bottom:1.5rem;'>"
        "Every spot on the floor has an expected foul rate. Rim shots glow orange. Jump shots stay dark."
        "</p>",
        unsafe_allow_html=True,
    )

    col_map, col_legend = st.columns([3, 1])
    with col_map:
        if len(_heatmap_bins) > 0:
            svg = court.draw_xfta_heatmap(_heatmap_bins, width=640, height=560)
            st.components.v1.html(svg, height=580, scrolling=False)
        else:
            st.info("Heatmap data not yet available.")

    with col_legend:
        st.markdown(
            "<div style='padding-top:2rem;'>"
            "<p style='font-family:\"IBM Plex Mono\",monospace; font-size:0.75rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.06em;'>"
            "Avg xFTA per shot"
            "</p>"
            "<div style='display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem;'>"
            "<div style='width:12px; height:12px; background:#E8600A; border-radius:2px;'></div>"
            "<span style='font-size:0.8125rem; color:var(--text-secondary);'>High — rim & paint (&gt;0.05)</span>"
            "</div>"
            "<div style='display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem;'>"
            "<div style='width:12px; height:12px; background:#A0522D; border-radius:2px;'></div>"
            "<span style='font-size:0.8125rem; color:var(--text-secondary);'>Medium — mid-range (&gt;0.01)</span>"
            "</div>"
            "<div style='display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem;'>"
            "<div style='width:12px; height:12px; background:#3E2723; border-radius:2px;'></div>"
            "<span style='font-size:0.8125rem; color:var(--text-secondary);'>Low — 3-point (&lt;0.01)</span>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ---- Narrative arc -----------------------------------------------------
    steps = [
        (
            "Free throws are free points.",
            "Getting to the line is one of the most efficient ways to score. Every foul drawn turns a field-goal attempt into unguarded shots from 15 feet. But not all players get there equally."
        ),
        (
            "Raw FTA misleads.",
            "A center who lives at the rim will naturally draw more fouls than a spot-up shooter who lives beyond the arc. That difference is mostly *shot diet*, not skill. If you want to know who is truly elite at drawing contact, you have to account for where they shoot from."
        ),
        (
            "Enter xFTA — expected free throw attempts.",
            "Given the exact shots a player takes — the distance, the zone, the action type, the game situation — how many free throws *should* those attempts produce? xFTA answers that. It is a context-aware baseline built from 650,000 NBA shots across three seasons."
        ),
        (
            "FTAOE is the gap that matters.",
            "**FTA Over Expected** = actual FTA minus xFTA. When a player consistently beats their expected rate, they are doing something shot selection cannot explain: initiating contact, selling the foul, earning the and-1. That is foul-drawing craft."
        ),
    ]

    for title, body in steps:
        st.markdown(
            f"<h3 style='font-size:1.125rem; font-weight:600; margin-bottom:0.25rem;'>{title}</h3>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<p style='font-size:0.9375rem; line-height:1.65; color:var(--text-secondary); margin-bottom:1rem;'>{body}</p>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<div style='margin: 1.5rem 0;'>"
        "<a href='#leaderboard' style='display:inline-flex; align-items:center; gap:0.4rem; color:#E8600A; font-weight:600; font-size:0.9375rem; text-decoration:none;'>"
        "See the Leaderboard →"
        "</a>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.divider()

    # ---- Glossary ----------------------------------------------------------
    st.markdown(
        "<h2 style='font-size:1.25rem; margin-bottom:0.75rem;'>Glossary</h2>",
        unsafe_allow_html=True,
    )

    glossary = [
        (
            "xFTA",
            "Expected Free Throw Attempts. The average number of free throws a shot with these characteristics should produce, based on league-wide rates."
        ),
        (
            "FTAOE",
            "FTA Over Expected. The difference between a player's actual shooting-foul free throws and their xFTA. Positive = better than expected at drawing fouls."
        ),
        (
            "FTAOE / 100 FGA",
            "FTAOE scaled per 100 field-goal attempts. This lets you compare foul-drawing skill across players with very different shot volumes."
        ),
        (
            "Expected stats",
            "A family of metrics (xG in soccer, xFG% in basketball) that estimate what *should* happen given context, isolating skill from circumstance."
        ),
    ]

    for term, definition in glossary:
        st.markdown(
            f"<div class='glossary-card'>"
            f"<dt>{term}</dt>"
            f"<dd>{definition}</dd>"
            f"</div>",
            unsafe_allow_html=True,
        )

# ===========================================================================
# Tab 2: Leaderboard
# ===========================================================================
with tab_leaderboard:
    st.markdown(
        "<h1 style='font-size:2.25rem; margin-bottom:0.25rem;'>FTA Over Expected Leaderboard</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:var(--text-muted); font-size:1rem; margin-bottom:1.5rem;'>"
        "Who draws more fouls than their shot profile predicts? Sorted by FTAOE per 100 FGA."
        "</p>",
        unsafe_allow_html=True,
    )

    # ---- Filters -----------------------------------------------------------
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        lb_season = st.selectbox("Season", ["All"] + _seasons, key="lb_season")
    with fcol2:
        lb_min_fga = st.slider("Min FGA", 100, 1000, 300, 50, key="lb_min_fga")
    with fcol3:
        lb_pos = st.selectbox("Position", ["All", "G", "F", "C"], key="lb_pos")

    lb_df = q.get_leaderboard(
        _conn,
        season=None if lb_season == "All" else lb_season,
        min_fga=lb_min_fga,
        position_filter=lb_pos,
    )

    if len(lb_df) == 0:
        st.info("No players meet the criteria.")
    else:
        lb_df = lb_df.sort_values("ftaoe_per_100_fga", ascending=True)  # asc for horizontal bar
        display_n = min(25, len(lb_df))
        top_df = lb_df.tail(display_n).copy()

        # Diverging color: orange positive, teal negative
        top_df["color"] = top_df["ftaoe_per_100_fga"].apply(
            lambda x: "#E8600A" if x >= 0 else "#0D9488"
        )

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=top_df["ftaoe_per_100_fga"],
            y=top_df["player_name"] + "  " + top_df["season"],
            orientation="h",
            marker=dict(color=top_df["color"], line=dict(width=0)),
            text=top_df["ftaoe_per_100_fga"].apply(lambda x: f"{x:+.1f}"),
            textposition="outside",
            textfont=dict(family="IBM Plex Mono", size=11, color="#A8A29E"),
            cliponaxis=False,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "FTAOE/100: %{x:+.2f}<br>"
                "FGA: %{customdata[0]:,}<br>"
                "FTAOE: %{customdata[1]:+.1f}<extra></extra>"
            ),
            customdata=np.stack([
                top_df["fga"].values,
                top_df["ftaoe"].values,
            ], axis=-1),
        ))

        fig.update_layout(
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=180, r=100, t=20, b=40),
            height=max(400, display_n * 26),
            xaxis=dict(
                title="FTAOE per 100 FGA",
                titlefont=dict(family="Inter", size=12, color="#78716C"),
                tickfont=dict(family="IBM Plex Mono", size=11, color="#A8A29E"),
                zeroline=True,
                zerolinecolor="rgba(255,255,255,0.15)",
                zerolinewidth=1,
                gridcolor="rgba(255,255,255,0.06)",
            ),
            yaxis=dict(
                tickfont=dict(family="Inter", size=12, color="#E7E5E4"),
                categoryorder="total ascending",
            ),
            showlegend=False,
            hoverlabel=dict(
                bgcolor="#292524",
                bordercolor="rgba(255,255,255,0.1)",
                font=dict(family="Inter", size=13, color="#E7E5E4"),
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

        # ---- Full table ------------------------------------------------------
        with st.expander("Full data table"):
            display_df = lb_df.sort_values("ftaoe_per_100_fga", ascending=False).copy()
            display_df = display_df[[
                "player_name", "season", "fga", "actual_fta_from_fouls",
                "xfta_total", "ftaoe", "ftaoe_centered", "ftaoe_per_100_fga"
            ]]
            display_df.columns = [
                "Player", "Season", "FGA", "FTA", "xFTA", "FTAOE", "FTAOE*", "FTAOE/100"
            ]
            st.dataframe(display_df, hide_index=True, use_container_width=True)
            st.caption(
                "FTAOE* = season-centered FTAOE (z-score relative to that season's mean). "
                "FTAOE/100 = FTAOE per 100 field-goal attempts."
            )

# ===========================================================================
# Tab 3: Shot Chart
# ===========================================================================
with tab_shotchart:
    st.markdown(
        "<h1 style='font-size:2.25rem; margin-bottom:0.25rem;'>Player Shot Chart</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:var(--text-muted); font-size:1rem; margin-bottom:1.5rem;'>"
        "Explore where a player shoots and where they draw fouls."
        "</p>",
        unsafe_allow_html=True,
    )

    _players = q.get_player_list(_conn)
    if len(_players) == 0:
        st.info("No player data available.")
    else:
        # Player selector + season
        pcol1, pcol2, pcol3 = st.columns([2, 1, 1])
        with pcol1:
            player_names = sorted(_players["player_name"].dropna().unique().tolist())
            selected_name = st.selectbox("Player", player_names, key="sc_player")
            selected_id = int(_players[_players["player_name"] == selected_name].iloc[0]["player_id"])
        with pcol2:
            sc_season = st.selectbox("Season", ["All"] + _seasons, key="sc_season")
        with pcol3:
            sc_view = st.radio("View", ["All Shots", "Foul Rate"], horizontal=True, key="sc_view")

        # Load shots
        shots = q.get_player_shots(
            _conn,
            selected_id,
            season=None if sc_season == "All" else sc_season,
        )

        if len(shots) == 0:
            st.info(f"No shot data for {selected_name} in {sc_season}.")
        else:
            c1, c2 = st.columns([3, 2])
            with c1:
                if sc_view == "All Shots":
                    svg = court.draw_shot_frequency_court(shots, width=560, height=520)
                else:
                    svg = court.draw_foul_rate_court(shots, width=560, height=520)
                st.components.v1.html(svg, height=540, scrolling=False)

            with c2:
                # Plain English summary
                if "player_season_xfta" in _tables and sc_season != "All":
                    summary = q.get_player_season_summary(_conn, selected_id, sc_season)
                    if summary:
                        fga = summary.get("fga", 0)
                        actual = summary.get("actual_fta_from_fouls", 0)
                        xfta = summary.get("xfta_total", 0)
                        ftaoe = summary.get("ftaoe", 0)
                        ftaoe_100 = summary.get("ftaoe_per_100_fga", 0)

                        sign = "+" if ftaoe >= 0 else ""
                        cmp = "above" if ftaoe >= 0 else "below"
                        _color = "#E8600A" if ftaoe >= 0 else "#0D9488"
                        rank_note = f"Ranked {summary.get('ftaoe_rank', '—')}th in FTAOE/100 that season." if summary.get('ftaoe_rank') else ""

                        st.markdown(
                            f"<div style='background:var(--charcoal-light); border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:1.25rem;'>"
                            f"<p style='font-family:\"DM Serif Display\",serif; font-size:1.125rem; color:var(--orange); margin-bottom:0.5rem;'>"
                            f"{selected_name} — {sc_season}"
                            f"</p>"
                            f"<p style='font-size:0.9375rem; line-height:1.65; color:var(--text-secondary); margin-bottom:0.75rem;'>"
                            f"Drew <b>{actual:.0f}</b> free throws on <b>{fga:.0f}</b> shot attempts. "
                            f"His shot profile predicted <b>{xfta:.1f}</b>. "
                            f"That's <b style='color:{_color};'>{sign}{ftaoe:.1f}</b> {cmp} expected."
                            f"</p>"
                            f"<p style='font-family:\"IBM Plex Mono\",monospace; font-size:0.8125rem; color:var(--text-muted);'>"
                            f"FTAOE/100: {ftaoe_100:+.2f}  |  {rank_note}"
                            f"</p>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                # FTAOE trend across seasons
                if "player_season_xfta" in _tables:
                    trend = pd.read_sql(
                        "SELECT season, ftaoe_per_100_fga FROM player_season_xfta "
                        "WHERE player_id = ? AND fga >= 100 ORDER BY season",
                        _conn, params=[selected_id],
                    )
                    if len(trend) > 1:
                        fig_trend = go.Figure()
                        colors = ["#E8600A" if v >= 0 else "#0D9488" for v in trend["ftaoe_per_100_fga"]]
                        fig_trend.add_trace(go.Bar(
                            x=trend["season"],
                            y=trend["ftaoe_per_100_fga"],
                            marker_color=colors,
                            text=trend["ftaoe_per_100_fga"].apply(lambda x: f"{x:+.1f}"),
                            textposition="outside",
                            textfont=dict(family="IBM Plex Mono", size=11, color="#A8A29E"),
                        ))
                        fig_trend.update_layout(
                            template="plotly_dark",
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            margin=dict(l=20, r=20, t=30, b=20),
                            height=220,
                            xaxis=dict(title="", tickfont=dict(family="Inter", size=12, color="#A8A29E")),
                            yaxis=dict(
                                title="FTAOE/100",
                                titlefont=dict(family="Inter", size=11, color="#78716C"),
                                tickfont=dict(family="IBM Plex Mono", size=11, color="#A8A29E"),
                                zeroline=True,
                                zerolinecolor="rgba(255,255,255,0.15)",
                                gridcolor="rgba(255,255,255,0.06)",
                            ),
                            showlegend=False,
                        )
                        st.plotly_chart(fig_trend, use_container_width=True)

# ===========================================================================
# Tab 4: Methodology
# ===========================================================================
with tab_methodology:
    st.markdown(
        "<h1 style='font-size:2.25rem; margin-bottom:0.25rem;'>How xFTA works</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:var(--text-muted); font-size:1rem; margin-bottom:1.5rem;'>"
        "Expected free throw attempts are built from 650,000 NBA shots. Here is how the model is calibrated and where it breaks down."
        "</p>",
        unsafe_allow_html=True,
    )

    # ---- Model overview ----------------------------------------------------
    st.markdown(
        "<h2 style='font-size:1.25rem; margin-bottom:0.75rem;'>What the model sees</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size:0.9375rem; line-height:1.65; color:var(--text-secondary); margin-bottom:1rem;'>"
        "xFTA is a gradient-boosted classifier trained on every field-goal attempt from the 2022-23 through 2024-25 regular seasons. "
        "For each shot it predicts the probability that the attempt produces one, two, or three free throws. "
        "The expected value of those outcomes is the xFTA for that shot."
        "</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size:0.9375rem; line-height:1.65; color:var(--text-secondary); margin-bottom:1rem;'>"
        "Features include: shot distance, shot zone, action type (drive, pull-up, catch-and-shoot, etc.), "
        "game situation (score margin, time remaining, in bonus), shooter height and position, "
        "and prior-season foul-drawing tendencies (FTR and drive rate). "
        "The model does <em>not</em> see the defender's identity or the player's reputation with officials."
        "</p>",
        unsafe_allow_html=True,
    )

    st.divider()

    # ---- Global calibration ------------------------------------------------
    st.markdown(
        "<h2 style='font-size:1.25rem; margin-bottom:0.75rem;'>Global calibration</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size:0.9375rem; line-height:1.65; color:var(--text-secondary); margin-bottom:1rem;'>"
        "A well-calibrated model means that when it predicts 2% foul rate, the actual foul rate is about 2% in the long run. "
        "Below, shots are sorted into ten equal buckets (deciles) by predicted xFTA. Each point shows the average predicted vs actual foul rate inside that bucket. "
        "The closer the points hug the diagonal, the more trustworthy the predictions."
        "</p>",
        unsafe_allow_html=True,
    )

    cal_df = q.get_calibration_data(_conn)
    if len(cal_df) > 0:
        max_val = max(cal_df["predicted"].max(), cal_df["actual"].max()) * 1.15
        fig_cal = go.Figure()
        # 45° reference line
        fig_cal.add_trace(go.Scatter(
            x=[0, max_val], y=[0, max_val],
            mode="lines",
            line=dict(color="rgba(255,255,255,0.15)", width=1, dash="dash"),
            name="Perfect calibration",
            hoverinfo="skip",
        ))
        fig_cal.add_trace(go.Scatter(
            x=cal_df["predicted"],
            y=cal_df["actual"],
            mode="markers+lines",
            marker=dict(size=10, color="#E8600A", line=dict(width=1, color="rgba(255,255,255,0.3)")),
            line=dict(color="rgba(232,96,10,0.4)", width=1.5),
            name="Actual",
            hovertemplate=(
                "Decile %{customdata}<br>"
                "Predicted: %{x:.3f}<br>"
                "Actual: %{y:.3f}<extra></extra>"
            ),
            customdata=cal_df["decile"],
        ))
        fig_cal.update_layout(
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=60, r=30, t=20, b=50),
            height=400,
            xaxis=dict(
                title="Predicted xFTA",
                titlefont=dict(family="Inter", size=12, color="#78716C"),
                tickfont=dict(family="IBM Plex Mono", size=11, color="#A8A29E"),
                gridcolor="rgba(255,255,255,0.06)",
                zerolinecolor="rgba(255,255,255,0.1)",
                range=[0, max_val],
            ),
            yaxis=dict(
                title="Actual FTA rate",
                titlefont=dict(family="Inter", size=12, color="#78716C"),
                tickfont=dict(family="IBM Plex Mono", size=11, color="#A8A29E"),
                gridcolor="rgba(255,255,255,0.06)",
                zerolinecolor="rgba(255,255,255,0.1)",
                range=[0, max_val],
                scaleanchor="x",
                scaleratio=1,
            ),
            showlegend=False,
            hoverlabel=dict(
                bgcolor="#292524",
                bordercolor="rgba(255,255,255,0.1)",
                font=dict(family="Inter", size=13, color="#E7E5E4"),
            ),
        )
        st.plotly_chart(fig_cal, use_container_width=True)

        st.markdown(
            "<p style='font-family:\"IBM Plex Mono\",monospace; font-size:0.75rem; color:var(--text-muted); margin-top:-0.5rem;'>"
            f"n = {cal_df['n'].sum():,} shots  |  10 deciles"
            "</p>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ---- Zone calibration --------------------------------------------------
    st.markdown(
        "<h2 style='font-size:1.25rem; margin-bottom:0.75rem;'>Calibration by shot zone</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size:0.9375rem; line-height:1.65; color:var(--text-secondary); margin-bottom:1rem;'>"
        "A model can look well-calibrated globally while being off in specific zones. "
        "Check each zone to see whether the predictions hold up in the corners, the paint, and beyond the arc."
        "</p>",
        unsafe_allow_html=True,
    )

    zone_cal = q.get_zone_calibration(_conn)
    if len(zone_cal) > 0:
        zones = sorted(zone_cal["zone"].unique().tolist())
        zcol1, _ = st.columns([1, 3])
        with zcol1:
            selected_zone = st.selectbox("Zone", zones, key="meth_zone")

        zdf = zone_cal[zone_cal["zone"] == selected_zone].copy()
        max_val_z = max(zdf["predicted"].max(), zdf["actual"].max()) * 1.15
        fig_zone = go.Figure()
        fig_zone.add_trace(go.Scatter(
            x=[0, max_val_z], y=[0, max_val_z],
            mode="lines",
            line=dict(color="rgba(255,255,255,0.15)", width=1, dash="dash"),
            name="Perfect calibration",
            hoverinfo="skip",
        ))
        fig_zone.add_trace(go.Scatter(
            x=zdf["predicted"],
            y=zdf["actual"],
            mode="markers+lines",
            marker=dict(size=10, color="#0D9488", line=dict(width=1, color="rgba(255,255,255,0.3)")),
            line=dict(color="rgba(13,148,136,0.4)", width=1.5),
            name="Actual",
            hovertemplate=(
                "Decile %{customdata}<br>"
                "Predicted: %{x:.3f}<br>"
                "Actual: %{y:.3f}<extra></extra>"
            ),
            customdata=zdf["decile"],
        ))
        fig_zone.update_layout(
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=60, r=30, t=20, b=50),
            height=400,
            xaxis=dict(
                title="Predicted xFTA",
                titlefont=dict(family="Inter", size=12, color="#78716C"),
                tickfont=dict(family="IBM Plex Mono", size=11, color="#A8A29E"),
                gridcolor="rgba(255,255,255,0.06)",
                zerolinecolor="rgba(255,255,255,0.1)",
                range=[0, max_val_z],
            ),
            yaxis=dict(
                title="Actual FTA rate",
                titlefont=dict(family="Inter", size=12, color="#78716C"),
                tickfont=dict(family="IBM Plex Mono", size=11, color="#A8A29E"),
                gridcolor="rgba(255,255,255,0.06)",
                zerolinecolor="rgba(255,255,255,0.1)",
                range=[0, max_val_z],
                scaleanchor="x",
                scaleratio=1,
            ),
            showlegend=False,
            hoverlabel=dict(
                bgcolor="#292524",
                bordercolor="rgba(255,255,255,0.1)",
                font=dict(family="Inter", size=13, color="#E7E5E4"),
            ),
        )
        st.plotly_chart(fig_zone, use_container_width=True)

        st.markdown(
            "<p style='font-family:\"IBM Plex Mono\",monospace; font-size:0.75rem; color:var(--text-muted); margin-top:-0.5rem;'>"
            f"Zone: {selected_zone}  |  n = {zdf['n'].sum():,} shots"
            "</p>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ---- Caveats -----------------------------------------------------------
    st.markdown(
        "<h2 style='font-size:1.25rem; margin-bottom:0.75rem;'>Caveats</h2>",
        unsafe_allow_html=True,
    )

    caveats = [
        (
            "Sample size matters.",
            "A player with 200 shots and a +2.0 FTAOE/100 may simply be lucky. The leaderboard defaults to a 300-FGA minimum, but even that is thin for rare events like foul calls."
        ),
        (
            "Context is partial.",
            "xFTA knows the shot distance and zone, but not whether the defender was in position, whether the player initiated contact, or whether the official had a clear sight line. Some of what we call 'skill' may be situation or officiating variance."
        ),
        (
            "Season-to-season noise.",
            "Foul-drawing rates are sticky but not perfectly so. A player who changes teams, roles, or shot diets can see large swings that are real, not random."
        ),
        (
            "Not all fouls are created equal.",
            "xFTA treats every shooting foul as worth the same 1.5 free throws on average. In reality, and-1s, two-shot fouls, and three-shot fouls have different values. Future versions may model the foul count distribution directly."
        ),
        (
            "No defender identity.",
            "The model does not know who guarded the shot. Drawing fouls against a foul-prone big is different from drawing them against a disciplined wing, but xFTA averages across all defenders."
        ),
    ]

    for title, body in caveats:
        st.markdown(
            f"<div class='glossary-card'>"
            f"<dt>{title}</dt>"
            f"<dd>{body}</dd>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<p style='font-size:0.8125rem; color:var(--text-muted); margin-top:1.5rem;'>"
        "Data: NBA via nba_api  ·  Model: XGBoost  ·  Built by Kevin B"
        "</p>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.sidebar.divider()
st.sidebar.caption(
    "<p style='font-size:0.6875rem; color:var(--text-muted);'>"
    "xFTA v2  ·  Built with Streamlit"
    "</p>",
    unsafe_allow_html=True,
)

_conn.close()
