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
        cap = "draws more fouls than expected"
    else:
        cap = "draws fewer fouls than expected"

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
        <span>fewer than expected</span>
        <span style="opacity: 0.5;">| zero</span>
        <span>more than expected</span>
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
    """Each row: rank · name · gap plot (actual dot, expected dot, line
    colored by sign of (actual − expected)) · inline percentile bar.

    The gap plot is the heart of the row. Inline SVG.
    """
    if len(df) == 0:
        return "<div class='glass'><p class='caption'>No players match the filters.</p></div>"

    # Accept both shapes — fixture uses ftaoe_per_100_fga, real data uses ftaoe_per_100
    rate_col = "ftaoe_per_100" if "ftaoe_per_100" in df.columns else "ftaoe_per_100_fga"
    df = df.sort_values(rate_col, ascending=False).head(int(top_n)).reset_index(drop=True)
    df["__rank"] = df.index + 1

    # Compute the plot's x-axis bounds from the cohort. Robust — use
    # the larger of (max actual) and (max expected) so both dots fit.
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
  <!-- expected mark (the model) — provisional treatment: hollow ring -->
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
  <td class="gap-num gap-hide-mobile"><span class="val">{expected:.1f}</span> <span style="color: var(--ink-4);">·</span> expected <span class="prov" style="margin-left:0.4rem;">provisional</span></td>
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
      <div class="caption">Each row: solid dot = actual FTA from fouls · hollow = expected (xFTA) · line color = sign of the gap</div>
    </div>
    <div style="display:flex; gap: 1.5rem; align-items: center; font-size: 0.75rem; color: var(--ink-3);">
      <span style="display:flex; align-items: center; gap: 0.4rem;">
        <span style="width: 8px; height: 8px; border-radius: 50%; background: var(--ink);"></span> actual · verified
      </span>
      <span style="display:flex; align-items: center; gap: 0.4rem;">
        <span style="width: 8px; height: 8px; border-radius: 50%; border: 1px dashed rgba(255,255,255,0.5);"></span> expected · provisional
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
    sentence. Four stat tiles: actual (verified), expected (provisional),
    FTAOE (provisional), percentile (provisional). The model "why" is
    shown honestly by labeling what's verified vs. model-derived.

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
    direction = "more" if ftaoe_100 >= 0 else "fewer"

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
        f"draws fouls in the <b>{int(round(pct))}th percentile</b> — "
        f"<b>{abs_delta:.1f} {direction}</b> than his shot profile predicts."
    )

    ftaoe_total_class = "pos" if ftaoe_total > 0 else "neg" if ftaoe_total < 0 else "zero"
    pct_class = "pos" if pct >= 60 else "neg" if pct <= 40 else "zero"

    return f"""
<div class="glass" style="padding: 2rem 2.25rem;">
  <div class="detail-grid">
    <div style="display:flex; flex-direction: column; gap: 0.75rem;">
      <div>
        <div class="eyebrow-sm" style="margin-bottom: 0.5rem;">
          FTA Over Expected · per 100 possessions
          <span class="prov" style="margin-left: 0.5rem;">provisional</span>
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
        <div class="stat-tile-label">Expected FTA (xFTA)</div>
        <div class="stat-tile-value">{xfta:.1f}</div>
        <div class="stat-tile-sub">model baseline · <span class="prov" style="margin-left: 0.3rem;">provisional</span></div>
      </div>
      <div class="stat-tile">
        <div class="stat-tile-label">FTAOE (absolute)</div>
        <div class="stat-tile-value {ftaoe_total_class}">{_fmt_signed(ftaoe_total)}</div>
        <div class="stat-tile-sub">actual − xFTA · <span class="prov" style="margin-left: 0.3rem;">provisional</span></div>
      </div>
      <div class="stat-tile">
        <div class="stat-tile-label">Percentile</div>
        <div class="stat-tile-value {pct_class}">{int(round(pct))}<span style="font-size: 1.125rem; color: var(--ink-3); margin-left: 2px;">th</span></div>
        <div class="stat-tile-sub">within qualified cohort · <span class="prov" style="margin-left: 0.3rem;">provisional</span></div>
      </div>
    </div>
  </div>

  <div style="margin-top: 1.75rem; padding-top: 1.25rem; border-top: 1px solid var(--rule); display:flex; gap: 1.5rem; flex-wrap: wrap;">
    <div class="caption" style="max-width: 64ch;">
      <b style="color: var(--ink); font-weight: 600;">What this number means.</b>
      The gap between actual free throws earned and the model's expected baseline.
      The model is context-only (shot location, period, score, bonus, home/away).
      It does not see who the player is.
    </div>
  </div>
</div>
"""
