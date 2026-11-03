# Research notes and consultations

This directory holds the student's research anchors and consultation summaries. The paper,
code and presentation live in their components at the repository root; they are not submodules.

```
scratch/
  notes/anchors/       topic manifest, spine and full-draft anchors
  notes/consultations/ one dated summary per consultation
  slides/README.md     notes about preparing talks
  lifecycle.md         generated lifecycle inventory
```

Create the student's project as a private repository from the public template after its contents
and disclosure are reviewed. Keep paper edits in `paper/`, code in `code/`, and presentation
materials in `presentation/`. After each consultation, add
`scratch/notes/consultations/YYYY-MM-DD.md` with the decisions, student actions and advisor
actions.

## Lifecycle inventory

Run `python3 scratch/scripts/lifecycle.py` from the repository root to regenerate
`scratch/lifecycle.md`. It reads the phase from `paper/draft.tex` and checks paths in the monorepo.
Recent-change rows use Git history for `paper/` and `code/`; they show `unknown` when history is
shallow or the path has no recorded commit. A zero-day age counts as recent.

The standalone lifecycle workflow remains under `scratch/.github/workflows/` as source. GitHub
does not discover nested workflows, and root `project.json` currently leaves scratch checks
disabled until their checks are ready.

## Review skills

The shared `self-score` and `reviewer-passes` skills live in the root `.claude/skills/` directory.
The links in `scratch/.claude/skills/` point there. `self-score` scores the final PDF against the
review sheet. `reviewer-passes` reads the paper from the perspective of its skim reviewer and
expert reviewers. Name `scratch/notes/anchors/spine.md` when running a review. Both use the
paper CI evidence for one commit and do not edit the paper.
