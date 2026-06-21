export interface LeaderboardRow {
  id: number;
  name: string;
  season: string;
  pos: string | null;
  /** Teams the player finished possessions for, in first-appearance order. */
  teams: string[];
  poss: number;
  fta: number;
  xfta: number;
  ftaoe: number;
  per100: number;
  pct: number | null;
  /** Style-adjusted FTAOE per 100 (vs attack-profile baseline); null when
      tracking exposures are unavailable or below the qualify threshold. */
  sper100: number | null;
  spct: number | null;
}

/** One player-season in the shot-value suite (xFG% + xFTA -> points). */
export interface ShotValueRow {
  id: number;
  name: string;
  pos: string | null;
  teams: string[];
  fga: number;
  poss: number;
  /** Actual FG% (percent). */
  fgPct: number;
  /** Expected FG% from the calibrated, shooter-agnostic xFG% model. */
  xfgPct: number;
  /** Shot-making over expected: FG% - xFG%, percentage points. */
  makeOE: number;
  /** Shot-selection value: mean expected points per shot of the looks taken. */
  xptsShot: number;
  /** Shot-making in points: FG points over expected per 100 possessions. */
  fgPoe100: number;
  /** Season free-throw make rate, for valuing drawn FTs in the gap chart. */
  ftPct: number;
  /** Foul-drawing: FTAOE per 100 possessions (the live FTAOE board's unit). */
  ftaoe100: number;
  /** Combined points over expected per 100 possessions (the headline). */
  poe100: number;
}

export interface ZoneAgg {
  zone: string;
  area: string;
  n: number;
  share: number;
}

/**
 * Per game, in schedule order:
 * [actual shooting-foul FTA, expected FTA, possessions, actual FG points,
 *  expected FG points]. The last two power the shot-value / shot-making
 * gap and form charts; absent in exports made before the suite existed.
 */
export type GameLine = [number, number, number, number?, number?];

/**
 * Shooting fouls itemized. FT counts by trip type; the identity
 * and1 + sf2 + sf3 === season actual FTA holds exactly by construction.
 */
export interface FoulBreakdown {
  /** FTs from and-1s (one per trip). */
  and1: number;
  /** FTs from fouled 2-pt misses (two per trip). */
  sf2: number;
  /** FTs from fouled 3-pt misses (three per trip). */
  sf3: number;
  /** And-1s with an officially located made shot (≤ and1). */
  located: number;
  /** Zones of located and-1 shots; shares sum to 1 over `located`. */
  zones: ZoneAgg[];
}

export interface SeasonDetail {
  games: GameLine[];
  zones: ZoneAgg[];
  /** Absent in exports made before the foul itemization existed. */
  fouls?: FoulBreakdown;
}

/** players-{season}.json: playerId -> detail. */
export type PlayerSeasonChunk = Record<string, SeasonDetail>;

export interface CalibrationBin {
  pred: number;
  actual: number;
  n: number;
}

/** Shooting-foul FTA per 100 possessions in one slice, against that slice's
    own league baseline. `per100` is the official, `lg` the league. */
export interface WhistleSplit {
  poss: number;
  /** Shooting-foul FTA per 100 possessions for this official in the slice. */
  per100: number;
  /** League per-100 baseline for the same slice (season + quarter/script). */
  lg: number;
}

export interface RefSeasonDetail {
  games: number;
  poss: number;
  fta: number;
  per100: number;
  lg: number;
  /** By quarter; "Q1".."Q4" plus "OT" when worked. */
  quarters: (WhistleSplit & { q: string })[];
  /** By final game script: "close" (<=5), "mid" (6-12), "blowout" (13+). */
  script: (WhistleSplit & { b: string; games: number })[];
}

export interface RefProfile {
  name: string;
  /** Seasons worked with >= 20 games, ascending. */
  seasons: string[];
  detail: Record<string, RefSeasonDetail>;
}

export interface SiteData {
  meta: {
    seasons: string[];
    /** Latest season with >= 50 qualified players; the UI's default. */
    defaultSeason: string;
    qualifyPossessions: number;
    nPossessions: number;
    leagueRatePer100: number;
    leagueRateBySeason: Record<string, number>;
    modelLiftPct: number;
    foldLifts: { season: string; liftPct: number }[];
    reliability: {
      fullSeasonR: number;
      yoyMeanR: number;
      yoyPairs: { pair: string; r: number; n: number }[];
      paddingK: number;
    };
  };
  leaderboard: LeaderboardRow[];
  distributions: Record<string, number[]>;
  leagueZones: Record<string, { zone: string; area: string; share: number }[]>;
  calibration: CalibrationBin[];
  /** Per season: officials with >= 20 games, sorted by diff desc. */
  referees: Record<
    string,
    { id: number; name: string; games: number; per100: number; diff: number }[]
  >;
  /** Per-official profile, keyed by official id (string). */
  refProfiles: Record<string, RefProfile>;
  /** Per season: qualified player-seasons in the shot-value suite. */
  shotValue: Record<string, ShotValueRow[]>;
  /** Per season: 30 teams, FTAOE/100 drawn (offense) and conceded (defense). */
  teams: Record<string, TeamRow[]>;
}

/** One team-season: shooting fouls drawn (offense) and conceded (defense). */
export interface TeamRow {
  team: string;
  poss: number;
  /** FTAOE/100 the offense draws. */
  drawn: number;
  /** FTAOE/100 the defense concedes. */
  conceded: number;
}
