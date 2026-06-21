import type { TeamRow } from "../../types";
import { divergingColor } from "../../lib/color";
import { useMeasure } from "../../lib/useMeasure";
import { useRevealed } from "../../lib/useRevealed";

/**
 * Offense (x) vs defense (y) for one metric, each centered on the league
 * average. Top-right = above the league on both ends; dot color is the net
 * (offense minus defense), warm = nets out positive. Wipes in on first view;
 * eases between positions/colors when the lens or season changes.
 */
export default function TeamScatter({
  teams,
  off,
  def,
  xAxis,
  defLabel,
  height = 380,
}: {
  teams: TeamRow[];
  off: (t: TeamRow) => number | undefined;
  def: (t: TeamRow) => number | undefined;
  xAxis: string;
  defLabel: string;
  height?: number;
}) {
  const [wrapRef, width] = useMeasure<HTMLDivElement>();
  const revealed = useRevealed(wrapRef);
  const reduce =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const pts = teams
    .map((t) => ({ team: t.team, x: off(t), y: def(t) }))
    .filter((p): p is { team: string; x: number; y: number } =>
      p.x !== undefined && p.y !== undefined);

  const pad = { top: 22, right: 18, bottom: 34, left: 18 };
  const innerW = Math.max(40, width - pad.left - pad.right);
  const innerH = height - pad.top - pad.bottom;
  const maxX = Math.max(0.5, ...pts.map((p) => Math.abs(p.x))) * 1.12;
  const maxY = Math.max(0.5, ...pts.map((p) => Math.abs(p.y))) * 1.12;
  const x = (v: number) => pad.left + ((v + maxX) / (2 * maxX)) * innerW;
  // y inverted so "concedes more" is up.
  const y = (v: number) => pad.top + ((maxY - v) / (2 * maxY)) * innerH;

  const sweep: React.CSSProperties = reduce
    ? {}
    : {
        clipPath: revealed ? "inset(-4% -4% -4% -4%)" : "inset(-4% 102% -4% -4%)",
        transition: "clip-path 950ms var(--ease-out-strong)",
      };
  const dotMove = reduce
    ? undefined
    : "transform 520ms var(--ease-out-strong), fill 360ms ease";

  return (
    <div ref={wrapRef} className="relative">
      {width > 0 && (
        <svg width={width} height={height} role="img"
          aria-label={`Team offense versus defense, ${pts.length} teams, both centered on the league average.`}>
          <line x1={x(0)} x2={x(0)} y1={pad.top} y2={pad.top + innerH} stroke="var(--color-line)" />
          <line x1={pad.left} x2={pad.left + innerW} y1={y(0)} y2={y(0)} stroke="var(--color-line)" />
          <text x={pad.left + innerW} y={y(0) - 6} textAnchor="end" fontSize={10.5}
            className="font-mono" fill="var(--color-ink-faint)">
            {xAxis}
          </text>
          <text x={x(0) + 6} y={pad.top + 4} textAnchor="start" fontSize={10.5}
            className="font-mono" fill="var(--color-ink-faint)">
            ↑ {defLabel.toLowerCase()} more
          </text>
          <g style={sweep}>
            {pts.map((p) => {
              const net = p.x - p.y;
              return (
                <g
                  key={p.team}
                  transform={`translate(${x(p.x).toFixed(1)} ${y(p.y).toFixed(1)})`}
                  style={{ transition: dotMove }}
                >
                  <circle cx={0} cy={0} r={4.5} fill={divergingColor(net)} opacity={0.9}
                    style={{ transition: dotMove }} />
                  <text x={0} y={-8} textAnchor="middle" fontSize={9.5}
                    className="font-mono" fill="var(--color-ink-soft)">
                    {p.team}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
      )}
    </div>
  );
}
