# xFTA — Expected Free Throw Attempts

Quantifies how many free throws a field-goal attempt *should* produce (xFTA), then
measures which NBA players draw more shooting fouls than their shot context predicts
(FTA Over Expected, or FTAOE).

## Quick start

```bash
# Install dependencies
pip install -r requirements.txt

# Gate A — single game test
python pull.py --game 0022300001
python build_tables.py --game 0022300001
python validate.py

# View the dashboard
streamlit run dashboard/app.py
```

## Pipeline

```
pull.py          →  network pull only, writes cache/
build_tables.py  →  builds xfta.db from cache (no network)
validate.py      →  5 automated checks, prints report
```

### Gates (mandatory)

1. **Gate A**: run on game `0022300001` only. Stop and review validation + training_fga rows.
2. **Gate B**: after approval, run one week (~50 games).
3. **Gate C**: after approval, run full 3 seasons (2022-23 through 2024-25).

## Data sources

- **PlayByPlayV3** — play-by-play events (shot→foul→FT linking)
- **shotchartdetail** — shot coordinates, zones, distance, action type
- **commonplayerinfo** — player height, position
- **LeagueDashPlayerStats** — prior-season FTr
- **LeagueDashPtStats (Drives)** — prior-season drive rate
- **LeagueGameFinder** — game list per season

## Tables

See `SCHEMA.md` for full column documentation.

| Table | Rows | Description |
|-------|------|-------------|
| games | ~3,690 | One per regular season game |
| shots | ~600k | One per FGA with spatial features |
| shot_outcomes | ~600k | One per FGA with foul/FT target |
| player_season | ~1,500 | One per player per season |
| training_fga | ~600k | Joined superset for modeling |

## Dashboard

`streamlit run dashboard/app.py` — four tabs:

1. **Raw Tables** — database explorer with SQL query box
2. **Leaderboard** — FTAOE rankings with filters
3. **Shot Chart** — player shot charts and foul rate by zone
4. **Calibration** — model diagnostics (Phase 2)

## Feature list

**Context-only (headline model):** shot_distance, shot_zone_basic, shot_zone_area,
action_type, shot_type, period, seconds_remaining_in_period, score_margin, in_bonus,
home_or_away, shooter_height, shooter_position

**Carried (future YoY model):** prior_season_ftr, prior_season_drive_rate

**Target:** fta_from_shot (0/1/2/3)

Feature lists live in `config.py` — never hardcoded in the pipeline.

## NBA API notes

The NBA stats API (`stats.nba.com`) has become increasingly restrictive. If you
encounter timeouts:
- The pipeline uses exponential backoff retry (3 attempts)
- Rate limiting is enforced (0.6s between calls)
- All data is cached — re-running skips already-cached items
- Run during off-peak hours for better reliability
