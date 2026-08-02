# Cover letter — JQAS

Required by the journal on first submission, addressed to the Editor-in-Chief,
containing a brief statement of the novelty on which the request for publication
rests. Draft below; check the current Editor-in-Chief's name on the journal
masthead before sending, and replace the placeholder.

---

To the Editor-in-Chief
*Journal of Quantitative Analysis in Sports*

Dear Professor **[EIC NAME — verify on the journal masthead]**,

I am submitting **"Adjustments that do not adjust: measuring shooting-foul
drawing in the NBA from public play-by-play"** for consideration as a Research
Article.

The paper reports one positive and one negative result, and the negative one is
the contribution.

The positive result is that shooting fouls drawn per finisher-possession, built
entirely from public play-by-play across six NBA seasons and 1,420,917
possessions, is a highly reliable player statistic: split-half r = 0.841 over
1,691 qualified player-seasons, Spearman-Brown full-season r = 0.914, and
year-over-year r = 0.85, stabilising with a padding constant of 67 possessions.

The negative result is that three separate attempts to adjust that statistic all
failed, and failed in a way that was predictable in advance. A context model
conditioning on period, clock, score margin, venue, opponent foul rate and
officiating crew reproduces the unadjusted rate at r = 0.995, because the fitted
expectation carries 0.9 % of between-player variance: an 82-game schedule
averages context away. Adding height and position does remove a substantial
body-type gradient, but the result reproduces an ordinary two-variable
regression residual at r = 0.988. Adding the player's own prior-season rate
explains the signal away by construction.

I believe this is a good fit for JQAS on the journal's second and third criteria.
It develops no new estimator, but it applies statistical thinking to a problem
the applied literature routinely gets wrong, and it proposes a concrete remedy:
a two-number precondition for residual metrics (the between-subject variance
share of the fitted expectation, and the correlation of the proposed residual
against the simplest thing it could have been). Both are one line of code, and
neither is commonly reported. In our case the per-event fit statistic was
significantly non-zero throughout and gave no warning at all. The framework in
Franks et al. (2016), published in this journal, is where these diagnostics
belong, and the paper is written to sit alongside it.

Two features of the submission may interest the editors. First, the paper reports
several errors that its own pre-publication audit missed and that were caught
later, including a mis-specified fitting universe whose artifact we had
misinterpreted as league-wide officiating drift. Second, it includes a leakage
audit of a companion model, with a controlled retrain on an identical split
moving holdout AUC from 0.6705 to 0.6578 while leaving calibration essentially
unchanged. That signature is the reason a calibration check alone would not have
detected the leak, and it seems worth recording for anyone building on the same
public feed.

The manuscript is not under consideration elsewhere and has not been published
previously. A preprint is deposited on Zenodo, which I understand falls under the
journal's pre-publication policy for recognised preprint servers; please tell me
if that is not the case for Zenodo specifically and I will act accordingly. All
code and model artifacts are openly archived, and every number in the manuscript
is reproducible from them.

Thank you for your consideration.

Yours sincerely,

Kevin Krajnc
Independent researcher
kevin@aandrs.at

---

## Suggested reviewers

The journal invites up to four, and requires that they be at **different
institutions and countries** from the author, with name, institution, country
and e-mail.

**I have deliberately not filled these in.** Supplying contact details for real
researchers from memory is exactly the failure mode this project spent Gate 1
eliminating, and a wrong address on a submission form is worse than a blank one.

Pick them yourself from the paper's own verified bibliography, where the fit is
genuine. Reasonable pools, all of whom have published directly relevant work:

- the authors of Franks et al. (2016), *Meta-analytics*, JQAS — closest possible
  match, since the paper is an application of their framework;
- the authors of Sandholtz et al. (2020), *Measuring spatial allocative
  efficiency in basketball*, JQAS — shot selection versus conversion;
- the authors of Deshpande and Jensen (2016), JQAS — possession-grain player
  valuation;
- the authors of Baumer et al. (2015), *openWAR*, JQAS — public reproducible
  player metrics.

Look up current affiliation and institutional e-mail on each person's
departmental page at the time you submit. Do not reuse any address from memory.
You may also name reviewers to exclude, which the journal permits.
