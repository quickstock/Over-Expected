import { Link, useParams, useSearchParams } from "react-router-dom";
import { useTitle } from "../lib/useTitle";
import { useData } from "../data";
import { divergingText } from "../lib/color";
import { int, ordinal, signed } from "../lib/format";
import { Delta } from "../components/Delta";
import SegmentedControl from "../components/SegmentedControl";
import GapArc from "../components/charts/GapArc";
import CourtZones from "../components/charts/CourtZones";

function NotFound({ qualify }: { qualify: number }) {
  return (
    <div className="mx-auto max-w-xl px-5 py-28 text-center sm:px-8">
      <p className="font-display text-2xl font-semibold text-ink">
        No qualified season for this player.
      </p>
      <p className="mt-3 text-sm leading-relaxed text-ink-soft">
        Player pages require at least {int(qualify)} possessions in a season —
        below that, per-possession rates are too unstable to present.
      </p>
      <Link
        to="/leaderboard"
        className="mt-8 inline-block rounded-md bg-ink px-5 py-2.5 font-display text-sm font-medium text-paper transition-opacity duration-150 hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        Back to the leaderboard
      </Link>
    </div>
  );
}

function Stat({
  value,
  label,
  sub,
}: {
  value: React.ReactNode;
  label: string;
  sub?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5 px-1 py-4 sm:py-1">
      <span className="font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
        {label}
      </span>
      <span className="font-mono tnum text-3xl text-ink sm:text-4xl">
        {value}
      </span>
      {sub && <span className="text-xs text-ink-soft">{sub}</span>}
    </div>
  );
}

export default function Player() {
  const data = useData();
  const { id } = useParams();
  const [params, setParams] = useSearchParams();

  const qualify = data.meta.qualifyPossessions;
  const player = id ? data.players[id] : undefined;
  if (!player) return <NotFound qualify={qualify} />;

  // Player's qualified seasons, in league season order.
  const seasons = data.meta.seasons.filter((s) => s in player.seasons);
  const requested = params.get("season");
  const season =
    requested && seasons.includes(requested)
      ? requested
      : seasons[seasons.length - 1];

  useTitle(`${player.name} \u00b7 FTAOE`);

  const row = data.leaderboard.find(
    (r) => r.id === Number(id) && r.season === season,
  );
  const detail = player.seasons[season];
  if (!row || !detail) return <NotFound qualify={qualify} />;

  const setSeason = (s: string) => {
    const next = new URLSearchParams(params);
    next.set("season", s);
    setParams(next);
  };

  return (
    <div className="mx-auto max-w-4xl px-5 py-10 sm:px-8 sm:py-14">
      <Link
        to={`/leaderboard?season=${encodeURIComponent(season)}`}
        className="font-display text-sm text-ink-soft transition-colors duration-150 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        ← Leaderboard
      </Link>

      <header className="mt-6">
        <h1 className="font-display text-4xl font-bold tracking-tight text-ink sm:text-6xl">
          {player.name}
        </h1>
        <p className="mt-3 text-sm text-ink-soft">
          {row.teams.join(" → ")}
          {row.pos ? ` · ${row.pos}` : ""} · {int(row.poss)} possessions
        </p>
        {seasons.length > 1 && (
          <SegmentedControl
            ariaLabel="Season"
            className="mt-5"
            options={seasons.map((s) => ({ value: s, label: s }))}
            value={season}
            onChange={setSeason}
          />
        )}
        {seasons.length === 1 && (
          <p className="mt-5 font-display text-[13px] font-medium text-ink-soft">
            {season}
          </p>
        )}
      </header>

      {/* stat band */}
      <section className="mt-10 grid grid-cols-2 divide-line border-y border-line py-2 max-sm:[&>*:nth-child(odd)]:border-r max-sm:[&>*:nth-child(-n+2)]:border-b sm:grid-cols-4 sm:divide-x sm:py-5">
        <Stat
          value={<Delta per100={row.per100} className="text-4xl sm:text-5xl" />}
          label="FTAOE per 100 poss"
        />
        <Stat
          value={
            row.pct !== null ? (
              <>
                {ordinal(Math.floor(row.pct))}
                <span className="text-xl text-ink-faint"> %ile</span>
              </>
            ) : (
              "—"
            )
          }
          label="Percentile"
          sub={`among qualified, ${season}`}
        />
        <Stat
          value={
            <>
              {int(row.fta)}
              <span className="text-xl text-ink-faint"> / {row.xfta.toFixed(1)}</span>
            </>
          }
          label="Actual / expected FTA"
        />
        <Stat
          value={
            <span style={{ color: divergingText(row.per100) }}>
              {signed(row.ftaoe, 1)}
            </span>
          }
          label="Extra FTA vs league"
        />
      </section>

      {/* the gap */}
      <section className="mt-14">
        <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
          The season, drawn as a gap
        </h2>
        <p className="mt-1.5 text-sm text-ink-soft">
          Cumulative shooting-foul free throws vs the league-average pace,
          game by game.
        </p>
        <GapArc games={detail.games} className="mt-6" />
      </section>

      {/* shot diet */}
      <section className="mt-14">
        <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
          Where he attacks
        </h2>
        <p className="mt-1.5 text-sm text-ink-soft">
          Charged field-goal attempts by zone, {season}.
        </p>
        <CourtZones zones={detail.zones} className="mt-6 max-w-[520px]" />
      </section>

      <p className="mt-16 border-t border-line pt-6">
        <Link
          to={`/leaderboard?season=${encodeURIComponent(season)}`}
          className="font-display text-sm font-medium text-ink underline underline-offset-4 transition-colors duration-150 hover:text-ink-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          See everyone →
        </Link>
      </p>
    </div>
  );
}
