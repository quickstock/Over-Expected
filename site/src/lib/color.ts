/**
 * The diverging FTAOE encoding. Warm = draws more shooting fouls than the
 * league baseline, cool = fewer, neutral at zero. This is the only place
 * vivid color comes from; it is never decoration.
 */

const WARM = { l: 0.58, c: 0.185, h: 38 };
const COOL = { l: 0.52, c: 0.115, h: 252 };
const NEUTRAL_L = 0.72;

/** Domain: FTAOE per 100 possessions. ±12 saturates the scale. */
export const SCALE_MAX = 12;

function clamp01(t: number) {
  return Math.max(0, Math.min(1, t));
}

/** Strong solid for text, strokes, and chips. */
export function divergingColor(per100: number): string {
  const t = clamp01(Math.abs(per100) / SCALE_MAX);
  const pole = per100 >= 0 ? WARM : COOL;
  const l = NEUTRAL_L + (pole.l - NEUTRAL_L) * t;
  const c = 0.008 + (pole.c - 0.008) * t;
  return `oklch(${l.toFixed(3)} ${c.toFixed(3)} ${pole.h})`;
}

/** Light tint for row washes and area fills. */
export function divergingTint(per100: number, maxAlpha = 0.16): string {
  const t = clamp01(Math.abs(per100) / SCALE_MAX);
  const pole = per100 >= 0 ? WARM : COOL;
  return `oklch(${pole.l} ${pole.c} ${pole.h} / ${(t * maxAlpha).toFixed(3)})`;
}

/** Dark enough for body-size text on paper (WCAG AA). */
export function divergingText(per100: number): string {
  const pole = per100 >= 0 ? WARM : COOL;
  const l = per100 >= 0 ? 0.5 : 0.46;
  return `oklch(${l} ${pole.c} ${pole.h})`;
}

export const warmText = divergingText(SCALE_MAX);
export const coolText = divergingText(-SCALE_MAX);
