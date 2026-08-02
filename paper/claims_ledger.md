# Over Expected / FTAOE — Claims Ledger (Gate 1)

Every quantitative claim the paper could make, traced to the file that holds it.
Built 2026-08-02 by reading the repo, not from any prior conversation.

Repo: `NBA_OE/` @ `70e11b7`. Paths are relative to `NBA_OE/`.

**Status key**

| status | meaning |
|---|---|
| ✅ VERIFIED | number exists in a committed artifact; safe to cite |
| ⚠️ ASSERTED | stated in `paper/experiment_record.md` but the generating artifact was not saved; re-run to capture before citing |
| ⛔ SUPERSEDED | real artifact, but from a build that was later rejected or rebuilt; must not be cited as a current result |
| ❌ UNTRACEABLE | no artifact anywhere in the repo or its git history; cannot go in the paper |

---

## 0. The blocking finding

The prompt's headline claim and the repo's current headline result are not the same
number, the same model, the same target, or the same unit of analysis.

| | prompt says | repo actually has |
|---|---|---|
| lift | 18.83% | **0.195%** |
| learner | Poisson **LightGBM** | Poisson **GLM** (statsmodels) |
| unit | per **shot** (FGA) | per **possession** |
| target | `fta_from_shot` | `sfta` (shooting-foul + and-1 FTs per possession) |
| sample | 655,000+ over 3 seasons | 1,420,917 possessions over 6 seasons |
| validation | single split | 6-fold season cross-fit, all predictions OOF |
| source | `model_artifacts/metrics_gate_a.json` | `model_artifacts/headline_v4_context_metrics.json` |

Detail in §3 and §4. Everything downstream of this (abstract, contribution,
methods, validation) depends on which one the paper is about.

---

## 1. Data and scope

| # | Claim | Value | Source | Status |
|---|---|---|---|---|
| D1 | Seasons covered | 6, 2020-21 → 2025-26 | `paper/experiment_record.md:10`; `config.py:13-31` | ✅ |
| D2 | Games | 7,230 (1,080 in 2020-21, 1,230 each after) | `paper/experiment_record.md:10-11` | ✅ |
| D3 | Field-goal attempts | 1,282,312 | `paper/experiment_record.md:12` | ✅ |
| D4 | Possessions | 1,420,917 | `paper/experiment_record.md:12` | ✅ |
| D4b | Possessions with an attributable finisher | **1,392,350** (98.0% of D4) | `variant_archetype.py` run output, 2026-08-02 | ✅ **Resolves O2.** README's "1.39M" is the finisher universe, not a conflicting count of D4. Both are right; the paper must label which it means. Every model metric is computed on this universe. |
| D4c | Finisher possessions joinable to a player-season record | 1,384,016 (99.4% of D4b); 100% of those carry height and position; 1,248,388 (89.7%) carry prior-season FTr | `variant_archetype.py` run output | ✅ |
| D5 | Data sources | NBA Stats V3 live PBP + `shotchartdetail`, both public; no tracking/optical | `paper/experiment_record.md:13-14`; `pull.py` | ✅ |
| D6 | Possession splitter | `pbpstats` library, no custom logic | `paper/experiment_record.md:15` | ✅ |
| D7 | `sfta` distribution | 1,278,429 zeros / 34,460 ones / 103,037 twos / 4,769 threes / 213 fours / 9 fives (sums to D4) | `paper/experiment_record.md:20-23` | ✅ |
| D8 | FTs kept vs excluded | 255,738 kept; 67,569 excluded (technical, flagrant, clear-path, away-from-play, inbound, penalty) | `paper/experiment_record.md:22-23` | ✅ |
| D9 | Contaminated trips dropped | 533 (0.085% audit rate) | `paper/experiment_record.md:23-24` | ✅ |
| D10 | Target identity | `sfta == ft_and1 + ft_sf2 + ft_sf3` holds on all 1,420,917 rows | `paper/experiment_record.md:25` | ✅ |
| D11 | Finisher attribution rule | FT shooter → last maker → last turnover → last shooter | `paper/experiment_record.md:26-28` | ✅ |
| D12 | Finisher coverage | 0% of fouled possessions lack a finisher; ~2% of all possessions do | `paper/experiment_record.md:27-28` | ✅ |
| D13 | Qualification threshold | ≥300 finisher-possessions (~280 players/season) | `paper/experiment_record.md:67`; `reliability.json:qualify` | ✅ |
| D14 | Qualified player-seasons | 3,213 in shot_value; **1,691** at the FTAOE board grain | `paper/experiment_record.md:67-68`; `reliability.json:nPlayerSeasons` | ✅ |

---

## 2. Current headline xFTA model (v4 context) — the shipping model

Script: `train_possession_v4_context.py`. Artifact:
`model_artifacts/headline_v4_context_metrics.json`.

| # | Claim | Value | Source | Status |
|---|---|---|---|---|
| M1 | Specification | Poisson GLM (`statsmodels`), possession grain | `train_possession_v4_context.py:180-183` | ✅ |
| M2 | Features (7) | `period`, `seconds_remaining_in_period`, `score_margin`, `q4_or_ot`, `offense_is_home`, `opp_rate_logo`, `crew_rate_logo` | `headline_v4_context_metrics.json:features`; `train_possession_v4_context.py:45-53` | ✅ |
| M3 | Validation design | 6-fold season cross-fit; train on 5, predict the 6th; every prediction OOF | `train_possession_v4_context.py:172-176` | ✅ |
| M4 | **OOF anchored Poisson-deviance lift vs season-mean baseline** | **0.195%** | `headline_v4_context_metrics.json:oof_lift_pct` = 0.19549069915689565 | ✅ |
| M5 | Per-fold anchored lift | 0.185 / 0.168 / 0.170 / 0.254 / 0.244 / 0.152 % (2020-21 → 2025-26) | `headline_v4_context_metrics.json:folds[].lift_pct` | ✅ |
| M6 | Per-fold raw (unanchored) lift | 0.180 / 0.183 / 0.280 / 0.245 / 0.238 / 0.273 % | `folds[].lift_raw_pct` | ✅ |
| M7 | Season anchor factors | 1.0131 – 1.0253 | `folds[].anchor` | ✅ |
| M8 | Season baseline rates (`sfta`/poss) | 0.1776 / 0.1751 / 0.1928 / 0.1806 / 0.1817 / 0.1933 | `folds[].baseline` | ✅ |
| M9 | Anchoring rule | Per-season mean scaling to that season's own league rate, on the finisher universe | `headline_v4_context_metrics.json:anchoring`; `train_possession_v4_context.py:186-192` | ✅ |
| M10 | Export gate on anchoring | \|poss-weighted mean per 100\| ≤ 0.2 | `paper/experiment_record.md:56-57`; `scripts/validate_export.py` | ✅ |
| M11 | Leak control on `score_margin` | Margin taken at possession START (last-known margin shifted back one possession), not the terminal event | `train_possession_v4_context.py:124-133` | ✅ |
| M12 | Leak control on opponent/crew rates | Leave-one-game-out season rates, so the current game never enters its own feature | `train_possession_v4_context.py:69-96` | ✅ |
| M13 | `q4_or_ot` is a proxy | It is `period >= 4`, not true bonus state; V3 PBP carries no bonus state | `train_possession_v4_context.py:48-50`; `paper/experiment_record.md:53-54, 132` | ✅ |

### 2b. Fitted coefficients (the `score_margin` finding lives here)

All from `headline_v4_context_metrics.json:folds[].params`, one fit per fold.

| feature | 2020-21 | 2021-22 | 2022-23 | 2023-24 | 2024-25 | 2025-26 | status |
|---|---|---|---|---|---|---|---|
| const | −2.9272 | −2.8885 | −2.9708 | −2.9379 | −2.8727 | −3.0029 | ✅ |
| `period` | +0.0881 | +0.0863 | +0.0860 | +0.0810 | +0.0798 | +0.0862 | ✅ |
| `seconds_remaining_in_period` | −1.362e-4 | −1.535e-4 | −1.460e-4 | −1.436e-4 | −1.402e-4 | −1.532e-4 | ✅ |
| **`score_margin`** | +9.60e-5 | +9.52e-5 | +4.35e-5 | **+1.66e-5** | +1.93e-4 | **+2.17e-4** | ✅ |
| `q4_or_ot` | −0.0964 | −0.0877 | −0.0898 | −0.0876 | −0.0818 | −0.0878 | ✅ |
| `offense_is_home` | +0.0147 | +0.0162 | +0.0165 | +0.0167 | +0.0176 | +0.0164 | ✅ |
| `opp_rate_logo` | +3.8437 | +3.9167 | +3.8813 | +3.5926 | +3.9292 | +3.7837 | ✅ |
| `crew_rate_logo` | +1.9962 | +1.7506 | +2.2431 | +2.4038 | +1.7052 | +2.5275 | ✅ |

**2026-08-02 addendum.** §2c and §2d below were produced by re-running the two
variant tests against the current model, on Kevin's instruction. Both harnesses
were gated on reproducing production before their variant arms were read:
`variant_archetype.py` reproduces Giannis 2024-25 FTAOE at **311.84** vs the
shipping **311.8**, and `variant_model_family.py` reproduces split-half **0.8408**
vs the shipped **0.841** and padding K **67** vs **67**. Ledger items U1, U2, O2 and
O3 are resolved; O3 produced a **correction** to the experiment record.

**Note for drafting.** The prompt asks for "the `score_margin` feature-importance finding
and its officiating-behavior interpretation." In the *current* model `score_margin` is a
GLM coefficient, not a gain-based importance, it is the smallest-magnitude slope in the
model, and it moves by an order of magnitude across folds (1.66e-5 → 2.17e-4) with no
monotone trend. The large gain-based `score_margin` importances (C4 below) belong to
superseded tree models. An officiating-behavior claim resting on this is not supportable
as written. `opp_rate_logo` and `crew_rate_logo` are where the real signal is, and
`crew_rate_logo` is the defensible officiating result.

---

## 2c. Archetype / identity variant — RE-RUN, now citable

Script: `variant_archetype.py`. Artifact: `model_artifacts/variant_archetype.json`.
Replaces the unciteable U1. Three Poisson GLM arms, identical folds, identical
anchoring; the `headline` arm imports the production feature list and `load()`, so
it *is* the shipping model.

**The question.** FTAOE's model is context-only by design and never sees who is
shooting. Hand it the finisher's identity and does the leaderboard change?

| # | Arm | Features | Mean fold lift | Source | Status |
|---|---|---|---|---|---|
| V1 | `headline` (production) | 7 | **0.196%** | `variant_archetype.json:arms.headline` | ✅ |
| V2 | `archetype` (+ height, position) | 15 | **0.827%** | `arms.archetype` | ✅ |
| V3 | `identity` (+ prior-season FTr + missingness flag) | 17 | **1.786%** | `arms.identity` | ✅ |

| # | Comparison | Value | Status |
|---|---|---|---|
| V4 | headline vs archetype, **Spearman rho** | **0.9061** (p < 1e-300, n = 1,691) | ✅ |
| V5 | headline vs archetype, Pearson r | 0.9182 | ✅ |
| V6 | headline vs archetype, top-N overlap | top10 **6**, top25 14, top50 37, top100 72 | ✅ |
| V7 | headline vs archetype, rank shift | mean 27.2, max 228 | ✅ |
| V8 | headline vs identity, **Spearman rho** | **0.8320** (n = 1,691) | ✅ |
| V9 | headline vs identity, Pearson r | 0.8100 | ✅ |
| V10 | headline vs identity, top-N overlap | top10 **2**, top25 5, top50 18, top100 56 | ✅ |
| V11 | headline vs identity, max \|delta/100\| | 35.76 | ✅ |
| V12 | Production reproduction gate | Giannis 2024-25: 311.84 vs shipping 311.8 (delta 0.04) | ✅ PASS |

**Named movers (all ✅, from `topGainers`/`topLosers`).** Under `archetype`, the
biggest losers are tall: Bol Bol −11.49, Wembanyama −10.98 (2025-26), −10.13
(2024-25), −9.77 (2023-24), Kornet −8.78, Porziņģis −8.72, Holmgren −8.52. Under
`identity`, Rudy Gobert 2022-23 collapses **+20.06 → −15.70** (−35.76); Gobert is
in four of the eight largest drops.

**Interpretation for the paper.** This is a strong result and it cuts both ways,
which is why it belongs in Validation rather than Findings:

- Identity features *do* add per-possession fit (0.196% → 0.827% → 1.786%), so
  "context-only" costs measurable likelihood. Say so.
- The ordering survives anyway (rho 0.906 with height/position), so the
  leaderboard is not an artefact of withholding identity.
- But the **extreme tail moves a lot**: top-10 overlap is 6/10 under archetype and
  2/10 under identity. The claim "the ranking is unchanged" would be an overclaim.
  The honest claim is "the ranking is broadly preserved; the leaders are not."
- The `identity` arm is the conceptual centrepiece. Prior-season FTr *is* a
  measurement of the thing FTAOE measures, so feeding it in explains the signal
  away by construction. Gobert going from the best foul-drawer in the league to
  the worst is the cleanest possible demonstration that this is circularity, not
  improvement. That is the argument for excluding identity, stated as evidence
  rather than as a design preference.

---

## 2d. Model-family comparison — RE-RUN, now citable

Script: `variant_model_family.py`. Artifact:
`model_artifacts/variant_model_family.json`. Replaces the unciteable U2. Same
folds, same anchoring, four scoring dimensions per arm.

| # | Arm | OOF lift | Split-half r | **Full-season r** | Calib. slope | Status |
|---|---|---|---|---|---|---|
| F1 | `poisson_glm` (production) | 0.1955% | 0.8408 | **0.9135** | 0.4256 | ✅ |
| F2 | `multinomial` {0,1,2,3+} | 0.1956% | 0.8408 | **0.9135** | 0.4260 | ✅ |
| F3 | `poisson_lgbm` | **0.2538%** | 0.8419 | **0.9141** | **0.2108** | ✅ |

| # | Claim | Value | Status |
|---|---|---|---|
| F4 | GLM vs multinomial, leaderboard Spearman | **1.0000**, top-20 overlap **20/20** | ✅ |
| F5 | GLM vs LightGBM, leaderboard Spearman | **0.9988**, top-20 overlap 19/20 | ✅ |
| F6 | LightGBM per-fold best iteration | 305, 292, 288, 306, 304, 303 | ✅ |
| F7 | Multinomial collapsed-class value (3+) | 3.044–3.048 by fold, from training rows only | ✅ |
| F8 | Padding constant K, all three arms | 67 possessions | ✅ |

**Interpretation for the paper.** Two clean negative results, which is exactly
what a model-selection section should contain:

- **Modelling the count categories explicitly buys literally nothing.** The
  multinomial arm matches the Poisson GLM to four decimal places on lift and
  produces a **rank-identical** leaderboard (rho = 1.0000, 20/20). The lumpy
  support (2 is commoner than 1, because a foul on a miss awards two shots and an
  and-1 awards one) does not matter once predictions are aggregated. This is the
  honest answer to "why not model the categories?"
- **The boosted learner wins on per-possession fit and loses everywhere else.**
  LightGBM lifts 0.254% vs 0.196% (+30% relative), but full-season reliability
  moves 0.9135 → 0.9141 (nothing), player-season calibration slope gets **worse**
  (0.426 → 0.211), and the leaderboard is 0.9988-identical anyway. Extra
  flexibility buys per-event fit that does not survive aggregation, and costs
  calibration. That is the argument for the GLM, and it doubles as the direct
  answer to why the superseded LightGBM lineage (§3) was abandoned.

---

## 2e. Calibration — CORRECTION to the experiment record

Artifact: `variant_model_family.json:arms.poisson_glm.calibration`, independently
confirmed by re-running the repo's own `check_calibration.py`.

`paper/experiment_record.md:61` says: *"Player-season decile calibration on OOF
aggregates is diagonal (slope ~1)."* **This is wrong.**

| # | Claim | Value | Status |
|---|---|---|---|
| K1 | Player-season decile calibration slope (≥100 poss) | **0.426** | ✅ measured twice |
| K2 | Intercept | 0.0973 | ✅ |
| K3 | Pearson r across decile means | 0.4374 | ✅ |
| K4 | Max \|residual\| from identity | **13.57%** (decile 10) | ✅ |
| K5 | Mean \|residual\| | 4.87% | ✅ |
| K6 | Aggregate calibration | mean predicted 0.1835 vs actual 0.1853, **+0.95%** | ✅ |
| K7 | Predicted-rate range across deciles | 0.1737 – 0.1969 | ✅ |

**What is actually true.** The model is well calibrated **in aggregate** (K6,
+0.95%, and anchoring pins this by construction) but **not** across its own
predicted deciles (K1). That is expected, not a defect: predicted spread is driven
by context (opponent, crew, period mix) and spans only 0.174–0.197 (K7), while
player-season actual rates are dominated by the player skill the model is
deliberately blind to. Sorting player-seasons by predicted rate therefore does not
sort them by actual rate, and the narrow x-range attenuates the OLS slope on top of
that.

The paper must state calibration as: aggregate calibration holds by construction;
per-decile calibration at player-season grain is weak and the reason is the design.
It must **not** repeat "well-calibrated across the range." `experiment_record.md:61`
should be corrected in the same pass.

---

## 3. Superseded model results — real artifacts, rejected builds

| # | Claim | Value | Source | Why superseded |
|---|---|---|---|---|
| S1 | **"18.83% lift"** | 18.83 | `model_artifacts/metrics_gate_a.json:lift_vs_baseline_pct` | ⛔ Target was `fta_from_shot` at FGA grain (`config.py:86` @ `e4a49a8^`), baseline mean 0.032112. That target was found to be wrong: `fix_training_targets.py` rescaled every shot's target per player-season to match basketball-reference totals (commit `ec5dd56`), the approach was then abandoned, and `tests/test_no_br_scaling.py` now **fails the build** if that path is reintroduced. |
| S1a | Gate A sample | train 432,269 (2022-23 + 2023-24) / test 217,738 (2024-25) = **650,007**, not 655,000+ | `metrics_gate_a.json`; `train_model.py:split_gate_a` @ `e4a49a8^` | ⛔ |
| S1b | Gate A learner | LightGBM Poisson, lr 0.05, 63 leaves, min_child 200, feature/bagging 0.8, best_iteration 217, 10 features | `train_model.py:LGBM_PARAMS` @ `e4a49a8^`; `headline_gate_a.txt` header | ⛔ |
| S2 | Gate A on `sfta` | 4.32% lift; 14 features; train 352,410 / test 177,132; best_iteration 230 | `model_artifacts/metrics_gate_a_headline.json` | ⛔ Possession-grain LightGBM, superseded by the v3/v4 GLM chain |
| S3 | v3 clean model | OOF lift 0.104%; 5 features incl. the mislabelled `in_bonus` | `headline_v3_clean_metrics.json`; `headline_v3_clean_final.json` | ⛔ Superseded by v4; `in_bonus` renamed `q4_or_ot` |
| S4 | v3 no-location variant | OOF lift 0.126%, 3 folds only | `headline_v3_clean_noloc_metrics.json` | ⛔ |
| C4 | `score_margin` gain importance | 1,027,884 (2nd of 10); also 77,140 and 91,369 in two other variants | `feature_importance.csv`, `feature_importance_headline.csv`, `headline_v2_importance.csv` | ⛔ All three are tree models on superseded targets/feature sets. None is the shipping model. |
| S5 | Orphaned calibration plots | `calibration_global.png`, `calibration_per_zone.png` | generated by `evaluate.py` @ `3bea8e8`, since deleted | ⛔ Plot the FGA-era `fta_from_shot` target. No code in the tree regenerates them. |

---

## 4. Untraceable — cannot appear in either version

| # | Prompt claim | Finding |
|---|---|---|
| U1 | **Archetype-variant test, Spearman rho = 0.92** | ✅ **RESOLVED 2026-08-02 by re-running it. See §2c.** The original was unrecoverable: `variants.py` printed rho to stdout, wrote no metrics file, and read a predictions CSV that no longer exists; it also ran on the broken `fta_from_shot` target, so recovering it would not have helped. Re-run against the shipping model gives **rho = 0.9061** (height + position) and **0.8320** (+ prior-season FTr). The remembered "0.92" is closest to the new **Pearson r = 0.9182**, but that is coincidence, not provenance: cite §2c, never the remembered figure. |
| U2 | **Poisson-vs-multiclass comparison** | ✅ **RESOLVED 2026-08-02 by re-running it. See §2d.** The original was printed-only, its predictions CSV deleted, its surviving PNG plots the broken target, and its config contradicted its own docstring (4-class in prose, `num_class: 3` in params, classes 0/1/2 in the expectation). Re-run on the current target: the multinomial arm is **rank-identical** to the Poisson GLM (rho = 1.0000, top-20 20/20). A third arm (Poisson LightGBM) was added to answer the learner question the prompt's "LightGBM" framing raises. |
| U3 | **Per-zone calibration of the FTAOE model** | ❌ **Still does not exist, and should not be manufactured.** Per-zone is an **xFG** result (`xfg_evaluate.py` → `xfg_reliability.png`); zones are a property of shot location, and the FTAOE model is at possession grain with no location feature at all, so a per-zone FTAOE calibration is not a well-defined object. Its nearest counterpart, per-decile calibration at player-season grain, is now captured in §2e, and it does **not** say what the prompt assumed it would. |
| U4 | **`ftaoe_centered` rationale** | ❌ Not a shipping concept. `ftaoe_centered` appears only in `build_leaderboard.py:73`, the legacy FGA-grain script writing the legacy `player_season_xfta` table. The production path is `build_possession_leaderboard_clean.py`, and season comparability is handled by **anchoring** (M9), not centering. The season-drift story is real; the mechanism named in the prompt is the wrong one. |
| U5 | "655,000+ shots/possessions across 3 seasons" | ❌ 650,007 rows, and it describes the superseded Gate A split, not the current 1,420,917-possession / 6-season build. |
| U6 | "18.83% lift" as a current result | ❌ See S1. |

---

## 5. Reliability of FTAOE as a player metric — the strongest available evidence

Source: `model_artifacts/reliability.json`, generated by `scripts/analyze_reliability.py`.

| # | Claim | Value | Status |
|---|---|---|---|
| R1 | Split-half r (odd/even games) | 0.841 | ✅ |
| R2 | Full-season r (Spearman-Brown corrected) | **0.914** | ✅ |
| R3 | Mean possessions per half | 354 | ✅ |
| R4 | Padding constant k | 67 | ✅ |
| R5 | Mean year-over-year r | 0.85 | ✅ |
| R6 | YoY pairs | 0.852 (n=208), 0.834 (n=210), 0.859 (n=219), 0.865 (n=222), 0.840 (n=217) | ✅ |
| R7 | Player-seasons in the pool | 1,691 (qualify ≥300 poss) | ✅ |

**Drafting note.** This is the paper's real quantitative backbone. A metric with
per-event lift of 0.195% but season-level reliability of 0.914 is a coherent and
interesting claim: the possession-level event is nearly all noise, and the value is in
the anchored aggregation. `paper/experiment_record.md:135-138` already says exactly this.
That is a stronger, more honest paper than one built on a retracted 18.83%.

---

## 6. xFG model (the sibling model, needed for shot value)

| # | Claim | Value | Source | Status |
|---|---|---|---|---|
| X1 | Specification | LightGBM binary, 700 trees, lr 0.03, 63 leaves, min_child 300, subsample 0.8, colsample 0.8, reg_lambda 1.0, seed 42 | `xfg_model.py:45-46`; `paper/experiment_record.md:33-34` | ✅ |
| X2 | Features (11) | distance, angle, x, y, period, clock, `run_margin`, zone_basic, zone_area, action_type, shot_type | `xfg_model.py:33-38` | ✅ |
| X3 | Calibration | Isotonic on a game-grouped 20% split; no game straddles fit/calib | `xfg_model.py:112-113` | ✅ |
| X4 | Split | fit 345,975 / calib 86,294 / holdout 217,738 (2024-25), make rate 0.4675 | `xfg_metrics.json` | ✅ |
| X5 | Raw holdout | AUC 0.6578, Brier 0.22427, log-loss 0.63727, ECE 0.00959 | `xfg_metrics.json:raw` | ✅ |
| X6 | Calibrated holdout | AUC 0.65762, Brier 0.22422, log-loss 0.63836, ECE 0.00421 | `xfg_metrics.json:calibrated` | ✅ |
| X7 | **Leakage finding** | Leaky AUC 0.6705 → clean 0.6578 (−1.3 AUC pts was leakage); ECE 0.0040 → 0.0042 | `paper/experiment_record.md:78-82` | ✅ Controlled A/B retrain on an identical split. Genuinely publishable. |
| X8 | Per-zone calibration | `xfg_reliability.png` | `xfg_evaluate.py:39-62` | ✅ figure exists |
| X9 | Cross-fit + anchoring for player eval | 6-fold season cross-fit, anchors 1.013–1.025 | `paper/experiment_record.md:44-46` | ✅ |

---

## 7. Audit findings (2026-07-01) — publishable as methodology contributions

From `paper/experiment_record.md:70-101`. All ✅.

| # | Finding | Before → after |
|---|---|---|
| A1 | CRITICAL: xFG score-margin leak | AUC 0.6705 → 0.6578 |
| A2 | MEANINGFUL: no xFG season anchoring | league FG pts over expected/100 ran −1.70 … +1.07 → −0.25 … +0.42 |
| A3 | MEANINGFUL: flat 0.77 FT baseline vs actual 0.775–0.784 | league FT pts over expected/100 +0.11 … +0.32 → −0.02 … +0.06 |
| A4 | REAL BUT IMMATERIAL: xFTA terminal-event margin leak | max \|FTAOE delta\| 1.03 FTs over 1,691 player-seasons, p99 0.73, **zero** top-20 membership changes, max rank shift 5 |
| A5 | COSMETIC | `in_bonus` renamed `q4_or_ot` (it was always `period >= 4`) |
| A6 | Headline effect | 2024-25 points-over-expected/100 leader flipped Jimmy Butler III 23.82 (leaky) → Ty Jerome 22.99 (clean); Butler clean 22.42. FTAOE board effectively unchanged (Giannis 311.3 → 311.8). |

---

## 8. Leaderboard / direction checks

From `paper/experiment_record.md:103-114`. All ✅.

| # | Claim | Value |
|---|---|---|
| L1 | 2024-25 FTAOE top | Giannis +311.8, Harden +192.5, Butler +190.7, SGA +175.0 |
| L2 | 2024-25 FTAOE bottom | Bridges −120.0, Thompson −104.5, Pritchard −103.7, Hield −97.3 |
| L3 | 2024-25 shot-making top | Jokic +10.1pp, Jerome +9.1, Durant +8.6, Pritchard +8.0 |
| L4 | 2024-25 shot-making bottom | Mogbo −14.6, Capela −9.7 |
| L5 | Orthogonality example | Curry: shot-making +5.4pp with FTAOE −23 (cross-season means) |
| L6 | League zone FG% vs public values | RA 0.641–0.671, paint non-RA 0.427–0.446, mid 0.406–0.420, corner 3 0.383–0.397, ABT3 0.346–0.360, eFG 0.531–0.546, FT 0.775–0.784 |
| L7 | League FT% by season (FTA-weighted) | 0.7746–0.7843 |

---

## 9. Limitations — all sourced, all ✅

From `paper/experiment_record.md:116-138`.

| # | Limitation | Source |
|---|---|---|
| N1 | No tracking data: no defender distance, shot clock, touch time, dribbles. Caps xFG AUC ~0.66. Calibration, not discrimination, is the design goal. | `:118-121` |
| N2 | `action_type` describes the attempt and may weakly correlate with outcome. Disclosed, standard in public xFG models. | `:122-124` |
| N3 | NBA 2025-26 heave rule creates a cross-season discontinuity: ~50 shots at 40+ ft at 44% vs ~600 at 2-4% in earlier seasons. | `:125-128` |
| N4 | ~1,800 shots/season (2021-22…2024-25) carry no zone/location, ~0.8%, excluded from xFG. | `:129-131` |
| N5 | `q4_or_ot` is a crude proxy; true bonus state absent from public V3 feed. | `:132` |
| N6 | `sfta` is shooting-foul FTs only; penalty FTs out of scope by design. | `:133-134` |
| N7 | **xFTA per-possession lift is ~0.2%: possession-level foul events are mostly noise given public features. The metric's value is the anchored aggregation, not per-possession discrimination.** | `:135-138` |
| N8 | Shot-selection confound: a context-only model absorbs shot-selection skill, so FTAOE measures contact craft given the shot diet, not total foul-drawing ability. | design of M2 (no player-identity features); `README.md:59-63` |

N7 is the limitation the prompt asks to be stated as a finding rather than buried.
It is already stated that way in the repo, and it is flatly incompatible with an
18.83% headline.

---

## 10. Venue tooling reality check

Asked: which of three skill repos provides LaTeX/arXiv scaffolding, a JQAS/De Gruyter
template, a Sloan/StatsBomb template, citation verification, drafting workflows, and an
adversarial review step.

**Only one of the three named repos is installed.**

| repo | status |
|---|---|
| `imbad0202/academic-research-skills` | ✅ installed, v3.15.0, `~/.claude/plugins/cache/academic-research-skills/` |
| `amatray/claude-skills-public` | ❌ not installed, not on disk |
| `Master-cai/Research-Paper-Writing-Skills` | ❌ not installed, not on disk |

What ARS actually ships:

> **2026-08-02 change: the preprint destination is Zenodo, not arXiv.** No arXiv
> endorser, and Zenodo has no endorsement gate, so it is the guaranteed path to a
> permanent DOI'd preprint. Zenodo needs no venue-specific LaTeX class: the same
> PDF built for the journal is what gets deposited, with the LaTeX source, the
> code-repo link, and a data description as supplementary files. It does need a
> metadata block (title, authors, abstract, keywords, licence) prepared alongside
> the PDF; recommended licence CC-BY 4.0. Full deposit checklist and the optional
> GitHub-release-DOI integration are in `paper/submission_targets.md`. The
> equivalent note for Football OE is at
> `Football OE/docs/paper-submission-targets.md`. Neither build spec existed as a
> file, so those two documents now *are* the specs' venue sections.

| need | covered? | what exists |
|---|---|---|
| (a) LaTeX scaffolding (Zenodo needs no venue class) | ✅ sufficient | `academic-paper/templates/latex_article_template.tex`, `references/latex_template_reference.md`. Generic `article` class, which is all a Zenodo deposit requires. |
| (a) JQAS / De Gruyter template | ❌ **none** | Zero hits for "De Gruyter", "JQAS", "Quantitative Analysis in Sports" across the whole plugin. |
| (a) Sloan / StatsBomb template | ❌ **none** | Zero hits for "Sloan" or "StatsBomb". Closest is `templates/conference_paper_template.md`, a generic 2,000–5,000-word skeleton. |
| (b) citation verification | ✅ **strong** | `scripts/crossref_client.py`, `openalex_client.py`, `semantic_scholar_client.py`, `arxiv_client.py`, plus `verification_gate/`, `verification_cache.py`, `citation_verification_summary.py`, and `/ars-citation-check`. This is the best-covered requirement. |
| (c) section drafting / manuscript generation | ✅ | `/ars-full`, `/ars-outline`, `/ars-plan`; 12-agent pipeline |
| (d) adversarial / peer-review simulation | ✅ | `academic-paper-reviewer` skill with `devils_advocate_reviewer_agent`, `domain_reviewer_agent`, `editorial_synthesizer_agent`; `/ars-reviewer` |

**Consequence.** Per the prompt's instruction to say so explicitly rather than guess:
neither the JQAS/De Gruyter journal template nor a Sloan/StatsBomb submission template
exists in any installed skill. I will use the generic academic LaTeX template for the
canonical version and the generic conference template for the derivative, and will fetch
each venue's live author guidelines from the web at Gate 5 rather than inventing
formatting requirements.

Sloan's innovation-paper page limit is also unconfirmed and must be checked against the
live CFP, not assumed.

---

## 11. What the paper can honestly claim

Given the ledger, three viable framings:

1. **Reliability-first (recommended).** The contribution is a public-data,
   leak-audited, season-anchored foul-drawing metric that is 0.914-reliable at
   season grain and 0.85 year-over-year, built on a model whose per-possession
   lift is deliberately reported as ~0.2%. The honesty is the paper. Headline
   numbers: R2 (0.914), R5 (0.85), M4 (0.195%), D14 (1,691 player-seasons).

2. **Leakage-and-audit paper.** The contribution is the audit methodology: A1–A6,
   with the controlled A/B retrain (X7) as the centrepiece, and the demonstration
   that a leak worth 1.3 AUC points moved the public leaderboard's top name. Fully
   sourced, genuinely novel for public sports-analytics work.

3. **Both**, with the xFG leak audit as the methods contribution and FTAOE
   reliability as the applied result. This is the closest fit to the prompt's
   requested structure and uses the most of the ledger.

None of the three supports an 18.83% headline.

---

## 12. Open items before Gate 2

| # | Item | Status |
|---|---|---|
| O1 | Which framing (§11) | ✅ **Framing #3 chosen** (2026-08-02): xFG leak audit as the methods contribution, FTAOE reliability as the applied result. |
| O2 | Possession count 1,420,917 vs 1.39M | ✅ Resolved. Not a conflict: 1,420,917 total, 1,392,350 with a finisher. See D4/D4b. |
| O3 | xFTA per-decile calibration | ✅ Resolved, and it produced a **correction**: measured slope is **0.426**, not the "~1" claimed at `experiment_record.md:61`. See §2e. |
| O4 | U1 archetype test | ✅ Re-run against the current model. See §2c. |
| O5 | U2 multiclass comparison | ✅ Re-run against the current target, plus a third LightGBM arm. See §2d. |
| O6 | Venue requirements | ⬜ Fetch live at Gate 5: Sloan innovation-track page limit, JQAS/De Gruyter author guidelines. Zenodo needs no template but needs the metadata block. |
| O7 | **Correct `experiment_record.md:61`** | ⬜ The "diagonal (slope ~1)" line is wrong and should be fixed in the same pass as Gate 2, so the repo and the paper agree. |
| O8 | Kill the orphaned calibration PNGs | ⬜ `calibration_global.png` / `calibration_per_zone.png` plot the abandoned target and no code regenerates them (§3 S5). Delete or move to `_v3_archive/` so nobody cites them. |

---

## 13. Changelog

- **2026-08-02** — Gate 1 built. Headline finding: the 18.83% lift is superseded (§0, §3).
- **2026-08-02** — Gate 2: canonical draft written under framing #3, 12 pages,
  compiled. 24 citations, every one resolved against CrossRef or OpenAlex; 6
  candidates dropped for failing verification. 21/22 spot-checked numbers
  reconcile against artifacts (the 22nd is a rounding presentation, not drift).
- **2026-08-02** — Framing #3 approved. U1 and U2 re-run against the current model
  and are now citable (§2c, §2d); O2 and O3 resolved; O3 produced a correction to
  the experiment record (§2e). Preprint destination changed arXiv → Zenodo (§10).
