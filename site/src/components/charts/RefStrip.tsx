import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { int, signed } from "../../lib/format";
import { useMeasure } from "../../lib/useMeasure";

/**
 * Officials as a neutral strip: x = shooting-foul FTA per 100 in their
 * games minus the season league rate. Descriptive league-level fact;
 * deliberately NOT the diverging encoding (these are not player FTAOE
 * values) and deliberately not crossed with players.
 */
export default function RefStrip({
  refs,
  height = 190,
}: {
  refs: { id: number; name: string; games: number; per100: number; diff: number }[];
  height?: number;
}) {
  const navigate = useNavigate();
  const [wrapRef, width] = useMeasure<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);

  const pad = { top: 44, bottom: 30, left: 12, right: 12 };
  const innerW = Math.max(40, width - pad.left - pad.right);
  const midY = pad.top + (height - pad.top - pad.bottom) / 2;
  const maxAbs = Math.max(1, ...refs.map((r) => Math.abs(r.diff))) * 1.12;
  const x = (v: number) => pad.left + ((v + maxAbs) / (2 * maxAbs)) * innerW;

  const dots = useMemo(() => {
    const r = 4;
    const gap = 2 * r + 1;
    const placed: { px: number; py: number; i: number }[] = [];
    refs
      .map((d, i) => ({ d, i }))
      .sort((a, b) => a.d.diff - b.d.diff)
      .forEach(({ d, i }) => {
        const px = x(d.diff);
        const conflicts = placed.filter((q) => Math.abs(q.px - px) < gap);
        const cands = [0];
        for (const q of conflicts) {
          const dy = Math.sqrt(Math.max(0, gap * gap - (q.px - px) ** 2));
          cands.push(q.py - midY + dy, q.py - midY - dy);
        }
        cands.sort((a, b) => Math.abs(a) - Math.abs(b));
        let off = 0;
        for (const c of cands) {
          if (
            conflicts.every(
              (q) => (q.px - px) ** 2 + (q.py - (midY + c)) ** 2 >= gap * gap - 0.01,
            )
          ) {
            off = c;
            break;
          }
        }
        placed.push({ px, py: midY + off, i });
      });
    return placed;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refs, width]);

  const extremes = useMemo(() => {
    const sorted = [...refs].sort((a, b) => b.diff - a.diff);
    return new Set(
      [...sorted.slice(0, 2), ...sorted.slice(-2)].map((r) => r.name),
    );
  }, [refs]);

  const hovered = hover !== null ? refs[hover] : null;
  const hoveredDot = hover !== null ? dots.find((d) => d.i === hover) : null;

  return (
    <div ref={wrapRef} className="relative">
      {width > 0 && (
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={`${refs.length} officials by shooting-foul rate in their games vs the season league rate.`}
        >
          <line
            x1={x(0)}
            x2={x(0)}
            y1={pad.top - 14}
            y2={height - pad.bottom + 6}
            stroke="var(--color-line)"
          />
          <text
            x={x(0)}
            y={height - 9}
            textAnchor="middle"
            fontSize={10.5}
            className="font-mono"
            fill="var(--color-ink-faint)"
          >
            league rate
          </text>
          <text
            x={pad.left}
            y={height - 9}
            textAnchor="start"
            fontSize={10.5}
            className="font-mono"
            fill="var(--color-ink-faint)"
          >
            ← fewer FTs in their games
          </text>
          <text
            x={width - pad.right}
            y={height - 9}
            textAnchor="end"
            fontSize={10.5}
            className="font-mono"
            fill="var(--color-ink-faint)"
          >
            more →
          </text>
          {dots.map(({ px, py, i }) => (
            <circle
              key={i}
              cx={px}
              cy={py}
              r={hover === i ? 5.5 : 4}
              fill={
                hover === i ? "var(--color-ink)" : "oklch(0.45 0.008 270 / 0.55)"
              }
              className="cursor-pointer"
              style={{ transition: "r 120ms ease" }}
              onPointerEnter={() => setHover(i)}
              onPointerLeave={() => setHover(null)}
              onClick={() => navigate(`/referee/${refs[i].id}`)}
            >
              <title>{`${refs[i].name}: open profile`}</title>
            </circle>
          ))}
          {dots
            .filter(({ i }) => extremes.has(refs[i].name))
            .map(({ px, py, i }) => (
              <text
                key={`l${i}`}
                x={px}
                y={py - 10}
                textAnchor="middle"
                fontSize={10.5}
                fontWeight={600}
                className="font-display"
                fill="var(--color-ink-soft)"
              >
                {refs[i].name.split(" ").slice(-1)[0]}
              </text>
            ))}
        </svg>
      )}
      {hovered && hoveredDot && (
        <div
          className="pointer-events-none absolute z-10 whitespace-nowrap rounded border border-line bg-paper px-2.5 py-1.5 text-[11px] leading-snug shadow-sm"
          style={{
            left: Math.min(Math.max(hoveredDot.px - 70, 0), Math.max(0, width - 180)),
            top: hoveredDot.py - 58,
          }}
        >
          <div className="font-display font-semibold text-ink">{hovered.name}</div>
          <div className="font-mono tnum text-ink-soft">
            {signed(hovered.diff, 1)} vs league · {int(hovered.games)} games
          </div>
        </div>
      )}
    </div>
  );
}
