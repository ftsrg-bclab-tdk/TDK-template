# Working in the TDK monorepo

The paper belongs to the student. For paper builds, lint, review, template updates or edits
under `paper/`, read `paper/AGENTS.md` before proceeding. It retains the complete paper rules,
markup conventions and pointers into the guide.

Keep the student's prose and review notes. Change `\lintphase` in `paper/draft.tex` only when
the student asks. Zotero refresh overwrites `paper/bib/zotero.bib`; correct imported entries
in Zotero. Apply only named mechanical changes during template updates; show other proposed
student-text rewrites for review. Never hand-edit generated template files or commit build output.

Paper sources and tooling are in `paper/`. Root `paper-draft.tex` and `paper-final.tex` are
Overleaf compilation entrypoints. `make draft final` delegates to `make -C paper draft final`;
`make paper-proxies` tests the root entrypoints. Generic onboarding, release, CI and external-input
automation stay in root `scripts/`; workflows stay in root `.github/`.

Native Overleaf GitHub synchronization transfers the whole repository when a collaborator
pulls or pushes in Overleaf. After a GitHub push, pull in Overleaf before editing the paper there.
Code, proof, benchmark and scratch work uses its normal tools. This editing convention does
not prevent Overleaf from changing executable modes or symlinks; verify round trips before use.
