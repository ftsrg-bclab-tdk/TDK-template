# Component import dispositions

This record describes committed source history imported into the monorepo, the adaptations made
for component boundaries, and source changes deliberately left out. The original code and notes
repositories were not changed.

## Code component

`code/` contains the code repository at `b993375ab89cf0e29b2ceb6a2a0f9555640c86ba`, followed by
the open PR stack in source order:

| Source intent | Source head | Disposition |
|---|---|---|
| Main | `b993375ab89cf0e29b2ceb6a2a0f9555640c86ba` | Imported with history. |
| PR #1 | `c1c63f475f6bd41ed9441bdf522ab13963802820` | Imported with history. |
| PR #2 | `7afa71b61ec0b827f69072058ef757d67c59d705` | Imported with history. |
| PR #3 | `6f0a5803fa5bbde9218ef0a92ffb070763daf08d` | Imported with history. |

The retained MIT license is attributed to Martin Farkas, the author recorded on the source commit
that introduced it. The license terms were not changed. The code hygiene tool now reads and scans
only the `code/` component when run from the monorepo. It also scans the original source history
at root paths using the imported tip recorded in `code/scripts/source-history.txt`. Its original
nested workflows remain as source; root CI does not discover them, and code checks remain disabled
until their real checks are ready. The standalone README now describes that boundary.

## Scratch component

`scratch/` contains notes-template main at `9dd2e451279f0f508ec6a2bef7996eb24d6f9343` and the
committed PR #2 head `97d4cb3562a8c635a830eb4e1d891b89bb009649`, including its draft-phase path
change and generated lifecycle report. These histories were imported without rewriting commits.
The README and lifecycle paths now describe the monorepo: the paper is `paper/draft.tex`, code is
under `code/`, notes are under `scratch/`, and presentation files are under `presentation/`.
Skill links point to the shared skills at the repository root.

The lifecycle check recognizes the paper's `topic`, `setup`, `research`, `plan`, `draft`, `polish`
and `submit` phases. Its recent-change rows query full history for `paper/` and `code/` separately.
Age zero is recent. Shallow or missing path history is reported as unknown and does not fail a due
recentness row. The nested lifecycle workflow is retained as source but inactive; root
`project.json` leaves scratch checks disabled until their checks are ready.

## Notes changes not imported

The local notes commit `6665d1d8291d67f15868bf09a4f169611dd8602c` was assessed and not imported.
It moved reviewer personas into a separate skill and narrowed self-score. The monorepo now keeps
those shared skills in root `.claude/skills/`, with CI-bundle inputs and current paper paths. The
notes commit's skill snapshot and README update are superseded by that shared implementation; its
separate persona set is not copied into `scratch/`.

The notes source checkout's 11 dirty status entries were left untouched and excluded. They remain
in `/home/blacklight/Projects/TDK/tdk-notes-template`:

- Modified `.claude/skills/self-score/SKILL.md`.
- Deleted `.claude/skills/self-score/personas/{bpm-expert,business-expert,champion,cryptographer,faculty-generalist,mathematician,reviewer-two,systems-engineer}.md`.
- Modified `README.md`.
- Untracked `.claude/skills/reviewer-passes/` directory, including its skill and persona files.

These uncommitted revisions remain deferred in the source checkout. They were not copied or
represented as accepted monorepo behavior.
