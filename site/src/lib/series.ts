export interface ArcPoint {
  /** 1-based game index in schedule order. */
  g: number;
  cumActual: number;
  cumExpected: number;
}

/** Per-game [actual, expected] pairs -> cumulative series. */
export function cumulativeArc(games: [number, number][]): ArcPoint[] {
  let a = 0;
  let x = 0;
  return games.map(([actual, expected], i) => {
    a += actual;
    x += expected;
    return { g: i + 1, cumActual: a, cumExpected: x };
  });
}
