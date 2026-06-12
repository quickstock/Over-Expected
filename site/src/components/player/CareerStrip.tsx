import type { LeaderboardRow } from "../../types";
import { divergingColor, divergingText } from "../../lib/color";
import { signed } from "../../lib/format";
import { useMeasure } from "../../lib/useMeasure";

/**
 * Career trajectory: FTAOE per 100 by season, dots in the diverging
 * encoding, clickable to switch the page's season. Zero line = league
 * average each season (anchored, so seasons are comparable).
 */
export default function CareerStrip({
  rows,
  activeSeason,
  onSelect,
  height = 170,
  className = "",
}: {
  rows: LeaderboardRow[];
  activeSeason: string;
  onSelect: (season: string) => void;
  height?: number;
  className?: string;
}) {
  const [wrapRef, width] = useMeasure<HTMLDivElement>();
  const n = rows.length;
  if (n < 2) return null;

  const pad = { top: 26, bottom: 26, left: 26, right: 26 };
  const innerW = Math.max(40, width - pad.left - pad.right);
  const innerH = height - pad.top - pad.bottom;
  const maxAbs = Math.max(4, ...rows.map((r) => Math.abs(r.per100))) * 1.15;
  const x = (i: number) => pad.left + (i / (n - 1)) * innerW;
  const y = (v: number) => pad.top + innerH / 2 - (v / maxAbs) * (innerH / 2);

  const path = rows
    .map((r, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${y(r.per100).toFixed(1)}`)
    .join("");

  return (
    <div ref={wrapRef} className={`relative ${className}`}>
      {width > 0 && (
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={`FTAOE per 100 by season: ${rows
            .map((r) => `${r.season} ${signed(r.per100, 1)}`)
            .join(", ")}.`}
        >
          {/* league-average axis */}
          <line
            x1={pad.left - 8}
            x2={pad.left + innerW + 8}
            y1={y(0)}
            y2={y(0)}
            stroke="var(--color-line)"
            strokeWidth={1}
          />
          <path
            d={path}
            fill="none"
            stroke="var(--color-ink-faint)"
            strokeWidth={1.25}
          />
          {rows.map((r, i) => {
            const active = r.season === activeSeason;
            return (
              <g
                key={r.season}
                className="cursor-pointer"
                role="button"
                tabIndex={0}
                aria-label={`${r.season}: ${signed(r.per100, 1)} per 100${active ? " (shown)" : ""}`}
                onClick={() => onSelect(r.season)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(r.season);
                  }
                }}
              >
                {/* generous hit area */}
                <rect
                  x={x(i) - 18}
                  y={pad.top - 10}
                  width={36}
                  height={innerH + 20}
                  fill="transparent"
                />
                <circle
                  cx={x(i)}
                  cy={y(r.per100)}
                  r={active ? 6 : 4.5}
                  fill={divergingColor(r.per100)}
                  stroke={active ? "var(--color-ink)" : "var(--color-paper)"}
                  strokeWidth={active ? 1.75 : 1}
                  style={{ transition: "r 150ms ease, stroke 150ms ease" }}
                />
                <text
                  x={x(i)}
                  y={y(r.per100) + (r.per100 >= 0 ? -12 : 19)}
                  textAnchor="middle"
                  fontSize={10.5}
                  fontWeight={650}
                  className="font-mono tnum"
                  fill={divergingText(r.per100)}
                >
                  {signed(r.per100, 1)}
                </text>
                <text
                  x={x(i)}
                  y={height - 8}
                  textAnchor="middle"
                  fontSize={10.5}
                  className="font-mono"
                  fill={active ? "var(--color-ink)" : "var(--color-ink-faint)"}
                >
                  '{r.season.slice(2, 4)}-{r.season.slice(5)}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}
