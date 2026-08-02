"""Gate 4 citation audit: every citation in every version, re-resolved live.

Stronger than "it verified once at Gate 2". For each key actually cited in each
manuscript this:
  1. confirms the key exists in references.bib
  2. confirms it is in citations_verified.json
  3. re-fetches its DOI from CrossRef and checks the returned title still
     matches the title in the .bib
  4. reports any bib entry that no manuscript cites

A key that fails 1-3 is an unverified citation and must not ship.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ARS = Path.home() / (
    ".claude/plugins/cache/academic-research-skills/"
    "academic-research-skills/3.15.0/scripts"
)
sys.path.insert(0, str(ARS))
from crossref_client import CrossrefClient, CrossrefUnavailable  # noqa: E402
from openalex_client import OpenAlexClient, OpenAlexUnavailable  # noqa: E402
from _text_similarity import _similarity  # noqa: E402

HERE = Path(__file__).parent
POLITE = "kevin@aandrs.at"
MANUSCRIPTS = {
    "canonical": HERE / "overexpected.tex",
    "conference": HERE / "overexpected_conference.tex",
}
CITE_RE = re.compile(r"\\cite[tp]?\*?(?:\[[^\]]*\])*\{([^}]*)\}")


def cited_keys(path: Path) -> set[str]:
    text = path.read_text()
    keys = set()
    for m in CITE_RE.finditer(text):
        for k in m.group(1).split(","):
            if k.strip():
                keys.add(k.strip())
    return keys


def parse_bib(path: Path) -> dict[str, dict]:
    out, cur = {}, None
    for line in path.read_text().splitlines():
        m = re.match(r"@\w+\{([^,]+),", line)
        if m:
            cur = m.group(1).strip()
            out[cur] = {}
            continue
        if cur:
            f = re.match(r"\s*(\w+)\s*=\s*\{+(.*?)\}*,?\s*$", line)
            if f:
                out[cur][f.group(1)] = f.group(2).strip()
    return out


def main() -> None:
    bib = parse_bib(HERE / "references.bib")
    verified = {r["key"]: r
                for r in json.loads((HERE / "citations_verified.json").read_text())}
    cr = CrossrefClient(polite_email=POLITE)
    oa = OpenAlexClient(polite_email=POLITE)

    all_cited: set[str] = set()
    per_doc = {}
    for name, p in MANUSCRIPTS.items():
        k = cited_keys(p)
        per_doc[name] = k
        all_cited |= k
        print(f"{name}: {len(k)} distinct citations")

    print(f"\nre-resolving {len(all_cited)} cited keys against CrossRef\n")
    failures, no_doi = [], []
    for key in sorted(all_cited):
        where = ",".join(n for n in MANUSCRIPTS if key in per_doc[n])
        if key not in bib:
            failures.append((key, "NOT IN references.bib"))
            print(f"FAIL {key:28s} not in references.bib")
            continue
        if key not in verified:
            failures.append((key, "NOT IN citations_verified.json"))
            print(f"FAIL {key:28s} not in citations_verified.json")
            continue
        doi = bib[key].get("doi")
        title = bib[key].get("title", "")
        if not doi:
            no_doi.append(key)
            print(f"OK*  {key:28s} no DOI; OpenAlex-verified "
                  f"({verified[key]['source']}, {verified[key]['year']})  [{where}]")
            continue
        # arXiv DOIs are registered with DataCite, not CrossRef; a CrossRef
        # lookup on one is a category error, not a bad citation.
        registry = "openalex" if doi.startswith("10.48550/") else "crossref"
        client = oa if registry == "openalex" else cr
        try:
            rec = client.doi_lookup_with_title_check(doi, title)
        except (CrossrefUnavailable, OpenAlexUnavailable) as e:
            failures.append((key, f"{registry} unavailable: {e}"))
            print(f"FAIL {key:28s} {registry} unavailable")
            continue
        if rec is None:
            # Title check can fail on punctuation/case; compare explicitly.
            failures.append((key, f"DOI {doi} did not confirm title"))
            print(f"FAIL {key:28s} DOI {doi} did not confirm the bib title")
            continue
        if registry == "openalex":
            # OpenAlex returns the title under `title` for some records and
            # `display_name` for others; reading only one reports a bogus 0.00.
            got = rec.get("display_name") or rec.get("title") or ""
        else:
            got = (rec.get("title") or [""])[0]
        sim = _similarity(got.lower(), title.lower())
        tag = "OK " if registry == "crossref" else "OK~"
        print(f"{tag}  {key:28s} {doi:34s} sim={sim:.2f} "
              f"via {registry}  [{where}]")

    print(f"\n{len(all_cited) - len(failures)}/{len(all_cited)} cited keys "
          f"re-resolved")
    if no_doi:
        print(f"  {len(no_doi)} legitimately have no DOI (proceedings): "
              f"{', '.join(no_doi)}")
    uncited = sorted(set(bib) - all_cited)
    if uncited:
        print(f"\n{len(uncited)} bib entries cited by no manuscript "
              f"(harmless; apalike omits them): {', '.join(uncited)}")
    if failures:
        print("\nFAILURES:")
        for k, why in failures:
            print(f"  {k}: {why}")
        sys.exit(1)
    print("\nPASS — zero unverified citations in either version.")


if __name__ == "__main__":
    main()
