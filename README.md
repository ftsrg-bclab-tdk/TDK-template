---
role: paper-template
canonical: https://github.com/FTSRG-BCLab-TDK/TDK-template
mirror: https://github.com/FTSRG-BCLab-TDK/tdk-paper-template
overleaf: https://www.overleaf.com/project/6aa7d78f4bf131387fb7c710
related:
  notes: https://github.com/FTSRG-BCLab-TDK/tdk-notes-template
  code: https://github.com/FTSRG-BCLab-TDK/tdk-code-template
---

# FTSRG TDK paper template

This is the FTSRG advisors' LaTeX template for a TDK paper at BME VIK. The advisors'
guide is included in the draft PDF. **This repository is the canonical source.** The
template's Overleaf project is synced with it through Overleaf's GitHub integration.
Advisors create each private student repository in the lab organization, then import it
through native Overleaf GitHub synchronization and invite the project collaborators.
The whole repository synchronizes; collaborators edit the paper in Overleaf and use
their normal tools for the other components.

Use `main` here for template maintenance. The public
[tdk-paper-template](https://github.com/FTSRG-BCLab-TDK/tdk-paper-template) is a mirror
of the same source. Overleaf receives updates through its GitHub sync menu.

- `paper/draft.tex` builds the draft with notes, the Checks page and the guide.
  The chapter files contain headings, stubs and notes linking to
  "The paper, chapter by chapter" in `paper/guide/05-chapter-by-chapter.tex`, where the
  instructions and worked examples live. `paper/final.tex` builds the PDF in submission
  format. It hides the notes and gap markers, so how it looks says nothing about
  readiness: it is ready to upload only when `make check-submit` passes and the advisors
  have reviewed it.
- Within `paper/`, `content/` holds the chapters, abstract, glossary, contribution statement and AI declaration; `guide/` holds
  the advisors' guide; `include/` the preamble; `bib/` the bibliographies; and `docs/`
  the review sheet.
- `paper/scripts/lint.lua` checks the paper. From `paper/`, `texlua scripts/lint.lua list` lists the rules,
  and `make check` runs them. `.github/workflows/paper.yml` runs each rule as a
  separate step on every push to main and every pull request that is not a draft.
- Set `\lintphase` in `paper/draft.tex` to your current lifecycle phase. Checks become
  required as you reach each phase.

The companion templates are [tdk-notes-template](https://github.com/FTSRG-BCLab-TDK/tdk-notes-template)
for the notes repository and [tdk-code-template](https://github.com/FTSRG-BCLab-TDK/tdk-code-template)
for the code repository. The guide explains all three after the draft's appendices.

Select root `paper-draft.tex` or `paper-final.tex` in Overleaf. The small root proxies
import the paper sources; root `latexmkrc` supplies bibliography/style search paths.
Build both proxies locally with `make paper-proxies`. Root proxy PDFs/logs are
`paper-draft.*` and `paper-final.*`; component build PDFs/logs are in `paper/`.
Paper lint and review commands run with `paper/` as their working directory.

Build locally with `make -C paper draft final`, or use root `make all` for the draft and `make final` for the final PDF.
Use TeX Live with XeLaTeX, Inkscape and shell escape enabled.
`make check-final` runs the lint on the final build, and `make check-submit` runs it
at the submit phase: the check before you upload.
