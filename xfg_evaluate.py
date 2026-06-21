"""xFG% Gate 1 calibration report.

Reads model_artifacts/xfg_holdout_predictions.csv (the 2024-25 holdout) and
produces the deliverables: a reliability plot (predicted xFG% vs actual make
rate, overall by decile + per zone) and the top/bottom xFG% shot types.

Calibration is the point: the curve must hug the diagonal. Accuracy is
secondary.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ART = Path(__file__).parent / "model_artifacts"


def decile_table(p: np.ndarray, y: np.ndarray, n: int = 10) -> pd.DataFrame:
    bins = pd.qcut(p, n, duplicates="drop")
    g = pd.DataFrame({"p": p, "y": y, "bin": bins}).groupby("bin", observed=True)
    return g.agg(pred=("p", "mean"), actual=("y", "mean"), n=("y", "size")).reset_index(drop=True)


def main() -> None:
    df = pd.read_csv(ART / "xfg_holdout_predictions.csv")
    y = df["shot_made"].to_numpy()

    # ---- reliability: overall (raw vs calibrated) + per zone ----
    raw_t = decile_table(df["xfg_raw"].to_numpy(), y)
    cal_t = decile_table(df["xfg"].to_numpy(), y)

    zones = (
        df.groupby("shot_zone_basic")
        .agg(pred=("xfg", "mean"), actual=("shot_made", "mean"), n=("shot_made", "size"))
        .reset_index()
        .sort_values("pred")
    )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.4))
    for ax in (ax1, ax2):
        ax.plot([0, 1], [0, 1], "--", color="#999", lw=1, label="perfect")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_aspect("equal")
        ax.set_xlabel("predicted xFG%"); ax.set_ylabel("actual make rate")
    ax1.plot(raw_t["pred"], raw_t["actual"], "o-", color="#bbb", lw=1.3,
             ms=5, label="raw LGBM")
    ax1.plot(cal_t["pred"], cal_t["actual"], "o-", color="#c0392b", lw=1.8,
             ms=6, label="isotonic")
    ax1.set_title("Reliability by decile — 2024-25 holdout")
    ax1.legend(loc="upper left", fontsize=9, frameon=False)

    sc = ax2.scatter(zones["pred"], zones["actual"], s=zones["n"] / 120,
                     c="#c0392b", alpha=0.65, edgecolor="white", lw=0.6)
    for r in zones.itertuples():
        ax2.annotate(r.shot_zone_basic, (r.pred, r.actual), fontsize=7.5,
                     xytext=(4, 4), textcoords="offset points", color="#555")
    ax2.set_title("Per-zone calibration (dot size = volume)")
    fig.tight_layout()
    fig.savefig(ART / "xfg_reliability.png", dpi=130)
    print(f"wrote {ART/'xfg_reliability.png'}")

    # ---- printed tables ----
    print("\n=== Overall reliability (calibrated, by decile) ===")
    print(cal_t.assign(gap=(cal_t["actual"] - cal_t["pred"]))
          .round({"pred": 3, "actual": 3, "gap": 3}).to_string(index=False))

    print("\n=== Per-zone calibration ===")
    print(zones.assign(gap=(zones["actual"] - zones["pred"]))
          .round({"pred": 3, "actual": 3, "gap": 3}).to_string(index=False))

    # Sanity: top/bottom xFG% shot types (action_type, >=300 holdout FGA).
    at = (
        df.groupby("action_type")
        .agg(xfg=("xfg", "mean"), actual=("shot_made", "mean"), n=("shot_made", "size"))
        .reset_index()
    )
    at = at[at["n"] >= 300].sort_values("xfg", ascending=False)
    show = at.round({"xfg": 3, "actual": 3})
    print("\n=== Highest xFG% shot types (action_type, n>=300) ===")
    print(show.head(10).to_string(index=False))
    print("\n=== Lowest xFG% shot types (action_type, n>=300) ===")
    print(show.tail(10).to_string(index=False))


if __name__ == "__main__":
    main()
