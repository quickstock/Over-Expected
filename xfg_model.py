"""xFG% — expected field-goal percentage. Gate 1.

One row = one FGA (reuses the xFTA shot table, no new pulls). Target is
shot_made (binary). LightGBM -> isotonic-calibrated P(make), because an
"expected" stat is only useful if the probability is calibrated.

Per Gate 0 there is no per-shot tracking (defender distance, shot clock,
touch time, dribbles are aggregate-per-player only), so v1 is built on the
per-shot context already in xfta.db. score_margin is rebuilt into a clean
running |margin| because the raw column is only stamped on scoring events
(55% zeros == missing, not tied).

Split mirrors xFTA Gate A: train 2022-23 + 2023-24, hold out 2024-25.
"""
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

from config import DB_PATH

TRAIN_SEASONS = ("2022-23", "2023-24")
HOLDOUT_SEASON = "2024-25"
ART = Path(__file__).parent / "model_artifacts"

NUM_FEATURES = [
    "shot_distance", "angle_deg", "shot_x", "shot_y",
    "period", "seconds_remaining_in_period", "run_margin",
]
CAT_FEATURES = ["shot_zone_basic", "shot_zone_area", "action_type", "shot_type"]
FEATURES = NUM_FEATURES + CAT_FEATURES


def make_clf() -> LGBMClassifier:
    """The shared xFG% classifier config (used by the holdout fit here and
    the season cross-fit in shot_value.py, so both score identically)."""
    return LGBMClassifier(
        objective="binary", n_estimators=700, learning_rate=0.03,
        num_leaves=63, min_child_samples=300, subsample=0.8,
        subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
        random_state=42, n_jobs=-1, verbose=-1,
    )


def load() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        """SELECT s.game_id, s.event_id, s.period,
                  s.seconds_remaining_in_period, s.shot_made,
                  s.shot_x, s.shot_y, s.shot_distance,
                  s.shot_zone_basic, s.shot_zone_area,
                  s.action_type, s.shot_type, s.score_margin, g.season
           FROM shots s JOIN games g ON g.GAME_ID = s.game_id
           WHERE g.season IN (?, ?, ?)
             AND s.shot_zone_basic IS NOT NULL AND s.shot_zone_basic != ''
             AND s.shot_x IS NOT NULL AND s.shot_y IS NOT NULL""",
        conn, params=(*TRAIN_SEASONS, HOLDOUT_SEASON),
    )
    conn.close()
    return df


def engineer(df: pd.DataFrame) -> pd.DataFrame:
    # Angle off the central axis to the rim: 0deg = straight on, ~90deg =
    # corner. Captures the corner-vs-central effect distance alone misses.
    df["angle_deg"] = np.degrees(np.arctan2(df["shot_x"].abs(), df["shot_y"]))

    # Clean running |score differential|: raw score_margin is only stamped
    # on scoring events, so treat 0 as missing and carry the last real
    # reading forward within each game (chronological order). |.| is
    # perspective-free (score_margin is signed by the shooting team).
    df = df.sort_values(
        ["game_id", "period", "seconds_remaining_in_period"],
        ascending=[True, True, False],
    )
    absm = df["score_margin"].abs().where(df["score_margin"] != 0)
    df["run_margin"] = absm.groupby(df["game_id"], sort=False).ffill().fillna(0)

    for c in CAT_FEATURES:
        df[c] = df[c].astype("category")
    return df


def main() -> None:
    ART.mkdir(exist_ok=True)
    df = engineer(load())
    print(f"loaded {len(df):,} FGA "
          f"({(df['season'].isin(TRAIN_SEASONS)).sum():,} train / "
          f"{(df['season'] == HOLDOUT_SEASON).sum():,} holdout); "
          f"league make rate {df['shot_made'].mean():.3f}")

    train = df[df["season"].isin(TRAIN_SEASONS)]
    hold = df[df["season"] == HOLDOUT_SEASON]

    # Split train into fit / calibration by GAME so no game straddles the
    # boundary (same no-leakage discipline as xFTA).
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    fit_idx, cal_idx = next(gss.split(train, groups=train["game_id"]))
    fit, cal = train.iloc[fit_idx], train.iloc[cal_idx]

    clf = make_clf()
    clf.fit(fit[FEATURES], fit["shot_made"])

    # Isotonic calibration on the held-out calibration games.
    cal_clf = CalibratedClassifierCV(FrozenEstimator(clf), method="isotonic")
    cal_clf.fit(cal[FEATURES], cal["shot_made"])

    y = hold["shot_made"].to_numpy()
    p_raw = clf.predict_proba(hold[FEATURES])[:, 1]
    p_cal = cal_clf.predict_proba(hold[FEATURES])[:, 1]

    def ece(p: np.ndarray, n_bins: int = 10) -> float:
        bins = np.clip((p * n_bins).astype(int), 0, n_bins - 1)
        out = 0.0
        for b in range(n_bins):
            m = bins == b
            if m.any():
                out += m.mean() * abs(p[m].mean() - y[m].mean())
        return out

    metrics = {
        "n_train_fit": int(len(fit)), "n_calib": int(len(cal)),
        "n_holdout": int(len(hold)),
        "holdout_make_rate": round(float(y.mean()), 4),
        "raw": {
            "brier": round(brier_score_loss(y, p_raw), 5),
            "logloss": round(log_loss(y, p_raw), 5),
            "auc": round(roc_auc_score(y, p_raw), 5),
            "ece": round(ece(p_raw), 5),
        },
        "calibrated": {
            "brier": round(brier_score_loss(y, p_cal), 5),
            "logloss": round(log_loss(y, p_cal), 5),
            "auc": round(roc_auc_score(y, p_cal), 5),
            "ece": round(ece(p_cal), 5),
        },
    }
    (ART / "xfg_metrics.json").write_text(json.dumps(metrics, indent=2))

    # Holdout predictions for the evaluator (calibration + sanity tables).
    out = hold[[
        "game_id", "event_id", "season", "shot_distance", "angle_deg",
        "shot_zone_basic", "shot_zone_area", "action_type", "shot_type",
        "shot_made",
    ]].copy()
    out["xfg_raw"] = p_raw.round(4)
    out["xfg"] = p_cal.round(4)
    out.to_csv(ART / "xfg_holdout_predictions.csv", index=False)
    clf.booster_.save_model(str(ART / "xfg_lgbm.txt"))

    print(json.dumps(metrics, indent=2))
    print(f"\nwrote {ART/'xfg_holdout_predictions.csv'} ({len(out):,} rows), "
          f"{ART/'xfg_lgbm.txt'}, {ART/'xfg_metrics.json'}")


if __name__ == "__main__":
    main()
