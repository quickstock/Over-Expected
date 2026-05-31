"""SVG court drawing helpers for the xFTA dashboard v2.

All functions return self-contained HTML/SVG strings suitable for
st.components.v1.html(..., height=...).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# NBA court dimensions (feet)
COURT_W = 50
COURT_H = 47  # half-court
HOOP_X, HOOP_Y = 0, 5.25
THREE_PT_RADIUS = 23.75
THREE_PT_CORNER_Y = 5.25
PAINT_W = 16
PAINT_H = 19
RA_RADIUS = 4
BACKBOARD_Y = 4
BACKBOARD_W = 6


def _svg_header(width: int = 540, height: int = 520, view: str = "-27 -2 54 50") -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg"
  width="{width}" height="{height}"
  viewBox="{view}"
  style="background:#1C1917; display:block; margin:auto;">
<defs>
  <radialGradient id="courtGrad" cx="50%" cy="90%" r="60%">
    <stop offset="0%" stop-color="#292524"/>
    <stop offset="100%" stop-color="#1C1917"/>
  </radialGradient>
  <clipPath id="courtClip">
    <rect x="{-COURT_W/2}" y="0" width="{COURT_W}" height="{COURT_H}"/>
  </clipPath>
</defs>
"""


def _court_outline(fill: bool = True) -> str:
    """Return SVG paths for the court markings."""
    # Baseline + sidelines
    fill_attr = 'fill="url(#courtGrad)"' if fill else 'fill="none"'
    outline = (
        f'<rect x="{-COURT_W/2}" y="0" width="{COURT_W}" height="{COURT_H}" '
        f'{fill_attr} stroke="rgba(255,255,255,0.25)" stroke-width="0.8"/>'
    )

    # Three-point arc
    arc = (
        f'<path d="M {-THREE_PT_RADIUS} {THREE_PT_CORNER_Y} '
        f'A {THREE_PT_RADIUS} {THREE_PT_RADIUS} 0 0 1 {THREE_PT_RADIUS} {THREE_PT_CORNER_Y}" '
        f'fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="0.8"/>'
    )

    # Corner 3 lines
    corners = (
        f'<line x1="{-COURT_W/2}" y1="0" x2="{-COURT_W/2}" y2="{THREE_PT_CORNER_Y}" '
        f'stroke="rgba(255,255,255,0.25)" stroke-width="0.8"/>'
        f'<line x1="{COURT_W/2}" y1="0" x2="{COURT_W/2}" y2="{THREE_PT_CORNER_Y}" '
        f'stroke="rgba(255,255,255,0.25)" stroke-width="0.8"/>'
    )

    # Paint (key)
    paint = (
        f'<rect x="{-PAINT_W/2}" y="0" width="{PAINT_W}" height="{PAINT_H}" '
        f'fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="0.7"/>'
    )

    # Free-throw circle (top half only, at top of key = y=19)
    ft = (
        f'<path d="M {-PAINT_W/2} {PAINT_H} '
        f'A {PAINT_W/2} {PAINT_W/2} 0 0 1 {PAINT_W/2} {PAINT_H}" '
        f'fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="0.7"/>'
    )

    # Restricted area arc
    ra = (
        f'<path d="M {-RA_RADIUS} {HOOP_Y} '
        f'A {RA_RADIUS} {RA_RADIUS} 0 0 1 {RA_RADIUS} {HOOP_Y}" '
        f'fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="0.6" stroke-dasharray="2,2"/>'
    )

    # Backboard
    bb = (
        f'<line x1="{-BACKBOARD_W/2}" y1="{BACKBOARD_Y}" '
        f'x2="{BACKBOARD_W/2}" y2="{BACKBOARD_Y}" '
        f'stroke="rgba(255,255,255,0.35)" stroke-width="1.2"/>'
    )

    # Hoop
    hoop = (
        f'<circle cx="{HOOP_X}" cy="{HOOP_Y}" r="0.6" '
        f'fill="none" stroke="#E8600A" stroke-width="1"/>'
    )

    return outline + arc + corners + paint + ft + ra + bb + hoop


def draw_empty_court(width: int = 540, height: int = 520) -> str:
    """Return HTML string of an empty half-court."""
    svg = _svg_header(width, height) + _court_outline() + "</svg>"
    return svg


def draw_xfta_heatmap(
    bins_df: pd.DataFrame,
    width: int = 540,
    height: int = 520,
    cmap: str = "orange",
) -> str:
    """Render a half-court heatmap where each bin is colored by avg xFTA.

    Parameters
    ----------
    bins_df : DataFrame with columns x_bin, y_bin, avg_xfta, n
    """
    if len(bins_df) == 0:
        return draw_empty_court(width, height)

    svg = _svg_header(width, height)

    # Dark court background drawn BEFORE bins so bins sit on top
    svg += (
        f'<rect x="{-COURT_W/2}" y="0" width="{COURT_W}" height="{COURT_H}" '
        f'fill="url(#courtGrad)" stroke="none"/>'
    )

    # Determine color scale — vmax tuned to actual data range so the gradient pops
    vmax = min(bins_df["avg_xfta"].quantile(0.95), 0.08)
    vmin = 0

    # Court pixel scale mapping: viewBox -27..27 x, 0..47 y
    vb_w = 54
    vb_h = 50
    bin_w = vb_w / 30  # 30 bins across width
    bin_h = vb_h / 30  # 30 bins across height
    pad = 0.05  # tiny overlap to kill grid lines

    svg += '<g clip-path="url(#courtClip)">'
    for _, row in bins_df.iterrows():
        xb, yb = int(row["x_bin"]), int(row["y_bin"])
        val = row["avg_xfta"]
        if pd.isna(val):
            continue

        # Map bin indices to court coordinates
        x = -27 + xb * bin_w - pad
        y = 0 + yb * bin_h - pad

        raw_ratio = max(0, min(1, (val - vmin) / (vmax - vmin))) if vmax > 0 else 0
        # Power curve to exaggerate differences: low values stay very faint
        ratio = raw_ratio ** 1.8
        # Interpolate from dark charcoal to orange
        r = int(28 + ratio * (232 - 28))
        g = int(25 + ratio * (96 - 25))
        b = int(23 + ratio * (10 - 23))
        alpha = 0.08 + ratio * 0.82

        svg += (
            f'<rect x="{x:.2f}" y="{y:.2f}" '
            f'width="{bin_w + 2*pad:.2f}" height="{bin_h + 2*pad:.2f}" '
            f'fill="rgba({r},{g},{b},{alpha:.2f})" stroke="none"/>'
        )
    svg += '</g>'

    # Court lines drawn ON TOP of bins so markings remain crisp
    svg += _court_outline(fill=False)
    svg += "</svg>"
    return svg


def draw_shot_frequency_court(
    shots_df: pd.DataFrame,
    width: int = 540,
    height: int = 520,
) -> str:
    """Hexbin-style shot frequency heatmap on the court.

    Orange = above league avg frequency, blue = below.
    For v2 we use a simple binned approach similar to draw_xfta_heatmap
    but colored relative to a reference (league average).
    """
    if len(shots_df) == 0:
        return draw_empty_court(width, height)

    svg = _svg_header(width, height)
    svg += _court_outline()

    # Bin shots
    shots_df = shots_df.copy()
    shots_df["x_bin"] = ((shots_df["shot_x"] + 25) / 50 * 30).astype(int).clip(0, 29)
    shots_df["y_bin"] = (shots_df["shot_y"] / 47 * 30).astype(int).clip(0, 29)
    binned = shots_df.groupby(["x_bin", "y_bin"]).size().reset_index(name="count")

    vmax = binned["count"].quantile(0.95) if len(binned) > 0 else 1

    vb_w = 54
    vb_h = 50
    bin_w = vb_w / 30
    bin_h = vb_h / 30

    svg += '<g clip-path="url(#courtClip)">'
    for _, row in binned.iterrows():
        xb, yb = int(row["x_bin"]), int(row["y_bin"])
        val = row["count"]
        ratio = max(0, min(1, val / vmax)) if vmax > 0 else 0

        x = -27 + xb * bin_w
        y = 0 + yb * bin_h

        # Skip bins fully outside court rectangle
        if x + bin_w < -25 or x > 25 or y + bin_h < 0 or y > COURT_H:
            continue

        # Orange heatmap
        r = int(28 + ratio * (232 - 28))
        g = int(25 + ratio * (96 - 25))
        b = int(23 + ratio * (10 - 23))
        alpha = 0.15 + ratio * 0.60

        svg += (
            f'<rect x="{x:.2f}" y="{y:.2f}" '
            f'width="{bin_w:.2f}" height="{bin_h:.2f}" '
            f'fill="rgba({r},{g},{b},{alpha:.2f})" stroke="none"/>'
        )
    svg += '</g></svg>'
    return svg


def draw_foul_rate_court(
    shots_df: pd.DataFrame,
    width: int = 540,
    height: int = 520,
) -> str:
    """Court heatmap colored by FTA rate per FGA in each spatial bin.

    Uses a diverging color scale: teal (low foul rate) → dark → orange (high).
    """
    if len(shots_df) == 0:
        return draw_empty_court(width, height)

    svg = _svg_header(width, height)
    # Draw dark background first
    svg += (
        f'<rect x="{-COURT_W/2}" y="0" width="{COURT_W}" height="{COURT_H}" '
        f'fill="url(#courtGrad)" stroke="none"/>'
    )

    # Bin spatially for granular heatmap
    shots_df = shots_df.copy()
    shots_df["x_bin"] = ((shots_df["shot_x"] + 25) / 50 * 30).astype(int).clip(0, 29)
    shots_df["y_bin"] = (shots_df["shot_y"] / 47 * 30).astype(int).clip(0, 29)
    binned = (
        shots_df.groupby(["x_bin", "y_bin"])
        .agg(FGA=("fta_from_shot", "count"), FTA=("fta_from_shot", "sum"))
        .reset_index()
    )
    binned["rate"] = binned["FTA"] / binned["FGA"]
    vmax = binned["rate"].quantile(0.95) if len(binned) > 0 else 1

    vb_w = 54
    vb_h = 50
    bin_w = vb_w / 30
    bin_h = vb_h / 30
    pad = 0.05

    svg += '<g clip-path="url(#courtClip)">'
    for _, row in binned.iterrows():
        xb, yb = int(row["x_bin"]), int(row["y_bin"])
        rate = row["rate"]
        ratio = max(0, min(1, rate / vmax)) if vmax > 0 else 0
        raw_ratio = ratio ** 1.8  # power curve for visibility

        x = -27 + xb * bin_w - pad
        y = 0 + yb * bin_h - pad

        # Skip bins fully outside court
        if x + bin_w < -25 or x > 25 or y + bin_h < 0 or y > COURT_H:
            continue

        # Diverging: teal → dark → orange
        r = int(13 + raw_ratio * (232 - 13))
        g = int(148 - raw_ratio * (148 - 96))
        b = int(136 - raw_ratio * (136 - 10))
        alpha = 0.08 + raw_ratio * 0.72

        svg += (
            f'<rect x="{x:.2f}" y="{y:.2f}" '
            f'width="{bin_w + 2*pad:.2f}" height="{bin_h + 2*pad:.2f}" '
            f'fill="rgba({r},{g},{b},{alpha:.2f})" stroke="none"/>'
        )
    svg += '</g>'

    # Court lines on top
    svg += _court_outline(fill=False)
    svg += "</svg>"
    return svg
