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
}

export interface ZoneAgg {
  zone: string;
  area: string;
  n: number;
  share: number;
}

/** Per game, in schedule order: [actual shooting-foul FTA, expected, possessions]. */
export type GameLine = [number, number, number];

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

export interface SiteData {
  meta: {
    seasons: string[];
    qualifyPossessions: number;
    nPossessions: number;
    leagueRatePer100: number;
    leagueRateBySeason: Record<string, number>;
    modelLiftPct: number;
    foldLifts: { season: string; liftPct: number }[];
  };
  leaderboard: LeaderboardRow[];
  distributions: Record<string, number[]>;
  leagueZones: Record<string, { zone: string; area: string; share: number }[]>;
  calibration: CalibrationBin[];
}
