import type { ReactNode } from "react";
import { divergingColor, divergingText } from "../../lib/color";
import { ordinal, signed } from "../../lib/format";

/**
 * Savant-style percentile bars. Position encodes rank within the
 * season's qualified pool; the dot's color encodes the VALUE through
 * the diverging FTAOE scale (not the percentile), so the color always
 * agrees with the signed number next to it.
 */

export interface SliderRow {
  label: string;
  per100: number;
  pct: number | null;
  note?: ReactNode;
}

function Row({ label, per100, pct, note }: SliderRow) {
  if (pct === null) return null;
  const p = Math.max(0, Math.min(100, pct));
  const fill: React.CSSProperties =
    p >= 50
      ? { left: "50%", width: `${p - 50}%` }
      : { left: `${p}%`, width: `${50 - p}%` };
  return (
    <div className="py-3.5">
      <div className="grid grid-cols-[7.5rem_minmax(0,1fr)_4.5rem] items-center gap-x-4 sm:grid-cols-[10rem_minmax(0,1fr)_5rem]">
        <span className="font-display text-[13px] font-medium leading-tight text-ink">
          {label}
        </span>
        <div
          className="relative h-2 rounded-full bg-wash"
          role="img"
          aria-label={`${label}: ${ordinal(Math.floor(p))} percentile, ${signed(per100, 1)} per 100`}
        >
          {/* fill from the median to the rank */}
          <span
            className="absolute top-0 h-full rounded-full transition-[width,left] duration-700 starting:w-0 starting:left-1/2"
            style={{
              ...fill,
              background: divergingColor(per100),
              opacity: 0.25,
              transitionTimingFunction: "var(--ease-out-strong)",
            }}
          />
          {/* median tick */}
          <span className="absolute left-1/2 top-1/2 h-3.5 w-px -translate-y-1/2 bg-line" />
          {/* rank dot, slides to position on mount */}
          <span
            className="absolute top-1/2 grid h-6 w-6 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full ring-2 ring-paper transition-[left] duration-700 starting:left-1/2"
            style={{
              left: `${p}%`,
              background: divergingColor(per100),
              transitionTimingFunction: "var(--ease-out-strong)",
            }}
          >
            <span className="font-mono tnum text-[10px] font-semibold leading-none text-paper">
              {Math.floor(p)}
            </span>
          </span>
        </div>
        <span
          className="font-mono tnum text-right text-base"
          style={{ color: divergingText(per100) }}
        >
          {signed(per100, 1)}
        </span>
      </div>
      {note && (
        <p className="mt-2 text-xs leading-relaxed text-ink-faint sm:grid sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-x-4"><span className="hidden sm:block" /><span>{note}</span>
        </p>
      )}
    </div>
  );
}

export default function PercentileSliders({
  rows,
  className = "",
}: {
  rows: SliderRow[];
  className?: string;
}) {
  const visible = rows.filter((r) => r.pct !== null);
  if (visible.length === 0) return null;
  return (
    <div className={`divide-y divide-line-soft ${className}`}>
      {visible.map((r) => (
        <Row key={r.label} {...r} />
      ))}
    </div>
  );
}
