"""Generate sitemap.xml (+ Sitemap line in robots.txt) for the deployed site.

Usage: python3 scripts/generate_sitemap.py https://your-domain.tld
Reads site/public/data.json for qualified player ids; writes
site/public/sitemap.xml. Run before `vite build` / deploy.
"""
import json
import sys
from pathlib import Path

if len(sys.argv) != 2 or not sys.argv[1].startswith("http"):
    raise SystemExit("usage: generate_sitemap.py https://domain.tld")
base = sys.argv[1].rstrip("/")

ROOT = Path(__file__).parent.parent / "site" / "public"
data = json.loads((ROOT / "data.json").read_text())

qualify = data["meta"]["qualifyPossessions"]
player_ids = sorted({r["id"] for r in data["leaderboard"] if r["poss"] >= qualify})

urls = [f"{base}/", f"{base}/leaderboard", f"{base}/methodology", f"{base}/data", f"{base}/crackdown", f"{base}/compare", f"{base}/league", f"{base}/feedback"] + [
    f"{base}/player/{pid}" for pid in player_ids
]
body = "\n".join(
    f"  <url><loc>{u}</loc></url>" for u in urls
)
(ROOT / "sitemap.xml").write_text(
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    f"{body}\n</urlset>\n"
)
(ROOT / "robots.txt").write_text(
    f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n"
)
print(f"sitemap.xml: {len(urls)} urls for {base}")
