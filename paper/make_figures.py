"""Generate the paper's figures from committed artifacts. Vector PDF out.

Every figure reads a real file. Nothing is illustrative or hand-drawn.

  fig1_xfg_reliability.pdf     xfg_holdout_predictions.csv
  fig2_ftaoe_reliability.pdf   xfta.db + reliability.json
  fig3_identity_variant.pdf    variant_archetype_boards.csv
  fig4_calibration.pdf         variant_model_family.json
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from config import DB_PATH, SEASONS  # noqa: E402

ART = ROOT / "model_artifacts"
OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

WARM, COOL, GREY, INK = "#c0392b", "#2c6fa8", "#9aa0a6", "#222222"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9.5,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 200,
    "savefig.bbox": "tight",
})


def decile_table(p, y, n=10):
    bins = pd.qcut(p, n, duplicates="drop")
    g = pd.DataFrame({"p": p, "y": y, "b": bins}).groupby("b", observed=True)
    return g.agg(pred=("p", "mean"), actual=("y", "mean"),
                 n=("y", "size")).reset_index(drop=True)


# ------------------------------------------------------------------ fig 1
def fig_xfg():
    df = pd.read_csv(ART / "xfg_holdout_predictions.csv")
    y = df["shot_made"].to_numpy()
    raw, cal = decile_table(df["xfg_raw"].to_numpy(), y), \
        decile_table(df["xfg"].to_numpy(), y)
    zones = (df.groupby("shot_zone_basic")
             .agg(pred=("xfg", "mean"), actual=("shot_made", "mean"),
                  n=("shot_made", "size")).reset_index())

    fig, (a1, a2) = plt.subplots(
        1, 2, figsize=(6.9, 3.2), gridspec_kw={"width_ratios": [1, 1.15]}
    )
    a1.plot([0, 1], [0, 1], "--", color=GREY, lw=0.9, zorder=1)
    a1.set_xlim(0.15, 0.85); a1.set_ylim(0.15, 0.85); a1.set_aspect("equal")
    a1.set_xlabel("predicted xFG%")
    a1.set_ylabel("observed make rate")
    a1.plot(raw["pred"], raw["actual"], "o-", color=GREY, lw=1.1, ms=3.6,
            label="raw LightGBM", zorder=2)
    a1.plot(cal["pred"], cal["actual"], "o-", color=WARM, lw=1.5, ms=4.2,
            label="isotonic", zorder=3)
    a1.set_title("(a) reliability by decile")
    a1.legend(loc="upper left", frameon=False)

    # Six zones clustered between .35 and .67 collide as a scatter, so show
    # predicted against observed as a dumbbell per zone instead. Backcourt is
    # dropped: ~1k attempts at a make rate far below the panel range, and the
    # 2025-26 heave-rule change makes it a moving target (see Limitations).
    n_bc = int(zones.loc[zones["shot_zone_basic"] == "Backcourt", "n"].sum())
    zones = zones[zones["shot_zone_basic"] != "Backcourt"]
    zones = zones.sort_values("n", ascending=True).reset_index(drop=True)
    ypos = np.arange(len(zones))
    a2.hlines(ypos, zones["pred"], zones["actual"], color=GREY, lw=1.1,
              zorder=1)
    a2.scatter(zones["pred"], ypos, s=22, color=COOL, zorder=3,
               label="predicted")
    a2.scatter(zones["actual"], ypos, s=22, color=WARM, zorder=3,
               label="observed")
    a2.set_yticks(ypos)
    a2.set_yticklabels(
        [f"{z}\n({n / 1000:.0f}k attempts)"
         for z, n in zip(zones["shot_zone_basic"], zones["n"])], fontsize=6.4
    )
    for r, y in zip(zones.itertuples(), ypos):
        a2.annotate(f"{(r.actual - r.pred) * 100:+.1f} pp",
                    (max(r.pred, r.actual), y), fontsize=6,
                    xytext=(7, -2), textcoords="offset points", color=INK)
    a2.set_xlim(0.30, 0.76)
    a2.set_ylim(-0.9, len(zones) - 0.4)
    a2.set_xlabel("field-goal percentage")
    a2.set_title("(b) per-zone calibration")
    a2.legend(loc="lower center", frameon=False, ncol=2, handletextpad=0.3,
              bbox_to_anchor=(0.5, -0.02))
    a2.spines["left"].set_visible(False)
    a2.tick_params(axis="y", length=0)
    fig.tight_layout()
    fig.savefig(OUT / "fig1_xfg_reliability.pdf")
    plt.close(fig)
    print(f"fig1 ok (backcourt excluded from panel b: {n_bc:,} attempts)")


# ------------------------------------------------------------------ fig 2
def fig_ftaoe_reliability():
    rel = json.loads((ART / "reliability.json").read_text())
    conn = sqlite3.connect(DB_PATH)
    pg = pd.read_sql(
        """SELECT p.finisher_player_id AS player_id, g.season, p.game_id,
                  SUM(p.sfta) AS a, SUM(pr.xfta) AS x, COUNT(*) AS n
           FROM possessions p
           JOIN games g ON g.GAME_ID = p.game_id
           JOIN predictions_poss_clean pr
             ON pr.game_id = p.game_id
            AND pr.possession_number = p.possession_number
           WHERE p.finisher_player_id IS NOT NULL
           GROUP BY p.finisher_player_id, g.season, p.game_id
           ORDER BY p.game_id""", conn)
    conn.close()
    pg["gidx"] = pg.groupby(["player_id", "season"]).cumcount()
    pg["half"] = pg["gidx"] % 2
    h = pg.groupby(["player_id", "season", "half"])[["a", "x", "n"]].sum().reset_index()
    w = h.pivot(index=["player_id", "season"], columns="half",
                values=["a", "x", "n"])
    w.columns = [f"{v}{k}" for v, k in w.columns]
    w = w.dropna().join(pg.groupby(["player_id", "season"])["n"].sum().rename("poss"))
    q = w[w["poss"] >= 300].copy()
    q["r0"] = (q["a0"] - q["x0"]) / q["n0"] * 100
    q["r1"] = (q["a1"] - q["x1"]) / q["n1"] * 100

    K = rel["paddingK"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.9, 3.2))

    a1.scatter(q["r0"], q["r1"], s=5, color=COOL, alpha=0.4, lw=0)
    lim = np.nanpercentile(np.abs(np.r_[q["r0"], q["r1"]]), 99.5)
    a1.plot([-lim, lim], [-lim, lim], "--", color=GREY, lw=0.9)
    a1.set_xlim(-lim, lim); a1.set_ylim(-lim, lim); a1.set_aspect("equal")
    a1.set_xlabel("FTAOE/100, odd games"); a1.set_ylabel("FTAOE/100, even games")
    a1.set_title(f"(a) split-half, $r$ = {rel['splitHalfR']:.3f} "
                 f"($n$ = {len(q):,})")

    n = np.arange(1, 2400)
    a2.plot(n, n / (n + K), color=WARM, lw=1.6)
    for mark, lab in ((300, "qualifying\nthreshold"), (1000, None)):
        a2.plot([mark, mark], [0, mark / (mark + K)], ":", color=GREY, lw=0.9)
        a2.plot(mark, mark / (mark + K), "o", color=INK, ms=3.4)
        a2.annotate(f"{mark} poss\n$r$ = {mark / (mark + K):.2f}",
                    (mark, mark / (mark + K)), fontsize=7,
                    xytext=(6, -16), textcoords="offset points", color=INK)
    a2.set_xlim(0, 2400); a2.set_ylim(0, 1)
    a2.set_xlabel("finisher possessions")
    a2.set_ylabel("implied reliability  $n/(n+K)$")
    a2.set_title(f"(b) stabilisation, $K$ = {K} possessions")
    fig.tight_layout()
    fig.savefig(OUT / "fig2_ftaoe_reliability.pdf")
    plt.close(fig)
    print(f"fig2 ok (split-half r={np.corrcoef(q['r0'], q['r1'])[0,1]:.4f})")


# ------------------------------------------------------------------ fig 3
def fig_identity():
    b = pd.read_csv(ART / "variant_archetype_boards.csv")
    v = json.loads((ART / "variant_archetype.json").read_text())
    rho_a = v["comparisons"][0]["spearmanRho"]
    rho_i = v["comparisons"][1]["spearmanRho"]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.9, 3.4))
    for ax, col, rho, lab in (
        (a1, "archetype", rho_a, "+ height, position"),
        (a2, "identity", rho_i, "+ prior-season FTr"),
    ):
        x = b["ftaoe_per_100_headline"]
        y = b[f"ftaoe_per_100_{col}"]
        ax.axhline(0, color=GREY, lw=0.6); ax.axvline(0, color=GREY, lw=0.6)
        lim = max(abs(x).max(), abs(y).max()) * 1.04
        ax.plot([-lim, lim], [-lim, lim], "--", color=GREY, lw=0.9, zorder=1)
        ax.scatter(x, y, s=5, color=COOL, alpha=0.35, lw=0, zorder=2)
        g = b[b["player_name"] == "Rudy Gobert"]
        ax.scatter(g["ftaoe_per_100_headline"], g[f"ftaoe_per_100_{col}"],
                   s=26, color=WARM, edgecolor="white", lw=0.7, zorder=4,
                   label="Rudy Gobert")
        ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_aspect("equal")
        ax.set_xlabel("FTAOE/100, context-only model")
        ax.set_title(f"{lab}\nSpearman $\\rho$ = {rho:.3f}")
        ax.legend(loc="upper left", frameon=False)
    a1.set_ylabel("FTAOE/100, variant model")
    fig.tight_layout()
    fig.savefig(OUT / "fig3_identity_variant.pdf")
    plt.close(fig)
    print("fig3 ok")


# ------------------------------------------------------------------ fig 4
def fig_calibration():
    m = json.loads((ART / "variant_model_family.json").read_text())
    fig, ax = plt.subplots(figsize=(4.1, 3.5))
    lo, hi = 0.165, 0.205
    ax.plot([lo, hi], [lo, hi], "--", color=GREY, lw=0.9, label="identity",
            zorder=1)
    for arm, colr, mk, lab in (
        ("poisson_glm", WARM, "o", "Poisson GLM"),
        ("poisson_lgbm", COOL, "s", "Poisson LightGBM"),
    ):
        c = m["arms"][arm]["calibration"]
        d = pd.DataFrame(c["deciles"])
        # Points are the deciles; the line is the fitted slope the text quotes.
        ax.scatter(d["predRate"], d["actualRate"], marker=mk, s=17,
                   color=colr, alpha=0.85, lw=0, zorder=3)
        xs = np.array([d["predRate"].min(), d["predRate"].max()])
        ax.plot(xs, c["slope"] * xs + c["intercept"], "-", color=colr, lw=1.5,
                zorder=2, label=f"{lab}: slope {c['slope']:.2f}")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi); ax.set_aspect("equal")
    ax.set_xlabel("predicted shooting-foul FTs / possession")
    ax.set_ylabel("observed")
    ax.set_title("player-season deciles ($\\geq$100 poss)")
    ax.legend(loc="upper left", frameon=False, handlelength=1.6)
    fig.tight_layout()
    fig.savefig(OUT / "fig4_calibration.pdf")
    plt.close(fig)
    print("fig4 ok")


if __name__ == "__main__":
    fig_xfg()
    fig_ftaoe_reliability()
    fig_identity()
    fig_calibration()
    print(f"\nfigures in {OUT}")
