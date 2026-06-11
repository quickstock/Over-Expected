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

export interface SeasonDetail {
  games: GameLine[];
  zones: ZoneAgg[];
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
