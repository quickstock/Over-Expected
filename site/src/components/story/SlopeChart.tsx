import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { divergingColor, divergingText } from "../../lib/color";
import { lastName, signed } from "../../lib/format";
import { useMeasure } from "../../lib/useMeasure";

export interface SlopePair {
  id: number;
  name: string;
  before: number;
  after: number;
}

/**
 * Slope chart: every player qualified in both seasons, FTAOE/100 before
 * vs after. The crowd stays hairline-gray; highlighted players take the
 * diverging encoding on their season-to-season CHANGE (cool = fell,
 * warm = rose) with direct labels. Lines draw on scroll-in.
 */
export default function SlopeChart({
  pairs,
  highlight,
  beforeLabel,
  afterLabel,
  height = 460,
  className = "",
}: {
  pairs: SlopePair[];
  highlight: number[];
  beforeLabel: string;
  afterLabel: string;
  height?: number;
  className?: string;
}) {
  const [wrapRef, width] = useMeasure<HTMLDivElement>();
  const [revealed, setRevealed] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!wrapRef.current) return;
    const io = new IntersectionObserver(
      (es) => {
        if (es[0].isIntersecting) {
          setRevealed(true);
          io.disconnect();
        }
      },
      { threshold: 0.25 },
    );
    io.observe(wrapRef.current);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pad = { top: 30, bottom: 30, left: 118, right: 118 };
  const innerW = Math.max(60, width - pad.left - pad.right);
  const innerH = height - pad.top - pad.bottom;
  const x0 = pad.left;
  const x1 = pad.left + innerW;

  const maxAbs = useMemo(
    () =>
      Math.max(
        4,
        ...pairs.map((p) => Math.max(Math.abs(p.before), Math.abs(p.after))),
      ) * 1.05,
    [pairs],
  );
  const y = (v: number) => pad.top + innerH / 2 - (v / maxAbs) * (innerH / 2);

  const hi = useMemo(() => {
    const set = new Set(highlight);
    return pairs.filter((p) => set.has(p.id));
  }, [pairs, highlight]);

  // Nudge labels apart vertically on each side.
  const placed = useMemo(() => {
    const space = (rows: { id: number; yy: number }[]) => {
      const sorted = [...rows].sort((a, b) => a.yy - b.yy);
      for (let i = 1; i < sorted.length; i++) {
        if (sorted[i].yy - sorted[i - 1].yy < 16) {
          sorted[i].yy = sorted[i - 1].yy + 16;
        }
      }
      return new Map(sorted.map((r) => [r.id, r.yy]));
    };
    return {
      left: space(hi.map((p) => ({ id: p.id, yy: y(p.before) }))),
      right: space(hi.map((p) => ({ id: p.id, yy: y(p.after) }))),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hi, width, height]);

  return (
    <div ref={wrapRef} className={`relative ${className}`}>
      {width > 0 && (
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={`FTAOE per 100, ${beforeLabel} versus ${afterLabel}, for ${pairs.length} players qualified in both seasons.`}
        >
          {/* axes */}
          {[x0, x1].map((xx) => (
            <line
              key={xx}
              x1={xx}
              x2={xx}
              y1={pad.top - 6}
              y2={pad.top + innerH + 6}
              stroke="var(--color-line)"
            />
          ))}
          <line
            x1={x0}
            x2={x1}
            y1={y(0)}
            y2={y(0)}
            stroke="var(--color-line-soft)"
          />
          <text
            x={x0}
            y={16}
            textAnchor="middle"
            fontSize={11.5}
            className="font-mono"
            fill="var(--color-ink-soft)"
          >
            {beforeLabel}
          </text>
          <text
            x={x1}
            y={16}
            textAnchor="middle"
            fontSize={11.5}
            className="font-mono"
            fill="var(--color-ink-soft)"
          >
            {afterLabel}
          </text>
          <text
            x={x0 - 8}
            y={y(0) + 3.5}
            textAnchor="end"
            fontSize={10}
            className="font-mono"
            fill="var(--color-ink-faint)"
          >
            league avg
          </text>

          {/* the crowd */}
          <g
            style={{
              opacity: revealed ? 1 : 0,
              transition: "opacity 700ms ease",
            }}
          >
            {pairs.map((p) => (
              <line
                key={p.id}
                x1={x0}
                x2={x1}
                y1={y(p.before)}
                y2={y(p.after)}
                stroke="var(--color-line)"
                strokeWidth={1}
              />
            ))}
          </g>

          {/* highlighted players, colored by their change */}
          {hi.map((p, i) => {
            const d = p.after - p.before;
            const color = divergingColor(d);
            const tcolor = divergingText(d);
            const ly0 = placed.left.get(p.id) ?? y(p.before);
            const ly1 = placed.right.get(p.id) ?? y(p.after);
            return (
              <g
                key={p.id}
                className="cursor-pointer"
                role="link"
                tabIndex={0}
                aria-label={`${p.name}: ${signed(p.before, 1)} to ${signed(p.after, 1)}`}
                onClick={() => navigate(`/player/${p.id}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") navigate(`/player/${p.id}`);
                }}
                style={{
                  opacity: revealed ? 1 : 0,
                  transition: `opacity 500ms ease ${250 + i * 90}ms`,
                }}
              >
                <line
                  x1={x0}
                  x2={x1}
                  y1={y(p.before)}
                  y2={y(p.after)}
                  stroke={color}
                  strokeWidth={2.25}
                />
                <circle cx={x0} cy={y(p.before)} r={3.5} fill={color} />
                <circle cx={x1} cy={y(p.after)} r={3.5} fill={color} />
                <text
                  x={x0 - 8}
                  y={ly0 + 3.5}
                  textAnchor="end"
                  fontSize={11.5}
                  fontWeight={600}
                  className="font-display"
                  fill="var(--color-ink)"
                >
                  {lastName(p.name)}{" "}
                  <tspan className="font-mono tnum" fontWeight={400} fill={tcolor}>
                    {signed(p.before, 1)}
                  </tspan>
                </text>
                <text
                  x={x1 + 8}
                  y={ly1 + 3.5}
                  textAnchor="start"
                  fontSize={11.5}
                  className="font-mono tnum"
                  fill={tcolor}
                >
                  {signed(p.after, 1)}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}
