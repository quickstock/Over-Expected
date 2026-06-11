# Product

## Register

brand

## Users

NBA fans and analytics-literate basketball people who open shared links (mostly on mobile) and want to see who draws shooting fouls above or below the league rate. Secondary: stats-savvy readers who scrutinize the methodology before trusting a new metric.

## Product Purpose

A static, shareable website presenting FTAOE: free throw attempts over expected, a per-possession shooting-foul-drawing rate vs the league-average baseline, built from a leak-free possession-level model over three NBA seasons. Success = people screenshot the leaderboard and player cards and pass them around, and skeptics find an honest methodology that holds up.

## Brand Personality

Editorial, precise, honest. The Pudding meets a premium annual report: big confident numbers, restrained surfaces, vivid color reserved for one meaning. Descriptive, never causal; the site says what the stat measures and plainly states what it cannot prove (referee bias).

## Anti-references

- Streamlit/dashboard-template look (the site replaces a Streamlit app)
- Sports-betting site aesthetics: neon glows, aggressive gradients, carnival color
- Spreadsheet walls: dense, undesigned data tables
- Hot-take framing: "robbed", "the whistle favors X", causal referee-bias claims

## Design Principles

1. Color is meaning: the diverging warm/cool encoding belongs to FTAOE alone, everywhere it appears; everything else stays neutral.
2. Honest framing beats a better story: descriptive language, real exported fields only, no invented metrics, no foul-location maps.
3. Numbers are the heroes: tabular numerals, strong typographic hierarchy, direct labels over legends.
4. Built to be screenshotted: every view should crop into a legible, self-explanatory share on a phone.
5. One visual language across all charts: crisp inline SVG, consistent formatting, zero layout shift.

## Accessibility & Inclusion

WCAG AA contrast for all text. The diverging encoding never relies on hue alone (numbers and signs always present). Reduced-motion honored for all transitions. Fully legible on mobile, where shared links get opened.
