# Database schema (`xfta.db`)

SQLite. Six seasons (2020-21 to 2025-26), 7,230 games, shooting fouls only.
Tables fall into three groups: ingested base data, training features, and model
outputs that feed the site.

## Rebuild order

```
pull.py                       network pull -> cache/ (parquet)
build_tables.py               -> games, shots, training_fga, player_season
build_possessions_v3.py       -> possessions  (per-possession shooting-foul target)
build_training_possessions_v2.py -> training_possessions_v2 (possession features)
backfill_score_margin.py      -> fills shots.score_margin from play-by-play
train_possession_v4_context.py-> predictions_poss_clean  (expected FTA per possession)
build_possession_leaderboard_clean.py -> player_season_xfta_poss_lb_clean (FTAOE board)
build_style_adjusted.py       -> style_expected  (attack-profile baseline)
build_player_ft.py            -> player_season_ft  (season FT%)
xfg_model.py / shot_value.py  -> shot_value, player_game_shot_value, team_shot_value
export_site_data.py           -> site/public/*.json   (gated by scripts/validate_export.py)
```

## Base / ingested

### games (7,230)
`GAME_ID, season, GAME_DATE, home_team_id, away_team_id`. One row per regular
season game.

### game_meta (7,230)
`game_id, home_team_id, away_team_id, ref1_id, ref1_name, ref2_id, ref2_name,
ref3_id, ref3_name, n_officials`. Officiating crew per game, source for the
referee profiles.

### shots (1,282,312)
One row per field-goal attempt.
`game_id, event_id, player_id, team_id, period, seconds_remaining_in_period,
shot_made, shot_x, shot_y, shot_distance, shot_zone_basic, shot_zone_area,
shot_zone_range, action_type, shot_type, home_or_away, score_margin`.
`event_id` maps 1:1 to play-by-play `actionNumber`. `score_margin` is signed by
the shooting team and is now complete (backfilled from play-by-play; about 5%
are genuine ties). A fouled miss is not a charged shot and is absent here, which
is why the foul-drawing stat is per possession, not per shot.

### possessions (1,420,917)
One row per possession.
`game_id, period, possession_number, start_time, end_time, offense_team_id,
n_events, sfta, finisher_player_id, excluded_ft_count, contamination_count,
ft_and1, ft_sf2, ft_sf3`. `sfta` is the shooting-foul free throw target (almost
always 0; 1-3 on a foul trip, rarely 4-5 when offensive rebounds produce two
foul trips in one possession). `ft_and1 / ft_sf2 / ft_sf3` itemize free throws
by trip type and sum to `sfta`. The finisher is the player charged with the
possession's shooting-foul free throws.

### and1_shots (34,454)
`game_id, event_id, player_id, possession_number`. Made shots that drew a foul
(the only shooting fouls with an official shot location), used for the
foul-origin court view.

### player_season (6,288)
`player_id, player_name, height_inches, position, season, prior_season_ftr,
prior_season_drive_rate, possessions`. Player attributes plus prior-season rates
used as carried features.

### tracking_exposures (3,407)
`player_id, gp, drives, paint_touches, post_touches, season`. Attack profile
feeding the style-adjusted baseline.

## Training features

### training_fga (1,282,312)
The modeling superset, one row per FGA, joining shot context to the foul target.
`game_id, event_id, player_id, season, shot_distance, shot_zone_basic,
shot_zone_area, action_type, shot_type, period, seconds_remaining_in_period,
score_margin, in_bonus, home_or_away, shooter_height, shooter_position,
prior_season_ftr, prior_season_drive_rate, fta_from_shot`. The site also reads
this for per-player charged-FGA shot zones.

## Model outputs

### predictions_poss_clean (1,420,917)
`game_id, possession_number, season, sfta, xfta`. The headline FTAOE model's
out-of-fold expected free throws per possession, leak-free season cross-fit
(written by `train_possession_v4_context.py`). FTAOE = `sfta - xfta`.

### player_season_xfta_poss_lb_clean (3,566)
The FTAOE leaderboard, one row per qualified player-season.
`player_id, season, possessions, actual_fta_from_fouls, xfta_total, ftaoe,
ftaoe_per_100, ftaoe_rank, player_name, position`. Anchored per season so the
league sits at zero and seasons are comparable.

### style_expected (1,691)
`player_id, season, style_xfta`. Expected free throws from a player's attack
profile alone (drives, paint and post touches). The residual against actual is
the style-adjusted FTAOE shown on player pages.

### player_season_ft (3,407)
`player_id, player_name, season, ftm, fta, ft_pct`. Season free-throw rate, used
to value a player's drawn free throws at his own line in the shot-value headline.

### shot_value (3,213)
The shot-value suite, one row per qualified player-season.
`player_id, player_name, season, position, possessions, fga, fgm, fg_pct,
xfg_pct, shot_making_oe, xpoints_per_shot, exp_fg_pts, act_fg_pts, fg_pts_oe,
fg_pts_oe_per100, actual_fta, xfta_total, ftaoe, ft_pct, ft_pts_oe,
ft_pts_oe_per100, points_oe, points_oe_per100`. `xfg_pct` is the leak-free
expected FG% for the looks taken; `points_oe_per100` is the headline (field-goal
points over expected plus free throws drawn at the player's own FT%).

### player_game_shot_value (145,131)
`player_id, game_id, season, fga, fgm, act_fg_pts, exp_fg_pts`. Per-game FG
points actual vs expected, the series behind the shot-value gap and form charts.

### team_shot_value (180)
`team_id, season, off_* / def_* (fga, act_fg_pts, exp_fg_pts)`. Team FG points
over expected on both ends, retained for analysis (the live League board uses
the foul-drawing side).

## Notes

- The numbers are descriptive. They blend playstyle, contact-seeking skill, and
  officiating, and do not isolate or prove referee bias.
- Models are leak-free (season cross-fit) and anchored per season.
- `xfta.db` is gitignored; a slim gzip is kept in version control.
