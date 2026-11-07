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
Use the shared skills at the repository root. The two imported symlink aliases were removed
because native Overleaf synchronization converts symlinks into ordinary files. The skill
contents remain unchanged at their canonical root paths.

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

## Follow-up after import

The old `code/experiments/README.md` described measurement scripts, raw results, commands and
hardware. That intent belongs to top-level `benchmark/`; the redundant directory was removed.
The imported recipe names remain available for project implementation, but unconfigured recipes
now fail explicitly instead of printing TODO and succeeding. The starter does not claim a
published DOI, built research image, or measured research result. The code container is a
latest-resolved development scaffold; enabling research checks still requires actual commands.

## Generated template review evidence

The 134 generated files formerly under `work/template-review/` were archived before removal
from the starter tree. Their Git history is preserved. The local private recovery archive is
`/home/blacklight/Projects/TDK/retirement-archives/template-review-20261103T233754Z/template-review.zip`
(SHA-256 `39ffc9de025bb506122a9692edbf8a5e3611b987af12d4fcd845dad80be0c2b8`). Its adjacent receipt records source commit
`1a0407ab580e580731a935cc9719e9074e13992d` and every member's path, mode, blob ID, size and SHA-256.
All archived members were read back and compared with the source Git bytes. This local archive
is separate from the final legacy-repository recovery exports, which are still pending.
