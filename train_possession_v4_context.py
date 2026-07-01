"""Train v4 possession-grain xFTA — leak-clean context model, anchored.

Base features: period, seconds_remaining_in_period, score_margin
(at possession START — the terminal-event margin stored in tpv2 contains
the possession's own points, including the target FTs), and q4_or_ot
(tpv2's misnamed "in_bonus": V3 PBP has no bonus state, so it is a
period >= 4 indicator). Extended with three context features that are
external to the player:

  - offense_is_home      from game_meta (liveData boxscore)
  - opp_rate_logo        opponent (defensive team) shooting-foul rate
                         per possession, season-specific, leave-one-
                         game-out so the current game's outcomes never
                         enter their own feature
  - crew_rate_logo       mean of the 3 assigned officials' season
                         shooting-foul rates, leave-one-game-out

Validation: 6-fold season cross-fit as v3 (train on 5, predict the 6th;
every prediction OOF). Then SEASON ANCHORING: each held-out season's
predictions are scaled so their mean equals that season's actual league
rate. This pins "expected" to each season's own whistle environment
(rule changes like 2021-22 non-basketball-move enforcement shift the
league rate; without anchoring that shift leaks into every player's
FTAOE as a league-wide offset).

Writes predictions_poss_clean (same schema as v3 — downstream unchanged)
and model_artifacts/headline_v4_context_metrics.json.
"""
from __future__ import annotations

import json
import os
import sqlite3

import numpy as np
import pandas as pd
import statsmodels.api as sm

from config import DB_PATH, SEASONS

MODEL_DIR = "model_artifacts"
os.makedirs(MODEL_DIR, exist_ok=True)

BASE_FEATURES = [
    "period",
    "seconds_remaining_in_period",
    "score_margin",   # margin at possession START (see load) — pre-outcome
    "q4_or_ot",       # tpv2's "in_bonus" column is actually period >= 4;
                      # named honestly here (V3 PBP carries no bonus state)
]
CONTEXT_FEATURES = ["offense_is_home", "opp_rate_logo", "crew_rate_logo"]
FEATURES = BASE_FEATURES + CONTEXT_FEATURES
TARGET = "sfta"


def poisson_deviance(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_pred = np.clip(y_pred, 1e-10, None)
    return 2 * float(np.sum(y_pred - y_true * np.log(y_pred)))


def lift_pct(y_true: np.ndarray, y_pred: np.ndarray, baseline: float) -> float:
    base_dev = poisson_deviance(y_true, np.full(len(y_true), baseline))
    pred_dev = poisson_deviance(y_true, y_pred)
    return (base_dev - pred_dev) / base_dev * 100


def logo_rate(df: pd.DataFrame, key: str) -> np.ndarray:
    """Leave-one-game-out mean sfta per possession for grouping `key`
    within (key, season): (season_total - game_total) / (n - game_n).
    Falls back to the season-global rate when a group has one game.
    Vectorized via merges; preserves df row order."""
    g = (
        df.groupby([key, "season", "game_id"])[TARGET]
        .agg(["sum", "count"])
        .reset_index()
    )
    s = (
        df.groupby([key, "season"])[TARGET]
        .agg(["sum", "count"])
        .reset_index()
    )
    g = g.merge(s, on=[key, "season"], suffixes=("", "_season"))
    denom = g["count_season"] - g["count"]
    g["rate"] = np.where(
        denom > 0, (g["sum_season"] - g["sum"]) / denom.replace(0, 1), np.nan
    )
    season_rate = (
        df.groupby("season")[TARGET].mean().rename("srate").reset_index()
    )
    g = g.merge(season_rate, on="season")
    g["rate"] = g["rate"].fillna(g["srate"])
    out = df[[key, "season", "game_id"]].merge(
        g[[key, "season", "game_id", "rate"]],
        on=[key, "season", "game_id"],
        how="left",
    )["rate"]
    return out.values


def load() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        """SELECT t.game_id, t.possession_number, t.season, t.sfta,
                  t.period, t.seconds_remaining_in_period,
                  t.score_margin AS term_margin,
                  t.in_bonus,
                  p.offense_team_id,
                  (p.finisher_player_id IS NOT NULL) AS has_finisher,
                  m.home_team_id, m.away_team_id,
                  m.ref1_id, m.ref2_id, m.ref3_id
           FROM training_possessions_v2 t
           JOIN possessions p
             ON p.game_id = t.game_id
            AND p.possession_number = t.possession_number
           LEFT JOIN game_meta m ON m.game_id = t.game_id""",
        conn,
    )
    conn.close()
    missing_meta = int(df["home_team_id"].isna().sum())
    print(
        f"possessions: {len(df):,} "
        f"({missing_meta:,} without game_meta; context imputed for those)"
    )

    # score_margin at possession START. tpv2's stored margin is stamped
    # on the possession's terminal event, which for a foul possession is
    # the last free throw — the very FTs the model predicts. Carrying the
    # last known margin forward and shifting one possession back gives
    # the margin the offense actually faced, with no outcome inside it.
    df = df.sort_values(["game_id", "possession_number"], ignore_index=True)
    run = df.groupby("game_id", sort=False)["term_margin"].ffill()
    df["score_margin"] = (
        run.groupby(df["game_id"], sort=False).shift(1).fillna(0.0)
    )
    df["seconds_remaining_in_period"] = df[
        "seconds_remaining_in_period"
    ].fillna(0.0)
    df["q4_or_ot"] = df["in_bonus"].fillna(0).astype(int)

    has_meta = df["home_team_id"].notna()
    df["offense_is_home"] = np.where(
        has_meta, (df["offense_team_id"] == df["home_team_id"]).astype(float), 0.5
    )
    df["def_team_id"] = np.where(
        df["offense_team_id"] == df["home_team_id"],
        df["away_team_id"],
        df["home_team_id"],
    )
    df["def_team_id"] = df["def_team_id"].fillna(-1)

    print("computing opponent LOGO rates ...")
    df["opp_rate_logo"] = logo_rate(df, "def_team_id")
    season_rate = df.groupby("season")["sfta"].transform("mean")
    df.loc[~has_meta, "opp_rate_logo"] = season_rate[~has_meta]

    print("computing crew LOGO rates ...")
    ref_rates = []
    for ref_col in ["ref1_id", "ref2_id", "ref3_id"]:
        sub = df[[ref_col, "season", "game_id", TARGET]].rename(
            columns={ref_col: "ref_id"}
        )
        sub["ref_id"] = sub["ref_id"].fillna(-1)
        ref_rates.append(logo_rate(sub, "ref_id"))
    df["crew_rate_logo"] = np.mean(np.column_stack(ref_rates), axis=1)
    df.loc[~has_meta, "crew_rate_logo"] = season_rate[~has_meta]

    return df


def main() -> None:
    df = load()

    print("\nFeature summary:")
    for f in FEATURES:
        print(f"  {f}: mean={df[f].mean():.4f} std={df[f].std():.4f}")

    all_preds = []
    fold_metrics = []
    for held in SEASONS:
        train = df[df["season"] != held]
        test = df[df["season"] == held]
        print(f"\nFold: hold out {held}  train={len(train):,}  test={len(test):,}")

        X_tr = sm.add_constant(train[FEATURES].astype(float), has_constant="add")
        X_te = sm.add_constant(test[FEATURES].astype(float), has_constant="add")
        model = sm.GLM(
            train[TARGET].values, X_tr, family=sm.families.Poisson()
        ).fit()
        raw = model.predict(X_te).values

        # Anchor on the FINISHER universe: possessions without a finisher
        # have sfta == 0 by construction and are never attributed to a
        # player, so the league-mean-zero invariant must hold on the
        # attributable possessions only.
        fin = test["has_finisher"].values.astype(bool)
        season_mean = float(test.loc[fin, TARGET].mean())
        anchor = season_mean / float(raw[fin].mean())
        xfta = raw * anchor

        lift_raw = lift_pct(
            test[TARGET].values[fin], raw[fin], float(train[TARGET].mean())
        )
        lift_anchored = lift_pct(test[TARGET].values[fin], xfta[fin], season_mean)
        print(
            f"  anchor x{anchor:.4f}  lift_raw={lift_raw:.3f}%  "
            f"lift_anchored(vs season mean)={lift_anchored:.3f}%"
        )
        fold_metrics.append(
            {
                "season": held,
                "lift_pct": lift_anchored,
                "lift_raw_pct": lift_raw,
                "anchor": anchor,
                "baseline": season_mean,
                "pred_mean": float(xfta.mean()),
                "actual_mean": season_mean,
                "params": {k: float(v) for k, v in model.params.items()},
            }
        )
        all_preds.append(
            pd.DataFrame(
                {
                    "game_id": test["game_id"].values,
                    "possession_number": test["possession_number"].values,
                    "season": held,
                    "sfta": test[TARGET].values,
                    "xfta": xfta,
                    "has_finisher": fin.astype(int),
                }
            )
        )

    oof = pd.concat(all_preds, ignore_index=True)

    # Global OOF lift vs per-season-mean baseline, finisher universe.
    fin_df = oof[oof["has_finisher"].astype(bool)]
    smeans = fin_df.groupby("season")["sfta"].mean()
    base_dev = poisson_deviance(
        fin_df["sfta"].values, fin_df["season"].map(smeans).values
    )
    pred_dev = poisson_deviance(fin_df["sfta"].values, fin_df["xfta"].values)
    oof_lift = (base_dev - pred_dev) / base_dev * 100
    print(f"\nOOF global anchored lift vs season-mean baseline: {oof_lift:.3f}%")
    for s in SEASONS:
        sub = oof[oof["season"] == s]
        print(
            f"  {s}: mean xfta={sub['xfta'].mean():.4f} "
            f"mean sfta={sub['sfta'].mean():.4f}"
        )

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS predictions_poss_clean")
    oof.drop(columns=["has_finisher"]).to_sql(
        "predictions_poss_clean", conn, if_exists="replace", index=False
    )
    conn.execute(
        "CREATE INDEX idx_ppc_game ON predictions_poss_clean(game_id, possession_number)"
    )
    conn.commit()
    conn.close()

    with open(os.path.join(MODEL_DIR, "headline_v4_context_metrics.json"), "w") as f:
        json.dump(
            {
                "folds": fold_metrics,
                "oof_lift_pct": oof_lift,
                "features": FEATURES,
                "anchoring": "per-season mean scaling to the season's own league rate",
            },
            f,
            indent=2,
        )
    print("predictions_poss_clean replaced; metrics written.")


if __name__ == "__main__":
    main()
