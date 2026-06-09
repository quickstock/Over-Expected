"""xFTA Dashboard — shooting-foul FTA per 100 vs league average.

Three tabs:
  - Leaderboard  (gap plot, per-100 sorted, filters)
  - Player       (hero card + detail + cumulative arc + context mix)
  - Methodology  (calibration, coefficients, context, caveats)
"""

import sys
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

import streamlit as st
import pandas as pd

from dashboard_v2.styles import CSS
from dashboard_v2 import components as c
from dashboard_v2 import queries as q

from config import DB_PATH, SEASONS


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="xFTA — shooting-foul FTA per 100",
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
      shooting-foul FTA per 100 vs league average
    </span>
  </div>
  <div class="eyebrow" style="display:flex; align-items:center; gap: 0.5rem;">
    <span class="verified">leak verified clean</span>
    <span style="font-weight: 500;">context-adjusted baseline · possession grain</span>
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
# Load real leaderboard data (cached at module level in queries.py)
# ---------------------------------------------------------------------------
lb_df = q.get_leaderboard_data(DB_PATH)

POS_BUCKETS = [
    ("All", "All positions"),
    ("G", "Guards"),
    ("F", "Forwards"),
    ("C", "Centers"),
]


# ===========================================================================
# Tab 1: Leaderboard
# ===========================================================================
with tab_leaderboard:
    st.markdown(
        """
<div style="max-width: 820px; margin-bottom: 1.75rem;">
  <h1 style="font-size: 3.25rem; line-height: 1.02; margin-bottom: 0.875rem;">
    Shooting-foul FTA per 100, vs league average.
  </h1>
  <p style="color: var(--ink-2); font-size: 1.0625rem; line-height: 1.55; max-width: 60ch; font-weight: 400;">
    Sorted by FTAOE per 100 possessions. The line in each row is the gap
    between a player's actual shooting-foul free throws and the
    context-adjusted league baseline — warm when a player draws <em>more</em>
    than the league, cool when <em>fewer</em>.
  </p>
</div>
""",
        unsafe_allow_html=True,
    )

    fcol1, fcol2, fcol3, fcol4 = st.columns([1, 1, 1, 1.4])
    # URL ?min_poss= pre-overrides the slider (used by screenshot tooling)
    qp_min = st.query_params.get("min_poss")
    if isinstance(qp_min, list):
        qp_min = qp_min[0] if qp_min else None
    default_min = int(qp_min) if qp_min and str(qp_min).isdigit() else 300
    default_min = max(100, min(2000, default_min))
    with fcol1:
        sel_season = st.selectbox("Season", ["All"] + SEASONS, key="lb_season")
    with fcol2:
        sel_pos = st.selectbox(
            "Position",
            options=[b[0] for b in POS_BUCKETS],
            format_func=lambda b: dict(POS_BUCKETS)[b],
            key="lb_pos",
        )
    with fcol3:
        min_poss = st.slider("Min possessions", 100, 2000, default_min, 50, key="lb_min_poss")
    with fcol4:
        top_n = st.select_slider("Show top", options=[10, 15, 20, 25, 40], value=25, key="lb_topn")

    filt = q.filter_leaderboard(
        lb_df,
        season=sel_season,
        position_bucket=sel_pos,
        min_possessions=int(min_poss),
    )

    if len(filt) == 0:
        st.markdown(
            "<div class='glass' style='padding: 3rem 2rem; text-align: center;'>"
            "<div class='eyebrow-sm' style='margin-bottom: 0.75rem;'>No matches</div>"
            "<p class='caption'>No players match the current filters. "
            "Try lowering the minimum possessions or removing a position filter.</p></div>",
            unsafe_allow_html=True,
        )
    else:
        # Robust p5/p95 clamp on the diverging scale
        vmin, vmax = c._DELTA_VMIN, c._DELTA_VMAX
        series = filt["ftaoe_per_100"].dropna()
        if len(series) > 0:
            p05 = float(series.quantile(0.05))
            p95 = float(series.quantile(0.95))
            m = max(abs(p05), abs(p95))
            if m > 0:
                vmin, vmax = -m, m
        c.set_delta_domain(vmin, vmax)

        st.markdown(c.render_gap_leaderboard(filt, top_n=int(top_n)), unsafe_allow_html=True)

        st.markdown(
            f"""
<div style="display:flex; gap:2rem; margin-top:1.25rem; align-items:flex-start; flex-wrap:wrap;">
  <div style="flex:1; min-width:280px;">
    <div class="eyebrow-sm" style="margin-bottom:0.4rem;">How to read this</div>
    <p class="caption" style="line-height:1.6; max-width: 56ch;">
      Each row is one player-season. The <b style="color: var(--ink);">solid dot</b>
      is actual free throws from shooting fouls (verified from pbpstats). The
      <b style="color: var(--ink);">hollow dot</b> is the context-adjusted
      league baseline at that player's context mix. The line between them
      is the gap, colored on the diverging scale by sign — warm when the
      player draws more trips than the league baseline, cool when fewer.
      The bar to the right is the percentile within the current filtered
      cohort ({len(filt):,} player-seasons).
    </p>
  </div>
  <div style="flex:0 0 auto; min-width:240px;">
    <div class="eyebrow-sm" style="margin-bottom:0.4rem;">Diverging key</div>
    <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.4rem;">
      <div style="width:18px; height:3px; background: var(--delta-warm-2); border-radius:2px;"></div>
      <span class="caption">positive · above league baseline</span>
    </div>
    <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.4rem;">
      <div style="width:18px; height:3px; background: var(--ink-3); border-radius:2px;"></div>
      <span class="caption">zero · at league baseline</span>
    </div>
    <div style="display:flex; align-items:center; gap:0.6rem;">
      <div style="width:18px; height:3px; background: var(--delta-cool-2); border-radius:2px;"></div>
      <span class="caption">negative · below league baseline</span>
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
    The hero card centers the player in the league distribution. The detail
    card below breaks out actual shooting-foul free throws, the context
    baseline, and the gap. Below: the season's running gap, and the
    context mix the baseline is computed against.
  </p>
</div>
""",
        unsafe_allow_html=True,
    )

    players = q.get_player_options(DB_PATH)
    qp = st.query_params.get("hero_player")
    if isinstance(qp, list):
        qp = qp[0] if qp else None
    if qp in players:
        st.session_state["hero_player"] = qp
    elif "hero_player" not in st.session_state:
        default_idx = players.index("Joel Embiid") if "Joel Embiid" in players else 0
        st.session_state["hero_player"] = players[default_idx]
    sel_player = st.selectbox("Player", players, key="hero_player")

    player_row = q.get_marquee_season(DB_PATH, sel_player)
    if player_row is None:
        st.markdown(
            "<div class='glass'><p class='caption'>Player not found.</p></div>",
            unsafe_allow_html=True,
        )
    else:
        # Cohort percentile (within season, qualified)
        pct = q.season_percentile(lb_df, int(player_row["player_id"]), player_row["season"])
        player_row["percentile"] = pct if pct is not None else 50.0

        # Robust domain from full leaderboard so the ring + distribution share scale
        all_ftaoe = lb_df["ftaoe_per_100"].dropna().tolist()
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

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

        st.markdown(c.render_player_detail(player_row), unsafe_allow_html=True)

        # -- Gate 3A: cumulative arc + Gate 3B: context mix ---------------
        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

        arc_df = q.get_player_arc(
            DB_PATH,
            int(player_row["player_id"]),
            player_row["season"],
        )
        mix_df = q.get_player_context_mix(
            DB_PATH,
            int(player_row["player_id"]),
            player_row["season"],
        )

        col_arc, = st.columns([1])
        with col_arc:
            st.markdown(
                c.render_cumulative_arc(arc_df, sel_player, player_row["season"]),
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

        st.markdown(
            c.render_context_mix(mix_df, sel_player, player_row["season"]),
            unsafe_allow_html=True,
        )

        # All-seasons context — small table at the bottom for cross-season read
        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
        all_seasons = q.get_player_seasons(DB_PATH, int(player_row["player_id"]))
        if len(all_seasons) > 1:
            all_seasons = all_seasons.copy()
            all_seasons["percentile"] = all_seasons.apply(
                lambda r: q.season_percentile(lb_df, int(r["player_id"]), r["season"]),
                axis=1,
            )
            rows_html = []
            for _, r in all_seasons.iterrows():
                ftaoe_100 = float(r["ftaoe_per_100"])
                pole = "pos" if ftaoe_100 > 0 else "neg" if ftaoe_100 < 0 else "zero"
                rows_html.append(
                    f"<tr style='border-bottom: 1px solid var(--rule);'>"
                    f"<td style='padding: 0.6rem 0.5rem; font-family: var(--mono); color: var(--ink-2);'>{r['season']}</td>"
                    f"<td style='padding: 0.6rem 0.5rem; font-family: var(--mono);'>{int(r['possessions']):,}</td>"
                    f"<td style='padding: 0.6rem 0.5rem; font-family: var(--mono);'>{int(r['actual_fta_from_fouls']):,}</td>"
                    f"<td style='padding: 0.6rem 0.5rem; font-family: var(--mono);'>{float(r['xfta_total']):.1f}</td>"
                    f"<td style='padding: 0.6rem 0.5rem; font-family: var(--mono);' class='{pole}'>{('+' if ftaoe_100>0 else ('' if ftaoe_100==0 else '−'))}{abs(ftaoe_100):.2f}</td>"
                    f"<td style='padding: 0.6rem 0.5rem; font-family: var(--mono); color: var(--ink-2);'>"
                    f"{(int(r['percentile']) if r['percentile'] is not None else '—')}"
                    f"{'th' if r['percentile'] is not None else ''}</td>"
                    f"</tr>"
                )
            st.markdown(
                f"""
<div class="glass" style="padding: 1.5rem 1.75rem;">
  <div class="eyebrow-sm" style="margin-bottom: 0.75rem;">{sel_player} · all seasons in the cohort</div>
  <table style="width: 100%; border-collapse: collapse; font-size: 0.875rem;">
    <thead>
      <tr style="border-bottom: 1px solid var(--rule); color: var(--ink-3); text-align: left;">
        <th style="padding: 0.4rem 0.5rem; font-weight: 500;">Season</th>
        <th style="padding: 0.4rem 0.5rem; font-weight: 500;">Poss</th>
        <th style="padding: 0.4rem 0.5rem; font-weight: 500;">Actual FTA</th>
        <th style="padding: 0.4rem 0.5rem; font-weight: 500;">xFTA</th>
        <th style="padding: 0.4rem 0.5rem; font-weight: 500;">FTAOE / 100</th>
        <th style="padding: 0.4rem 0.5rem; font-weight: 500;">Percentile</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
</div>
""",
                unsafe_allow_html=True,
            )


# ===========================================================================
# Tab 3: Methodology
# ===========================================================================
with tab_methodology:
    st.markdown(
        """
<div style="max-width: 820px;">
  <h1 style="font-size: 3rem; line-height: 1.05; margin-bottom: 0.875rem;">How the baseline works</h1>
  <p style="color: var(--ink-2); font-size: 1.0625rem; line-height: 1.55; max-width: 60ch; font-weight: 400;">
    The leaderboard baseline is a context-adjusted league average: a 4-feature
    Poisson GLM fit on possession grain, scored out-of-fold. The baseline moves
    very little with context — the gap is mostly the player.
  </p>
</div>
""",
        unsafe_allow_html=True,
    )

    # -- Gate 3C.1: Calibration -----------------------------------------------
    cal_df = q.get_calibration_data(DB_PATH)
    st.markdown(
        c.render_calibration(cal_df),
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

    # -- Gate 3C.2: Coefficients ----------------------------------------------
    coef_df = q.get_model_coefficients(DB_PATH)
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown(
            c.render_coefficients(coef_df),
            unsafe_allow_html=True,
        )
    with col_right:
        st.markdown(
            """
<div class="glass" style="padding: 1.5rem 1.75rem; height: 100%;">
  <div class="eyebrow-sm" style="margin-bottom: 0.6rem;">Why the baseline is so flat</div>
  <p class="caption" style="line-height: 1.65; max-width: 56ch; font-size: 0.9375rem;">
    The intercept is roughly <span style="font-family: var(--mono);">e<sup>-1.87</sup> ≈ 0.154</span> FTA per possession
    — the league-average rate of going to the line from a shooting foul.
    The four context features move that number only a few percent.
  </p>
  <p class="caption" style="line-height: 1.65; max-width: 56ch; font-size: 0.9375rem; margin-top: 0.875rem;">
    Concretely: a player with an extreme context mix (e.g. Q4+OT only,
    always in bonus) might see a +5% shift off league average. A typical
    player in a typical mix is at the league mean. So the leaderboard
    ranking is driven by <em>who they are</em>, not by <em>where they play</em> —
    which is the point.
  </p>
  <p class="caption" style="line-height: 1.65; max-width: 56ch; font-size: 0.9375rem; margin-top: 0.875rem;">
    A 30% lift would mean the baseline was doing most of the talking.
    A near-zero lift means the baseline does what it should — holds
    the context steady so the rest of the gap is the player.
  </p>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

    # -- Gate 3C.3: Why possession + caveats --------------------------------
    st.markdown(
        """
<div class="bento bento-2-1" style="margin-top: 1rem;">
  <div class="glass" style="padding: 1.75rem;">
    <div class="eyebrow-sm" style="margin-bottom: 0.75rem;">Why the unit is the possession</div>
    <p class="caption" style="line-height: 1.65; max-width: 52ch; font-size: 0.9375rem;">
      A fouled missed shot is <b style="color: var(--ink);">not</b> charged as a field goal
      attempt. The shot never happens. So the right denominator is the
      possession, not the FGA — the baseline answers "at this mix of
      period, clock, score, and bonus, what's the league-average rate of
      a shooting-foul free throw trip?"
    </p>
  </div>
  <div class="glass" style="padding: 1.75rem;">
    <div class="eyebrow-sm" style="margin-bottom: 0.75rem;">What the baseline uses</div>
    <p class="caption" style="line-height: 1.65; max-width: 52ch; font-size: 0.9375rem;">
      Four features, all pre-foul context: <span style="font-family: var(--mono);">period</span>,
      <span style="font-family: var(--mono);">seconds_remaining_in_period</span>,
      <span style="font-family: var(--mono);">score_margin</span>,
      <span style="font-family: var(--mono);">in_bonus</span>. The baseline is
      <b style="color: var(--ink);">context-only</b> — it does not see who the
      player is, the shot location, or how the possession resolved. The
      gap between actual and baseline is the player signal.
    </p>
  </div>
</div>

<div class="glass" style="margin-top: 1rem; padding: 1.75rem;">
  <div class="eyebrow-sm" style="margin-bottom: 0.75rem;">What the gap could mean</div>
  <p class="caption" style="line-height: 1.65; max-width: 72ch; font-size: 0.9375rem;">
    A positive FTAOE could be an attacking style, contact-seeking shot
    selection, or context features the baseline doesn't see. The
    baseline doesn't separate those — and neither does this dashboard.
    A negative gap is the same picture from the other side. The
    percentile bar is descriptive, not causal.
  </p>
  <p class="caption" style="line-height: 1.65; max-width: 72ch; font-size: 0.9375rem; margin-top: 0.875rem;">
    <b style="color: var(--ink);">What the baseline can't see.</b> Pre-foul context only.
    No shot location, no play-type, no defender identity, no game script.
    A player who lives at the rim in traffic has the same baseline
    as a spot-up shooter with identical period/clock/margin/bonus. If a
    player's FTAOE is being driven by where they shoot from, the
    baseline misses it. That omission is intentional — the alternative
    was a leak.
  </p>
  <p class="caption" style="line-height: 1.65; max-width: 72ch; font-size: 0.9375rem; margin-top: 0.875rem;">
    <b style="color: var(--ink);">OOF under-prediction.</b> The leaderboard is
    scored on out-of-fold predictions — each season's possessions are
    predicted by a baseline fit on the other two seasons. A small (~7%)
    under-prediction in the top decile is honest tail compression and
    stays. It would be misleading to multiply it away. The calibration
    view above is where that lives.
  </p>
  <p class="caption" style="line-height: 1.65; max-width: 72ch; font-size: 0.9375rem; margin-top: 0.875rem;">
    <b style="color: var(--ink);">Refit note.</b> The earlier baseline carried
    a leak (action_type + shot_zone_basic missingness encoded possession
    resolution, inflating apparent lift to ~25%). The current baseline
    dropped those features. Lift on the same metric dropped to ~0.1%.
    Top-20 overlap with the leaky leaderboard is 15/20. Spearman rank
    correlation is 0.887. The big movers were players whose shot
    profiles the leaky baseline was secretly memorizing.
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
<div class="brand-tagline">shooting-foul FTA per 100</div>

<p style="font-size: 0.875rem; line-height: 1.6; color: var(--ink-2); max-width: 28ch; font-weight: 400;">
  A player's shooting-foul free throws per 100 possessions, compared
  to a context-adjusted league baseline. The gap is what the player
  is doing differently.
</p>

<div style="height: 1.75rem;"></div>

<div class="sidebar-meta" style="margin-bottom: 0.5rem;">DATA</div>
<p class="caption" style="margin-bottom: 1rem;">
  725,085 possessions · 3 seasons · NBA via nba_api / pbpstats
</p>

<div class="sidebar-meta" style="margin-bottom: 0.5rem;">BASELINE</div>
<p class="caption" style="margin-bottom: 1rem;">
  4-feature Poisson GLM · possession grain · 3-fold OOF
</p>

<div class="sidebar-meta" style="margin-bottom: 0.5rem;">STATUS</div>
<p class="caption" style="margin-bottom: 0.25rem;">
  <span class="verified">leak verified clean</span>
</p>
<p class="caption" style="line-height: 1.55;">
  Refit on 4 pre-foul features. OOF Poisson deviance lift: ~0.1%.
  Baseline moves very little with context.
</p>
""",
        unsafe_allow_html=True,
    )
