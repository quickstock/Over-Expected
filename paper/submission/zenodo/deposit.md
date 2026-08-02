# Zenodo deposit

Two deposits, in this order. The code release goes first so the paper can cite
its DOI.

---

## Deposit 1 — the code (do this first)

Zenodo's GitHub integration mints a DOI for a tagged release, which is stronger
than a bare repository URL because a repository can drift and a release cannot.

1. Zenodo → Settings → GitHub → enable `quickstock/Over-Expected`
2. Tag the commit the paper's numbers came from and publish a GitHub release:
   ```bash
   git tag -a v1.0-paper -m "Numbers as reported in the JQAS submission"
   git push origin v1.0-paper
   ```
   Then publish the release on GitHub. Zenodo archives it automatically.
3. Copy the minted DOI into:
   - `submission/jqas/declarations.md` → Data availability
   - the manuscript's Reproducibility section
   - this file, below

Code DOI: **[TO INSERT]**

### Before tagging

Two reproducibility gaps the review flagged. Neither blocks submission, both are
cheap and both would be asked about:

- **Pin package versions.** `pbpstats` is load-bearing: the possession
  definition underlies every number in the paper and its logic has changed across
  releases. A `requirements.txt` with pinned versions plus the Python version is
  the minimum.
- **Consider archiving the derived possession table.** 1,420,917 rows is trivial
  to archive and it is the actual input to every result. `stats.nba.com` is
  undocumented, rate-limited and retroactively edits historical play-by-play, so
  "re-scrapable" is not the same as reproducible. Check the endpoint's terms
  before depositing derived data.

---

## Deposit 2 — the paper

### Files

| file | role |
|---|---|
| `overexpected.pdf` | the preprint |
| `overexpected_conference.pdf` | condensed version |
| `source/` | LaTeX source, bibliography, figure and verification scripts |
| `source/claims_ledger.md` | provenance for every number |
| `source/review_findings.md` | adversarial review and its resolution |

### Metadata

| field | value |
|---|---|
| **Resource type** | Publication → Preprint |
| **Title** | Adjustments that do not adjust: measuring shooting-foul drawing in the NBA from public play-by-play |
| **Authors** | Krajnc, Kevin (Independent researcher) — add ORCID once registered |
| **Publication date** | date of deposit |
| **Licence** | **CC-BY 4.0** |
| **Language** | English |
| **Keywords** | basketball analytics; measurement reliability; residual metrics; Poisson regression; data leakage; sports officiating |
| **Related identifiers** | `is supplemented by` → the code DOI from Deposit 1 |
| **Version** | v1.0 |

### Description

> How often a player draws shooting fouls, per possession he finishes, is a
> strikingly stable statistic: split-half r = 0.841 over 1,691 qualified
> player-seasons, Spearman-Brown full-season r = 0.914, year-over-year r = 0.85,
> and a padding constant of 67 possessions. This is established on 1,420,917
> possessions from six NBA regular seasons, built entirely from public
> play-by-play with no optical tracking.
>
> The natural next step is to adjust it, because a raw foul-drawing rate
> confounds craft with role and body type. Three separate adjustments all fail.
> A context model conditioning on period, clock, score margin, venue, opponent
> foul rate and officiating crew reproduces the unadjusted rate at r = 0.995,
> because an 82-game schedule averages context away: the fitted expectation
> carries 0.9 % of between-player variance. Adding height and position does
> remove a large body-type gradient (correlation with height falls from 0.391 to
> 0.016) but reproduces an ordinary two-variable regression residual at
> r = 0.988. Supplying prior-season foul-drawing rate explains the signal away by
> construction.
>
> The paper gives the two-number diagnostic that would have caught all three
> before any modelling, and reports a leakage audit of a companion model,
> including a controlled retrain that moved holdout AUC from 0.6705 to 0.6578 and
> changed a published leaderboard.

### Note on the journal

JQAS's pre-publication policy does not treat deposits on recognised preprint
servers as prior publication, naming arXiv, RePEc, bioRxiv and ResearchSquare
with "etc.". Zenodo is not named explicitly. The cover letter asks the editor to
confirm, which is the safe way to handle it: depositing first and asking later
would be the wrong order if the answer is no.

Paper DOI: **[TO INSERT after deposit]**
