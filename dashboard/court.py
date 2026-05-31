"""Half-court drawing helpers for Plotly."""

import plotly.graph_objects as go


# Court dimensions (NBA)
COURT_WIDTH = 50   # feet
COURT_LENGTH = 94  # feet
HALF_COURT = 47    # half court line


def draw_half_court(fig: go.Figure, row=None, col=None):
    """Add half-court outline to a Plotly figure.

    Draws the standard NBA half-court markings: baseline, sidelines,
    three-point arc, paint, restricted area, backboard.
    """
    # Court boundaries
    court_x = [-25, 25, 25, -25, -25]  # sideline to sideline
    court_y = [0, 0, 47, 47, 0]       # baseline to half-court

    opts = dict(showlegend=False)
    if row is not None:
        opts["row"] = row
        opts["col"] = col

    fig.add_trace(go.Scatter(
        x=court_x, y=court_y, mode="lines", name="court",
        line=dict(color="white", width=1),
        fill="toself", fillcolor="rgba(0,0,0,0.1)", **opts,
    ))

    # Three-point arc (center at basket: x=0, y=5.25 from baseline)
    # NBA 3PT line: 23.75ft at top, 22ft in corners
    import numpy as np
    theta = np.linspace(-np.pi / 2, np.pi / 2, 100)
    arc_x = 23.75 * np.cos(theta)
    arc_y = 5.25 + 23.75 * np.sin(theta)
    fig.add_trace(go.Scatter(
        x=arc_x.tolist(), y=arc_y.tolist(), mode="lines",
        line=dict(color="white", width=1, dash="dash"),
        name="3pt line", **opts,
    ))

    # Corner 3 extensions
    fig.add_trace(go.Scatter(
        x=[-25, -22, -22, 22, 22, 25],
        y=[0, 0, 5.25, 5.25, 0, 0],
        mode="lines", line=dict(color="white", width=1),
        name="corner 3", **opts,
    ))

    # Paint (key): 16ft wide, 19ft deep
    paint_x = [-8, 8, 8, -8, -8]
    paint_y = [0, 0, 19, 19, 0]
    fig.add_trace(go.Scatter(
        x=paint_x, y=paint_y, mode="lines",
        line=dict(color="white", width=1),
        name="paint", **opts,
    ))

    # Restricted area arc (4ft radius)
    ra_theta = np.linspace(-np.pi / 2, np.pi / 2, 50)
    ra_x = 4 * np.cos(ra_theta)
    ra_y = 5.25 + 4 * np.sin(ra_theta)
    fig.add_trace(go.Scatter(
        x=ra_x.tolist(), y=ra_y.tolist(), mode="lines",
        line=dict(color="white", width=0.5, dash="dot"),
        name="restricted area", **opts,
    ))

    # Backboard (6ft wide, at y=4 from baseline)
    fig.add_trace(go.Scatter(
        x=[-3, 3], y=[4, 4], mode="lines",
        line=dict(color="white", width=2),
        name="backboard", **opts,
    ))

    # Hoop marker
    fig.add_trace(go.Scatter(
        x=[0], y=[5.25], mode="markers",
        marker=dict(color="orange", size=6, symbol="x"),
        name="hoop", **opts,
    ))

    # Layout
    fig.update_xaxes(range=[-27, 27], showgrid=False, zeroline=False, visible=False,
                      scaleanchor="y", scaleratio=1)
    fig.update_yaxes(range=[-2, 49], showgrid=False, zeroline=False, visible=False)

    return fig


def shot_zone_bounds():
    """Return approximate bounds for common shot zones (for hexbin coloring)."""
    return {
        "Restricted Area": {"x": (-6, 6), "y": (0, 9)},
        "In The Paint (Non-RA)": {"x": (-9, 9), "y": (9, 19)},
        "Mid-Range": {"x": (-23.75, 23.75), "y": (9, 23.75)},
        "Left Corner 3": {"x": (-25, -22), "y": (0, 5.25)},
        "Right Corner 3": {"x": (22, 25), "y": (0, 5.25)},
        "Above the Break 3": {"x": (-23.75, 23.75), "y": (23.75, 47)},
    }
