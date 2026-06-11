import type { GameLine } from "../types";

export interface ArcPoint {
  /** 1-based game index in schedule order. */
  g: number;
  cumActual: number;
  cumExpected: number;
}

/** Per-game [actual, expected, poss] lines -> cumulative series. */
export function cumulativeArc(games: GameLine[]): ArcPoint[] {
  let a = 0;
  let x = 0;
  return games.map(([actual, expected], i) => {
    a += actual;
    x += expected;
    return { g: i + 1, cumActual: a, cumExpected: x };
  });
}

export interface RollingPoint {
  /** 1-based index of the window's last game. */
  g: number;
  /** FTAOE per 100 possessions over the trailing window. */
  per100: number;
  /** Possessions inside the window (stability context). */
  poss: number;
}

/**
 * Trailing-window FTAOE per 100 possessions — same unit as the
 * leaderboard, computed over the last `window` games. Starts once a
 * full window exists; windows with zero possessions are skipped.
 */
export function rollingRate(games: GameLine[], window: number): RollingPoint[] {
  const out: RollingPoint[] = [];
  for (let i = window - 1; i < games.length; i++) {
    let a = 0;
    let x = 0;
    let p = 0;
    for (let j = i - window + 1; j <= i; j++) {
      a += games[j][0];
      x += games[j][1];
      p += games[j][2];
    }
    if (p === 0) continue;
    out.push({ g: i + 1, per100: ((a - x) / p) * 100, poss: p });
  }
  return out;
}
