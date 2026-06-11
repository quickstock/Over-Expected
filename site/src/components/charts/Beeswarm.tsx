import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { divergingColor, divergingText, warmText, coolText } from "../../lib/color";
import { signed, lastName } from "../../lib/format";
import { useMeasure } from "../../lib/useMeasure";

export interface SwarmPlayer {
  id: number;
  name: string;
  per100: number;
}

interface Props {
  players: SwarmPlayer[];
  season: string;
  /** Player ids to call out by name; top/bottom are added automatically. */
  highlightIds?: number[];
  height?: number;
  className?: string;
}

interface Dot extends SwarmPlayer {
  px: number;
  py: number;
}

/**
 * Every qualified player in one season, placed by FTAOE per 100.
 * Dots take the diverging encoding; names are labeled directly.
 */
export default function Beeswarm({
  players,
  season,
  highlightIds = [],
  height = 230,
  className = "",
}: Props) {
  const [wrapRef, width] = useMeasure<HTMLDivElement>();
  const [hover, setHover] = useState<Dot | null>(null);
  const navigate = useNavigate();

  const labelBand = 56;
  const pad = { top: labelBand, bottom: 30, left: 10, right: 10 };
  const innerW = Math.max(40, width - pad.left - pad.right);
  const r = width < 480 ? 2.7 : 3.4;

  const { dots, maxAbs } = useMemo(() => {
    if (!width || players.length === 0) return { dots: [] as Dot[], maxAbs: 1 };
    const maxAbs =
      Math.max(...players.map((p) => Math.abs(p.per100)), 0.1) * 1.06;
    const x = (v: number) => pad.left + ((v + maxAbs) / (2 * maxAbs)) * innerW;
    const midY = pad.top + (height - pad.top - pad.bottom) / 2;
    const sorted = [...players].sort((a, b) => a.per100 - b.per100);
    const placed: Dot[] = [];
    const gap = 2 * r + 0.7;
    for (const p of sorted) {
      const px = x(p.per100);
      const conflicts = placed.filter((q) => Math.abs(q.px - px) < gap);
      const candidates = [0];
      for (const q of conflicts) {
        const dy = Math.sqrt(Math.max(0, gap * gap - (q.px - px) ** 2));
        candidates.push(q.py - midY + dy, q.py - midY - dy);
      }
      candidates.sort((a, b) => Math.abs(a) - Math.abs(b));
      const maxOff = (height - pad.top - pad.bottom) / 2 - r;
      let off = 0;
      for (const c of candidates) {
        if (Math.abs(c) > maxOff) continue;
        const ok = conflicts.every(
          (q) => (q.px - px) ** 2 + (q.py - (midY + c)) ** 2 >= gap * gap - 0.01,
        );
        if (ok) {
          off = c;
          break;
        }
      }
      placed.push({ ...p, px, py: midY + off });
    }
    return { dots: placed, maxAbs };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [players, width, height]);

  const callouts = useMemo(() => {
    if (dots.length === 0) return [];
    const bySigned = [...dots].sort((a, b) => b.per100 - a.per100);
    const nTop = width < 480 ? 2 : 3;
    const nBot = width < 480 ? 1 : 2;
    const picked = new Map<number, Dot>();
    for (const d of bySigned.slice(0, nTop)) picked.set(d.id, d);
    for (const d of bySigned.slice(-nBot)) picked.set(d.id, d);
    for (const id of highlightIds) {
      const d = dots.find((q) => q.id === id);
      if (d) picked.set(d.id, d);
    }
    // Space labels along x without overlap: forward pass pushes right,
    // then a backward pass pulls everything inside the right edge.
    const out = [...picked.values()].sort((a, b) => a.px - b.px);
    const w = (d: Dot) => lastName(d.name).length * 7 + 10;
    const lx = out.map((d) => d.px);
    for (let i = 1; i < out.length; i++) {
      const gap = w(out[i - 1]) / 2 + w(out[i]) / 2 + 6;
      lx[i] = Math.max(lx[i], lx[i - 1] + gap);
    }
    const maxX = width - w(out[out.length - 1]) / 2;
    lx[out.length - 1] = Math.min(lx[out.length - 1], maxX);
    for (let i = out.length - 2; i >= 0; i--) {
      const gap = w(out[i]) / 2 + w(out[i + 1]) / 2 + 6;
      lx[i] = Math.min(lx[i], lx[i + 1] - gap);
    }
    for (let i = 0; i < out.length; i++) {
      const gap = i === 0 ? 0 : w(out[i - 1]) / 2 + w(out[i]) / 2 + 6;
      lx[i] = Math.max(lx[i], i === 0 ? w(out[0]) / 2 : lx[i - 1] + gap);
    }
    return out.map((d, i) => ({ ...d, lx: lx[i] }));
  }, [dots, highlightIds, width]);

  const x0 = width
    ? pad.left + (maxAbs / (2 * maxAbs)) * innerW
    : 0;

  if (players.length === 0) return null;

  return (
    <div ref={wrapRef} className={`relative ${className}`}>
      {width > 0 && (
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={`Distribution of FTAOE per 100 possessions for ${players.length} qualified players in ${season}.`}
        >
          {/* league-average axis */}
          <line
            x1={x0}
            x2={x0}
            y1={labelBand - 12}
            y2={height - pad.bottom + 6}
            stroke="var(--color-line)"
            strokeWidth={1}
          />
          <text
            x={x0}
            y={height - 9}
            textAnchor="middle"
            fontSize={10.5}
            fill="var(--color-ink-faint)"
            className="font-mono"
          >
            league average
          </text>
          <text
            x={width - pad.right}
            y={height - 9}
            textAnchor="end"
            fontSize={10.5}
            fill={warmText}
            className="font-mono"
          >
            draws more →
          </text>
          <text
            x={pad.left}
            y={height - 9}
            textAnchor="start"
            fontSize={10.5}
            fill={coolText}
            className="font-mono"
          >
            ← fewer
          </text>

          {dots.map((d) => (
            <circle
              key={d.id}
              cx={d.px}
              cy={d.py}
              r={hover?.id === d.id ? r + 1.5 : r}
              fill={divergingColor(d.per100)}
              stroke={hover?.id === d.id ? "var(--color-ink)" : "none"}
              strokeWidth={1}
              className="cursor-pointer transition-[r] duration-100"
              onPointerEnter={() => setHover(d)}
              onPointerLeave={() => setHover(null)}
              onClick={() =>
                navigate(`/player/${d.id}?season=${encodeURIComponent(season)}`)
              }
            />
          ))}

          {/* direct name labels with leader lines */}
          {callouts.map((c) => (
            <g
              key={`label-${c.id}`}
              className="cursor-pointer"
              role="link"
              tabIndex={0}
              aria-label={`${c.name}, ${signed(c.per100, 1)} per 100`}
              onClick={() =>
                navigate(`/player/${c.id}?season=${encodeURIComponent(season)}`)
              }
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  navigate(`/player/${c.id}?season=${encodeURIComponent(season)}`);
                }
              }}
            >
              <line
                x1={c.px}
                x2={c.lx}
                y1={c.py - r - 2}
                y2={32}
                stroke="var(--color-line)"
                strokeWidth={1}
              />
              <text
                x={c.lx}
                y={13}
                textAnchor="middle"
                fontSize={11.5}
                fontWeight={600}
                fill="var(--color-ink)"
                className="font-display"
              >
                {lastName(c.name)}
              </text>
              <text
                x={c.lx}
                y={27}
                textAnchor="middle"
                fontSize={10.5}
                fill={divergingText(c.per100)}
                className="font-mono tnum"
              >
                {signed(c.per100, 1)}
              </text>
            </g>
          ))}
        </svg>
      )}

      {hover && (
        <div
          className="pointer-events-none absolute z-10 whitespace-nowrap rounded border border-line bg-paper px-2.5 py-1.5 text-[11px] leading-snug shadow-sm"
          style={{
            left: Math.min(Math.max(hover.px - 50, 0), Math.max(0, width - 130)),
            top: hover.py - 52,
          }}
        >
          <div className="font-display font-semibold text-ink">{hover.name}</div>
          <div className="font-mono tnum" style={{ color: divergingText(hover.per100) }}>
            {signed(hover.per100, 1)} per 100
          </div>
        </div>
      )}
    </div>
  );
}
