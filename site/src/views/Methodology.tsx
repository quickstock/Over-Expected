import { useData } from "../data";
import type { CalibrationBin } from "../types";
import { int } from "../lib/format";
import { useMeasure } from "../lib/useMeasure";
import { useTitle } from "../lib/useTitle";

/**
 * Calibration of the possession model: predicted vs actual shooting-foul
 * FTA rate per decile bin. Neutral ink only — this chart is not FTAOE,
 * so the diverging encoding stays out of it.
 */
function CalibrationChart({ bins }: { bins: CalibrationBin[] }) {
  const [wrapRef, width] = useMeasure<HTMLDivElement>();
  const size = Math.min(width, 420);
  const pad = { top: 16, right: 16, bottom: 44, left: 44 };

  const values = bins.flatMap((b) => [b.pred, b.actual]);
  const lo = Math.min(...values) - 0.004;
  const hi = Math.max(...values) + 0.004;
  const inner = size - pad.left - pad.top;
  const innerH = size - pad.top - pad.bottom;
  const x = (v: number) => pad.left + ((v - lo) / (hi - lo)) * (size - pad.left - pad.right);
  const y = (v: number) => pad.top + innerH - ((v - lo) / (hi - lo)) * innerH;

  // per-100 tick values inside the domain
  const ticks = [0.15, 0.17, 0.19, 0.21].filter((t) => t >= lo && t <= hi);

  return (
    <div ref={wrapRef} className="max-w-[420px]">
      {width > 0 && inner > 0 && (
        <svg
          width={size}
          height={size}
          role="img"
          aria-label="Calibration: predicted vs actual shooting-foul free throw rate per decile bin. Bins sit close to the diagonal."
        >
          {/* y = x reference */}
          <line
            x1={x(lo)}
            y1={y(lo)}
            x2={x(hi)}
            y2={y(hi)}
            stroke="var(--color-line)"
            strokeWidth={1}
            strokeDasharray="3 4"
          />
          <text
            x={x(hi) - 4}
            y={y(hi) + 12}
            textAnchor="end"
            fontSize={10.5}
            fill="var(--color-ink-faint)"
            className="font-mono"
          >
            perfect calibration
          </text>

          {ticks.map((t) => (
            <g key={t} className="font-mono tnum" fontSize={10.5}>
              <line
                x1={x(t)}
                x2={x(t)}
                y1={pad.top + innerH}
                y2={pad.top + innerH + 4}
                stroke="var(--color-line)"
              />
              <text
                x={x(t)}
                y={pad.top + innerH + 17}
                textAnchor="middle"
                fill="var(--color-ink-faint)"
              >
                {(t * 100).toFixed(0)}
              </text>
              <line
                x1={pad.left - 4}
                x2={pad.left}
                y1={y(t)}
                y2={y(t)}
                stroke="var(--color-line)"
              />
              <text
                x={pad.left - 8}
                y={y(t) + 3.5}
                textAnchor="end"
                fill="var(--color-ink-faint)"
              >
                {(t * 100).toFixed(0)}
              </text>
            </g>
          ))}

          <text
            x={pad.left + (size - pad.left - pad.right) / 2}
            y={size - 6}
            textAnchor="middle"
            fontSize={11}
            fill="var(--color-ink-soft)"
            className="font-mono"
          >
            predicted FTA per 100 poss
          </text>
          <text
            x={12}
            y={pad.top + innerH / 2}
            textAnchor="middle"
            fontSize={11}
            fill="var(--color-ink-soft)"
            className="font-mono"
            transform={`rotate(-90 12 ${pad.top + innerH / 2})`}
          >
            actual
          </text>

          {bins.map((b, i) => (
            <circle
              key={i}
              cx={x(b.pred)}
              cy={y(b.actual)}
              r={4}
              fill="var(--color-ink)"
            >
              <title>{`decile ${i + 1}: predicted ${(b.pred * 100).toFixed(1)}, actual ${(b.actual * 100).toFixed(1)} per 100 (${int(b.n)} possessions)`}</title>
            </circle>
          ))}
        </svg>
      )}
    </div>
  );
}

function H2({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mt-14 font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
      {children}
    </h2>
  );
}

export default function Methodology() {
  const data = useData();
  useTitle("Methodology \u00b7 FTAOE");
  const { meta, calibration } = data;
  const seasons = meta.seasons;

  const calLo = calibration[0];
  const calHi = calibration[calibration.length - 1];
  const spreadPer100 = ((calHi.pred - calLo.pred) * 100).toFixed(1);

  return (
    <article className="mx-auto max-w-2xl px-5 py-12 sm:px-8 sm:py-16">
      <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-5xl">
        Methodology
      </h1>
      <p className="mt-4 text-base leading-relaxed text-ink-soft sm:text-lg">
        FTAOE, free throw attempts over expected, is how many shooting-foul
        free throws a player draws per 100 possessions, compared with the
        league-average rate. FTAOE = actual FTA − expected FTA; the per-100
        version divides by the possessions a player finished.
      </p>

      <H2>What counts as a shooting foul</H2>
      <div className="mt-4 space-y-4 text-[15px] leading-relaxed sm:text-base">
        <p>
          Only free throws from shooting fouls count: and-1s and fouled misses
          (two or three attempts). Free throws from the bonus on non-shooting
          fouls, technicals, and flagrants are excluded, as are off-ball
          fouls. Attempts are attributed to the player who finished the
          possession: the one fouled in the act of shooting.
        </p>
        <p>
          The data is possession-level play-by-play:{" "}
          <span className="font-mono tnum">{int(meta.nPossessions)}</span>{" "}
          possessions across {int(seasons.length)} seasons, {seasons[0]} to{" "}
          {seasons[seasons.length - 1]}. Each possession's target is the
          number of shooting-foul free throws it produced (almost always 0,
          occasionally 2 or 3).
        </p>
      </div>

      <H2>Why per possession</H2>
      <div className="mt-4 space-y-4 text-[15px] leading-relaxed sm:text-base">
        <p>
          A fouled miss is not a charged field-goal attempt and has no shot
          location in the play-by-play. Any per-shot rate therefore silently
          drops the exact events this stat is made of, and punishes the
          players who draw the most fouls. Possessions don't have that
          problem: every trip ends somewhere, fouled or not. So the rate is
          per possession, and the leaderboard's unit is FTAOE per 100
          possessions.
        </p>
      </div>

      <H2>The baseline</H2>
      <div className="mt-4 space-y-4 text-[15px] leading-relaxed sm:text-base">
        <p>
          Expected FTA is the league-average shooting-foul rate times the
          possessions a player finished, season by season:{" "}
          {seasons.map((sn, i) => (
            <span key={sn}>
              <span className="font-mono tnum">
                {meta.leagueRateBySeason[sn].toFixed(1)}
              </span>{" "}
              in {sn}
              {i < seasons.length - 1 ? ", " : "."}
            </span>
          ))}
        </p>
        <p>
          On top of that rate we fit a context model: a Poisson GLM (log
          link, no interactions) on seven features that are all external to
          the player. Four describe game state (period, seconds remaining in
          the period, score margin, a late-game bonus proxy) and three
          describe the situation: whether the offense is at home, the
          opponent's shooting-foul rate, and the assigned officiating crew's
          foul rate. The opponent and crew rates are season-specific and
          leave-one-game-out, so a game's own outcomes never enter its own
          features. Validation is season cross-fitting (train on five
          seasons, predict the held-out sixth), so every prediction is
          out-of-fold. Earlier versions included shot location and
          play-resolution features and looked far stronger; that strength was
          leakage (the features encoded how the possession ended), and they
          were removed.
        </p>
        <p>
          Expected is then anchored to each season's own league rate: the
          held-out season's predictions are scaled so their mean equals that
          season's actual rate. Without this, rule changes move everyone's
          number: when the 2021-22 enforcement change on non-basketball moves
          cut league foul rates, a model trained on other seasons would
          over-expect free throws for every 2021-22 player. Anchoring keeps
          FTAOE a within-season comparison, which is what it claims to be.
        </p>
        <p className="border-l-2 border-line pl-4 text-ink">
          The honest punchline: out-of-fold, the full context model (game
          state, home court, opponent, officiating crew) reduces Poisson
          deviance by just{" "}
          <span className="font-mono tnum">{meta.modelLiftPct.toFixed(2)}%</span>{" "}
          against each season's own league-average rate. We adjusted for who
          you played, where, and who officiated, and it still barely moves.
          FTAOE is, in practice, "versus league average", and the site
          presents it that way.
        </p>
        <table className="mt-2 w-full max-w-sm border-collapse text-sm">
          <thead>
            <tr className="border-b border-line text-left">
              <th className="py-2 pr-4 font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
                Held-out season
              </th>
              <th className="py-2 font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
                Deviance reduction
              </th>
            </tr>
          </thead>
          <tbody>
            {meta.foldLifts.map((f) => (
              <tr key={f.season} className="border-b border-line-soft">
                <td className="py-2 pr-4 font-mono tnum">{f.season}</td>
                <td className="py-2 font-mono tnum">{f.liftPct.toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <H2>Calibration</H2>
      <div className="mt-4 space-y-4 text-[15px] leading-relaxed sm:text-base">
        <p>
          Possessions binned into deciles by predicted rate, predicted vs
          actual:
        </p>
        <CalibrationChart bins={calibration} />
        <p>
          Each dot is roughly{" "}
          <span className="font-mono tnum">{int(calibration[0].n)}</span>{" "}
          possessions. The bins sit near the diagonal (the model isn't
          systematically over- or under-calling fouls), but look at the
          x-axis: from the lowest to the highest decile it separates
          possessions by only about{" "}
          <span className="font-mono tnum">{spreadPer100}</span> free throws
          per 100. There is almost nothing to discriminate. That is the
          calibration picture of a baseline, which is what this model
          effectively is.
        </p>
      </div>

      <H2>Style-adjusted FTAOE</H2>
      <div className="mt-4 space-y-4 text-[15px] leading-relaxed sm:text-base">
        <p>
          Player pages also show a second, labeled number that answers a
          different question: how many shooting-foul free throws does a
          player draw above what his attack profile predicts? The baseline
          is a player-season Poisson model whose only inputs are exposure
          counts from NBA tracking data: drives, paint touches, and post
          touches per 100 possessions. It is fit the same leak-free way
          (train on five seasons, predict the sixth, anchor to the season),
          and the player's own free-throw outcomes on those plays are never
          features.
        </p>
        <p>
          Attack profile alone explains most foul-drawing volume (predicted
          and actual FTA correlate around 0.85 season over season). The
          residual separates two archetypes the headline number mixes: the
          high-volume interior player whose big FTAOE comes with enormous
          paint volume, and the per-exposure specialist who converts each
          drive or touch into free throws at an unusual rate. Neither
          reading is more correct; they answer different questions, which is
          why both numbers are shown and labeled.
        </p>
      </div>

      <H2>What this number is not</H2>
      <div className="mt-4 space-y-4 text-[15px] leading-relaxed sm:text-base">
        <p>
          FTAOE is descriptive. A high number blends playstyle (rim pressure,
          post touches, late-clock creation), contact-seeking skill, and
          officiating, and this method cannot separate those three. In
          particular, it does not isolate and does not prove referee bias, in
          either direction, for any player. That question stays open.
        </p>
        <p>
          The model cannot see who was defending. Per-possession defender
          identity and position exist only in the league's internal tracking
          stack; public matchup data is aggregated and cannot be joined to
          possessions, and a fouled miss has no shot event to attach a
          defender to. That is a real ceiling on how sophisticated a public,
          leak-free baseline can get.
        </p>
        <p>
          On referees: the officiating crew's overall foul tendency is
          adjusted for as context above. We deliberately do not publish
          player-by-referee splits. With three officials per game and a few
          dozen shared games per player-referee pair, those tables are noise
          machines that read as accusations; nothing here supports a claim
          about any referee and any player.
        </p>
        <p>
          Because attempts are attributed to the possession finisher, players
          who draw off-ball fouls are out of scope. Players below{" "}
          <span className="font-mono tnum">{int(meta.qualifyPossessions)}</span>{" "}
          possessions in a season get no percentile and are excluded from the
          leaderboard by default; per-possession rates are unstable in small
          samples. And {int(seasons.length)} seasons is{" "}
          {int(seasons.length)} seasons: a career view this is not.
        </p>
      </div>

      <H2>Data notes</H2>
      <div className="mt-4 space-y-4 text-[15px] leading-relaxed sm:text-base">
        <p>
          Shot-zone charts use charged field-goal attempts only; fouled
          misses have no location, so no chart on this site claims to show
          where fouls happen. Team labels are derived from the possession
          data itself (the teams a player finished possessions for, in order
          of first appearance), which is also how midseason trades show up.
          Home/away and officiating crews come from the NBA's public game
          feeds; drives and touch counts come from the NBA's public tracking
          aggregates. Percentiles are computed within each season's
          qualified pool.
        </p>
      </div>
    </article>
  );
}
