# Working on this paper

This repository is a TDK paper built from the FTSRG template. The paper belongs to the student.
This file tells an agent how to build, check and change it, and where the rules are. Students
can read it too. The rules themselves are in the guide, which `draft.tex` builds after the
paper's appendices; the table at the end points into it.

## Build and check

- `make draft` (or `make all`) builds `draft.pdf`: the paper with its notes, the Checks page and
  the guide.
- `make final` builds `final.pdf`, the submission format, with no notes and no guide. On
  Overleaf, open `final.tex` and choose *Recompile from this file*. "Final" names the format: this
  PDF builds in every phase, and only `make check-submit` says it is ready.
- `make check-final` builds the final PDF and runs every lint rule on it. CI
  (`.github/workflows/paper.yml`) uses this build; lint findings (exit 1) are advisory while compilation and technical errors fail, and template regression and consistency checks must pass. Prefer it to `make check`, which lints
