/**
 * Post-build static generation:
 *   1. An OG share card (1200x630 PNG) per qualified player (latest
 *      season) via satori + resvg, plus one generic site card.
 *   2. Per-route HTML shells (player pages, /leaderboard, /methodology,
 *      /data) with route-specific <title>, description and og/twitter
 *      tags, so crawlers and link unfurlers get real metadata without
 *      a server.
 *
 * Usage:  node scripts/generate-static.mjs [--base https://domain.tld]
 * Run AFTER `vite build`; writes into dist/.
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const DIST = join(ROOT, "dist");

const baseArg = process.argv.indexOf("--base");
const envBase = process.env.VERCEL_PROJECT_PRODUCTION_URL
  ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
  : "https://ftaoe.vercel.app";
const BASE = (baseArg > -1 ? process.argv[baseArg + 1] : envBase).replace(/\/$/, "");

const data = JSON.parse(readFileSync(join(ROOT, "public", "data.json"), "utf8"));
const template = readFileSync(join(DIST, "index.html"), "utf8");

const fonts = [
  {
    name: "Bricolage Grotesque",
    data: readFileSync(join(__dirname, "fonts", "BricolageGrotesque-Bold.ttf")),
    weight: 700,
    style: "normal",
  },
  {
    name: "JetBrains Mono",
    data: readFileSync(join(__dirname, "fonts", "JetBrainsMono-Bold.ttf")),
    weight: 700,
    style: "normal",
  },
  {
    name: "JetBrains Mono",
    data: readFileSync(join(__dirname, "fonts", "JetBrainsMono-Regular.ttf")),
    weight: 400,
    style: "normal",
  },
];

// Diverging text colors (hex equivalents of the site's oklch tokens).
const WARM = "#b8431f";
const COOL = "#2f5e9e";
const INK = "#25262c";
const SOFT = "#5e606b";
const FAINT = "#909097";
const PAPER = "#f7f7f6";
const LINE = "#dededf";

const signed = (v, d = 1) => {
  const s = v.toFixed(d);
  return parseFloat(s) > 0 ? `+${s}` : s.replace("-", "−");
};
const ordinal = (n) => {
  const r10 = n % 10, r100 = n % 100;
  if (r10 === 1 && r100 !== 11) return `${n}st`;
  if (r10 === 2 && r100 !== 12) return `${n}nd`;
  if (r10 === 3 && r100 !== 13) return `${n}rd`;
  return `${n}th`;
};
const deltaColor = (v) => (v > 0.05 ? WARM : v < -0.05 ? COOL : SOFT);

function card(row) {
  const pct = Math.max(0, Math.min(100, Math.floor(row.pct ?? 50)));
  return {
    type: "div",
    props: {
      style: {
        width: 1200, height: 630, display: "flex", flexDirection: "column",
        backgroundColor: PAPER, padding: 72, justifyContent: "space-between",
      },
      children: [
        {
          type: "div",
          props: {
            style: { display: "flex", justifyContent: "space-between", alignItems: "baseline" },
            children: [
              { type: "div", props: { style: { fontFamily: "Bricolage Grotesque", fontSize: 34, color: INK }, children: "FTAOE" } },
              { type: "div", props: { style: { fontFamily: "JetBrains Mono", fontWeight: 400, fontSize: 26, color: FAINT }, children: `${row.season} · shooting fouls only` } },
            ],
          },
        },
        {
          type: "div",
          props: {
            style: { display: "flex", flexDirection: "column", gap: 6 },
            children: [
              { type: "div", props: { style: { fontFamily: "Bricolage Grotesque", fontSize: 64, color: INK }, children: row.name } },
              {
                type: "div",
                props: {
                  style: { display: "flex", alignItems: "baseline", gap: 28 },
                  children: [
                    { type: "div", props: { style: { fontFamily: "JetBrains Mono", fontSize: 150, color: deltaColor(row.per100) }, children: signed(row.per100) } },
                    { type: "div", props: { style: { display: "flex", flexDirection: "column", fontFamily: "JetBrains Mono", fontWeight: 400, fontSize: 27, color: SOFT, lineHeight: 1.5 }, children: [
                      { type: "div", props: { children: "free throws per 100 possessions" } },
                      { type: "div", props: { children: "over the league-average rate" } },
                    ] } },
                  ],
                },
              },
            ],
          },
        },
        {
          type: "div",
          props: {
            style: { display: "flex", flexDirection: "column", gap: 18 },
            children: [
              {
                type: "div",
                props: {
                  style: { display: "flex", position: "relative", height: 10, backgroundColor: "#ecece9", borderRadius: 5 },
                  children: [
                    { type: "div", props: { style: { position: "absolute", left: "50%", top: -5, width: 2, height: 20, backgroundColor: LINE } } },
                    { type: "div", props: { style: {
                      position: "absolute", left: `${pct}%`, top: -13,
                      transform: "translateX(-18px)",
                      width: 36, height: 36, borderRadius: 18,
                      backgroundColor: deltaColor(row.per100),
                      display: "flex", alignItems: "center", justifyContent: "center",
                      color: PAPER, fontFamily: "JetBrains Mono", fontSize: 17,
                    }, children: `${pct}` } },
                  ],
                },
              },
              {
                type: "div",
                props: {
                  style: { display: "flex", justifyContent: "space-between", fontFamily: "JetBrains Mono", fontWeight: 400, fontSize: 24, color: FAINT },
                  children: [
                    { type: "div", props: { children: `${ordinal(pct)} percentile · ${row.fta} FTA vs ${row.xfta.toFixed(1)} expected` } },
                    { type: "div", props: { children: `${row.teams.join(" · ")}` } },
                  ],
                },
              },
            ],
          },
        },
      ],
    },
  };
}

function genericCard() {
  const seasons = data.meta.seasons;
  return {
    type: "div",
    props: {
      style: {
        width: 1200, height: 630, display: "flex", flexDirection: "column",
        backgroundColor: PAPER, padding: 72, justifyContent: "space-between",
      },
      children: [
        { type: "div", props: { style: { fontFamily: "JetBrains Mono", fontWeight: 400, fontSize: 26, color: FAINT }, children: `${seasons[0]} to ${seasons[seasons.length - 1]} · shooting fouls only` } },
        {
          type: "div",
          props: {
            style: { display: "flex", flexDirection: "column", gap: 14 },
            children: [
              { type: "div", props: { style: { fontFamily: "Bricolage Grotesque", fontSize: 110, color: INK, lineHeight: 1.02 }, children: "The free-throw gap." } },
              { type: "div", props: { style: { display: "flex", fontFamily: "JetBrains Mono", fontWeight: 400, fontSize: 30, color: SOFT }, children: [
                { type: "span", props: { style: { color: COOL }, children: signed(-15.1) } },
                { type: "span", props: { children: " to " } },
                { type: "span", props: { style: { color: WARM }, children: signed(25.6) } },
                { type: "span", props: { children: " free throws per 100 possessions" } },
              ] } },
            ],
          },
        },
        { type: "div", props: { style: { fontFamily: "Bricolage Grotesque", fontSize: 30, color: INK }, children: "FTAOE — free throw attempts over expected" } },
      ],
    },
  };
}

async function renderPng(node, path) {
  const svg = await satori(node, { width: 1200, height: 630, fonts });
  const png = new Resvg(svg, { fitTo: { mode: "width", value: 1200 } }).render().asPng();
  writeFileSync(path, png);
}

function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

function shell({ title, description, path, image }) {
  let html = template;
  html = html.replace(/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`);
  html = html.replace(
    /(<meta\s+name="description"\s+content=")[^"]*(")/,
    `$1${esc(description)}$2`,
  );
  html = html.replace(
    /(<meta property="og:title" content=")[^"]*(")/,
    `$1${esc(title)}$2`,
  );
  html = html.replace(
    /(<meta\s+property="og:description"\s+content=")[^"]*(")/,
    `$1${esc(description)}$2`,
  );
  const extra = [
    `<meta property="og:type" content="website" />`,
    `<meta property="og:url" content="${BASE}${path}" />`,
    `<meta property="og:image" content="${BASE}/og/${image}" />`,
    `<meta property="og:image:width" content="1200" />`,
    `<meta property="og:image:height" content="630" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:image" content="${BASE}/og/${image}" />`,
    `<link rel="canonical" href="${BASE}${path}" />`,
  ].join("\n    ");
  html = html.replace("</head>", `    ${extra}\n  </head>`);
  const dir = join(DIST, ...path.split("/").filter(Boolean));
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "index.html"), html);
}

// ---------------------------------------------------------------- main
mkdirSync(join(DIST, "og"), { recursive: true });

// Latest qualified season per player.
const latestByPlayer = new Map();
for (const season of data.meta.seasons) {
  for (const r of data.leaderboard) {
    if (r.season === season && r.pct !== null) latestByPlayer.set(r.id, r);
  }
}

await renderPng(genericCard(), join(DIST, "og", "site.png"));

let n = 0;
for (const row of latestByPlayer.values()) {
  await renderPng(card(row), join(DIST, "og", `p${row.id}.png`));
  shell({
    title: `${row.name} · FTAOE`,
    description: `${row.name}, ${row.season}: ${signed(row.per100)} shooting-foul free throws per 100 possessions vs the league-average rate (${ordinal(Math.floor(row.pct))} percentile, ${row.fta} FTA vs ${row.xfta.toFixed(1)} expected).`,
    path: `/player/${row.id}`,
    image: `p${row.id}.png`,
  });
  n++;
  if (n % 100 === 0) console.log(`  ${n}/${latestByPlayer.size} player cards`);
}

shell({
  title: "Leaderboard · FTAOE",
  description: "Free throw attempts over expected per 100 possessions: every qualified NBA player, sortable and filterable, across six seasons.",
  path: "/leaderboard",
  image: "site.png",
});
shell({
  title: "Methodology · FTAOE",
  description: "How FTAOE is measured: shooting fouls only, per possession, against each season's league-average rate. Leak-free, anchored, and honest about what it cannot prove.",
  path: "/methodology",
  image: "site.png",
});
shell({
  title: "The crackdown, measured · FTAOE",
  description: "The NBA's 2021-22 memo on non-basketball moves barely moved the league's foul rate. It surgically repriced a handful of players. Six seasons of FTAOE, measured.",
  path: "/crackdown",
  image: "site.png",
});
shell({
  title: "Compare · FTAOE",
  description: "Two NBA players, same season, same baseline: FTAOE per 100, style-adjusted, and the cumulative gap, side by side.",
  path: "/compare",
  image: "site.png",
});
shell({
  title: "Data · FTAOE",
  description: "Download the FTAOE dataset: leaderboard, per-game series, shot zones and foul ledgers for six NBA seasons, as static JSON.",
  path: "/data",
  image: "site.png",
});

// sitemap + robots for the deployed domain
const urls = [
  `${BASE}/`, `${BASE}/leaderboard`, `${BASE}/methodology`,
  `${BASE}/data`, `${BASE}/crackdown`, `${BASE}/compare`,
  ...[...latestByPlayer.keys()].sort((a, b) => a - b).map((id) => `${BASE}/player/${id}`),
];
writeFileSync(
  join(DIST, "sitemap.xml"),
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls
    .map((u) => `  <url><loc>${u}</loc></url>`)
    .join("\n")}\n</urlset>\n`,
);
writeFileSync(
  join(DIST, "robots.txt"),
  `User-agent: *\nAllow: /\n\nSitemap: ${BASE}/sitemap.xml\n`,
);

console.log(`done: ${n} player cards + site card, ${n + 4} HTML shells, sitemap ${urls.length} urls (base ${BASE})`);
