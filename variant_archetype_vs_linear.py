"""Does the archetype model clear a trivial linear body-type adjustment?

Gate 4 established two things. FTAOE is the raw shooting-foul rate per 100 to
within rho = 0.995 (F1), and about 15% of its variance is height (F16). The
archetype arm (context + height + position) removes the height gradient
(corr 0.391 -> 0.016), which is why it is a candidate headline specification.

But removing a height gradient is trivial. Anyone can regress the raw rate on
height and position and take the residual, with no Poisson model, no possession
grain, and no context features at all. So the question that decides whether the
archetype specification is worth shipping is:

    does archetype-FTAOE differ from that linear residual by a real,
    distinguishable margin?

If it does not, the archetype arm is an expensive way to compute a two-variable
regression residual, and the honest paper is the negative result: both the
context model and the body-type model collapse onto simple transforms of the
raw rate, for the same structural reason.

Baselines compared, all at qualified player-season grain (>=300 poss):
  raw          shooting-foul FTs per 100 finisher possessions
  linear       raw, residualised on height + position within season (WLS by
               possessions), i.e. the trivial body-type adjustment
  headline     the shipped context-only FTAOE per 100
  archetype    FTAOE per 100 from the context + height + position arm

Uncertainty is bootstrapped clustering on PLAYER, not player-season, because
546 players supply 1,691 player-seasons.

Writes model_artifacts/variant_archetype_vs_linear.json.
"""
from __future__ import annotations

import json
import os
import sqlite3

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import spearmanr

from config import DB_PATH

MODEL_DIR = "model_artifacts"
QUALIFY = 300
SEED = 42
N_BOOT = 2000


def load() -> pd.DataFrame:
    b = pd.read_csv(os.path.join(MODEL_DIR, "variant_archetype_boards.csv"))
    conn = sqlite3.connect(DB_PATH)
    ps = pd.read_sql(
        "SELECT player_id, season, height_inches, position FROM player_season",
        conn,
    )
    conn.close()
    b = b.merge(ps, left_on=["finisher_player_id", "season"],
                right_on=["player_id", "season"], how="inner")
    b = b[b["possessions"] >= QUALIFY].copy()
    b["raw_per100"] = b["actual_fta"] / b["possessions"] * 100
    return b


def linear_baseline(df: pd.DataFrame) -> pd.Series:
    """Raw rate residualised on height + position, within season, weighted by
    possessions. This is the whole 'adjustment' a reader could do by hand."""
    out = pd.Series(index=df.index, dtype=float)
    for season, g in df.groupby("season"):
        X = pd.get_dummies(g["position"].fillna("None"), drop_first=True)
        X["height"] = g["height_inches"].astype(float)
        X = sm.add_constant(X.astype(float), has_constant="add")
        fit = sm.WLS(g["raw_per100"], X, weights=g["possessions"]).fit()
        out.loc[g.index] = g["raw_per100"] - fit.fittedvalues
    return out


def agreement(a: pd.Series, b: pd.Series, season: pd.Series) -> dict:
    rho, _ = spearmanr(a, b)
    r = float(np.corrcoef(a, b)[0, 1])
    d = pd.DataFrame({"a": a, "b": b, "season": season})
    d["ra"] = d.groupby("season")["a"].rank(ascending=False, method="min")
    d["rb"] = d.groupby("season")["b"].rank(ascending=False, method="min")
    shift = (d["ra"] - d["rb"]).abs()
    ov = {}
    for k in (10, 20, 50):
        ov[f"top{k}"] = len(set(d.nlargest(k, "a").index)
                            & set(d.nlargest(k, "b").index))
    return {"pearson": round(r, 4), "spearman": round(float(rho), 4),
            "rankShiftMean": round(float(shift.mean()), 2),
            "rankShiftP95": float(shift.quantile(0.95)),
            "rankShiftMax": float(shift.max()), "topNOverlap": ov}


def boot_ci(df: pd.DataFrame, col_a: str, col_b: str) -> tuple:
    """Player-clustered bootstrap CI on Pearson r between two columns."""
    rng = np.random.RandomState(SEED)
    players = df["finisher_player_id"].unique()
    idx_by_player = {p: df.index[df["finisher_player_id"] == p].to_numpy()
                     for p in players}
    stats = []
    for _ in range(N_BOOT):
        pick = rng.choice(players, size=len(players), replace=True)
        rows = np.concatenate([idx_by_player[p] for p in pick])
        s = df.loc[rows]
        stats.append(np.corrcoef(s[col_a], s[col_b])[0, 1])
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return round(float(lo), 4), round(float(hi), 4)


def main() -> None:
    df = load().reset_index(drop=True)
    df["linear"] = linear_baseline(df)
    df = df.rename(columns={"ftaoe_per_100_headline": "headline",
                            "ftaoe_per_100_archetype": "archetype"})
    print(f"qualified player-seasons: {len(df):,}  "
          f"(distinct players: {df.finisher_player_id.nunique()})\n")

    # Height gradient of each candidate.
    print("height gradient, corr(metric, height):")
    grads = {}
    for c in ("raw_per100", "linear", "headline", "archetype"):
        g = float(df[c].corr(df["height_inches"]))
        grads[c] = round(g, 4)
        print(f"  {c:12s} {g:+.4f}")

    print("\nspread (sd per 100):")
    sds = {c: round(float(df[c].std()), 3)
           for c in ("raw_per100", "linear", "headline", "archetype")}
    for c, v in sds.items():
        print(f"  {c:12s} {v:.3f}")

    # THE decisive comparison.
    print("\n=== does archetype clear the trivial linear adjustment? ===")
    ag = agreement(df["archetype"], df["linear"], df["season"])
    lo, hi = boot_ci(df, "archetype", "linear")
    print(f"  archetype vs linear : Pearson {ag['pearson']:+.4f} "
          f"[{lo:+.4f}, {hi:+.4f}]  Spearman {ag['spearman']:+.4f}")
    print(f"     rank shift mean {ag['rankShiftMean']}, p95 "
          f"{ag['rankShiftP95']:.0f}, max {ag['rankShiftMax']:.0f}; "
          f"top-20 overlap {ag['topNOverlap']['top20']}/20")

    # Reference comparisons.
    others = {}
    for a, b in (("headline", "raw_per100"), ("archetype", "raw_per100"),
                 ("linear", "raw_per100"), ("archetype", "headline")):
        r = agreement(df[a], df[b], df["season"])
        l, h = boot_ci(df, a, b)
        others[f"{a}_vs_{b}"] = {**r, "pearsonCI": [l, h]}
        print(f"  {a:9s} vs {b:11s}: Pearson {r['pearson']:+.4f} "
              f"[{l:+.4f}, {h:+.4f}]  top-20 {r['topNOverlap']['top20']}/20")

    verdict = (
        "archetype does NOT clear the linear baseline"
        if ag["pearson"] >= 0.97 else
        "archetype DOES clear the linear baseline"
    )
    print(f"\nVERDICT: {verdict}")
    print("  bar: Pearson r < 0.97 against the linear residual, with the "
          "bootstrap CI excluding 0.97, would mean the model adds something a "
          "two-variable regression cannot.")

    out = {
        "qualifyPossessions": QUALIFY,
        "nPlayerSeasons": int(len(df)),
        "nPlayers": int(df.finisher_player_id.nunique()),
        "heightGradient": grads,
        "sdPer100": sds,
        "archetypeVsLinear": {**ag, "pearsonCI": [lo, hi]},
        "reference": others,
        "verdict": verdict,
        "bar": ("Pearson r < 0.97 against the linear residual with the "
                "player-clustered bootstrap CI excluding 0.97"),
    }
    path = os.path.join(MODEL_DIR, "variant_archetype_vs_linear.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
