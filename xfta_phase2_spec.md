# xFTA — Phase 2: Model + Predictions + Leaderboard (Claude Code task spec)

## Context

The Phase 1 data pipeline is complete. `xfta.db` holds 655k FGA rows in
`training_fga`, one row per field-goal attempt, with the target `fta_from_shot`
(0/1/2/3) and the feature columns. All validation passed.

This phase trains the model that turns actual FTA into **expected** FTA (xFTA), then
computes the leaderboard stat — **FTAOE = actual FTA from shooting fouls − xFTA** —
and wires it into the existing Streamlit dashboard, replacing the raw stand-in.

**Read first:** `config.py` (the feature list lives here), `SCHEMA.md` (the
`training_fga` columns), and `xfta_phase1_spec.md` (the decisions behind the table).
Do not re-derive the data — consume `training_fga` as-is.

## The stat, precisely

xFTA per shot = the model's expected number of free throws this FGA should produce,
given **only the shot context** — never who took it. A player's season FTAOE is the
sum over his shots of (actual `fta_from_shot` − predicted xFTA). Positive = draws more
shooting fouls than his shot diet predicts. That residual is the whole point: the shot
features already absorb *where* and *how* he shoots, so FTAOE isolates the part that
isn't explained by shot selection.

## Model design — decisions, do not re-litigate

**Headline objective: single-stage Poisson regression (LightGBM, `objective='poisson'`)**
predicting `fta_from_shot` directly. The prediction *is* xFTA. Simple, interpretable,
sums cleanly to a season total.

**Headline feature set (context-only).** Read these exact columns from `config.py` —
do not hardcode. Default headline set:
`shot_distance, shot_zone_basic, shot_zone_area, action_type, shot_type, period,
seconds_remaining_in_period, score_margin, in_bonus, home_or_away`.

**Held out of the headline model** (used only in the variant comparisons below):
`shooter_height, shooter_position` (archetype variant) and
`prior_season_ftr, prior_season_drive_rate` (year-over-year variant). The headline
model must not see any player-identity signal. Add a runtime assert that the headline
feature list contains none of those four columns.

**Categoricals:** `shot_zone_basic, shot_zone_area, action_type, shot_type,
home_or_away` are categorical. `action_type` is high-cardinality (~50–70 values) — use
LightGBM **native** categorical handling (pandas `category` dtype + `categorical_feature`),
not one-hot.

**Hyperparameters:** don't over-tune for v1. `learning_rate=0.05`, `num_leaves=63`,
`min_child_samples=200` (the positive class is rare — guard against overfitting to
freak foul events), `n_estimators=2000` with **early stopping** (patience 50) on the
validation fold's Poisson deviance. No Optuna pass for v1.

### Leakage-free predictions: out-of-fold by season

A single train/test split is fine for *validating* the model, but the leaderboard
needs an xFTA for every one of the 655k shots, and no shot's prediction may come from
a model that trained on that shot. So:

- **Validation (Gate A):** train on 2022-23 + 2023-24, test on held-out 2024-25.
  Report metrics on 2024-25. This proves generalization to an unseen season.
- **Leaderboard predictions (Gate B):** 3-fold cross-fit **by season**. For each
  season, train on the other two and predict that season. Every shot's xFTA then comes
  from a model that never saw its season. ~3 fits, minutes on 655k rows.
- Also train one **final model on all three seasons**, saved to disk, for scoring any
  future season later. (Not used for the historical leaderboard.)

### The cross-season baseline caveat (build for it now)

Leaguewide, in a calibrated model, total actual FTA ≈ total xFTA, so leaguewide FTAOE
≈ 0 by construction *within the data the model saw*. Across seasons the foul
environment drifts (officiating points of emphasis move year to year). For within-season
player ranking this is irrelevant — it cancels. For Kevin's later season-vs-season
comparison it is not. So produce **two** FTAOE columns:
- `ftaoe` — raw (actual − xFTA).
- `ftaoe_centered` — per season, subtract that season's league-mean per-shot residual,
  so each season is centered on its own league. Use `ftaoe_centered` for cross-season
  comparisons; document why in SCHEMA.md.

## Working discipline + gates

Same gate discipline as Phase 1. Commit at each gate. Do not cross a gate without my
explicit approval in chat.

- **Gate A — sanity.** Single split (train 2022-24, test 2024-25). Produce the full
  validation report (below). **STOP and show me:** the global calibration plot, held-out
  Poisson deviance, the top-10 / bottom-10 shots by xFTA, the 20-shot spot-check table,
  and the held-out-season leaderboard top-30. This is the go/no-go on whether the model
  is trustworthy.
- **Gate B — predictions + leaderboard + variants.** After I approve: run the 3-fold
  season cross-fit, write the predictions and leaderboard tables, run the two variant
  comparisons, wire the dashboard. **STOP and show me** the real all-seasons leaderboard
  top-30 and the variant-comparison results.

## Validation report (Gate A — print all of it)

1. **Held-out Poisson deviance** on 2024-25, plus a naive baseline (predict every
   shot's xFTA = train-set mean `fta_from_shot`) so the lift is legible.
2. **Global calibration plot** — bucket held-out predictions into 10 deciles, plot mean
   predicted xFTA vs mean actual FTA per bucket, with the diagonal. Save PNG to
   `model_artifacts/`. This is the single most important output.
3. **Per-zone calibration** — the same calibration check computed *within* each
   `shot_zone_basic` (Restricted Area, In The Paint (Non-RA), Mid-Range, Above the
   Break 3, etc.). A model can be globally calibrated but locally biased. **This is the
   defender-data trigger from Phase 1:** if contested zones (mid-range, paint non-RA)
   come out systematically off, that's the signal that v2 needs closest-defender
   buckets. Flag any zone whose calibration slope deviates materially from 1.
4. **Top/bottom-10 shots by xFTA** — print shot description, zone, action_type, made/
   missed. Top should be at-rim drives, dunks, cutting layups. Bottom should be open,
   long, off-the-dribble 3s. If it's inverted, the model is broken.
5. **20-shot spot-check** — 20 random shots with predicted xFTA, actual fta_from_shot,
   game_id, event_id, player name, full shot description. This is the table to hand-verify
   against NBA.com clips before trusting anything. Do not skip it.
6. **Feature importance** — gain-based, written to `model_artifacts/feature_importance.csv`
   (the dashboard's Calibration tab reads this).

## Variant comparisons (Gate B — settles two open questions empirically)

These are *not* new headline models — they exist to inform decisions, then get shelved.

1. **Archetype variant (settles the height/position question).** Train an identical
   model with `shooter_height, shooter_position` added. Compute the player-season
   leaderboard from it. Report: Spearman rank correlation between this board's top-100
   and the headline board's top-100, and the 10 players who move the most (and which
   direction). Expected: adding height suppresses bigs. **Print the side-by-side top-30
   so the call is visible**, then default to the headline (context-only) board. If the
   boards barely differ, the question was moot; if bigs collapse, that confirms holding
   them out was right.
2. **Multiclass calibration check (confirms Poisson is the right objective).** Fit one
   LightGBM multiclass model (`num_class=4`, predicting P(0/1/2/3)); derive xFTA as the
   expected value `0·P0 + 1·P1 + 2·P2 + 3·P3`. Compare its held-out calibration plot to
   Poisson's. Default to Poisson; switch only if multiclass is **clearly** better
   calibrated. Report both plots.

## Leaderboard + dashboard activation (Gate B)

- Write a `predictions` table (`game_id, event_id, xfta`) and add/refresh an `xfta`
  column on `training_fga` joined on `(game_id, event_id)`.
- Build `player_season_xfta`: one row per (player_id, season) with player name, team,
  `fga`, `actual_fta_from_fouls`, `xfta_total`, `ftaoe`, `ftaoe_centered`,
  `ftaoe_per_100_fga`, `ftaoe_per_100_poss` (use `player_season.possessions`). Min-FGA
  filtering happens in the dashboard, so store everyone.
- **Dashboard:** the Leaderboard tab now reads `player_season_xfta` and the real
  FTAOE columns instead of the raw stand-in — remove the "raw foul-drawing rate"
  placeholder label. The Calibration tab now renders the saved calibration PNG(s), the
  feature-importance bar chart from the CSV, and the per-player-season residual
  histogram. Everything still must not crash if a table is missing.

## Deliverables

- `train_model.py` — trains headline model (split for Gate A; season cross-fit for
  Gate B), saves the all-seasons model + per-fold models, writes predictions.
- `evaluate.py` — the full validation report + calibration PNGs + spot-check printout.
- `variants.py` — the two variant comparisons.
- `build_leaderboard.py` — builds `player_season_xfta` from predictions.
- `model_artifacts/` — model files, `feature_importance.csv`, calibration PNGs,
  `metrics.json` (deviance, baseline, per-zone slopes).
- Updated `dashboard/` (Leaderboard + Calibration tabs live), `SCHEMA.md`, `README.md`.

## Start here

Read `config.py`, `SCHEMA.md`, and `training_fga`'s columns. Implement
`train_model.py` and `evaluate.py` for the **Gate A single split only** (train 2022-24,
test 2024-25). Run it. **Print the full Gate A validation report and STOP.** Do not run
the cross-fit, variants, or dashboard wiring until I approve Gate A.
