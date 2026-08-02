# Submission targets — Over Expected paper

One canonical paper, two compiled outputs, three destinations. Updated
2026-08-02: the preprint destination is **Zenodo**, not arXiv.

## Why Zenodo, not arXiv

arXiv requires endorsement for a first submission in most categories, and there
is no endorser. Zenodo has no endorsement gate, mints a permanent DOI, and is
CERN-operated, so it is the faster and guaranteed path to a citable preprint.
The trade is discoverability inside the ML/stats community, which arXiv wins;
that is an acceptable loss for a paper whose primary targets are a journal and a
practitioner conference anyway.

## The three destinations

| # | destination | source | format |
|---|---|---|---|
| 1 | **Zenodo** (preprint, DOI) | canonical paper, unchanged | PDF + LaTeX source + supplementary |
| 2 | **JQAS** (De Gruyter), peer-reviewed | canonical paper | journal template |
| 3 | **MIT Sloan SSAC** innovation track, or StatsBomb Conference | conference derivative | venue template, hard page limit |

Destinations 1 and 2 ship the *same* canonical paper. Destination 3 is condensed
from it against the same claims ledger. No number and no claim's strength may
differ between the two compiled outputs.

## Zenodo deposit contents

The deposit is not just a PDF. Prepare all of it together:

- **PDF** — the same build produced for the journal version
- **LaTeX source** — `.tex` + `.bib` + figures, as supplementary files
- **Code repository link** — `github.com/quickstock/Over-Expected` (public)
- **Data description** — what the pipeline ingests, from which public endpoints,
  and what cannot be redistributed

### Required metadata block

Draft this alongside the PDF, not after:

| field | value |
|---|---|
| Title | (final paper title) |
| Author(s) | Kevin (+ ORCID if one exists; register one if not, it takes minutes and makes the DOI resolvable to a person) |
| Abstract | the canonical abstract, verbatim |
| Keywords | 5-7; expect: basketball analytics, free-throw modelling, Poisson regression, measurement reliability, data leakage, sports officiating |
| License | **CC-BY 4.0** — standard permissive choice for open research; permits reuse with attribution |
| Resource type | Preprint |
| Related identifiers | link the GitHub repo DOI (see below) as "is supplemented by" |

### GitHub integration (recommended)

Zenodo can watch a public GitHub repo and mint a DOI for a specific tagged
release. Doing this means the paper and the exact code that produced its numbers
are both permanently archived and cross-referenced, which is a materially
stronger reproducibility story than a bare repo URL that can drift.

All four repos are already public. Steps:

1. Zenodo → Settings → GitHub → toggle on `quickstock/Over-Expected`
2. Tag and publish a GitHub release (e.g. `v1.0-paper`) pinned to the commit the
   paper's numbers came from
3. Zenodo mints a version DOI automatically
4. Cite that DOI in the paper's data-availability statement, and list it as a
   related identifier on the paper deposit

Do this **before** depositing the paper, so the paper can cite the code DOI.

## Gate 5 deliverable (revised)

Gate 5 prepares a **Zenodo deposit**, not an arXiv submission:

- [ ] Canonical PDF, final
- [ ] LaTeX source bundle
- [ ] Metadata block above, complete, license selected
- [ ] Code release tagged and its DOI minted
- [ ] Data-availability statement citing the code DOI
- [ ] JQAS submission package checked against De Gruyter's live author guidelines
- [ ] Conference derivative checked against the venue's live CFP page limit

Sloan's innovation-track page limit and JQAS's formatting requirements are both
**unconfirmed** and must be read from the live pages at Gate 5, not assumed. No
installed skill ships a JQAS/De Gruyter or Sloan/StatsBomb template (see
`claims_ledger.md` §10).
