"""Build the submission packages from the canonical manuscript.

Nothing here is hand-authored twice. The JQAS manuscript is derived from
overexpected.tex by transformation, so the two cannot drift on any number, and
the anonymised copy is derived from the JQAS copy for the same reason.

Requirements encoded below are from the JQAS "Instructions for Authors"
(De Gruyter, last update 2025-03-03) and the SSAC research-paper competition
rules, both read on 2026-08-02. Sources are cited in SUBMISSION_CHECKLIST.md.

Outputs, all under paper/submission/:
  jqas/          manuscript (blinded + unblinded), title page, cover letter,
                 declarations, bib with issue numbers stripped, raster figures
  zenodo/        deposit metadata, description, file manifest
  sloan/         abstract-round package
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "submission"
FIGS = HERE / "figures"

TITLE_SENTENCE = ("Adjustments that do not adjust: measuring shooting-foul "
                  "drawing in the NBA from public play-by-play")
SHORT_TITLE = "Adjustments that do not adjust"          # 30 chars, limit 75


def jqas_manuscript(src: str, blinded: bool) -> str:
    s = src

    # JQAS: 8.5 x 11 inch paper, 1 inch margins.
    s = s.replace("\\documentclass[11pt,a4paper]{article}",
                  "\\documentclass[11pt,letterpaper]{article}")

    # JQAS: title and headings in sentence case, lowercase after colon.
    s = s.replace(
        "\\title{\\bfseries Adjustments That Do Not Adjust:\\\\\n"
        "Measuring Shooting-Foul Drawing in the NBA\\\\\n"
        "from Public Play-by-Play}",
        "\\title{\\bfseries Adjustments that do not adjust:\\\\\n"
        "measuring shooting-foul drawing in the NBA\\\\\n"
        "from public play-by-play}")

    # JQAS: abstract is a single paragraph, max 250 words.
    a0, a1 = s.index("\\begin{abstract}"), s.index("\\end{abstract}")
    ab = s[a0:a1]
    ab_single = re.sub(r"\n\n+", " ", ab)
    s = s[:a0] + ab_single + "\n" + s[a1:]

    # Running head.
    s = s.replace("\\begin{document}",
                  "\\usepackage{fancyhdr}\n"
                  "\\pagestyle{fancy}\\fancyhf{}\n"
                  f"\\fancyhead[L]{{\\small {SHORT_TITLE}}}\n"
                  "\\fancyfoot[C]{\\thepage}\n"
                  "\\renewcommand{\\headrulewidth}{0pt}\n\n"
                  "\\begin{document}")

    if blinded:
        # Double-anonymised review: strip every identifying trace.
        s = s.replace(
            "\\author{Kevin Krajnc\\thanks{Independent researcher.\n"
            "\\texttt{kevin@aandrs.at}. Code, model artifacts and the scripts "
            "producing every\nfigure and table: "
            "\\url{https://github.com/quickstock/Over-Expected}.}}",
            "\\author{}")
        s = s.replace("\\date{\\today}", "\\date{}")
        # The repository URL identifies the author; replace, do not delete, so
        # the reviewer still knows the artifact exists.
        s = s.replace(
            "All model artifacts, validation scripts and the code producing "
            "every figure and\ntable are in the repository named on the title "
            "page.",
            "All model artifacts, validation scripts and the code producing "
            "every figure and\ntable are in a public repository, withheld here "
            "for anonymous review and\nsupplied to the editor.")
    return s


def strip_issue_numbers(bib: str) -> str:
    """JQAS reference style: issue numbers are not permitted."""
    out, dropped = [], 0
    for line in bib.splitlines(keepends=True):
        if re.match(r"\s*number\s*=", line):
            dropped += 1
            continue
        out.append(line)
    # A dangling comma before a closing brace breaks BibTeX.
    txt = re.sub(r",(\s*\n\s*)\}", r"\1}", "".join(out))
    print(f"  stripped {dropped} issue-number fields from the bibliography")
    return txt


def main() -> None:
    for d in ("jqas", "zenodo", "sloan"):
        (OUT / d).mkdir(parents=True, exist_ok=True)

    src = (HERE / "overexpected.tex").read_text()
    bib = (HERE / "references.bib").read_text()

    print("JQAS package:")
    (OUT / "jqas" / "manuscript_anonymised.tex").write_text(
        jqas_manuscript(src, blinded=True))
    (OUT / "jqas" / "manuscript_with_authors.tex").write_text(
        jqas_manuscript(src, blinded=False))
    (OUT / "jqas" / "references.bib").write_text(strip_issue_numbers(bib))

    figdir = OUT / "jqas" / "figures"
    figdir.mkdir(exist_ok=True)
    shutil.copytree(FIGS, figdir, dirs_exist_ok=True)
    # Journal wants figures named by their order in the manuscript.
    order = {"fig1_xfg_reliability": "Figure 1",
             "fig2_ftaoe_reliability": "Figure 2",
             "fig3_adjustments": "Figure 3",
             "fig4_height_gradient": "Figure 4"}
    named = figdir / "named_for_upload"
    named.mkdir(exist_ok=True)
    for stem, label in order.items():
        srcpng = FIGS / "raster_300dpi" / f"{stem}.png"
        if srcpng.exists():
            shutil.copy(srcpng, named / f"{label}.png")
    print(f"  {len(list(named.glob('*.png')))} figures named for upload "
          f"(400 dpi PNG)")

    # Zenodo takes the compiled PDF plus the source bundle.
    zsrc = OUT / "zenodo" / "source"
    zsrc.mkdir(exist_ok=True)
    for f in ("overexpected.tex", "references.bib", "make_bib.py",
              "make_figures.py", "verify_citations.py", "audit_citations.py",
              "citations_verified.json", "claims_ledger.md",
              "review_findings.md", "experiment_record.md"):
        if (HERE / f).exists():
            shutil.copy(HERE / f, zsrc / f)
    shutil.copytree(FIGS, zsrc / "figures", dirs_exist_ok=True)
    for pdf in ("overexpected.pdf", "overexpected_conference.pdf"):
        if (HERE / pdf).exists():
            shutil.copy(HERE / pdf, OUT / "zenodo" / pdf)
    print(f"Zenodo package: source bundle + "
          f"{len(list((OUT / 'zenodo').glob('*.pdf')))} PDFs")

    if (HERE / "sloan_abstract.md").exists():
        shutil.copy(HERE / "sloan_abstract.md", OUT / "sloan")
    sfig = OUT / "sloan" / "figures"
    sfig.mkdir(exist_ok=True)
    for stem in ("fig3_adjustments", "fig4_height_gradient"):
        shutil.copy(FIGS / "raster_300dpi" / f"{stem}.png", sfig)
    print("Sloan package: abstract + the two permitted figures")


if __name__ == "__main__":
    main()
