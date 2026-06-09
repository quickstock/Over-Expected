"""Custom HTML components — Apple Sport Analytics / bento.

Re-skin on top of the existing data layer. Every component traces back
to a real column in xfta.db. No invented metrics. Diverging scale is
the single source of truth for the data encoding.
"""

from __future__ import annotations

import math
import pandas as pd


# The diverging scale stops, RGB. Mirrors --delta-* CSS vars.
_DELTA_STOPS = [
    (0.00, 17, 64, 76),     # --delta-cool-3
    (0.20, 45, 122, 140),   # --delta-cool-2
    (0.40, 111, 168, 184),  # --delta-cool-1
    (0.50, 46, 46, 50),     # --delta-zero
    (0.60, 228, 138, 80),   # --delta-warm-1
    (0.80, 194, 66, 10),    # --delta-warm-2
    (1.00, 156, 46, 4),     # --delta-warm-3
]

_DELTA_VMIN = -7.5
_DELTA_VMAX = 7.5


def set_delta_domain(vmin: float, vmax: float) -> None:
    global _DELTA_VMIN, _DELTA_VMAX
    if vmax <= vmin:
        vmax = vmin + 1.0
    _DELTA_VMIN = float(vmin)
    _DELTA_VMAX = float(vmax)


def _interp(value: float) -> tuple[int, int, int]:
    """Map a value to (r, g, b) on the diverging scale. Mid = neutral."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return (46, 46, 50)
    clamped = max(_DELTA_VMIN, min(_DELTA_VMAX, float(value)))
    ratio = (clamped - _DELTA_VMIN) / (_DELTA_VMAX - _DELTA_VMIN)
    lo, hi = _DELTA_STOPS[0], _DELTA_STOPS[-1]
    for i in range(len(_DELTA_STOPS) - 1):
        a, b = _DELTA_STOPS[i], _DELTA_STOPS[i + 1]
        if a[0] <= ratio <= b[0]:
            lo, hi = a, b
            break
    span = hi[0] - lo[0] or 1
    t = (ratio - lo[0]) / span
    r = int(lo[1] + (hi[1] - lo[1]) * t)
    g = int(lo[2] + (hi[2] - lo[2]) * t)
    b = int(lo[3] + (hi[3] - lo[3]) * t)
    return (r, g, b)


def _delta_text_color(value: float) -> str:
    """Saturated rgb for text — picks the deeper pole of the scale."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "rgb(168,168,173)"
    r, g, b = _interp(value)
    return f"rgb({r},{g},{b})"


def _delta_pole_class(value: float) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "zero"
    if value > 0:
        return "pos"
    if value < 0:
        return "neg"
    return "zero"


# --- formatters ----------------------------------------------------------
def _fmt_signed(value, decimals: int = 1) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    v = float(value)
    if v > 0:
        return f"+{v:.{decimals}f}"
    if v < 0:
        return f"−{abs(v):.{decimals}f}"
    return f"{0:.{decimals}f}"


def _fmt_int(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{int(round(float(value))):,}"


def _fmt_pct(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{int(round(float(value)))}th"


# =====================================================================
# 1. LEAGUE HERO — percentile ring (real, bounded 0-100) + distribution strip
# =====================================================================
def render_league_hero(player: dict, all_ftaoe: list[float]) -> str:
    """League hero card. Two bento cells in one row:
       - Left: a percentile ring (real, 0-100, bounded) for the selected player.
       - Right: a league FTAOE distribution strip with the player's position
         marked and the league mean + zero line.

    No invented metrics. Ring fill follows the diverging scale by sign of
    the player's FTAOE.
    """
    ftaoe = float(player.get("ftaoe_per_100", 0) or 0)
    pct = float(player.get("percentile", 50) or 50)
    pct = max(0, min(100, pct))

    # Ring geometry — single SVG, stroke-dasharray draws the arc
    size = 240
    cx, cy = size / 2, size / 2
    radius = 96
    stroke = 14
    circumference = 2 * math.pi * radius
    dash = (pct / 100) * circumference

    r, g, b = _interp(ftaoe)
    ring_color = f"rgb({r},{g},{b})"
    pole = _delta_pole_class(ftaoe)

    # Ring caption — plain English
    if ftaoe >= 0:
        cap = "above league baseline"
    else:
        cap = "below league baseline"

    # Distribution strip — histogram of FTAOE in 24 bins
    bins = 32
    lo, hi = _DELTA_VMIN, _DELTA_VMAX
    counts = [0] * bins
    for v in all_ftaoe:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        r0 = max(0.0, min(1.0, (float(v) - lo) / (hi - lo)))
        idx = min(bins - 1, int(r0 * bins))
        counts[idx] += 1
    max_count = max(counts) if counts else 1

    bin_w = 100 / bins
    bars = []
    for i, c in enumerate(counts):
        if c == 0:
            continue
        h = (c / max_count) * 38
        x = i * bin_w
        # bin center → ratio → diverging color
        center_ratio = (i + 0.5) / bins
        v_at_center = lo + center_ratio * (hi - lo)
        cr, cg, cb = _interp(v_at_center)
        bars.append(
            f'<rect x="{x:.2f}%" y="{56 - h:.1f}" width="{bin_w * 0.95:.2f}%" '
            f'height="{h:.1f}" rx="0.6" fill="rgba({cr},{cg},{cb},0.85)"/>'
        )

    # Player marker on strip
    player_ratio = max(0.0, min(1.0, (ftaoe - lo) / (hi - lo)))
    marker_x = player_ratio * 100
    mean_x = (0 - lo) / (hi - lo) * 100  # zero line

    return f"""
<div class="glass" style="padding: 1.5rem 1.75rem;">
  <div class="bento" style="grid-template-columns: 260px 1fr; gap: 1.25rem; align-items: stretch;">
    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap: 0.25rem;">
      <div class="eyebrow-sm" style="margin-bottom: 0.25rem;">FTAOE percentile</div>
      <div class="ring-wrap" style="max-width: 200px; aspect-ratio: 1;">
        <svg viewBox="0 0 {size} {size}" preserveAspectRatio="xMidYMid meet">
          <defs>
            <linearGradient id="ringFade" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="{ring_color}" stop-opacity="0.4"/>
              <stop offset="100%" stop-color="{ring_color}" stop-opacity="1"/>
            </linearGradient>
          </defs>
          <circle cx="{cx}" cy="{cy}" r="{radius}"
            fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="{stroke}"/>
          <circle cx="{cx}" cy="{cy}" r="{radius}"
            fill="none" stroke="url(#ringFade)" stroke-width="{stroke}"
            stroke-linecap="round"
            stroke-dasharray="{dash:.2f} {circumference:.2f}"
            transform="rotate(-90 {cx} {cy})"/>
        </svg>
        <div class="ring-label">
          <div class="ring-value {pole}">{int(round(pct))}<span class="pct-mark">th</span></div>
          <div class="ring-caption">percentile</div>
        </div>
      </div>
      <div class="caption" style="text-align:center; margin-top: 0.5rem; max-width: 22ch;">
        Within the qualified cohort — {cap}.
      </div>
    </div>

    <div style="display:flex; flex-direction:column; gap: 0.625rem; justify-content:center;">
      <div class="eyebrow-sm">League FTAOE distribution · per 100 possessions</div>
      <div class="dist-strip">
        <svg viewBox="0 0 100 56" preserveAspectRatio="none" style="width:100%; height:56px;">
          <line x1="{mean_x}" y1="0" x2="{mean_x}" y2="56" stroke="rgba(255,255,255,0.18)" stroke-width="0.4" stroke-dasharray="1 1"/>
          {''.join(bars)}
          <line x1="{marker_x}" y1="2" x2="{marker_x}" y2="54" stroke="var(--ink)" stroke-width="0.6"/>
          <circle cx="{marker_x}" cy="2" r="1.6" fill="var(--ink)"/>
          <circle cx="{marker_x}" cy="54" r="1.6" fill="var(--ink)"/>
        </svg>
      </div>
      <div style="display:flex; justify-content: space-between; font-family: var(--mono); font-size: 0.6875rem; color: var(--ink-3);">
        <span>below baseline</span>
        <span style="opacity: 0.5;">| zero</span>
        <span>above baseline</span>
      </div>
      <div style="display:flex; gap: 1.5rem; margin-top: 0.5rem;">
        <div>
          <div class="eyebrow-sm">This player</div>
          <div class="display-sm {_delta_pole_class(ftaoe) if ftaoe else 'zero'}" style="margin-top: 0.25rem;">{_fmt_signed(ftaoe)}</div>
        </div>
        <div>
          <div class="eyebrow-sm">League mean</div>
          <div class="display-sm" style="margin-top: 0.25rem; color: var(--ink-2);">0.0</div>
        </div>
        <div>
          <div class="eyebrow-sm">Sign</div>
          <div class="display-sm" style="margin-top: 0.25rem;">{'+' if ftaoe > 0 else '−' if ftaoe < 0 else '·'}</div>
        </div>
      </div>
    </div>
  </div>
</div>
"""


# =====================================================================
# 2. GAP LEADERBOARD — comet / dot plot rows
# =====================================================================
def render_gap_leaderboard(df: pd.DataFrame, top_n: int = 25) -> str:
    """Each row: rank · name · gap plot (actual dot, baseline dot, line
    colored by sign of (actual − baseline)) · inline percentile bar.

    The gap plot is the heart of the row. Inline SVG.
    """
    if len(df) == 0:
        return "<div class='glass'><p class='caption'>No players match the filters.</p></div>"

    # Accept both shapes — fixture uses ftaoe_per_100_fga, real data uses ftaoe_per_100
    rate_col = "ftaoe_per_100" if "ftaoe_per_100" in df.columns else "ftaoe_per_100_fga"
    df = df.sort_values(rate_col, ascending=False).head(int(top_n)).reset_index(drop=True)
    df["__rank"] = df.index + 1

    # Compute the plot's x-axis bounds from the cohort. Robust — use
    # the larger of (max actual) and (max baseline) so both dots fit.
    actual_max = float(df["actual_fta_from_fouls"].max() or 1)
    expected_max = float(df["xfta_total"].max() or 1)
    plot_max = max(actual_max, expected_max) * 1.05

    rows = []
    for _, r in df.iterrows():
        actual = float(r["actual_fta_from_fouls"])
        expected = float(r["xfta_total"])
        delta = actual - expected
        pct = max(0, min(100, float(r.get("percentile", 0))))
        sign_class = "pos" if delta > 0 else "neg" if delta < 0 else "zero"
        sign_glyph = "+" if delta > 0 else "−" if delta < 0 else "·"
        sign_color = _delta_text_color(delta)

        ax = (actual / plot_max) * 100
        ex = (expected / plot_max) * 100

        # The connecting line color follows the sign of the gap (the data)
        gap_stroke = sign_color
        gap_opacity = 0.55 if delta != 0 else 0.2

        plot_svg = f"""
<svg viewBox="0 0 100 36" preserveAspectRatio="none" class="gap-plot-svg">
  <!-- baseline rule -->
  <line x1="0" y1="18" x2="100" y2="18" stroke="rgba(255,255,255,0.05)" stroke-width="0.4"/>
  <!-- context baseline mark -->
  <circle cx="{ex:.2f}" cy="18" r="3.6" fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="0.8" stroke-dasharray="1.2 1.2"/>
  <!-- actual mark — verified treatment: solid filled -->
  <circle cx="{ax:.2f}" cy="18" r="3.6" fill="var(--ink)"/>
  <!-- connecting line, colored by sign of the gap -->
  <line x1="{min(ax, ex):.2f}" y1="18" x2="{max(ax, ex):.2f}" y2="18"
    stroke="{gap_stroke}" stroke-width="1.2" opacity="{gap_opacity}"/>
</svg>"""

        rows.append(
            f"""
<tr class="gap-row">
  <td class="gap-rank">{int(r['__rank']):02d}</td>
  <td>
    <div class="gap-name">
      <span class="delta-sign {sign_class}">{sign_glyph}</span>{r['player_name']}
      <span class="sub">· {r.get('pos_bucket','—')} · {r['season']}</span>
    </div>
  </td>
  <td class="gap-num gap-hide-mobile"><span class="val">{_fmt_int(actual)}</span> <span style="color: var(--ink-4);">·</span> actual <span class="verified">· verified</span></td>
  <td class="gap-num gap-hide-mobile"><span class="val">{expected:.1f}</span> <span style="color: var(--ink-4);">·</span> baseline</td>
  <td>{plot_svg}</td>
  <td class="gap-pctbar">
    <div class="gap-pctbar-track">
      <div class="gap-pctbar-fill" style="width: {pct:.1f}%;"></div>
    </div>
    <div class="gap-pctbar-label">{_fmt_pct(pct)} pctile</div>
  </td>
</tr>
"""
        )

    return f"""
<div class="glass" style="padding: 1.25rem 1.5rem;">
  <div style="display:flex; align-items: baseline; justify-content: space-between; margin-bottom: 1.25rem;">
    <div>
      <div class="eyebrow-sm" style="margin-bottom: 0.25rem;">The gap leaderboard</div>
      <div class="caption">Each row: solid dot = actual FTA from fouls · hollow = context baseline · line color = sign of the gap</div>
    </div>
    <div style="display:flex; gap: 1.5rem; align-items: center; font-size: 0.75rem; color: var(--ink-3);">
      <span style="display:flex; align-items: center; gap: 0.4rem;">
        <span style="width: 8px; height: 8px; border-radius: 50%; background: var(--ink);"></span> actual · verified
      </span>
      <span style="display:flex; align-items: center; gap: 0.4rem;">
        <span style="width: 8px; height: 8px; border-radius: 50%; border: 1px dashed rgba(255,255,255,0.5);"></span> baseline
      </span>
    </div>
  </div>
  <table class="gap-table" role="table" aria-label="FTAOE gap leaderboard">
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</div>
"""


# =====================================================================
# 3. PLAYER DETAIL — expanding bento
# =====================================================================
def render_player_detail(player: dict) -> str:
    """The detail view. Massive delta (dominant), percentile, plain-English
    sentence. Four stat tiles: actual (verified), context baseline,
    FTAOE, percentile.

    No fabricated physics. No invented playstyle stats. Shot diet /
    cumulative arc / methodology are post-refit gates.
    """
    ftaoe_100 = float(player.get("ftaoe_per_100", 0) or 0)
    ftaoe_total = float(player.get("ftaoe", 0) or 0)
    actual = float(player.get("actual_fta_from_fouls", 0) or 0)
    xfta = float(player.get("xfta_total", 0) or 0)
    possessions = int(player.get("possessions", 0) or 0)
    season = player.get("season", "")
    name = player.get("player_name", "—")
    pos = player.get("position", "—")
    pct = float(player.get("percentile", 50) or 50)

    pole = _delta_pole_class(ftaoe_100)
    abs_delta = abs(ftaoe_100)
    direction = "above" if ftaoe_100 >= 0 else "below"

    if abs_delta >= 5:
        strength = "well above"
    elif abs_delta >= 2.5:
        strength = "above"
    elif abs_delta >= 1:
        strength = "slightly above"
    elif abs_delta >= -1:
        strength = "in line with"
    elif abs_delta >= -2.5:
        strength = "slightly below"
    elif abs_delta >= -5:
        strength = "below"
    else:
        strength = "well below"

    sentence = (
        f"sits in the <b>{int(round(pct))}th percentile</b> of the cohort — "
        f"<b>{abs_delta:.1f} FTA/100 {direction}</b> the context-adjusted baseline."
    )

    ftaoe_total_class = "pos" if ftaoe_total > 0 else "neg" if ftaoe_total < 0 else "zero"
    pct_class = "pos" if pct >= 60 else "neg" if pct <= 40 else "zero"

    return f"""
<div class="glass" style="padding: 2rem 2.25rem;">
  <div class="detail-grid">
    <div style="display:flex; flex-direction: column; gap: 0.75rem;">
      <div>
        <div class="eyebrow-sm" style="margin-bottom: 0.5rem;">
          FTAOE · per 100 possessions
        </div>
        <h1 class="detail-name">{name}</h1>
        <div class="detail-sub">{pos} · {season} · {_fmt_int(possessions)} possessions</div>
      </div>
      <div>
        <div class="detail-headline {pole}">{_fmt_signed(ftaoe_100)}</div>
        <div class="detail-sentence">{sentence}</div>
      </div>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; align-content: start;">
      <div class="stat-tile">
        <div class="stat-tile-label">Actual FTA from fouls</div>
        <div class="stat-tile-value">{_fmt_int(actual)}</div>
        <div class="stat-tile-sub">free throws earned · <span class="verified">verified</span></div>
      </div>
      <div class="stat-tile">
        <div class="stat-tile-label">Context baseline</div>
        <div class="stat-tile-value">{xfta:.1f}</div>
        <div class="stat-tile-sub">at this player's context mix</div>
      </div>
      <div class="stat-tile">
        <div class="stat-tile-label">FTAOE (absolute)</div>
        <div class="stat-tile-value {ftaoe_total_class}">{_fmt_signed(ftaoe_total)}</div>
        <div class="stat-tile-sub">actual − baseline</div>
      </div>
      <div class="stat-tile">
        <div class="stat-tile-label">Percentile</div>
        <div class="stat-tile-value {pct_class}">{int(round(pct))}<span style="font-size: 1.125rem; color: var(--ink-3); margin-left: 2px;">th</span></div>
        <div class="stat-tile-sub">within qualified cohort</div>
      </div>
    </div>
  </div>

  <div style="margin-top: 1.75rem; padding-top: 1.25rem; border-top: 1px solid var(--rule); display:flex; gap: 1.5rem; flex-wrap: wrap;">
    <div class="caption" style="max-width: 64ch;">
      <b style="color: var(--ink); font-weight: 600;">What this number means.</b>
      The gap between actual free throws earned and the model's expected baseline.
      The model is context-only (period, clock, score, bonus).
      It does not see who the player is.
    </div>
  </div>
</div>
"""


# =====================================================================
# 4. CUMULATIVE ARC — xG-style running sum of (actual − xfta)
# =====================================================================
def render_cumulative_arc(arc_df, player_name: str, season: str) -> str:
    """For the selected (player, season), show the running sum of
    (actual sfta − baseline xfta) over the season's possessions, in
    possession order. The line is colored by sign at each point — cool
    when below the baseline, warm when above. The end-of-season
    point shows the final ftaoe magnitude. The shape tells you whether
    the gap accumulated steadily or in bursts.
    """
    if len(arc_df) == 0:
        return "<div class='glass'><p class='caption'>No possessions found for this player-season.</p></div>"

    n = len(arc_df)
    cum = arc_df["cum_delta"].astype(float).tolist()
    final_delta = cum[-1]
    final_color = _delta_text_color(final_delta)
    pole = _delta_pole_class(final_delta)

    if n > 1:
        ymin = min(cum)
        ymax = max(cum)
        yspan = ymax - ymin if ymax > ymin else 1
        ypad = yspan * 0.18
        ymin -= ypad
        ymax += ypad
        yspan = ymax - ymin
        zero_y = 60 - (0 - ymin) / yspan * 60

        pts = []
        for i, v in enumerate(cum):
            x = (i / (n - 1)) * 100
            y = 60 - (v - ymin) / yspan * 60
            pts.append((x, y))

        def _seg_color(v):
            if abs(v) < 0.5:
                return "var(--ink-3)"
            return _delta_text_color(v)

        segs_neg, segs_flat, segs_pos = [], [], []
        for i in range(1, len(pts)):
            x1, y1 = pts[i-1]
            x2, y2 = pts[i]
            mid = (cum[i-1] + cum[i]) / 2
            c = _seg_color(mid)
            s = (
                f'<polyline points="{x1:.2f},{y1:.2f} {x2:.2f},{y2:.2f}" '
                f'stroke="{c}" stroke-width="1.4" fill="none" opacity="0.95"/>'
            )
            if abs(mid) < 0.5:
                segs_flat.append(s)
            elif mid > 0:
                segs_pos.append(s)
            else:
                segs_neg.append(s)

        end_x, end_y = pts[-1]

        y_labels = []
        for v in (ymin, (ymin + ymax) / 2, ymax):
            y_pos = 60 - (v - ymin) / yspan * 60
            y_labels.append(
                f'<text x="0" y="{y_pos-0.6:.2f}" font-size="3" fill="rgba(255,255,255,0.45)" '
                f'font-family="var(--mono)">{v:+.0f}</text>'
            )
        x_labels = [
            f'<text x="0" y="65" font-size="3" fill="rgba(255,255,255,0.45)" '
            f'font-family="var(--mono)">1</text>',
            f'<text x="50" y="65" font-size="3" fill="rgba(255,255,255,0.45)" '
            f'font-family="var(--mono)" text-anchor="middle">{n//2}</text>',
            f'<text x="100" y="65" font-size="3" fill="rgba(255,255,255,0.45)" '
            f'font-family="var(--mono)" text-anchor="end">{n}</text>',
        ]
    else:
        zero_y = 30
        end_x, end_y = 0, 30
        y_labels, x_labels = [], []
        segs_neg, segs_flat, segs_pos = [], [], []

    return f"""
<div class="glass" style="padding: 1.5rem 1.75rem;">
  <div style="display:flex; align-items: baseline; justify-content: space-between; margin-bottom: 1rem;">
    <div>
      <div class="eyebrow-sm" style="margin-bottom: 0.25rem;">Cumulative FTAOE over the season</div>
      <div class="caption">Running sum of (actual FTA − context baseline), possession by possession, ordered chronologically</div>
    </div>
    <div style="text-align: right;">
      <div class="eyebrow-sm">Final FTAOE</div>
      <div class="display-sm {pole}" style="margin-top: 0.2rem;">{_fmt_signed(final_delta, 0)}</div>
    </div>
  </div>
  <svg viewBox="0 8 100 64" preserveAspectRatio="none" style="width:100%; height: 220px;">
    <line x1="0" y1="{zero_y:.2f}" x2="100" y2="{zero_y:.2f}"
      stroke="rgba(255,255,255,0.18)" stroke-width="0.3" stroke-dasharray="1 1"/>
    <text x="100" y="{zero_y-1.5:.2f}" font-size="2.6" fill="rgba(255,255,255,0.4)"
      font-family="var(--mono)" text-anchor="end">zero</text>
    {''.join(segs_neg)}
    {''.join(segs_flat)}
    {''.join(segs_pos)}
    <circle cx="{end_x:.2f}" cy="{end_y:.2f}" r="1.6" fill="{final_color}"/>
    {''.join(y_labels)}
    {''.join(x_labels)}
  </svg>
  <div style="display:flex; justify-content: space-between; font-family: var(--mono); font-size: 0.6875rem; color: var(--ink-3); margin-top: 0.25rem;">
    <span>possession 1</span>
    <span>possession {n}</span>
  </div>
</div>
"""


# =====================================================================
# 5. CONTEXT MIX — distribution of a player's possessions across the
#    4 model features, with predicted vs actual FTA rate per bucket
# =====================================================================
def render_context_mix(mix_df, player_name: str, season: str) -> str:
    """Show what context the player operates in and how the baseline
    rates it. Four mini-cards, one per feature (period, score margin,
    clock, bonus). Each card is a stacked bar of the player's
    possession share, with the baseline's predicted FTA rate overlaid.
    """
    if len(mix_df) is None or len(mix_df) == 0:
        return "<div class='glass'><p class='caption'>No possessions found for this player-season.</p></div>"

    def _bucket_card(label: str, col: str, order: list[str]) -> str:
        agg = mix_df.groupby(col, observed=True).agg(
            n=("sfta", "size"),
            sfta=("sfta", "sum"),
            xfta=("xfta", "sum"),
        ).reindex(order, fill_value=0)
        total = agg["n"].sum()
        if total == 0:
            return ""
        agg["pct"] = agg["n"] / total * 100
        agg["pred_rate"] = agg["xfta"] / agg["n"].replace(0, pd.NA)
        agg["actual_rate"] = agg["sfta"] / agg["n"].replace(0, pd.NA)

        bar_w = 0.0
        bars = []
        for k, row in agg.iterrows():
            w = float(row["pct"])
            if w < 0.5:
                continue
            r, g, b = _interp((row["actual_rate"] - row["pred_rate"]) * 100)
            color = f"rgba({r},{g},{b},0.85)"
            bars.append(
                f'<rect x="{bar_w:.2f}" y="0" width="{w:.2f}" height="100" fill="{color}"/>'
            )
            if w > 6:
                bars.append(
                    f'<text x="{bar_w + w/2:.2f}" y="55" font-size="9" '
                    f'fill="rgba(0,0,0,0.7)" font-family="var(--mono)" '
                    f'font-weight="600" text-anchor="middle">{int(round(w))}%</text>'
                )
            bar_w += w

        legend = []
        for k, row in agg.iterrows():
            if row["n"] == 0:
                continue
            r, g, b = _interp((row["actual_rate"] - row["pred_rate"]) * 100)
            color = f"rgba({r},{g},{b},0.85)"
            pred = row["pred_rate"] * 100
            actual = row["actual_rate"] * 100
            legend.append(
                f'<div style="display:flex; align-items:center; gap:0.4rem; font-size:0.75rem; color: var(--ink-2);">'
                f'<span style="display:inline-block; width:9px; height:9px; border-radius:2px; background: {color};"></span>'
                f'<span class="caption">{k}</span>'
                f'<span class="caption" style="color: var(--ink-3); font-family: var(--mono);">{actual:+.1f}/100 vs {pred:+.1f}</span>'
                f'</div>'
            )

        return f"""
<div class="glass" style="padding: 1.25rem;">
  <div class="eyebrow-sm" style="margin-bottom: 0.6rem;">{label}</div>
  <svg viewBox="0 0 100 100" preserveAspectRatio="none" style="width:100%; height: 24px; border-radius: 6px; overflow: hidden;">
    {''.join(bars)}
  </svg>
  <div style="display:flex; flex-direction: column; gap: 0.3rem; margin-top: 0.75rem;">
    {''.join(legend)}
  </div>
</div>
"""

    period_card = _bucket_card("Period", "period_b", ["Q1", "Q2", "Q3", "Q4", "OT1", "OT2", "OT3"])
    margin_card = _bucket_card("Score margin", "margin_b",
                                ["trail 10+", "trail 3-10", "close", "lead 3-10", "lead 10+", "unknown"])
    clock_card = _bucket_card("Clock", "clock_b", ["early", "mid", "late", "clutch (<1m)", "unknown"])
    bonus_card = _bucket_card("Bonus state", "bonus_b", ["regulation", "in bonus"])

    return f"""
<div class="bento" style="grid-template-columns: 1fr 1fr; gap: 0.75rem;">
  {period_card}
  {margin_card}
  {clock_card}
  {bonus_card}
</div>
"""


# =====================================================================
# 6. CALIBRATION — predicted vs actual per predicted-xfta decile
# =====================================================================
def render_calibration(cal_df) -> str:
    """Predicted (x) vs actual (y) per baseline decile, on a y=x reference.
    Points on the line = calibrated. Above = under-predicting. Below =
    over-predicting. """
    if len(cal_df) == 0:
        return "<div class='glass'><p class='caption'>No calibration data.</p></div>"

    # Range
    pmax = float(cal_df["mean_pred"].max())
    amax = float(cal_df["mean_actual"].max())
    vmax = max(pmax, amax) * 1.1

    # Scatter points + y=x reference
    points = []
    for _, r in cal_df.iterrows():
        x = r["mean_pred"] / vmax * 100
        y = 60 - (r["mean_actual"] / vmax * 60)
        size = 6 + (r["n"] / cal_df["n"].max()) * 8
        # Color by sign
        diff = r["mean_actual"] - r["mean_pred"]
        col = _delta_text_color(diff * 100)
        points.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{size/4:.2f}" fill="{col}" '
            f'stroke="rgba(255,255,255,0.5)" stroke-width="0.4"/>'
        )
        # Decile label
        points.append(
            f'<text x="{x+2:.2f}" y="{y-1.5:.2f}" font-size="2.6" fill="rgba(255,255,255,0.45)" '
            f'font-family="var(--mono)">D{int(r["decile"])+1}</text>'
        )

    # Y=X reference line
    ref = (
        f'<line x1="0" y1="60" x2="100" y2="0" stroke="rgba(255,255,255,0.3)" '
        f'stroke-width="0.5" stroke-dasharray="2 1"/>'
    )

    # Axis labels
    ax_labels = (
        f'<text x="0" y="63" font-size="2.6" fill="rgba(255,255,255,0.4)" font-family="var(--mono)">0</text>'
        f'<text x="100" y="63" font-size="2.6" fill="rgba(255,255,255,0.4)" font-family="var(--mono)" text-anchor="end">{vmax:.2f}</text>'
        f'<text x="0" y="2" font-size="2.6" fill="rgba(255,255,255,0.4)" font-family="var(--mono)">{vmax:.2f}</text>'
    )

    return f"""
<div class="glass" style="padding: 1.5rem 1.75rem;">
  <div class="eyebrow-sm" style="margin-bottom: 0.6rem;">Calibration · baseline (x) vs actual (y) by predicted decile</div>
  <p class="caption" style="margin-bottom: 1rem; max-width: 56ch;">
    The line is y = x. Each point is one decile of the baseline's predicted xFTA.
    Point size scales with possession count in the bin. The baseline is
    near-zero, so the decile spread is tight — and the baseline doesn't
    move actuals around much.
  </p>
  <svg viewBox="0 -2 100 66" preserveAspectRatio="none" style="width:100%; height: 240px;">
    {ref}
    {''.join(points)}
    {ax_labels}
  </svg>
  <div style="display:flex; justify-content: space-between; font-family: var(--mono); font-size: 0.6875rem; color: var(--ink-3);">
    <span>baseline xfta (per possession)</span>
    <span>actual sfta (per possession)</span>
  </div>
</div>
"""


# =====================================================================
# 7. BASELINE COEFFICIENTS — what the Poisson GLM learned
# =====================================================================
def render_coefficients(coef_df) -> str:
    """The 4-feature Poisson GLM coefficients for the baseline. The headline
    is: the intercept is -1.87, period is small positive, in_bonus is small
    negative, score_margin and clock are near-zero. The baseline has
    almost nothing to work with — which is the point."""
    if len(coef_df) == 0:
        return "<div class='glass'><p class='caption'>No coefficients found. Run train_possession_v3_clean.py.</p></div>"

    coef_df = coef_df.copy()
    if "const" in coef_df["feature"].values:
        coef_df = coef_df[coef_df["feature"] != "const"]
    # Sort by absolute value desc
    coef_df["abs_coef"] = coef_df["coef"].abs()
    coef_df = coef_df.sort_values("abs_coef", ascending=False).reset_index(drop=True)

    rows = []
    max_abs = coef_df["abs_coef"].max() if len(coef_df) else 1
    for _, r in coef_df.iterrows():
        c = r["coef"]
        sign = "+" if c > 0 else "−"
        # Bar width as fraction of max_abs, scaled to chart width
        bar_w = (r["abs_coef"] / max_abs) * 50
        # Sign → left or right of zero line
        if c > 0:
            bar = (
                f'<rect x="50" y="0" width="{bar_w:.2f}" height="14" '
                f'fill="var(--delta-warm-2)" rx="1"/>'
            )
        else:
            bar = (
                f'<rect x="{50-bar_w:.2f}" y="0" width="{bar_w:.2f}" height="14" '
                f'fill="var(--delta-cool-2)" rx="1"/>'
            )
        rows.append(
            f'<div style="display: grid; grid-template-columns: 180px 1fr 60px; align-items: center; gap: 0.5rem; padding: 0.45rem 0; border-bottom: 1px solid var(--rule);">'
            f'<div class="caption" style="color: var(--ink); font-family: var(--mono);">{r["feature"]}</div>'
            f'<svg viewBox="0 0 100 14" preserveAspectRatio="none" style="width:100%; height: 14px;">'
            f'<line x1="50" y1="0" x2="50" y2="14" stroke="rgba(255,255,255,0.2)" stroke-width="0.4"/>'
            f'{bar}'
            f'</svg>'
            f'<div class="caption" style="font-family: var(--mono); text-align: right; color: var(--ink);">{sign}{abs(c):.4f}</div>'
            f'</div>'
        )

    # Re-interpret the feature names
    name_map = {
        "period": "Period (Q1..Q4+OT)",
        "in_bonus": "In bonus (Q4+ proxy)",
        "score_margin": "Score margin",
        "seconds_remaining_in_period": "Seconds remaining in period",
    }
    legend = []
    for f in coef_df["feature"]:
        nice = name_map.get(f, f)
        legend.append(
            f'<div class="caption" style="color: var(--ink-2);">'
            f'<b style="color: var(--ink); font-family: var(--mono);">{f}</b>'
            f' &nbsp; {nice}</div>'
        )

    return f"""
<div class="glass" style="padding: 1.5rem 1.75rem;">
  <div class="eyebrow-sm" style="margin-bottom: 0.5rem;">Baseline coefficients</div>
  <p class="caption" style="margin-bottom: 1rem; max-width: 56ch;">
    On the log link scale. A coefficient of <span style="font-family: var(--mono);">+0.1</span>
    means a one-unit feature increase multiplies predicted xFTA by
    <span style="font-family: var(--mono);">e<sup>0.1</sup> ≈ 1.105</span>. Most
    coefficients are small — the baseline is a near-zero context adjustment.
  </p>
  {''.join(rows)}
</div>
"""
