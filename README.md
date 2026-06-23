# Over Expected

An end-to-end NBA shot-value system. It ingests six seasons of play-by-play,
trains leak-free models for what a shot is worth, and ships the results as a
data-journalism site.

**Live: [overexpected.com](https://overexpected.com)**

The core idea is a single question asked three ways: how much does a player add
over what an average player would do with the same looks?

- **Shot value**: points over expected per 100 possessions, fusing the shot and
  the fouls it draws.
- **Shot-making**: field-goal points over expected, actual conversion against
  the difficulty of the looks taken (xFG%).
- **Foul-drawing (FTAOE)**: shooting-foul free throws drawn over the league rate,
  the original stat the project is built around.

The same three lenses run on players, teams, and officials.

<!-- TODO: add screenshots: hero, a player page (the gap chart), the leaderboard, the crackdown trend -->

## Scale

- 1.39M possessions, 1.28M field-goal attempts, 7,230 games
- Six seasons (2020-21 to 2025-26), shooting fouls only
- ~550 statically prerendered routes with per-route OG cards and a sitemap

## How it works

```
nba_api  ->  cache/ (parquet)  ->  xfta.db (SQLite)  ->  models  ->  site/public/*.json  ->  React site
   pull.py        raw            possession + shot tables   LightGBM      export_site_data.py     Vite + TS
```

1. **Pull** (`pull.py`): network-only fetch of play-by-play, shot charts, box
   and tracking stats into a parquet cache. No table building here.
2. **Build**: possession-level and shot-level tables in `xfta.db`, including a
   target of shooting-foul free throws per possession.
3. **Model**:
   - Headline FTAOE: a possession-level model of expected shooting-foul free
     throws. FTAOE is actual minus expected, anchored per season so the league
     sits at zero and seasons are comparable.
   - xFG% (`xfg_model.py`): a LightGBM classifier giving every field-goal
     attempt a make probability from shot context only (location, distance,
     zone, action type, shot type, period, clock, score margin), never the
     shooter.
   - Shot value (`shot_value.py`): combines xFG% (make value) with expected
     free throws (foul value) into expected points per shot. The headline is
     points over expected per 100, crediting actual conversion on both sides
     (field goals at the player's rate, drawn free throws at his own FT%).
   - Style-adjusted FTAOE: a second baseline that predicts free throws from a
     player's attack profile (drives, paint and post touches), so the residual
     separates contact-seeking skill from sheer volume.
4. **Export** (`export_site_data.py`): writes a small core JSON plus per-season
   player chunks, validated by `scripts/validate_export.py`.
5. **Site** (`site/`): React + Vite + TypeScript, bespoke SVG charts, statically
   prerendered with OG cards for sharing.

## Leak-free and honest by construction

The discipline is the point, not a footnote.

- **Leak-free season cross-fit.** For each season the models train on the other
  five and predict the held-out one, so a shot's expected value never comes from
  a model that saw it.
- **Anchored.** Within-season residuals sum to ~0, so seasons are directly
  comparable rather than drifting with the league's foul environment.
- **The possession is the unit.** A fouled miss is not a charged shot and has no
  location, so any per-shot rate silently drops the exact plays the stat is
  about. Rates are per 100 possessions.
- **Scoped claims.** The number blends playstyle, contact-seeking skill, and
  officiating. It does not isolate them and it does not prove referee bias. The
  site deliberately publishes no player-by-official splits, which on this sample
  size would manufacture accusations the data cannot support.
- **Validated.** `scripts/validate_export.py` is a gate: row counts, calibration,
  anchoring, the foul-ledger identity, and zone-share sums all have to pass
  before an export ships.

## A finding

The NBA's 2021-22 "non-basketball moves" crackdown barely moved the league rate
(17.8 to 17.5 shooting-foul FTA per 100). It was surgical: it repriced a handful
of high-volume foul-drawers rather than changing the whole game, and the
environment drifted back up the next season. The League tab draws this as a
season-by-season trend, with the full study at `/crackdown`.

## Repo layout

```
.
├── pull.py                  network pull -> cache/
├── build_*.py               possession + training tables
├── xfg_model.py             leak-free xFG% model
├── shot_value.py            shot value suite (xFG% + xFTA -> points)
├── backfill_score_margin.py reconstruct in-game margin from play-by-play
├── export_site_data.py      DB -> site JSON
├── scripts/validate_export.py  the export gate
├── config.py                seasons, feature lists, paths
└── site/                    React + Vite front end
    ├── src/                 views, charts, lib
    ├── scripts/generate-static.mjs  prerender + OG cards + sitemap
    └── public/              exported data JSON
```

## Stack

- **Data and ML:** Python, pandas, SQLite, LightGBM, nba_api, numpy
- **Front end:** React, Vite, TypeScript, Tailwind, hand-built SVG charts, CSS
  motion with reduced-motion fallbacks
- **Build and deploy:** static prerender with satori OG cards, Vercel

## Running it

Data side (Python, from the repo root):

```bash
pip install -r requirements.txt   # nba_api, pandas, lightgbm, ...
python pull.py                    # fetch raw data to cache/ (network)
python shot_value.py              # train xFG%, build the shot-value tables
python export_site_data.py        # write site/public/*.json
python scripts/validate_export.py # gate
```

Site (from `site/`):

```bash
cd site
npm install
npm run dev          # local dev server
npm run build        # production build
```

## Credits

Built by Kevin Krajnc. Data from the NBA stats API. Shooting fouls only;
descriptive, not a referee-bias claim. See `/methodology` on the live site.
