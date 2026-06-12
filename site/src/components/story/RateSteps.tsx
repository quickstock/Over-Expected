import { useEffect, useRef, useState } from "react";
import { useMeasure } from "../../lib/useMeasure";

/**
 * League shooting-foul rate by season (per 100 possessions). Neutral
 * ink: these are league levels, not FTAOE values, so the diverging
 * encoding stays out. The annotated season gets the emphasis.
 */
export default function RateSteps({
  rates,
  annotate,
  annotation,
  height = 230,
  className = "",
}: {
  rates: Record<string, number>;
  annotate: string;
  annotation: string;
  height?: number;
  className?: string;
}) {
  const [wrapRef, width] = useMeasure<HTMLDivElement>();
  const [revealed, setRevealed] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!wrapRef.current) return;
    const io = new IntersectionObserver(
      (es) => {
        if (es[0].isIntersecting) {
          setRevealed(true);
          io.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    io.observe(wrapRef.current);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const seasons = Object.keys(rates);
  const values = Object.values(rates);
  const pad = { top: 34, bottom: 28, left: 22, right: 26 };
  const innerW = Math.max(40, width - pad.left - pad.right);
  const innerH = height - pad.top - pad.bottom;
  const lo = Math.min(...values) - 0.5;
  const hi = Math.max(...values) + 0.5;
  const x = (i: number) => pad.left + (i / (seasons.length - 1)) * innerW;
  const y = (v: number) => pad.top + innerH - ((v - lo) / (hi - lo)) * innerH;

  return (
    <div ref={wrapRef} className={`relative ${className}`}>
      <div ref={ref} />
      {width > 0 && (
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={`League shooting-foul FTA per 100 possessions by season: ${seasons
            .map((s) => `${s} ${rates[s].toFixed(1)}`)
            .join(", ")}.`}
        >
          <g
            style={{
              clipPath: revealed
                ? "inset(-2% -2% -2% -2%)"
                : "inset(-2% 102% -2% -2%)",
              transition: "clip-path 900ms var(--ease-out-strong)",
            }}
          >
            <path
              d={seasons
                .map(
                  (s, i) =>
                    `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${y(rates[s]).toFixed(1)}`,
                )
                .join("")}
              fill="none"
              stroke="var(--color-ink-faint)"
              strokeWidth={1.5}
            />
            {seasons.map((s, i) => {
              const focus = s === annotate;
              return (
                <g key={s}>
                  <circle
                    cx={x(i)}
                    cy={y(rates[s])}
                    r={focus ? 5.5 : 4}
                    fill={focus ? "var(--color-ink)" : "var(--color-paper)"}
                    stroke="var(--color-ink)"
                    strokeWidth={1.5}
                  />
                  <text
                    x={x(i)}
                    y={y(rates[s]) - 12}
                    textAnchor="middle"
                    fontSize={11.5}
                    fontWeight={focus ? 700 : 400}
                    className="font-mono tnum"
                    fill={focus ? "var(--color-ink)" : "var(--color-ink-soft)"}
                  >
                    {rates[s].toFixed(1)}
                  </text>
                  <text
                    x={x(i)}
                    y={height - 8}
                    textAnchor="middle"
                    fontSize={10.5}
                    className="font-mono"
                    fill={focus ? "var(--color-ink)" : "var(--color-ink-faint)"}
                  >
                    '{s.slice(2, 4)}-{s.slice(5)}
                  </text>
                </g>
              );
            })}
          </g>
          <text
            x={x(seasons.indexOf(annotate))}
            y={pad.top - 18}
            textAnchor="middle"
            fontSize={11.5}
            className="font-serif"
            fill="var(--color-ink-soft)"
            style={{
              opacity: revealed ? 1 : 0,
              transition: "opacity 400ms ease 650ms",
            }}
          >
            {annotation}
          </text>
        </svg>
      )}
    </div>
  );
}
