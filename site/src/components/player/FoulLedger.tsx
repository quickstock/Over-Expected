import type { FoulBreakdown } from "../../types";
import { int } from "../../lib/format";

/**
 * Every shooting-foul free throw, reconciled: and-1s contribute one FT,
 * fouled 2-pt misses two, fouled 3-pt misses three. The total equals the
 * season's actual FTA exactly. Neutral ink throughout: these are counts,
 * not FTAOE, so the diverging encoding stays out.
 */

/**
 * "47 × 2 FT" when the FT count divides evenly; otherwise an approximate
 * trip count with no multiplication shown (the FTA column stays exact).
 */
function tripsCell(fts: number, per: number): React.ReactNode {
  if (fts === 0) return "0";
  if (fts % per === 0) {
    return (
      <>
        {int(fts / per)} <span className="text-ink-faint">× {per} FT</span>
      </>
    );
  }
  return (
    <>
      ≈{int(Math.round(fts / per))} <span className="text-ink-faint">trips</span>
    </>
  );
}

interface RowProps {
  label: string;
  note?: string;
  per: number;
  fta: number;
  delay: number;
}

function Row({ label, note, per, fta, delay }: RowProps) {
  return (
    <tr
      className="translate-y-0 border-b border-line-soft opacity-100 transition-[opacity,transform] duration-500 starting:translate-y-1.5 starting:opacity-0"
      style={{ transitionDelay: `${delay}ms` }}
    >
      <td className="py-2.5 pr-3 text-[15px] text-ink">
        {label}
        {note && (
          <span className="block text-xs text-ink-faint sm:ml-1.5 sm:inline">
            {note}
          </span>
        )}
      </td>
      <td className="font-mono tnum whitespace-nowrap py-2.5 pr-3 text-right text-sm text-ink-soft">
        {tripsCell(fta, per)}
      </td>
      <td className="font-mono tnum py-2.5 text-right text-base text-ink">
        {int(fta)}
      </td>
    </tr>
  );
}

export default function FoulLedger({
  fouls,
  fta,
  className = "",
}: {
  fouls: FoulBreakdown;
  /** Season actual FTA from the leaderboard; the table must sum to it. */
  fta: number;
  className?: string;
}) {
  const total = fouls.and1 + fouls.sf2 + fouls.sf3;
  return (
    <div className={className}>
      <table className="w-full max-w-xl border-collapse">
        <thead>
          <tr className="border-b border-line">
            <th className="py-2 pr-3 text-left font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
              Foul type
            </th>
            <th className="py-2 pr-3 text-right font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
              Trips
            </th>
            <th className="py-2 text-right font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
              FTA
            </th>
          </tr>
        </thead>
        <tbody>
          <Row
            label="And-1s"
            note="made shot, placed on the court"
            per={1}
            fta={fouls.and1}
            delay={0}
          />
          <Row
            label="Fouled 2-pt attempts"
            note="no location recorded"
            per={2}
            fta={fouls.sf2}
            delay={50}
          />
          <Row
            label="Fouled 3-pt attempts"
            note="no location recorded"
            per={3}
            fta={fouls.sf3}
            delay={100}
          />
        </tbody>
        <tfoot>
          <tr
            className="translate-y-0 opacity-100 transition-[opacity,transform] duration-500 starting:translate-y-1.5 starting:opacity-0"
            style={{ transitionDelay: "150ms" }}
          >
            <td className="py-3 pr-3 font-display text-[15px] font-semibold text-ink">
              Shooting-foul free throws
            </td>
            <td />
            <td className="font-mono tnum py-3 text-right text-lg font-medium text-ink">
              {int(total)}
            </td>
          </tr>
        </tfoot>
      </table>
      {total !== fta && (
        <p className="mt-1 text-xs text-ink-faint">
          Note: itemization covers {int(total)} of {int(fta)} free throws for
          this season.
        </p>
      )}
    </div>
  );
}
