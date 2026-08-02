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
| D4b | Possessions (conflicting) | "1.39M" | `README.md:41`; `CASE_STUDY.md:26` | ⚠️ conflicts with D4; resolve before citing |
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

**Note for drafting.** The prompt asks for "the `score_margin` feature-importance finding
and its officiating-behavior interpretation." In the *current* model `score_margin` is a
GLM coefficient, not a gain-based importance, it is the smallest-magnitude slope in the
model, and it moves by an order of magnitude across folds (1.66e-5 → 2.17e-4) with no
monotone trend. The large gain-based `score_margin` importances (C4 below) belong to
superseded tree models. An officiating-behavior claim resting on this is not supportable
as written. `opp_rate_logo` and `crew_rate_logo` are where the real signal is, and
`crew_rate_logo` is the defensible officiating result.

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
| U1 | **Archetype-variant test, Spearman rho = 0.92** | ❌ `variants.py` (deleted, recoverable at `e4a49a8^`) computed `spearmanr(...)` and **printed to stdout only**. No metrics file was ever written. It read `model_artifacts/cross_fit_predictions.csv`, which no longer exists. Surviving: the two model binaries (`archetype_gate_a.txt` with `shooter_height` + `shooter_position`, `headline_gate_a.txt` without) and nothing else. The **design** of the test is documented and citable; the **result** is not. And it ran on the broken `fta_from_shot` target, so re-running it as-is would not rescue the number either. |
| U2 | **Poisson-vs-multiclass comparison** | ❌ Same fate: printed only, `multiclass_predictions.csv` deleted. Only `calibration_poisson_vs_multiclass.png` survives, and it plots the broken target. Separately, the committed config is internally inconsistent: docstring says 4-class (0/1/2/3), `MULTICLASS_PARAMS` sets `num_class: 3`, and the EV uses classes 0/1/2 only (`variants.py:44-55, 228-231`). The variant as committed does not match its own description. |
| U3 | **Per-zone calibration of the FTAOE model** | ❌ Does not exist. Per-zone calibration is an **xFG** result (`xfg_evaluate.py` → `xfg_reliability.png`). xFTA's calibration is per-**decile** at player-season grain (`check_calibration.py`), and that script prints without saving. |
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

| need | covered? | what exists |
|---|---|---|
| (a) LaTeX/arXiv scaffolding | ⚠️ generic only | `academic-paper/templates/latex_article_template.tex`, `references/latex_template_reference.md`. Generic `article` class. No arXiv-specific class. |
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

| # | Item | Action |
|---|---|---|
| O1 | Which framing (§11) | **Your call.** Blocks the abstract and contribution statement. |
| O2 | D4 vs D4b possession count (1,420,917 vs 1.39M) | Resolve; one is wrong or they are different filters |
| O3 | xFTA per-decile calibration slope (`experiment_record.md:61` says "slope ~1", no artifact) | Re-run `check_calibration.py`, capture to JSON. Needed if the paper claims calibration. |
| O4 | U1 archetype test | Either re-run on the *current* possession model and target (a real, defensible held-out-identity test), or drop the claim. Cannot be cited as-is. |
| O5 | U2 multiclass comparison | Same choice, plus fix the `num_class` inconsistency if re-run |
| O6 | Sloan page limit + JQAS author guidelines | Fetch live at Gate 5 |
