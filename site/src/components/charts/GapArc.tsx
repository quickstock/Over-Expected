import { useEffect, useMemo, useState } from "react";
import type { GameLine } from "../../types";
import { cumulativeArc } from "../../lib/series";
import { signed } from "../../lib/format";
import { divergingText } from "../../lib/color";
import { useMeasure } from "../../lib/useMeasure";

const WARM_FILL = "oklch(0.62 0.17 38 / 0.22)";
const COOL_FILL = "oklch(0.55 0.11 252 / 0.20)";

interface Props {
  /** Per game, schedule order: [actual FTA, expected, possessions]. */
  games: GameLine[];
  height?: number;
  showTooltip?: boolean;
  /** Draw-on reveal when scrolled into view (reduced-motion safe). */
  animate?: boolean;
  className?: string;
}

/**
 * The signature element: cumulative actual vs league-average-pace FTA,
 * the gap between them shaded in the diverging FTAOE encoding.
 */
export default function GapArc({
  games,
  height = 280,
  showTooltip = true,
  animate = true,
  className = "",
}: Props) {
  const [wrapRef, width] = useMeasure<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const [revealed, setRevealed] = useState(!animate);

  useEffect(() => {
    if (!animate || revealed || !wrapRef.current) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setRevealed(true);
          io.disconnect();
        }
      },
      { threshold: 0.3 },
    );
    io.observe(wrapRef.current);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [animate, revealed]);

  const arc = useMemo(() => cumulativeArc(games), [games]);
  const n = arc.length;

  const pad = { top: 18, right: 14, bottom: 26, left: 8 };
  const labelW = width < 480 ? 92 : 128;
  const innerW = Math.max(40, width - pad.left - pad.right - labelW);
  const innerH = height - pad.top - pad.bottom;

  const maxY = Math.max(
    1,
    ...arc.map((p) => Math.max(p.cumActual, p.cumExpected)),
  );
  const x = (g: number) => pad.left + ((g - 1) / Math.max(1, n - 1)) * innerW;
  const y = (v: number) => pad.top + innerH - (v / maxY) * innerH;

  const { actualPath, expectedPath, gapPaths } = useMemo(() => {
    if (n === 0) return { actualPath: "", expectedPath: "", gapPaths: [] };
    const pts = arc.map((p) => ({
      px: x(p.g),
      ya: y(p.cumActual),
      ye: y(p.cumExpected),
      diff: p.cumActual - p.cumExpected,
    }));
    const actualPath = pts
      .map((p, i) => `${i === 0 ? "M" : "L"}${p.px.toFixed(1)} ${p.ya.toFixed(1)}`)
      .join("");
    const expectedPath = pts
      .map((p, i) => `${i === 0 ? "M" : "L"}${p.px.toFixed(1)} ${p.ye.toFixed(1)}`)
      .join("");

    // Split the band between the lines into sign-runs, with exact
    // crossing points so warm/cool areas tile without seams.
    const gapPaths: { d: string; warm: boolean }[] = [];
    let run: { px: number; ya: number; ye: number }[] = [pts[0]];
    let runSign = Math.sign(pts[0].diff);
    const flush = (sign: number) => {
      if (run.length < 2 || sign === 0) return;
      const top = run.map((p, i) => `${i === 0 ? "M" : "L"}${p.px.toFixed(1)} ${p.ya.toFixed(1)}`).join("");
      const back = [...run]
        .reverse()
        .map((p) => `L${p.px.toFixed(1)} ${p.ye.toFixed(1)}`)
        .join("");
      gapPaths.push({ d: `${top}${back}Z`, warm: sign > 0 });
    };
    for (let i = 1; i < pts.length; i++) {
      const p = pts[i];
      const s = Math.sign(p.diff);
      if (s !== runSign && runSign !== 0 && s !== 0) {
        const prev = pts[i - 1];
        const dPrev = prev.ya - prev.ye;
        const dCur = p.ya - p.ye;
        const t = dPrev / (dPrev - dCur);
        const cx = prev.px + t * (p.px - prev.px);
        const cy = prev.ya + t * (p.ya - prev.ya);
        run.push({ px: cx, ya: cy, ye: cy });
        flush(runSign);
        run = [{ px: cx, ya: cy, ye: cy }, p];
        runSign = s;
      } else {
        run.push(p);
        if (runSign === 0) runSign = s;
      }
    }
    flush(runSign);
    return { actualPath, expectedPath, gapPaths };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [arc, width, height]);

  if (n === 0) {
    return (
      <div className={`rounded border border-line-soft bg-wash px-4 py-8 text-center text-sm text-ink-faint ${className}`}>
        No per-game series available for this season.
      </div>
    );
  }

  const last = arc[n - 1];
  const finalDiff = last.cumActual - last.cumExpected;
  const yActualLabel = y(last.cumActual);
  const yExpectedLabel = y(last.cumExpected);
  const tooClose = Math.abs(yActualLabel - yExpectedLabel) < 30;
  const spread = tooClose ? (15 - Math.abs(yActualLabel - yExpectedLabel) / 2) : 0;
  const actualUp = yActualLabel <= yExpectedLabel;

  const hovered = hover !== null ? arc[hover] : null;
  const ticks = n > 20 ? [1, ...[20, 40, 60, 80].filter((t) => t < n), n] : [1, n];

  // Reveal: gap + expected sweep left-to-right under a clip; the actual
  // line draws via normalized dash; labels land last.
  const sweepStyle: React.CSSProperties = {
    clipPath: revealed ? "inset(-2% -2% -2% -2%)" : "inset(-2% 102% -2% -2%)",
    transition: "clip-path 1000ms var(--ease-out-strong)",
  };
  const labelStyle: React.CSSProperties = {
    opacity: revealed ? 1 : 0,
    transition: "opacity 420ms ease 700ms",
  };

  return (
    <div ref={wrapRef} className={`relative ${className}`}>
      {width > 0 && (
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={`Cumulative free throw attempts from shooting fouls versus league-average pace across ${n} games. Final: ${last.cumActual} actual, ${last.cumExpected.toFixed(0)} expected, gap ${signed(finalDiff, 1)}.`}
        >
          <g style={sweepStyle}>
            {gapPaths.map((p, i) => (
              <path key={i} d={p.d} fill={p.warm ? WARM_FILL : COOL_FILL} />
            ))}
            <path
              d={expectedPath}
              fill="none"
              stroke="var(--color-ink-faint)"
              strokeWidth={1.5}
              strokeDasharray="2 4"
              strokeLinecap="round"
            />
          </g>
          <path
            d={actualPath}
            fill="none"
            stroke="var(--color-ink)"
            strokeWidth={2.25}
            strokeLinejoin="round"
            strokeLinecap="round"
            pathLength={1}
            style={{
              strokeDasharray: 1,
              strokeDashoffset: revealed ? 0 : 1,
              transition: "stroke-dashoffset 1000ms var(--ease-out-strong)",
            }}
          />

          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={x(t)}
                x2={x(t)}
                y1={pad.top + innerH}
                y2={pad.top + innerH + 4}
                stroke="var(--color-line)"
              />
              <text
                x={x(t)}
                y={height - 8}
                textAnchor={t === 1 ? "start" : t === n ? "end" : "middle"}
                className="font-mono tnum"
                fontSize={10}
                fill="var(--color-ink-faint)"
              >
                {t === 1 ? "game 1" : t}
              </text>
            </g>
          ))}

          <g className="font-mono tnum" fontSize={11.5} textAnchor="start" style={labelStyle}>
            <text
              x={x(n) + 7}
              y={yActualLabel + (actualUp ? -spread : spread) + 4}
              fill="var(--color-ink)"
              fontWeight={600}
            >
              {last.cumActual} actual
            </text>
            <text
              x={x(n) + 7}
              y={yExpectedLabel + (actualUp ? spread : -spread) + 4}
              fill="var(--color-ink-faint)"
            >
              {last.cumExpected.toFixed(0)} expected
            </text>
            <text
              x={x(n) + 7}
              y={(yActualLabel + yExpectedLabel) / 2 + (tooClose ? 34 : 4) + 14}
              fill={divergingText(finalDiff)}
              fontWeight={700}
              fontSize={12.5}
            >
              {signed(finalDiff, 1)}
            </text>
          </g>

          {hovered && (
            <g pointerEvents="none">
              <line
                x1={x(hovered.g)}
                x2={x(hovered.g)}
                y1={pad.top}
                y2={pad.top + innerH}
                stroke="var(--color-ink-faint)"
                strokeWidth={1}
                strokeDasharray="3 3"
              />
              <circle cx={x(hovered.g)} cy={y(hovered.cumActual)} r={3.5} fill="var(--color-ink)" />
              <circle cx={x(hovered.g)} cy={y(hovered.cumExpected)} r={3} fill="var(--color-paper)" stroke="var(--color-ink-faint)" strokeWidth={1.5} />
            </g>
          )}

          {showTooltip && (
            <rect
              x={pad.left}
              y={pad.top}
              width={innerW}
              height={innerH}
              fill="transparent"
              onPointerMove={(e) => {
                const rect = e.currentTarget.getBoundingClientRect();
                const t = (e.clientX - rect.left) / Math.max(1, rect.width);
                const g = Math.round(t * (n - 1));
                setHover(Math.max(0, Math.min(n - 1, g)));
              }}
              onPointerLeave={() => setHover(null)}
            />
          )}
        </svg>
      )}

      {hovered && showTooltip && (
        <div
          className="pointer-events-none absolute z-10 rounded border border-line bg-paper px-2.5 py-1.5 font-mono text-[11px] leading-snug shadow-sm tnum"
          style={{
            left: Math.min(Math.max(x(hovered.g) - 60, 0), Math.max(0, width - 150)),
            top: Math.max(0, Math.min(y(hovered.cumActual), y(hovered.cumExpected)) - 64),
          }}
        >
          <div className="text-ink-faint">game {hovered.g}</div>
          <div className="text-ink">
            {hovered.cumActual} act · {hovered.cumExpected.toFixed(1)} exp
          </div>
          <div style={{ color: divergingText(hovered.cumActual - hovered.cumExpected) }}>
            {signed(hovered.cumActual - hovered.cumExpected, 1)}
          </div>
        </div>
      )}
    </div>
  );
}
