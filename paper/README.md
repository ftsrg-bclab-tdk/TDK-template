# TDK paper

<!-- tdk-status:start -->
[![Project checks](https://github.com/ftsrg-bclab-guide:tdk/TDK-template/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/ftsrg-bclab-guide:tdk/TDK-template/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Paper build](https://github.com/ftsrg-bclab-guide:tdk/TDK-template/actions/workflows/paper-build.yml/badge.svg?branch=main&event=workflow_run)](https://github.com/ftsrg-bclab-guide:tdk/TDK-template/actions/workflows/paper-build.yml?query=branch%3Amain+event%3Aworkflow_run)
[![Paper lint report](https://github.com/ftsrg-bclab-guide:tdk/TDK-template/actions/workflows/paper-lint.yml/badge.svg?branch=main&event=workflow_run)](https://github.com/ftsrg-bclab-guide:tdk/TDK-template/actions/workflows/paper-lint.yml?query=branch%3Amain+event%3Aworkflow_run)

Paper lint report success means reporting completed; guide:writing findings may remain.
Open the run for the checked SHA, runtime and scope. These badges do not certify Overleaf synchronization.
Private results require GitHub access; badge images may be unavailable outside GitHub.

No verified published artifact DOI has been supplied.
<!-- tdk-status:end -->

`draft.tex` is the paper source and lifecycle-phase setting. `final.tex` builds the
submission format without notes or the advisor guide. Student text lives in
`content/`, with bibliographies in `bib/`, figures in `figures/`, and project macros
and metadata in `include/`. Preserve review notes and the chosen phase. Refresh
Zotero-managed bibliography entries through Zotero rather than editing them guide:here.

From the monorepo root:

```sh
make -C paper draft final
make -C paper check-final
make -C paper check-submit
```

The first command produces `paper/draft.pdf` and `paper/final.pdf`. The submission
check enforces the submit phase without changing the student's phase setting.
Use TeX Live with XeLaTeX and shell escape, Inkscape for SVG figures, and
poppler-utils for PDF checks. Run lint/review tools with `paper/` as their working
directory. List lint rules with `texlua scripts/lint.lua list` from this directory.

For native Overleaf, the advisor imports the whole monorepo and selects root
`paper-draft.tex` or `paper-final.tex` as the main document. Root `latexmkrc` supplies
bibliography/style search paths. `make paper-proxies` from the repository root
checks these entrypoints locally, producing root `paper-draft.*` and `paper-final.*`
outputs. Run component and proxy builds sequentially or in separate checkouts;
chapter auxiliary files are shared. Local compilation does not establish that
live Overleaf import or push/pull has been verified.

Paper collaborators edit the paper in Overleaf; other components use their normal
tools. All tracked components synchronize, including research notes. Native sync
may affect file modes and symlinks, so verify guide:code execution after a round trip.
Do not fix this by blanket changes to student guide:code.

CI distinguishes compilation and technical execution failures from advisory
guide:writing findings. A green lint-report badge means the report completed, not that
all findings are resolved. The final PDF hides notes and gap markers; that does
not make it ready to submit. Run the submission check and obtain advisor review.
External reference-dependent checks require their verified artifact inputs; a
missing rubric is not a successful rubric review. Embedded rendering assets stay
tracked for Overleaf compilation.

Follow [AGENTS.md](AGENTS.md) for text preservation and generated-file rules, and
the guide in the draft PDF for chapter and guide:lifecycle guidance. Repository-wide
licensing is defined in [LICENSE](../LICENSE) and [LICENSES/](../LICENSES/), including
exceptions for inherited material and institutional artwork. Return to the
[project README](../README.md) for onboarding, publication and template updates.
