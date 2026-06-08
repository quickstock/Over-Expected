"""xFTA Dashboard — Gate 1 reskin, Apple Sport Analytics aesthetic.

Re-skin on top of the existing data layer. Wires to fixtures.py (not
real data) per Gate 1 brief. Real-data wiring, cumulative arc, and
methodology content come after the model refit.
"""

import sys
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

import streamlit as st
import pandas as pd

from dashboard_v2.styles import CSS
from dashboard_v2 import components as c
from dashboard_v2 import fixtures as fix


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="xFTA — expected free throw attempts",
    page_icon="•",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Inject design system
# ---------------------------------------------------------------------------
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Top brand strip
# ---------------------------------------------------------------------------
st.markdown(
    """
<div style="display:flex; align-items:center; justify-content: space-between; padding: 0.5rem 0 1.5rem 0;">
  <div style="display:flex; align-items: baseline; gap: 0.5rem;">
    <div class="brand-mark" style="margin-bottom: 0;">
      <span class="dot"></span>
      <span class="mark">xFTA</span>
    </div>
    <span style="font-family: var(--sans); font-size: 0.6875rem; color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.12em; font-weight: 600; margin-left: 0.75rem;">
      expected free throw attempts
    </span>
  </div>
  <div class="eyebrow" style="display:flex; align-items:center; gap: 0.5rem;">
    <span class="prov">provisional</span>
    <span style="font-weight: 500;">FTAOE pending model refit</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_leaderboard, tab_player, tab_methodology = st.tabs([
    "Leaderboard",
    "Player",
    "Methodology",
])


# ---------------------------------------------------------------------------
# Load fixture data
# ---------------------------------------------------------------------------
lb_df = fix.get_fixture_leaderboard()
SEASONS = ["2022-23", "2023-24", "2024-25"]
POSITIONS = ["Guard", "Forward", "Center"]


# ===========================================================================
# Tab 1: Leaderboard
# ===========================================================================
with tab_leaderboard:
    st.markdown(
        """
<div style="max-width: 820px; margin-bottom: 1.75rem;">
  <h1 style="font-size: 3.25rem; line-height: 1.02; margin-bottom: 0.875rem;">
    Who draws more fouls than their shot profile predicts?
  </h1>
  <p style="color: var(--ink-2); font-size: 1.0625rem; line-height: 1.55; max-width: 60ch; font-weight: 400;">
    Sorted by FTAOE per 100 possessions. The line in each row is the gap between
    a player's actual shooting-foul free throws and the model's expected baseline —
    colored warm when a player draws <em>more</em>, cool when <em>fewer</em>.
  </p>
</div>
""",
        unsafe_allow_html=True,
    )

    fcol1, fcol2, fcol3, fcol4 = st.columns([1, 1, 1, 1.4])
    with fcol1:
        sel_season = st.selectbox("Season", ["All"] + SEASONS, key="lb_season")
    with fcol2:
        sel_pos = st.selectbox("Position", ["All"] + POSITIONS, key="lb_pos")
    with fcol3:
        min_fga = st.slider("Min FGA", 100, 1500, 300, 50, key="lb_min_fga")
    with fcol4:
        top_n = st.select_slider("Show top", options=[10, 15, 20, 25, 40], value=25, key="lb_topn")

    df = lb_df.copy()
    if sel_season != "All":
        df = df[df["season"] == sel_season]
    if sel_pos != "All":
        df = df[df["position"].str.contains(sel_pos, na=False)]
    df = df[df["fga"] >= min_fga]

    if len(df) == 0:
        st.markdown(
            "<div class='glass' style='padding: 3rem 2rem; text-align: center;'>"
            "<div class='eyebrow-sm' style='margin-bottom: 0.75rem;'>No matches</div>"
            "<p class='caption'>No players match the current filters. "
            "Try lowering the minimum FGA or removing a position filter.</p></div>",
            unsafe_allow_html=True,
        )
    else:
        # Robust p5/p95 clamp on the diverging scale
        vmin, vmax = c._DELTA_VMIN, c._DELTA_VMAX
        if "ftaoe_per_100_fga" in df.columns:
            series = df["ftaoe_per_100_fga"].dropna()
            if len(series) > 0:
                p05 = float(series.quantile(0.05))
                p95 = float(series.quantile(0.95))
                m = max(abs(p05), abs(p95))
                if m > 0:
                    vmin, vmax = -m, m
        c.set_delta_domain(vmin, vmax)

        st.markdown(c.render_gap_leaderboard(df, top_n=int(top_n)), unsafe_allow_html=True)

        st.markdown(
            f"""
<div style="display:flex; gap:2rem; margin-top:1.25rem; align-items:flex-start; flex-wrap:wrap;">
  <div style="flex:1; min-width:280px;">
    <div class="eyebrow-sm" style="margin-bottom:0.4rem;">How to read this</div>
    <p class="caption" style="line-height:1.6; max-width: 56ch;">
      Each row is one player-season. The <b style="color: var(--ink);">solid dot</b>
      is actual free throws from fouls (verified). The <b style="color: var(--ink);">hollow dot</b>
      is the model's expected baseline (provisional). The line between them
      is the gap, colored on the diverging scale by sign — warm when the player
      draws more fouls than expected, cool when fewer. The bar to the right is
      the percentile within the current filtered cohort ({len(df):,} player-seasons).
    </p>
  </div>
  <div style="flex:0 0 auto; min-width:240px;">
    <div class="eyebrow-sm" style="margin-bottom:0.4rem;">Diverging key</div>
    <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.4rem;">
      <div style="width:18px; height:3px; background: var(--delta-warm-2); border-radius:2px;"></div>
      <span class="caption">positive · draws more</span>
    </div>
    <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.4rem;">
      <div style="width:18px; height:3px; background: var(--ink-3); border-radius:2px;"></div>
      <span class="caption">zero · league average</span>
    </div>
    <div style="display:flex; align-items:center; gap:0.6rem;">
      <div style="width:18px; height:3px; background: var(--delta-cool-2); border-radius:2px;"></div>
      <span class="caption">negative · draws fewer</span>
    </div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )


# ===========================================================================
# Tab 2: Player
# ===========================================================================
with tab_player:
    st.markdown(
        """
<div style="max-width: 820px; margin-bottom: 1.5rem;">
  <h1 style="font-size: 3.25rem; line-height: 1.02; margin-bottom: 0.875rem;">
    A closer look at one player.
  </h1>
  <p style="color: var(--ink-2); font-size: 1.0625rem; line-height: 1.55; max-width: 60ch; font-weight: 400;">
    The league hero card centers the player's position in the distribution.
    The detail card below breaks out actual free throws earned, the xFTA
    baseline, and the gap.
  </p>
</div>
""",
        unsafe_allow_html=True,
    )

    players = sorted(fix.get_fixture_leaderboard()["player_name"].unique().tolist())
    # URL ?hero_player=Foo+Bar pre-selects
    qp = st.query_params.get("hero_player")
    if isinstance(qp, list):
        qp = qp[0] if qp else None
    if "hero_player" not in st.session_state and qp in players:
        st.session_state["hero_player"] = qp
    default_idx = players.index("Joel Embiid") if "Joel Embiid" in players else 0
    sel_player = st.selectbox("Player", players, index=default_idx, key="hero_player")

    player_row = fix.get_fixture_player(sel_player)
    if player_row is None:
        st.markdown(
            "<div class='glass'><p class='caption'>Player not found.</p></div>",
            unsafe_allow_html=True,
        )
    else:
        # Robust domain from fixture data so the ring + distribution share scale
        all_ftaoe = (
            lb_df["ftaoe_per_100_fga"].dropna().tolist()
            if "ftaoe_per_100_fga" in lb_df.columns
            else []
        )
        vmin, vmax = c._DELTA_VMIN, c._DELTA_VMAX
        if all_ftaoe:
            s = pd.Series(all_ftaoe)
            p05 = float(s.quantile(0.05))
            p95 = float(s.quantile(0.95))
            m = max(abs(p05), abs(p95))
            if m > 0:
                vmin, vmax = -m, m
        c.set_delta_domain(vmin, vmax)

        st.markdown(
            c.render_league_hero(player_row, all_ftaoe),
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div style='height: 1rem;'></div>",
            unsafe_allow_html=True,
        )

        st.markdown(c.render_player_detail(player_row), unsafe_allow_html=True)


# ===========================================================================
# Tab 3: Methodology (stub — full content after refit)
# ===========================================================================
with tab_methodology:
    st.markdown(
        """
<div style="max-width: 820px;">
  <h1 style="font-size: 3rem; line-height: 1.05; margin-bottom: 0.875rem;">How xFTA works</h1>
  <p style="color: var(--ink-2); font-size: 1.0625rem; line-height: 1.55; max-width: 60ch; font-weight: 400;">
    The full methodology page — calibration curve, feature importances, and the
    fouled-miss-isn't-an-FGA explainer — is scheduled for the post-refit gate.
    Until then, the short version.
  </p>
</div>

<div class="bento bento-2-1" style="margin-top: 2rem;">
  <div class="glass" style="padding: 1.75rem;">
    <div class="eyebrow-sm" style="margin-bottom: 0.75rem;">The unit is the possession</div>
    <p class="caption" style="line-height: 1.65; max-width: 52ch; font-size: 0.9375rem;">
      A fouled missed shot is <b style="color: var(--ink);">not</b> charged as a field goal
      attempt. The shot never happens. So the right denominator is the
      possession, not the FGA — the model answers "given this shot-context
      cocktail, what's the chance the possession ends in a shooting-foul free throw trip?"
    </p>
  </div>
  <div class="glass" style="padding: 1.75rem;">
    <div class="eyebrow-sm" style="margin-bottom: 0.75rem;">What the model sees</div>
    <p class="caption" style="line-height: 1.65; max-width: 52ch; font-size: 0.9375rem;">
      Shot location, period, clock, score margin, bonus state, home/away.
      The model is <b style="color: var(--ink);">context-only</b> — it does not
      see who the player is. The gap between actual and expected is the
      signal.
    </p>
  </div>
</div>

<div class="glass" style="margin-top: 1rem; padding: 1.75rem;">
  <div class="eyebrow-sm" style="margin-bottom: 0.75rem;">What the gap could mean</div>
  <p class="caption" style="line-height: 1.65; max-width: 72ch; font-size: 0.9375rem;">
      A positive FTAOE could be: real skill at drawing contact, an
      attacking style the model under-weights, or features the model
      doesn't see. It could also reflect referee tendencies toward a player.
      The model doesn't distinguish those. Bias-vs-skill is unresolved
      and labeled as such.
  </p>
  <p class="caption" style="line-height: 1.65; max-width: 72ch; font-size: 0.9375rem; margin-top: 0.875rem;">
      <b style="color: var(--ink);">Provisional</b> — the model is being refit to remove a
      feature leak. The leaderboard, distribution, and percentile numbers carry
      a provisional tag until the refit lands. Verified data (actual FTA,
      possessions) renders final.
  </p>
</div>
""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
<div class="brand-mark">
  <span class="dot"></span>
  <span class="mark">xFTA</span>
</div>
<div class="brand-tagline">expected free throw attempts</div>

<p style="font-size: 0.875rem; line-height: 1.6; color: var(--ink-2); max-width: 28ch; font-weight: 400;">
  The gap between a player's actual free throws and what their shot profile
  should produce. That gap is foul-drawing craft.
</p>

<div style="height: 1.75rem;"></div>

<div class="sidebar-meta" style="margin-bottom: 0.5rem;">DATA</div>
<p class="caption" style="margin-bottom: 1rem;">
  650,007 shots · 3 seasons · NBA via nba_api
</p>

<div class="sidebar-meta" style="margin-bottom: 0.5rem;">MODEL</div>
<p class="caption" style="margin-bottom: 1rem;">
  XGBoost · context-only
</p>

<div class="sidebar-meta" style="margin-bottom: 0.5rem;">STATUS</div>
<p class="caption" style="margin-bottom: 0.25rem;">
  <span class="prov">provisional</span>
</p>
<p class="caption" style="line-height: 1.55;">
  FTAOE pending refit to remove a feature leak. Actual FTA / capture data is verified.
</p>
""",
        unsafe_allow_html=True,
    )
