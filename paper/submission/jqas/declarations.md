# Ethical and legal declarations — JQAS submission

JQAS requires these to be entered in De Gruyter's **Template for Ethical and
Legal Declarations**, uploaded with the manuscript. The text below is what goes
in each field. Wording matters here, particularly the AI section: read it before
submitting and change anything you disagree with, because you are the one
signing it.

---

## Research ethics

Not applicable. This study analyses publicly available aggregate sports
event data. It involves no human subjects, no animals, and no personal data
within the meaning of the GDPR: the individuals appearing in the analysis are
professional athletes and match officials acting in a public professional
capacity, and every field used is published by the league.

## Informed consent

Not applicable.

## Author contributions

The author is the sole author and is responsible for the entire content of the
manuscript: conception, data pipeline, modelling, analysis, and drafting.

## Use of Large Language Models, AI and Machine Learning Tools

This declaration is deliberately full rather than minimal, because the tools were
used substantively rather than cosmetically.

**Machine learning as research methodology.** The study fits gradient-boosted
trees (LightGBM), Poisson and multinomial generalised linear models, and
isotonic calibration. These are the object of study and are specified in the
manuscript with hyperparameters, software, and validation design.

**Large Language Model assistance.** Anthropic's Claude (Claude Opus 5) was used
throughout the project, under the author's direction and review, for:

- writing and refactoring the data pipeline, modelling and analysis code;
- proposing and implementing the validation experiments reported in the paper,
  including the baseline comparisons that produced its central negative result;
- drafting and revising the manuscript text;
- generating the bibliography programmatically against CrossRef and OpenAlex;
- running a simulated adversarial peer review of an earlier draft, which
  identified several errors subsequently corrected in the manuscript
  (a mis-specified fitting universe, a mis-estimated calibration slope, and an
  incorrect claim about which features carried predictive signal).

No LLM is an author. The author takes full responsibility for all content,
including every numerical result, and has verified the reported figures against
the committed artifacts. All quantitative claims in the manuscript are
reproducible from the deposited code.

## Research funding

None declared.

## Conflict of interest

The author declares no conflict of interest.

The author operates a public website (overexpected.com) presenting metrics
derived from the same pipeline. It is non-commercial and carries no advertising,
sponsorship or paid access. It is disclosed here because the manuscript reports
that a metric previously published on that site does not do what it was
presented as doing, which is a fact readers may reasonably want to weigh.

## Data availability

The play-by-play and shot-chart data underlying this study are published by the
NBA at `stats.nba.com` and are freely accessible without registration. They are
not redistributed here, and the terms of use of that endpoint do not clearly
permit redistribution.

All code required to reconstruct the derived dataset from those public
endpoints, together with every model artifact, validation script and
figure-generating script, is openly available at:

> **[TO INSERT: Zenodo DOI for the archived code release]**
> Mirror: https://github.com/quickstock/Over-Expected

The derived possession-level table (1,420,917 rows) is the input to every result
in the paper. Archiving it directly would materially improve reproducibility,
because `stats.nba.com` is undocumented, rate-limited, and retroactively edits
historical play-by-play. See the reproducibility note in the submission
checklist.

**Data citation.** Once the Zenodo DOI is minted, cite the archived release in
the reference list following DataCite's minimum fields (creator, title,
publisher, year, identifier), as the journal requests.
