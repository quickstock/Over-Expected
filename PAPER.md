# The paper moved

The research paper built from this pipeline used to live at `NBA_OE/paper/`.
It now sits beside this repo, as its own git repository:

```
Basket OE/
├── NBA_OE/     <- you are here (the pipeline)
└── paper/      <- the manuscript, figures, verification, submission packages
```

Its history moved with it (`git subtree split`), so the Gate 1-5 record is
intact there rather than here. The commits that produced it are still in this
repo's history up to `b5a2ace`, but the live files are in `../paper/`.

## What the paper depends on, in this repo

It is a read-only consumer. It never writes here.

| what it reads | why |
|---|---|
| `config.py` | `DB_PATH`, `SEASONS` |
| `xfta.db` | possessions, predictions, player-season records |
| `model_artifacts/*.json` | every number in the manuscript traces to one of these |

If you rename or move any of those, `../paper/make_figures.py` will fail loudly
with a message naming what it looked for. That is deliberate.

## Validation scripts the paper relies on

These live here, not in the paper repo, because they are pipeline experiments:

- `variant_archetype.py` — context-only vs identity-aware arms
- `variant_model_family.py` — Poisson GLM vs multinomial vs LightGBM
- `variant_raw_baseline.py` — the metric against the unadjusted rate
- `variant_archetype_vs_linear.py` — the body-type arm against a linear residual
- `scripts/analyze_reliability.py`, `check_calibration.py`

Each of the four `variant_*` scripts asserts that its baseline arm reproduces
the shipped model before its variant arms are read.

## Open item

`train_possession_v4_context.py` fits on all 1,420,917 possessions including
28,567 that carry `sfta == 0` by construction. That biases the intercept and
produces per-season anchor factors of ~1.0204 that were misread as league
enforcement drift; refitting on the finisher universe moves them to ~0.9987.
See `../paper/review_findings.md` F3. This affects `predictions_poss_clean`,
which feeds the live site, so it is a pipeline fix rather than a paper fix.
