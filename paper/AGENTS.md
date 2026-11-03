# Working on this paper

This repository is a TDK paper built from the FTSRG template. The paper belongs to the student.
This file tells an agent how to build, check and change it, and where the rules are. Students
can read it too. The rules themselves are in the guide, which `draft.tex` builds after the
paper's appendices; the table at the end points into it.

Paths and commands below are relative to `paper/` unless marked as root paths.
From the monorepo root, use `make -C paper <target>` or the root Makefile delegation.
For Overleaf, select root `paper-draft.tex` or `paper-final.tex`; edit `draft.tex` here.

## Build and check

- `make draft` (or `make all`) builds `draft.pdf`: the paper with its notes, the Checks page and
  the guide.
- `make final` builds `final.pdf`, the submission format, with no notes and no guide. On
  Overleaf, open root `paper-final.tex` and choose *Recompile from this file*. "Final" names the format: this
  PDF builds in every phase, and only `make check-submit` says it is ready.
- `make check-final` builds the final PDF and runs every lint rule on it. CI
  (`../.github/workflows/ci.yml`) reports writing findings as advice. Compilation failures,
  technical errors, and failed template regression or consistency checks fail CI. Local check
  targets remain strict. Prefer it to `make check`, which lints
  the draft build. `make check-submit` does the same at the `submit` phase whatever
  `\lintphase` says: the check before upload.
- `texlua scripts/lint.lua list` lists the rules with their severity and phase; `make lint-<rule>`
  runs one.
- The toolchain is TeX Live with XeLaTeX and shell escape, Inkscape for SVG figures, and
  poppler-utils for the PDF rules.

## The phase

`\lintphase` in `draft.tex` is the student's phase in the lifecycle: `topic`, `setup`,
`research`, `plan`, `draft`, `polish` or `submit`. Checks become required as the phase
advances, and any other value stops the lint. Change it only when the student asks. The phases
and their steps are in `guide/02-lifecycle.tex` (`tab:lifecycle`).

## Files

- The student's: `content/` (chapters, abstract, glossary, AI declaration), `bib/references.bib`,
  `figures/`, `include/macros.tex` and `include/tdk-variables.tex`. `draft.tex` is shared: the
  student sets the title, `\lintphase` and the chapter list; template updates change the rest.
- `bib/zotero.bib` comes from the Zotero group library through Overleaf, and *Refresh*
  overwrites it. Correct entries in Zotero, not in this file.
- The template's, replaced by template updates: `guide/`, the rest of `include/`, `scripts/`,
  root `.github/`, root `.claude/skills/`, `docs/`, `final.tex`, `Makefile`, `tdkieee.bst`, `README.md`
  and this file.
- Generated, never edited by hand: `guide/essentials.tex`, `guide/guide.bbl`, `lint-checks.tex`
  and `scripts/lint/skeleton/`.
- Maintainer targets, never run in a paper repository: `make skeleton`, `make essentials` and
  `make guide-bib`. `make skeleton` would make the lint treat the student's text as the template's.
- Never commit build output such as PDFs, logs or `.aux` files; the `repo-hygiene` rule fails on it.
- The student edits on Overleaf, which syncs with this repository only when someone pulls or
  pushes from Overleaf's GitHub menu. After you push, the student pulls in Overleaf before
  editing there.

## Changing the student's text

- The person running you decides what you may change in their own text.
- In a template update, apply only named mechanical changes, such as a renamed macro. Show every
  other deletion or rewrite for review instead of applying it.
- When a paper repository still has `thesis.tex` and `reviewer.tex`, the update renames them:
  run `git mv thesis.tex draft.tex` and take `final.tex` from the template in place of
  `reviewer.tex`. In `include/macros.tex` and `content/`, replace `\reviewermode` with `\finalmode`
  and `thesis.tex` with `draft.tex`. The student then sets root `paper-draft.tex` as the main document in
  Overleaf's menu.
- Keep the notes. `\todo` (orange) is for the student, `\advisortodo` (blue) for the advisors, and
  `\atodo` (green) is an advisor's review comment that the student resolves and then deletes.
- Mark a gap with `\tbd{...}` or `\citeneeded[...]`, never with a typed TBD, [CITE] or XXX.
- Check every source you suggest before it is cited. By the advisors' rule, an AI answer never goes in the
  bibliography; it goes in the AI declaration (`guide/04-writing.tex`, `app:writing:ai`).

## Markup the lint reads

- Chapters are found by their labels, such as `ch:intro` and `ch:conclusion`, not by file name.
- Tagged lists and their label prefixes: `requirements` (`req:`), `derivedrequirements` (`dr:`),
  `contributions` (`c:`), `threats` (`thr:`), `assumptions` (`asm:`), `guarantees` (`g:`),
  `rqlist` (`rq:`) and `limitations` (`lim:`).
- Abbreviations, symbols and terms go through `\gls` (`guide/09-latex-template.tex`, `app:latex:acro`).

## Where the guidance is

| To find | Look in |
| --- | --- |
| Where to start, by situation | `guide/00-start-here.tex` (`app:here`) |
| What each chapter must contain, with a worked example | `guide/05-chapter-by-chapter.tex` (`app:chapters`) |
| The elements the lint measures in every paper | `guide/04-writing.tex` (`app:writing:essentials`) |
| What must hold before upload | `guide/02-lifecycle.tex` (`tab:polish`) |
| What the draft and final builds contain, and what reads each | `guide/07-code-tools-checks.tex` (`app:code:builds`) |
| What each lint rule checks | `guide/07-code-tools-checks.tex` (`app:code:paperci`) |
| Reviewer passes: what they are and when to run them | `guide/02-lifecycle.tex` (`app:lifecycle:reviewers`) |
| Running the reviewer passes and self-score | `guide/07-code-tools-checks.tex` (`app:code:reviewers`) |
| AI use and the declaration | `guide/04-writing.tex` (`app:writing:ai`) |
| The faculty's dates, form rules and review sheet | `guide/06-tdk-rules-and-dates.tex` (`app:tdk`) |
| LaTeX syntax: notes, glossary, citations, figures, listings | `guide/09-latex-template.tex` (`app:latex`) |
