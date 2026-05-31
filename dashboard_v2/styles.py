"""CSS design system for xFTA dashboard v2.

Inject this at the top of every page run via st.markdown(..., unsafe_allow_html=True).
"""

CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Inter:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

/* ================================================================
   ROOT VARIABLES
   ================================================================ */
:root {
    --orange: #E8600A;
    --orange-light: #F08A4A;
    --orange-dark: #C44E00;
    --teal: #0D9488;
    --teal-light: #2DD4BF;
    --teal-dark: #0F766E;
    --charcoal: #1C1917;
    --charcoal-light: #292524;
    --cream: #FAF7F2;
    --cream-dark: #EDE9E3;
    --text-primary: #E7E5E4;
    --text-secondary: #A8A29E;
    --text-muted: #78716C;
    --positive: #E8600A;
    --negative: #0D9488;
}

/* ================================================================
   GLOBAL RESET
   ================================================================ */
html, body, .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: var(--charcoal) !important;
    color: var(--text-primary) !important;
}

/* Kill Streamlit's top padding */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 1200px !important;
}

/* Override Streamlit's default top bar / header */
.stApp header[data-testid="stHeader"] {
    background-color: var(--charcoal) !important;
    border-bottom: 1px solid rgba(255,255,255,0.06) !important;
}
.stApp header[data-testid="stHeader"] * {
    color: var(--text-secondary) !important;
}

/* Override Streamlit's top-level background */
.stApp > div:first-child {
    background-color: var(--charcoal) !important;
}

/* Deploy button hide */
.stDeployButton,
[data-testid="stDeployButton"],
button[kind="deploy"] {
    display: none !important;
}

/* Hide Streamlit top-right menu */
[data-testid="stToolbar"] {
    display: none !important;
}

/* Ensure tab list sits flush under any header */
.stTabs {
    margin-top: 0.5rem !important;
}

/* Make tab text more legible */
.stTabs [data-baseweb="tab"] p {
    color: inherit !important;
    font-size: inherit !important;
}

/* ================================================================
   SIDEBAR
   ================================================================ */
section[data-testid="stSidebar"] {
    background-color: var(--charcoal) !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}
section[data-testid="stSidebar"] > div {
    background-color: var(--charcoal) !important;
}
section[data-testid="stSidebar"] .stMarkdown {
    color: var(--text-secondary) !important;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: var(--text-primary) !important;
    font-family: 'DM Serif Display', serif !important;
}

/* Sidebar logo mark */
.xfta-logo {
    font-family: 'DM Serif Display', serif !important;
    font-size: 2rem;
    color: var(--orange);
    letter-spacing: -0.02em;
    line-height: 1;
    margin-bottom: 0.25rem;
}
.xfta-tagline {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-secondary);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 1.5rem;
}

/* ================================================================
   TABS
   ================================================================ */
.stTabs [data-baseweb="tab-list"] {
    background-color: transparent !important;
    border-bottom: 1px solid rgba(255,255,255,0.08) !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background-color: transparent !important;
    border: none !important;
    color: var(--text-muted) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.8125rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.02em;
    padding: 0.75rem 1.25rem !important;
    margin: 0 !important;
    border-bottom: 2px solid transparent !important;
    transition: color 0.15s ease, border-color 0.15s ease;
}
.stTabs [data-baseweb="tab"]:hover {
    color: var(--text-secondary) !important;
}
.stTabs [aria-selected="true"] {
    color: var(--orange) !important;
    border-bottom-color: var(--orange) !important;
}

/* ================================================================
   TYPOGRAPHY
   ================================================================ */
h1, h2, h3, h4 {
    font-family: 'DM Serif Display', serif !important;
    color: var(--text-primary) !important;
    letter-spacing: -0.01em;
    font-weight: 400 !important;
}
h1 { font-size: 2.25rem !important; margin-bottom: 0.5rem !important; }
h2 { font-size: 1.75rem !important; margin-bottom: 0.75rem !important; }
h3 { font-size: 1.25rem !important; margin-bottom: 0.5rem !important; }

p, li, label, .stMarkdown {
    font-family: 'Inter', sans-serif !important;
    color: var(--text-secondary) !important;
    line-height: 1.65 !important;
    font-size: 0.9375rem !important;
}

/* Monospace numbers */
.mono-num {
    font-family: 'IBM Plex Mono', monospace !important;
    font-variant-numeric: tabular-nums;
    font-feature-settings: 'tnum';
}

/* ================================================================
   BUTTONS
   ================================================================ */
.stButton > button {
    background-color: var(--orange) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.8125rem !important;
    padding: 0.5rem 1.25rem !important;
    transition: background-color 0.15s ease, transform 0.05s ease;
}
.stButton > button:hover {
    background-color: var(--orange-light) !important;
}
.stButton > button:active {
    transform: scale(0.98);
}

/* ================================================================
   INPUTS / SELECTS / SLIDERS
   ================================================================ */
.stSelectbox > div > div,
.stSlider > div > div {
    background-color: var(--charcoal-light) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 6px !important;
    color: var(--text-primary) !important;
}
.stSlider [data-baseweb="slider"] [role="slider"] {
    background-color: var(--orange) !important;
    border-color: var(--orange) !important;
}
.stSlider [data-baseweb="slider"] [data-testid="stTickBar"] {
    background-color: rgba(255,255,255,0.08) !important;
}

/* ================================================================
   DATAFRAMES / TABLES
   ================================================================ */
.stDataFrame {
    font-family: 'IBM Plex Mono', monospace !important;
    font-variant-numeric: tabular-nums;
}
.stDataFrame th {
    background-color: var(--charcoal-light) !important;
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 1px solid rgba(255,255,255,0.08) !important;
}
.stDataFrame td {
    color: var(--text-primary) !important;
    font-size: 0.8125rem !important;
    border-bottom: 1px solid rgba(255,255,255,0.04) !important;
}
.stDataFrame tr:hover td {
    background-color: rgba(232,96,10,0.04) !important;
}

/* ================================================================
   EXPANDER
   ================================================================ */
.streamlit-expanderHeader {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: var(--text-secondary) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 6px !important;
    background-color: var(--charcoal-light) !important;
}
.streamlit-expanderContent {
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-top: none !important;
    border-radius: 0 0 6px 6px !important;
    background-color: var(--charcoal) !important;
}

/* ================================================================
   METRICS
   ================================================================ */
[data-testid="stMetric"] {
    background-color: var(--charcoal-light) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 8px !important;
    padding: 1rem !important;
}
[data-testid="stMetric"] label {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.6875rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted) !important;
}
[data-testid="stMetric"] div:last-child {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 1.5rem !important;
    font-weight: 600 !important;
    color: var(--text-primary) !important;
}

/* ================================================================
   DIVIDERS / HELPERS
   ================================================================ */
hr {
    border-color: rgba(255,255,255,0.08) !important;
    margin: 1.5rem 0 !important;
}

/* Glossary card */
.glossary-card {
    background-color: var(--charcoal-light);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 1.25rem;
    margin-bottom: 0.75rem;
}
.glossary-card dt {
    font-family: 'DM Serif Display', serif;
    font-size: 1rem;
    color: var(--orange);
    margin-bottom: 0.25rem;
}
.glossary-card dd {
    font-family: 'Inter', sans-serif;
    font-size: 0.8125rem;
    color: var(--text-secondary);
    margin-left: 0;
    line-height: 1.55;
}

/* CTA link */
.cta-link {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--orange);
    font-weight: 600;
    font-size: 0.875rem;
    text-decoration: none;
    transition: color 0.15s ease;
}
.cta-link:hover {
    color: var(--orange-light);
}

/* Hide default Streamlit footer */
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
"""
