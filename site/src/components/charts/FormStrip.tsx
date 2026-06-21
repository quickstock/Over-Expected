import { useMemo, useState } from "react";
import type { GameLine } from "../../types";
import { rollingRate } from "../../lib/series";
import { divergingColor, divergingText } from "../../lib/color";
import { int, signed } from "../../lib/format";
import { useMeasure } from "../../lib/useMeasure";
import { useRevealed } from "../../lib/useRevealed";

interface Props {
  /** Per game, schedule order: [actual FTA, expected, possessions]. */
  games: GameLine[];
  /** Trailing window size in games. */
  window: number;
  height?: number;
  className?: string;
}

/**
 * Form: trailing-window FTAOE per 100 possessions, one bar per game,
 * the leaderboard's unit, watched move through a season. Bars animate
 * between window sizes (geometry transitions; reduced motion safe).
 */
export default function FormStrip({
  games,
  window: win,
  height = 200,
  className = "",
}: Props) {
  const [wrapRef, width] = useMeasure<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const revealed = useRevealed(wrapRef);

  const points = useMemo(() => rollingRate(games, win), [games, win]);
  const n = games.length;

  const pad = { top: 14, right: 14, bottom: 26, left: 8 };
  const innerW = Math.max(40, width - pad.left - pad.right);
  const innerH = height - pad.top - pad.bottom;
  const mid = pad.top + innerH / 2;

  const maxAbs = Math.max(4, ...points.map((p) => Math.abs(p.per100))) * 1.08;
  const x = (g: number) => pad.left + ((g - 1) / Math.max(1, n - 1)) * innerW;
  const scaleY = (v: number) => (v / maxAbs) * (innerH / 2);
  const barW = Math.max(2, Math.min(9, (innerW / Math.max(1, n)) * 0.66));

  if (points.length === 0) {
    return (
      <div className={`rounded border border-line-soft bg-wash px-4 py-8 text-center text-sm text-ink-faint ${className}`}>
        Not enough games for a {win}-game window.
      </div>
    );
  }

  const peak = points.reduce((a, b) => (b.per100 > a.per100 ? b : a));
  const trough = points.reduce((a, b) => (b.per100 < a.per100 ? b : a));
  const hovered = hover !== null ? points.find((p) => p.g === hover) ?? null : null;

  const callouts = [peak, ...(trough.g !== peak.g ? [trough] : [])];

  return (
    <div ref={wrapRef} className={`relative ${className}`}>
      {width > 0 && (
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={`Trailing ${win}-game FTAOE per 100 possessions across the season. Peak ${signed(peak.per100, 1)}, low ${signed(trough.per100, 1)}.`}
        >
          {/* zero = league-average rate */}
          <line
            x1={pad.left}
            x2={pad.left + innerW}
            y1={mid}
            y2={mid}
            stroke="var(--color-line)"
            strokeWidth={1}
          />
          <text
            x={pad.left}
            y={height - 8}
            textAnchor="start"
            fontSize={10}
            fill="var(--color-ink-faint)"
            className="font-mono"
          >
            league average
          </text>
          <text
            x={pad.left + innerW}
            y={height - 8}
            textAnchor="end"
            fontSize={10}
            fill="var(--color-ink-faint)"
            className="font-mono tnum"
          >
            trailing {win} games
          </text>

          <g
            style={{
              clipPath: revealed ? "inset(-6% -6% -6% -6%)" : "inset(-6% 102% -6% -6%)",
              transition: "clip-path 900ms var(--ease-out-strong)",
            }}
          >
            {points.map((p) => {
              const h = Math.max(1.5, Math.abs(scaleY(p.per100)));
              const up = p.per100 >= 0;
              return (
                <rect
                  key={p.g}
                  x={x(p.g) - barW / 2}
                  y={up ? mid - h : mid}
                  width={barW}
                  height={h}
                  rx={1}
                  fill={divergingColor(p.per100)}
                  opacity={hover === null || hover === p.g ? 1 : 0.45}
                  style={{
                    transition:
                      "y 320ms var(--ease-out-strong), height 320ms var(--ease-out-strong), opacity 150ms ease",
                  }}
                  onPointerEnter={() => setHover(p.g)}
                  onPointerLeave={() => setHover(null)}
                />
              );
            })}
          </g>

          {/* direct labels on the extremes: peak beyond its tip, trough on
              the empty side of the baseline when every bar points one way */}
          {callouts.map((p) => {
            const isPeak = p.g === peak.g;
            let yv: number;
            if (isPeak) {
              yv = p.per100 >= 0 ? mid - Math.abs(scaleY(p.per100)) - 6 : mid - 6;
            } else {
              yv = p.per100 < 0 ? mid + Math.abs(scaleY(p.per100)) + 13 : mid + 13;
            }
            return (
              <text
                key={`co-${p.g}`}
                x={Math.min(Math.max(x(p.g), pad.left + 18), pad.left + innerW - 18)}
                y={yv}
                textAnchor="middle"
                fontSize={10.5}
                fontWeight={650}
                className="font-mono tnum"
                fill={divergingText(p.per100)}
              >
                {signed(p.per100, 1)}
              </text>
            );
          })}
        </svg>
      )}

      {hovered && (
        <div
          className="pointer-events-none absolute z-10 whitespace-nowrap rounded border border-line bg-paper px-2.5 py-1.5 font-mono text-[11px] leading-snug shadow-sm tnum"
          style={{
            left: Math.min(Math.max(x(hovered.g) - 70, 0), Math.max(0, width - 170)),
            top: 0,
          }}
        >
          <div className="text-ink-faint">
            games {hovered.g - win + 1}-{hovered.g}
          </div>
          <div style={{ color: divergingText(hovered.per100) }}>
            {signed(hovered.per100, 1)} per 100
          </div>
          <div className="text-ink-soft">{int(hovered.poss)} poss in window</div>
        </div>
      )}
    </div>
  );
}
