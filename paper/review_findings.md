# Gate 4 — adversarial review findings and their resolution

Five-reviewer panel (EIC, methodology, domain, cross-disciplinary perspective,
devil's advocate) run 2026-08-02 against the Gate 2 canonical draft. Each
reviewer was given the manuscript, the artifacts, and an explicit adversarial
brief. Findings below are **verified against the repo by me**, not accepted on
the reviewer's word. Several reviewer claims were wrong and are marked as such.

**Panel verdicts:** EIC major revision (originality 2/5, significance 2/5),
perspective major revision (conceptual soundness 2/5), domain major revision
(literature 2/5), devil's advocate **reject**.

---

## Tier 1 — findings that change what the paper claims

### F1. FTAOE is an affine transform of the raw rate. ✅ CONFIRMED, decisive
Raised by all four completed reviewers. The perspective reviewer derived
corr ≥ 0.99 analytically from the paper's own published numbers *before* seeing
data; I then measured it.

| | split-half | full-season | K | YoY |
|---|---|---|---|---|
| raw shooting-foul FT/100 | 0.841 | **0.914** | 67 | 0.849 |
| FTAOE/100 | 0.841 | **0.913** | 67 | 0.850 |

Spearman rho between them **0.9947**, Pearson 0.9953, top-10 overlap 9/10,
top-25 24/25, mean within-season rank shift **1.7 places** (max 14).

Mechanism, measured: expected rate sd **0.73** per 100 against actual-rate sd
**7.58**. The context adjustment carries 9.7% of the spread of the thing it
adjusts and 0.93% of between-player variance.

**Consequence.** The 0.914 reliability is a property of the raw rate. The
abstract's "despite a 0.195% fit, the metric is reliable" is arithmetic
presented as a paradox. Artifact: `model_artifacts/variant_raw_baseline.json`,
script `variant_raw_baseline.py`.

**Resolution: requires reframing. Blocks resubmission.**

### F2. The model contains no shot-diet feature, so the stated motivation is undeliverable. ✅ CONFIRMED
All four reviewers. The abstract promises to separate rim volume from
foul-drawing skill; the introduction promises "given where and how a player
finishes possessions." The seven features are period, clock, margin, Q4/OT,
home, opponent rate, crew rate. None describes the shot.

Two sub-findings worth keeping:
- The face-validity check in §6 ("the ordering is unsurprising, which is the
  point") has **no discriminating power**: the raw rate produces the same
  ordering, so the confound and the confirmation give identical output.
- The archetype arm (height + position only) quadruples fit and strips 9-11
  FTAOE/100 from the tallest players (Bol Bol, Wembanyama, Kornet, Porziņģis,
  Holmgren). The circularity defence covers prior-season FTr but **not** height,
  which is not a prior measurement of the outcome. The paper reports only the
  Gobert mover and omits the archetype movers, which the devil's advocate
  correctly called the strongest selective-reporting charge available.

**Resolution: rewrite the motivation to the question the model answers, or fit
the model the motivation describes. Blocks resubmission.**

### F3. Anchoring corrects a fitting-universe mismatch, not league drift. ✅ CONFIRMED
Domain reviewer. Verified arithmetically:

| quantity | value |
|---|---|
| all ÷ attributable possessions (1,420,917 / 1,392,350) | 1.02052 |
| mean anchor factor across six folds | 1.02037 |
| mean sfta on finisher possessions ÷ overall | 1.02052 |

28,567 possessions have no finisher and carry `sfta = 0` **by construction**.
Fitting on those structural zeros biases the fitted mean down by exactly the
universe ratio; anchoring scales it back. The 2021-22 crackdown, the paper's
stated rationale, leaves **no signature**: its anchor (1.0253) equals 2020-21's.

**Refit result (2026-08-02).** Excluding non-finisher possessions from the fit:

| season | anchor (fit on all) | anchor (fit on finisher only) | lift all | lift fin |
|---|---|---|---|---|
| 2020-21 | 1.02528 | 1.00381 | 0.185 | 0.208 |
| 2021-22 | 1.02529 | 1.00503 | 0.168 | 0.168 |
| 2022-23 | 1.01566 | 0.99358 | 0.170 | 0.179 |
| 2023-24 | 1.02238 | 1.00036 | 0.254 | 0.276 |
| 2024-25 | 1.02055 | 0.99842 | 0.244 | 0.265 |
| 2025-26 | 1.01305 | 0.99076 | 0.152 | 0.151 |
| **mean** | **1.02037** | **0.99866** | 0.195 | 0.208 |

The anchors collapse to **0.99866** (sd 0.0051) against a structural ratio of
1.02052. Anchoring was almost entirely correcting the fitting universe.

The residual season variation after the fix is ±0.5% and still shows **no
crackdown signature**: 2021-22's anchor is 1.00503, the highest of the six, when
a crackdown that suppressed shooting fouls should push it *below* 1.

**Resolution: this is a real pipeline bug, not just a prose error. Structural
zeros (28,567 possessions that cannot produce a shooting foul) were in the
training set, biasing the intercept. Refit the production model on the finisher
universe, delete the crackdown rationale, and re-derive whatever cross-season
argument survives. Note this also changes shipped numbers: `predictions_poss_clean`
feeds the live site.**

---

### F16. FTAOE has a large, monotone height gradient. ✅ CONFIRMED, new and serious
Methodology reviewer. I re-ran it and reproduced every figure:

- corr(FTAOE/100, height) = **+0.391** (r² = 0.153)
- mean FTAOE/100 by height band: ≤6'2" **−4.31**, 6'3"–6'6" −1.98, 6'7"–6'9"
  −0.21, 6'10"–7'0" **+5.24**, ≥7'0" **+5.76**. A **10.07** per-100 spread on a
  metric whose sd is 7.57.
- adding height + position collapses it: corr → **+0.016**
- corr(archetype − headline delta, height) = **−0.9515**, i.e. the archetype
  adjustment is almost purely a height correction

So roughly 15% of FTAOE's variance is body type, which no definition of
"foul-drawing craft" includes. This also destroys the face-validity argument a
second way: the recovered ordering is substantially a height ordering.

**Resolution: report the height gradient, and either ship the archetype
specification as the headline (height is not a prior measurement of the outcome,
so including it is not circular the way prior-season FTr is) or state and
quantify that FTAOE conflates size with craft. Blocks resubmission.**

### F17. The calibration "weakness" was an artifact, and my Gate 1 correction was itself wrong. ✅ CONFIRMED
Methodology reviewer. This one reverses an earlier finding of mine and I want it
recorded plainly.

| estimator | sample | slope | 95% CI |
|---|---|---|---|
| decile OLS (as run) | ≥100 poss, n=2488 | 0.426 | **[−0.288, 1.139]**, p=0.206 |
| decile OLS | ≥300 poss, n=1691 | 0.714 | [0.095, 1.332] |
| player-season WLS | ≥100 poss | 0.788 | [0.374, 1.202] |
| **player-season WLS** | **≥300 poss (leaderboard threshold)** | **1.011** | **[0.512, 1.509]** |

At the threshold the metric actually uses, with a possession-weighted estimator,
the slope is **1.01**. The 0.426 is manufactured by unweighted 10-point binning
over a sample that includes 797 sub-threshold player-seasons, and its own CI
spans 1.

The reviewer also showed my *explanation* was mechanistically wrong: regression
dilution requires measurement error in x, and the predicted player-season rate
has none in the classical sense; a narrow predictor range inflates the standard
error of a slope without biasing it.

**Chain of errors, for the record.** The original `experiment_record.md:61`
claimed "diagonal (slope ~1)" — unmeasured, but roughly right. At Gate 1 I
"corrected" it to weak calibration (slope 0.426) — measured, but with the wrong
estimator on the wrong sample, and defended with the wrong mechanism. Gate 4
measured it properly. Both prior versions are now superseded in
`experiment_record.md` and in ledger §2e.

**Consequences:** §6.6 and the Limitations paragraph on calibration must be
deleted, not softened. Table 5's model-family verdict cites "calibration gets
worse (0.211 vs 0.426)" as the reason to keep the GLM; with SE ≈ 0.31 those are
the same number, so **that decision rationale must be withdrawn** and the GLM
justified on other grounds (parsimony, and the rank-identical leaderboards).

### F18. The rate features do not "carry almost all the signal", and their contribution is same-season target encoding. ✅ CONFIRMED
Methodology reviewer's ablation, identical folds and anchoring:

| specification | mean fold lift |
|---|---|
| 4 base features only (period, seconds, margin, Q4/OT) | **0.153%** |
| + same-season LOGO opponent & crew rates (shipped) | **0.196%** |
| + opponent & crew rates built from **training seasons only** | **0.146%** |

The two rate features add 0.043 pp, i.e. 22% of the reported lift rather than
"almost all" — and built honestly out-of-fold they add *nothing* (they cost
0.007 pp). This quantifies F6: the reported 0.195% is a retrospective fit, not a
prospective one.

**Resolution: report the ablation. Either rebuild the features from prior
seasons and report 0.146%, or relabel 0.195% as retrospective. Delete the
"carry almost all the signal" sentence.**

### F19. Officiating crews barely persist, which kills the practitioner claim. ✅ CONFIRMED
Methodology reviewer, measured directly: official-season foul rate has
within-season split-half r = **0.508** and **year-over-year r = 0.178** (0.254,
0.185, 0.150, 0.139, 0.162). For contrast, defensive-team rate is 0.688.

The crew coefficient itself is real (cluster-robust z = 5.0–7.2). But you cannot
forecast a crew's rate at YoY 0.18, so §9's "a team can quantify how much of a
player's variance is attributable to officiating assignment" is unsupportable on
its own terms, independently of the causal objection in F9.

### F20. The reported statistic is 2×NLL, not the Poisson deviance. ✅ CONFIRMED
`poisson_deviance()` in `train_possession_v4_context.py:56-64` omits the
saturated-model term. The deviance *drop* is unaffected, but the denominator is:
true lift is **0.227%**, not 0.195%. The error runs in the conservative
direction, which is to the paper's credit, but a quantity labelled "Poisson
deviance" in a statistics venue must be the deviance.

### F21. The lift IS distinguishable from zero, and the paper undersells it. ✅ CONFIRMED
Cluster-robust by game (G = 7,230): per-possession gain 0.001935, SE 0.000081,
t = 23.9, **95% CI 0.180% to 0.212%**. The paper never says this. The correct
caveat was always effect size, not significance.

---

## Tier 2 — verified errors requiring correction

### F4. "600 possessions ≈ two months" is wrong by roughly a factor of two. ✅ CONFIRMED
Perspective reviewer. Measured: mean **709** finisher-possessions per qualified
player-season over **63.2** games, i.e. 11.3 per game. So 600 possessions is
~53 games (about 3.5 months), not two. Two months (~30 games) gives r ≈ 0.82.
This is the load-bearing sentence of the practitioner section in **both**
versions.

### F5. Curry's "−23" is a season total paired with a rate in the same clause. ✅ CONFIRMED
Cross-season means: total **−23.5**, per 100 **−1.77**. Against a between-player
sd of 7.57 per 100, Curry is slightly below average, not an outlier. The "clean
illustration" framing does not survive the correct units. Appears in both
versions; the conference version leans harder on it.

### F6. "Every prediction is out-of-fold" is false for the features. ✅ CONFIRMED
EIC and perspective. Verified in code: `logo_rate` is called at
`train_possession_v4_context.py:152` and `:164`, inside `load()`, **before** the
fold loop at `:179`. The held-out season's opponent and crew rates are computed
from that season's own games. Coefficients are out-of-fold; features are not.
Acutely embarrassing in a paper whose methods contribution is feature timing.

### F7. Conference version miscounts its own model. ✅ CONFIRMED
Perspective. §3 says "the seven context features above"; §2 enumerates six. The
missing one is Q4/OT, the feature whose provenance the canonical version flags
twice.

### F8. No uncertainty quantification anywhere. ✅ CONFIRMED
All reviewers. Table 2 is a fitted `statsmodels` GLM table with the standard
errors removed, and the paper then adjudicates coefficient stability without
them. Also missing: DeLong/bootstrap CI on the 0.6705 → 0.6578 AUC delta
(n = 217,738, free to compute); any interval on split-half 0.841; any interval
on the 6/10 and 2/10 top-ten overlaps, where uncertainty is large; any error bar
on the Butler/Jerome flip, whose gap is 0.57.

### F9. §7 and §9 contradict each other on officiating. ✅ CONFIRMED
EIC, domain, devil's advocate. §7 correctly declines any causal claim because
crew assignment is not random. §9 then proposes attributing a player's variance
"to officiating assignment rather than to his own play," which is exactly the
disclaimed decomposition. Delete the §9 sentence.

### F10. Reproducibility artifact contained a known-false claim. ✅ FIXED
EIC and devil's advocate. `experiment_record.md:61` claimed decile calibration
was "diagonal (slope ~1)"; measured slope is 0.426. **Corrected 2026-08-02.**
Three orphaned PNGs plotting the abandoned target moved to
`_v3_archive/orphaned_figures/` with a do-not-cite README. Ledger O7 and O8
closed.

### F11. Leaky-arm metrics have no committed artifact. ✅ CONFIRMED
Devil's advocate, and it is a fair hit. The X7 ledger row (AUC 0.6705 → 0.6578)
is marked VERIFIED but sources to prose in `experiment_record.md`, not a metrics
file. Table 1's leaky column shows "--" for Brier and log-loss because that arm
was never fully re-scored. The authors applied a re-run standard to the variant
tests (U1, U2) and not to the number in their own abstract.

**Resolution: re-run the leaky xFG arm and capture a metrics artifact, or
downgrade the ledger row to ASSERTED and say so in the paper.**

---

## Tier 3 — reviewer claims I tested and rejected

### R1. "The multinomial arm is almost certainly a bug." ❌ DISPROVED
Domain reviewer, marked Critical. Tested directly: the two arms are **not**
bit-identical (max per-possession difference 0.000914, mean 0.000130,
correlation 0.99995). Two genuinely distinct fits. They agree closely because
both are near-constant models over the same seven features.

The devil's advocate read the same fact correctly: two different likelihoods
agreeing to four decimals is independent **corroboration of F1**, not a coding
error. Worth stating in the paper that way.

### R3. Odd/even splitting inflates split-half r by 0.033, and that is all. ✅ QUANTIFIED
Methodology reviewer. A chronologically blocked split gives r = **0.8081**
(K = 84) against odd/even's 0.8408 (K = 67). Method-of-moments predicts 0.8350
from pure sampling error alone, so the excess over sampling noise is +0.006:
there is **no meaningful shared-nuisance inflation** from opponent/crew overlap
or the shared anchor. Report both splits; the blocked figure is the more honest
test-retest and is still high.

Also quantified: K = 67 has a player-clustered bootstrap CI of **[57, 80]**, so
"r = 0.9 at about 600 possessions" is really **[510, 719]**, and 758 under the
blocked split.

### R4. LOGO self-contamination via the player's own later games. ❌ UNFOUNDED, measured
The methodology reviewer checked the concern I would have raised and dismissed
it with numbers: a player's own possessions are a mean of **0.33%** of an
opponent's season possessions (p95 0.76%, max 1.85%), shifting the expectation
by at most **0.61%** at the 99th percentile. An order of magnitude below the
second margin leak already classified as immaterial. Disclose in one sentence;
change nothing.

### R2. "Reliability of 0.841 is inflated by the odd/even split." ⚠️ SUPERSEDED by R3
The concern is real in principle (halves share opponents, crews and the same
anchoring constant), but the perspective reviewer's own note cuts the other way:
subtracting an expectation that differs between halves should if anything
*depress* the split-half r relative to the raw rate. Measured, they are equal to
three decimals (0.8408 vs 0.8408), which is consistent with the adjustment being
negligible (F1) rather than with inflation. Keep as a stated limitation; it does
not change a number.

---

## Tier 4 — literature and framing

### F12. Missing citations, several of them serious. ✅ ACCEPTED
The bibliography was built programmatically against CrossRef and OpenAlex, which
indexes ML methodology, soccer and referee economics well and applied basketball
analytics badly, because that work lives in Sloan proceedings, books and public
sites. The gap is systematic and the domain reviewer diagnosed the cause exactly.

Highest priority, all to be verified before adding:
- **Franks, D'Amour, Cervone & Bornn (2016), "Meta-analytics: tools for
  understanding the statistical properties of sports metrics", JQAS 12(4).**
  The single most important omission: it formalises discrimination, stability and
  independence for sports metrics, it is the framework §6.3 is groping toward,
  and it is in the target venue.
- Chang, Maheswaran et al. (2014), "Quantifying Shot Quality in the NBA", Sloan.
- Sicilia, Pelechrinis & Goldsberry (2019), "DeepHoops", KDD — models shooting
  fouls as terminal actions.
- Oliver (2004), *Basketball on Paper* — FTr is the direct ancestor of the
  denominator.
- Carleton (2013) — origin of the split-half/Spearman-Brown convention in sports.
- Schuckers & Curro (2013), THoR — penalty-drawing as a measurable skill, the
  cross-sport precedent.
- Gift & Rodenberg (2014), height bias among NBA referees — directly relevant to
  the archetype arm.
- `pbpstats` (Blackport) — the reproducibility argument rests on it and it is
  uncited.

Also required: acknowledge DARKO / EPM / LEBRON / RAPTOR as the public
state of the art, and Cleaning the Glass and NBA.com Synergy play-type tables as
closer competitors than anything currently in Related Work. The novelty sentence
must narrow accordingly.

### F13. The leak audit does not yet generalise. ✅ ACCEPTED
EIC, perspective, devil's advocate. "Anyone building on the same feed will hit
it" is rhetorical. The upgrade path is concrete and cheap, and the material is
already on disk: **all eight non-NBA league feeds are cached locally (3.4 GB in
`Euro_OE/cache`)**. Testing whether the same post-event stamping occurs in
Euroleague, Genius LiveStats, ACB, LBA, BBL, ABA, GBL and WNBA converts an n=1
bug report into a cross-source survey.

The perspective reviewer's stronger suggestion: ship a **source-agnostic
detector**. For any event-keyed feed, for every numeric field, test whether the
delta from event t−1 to t is a deterministic function of event t's outcome. That
is the generalisable object, it is a few lines, and it applies well beyond sports.

### F14. Findings report totals, reintroducing the volume confound. ✅ ACCEPTED
Domain reviewer. The metric is defined per 100, the reliability analysis is per
100, the argument is that counting stats reward volume — and then the only
leaderboard is a counting stat. Lead with per-100 and apply the K = 67 shrinkage
the paper derives and never uses.

### F15. Scope/title mismatches. ✅ ACCEPTED
- The metric covers shooting fouls only, excluding 67,569 of 323,307 drawn free
  throws (21%). Title says "Foul-Drawing Skill". Narrow it to shooting-foul
  drawing, and run the sensitivity check with all drawn FTs in the target.
- "FTAOE" expands in the paper as "free throws over expected", but the target
  counts attempts, so the A is right and the expansion is wrong. Fix everywhere.
- The critical leak is in xFG, a sibling model on a different grain, while the
  leak that touched FTAOE moved no player more than 1.03 FTs. The title
  advertises an audit of FTAOE. Retitle or restructure.

---

## Status

| tier | finding | status |
|---|---|---|
| 1 | F1 raw-rate equivalence | confirmed, blocks resubmission |
| 1 | F2 no shot-diet feature | confirmed, blocks resubmission |
| 1 | F3 anchoring artifact | confirmed, refit running |
| 2 | F4-F9 | confirmed, correctable |
| 2 | F10 | **fixed** |
| 2 | F11 | confirmed, needs re-run or downgrade |
| 1 | F16 height gradient | confirmed, blocks resubmission |
| 1 | F17 calibration reversal | confirmed, **corrects my own Gate 1 correction** |
| 2 | F18-F21 | confirmed, correctable |
| 3 | R1 multinomial bug | **disproved** |
| 3 | R3 split-half inflation | quantified at +0.033, benign |
| 3 | R4 LOGO self-contamination | **unfounded**, measured |
| 4 | F12-F15 | accepted, scoped |

**All five reviews complete.** Methodology reviewer: major revision, statistical
validity 2/5, **reproducibility 5/5** ("every headline figure reproduced exactly
... without contacting the authors"). It ran its own analyses; the tier-1
additions below come from it and I verified each one.

**Decision required before revision:** whether to reframe to the finding the
data supports (foul-drawing rate is reliable and fast-stabilising; context
adjustment does not move it, and here is the structural reason) or to fit the
model the current motivation describes. The second is a research project, not a
revision, and carries a real objection: conditioning on the observed shot selects
on the outcome, because a shooting foul frequently corrupts or replaces the
recorded field-goal attempt. If that is why location was excluded, it is a
genuine methodological contribution and belongs in the paper. Right now the
omission is silent.
