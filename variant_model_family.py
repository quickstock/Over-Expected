"""Model-family comparison, re-run against the CURRENT possession target.

The original comparison (variants.py, deleted at e4a49a8) pitted a Poisson
LightGBM against a multiclass LightGBM on the FGA-grain `fta_from_shot`
target. That target was later abandoned, the comparison printed to stdout
without saving, and the committed config contradicted its own docstring
(4-class in prose, num_class=3 in params, classes 0/1/2 in the expectation).
Nothing about it is citable. This asks the same two questions of the target
that actually ships.

Q1 (likelihood): the target is a small count with a lumpy support — 2 is far
    more common than 1, because a shooting foul on a miss awards two shots
    while an and-1 awards one. Poisson cannot represent that shape. Does
    modelling the categories explicitly beat it?
Q2 (learner): the headline is a GLM. Does a gradient-boosted Poisson learner,
    given the same seven features, extract materially more?

Three arms, identical folds, identical per-season anchoring:

  poisson_glm    the production model (imported, so it is the shipping model)
  multinomial    multinomial logit over {0, 1, 2, 3+}, expectation taken as
                 the probability-weighted class value, 3+ valued at its
                 training-fold empirical mean
  poisson_lgbm   gradient-boosted Poisson, same seven features, early stopped
                 on a held-out slice of the TRAINING rows so the evaluation
                 fold is never touched

Each arm is scored on four things, because per-possession fit is not what
this metric is for:

  1. OOF anchored Poisson-deviance lift vs the season-mean baseline
  2. split-half reliability of the resulting FTAOE/100 leaderboard, and the
     Spearman-Brown full-season figure (the number that matters)
  3. per-decile calibration at player-season grain (slope, intercept, drift)
  4. rank agreement with the production arm

An arm that wins on 1 and loses on 2 is the wrong model for this problem.

Writes model_artifacts/variant_model_family.json.
"""
from __future__ import annotations

import json
import os
import sqlite3

import numpy as np
import pandas as pd
import statsmodels.api as sm
import lightgbm as lgb
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from config import DB_PATH, SEASONS
from train_possession_v4_context import FEATURES, TARGET, load, poisson_deviance

MODEL_DIR = "model_artifacts"
QUALIFY = 300
CALIB_MIN_POSS = 100          # matches check_calibration.py
CLASS_CAP = 3                 # {0, 1, 2, 3+}
SEED = 42


# ------------------------------------------------------------------ arms

def arm_poisson_glm(train, test):
    X_tr = sm.add_constant(train[FEATURES].astype(float), has_constant="add")
    X_te = sm.add_constant(test[FEATURES].astype(float), has_constant="add")
    m = sm.GLM(train[TARGET].values, X_tr, family=sm.families.Poisson()).fit()
    return m.predict(X_te).values


def arm_multinomial(train, test):
    y = np.minimum(train[TARGET].values, CLASS_CAP)
    # Value of the collapsed top class, from training rows only.
    tail = train[TARGET].values[train[TARGET].values >= CLASS_CAP]
    tail_value = float(tail.mean()) if len(tail) else float(CLASS_CAP)

    scaler = StandardScaler().fit(train[FEATURES].astype(float))
    X_tr = scaler.transform(train[FEATURES].astype(float))
    X_te = scaler.transform(test[FEATURES].astype(float))

    clf = LogisticRegression(
        solver="lbfgs", max_iter=400, C=1e6, n_jobs=-1, random_state=SEED
    )
    clf.fit(X_tr, y)
    proba = clf.predict_proba(X_te)
    values = np.array(
        [tail_value if c >= CLASS_CAP else float(c) for c in clf.classes_]
    )
    return proba @ values, tail_value


def arm_poisson_lgbm(train, test):
    rng = np.random.RandomState(SEED)
    idx = rng.permutation(len(train))
    cut = int(len(train) * 0.9)
    fit_i, val_i = idx[:cut], idx[cut:]
    Xtr = train[FEATURES].astype(float).values
    ytr = train[TARGET].values

    model = lgb.LGBMRegressor(
        objective="poisson", n_estimators=2000, learning_rate=0.05,
        num_leaves=63, min_child_samples=200, feature_fraction=0.8,
        bagging_fraction=0.8, bagging_freq=1, verbose=-1, random_state=SEED,
    )
    model.fit(
        Xtr[fit_i], ytr[fit_i],
        eval_set=[(Xtr[val_i], ytr[val_i])], eval_metric="poisson",
        callbacks=[lgb.early_stopping(50, verbose=False),
                   lgb.log_evaluation(0)],
    )
    return model.predict(test[FEATURES].astype(float).values), model.best_iteration_


# --------------------------------------------------------------- scoring

def split_half_reliability(pg: pd.DataFrame, xcol: str) -> dict:
    """Odd/even game split within player-season, exactly as
    scripts/analyze_reliability.py does it."""
    pg = pg.sort_values(["player_id", "season", "game_id"]).copy()
    pg["gidx"] = pg.groupby(["player_id", "season"]).cumcount()
    pg["half"] = pg["gidx"] % 2
    h = (
        pg.groupby(["player_id", "season", "half"])[["a", xcol, "n"]]
        .sum().reset_index()
    )
    wide = h.pivot(index=["player_id", "season"], columns="half",
                   values=["a", xcol, "n"])
    wide.columns = [f"{v}{k}" for v, k in wide.columns]
    wide = wide.dropna()
    totals = pg.groupby(["player_id", "season"])["n"].sum().rename("poss")
    wide = wide.join(totals)
    q = wide[wide["poss"] >= QUALIFY].copy()
    q["r0"] = (q["a0"] - q[f"{xcol}0"]) / q["n0"] * 100
    q["r1"] = (q["a1"] - q[f"{xcol}1"]) / q["n1"] * 100
    r_half = float(np.corrcoef(q["r0"], q["r1"])[0, 1])
    r_full = 2 * r_half / (1 + r_half)
    n_half = float((q["n0"].mean() + q["n1"].mean()) / 2)
    return {
        "splitHalfR": round(r_half, 4),
        "fullSeasonR": round(r_full, 4),
        "meanHalfPoss": round(n_half),
        "paddingK": round(n_half * (1 - r_half) / r_half),
        "nPlayerSeasons": int(len(q)),
    }


def decile_calibration(ps: pd.DataFrame, xcol: str) -> dict:
    """Player-season grain, deciles of predicted rate. Slope 1 / intercept 0
    is perfect."""
    d = ps[ps["n"] >= CALIB_MIN_POSS].copy()
    d["pred_rate"] = d[xcol] / d["n"]
    d["act_rate"] = d["a"] / d["n"]
    d["dec"] = pd.qcut(d["pred_rate"], 10, labels=False, duplicates="drop") + 1
    cal = d.groupby("dec").agg(
        n_ps=("a", "size"), pred=("pred_rate", "mean"),
        act=("act_rate", "mean"),
    ).reset_index()
    slope, intercept = np.polyfit(cal["pred"], cal["act"], 1)
    resid_pct = (cal["act"] - cal["pred"]) / cal["pred"] * 100
    return {
        "minPossessions": CALIB_MIN_POSS,
        "nPlayerSeasons": int(len(d)),
        "slope": round(float(slope), 4),
        "intercept": round(float(intercept), 6),
        "maxAbsResidualPct": round(float(resid_pct.abs().max()), 3),
        "meanAbsResidualPct": round(float(resid_pct.abs().mean()), 3),
        "deciles": [
            {"decile": int(r.dec), "nPlayerSeasons": int(r.n_ps),
             "predRate": round(float(r.pred), 5),
             "actualRate": round(float(r.act), 5),
             "residualPct": round(float((r.act - r.pred) / r.pred * 100), 3)}
            for r in cal.itertuples()
        ],
    }


def main() -> None:
    df = load()

    conn = sqlite3.connect(DB_PATH)
    fin = pd.read_sql(
        "SELECT game_id, possession_number, finisher_player_id FROM possessions",
        conn,
    )
    names = pd.read_sql(
        "SELECT player_id, season, player_name FROM player_season", conn
    )
    conn.close()
    df = df.merge(fin, on=["game_id", "possession_number"], how="left")

    arms = ["poisson_glm", "multinomial", "poisson_lgbm"]
    fold_meta = {a: [] for a in arms}

    for held in SEASONS:
        tr_mask = df["season"] != held
        te_mask = df["season"] == held
        train, test = df[tr_mask], df[te_mask]
        fin_te = test["has_finisher"].values.astype(bool)
        season_mean = float(test.loc[fin_te, TARGET].mean())
        print(f"\nFold {held}: train={len(train):,} test={len(test):,}")

        raws = {}
        raws["poisson_glm"] = arm_poisson_glm(train, test)
        mn, tail_value = arm_multinomial(train, test)
        raws["multinomial"] = mn
        lg, best_iter = arm_poisson_lgbm(train, test)
        raws["poisson_lgbm"] = lg

        for a in arms:
            raw = raws[a]
            anchor = season_mean / float(raw[fin_te].mean())
            xfta = raw * anchor
            df.loc[te_mask, f"x_{a}"] = xfta

            base = poisson_deviance(
                test[TARGET].values[fin_te],
                np.full(int(fin_te.sum()), season_mean),
            )
            pred = poisson_deviance(test[TARGET].values[fin_te], xfta[fin_te])
            lift = (base - pred) / base * 100
            meta = {"season": held, "liftPct": round(lift, 4),
                    "anchor": round(anchor, 5)}
            if a == "multinomial":
                meta["tailClassValue"] = round(tail_value, 4)
            if a == "poisson_lgbm":
                meta["bestIteration"] = int(best_iter)
            fold_meta[a].append(meta)
            print(f"  {a:13s} anchor x{anchor:.4f}  lift {lift:.3f}%")

    # ------------------------------------------------- aggregate scoring
    d = df[df["has_finisher"].astype(bool) & df["finisher_player_id"].notna()].copy()
    d["player_id"] = d["finisher_player_id"].astype(int)

    xcols = [f"x_{a}" for a in arms]
    pg = (
        d.groupby(["player_id", "season", "game_id"])
        .agg(a=("sfta", "sum"), n=("sfta", "size"),
             **{c: (c, "sum") for c in xcols})
        .reset_index()
    )
    ps = (
        pg.groupby(["player_id", "season"])
        .agg(a=("a", "sum"), n=("n", "sum"),
             **{c: (c, "sum") for c in xcols})
        .reset_index()
    )
    ps = ps.merge(names, on=["player_id", "season"], how="left")

    boards = {}
    for a in arms:
        b = ps[ps["n"] >= QUALIFY].copy()
        b["ftaoe"] = b["a"] - b[f"x_{a}"]
        b["ftaoe_per_100"] = b["ftaoe"] / b["n"] * 100
        boards[a] = b

    # OOF global anchored lift, finisher universe, per arm.
    smeans = d.groupby("season")["sfta"].transform("mean")
    base_dev = poisson_deviance(d["sfta"].values, smeans.values)

    results = {"arms": {}, "rankAgreementVsProduction": {}}
    for a in arms:
        pred_dev = poisson_deviance(d["sfta"].values, d[f"x_{a}"].values)
        oof_lift = (base_dev - pred_dev) / base_dev * 100
        results["arms"][a] = {
            "oofLiftPct": round(float(oof_lift), 4),
            "folds": fold_meta[a],
            "reliability": split_half_reliability(
                pg.rename(columns={f"x_{a}": "x"})[
                    ["player_id", "season", "game_id", "a", "x", "n"]
                ], "x"
            ),
            "calibration": decile_calibration(
                ps.rename(columns={f"x_{a}": "x"}), "x"
            ),
            "nQualified": int(len(boards[a])),
        }
        print(f"\n{a}: OOF lift {oof_lift:.4f}%  "
              f"full-season r {results['arms'][a]['reliability']['fullSeasonR']}  "
              f"calib slope {results['arms'][a]['calibration']['slope']}")

    for a in arms[1:]:
        m = boards["poisson_glm"].merge(
            boards[a], on=["player_id", "season"], suffixes=("_p", "_v")
        )
        rho, p = spearmanr(m["ftaoe_per_100_p"], m["ftaoe_per_100_v"])
        top20 = lambda fr, col: set(
            fr.nlargest(20, col)["player_id"].astype(str) + "_" + fr.nlargest(20, col)["season"]
        )
        ov = len(top20(m, "ftaoe_per_100_p") & top20(m, "ftaoe_per_100_v"))
        results["rankAgreementVsProduction"][a] = {
            "spearmanRho": round(float(rho), 4),
            "spearmanP": float(p),
            "top20Overlap": ov,
            "n": int(len(m)),
        }
        print(f"poisson_glm vs {a}: rho {rho:.4f}, top-20 overlap {ov}/20")

    results["design"] = (
        "Identical 6-fold season cross-fit and per-season anchoring on the "
        "finisher universe for every arm. Multinomial collapses the target to "
        "{0,1,2,3+} with the top class valued at its training-fold empirical "
        "mean. LightGBM early-stops on a random 10% of training rows, never on "
        "the evaluation fold."
    )
    results["qualifyPossessions"] = QUALIFY
    results["verdict"] = (
        "Read the reliability column, not the lift column: the possession-level "
        "event is near-pure noise under any learner, so per-possession lift "
        "cannot separate these models. Season-grain reliability can."
    )

    out = os.path.join(MODEL_DIR, "variant_model_family.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
