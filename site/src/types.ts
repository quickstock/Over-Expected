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

export interface SeasonDetail {
  /** Per game, in schedule order: [actual shooting-foul FTA, baseline xFTA] */
  games: [number, number][];
  zones: ZoneAgg[];
}

export interface PlayerData {
  name: string;
  seasons: Record<string, SeasonDetail>;
}

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
  players: Record<string, PlayerData>;
  calibration: CalibrationBin[];
}
