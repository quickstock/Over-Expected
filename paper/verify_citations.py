"""Verify every candidate citation against CrossRef, then OpenAlex.

No DOI is ever typed by hand. Each candidate is a title + year hint; the
authoritative DOI, author list, year and venue come back from the API. Anything
that does not verify is dropped from the paper rather than guessed at.

Run:  python3 paper/verify_citations.py
Out:  paper/citations_verified.json   (the ones that resolved)
      paper/citations_failed.json     (the ones to drop or replace)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ARS = Path.home() / (
    ".claude/plugins/cache/academic-research-skills/"
    "academic-research-skills/3.15.0/scripts"
)
sys.path.insert(0, str(ARS))

from crossref_client import CrossrefClient, CrossrefUnavailable  # noqa: E402
from openalex_client import OpenAlexClient, OpenAlexUnavailable  # noqa: E402

POLITE_EMAIL = "kevin@aandrs.at"
HERE = Path(__file__).parent

# (bibtex_key, title, year_hint, why_it_is_cited, doi_hint)
#
# A doi_hint is NOT a typed-in citation. It is passed to
# doi_lookup_with_title_check, which fetches that DOI and rejects it unless the
# fetched title actually matches. A wrong hint fails loudly instead of landing
# in the bibliography. Hints exist only where a bare title search returned the
# wrong record (generic titles) or nothing.
CANDIDATES = [
    # --- basketball shot quality / spatial models
    ("cervone2016multiresolution",
     "A Multiresolution Stochastic Process Model for Predicting Basketball "
     "Possession Outcomes", 2016,
     "tracking-era possession value; the ceiling public data cannot reach",
     None),
    ("miller2014factorized",
     "Factorized Point Process Intensities: A Spatial Analysis of "
     "Professional Basketball", 2014,
     "spatial shot models", None),
    ("franks2015characterizing",
     "Characterizing the spatial structure of defensive skill in "
     "professional basketball", 2015,
     "defensive skill from tracking; why defender proximity is out of reach",
     None),
    ("kubatko2007starting",
     "A Starting Point for Analyzing Basketball Statistics", 2007,
     "possession estimation and the four factors; foundational box-score work",
     None),

    # --- adjusted plus-minus / measurement in basketball
    ("deshpande2016estimating",
     "Estimating an NBA player's impact on his team's chances of winning",
     2016, "player impact estimation in JQAS; the target venue's own tradition",
     "10.1515/jqas-2015-0027"),

    # --- officiating
    ("price2010racial",
     "Racial Discrimination Among NBA Referees", 2010,
     "officiating behaviour is measurable and non-neutral; crew effects", None),

    ("anderson2009officiating",
     "Officiating bias: The effect of foul differential on foul calls in "
     "NCAA basketball", 2009,
     "foul calls respond to game state, not just to fouls", None),
    ("pope2018awareness",
     "Awareness Reduces Racial Bias", 2018,
     "officiating behaviour shifts when it is measured and published", None),

    # --- shot selection and allocative efficiency (the confound this metric has)
    ("sandholtz2020markov",
     "Markov decision processes with dynamic transition probabilities: An "
     "analysis of shooting strategies in basketball", 2020,
     "shot selection as a decision process, not a fixed diet", None),
    ("sandholtz2020measuring",
     "Measuring spatial allocative efficiency in basketball", 2020,
     "separating shot selection from conversion; the JQAS precedent", None),

    # --- count models for sports events
    ("maher1982modelling",
     "Modelling association football scores", 1982,
     "Poisson counts as the standard model for sports event data", None),
    ("dixon1997modelling",
     "Modelling Association Football Scores and Inefficiencies in the "
     "Football Betting Market", 1997,
     "refinements to the Poisson sports-count baseline", None),

    # --- expected goals, the analogous framework in soccer
    ("decroos2019actions",
     "Actions Speak Louder than Goals", 2019,
     "action-value framing transferred across sports",
     "10.1145/3292500.3330758"),
    ("rathke2017examination",
     "An examination of expected goals and shot efficiency in soccer", 2017,
     "expected-goals as a shot-quality baseline", None),

    # --- calibration
    ("brier1950verification",
     "Verification of Forecasts Expressed in Terms of Probability", 1950,
     "the Brier score reported for xFG", None),
    ("zadrozny2002transforming",
     "Transforming classifier scores into accurate multiclass probability "
     "estimates", 2002,
     "isotonic calibration, the method used on xFG", None),
    ("niculescu2005predicting",
     "Predicting good probabilities with supervised learning", 2005,
     "why boosted models need post-hoc calibration", None),
    ("guo2017calibration",
     "On Calibration of Modern Neural Networks", 2017,
     "calibration vs discrimination as distinct goals", None),

    # --- leakage
    ("kaufman2012leakage",
     "Leakage in data mining", 2012,
     "the leakage taxonomy this paper's audit instantiates",
     "10.1145/2382577.2382579"),
    ("kapoor2023leakage",
     "Leakage and the reproducibility crisis in machine-learning-based "
     "science", 2023,
     "leakage as a field-wide reproducibility problem", None),

    # --- methods
    ("nelder1972generalized",
     "Generalized Linear Models", 1972,
     "the Poisson GLM specification", "10.2307/2344614"),
    ("ke2017lightgbm",
     "LightGBM: A Highly Efficient Gradient Boosting Decision Tree", 2017,
     "the learner used for xFG and the rejected FTAOE arm", None),
    ("spearman1910correlation",
     "Correlation calculated from faulty data", 1910,
     "Spearman-Brown, used for the full-season reliability figure", None),
    ("brown1910some",
     "Some experimental results in the correlation of mental abilities", 1910,
     "the Brown half of Spearman-Brown",
     "10.1111/j.2044-8295.1910.tb00207.x"),
]


def norm_authors(rec, source):
    if source == "crossref":
        return [
            f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
            for a in rec.get("author", []) or []
        ]
    aus = []
    for a in rec.get("authorships", []) or []:
        nm = (a.get("author") or {}).get("display_name")
        if nm:
            aus.append(nm)
    return aus


def norm_crossref(rec):
    titles = rec.get("title") or []
    dp = (rec.get("published-print") or rec.get("published-online")
          or rec.get("issued") or {}).get("date-parts") or [[None]]
    return {
        "source": "crossref",
        "title": titles[0] if titles else "",
        "doi": rec.get("DOI"),
        "year": dp[0][0] if dp and dp[0] else None,
        "authors": norm_authors(rec, "crossref"),
        "container": (rec.get("container-title") or [""])[0],
        "publisher": rec.get("publisher"),
        "type": rec.get("type"),
        "volume": rec.get("volume"),
        "issue": rec.get("issue"),
        "page": rec.get("page"),
    }


def norm_openalex(rec):
    loc = (rec.get("primary_location") or {}).get("source") or {}
    return {
        "source": "openalex",
        "title": rec.get("display_name") or rec.get("title") or "",
        "doi": (rec.get("doi") or "").replace("https://doi.org/", "") or None,
        "year": rec.get("publication_year"),
        "authors": norm_authors(rec, "openalex"),
        "container": loc.get("display_name") or "",
        "publisher": loc.get("host_organization_name"),
        "type": rec.get("type"),
        "volume": (rec.get("biblio") or {}).get("volume"),
        "issue": (rec.get("biblio") or {}).get("issue"),
        "page": "-".join(
            p for p in [(rec.get("biblio") or {}).get("first_page"),
                        (rec.get("biblio") or {}).get("last_page")] if p
        ) or None,
    }


def main():
    cr = CrossrefClient(polite_email=POLITE_EMAIL)
    oa = OpenAlexClient(polite_email=POLITE_EMAIL)

    verified, failed = [], []
    for key, title, year, why, doi_hint in CANDIDATES:
        rec, out = None, None
        if doi_hint:
            # Validated lookup: rejected unless the fetched title matches.
            try:
                rec = cr.doi_lookup_with_title_check(doi_hint, title)
                if rec:
                    out = norm_crossref(rec)
                    print(f"     (doi hint {doi_hint} confirmed by title check)")
                else:
                    print(f"     (doi hint {doi_hint} REJECTED by title check)")
            except CrossrefUnavailable as e:
                print(f"  crossref unavailable for {key}: {e}")
        if out is not None:
            pass
        else:
          try:
            rec = cr.title_search(title, year)
            if rec:
                out = norm_crossref(rec)
          except CrossrefUnavailable as e:
            print(f"  crossref unavailable for {key}: {e}")
        if out is None:
            try:
                rec = oa.title_search(title, year)
                if rec:
                    out = norm_openalex(rec)
            except OpenAlexUnavailable as e:
                print(f"  openalex unavailable for {key}: {e}")

        ok = bool(out) and (
            bool(out.get("doi"))
            or (out.get("source") == "openalex"
                and out.get("authors") and out.get("year"))
        )
        if ok:
            out["hasDoi"] = bool(out.get("doi"))
            out.update({"key": key, "queryTitle": title,
                        "queryYear": year, "why": why})
            verified.append(out)
            print(f"OK   {key:28s} {out['source']:9s} "
                  f"{out['doi'] or '(no DOI — proceedings)'}")
            print(f"     -> {out['title'][:82]}")
            if out["year"] and year and abs(out["year"] - year) > 1:
                print(f"     !! year drift: asked {year}, got {out['year']}")
        else:
            failed.append({"key": key, "queryTitle": title,
                           "queryYear": year, "why": why})
            print(f"FAIL {key:28s} no match — DROP or replace")

    (HERE / "citations_verified.json").write_text(
        json.dumps(verified, indent=2)
    )
    (HERE / "citations_failed.json").write_text(json.dumps(failed, indent=2))
    print(f"\nverified {len(verified)}/{len(CANDIDATES)}; "
          f"failed {len(failed)}")


if __name__ == "__main__":
    main()
