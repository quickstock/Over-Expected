# Over Expected: measuring what an NBA shot is really worth

**Live: [over-expected.vercel.app](https://over-expected.vercel.app)**

A solo, end-to-end NBA analytics product: a data pipeline over six seasons of
play-by-play, leak-free models for shot value, an original public stat, and a
data-journalism site to make it legible.

---

## TL;DR

I built a system that answers one question, "how much does a player add over
what an average player would do with the same looks," and answers it three ways:
the shots he makes above their difficulty, the fouls he draws above the league
rate, and the two fused into points over expected per 100 possessions. The same
lenses run on players, teams, and officials.

The interesting part is not the basketball. It is that the whole thing is built
to be honest: leak-free models, anchored so seasons are comparable, scoped so it
never claims more than the data supports, and gated by automated validation
before anything ships.

Scope: 1.39M possessions, 1.28M field-goal attempts, 7,230 games, 2020-21 to
2025-26.

## The question

"Who draws fouls" is a counting stat that flatters high-volume players and tells
you nothing about skill. I wanted the residual: given where and how a player
shoots, how many more free throws does he draw than that shot diet predicts? That
is FTAOE, free throw attempts over expected. Then I extended it. Free throws are
only half of what a shot is worth, so I added an expected field-goal model and
fused the two into expected points per shot. The product lets you look through
any of the three lenses.

## What I built

Three reads on the same player pool, switchable everywhere:

- **Foul-drawing (FTAOE).** Shooting-foul free throws drawn per 100 possessions
  against the league-average rate.
- **Shot-making.** Actual FG% against a shooter-agnostic expected FG% for the
  looks taken, expressed as field-goal points over expected.
- **Shot value.** The headline. Points over expected per 100, the made shots and
  the drawn free throws together.

Around that: per-player pages with a cumulative season "gap" chart, rolling form,
a shot chart, and career trajectory; a team view (who draws and concedes shooting
fouls); referee whistle profiles; a methodology page; and a study of the 2021-22
officiating crackdown.

## The hard parts

This is where the real work was.

**Reconstructing the score margin for 700k shots.** The shot-chart feed only
stamps the running score on scoring events, so 55% of shots had a score margin of
zero, which meant "not recorded," not "tied." A referee split on game state was
therefore sitting on bad data. The play-by-play feed carries the running score on
every scoring event, and a shot's event id maps one-to-one to the play-by-play
action number, so I forward-filled the score per game and reconstructed a
complete, correctly signed margin for all 706,961 missing shots. Verified against
the recorded values at 100% before backfilling only the gaps.

**Leak-free season cross-fit.** Every shot needs an expected value, and no shot's
prediction may come from a model that trained on it. So for each season the model
trains on the other five and predicts the held-out one. Coming from algorithmic
trading, this is the same anti-lookahead discipline as a walk-forward backtest,
and it is the difference between a number you can trust and one you cannot.

**Anchoring so seasons compare.** Within-season residuals sum to roughly zero by
construction, so a player in 2021-22 and a player in 2024-25 are measured against
their own league, not a drifting foul environment.

**Knowing what not to claim.** The number blends playstyle, contact-seeking
skill, and officiating, and this method cannot separate them. So the site says so,
plainly, and refuses to publish player-by-referee splits, which on a few dozen
shared games per pair would manufacture accusations the data cannot support. The
possession, not the shot, is the unit, because a fouled miss has no shot location
and any per-shot rate would quietly drop the exact plays the stat is about.

**The front end is real, not a notebook.** React, Vite, and TypeScript, with
hand-built SVG charts (the cumulative gap, a physics-placed beeswarm, a shot-zone
court, rolling form, a team scatter), motion that reveals on scroll with
reduced-motion fallbacks, and a static prerender that generates per-route titles,
descriptions, OG share cards, and a sitemap across ~550 pages.

## A finding

The NBA's 2021-22 crackdown on "non-basketball moves" is treated as a league-wide
event, but the league rate barely moved (17.8 to 17.5 shooting-foul FTA per 100).
It was surgical. It repriced a small set of high-volume foul-drawers and left
everyone else alone, and the environment crept back up the next season. The data
shows a policy aimed at a handful of players, not the game.

## Stack

- **Data and ML:** Python, pandas, SQLite, LightGBM, the NBA stats API, numpy.
  Leak-free cross-fit, calibration and anchoring checks, an automated export gate.
- **Front end:** React, Vite, TypeScript, Tailwind, bespoke SVG data viz, CSS
  motion.
- **Build and deploy:** static prerender with satori-generated OG cards, Vercel,
  a self-updating weekly pipeline.

## What I would do next

- Closest-defender context. Public matchup data is aggregated, not per shot, so
  this is a genuine ceiling on a public model, and the site says so. The per-zone
  calibration check is built to flag exactly where that ceiling bites.
- Sharpen the style-adjusted baseline with more shot-creation tracking signals
  (elbow touches, catch-and-shoot versus pull-up, isolation and transition rate).

## Links

- Live site: [over-expected.vercel.app](https://over-expected.vercel.app)
- Methodology: [over-expected.vercel.app/methodology](https://over-expected.vercel.app/methodology)
- The crackdown study: [over-expected.vercel.app/crackdown](https://over-expected.vercel.app/crackdown)
