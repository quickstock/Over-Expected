import { Link } from "react-router-dom";
import { useData } from "../data";
import { int } from "../lib/format";
import { useTitle } from "../lib/useTitle";

function FileRow({
  href,
  name,
  desc,
}: {
  href: string;
  name: string;
  desc: string;
}) {
  return (
    <li className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b border-line-soft py-3">
      <a
        href={href}
        download
        className="font-mono text-sm text-ink underline underline-offset-2 transition-colors duration-150 hover:text-ink-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        {name}
      </a>
      <span className="text-sm text-ink-soft">{desc}</span>
    </li>
  );
}

export default function OpenData() {
  const data = useData();
  useTitle("Data · FTAOE");
  const { meta } = data;
  const base = import.meta.env.BASE_URL;

  return (
    <article className="mx-auto max-w-2xl px-5 py-12 sm:px-8 sm:py-16">
      <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-5xl">
        The data
      </h1>
      <p className="mt-4 text-base leading-relaxed text-ink-soft sm:text-lg">
        Everything this site shows ships as static JSON, and you're welcome
        to use it: {int(data.leaderboard.length)} player-season rows across{" "}
        {int(meta.seasons.length)} seasons, built from{" "}
        {int(meta.nPossessions)} possessions of public play-by-play.
      </p>

      <h2 className="mt-12 font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
        Files
      </h2>
      <ul className="mt-4">
        <FileRow
          href={`${base}data.json`}
          name="data.json"
          desc="leaderboard, league distributions, calibration, meta"
        />
        {meta.seasons.map((s) => (
          <FileRow
            key={s}
            href={`${base}players-${s}.json`}
            name={`players-${s}.json`}
            desc={`per-game series, shot zones, foul ledger (${s})`}
          />
        ))}
      </ul>

      <h2 className="mt-12 font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
        Schema, in brief
      </h2>
      <div className="mt-4 space-y-4 text-[15px] leading-relaxed sm:text-base">
        <p>
          Leaderboard rows carry{" "}
          <span className="font-mono text-sm">
            id, name, season, teams, pos, poss, fta, xfta, ftaoe, per100,
            pct, sper100, spct
          </span>
          . Per-season player files map player id to{" "}
          <span className="font-mono text-sm">games</span> (per game:
          [actual FTA, expected, possessions], schedule order),{" "}
          <span className="font-mono text-sm">zones</span> (charged-FGA
          shot zones), and <span className="font-mono text-sm">fouls</span>{" "}
          (and-1 / fouled 2-pt / fouled 3-pt free-throw counts, plus located
          and-1 zones). Definitions and caveats live in the{" "}
          <Link
            to="/methodology"
            className="underline underline-offset-2 transition-colors duration-150 hover:text-ink-soft"
          >
            methodology
          </Link>
          .
        </p>
        <p>
          If you publish something built on this, credit "FTAOE" with a link
          back, and keep the framing descriptive: the number blends
          playstyle, contact-seeking skill, and officiating, and it does not
          prove referee bias. Underlying play-by-play and tracking
          aggregates are NBA.com data.
        </p>
      </div>
    </article>
  );
}
