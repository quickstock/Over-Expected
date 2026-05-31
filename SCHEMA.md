# xFTA Database Schema

All tables live in `xfta.db` (SQLite).

## games

One row per regular-season game.

| Column | Type | Source | Notes |
|--------|------|--------|-------|
| GAME_ID | TEXT | LeagueGameFinder | NBA game ID (e.g. "0022300001") |
| season | TEXT | config.py SEASONS | e.g. "2023-24" |
| GAME_DATE | TEXT | LeagueGameFinder | ISO date |
| home_team_id | INTEGER | PBP teamId | First team in PBP |
| away_team_id | INTEGER | PBP teamId | Second team in PBP |

## shots

One row per field-goal attempt. Joins to shotchartdetail for spatial features.

| Column | Type | Source | Notes |
|--------|------|--------|-------|
| game_id | TEXT | PBP | |
| event_id | INTEGER | PBP actionNumber | Join key with shotchartdetail GAME_EVENT_ID |
| player_id | INTEGER | PBP personId | Shooter |
| team_id | INTEGER | PBP teamId | |
| period | INTEGER | PBP | 1-4 (no OT yet) |
| seconds_remaining_in_period | REAL | PBP clock parsed | Seconds |
| shot_made | INTEGER | PBP shotResult | 1=made, 0=missed |
| shot_x | REAL | shotchartdetail LOC_X | Feet (-25 to 25) |
| shot_y | REAL | shotchartdetail LOC_Y | Feet (0 to ~47) |
| shot_distance | REAL | shotchartdetail SHOT_DISTANCE | Feet |
| shot_zone_basic | TEXT | shotchartdetail SHOT_ZONE_BASIC | |
| shot_zone_area | TEXT | shotchartdetail SHOT_ZONE_AREA | |
| shot_zone_range | TEXT | shotchartdetail SHOT_ZONE_RANGE | |
| action_type | TEXT | shotchartdetail ACTION_TYPE | |
| shot_type | TEXT | shotchartdetail SHOT_TYPE | "2PT Field Goal" / "3PT Field Goal" |
| score_margin | REAL | PBP scoreHome/scoreAway | From shooting team's perspective |
| home_or_away | TEXT | Derived | "home" or "away" |

## shot_outcomes

One row per FGA. The **target** table.

| Column | Type | Source | Notes |
|--------|------|--------|-------|
| game_id | TEXT | PBP | |
| event_id | INTEGER | PBP actionNumber | |
| drew_shooting_foul | INTEGER | Derived | 1 if a shooting foul occurred on this shot |
| fta_from_shot | INTEGER | Derived | 0/1/2/3 — number of FTs from the shooting foul |
| is_and1 | INTEGER | Derived | 1 if made shot + 1 FT |

**Derivation:**
- `is_and1`: made shot + shooting foul at same clock + exactly 1 FT
- `fta_from_shot`: is_and1→1; missed shot + shooting foul→number of linked FTs; else 0
- Excluded: technical, flagrant, away-from-play, inbound, offensive, charge, double, clear path fouls

## player_season

One row per player per season.

| Column | Type | Source | Notes |
|--------|------|--------|-------|
| player_id | INTEGER | CommonPlayerInfo | |
| player_name | TEXT | CommonPlayerInfo | |
| height_inches | REAL | CommonPlayerInfo HEIGHT | Parsed from "6-8" format |
| position | TEXT | CommonPlayerInfo POSITION | |
| season | TEXT | config.py | |
| prior_season_ftr | REAL | LeagueDashPlayerStats | Prior season FTA/FGA ratio |
| prior_season_drive_rate | REAL | LeagueDashPtStats Drives | Prior season drives/game |
| possessions | INTEGER | Placeholder | For future phase |

## training_fga

The final joined superset table. One row per FGA with all features + target.

| Column | Type | Description |
|--------|------|-------------|
| game_id | TEXT | Traceability |
| event_id | INTEGER | Traceability |
| player_id | INTEGER | Shooter |
| season | TEXT | Season |
| shot_distance | REAL | Context feature |
| shot_zone_basic | TEXT | Context feature |
| shot_zone_area | TEXT | Context feature |
| action_type | TEXT | Context feature |
| shot_type | TEXT | Context feature |
| period | INTEGER | Context feature |
| seconds_remaining_in_period | REAL | Context feature |
| score_margin | REAL | Context feature |
| in_bonus | INTEGER | Context feature (placeholder) |
| home_or_away | TEXT | Context feature |
| shooter_height | REAL | Context feature |
| shooter_position | TEXT | Context feature |
| prior_season_ftr | REAL | Carried (NOT used by headline model) |
| prior_season_drive_rate | REAL | Carried (NOT used by headline model) |
| fta_from_shot | INTEGER | Target (0/1/2/3) |
| xfta | REAL | Model-predicted expected FTA (from cross-fit) |

## predictions

One row per FGA. The cross-fit xFTA predictions.

| Column | Type | Description |
|--------|------|-------------|
| game_id | TEXT | Join key |
| event_id | INTEGER | Join key |
| xfta | REAL | Predicted expected FTA from cross-fold model |

## player_season_xfta

One row per player per season. The leaderboard table.

| Column | Type | Description |
|--------|------|-------------|
| player_id | INTEGER | Shooter |
| player_name | TEXT | Player name |
| season | TEXT | Season |
| fga | INTEGER | Field goal attempts |
| actual_fta_from_fouls | INTEGER | Actual FTA from shooting fouls |
| xfta_total | REAL | Sum of xFTA across all shots |
| ftaoe | REAL | Raw FTAOE = actual − xFTA |
| ftaoe_centered | REAL | Season-centered FTAOE (subtracts league-mean per-shot residual) |
| ftaoe_per_100_fga | REAL | FTAOE per 100 FGA |
| ftaoe_per_100_poss | REAL | FTAOE per 100 possessions (NaN if possessions unavailable) |
| possessions | INTEGER | Player-season possessions (placeholder) |

**FTAOE vs FTAOE_centered:** FTAOE is raw (actual − xFTA). Use FTAOE_centered for cross-season comparisons because the league-wide foul environment drifts year to year, so each season is centered on its own league mean. For within-season ranking, plain FTAOE is fine.

## model_artifacts/

Directory containing model files and outputs:

| File | Description |
|------|-------------|
| headline_gate_a.txt | LightGBM model (Gate A single split) |
| headline_final.txt | LightGBM model (all 3 seasons, for future scoring) |
| feature_importance.csv | Gain-based feature importance |
| metrics_gate_a.json | Gate A validation metrics |
| calibration_global.png | Global calibration plot (10 deciles) |
| calibration_per_zone.png | Per-zone calibration plot |
| calibration_poisson_vs_multiclass.png | Poisson vs multiclass calibration comparison |
| cross_fit_predictions.csv | Per-shot xFTA from 3-fold season cross-fit |
| gate_a_test_predictions.csv | Gate A test set predictions |
| gate_a_test_full.csv | Gate A test set with all columns |
| archetype_predictions.csv | Archetype variant predictions |
| multiclass_predictions.csv | Multiclass variant predictions |
