# xFTA — Phase 1: Data Pipeline & Tables (Claude Code task spec)

## Context

xFTA ("expected free throw attempts") is an NBA stat. **Unit of analysis: one row =
one field-goal attempt (FGA).** The target is how many free throws a *shooting foul*
on that shot produced. The leaderboard stat is FTA-over-expected: actual FTA from
shooting fouls minus model-predicted xFTA.

Phase 0 is done. `xfta_phase0_link.py` is in the repo — it manually links a shooting
foul → FGA → FTs for one game. **Read it first**; it documents the linking logic and
the edge cases. This phase scales that up robustly using `pbpstats` (proper and-1 /
continuation parsing) and `nba_api` (shot coordinates and zones).

**Model decision that shapes the tables:** the headline model is *context-only* — it
sees only properties of the shot, never a player-identity foul-drawing prior. But
build the tables as a **superset**: include player prior-season rate columns too, so
a year-over-year model variant is possible later without re-pulling. Feature
*selection* happens at model time, not in this pipeline.

## Objective

A reproducible, cached, idempotent pipeline that produces a clean training table —
one row per FGA, all features + target — for the **2022-23, 2023-24, and 2024-25
regular seasons**, plus the staging tables behind it. Store in SQLite. Expect
~600k FGA rows.

## Working discipline — read before writing code

1. **Phased, with stop-for-review gates. Do NOT run the full 3-season pull
   unattended.** Sequence:
   - **Gate A** — build the pipeline, run on one game (`0022300001`), STOP, show me
     the `training_fga` rows + validation report for that game.
   - **Gate B** — after I approve, run one week of games (~50), STOP, show validation.
   - **Gate C** — after I approve, run the full 3 seasons.
   Do not cross a gate without my explicit approval. Commit working code at each gate.
2. **One rate-limited request wrapper.** Every `nba_api` web call goes through it:
   configurable min sleep between calls (start at 0.6s), exponential-backoff retry on
   timeouts and HTTP 429 (3 retries, jitter).
3. **Idempotent + cached.** Cache every raw response to disk per game/player. A re-run
   skips already-cached items; a crash mid-pull loses nothing. The network pull and
   the table-building must be **separate steps** (separate scripts).
4. **No defender / player-tracking data this phase** — deferred to v2. Don't pull it.
5. **Never silently impute.** If a field is missing for a shot, leave it null and log
   it.

## Data sources

**pbpstats** — robust shot↔free-throw linking + possession context. Configure
`pbpstats.client.Client` with the `stats_nba` provider and a response-cache `dir`
(this gives pbpstats caching for free). Relevant enhanced-pbp event properties
(already verified to exist):
- `FieldGoal`: `is_made`, `shot_value` (2/3), `is_and1`, `distance`, `shot_type`,
  `is_putback`
- `Foul`: `is_shooting_foul`, `is_shooting_block_foul`, `number_of_fta_for_foul`,
  `counts_towards_penalty`
- `FreeThrow`: `foul_that_led_to_ft`, `is_technical_ft`, `num_ft_for_trip`,
  `is_first_ft`

Read the pbpstats docs/source to confirm the `Game` / possession-iteration API, then
verify it on game `0022300001` before scaling.

**nba_api `shotchartdetail`** — per-shot X/Y, distance, `SHOT_ZONE_BASIC`,
`SHOT_ZONE_AREA`, `SHOT_ZONE_RANGE`, `ACTION_TYPE`, `SHOT_TYPE` (2PT/3PT).
- **Gotcha:** pass `context_measure_simple='FGA'` — the default `'PTS'` returns made
  shots only. You need misses.
- Pull per player per season (`team_id=0`, `player_id=<id>`, `season_nullable`,
  `season_type_all_star='Regular Season'`). Cache one parquet per player-season.

**The join:** `shotchartdetail.GAME_EVENT_ID` == play-by-play `EVENTNUM`. Join shot
spatial features to the pbpstats shot event on `(GAME_ID, GAME_EVENT_ID)`. Report
join coverage; expect ~99%+.

**Player attributes** — `commonplayerinfo` for height (convert to inches) and
position.

**Prior-season player rates** — `leaguedashplayerstats` for FTA/FGA → FTr, and
`leaguedashptstats` (`pt_measure_type='Drives'`) for drives per game. **Prior season
only** — 2022-23 rows use 2021-22 rates — so pull player rates for 2021-22 through
2024-25. Carried columns; the headline model does not use them.

## Tables (SQLite `xfta.db`, plus parquet raw cache)

- `games` — game_id, season, game_date, home_team_id, away_team_id
- `shots` — one row per FGA: game_id, event_id, player_id, team_id, period,
  seconds_remaining_in_period, score_margin, shot_x, shot_y, shot_distance,
  shot_zone_basic, shot_zone_area, shot_zone_range, action_type, shot_type, shot_made
- `shot_outcomes` — one row per FGA, the **target**: game_id, event_id,
  drew_shooting_foul, fta_from_shot (0/1/2/3), is_and1
- `player_season` — player_id, season, height_inches, position, possessions,
  prior_season_ftr, prior_season_drive_rate
- `training_fga` — final joined table, one row per FGA: all model features + target +
  game_id/event_id/player_id for traceability
- `SCHEMA.md` — documents every table: each column, dtype, source endpoint, notes

### `training_fga` columns

**Target:** `fta_from_shot` (0/1/2/3)

**Context-only model features** (the headline model uses exactly these):
`shot_distance`, `shot_zone_basic`, `shot_zone_area`, `action_type`, `shot_type`,
`period`, `seconds_remaining_in_period`, `score_margin`, `in_bonus`, `home_or_away`,
`shooter_height`, `shooter_position`

**Carried, NOT used by the headline model** (for the future year-over-year variant):
`prior_season_ftr`, `prior_season_drive_rate`

The model code will read its feature list from a config list — keep the table a
superset and never hardcode a feature set into the pipeline.

**Leakage rule:** any player-rate feature is prior-season only. Never the current
season's FTr/drives. Assert this in code.

### Deriving the trickier columns
- `fta_from_shot`: `is_and1` → 1; else a missed shot with a linked shooting foul →
  `number_of_fta_for_foul`; else 0. Exclude technical, flagrant, away-from-play,
  inbound FTs, and bonus (non-shooting) fouls — those are not `fta_from_shot`.
- `in_bonus`: defending team in the penalty when the shot was taken — use pbpstats'
  team-foul tracking, or count penalty-countable fouls per team per period.
- `score_margin`: from the shooting team's perspective; convert PBP `SCOREMARGIN`.
- `seconds_remaining_in_period`: parse `PCTIMESTRING`.

## Validation (pipeline runs this automatically at each gate, prints a report)

1. **Row counts** — FGAs per game ≈ 160–185 combined; flag games far outside.
2. **Target distribution** — print the share of rows at fta_from_shot 0/1/2/3. 0
   dominates; 1/2/3 are small.
3. **Box-score cross-check** — per game, `sum(fta_from_shot)` must be ≤ each side's
   total FTA from the nba_api box score (non-shooting-foul FTs exist). If it
   *exceeds* total FTA, that is a bug — fail loudly.
4. **Phase 0 agreement** — for game `0022300001`, 10 random `shot_outcomes` rows must
   match `xfta_phase0_link.py`'s output.
5. **Join coverage** — % of shot events with a shotchartdetail match; report
   unmatched rows.

## Deliverables
- `nba_client.py` — the rate-limited / retrying request wrapper
- `pull.py` — network pull, writes raw cache only
- `build_tables.py` — builds the SQLite tables from cache (no network)
- `validate.py` — the checks above
- `xfta.db` — SQLite output
- `SCHEMA.md`, `README.md` (how to re-run)

## First action
Read `xfta_phase0_link.py` and the pbpstats docs. Build `nba_client.py` and the
single-game path. Run **Gate A** on `0022300001`. **Stop and show me** the
`training_fga` rows for that game and the validation report. Do not proceed past
Gate A.
