"""CSS design system — Apple Sport Analytics / bento / true dark.

On top of the existing data layer. Diverging FTAOE scale is unchanged.
One accent (brand orange) for chrome only. Glass cards over a near-black
ground. Premium sans, tabular numerals, restrained motion.
"""

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&family=Instrument+Serif:ital@0;1&display=swap');

/* ================================================================
   ROOT — midnight-slate ground, single accent, diverging data scale
   ================================================================ */
:root {
    /* Ground */
    --ground:        #0B0F19;     /* midnight slate, true dark */
    --surface:       rgba(255, 255, 255, 0.04);   /* glass base */
    --surface-hi:    rgba(255, 255, 255, 0.06);   /* glass hover */
    --surface-2:     rgba(255, 255, 255, 0.025);  /* glass recessed */
    --rule:          rgba(255, 255, 255, 0.08);   /* hairlines */
    --rule-soft:     rgba(255, 255, 255, 0.04);

    /* Type */
    --ink:           #F5F6F8;
    --ink-2:         rgba(245, 246, 248, 0.72);
    --ink-3:         rgba(245, 246, 248, 0.48);
    --ink-4:         rgba(245, 246, 248, 0.32);

    /* Brand accent — chrome only (links, the brand mark, the prov dot) */
    --accent:        #E8600A;
    --accent-soft:   #C44E00;

    /* === FTAOE diverging scale — unchanged. Warm pole is deeper than brand. */
    --delta-warm-3:  #9C2E04;
    --delta-warm-2:  #C2420A;
    --delta-warm-1:  #E48A50;
    --delta-zero:    #2E2E32;
    --delta-cool-1:  #6FA8B8;
    --delta-cool-2:  #2D7A8C;
    --delta-cool-3:  #11404C;

    /* Numeric type */
    --mono: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
    --sans: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    --serif: 'Instrument Serif', 'Iowan Old Style', Georgia, serif;

    /* Glass tokens */
    --glass-blur:   24px;
    --glass-radius: 20px;
    --glass-radius-sm: 14px;
    --shadow-1: 0 1px 0 rgba(255,255,255,0.04) inset, 0 8px 32px rgba(0,0,0,0.32);
    --shadow-2: 0 1px 0 rgba(255,255,255,0.06) inset, 0 16px 48px rgba(0,0,0,0.4);
}

/* ================================================================
   RESET / GLOBAL
   ================================================================ */
html, body, .stApp {
    font-family: var(--sans) !important;
    background-color: var(--ground) !important;
    color: var(--ink) !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    letter-spacing: -0.005em;
}

.block-container {
    padding-top: 2.5rem !important;
    padding-bottom: 5rem !important;
    max-width: 1240px !important;
}

/* ================================================================
   HIDE ALL STREAMLIT CHROME
   ================================================================ */
.stApp header[data-testid="stHeader"],
.stApp [data-testid="stToolbar"],
#MainMenu, footer, .stDeployButton,
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {
    display: none !important;
    visibility: hidden !important;
}

/* Subtle ambient gradient at top — gives the dark surface depth without
   being a wallpaper */
.stApp::before {
    content: '';
    position: fixed; inset: 0;
    background:
        radial-gradient(1200px 600px at 20% -10%, rgba(232,96,10,0.06), transparent 60%),
        radial-gradient(900px 500px at 90% 0%, rgba(45,122,140,0.05), transparent 60%);
    pointer-events: none;
    z-index: 0;
}

/* ================================================================
   TYPOGRAPHY
   ================================================================ */
h1, h2, h3, h4 {
    font-family: var(--sans) !important;
    color: var(--ink) !important;
    font-weight: 700 !important;
    letter-spacing: -0.025em;
    line-height: 1.05;
}
h1 { font-size: 3rem !important; }
h2 { font-size: 1.75rem !important; }
h3 { font-size: 1.25rem !important; }
h4 { font-size: 1rem !important; font-weight: 600 !important; }

p, li, label, .stMarkdown {
    font-family: var(--sans) !important;
    color: var(--ink-2) !important;
    line-height: 1.55 !important;
    font-size: 0.9375rem !important;
}

.mono, .mono-num, code, kbd {
    font-family: var(--mono) !important;
    font-variant-numeric: tabular-nums;
    font-feature-settings: 'tnum' 1, 'zero' 1, 'ss01' 1;
}

/* The display numbers — massive, confident, tabular */
.display {
    font-family: var(--sans) !important;
    font-size: 5.5rem !important;
    line-height: 0.95;
    font-weight: 700 !important;
    letter-spacing: -0.04em;
    font-variant-numeric: tabular-nums;
    font-feature-settings: 'tnum' 1, 'ss01' 1;
}
.display-md {
    font-family: var(--sans) !important;
    font-size: 3rem !important;
    line-height: 1;
    font-weight: 700 !important;
    letter-spacing: -0.03em;
    font-variant-numeric: tabular-nums;
}
.display-sm {
    font-family: var(--sans) !important;
    font-size: 1.75rem !important;
    line-height: 1.05;
    font-weight: 600 !important;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
}

/* Eyebrow / micro-label */
.eyebrow {
    font-family: var(--sans) !important;
    font-size: 0.6875rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--ink-3) !important;
}
.eyebrow-sm {
    font-family: var(--sans) !important;
    font-size: 0.625rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--ink-4) !important;
}

.caption {
    font-family: var(--sans) !important;
    font-size: 0.8125rem !important;
    color: var(--ink-3) !important;
    line-height: 1.55 !important;
}

/* ================================================================
   GLASS CARDS — the bento primitive
   ================================================================ */
.glass {
    background: var(--surface);
    backdrop-filter: blur(var(--glass-blur)) saturate(180%);
    -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(180%);
    border: 1px solid var(--rule);
    border-radius: var(--glass-radius);
    box-shadow: var(--shadow-1);
    padding: 1.75rem;
    transition: background-color 200ms ease, border-color 200ms ease, transform 200ms ease;
}
.glass-sm {
    background: var(--surface);
    backdrop-filter: blur(var(--glass-blur)) saturate(180%);
    -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(180%);
    border: 1px solid var(--rule);
    border-radius: var(--glass-radius-sm);
    box-shadow: var(--shadow-1);
    padding: 1.25rem 1.5rem;
}
.glass:hover {
    background: var(--surface-hi);
    border-color: rgba(255,255,255,0.12);
}
.glass-recessed {
    background: var(--surface-2);
    border: 1px solid var(--rule-soft);
    border-radius: var(--glass-radius-sm);
    padding: 1rem 1.25rem;
}

/* ================================================================
   BENTO GRID — the layout primitive
   ================================================================ */
.bento {
    display: grid;
    gap: 1rem;
}
.bento-3 {
    grid-template-columns: 1.4fr 1fr 1fr;
}
.bento-2-1 {
    grid-template-columns: 2fr 1fr;
}
.bento-1-2 {
    grid-template-columns: 1fr 2fr;
}
@media (max-width: 980px) {
    .bento-3, .bento-2-1, .bento-1-2 { grid-template-columns: 1fr; }
}

/* ================================================================
   SIDEBAR
   ================================================================ */
section[data-testid="stSidebar"] {
    background-color: rgba(11, 15, 25, 0.6) !important;
    backdrop-filter: blur(24px) saturate(180%);
    -webkit-backdrop-filter: blur(24px) saturate(180%);
    border-right: 1px solid var(--rule) !important;
}
section[data-testid="stSidebar"] > div {
    background-color: transparent !important;
    padding-top: 2rem !important;
}
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] p {
    color: var(--ink-2) !important;
    font-size: 0.8125rem !important;
}

.brand-mark {
    display: flex; align-items: baseline; gap: 0.5rem;
    margin-bottom: 0.4rem;
}
.brand-mark .mark {
    font-family: var(--sans);
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--ink);
    letter-spacing: -0.04em;
    line-height: 1;
}
.brand-mark .dot {
    width: 7px; height: 7px;
    background: var(--accent);
    border-radius: 50%;
    transform: translateY(-1px);
    box-shadow: 0 0 12px rgba(232,96,10,0.5);
}
.brand-tagline {
    font-family: var(--sans);
    font-size: 0.6875rem;
    font-weight: 500;
    color: var(--ink-3);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 2rem;
}

.sidebar-meta {
    font-family: var(--mono);
    font-size: 0.625rem;
    color: var(--ink-3);
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

/* ================================================================
   TABS — quiet underline, just ink
   ================================================================ */
.stTabs [data-baseweb="tab-list"] {
    background-color: transparent !important;
    border-bottom: 1px solid var(--rule) !important;
    gap: 0 !important;
    padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background-color: transparent !important;
    border: none !important;
    color: var(--ink-3) !important;
    font-family: var(--sans) !important;
    font-size: 0.8125rem !important;
    font-weight: 600 !important;
    letter-spacing: 0;
    padding: 0.875rem 1.5rem !important;
    margin: 0 !important;
    border-bottom: 1px solid transparent !important;
    transition: color 160ms ease, border-color 160ms ease;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--ink) !important; }
.stTabs [aria-selected="true"] {
    color: var(--ink) !important;
    border-bottom-color: var(--ink) !important;
}
.stTabs [data-baseweb="tab"] p { color: inherit !important; font-size: inherit !important; }

/* ================================================================
   BUTTONS
   ================================================================ */
.stButton > button {
    background-color: var(--surface) !important;
    color: var(--ink) !important;
    border: 1px solid var(--rule) !important;
    border-radius: 10px !important;
    font-family: var(--sans) !important;
    font-weight: 600 !important;
    font-size: 0.8125rem !important;
    padding: 0.5rem 1rem !important;
    transition: background-color 160ms ease, border-color 160ms ease, transform 160ms ease;
}
.stButton > button:hover {
    background-color: var(--surface-hi) !important;
    border-color: rgba(255,255,255,0.18) !important;
}
.stButton > button:active { transform: scale(0.98); }
.stDownloadButton > button {
    background-color: var(--ink) !important;
    color: var(--ground) !important;
    border: 1px solid var(--ink) !important;
    border-radius: 10px !important;
    font-family: var(--sans) !important;
    font-weight: 600 !important;
    font-size: 0.8125rem !important;
    padding: 0.5rem 1rem !important;
    transition: opacity 160ms ease;
}
.stDownloadButton > button:hover { opacity: 0.88; }

/* ================================================================
   INPUTS / SELECTS / SLIDERS
   ================================================================ */
.stSelectbox label, .stSlider label, .stRadio label {
    font-family: var(--sans) !important;
    font-size: 0.625rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--ink-3) !important;
}
.stSelectbox > div > div,
.stMultiSelect > div > div {
    background-color: var(--surface) !important;
    border: 1px solid var(--rule) !important;
    border-radius: 10px !important;
    color: var(--ink) !important;
    font-family: var(--sans) !important;
    font-size: 0.875rem !important;
    backdrop-filter: blur(12px) saturate(180%);
    -webkit-backdrop-filter: blur(12px) saturate(180%);
    transition: border-color 160ms ease, background-color 160ms ease;
}
.stSelectbox > div > div:hover { border-color: rgba(255,255,255,0.18) !important; }
.stSelectbox > div > div:focus-within { border-color: var(--ink) !important; }

.stSlider [data-baseweb="slider"] [role="slider"] {
    background-color: var(--ink) !important;
    border-color: var(--ink) !important;
}
.stSlider [data-baseweb="slider"] > div > div {
    background-color: var(--ink-3) !important;
}
.stRadio [role="radiogroup"] { gap: 0.5rem; }
.stRadio [role="radiogroup"] label {
    background-color: var(--surface) !important;
    border: 1px solid var(--rule) !important;
    border-radius: 10px !important;
    padding: 0.4375rem 0.9375rem !important;
    color: var(--ink-2) !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    font-size: 0.8125rem !important;
    transition: all 160ms ease;
}
.stRadio [role="radiogroup"] label:hover {
    border-color: rgba(255,255,255,0.18) !important;
    color: var(--ink) !important;
}
.stRadio [role="radiogroup"] label:has(input:checked) {
    background-color: var(--ink) !important;
    color: var(--ground) !important;
    border-color: var(--ink) !important;
}

/* ================================================================
   LEADERBOARD — gap plot rows
   ================================================================ */
.gap-table { width: 100%; border-collapse: separate; border-spacing: 0 0.5rem; }
.gap-row {
    background: var(--surface);
    border: 1px solid var(--rule);
    transition: background-color 200ms ease, border-color 200ms ease, transform 200ms ease;
}
.gap-row:hover {
    background: var(--surface-hi);
    border-color: rgba(255,255,255,0.14);
}
.gap-row td {
    padding: 1.125rem 1.25rem;
    vertical-align: middle;
}
.gap-rank {
    width: 56px;
    font-family: var(--mono);
    font-size: 0.75rem;
    color: var(--ink-3);
    font-variant-numeric: tabular-nums;
    border-radius: 20px 0 0 20px;
}
.gap-name {
    font-family: var(--sans);
    color: var(--ink);
    font-weight: 600;
    font-size: 1rem;
    letter-spacing: -0.01em;
}
.gap-name .sub {
    color: var(--ink-3);
    font-size: 0.75rem;
    font-weight: 400;
    margin-left: 0.4rem;
    letter-spacing: 0;
}
.gap-name .delta-sign {
    font-family: var(--mono);
    font-size: 1.25rem;
    font-weight: 700;
    margin-right: 0.5rem;
    font-variant-numeric: tabular-nums;
}
.gap-name .delta-sign.pos { color: var(--delta-warm-2); }
.gap-name .delta-sign.neg { color: var(--delta-cool-2); }

.gap-plot { width: 100%; min-width: 220px; }
.gap-plot svg { width: 100%; height: 36px; display: block; }

.gap-num {
    font-family: var(--mono);
    font-size: 0.875rem;
    font-variant-numeric: tabular-nums;
    text-align: right;
    color: var(--ink-2);
    white-space: nowrap;
}
.gap-num .val { color: var(--ink); font-weight: 600; }

.gap-pctbar { width: 110px; padding-right: 1.25rem; border-radius: 0 20px 20px 0; }
.gap-pctbar-track {
    position: relative;
    height: 4px;
    background: var(--rule-soft);
    border-radius: 2px;
    overflow: hidden;
}
.gap-pctbar-fill {
    position: absolute; top: 0; left: 0; bottom: 0;
    background: var(--ink);
    border-radius: 2px;
    transition: width 200ms ease;
}
.gap-pctbar-label {
    font-family: var(--mono);
    font-size: 0.6875rem;
    color: var(--ink-3);
    margin-top: 0.5rem;
    text-align: right;
    letter-spacing: 0.02em;
    font-variant-numeric: tabular-nums;
}

/* Mobile — collapse to rank + name + delta sign + plot */
@media (max-width: 768px) {
    .gap-hide-mobile { display: none !important; }
    .gap-row td { padding: 0.875rem 0.625rem; }
    .gap-name { font-size: 0.875rem; }
    .gap-num { font-size: 0.75rem; }
    .gap-pctbar { width: 64px; padding-right: 0.75rem; }
}

/* ================================================================
   PLAYER DETAIL — expanding bento
   ================================================================ */
.detail-grid {
    display: grid;
    grid-template-columns: 1.3fr 1fr;
    gap: 1rem;
}
@media (max-width: 900px) { .detail-grid { grid-template-columns: 1fr; } }

.detail-headline {
    font-family: var(--sans);
    font-size: 6rem;
    font-weight: 800;
    line-height: 0.92;
    letter-spacing: -0.045em;
    font-variant-numeric: tabular-nums;
    margin: 0.75rem 0 0.5rem 0;
}
.detail-headline.pos { color: var(--delta-warm-2); }
.detail-headline.neg { color: var(--delta-cool-2); }
.detail-headline.zero { color: var(--ink); }

.detail-name {
    font-family: var(--sans);
    font-size: 1.875rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--ink);
    margin: 0 0 0.25rem 0;
    line-height: 1.1;
}
.detail-sub {
    font-family: var(--sans);
    color: var(--ink-3);
    font-size: 0.8125rem;
    letter-spacing: 0.02em;
}
.detail-sentence {
    font-family: var(--sans);
    font-size: 1rem;
    color: var(--ink);
    margin-top: 1.25rem;
    line-height: 1.55;
    max-width: 44ch;
}
.detail-sentence b { font-weight: 700; }

.stat-tile {
    background: var(--surface);
    border: 1px solid var(--rule);
    border-radius: var(--glass-radius-sm);
    padding: 1.125rem 1.375rem;
    backdrop-filter: blur(var(--glass-blur)) saturate(180%);
    -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(180%);
    transition: background-color 200ms ease, border-color 200ms ease;
}
.stat-tile:hover { background: var(--surface-hi); border-color: rgba(255,255,255,0.12); }
.stat-tile-label {
    font-family: var(--sans);
    font-size: 0.625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--ink-3);
    margin-bottom: 0.625rem;
}
.stat-tile-value {
    font-family: var(--sans);
    font-size: 1.875rem;
    font-weight: 700;
    color: var(--ink);
    line-height: 1;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
}
.stat-tile-value.pos { color: var(--delta-warm-2); }
.stat-tile-value.neg { color: var(--delta-cool-2); }
.stat-tile-sub {
    font-family: var(--sans);
    font-size: 0.75rem;
    color: var(--ink-3);
    margin-top: 0.5rem;
}

/* ================================================================
   LEAGUE HERO — percentile ring + distribution strip
   ================================================================ */
.league-hero {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 1rem;
    align-items: stretch;
}
@media (max-width: 900px) { .league-hero { grid-template-columns: 1fr; } }

.ring-wrap {
    position: relative;
    aspect-ratio: 1;
    max-width: 280px;
    margin: 0 auto;
}
.ring-wrap svg { width: 100%; height: 100%; display: block; }
.ring-label {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    pointer-events: none;
}
.ring-value {
    font-family: var(--sans);
    font-size: 3.25rem;
    font-weight: 800;
    line-height: 1;
    letter-spacing: -0.04em;
    color: var(--ink);
    font-variant-numeric: tabular-nums;
}
.ring-value .pct-mark {
    font-size: 1.125rem;
    color: var(--ink-3);
    font-weight: 600;
    margin-left: 2px;
}
.ring-value.pos { color: var(--delta-warm-2); }
.ring-value.neg { color: var(--delta-cool-2); }
.ring-caption {
    font-family: var(--sans);
    font-size: 0.6875rem;
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 0.5rem;
    font-weight: 600;
}

.dist-strip {
    width: 100%;
    height: 56px;
    position: relative;
}
.dist-strip svg { width: 100%; height: 100%; display: block; }

/* ================================================================
   PROVISIONAL TAG
   ================================================================ */
.prov {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    background: rgba(232,96,10,0.10);
    color: var(--accent);
    border: 1px solid rgba(232,96,10,0.28);
    border-radius: 6px;
    padding: 0.15rem 0.5rem;
    font-family: var(--sans);
    font-size: 0.625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    vertical-align: middle;
    line-height: 1.4;
}
.prov::before {
    content: '';
    width: 5px; height: 5px;
    background: var(--accent);
    border-radius: 50%;
    box-shadow: 0 0 8px rgba(232,96,10,0.6);
}
.verified {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    color: var(--ink-3);
    font-family: var(--sans);
    font-size: 0.6875rem;
    font-weight: 500;
    letter-spacing: 0.04em;
}

/* ================================================================
   DIVERGING TEXT UTILITIES (kept for tile accent)
   ================================================================ */
.delta-pos-strong  { color: var(--delta-warm-3); }
.delta-pos         { color: var(--delta-warm-2); }
.delta-pos-soft    { color: var(--delta-warm-1); }
.delta-zero        { color: var(--ink-3); }
.delta-neg-soft    { color: var(--delta-cool-1); }
.delta-neg         { color: var(--delta-cool-2); }
.delta-neg-strong  { color: var(--delta-cool-3); }

/* ================================================================
   EXPANDER — dressed as glass card
   ================================================================ */
.streamlit-expanderHeader {
    font-family: var(--sans) !important;
    font-size: 0.9375rem !important;
    font-weight: 600 !important;
    color: var(--ink) !important;
    background: var(--surface) !important;
    border: 1px solid var(--rule) !important;
    border-radius: 14px !important;
    backdrop-filter: blur(16px) saturate(180%);
    -webkit-backdrop-filter: blur(16px) saturate(180%);
    transition: background-color 160ms ease, border-color 160ms ease;
    padding: 1rem 1.5rem !important;
}
.streamlit-expanderHeader:hover {
    background: var(--surface-hi) !important;
    border-color: rgba(255,255,255,0.16) !important;
}
.streamlit-expanderContent {
    border: 1px solid var(--rule) !important;
    border-top: none !important;
    border-radius: 0 0 14px 14px !important;
    background: var(--surface-2) !important;
    padding: 0 1.5rem 1.5rem 1.5rem !important;
}
div[data-testid="stExpander"] {
    border: none !important;
    background: transparent !important;
}

/* ================================================================
   METRICS (Streamlit native) — quiet
   ================================================================ */
[data-testid="stMetric"] {
    background: var(--surface) !important;
    border: 1px solid var(--rule) !important;
    border-radius: 12px !important;
    padding: 1rem 1.25rem !important;
}
[data-testid="stMetric"] label {
    font-family: var(--sans) !important;
    font-size: 0.625rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--ink-3) !important;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-family: var(--mono) !important;
    font-size: 1.375rem !important;
    font-weight: 500 !important;
    color: var(--ink) !important;
}

/* ================================================================
   DIVIDERS / MISC
   ================================================================ */
hr { border-color: var(--rule) !important; margin: 2rem 0 !important; }
a { color: var(--ink); text-decoration: none; border-bottom: 1px solid var(--rule); }
a:hover { border-bottom-color: var(--ink); }
"""
