# Paper layout verification

The paper move and build adaptations are committed in `7f84853847efdc1b7e9f6df634105b1daf62cdfb`, based on coordinator commit `17fa89072315e039931c4b9a5e2a7e9211b973e8`. Follow-up `4a065f1` fixes historical lint-script replay from the nested directory and adds its regression test. No push, main merge or live Overleaf action was performed.

## Paths and build contract

- Component source: `paper/draft.tex`, with submission-format wrapper `paper/final.tex`.
- Component commands: `make -C paper draft final`; output PDFs, logs and top-level auxiliary files are `paper/draft.*` and `paper/final.*`.
- Root entrypoints: `paper-draft.tex` and `paper-final.tex`. `make paper-proxies` compiles them with XeLaTeX and shell escape, producing root `paper-draft.*` and `paper-final.*`.
- Root `latexmkrc` adds `paper//` to BibTeX's bibliography/style search paths while retaining default search paths. Without it, latexmk returned zero while leaving unresolved citations; the verification below checks the logs and text as well as exit status.
- Root `make draft final` delegates to the paper Makefile. Paper-specific scripts, reference documents, guide and assets live under `paper/`; generic scripts, agent skills, workflows, infrastructure and presentation remain at root.
- Root proxies import the corresponding paper source and set `paperroot=paper/`, `paperbuilddir=..`. The draft's shell helper changes into the paper directory and runs `texlua scripts/lint.lua overleaf --dir .. --doc paper-draft --tex > lint-checks.tex`. TeX then reads `paper/lint-checks.tex`. Component builds use `.` and their own job name.
- Chapter auxiliary files stay beside their paper sources. The root proxy's top-level `.aux` records `paper/...` paths; component `.aux` records component-relative paths. Build the routes sequentially in a shared checkout, or use separate checkouts, because chapter auxiliary files are shared.
- Lint/review/skim commands run with `paper/` as cwd. JSON source paths remain paper-relative; plain GitHub annotations resolve to root-relative paths. Git hygiene discovers the parent Git root and scans tracked files repository-wide. Root proxies' generated PDFs are ignored and are detected if force-tracked.
- Root `AGENTS.md` routes paper work to complete `paper/AGENTS.md`; phase, student-text, generated-file and Zotero rules are preserved. Student sources, phase, bibliography and figure bytes are unchanged from the base.

## Actual clean builds

Two independent clones of the committed source were created under `/tmp/tdk-layout-evidence/`, avoiding any earlier build output. Both used this resolved image:

```text
danteev/texlive@sha256:0d9a3e04eb3a6918c64c502c2129e9ffbf5ec0c55ea74f0eff277bc564ae5c41
```

Commands run from the implementation worktree:

```bash
git clone --quiet --no-hardlinks --single-branch \
  --branch feat/automate-overleaf-repo-workflow "$PWD" /tmp/tdk-layout-evidence/component
git clone --quiet --no-hardlinks --single-branch \
  --branch feat/automate-overleaf-repo-workflow "$PWD" /tmp/tdk-layout-evidence/proxy

docker run --rm --user "$(id -u):$(id -g)" \
  -v /tmp/tdk-layout-evidence/component:/work -w /work \
  danteev/texlive@sha256:0d9a3e04eb3a6918c64c502c2129e9ffbf5ec0c55ea74f0eff277bc564ae5c41 \
  bash -c 'make -C paper draft final > /work/component-build.log 2>&1'

docker run --rm --user "$(id -u):$(id -g)" \
  -v /tmp/tdk-layout-evidence/proxy:/work -w /work \
  danteev/texlive@sha256:0d9a3e04eb3a6918c64c502c2129e9ffbf5ec0c55ea74f0eff277bc564ae5c41 \
  bash -c 'make paper-proxies > /work/proxy-build.log 2>&1'
```

Both commands exited zero. Each route produced a 126-page draft and a 23-page final PDF. `pdftotext -layout` produced identical draft text across routes and identical final text across routes. All four TeX logs had zero TeX errors, zero undefined citations and zero undefined references. The proxy log confirms execution of the paper-cwd lint helper and loading of the generated Checks page. BibTeX resolved `tdkieee.bst` and both bibliography files. The real draft exercised the SVG example, guide graphics, listings and glossary sorting. Existing nonfatal template warnings remain; this is build verification, not a claim of submission readiness.

PDF/log/text hashes and evidence-log hashes are in [paper-layout-evidence.json](paper-layout-evidence.json). Raw outputs remain outside Git in `/tmp/tdk-layout-evidence/` and are local evidence, not durable published artifacts.

## Lint, regression tests and review bundle

With cwd `/work/paper` in the clean component clone, the following commands ran inside the same image. `/evidence` was mounted from `/tmp/tdk-layout-evidence/results`:

```bash
LINT_OFFLINE=1 texlua scripts/lint.lua all --doc final --json \
  > /evidence/lint.json 2> /evidence/lint.stderr
make test-lint
python3 -m pip install --target /tmp/layout-deps pymupdf
PYTHONPATH=/tmp/layout-deps make test-review test-layout
PYTHONPATH=/tmp/layout-deps python3 scripts/skim/skim.py build . \
  -o /evidence/skim --lint /evidence/lint.json
python3 scripts/review/review.py bundle --built . \
  --lint /evidence/lint.json --lint-stderr /evidence/lint.stderr \
  --skim /evidence/skim --out /evidence/review-bundle --by local \
  --repo FTSRG-BCLab-TDK/TDK-template --image-ref danteev/texlive:latest \
  --image-digest sha256:0d9a3e04eb3a6918c64c502c2129e9ffbf5ec0c55ea74f0eff277bc564ae5c41 \
  --exit draft=0 --exit final=0 --exit lint=0 --exit skim=0
```

The TeX image lacks PyMuPDF; the isolated installation resolved PyMuPDF 2.1 and its dependencies, recorded in `results/dependencies.log`. No host package installation or source change was needed.

Results:

- Lint returned 0 with valid JSON and 52 rule results. Frame, build and repo hygiene passed; hygiene reported zero tracked outputs. No rule crashed. The link check was explicitly skipped because this run was offline; writing findings remain visible at their applicable phases.
- Mutation suite: zero missed cases. Fault-injection and CI exit-status tests passed. Evidence suite: 115/115. Safety-reader suite: 210/210.
- Review/skim unit tests: 36 passed. Initial layout tests: 2 passed. Follow-up layout suite: 3 passed, including current-Git script replay. Replay of the selected baseline case passed for both the monorepo HEAD and pre-move `17fa890`.
- Skim rendered the final PDF: 23 pages, 10 main pages, matched figure/table/tag counts, zero unsure detections and zero unclassified lines.
- The 37-file review bundle verified against the source SHA with no integrity problems. Its manifest records a clean local build, not a CI run.

The parent-Git regression force-tracks component and root generated PDFs plus root private agent settings in a temporary repository, verifies that hygiene fails from `paper/`, permits the tracked guide bibliography, and checks root-relative annotations. Persona lookup is tested against root `.claude/skills/`.

For CI, `--by ci` additionally requires the run identity (`GITHUB_RUN_ID`, repository/ref/source SHA) and the actual exit codes. The bundle command's paths can be component-local or explicit absolute paths, but `--built .` requires paper cwd. `all --json` returns top-level `ok`, phase/profile/doc, `rules`, `findings`, chapter roles and tag lists, plus essentials fields when available. A crashed rule has `status: "error"` and process exit 2; there is no separate serialized technical-error boolean. Invalid setup can exit 2 before valid JSON, so absent/malformed JSON also fails CI. Ordinary rule findings return 0 or 1. The CI owner received this contract and owns root workflow/config integration.

## Remaining native-only verification

The Docker results do not prove Overleaf main-document selection, native GitHub import, collaborator permissions, live push/pull or conflict recovery. The later disposable native pilot must test those, including execute-bit resets, symlinks, tracked-tree budgets, Zotero refresh and real code execution after the round trip. No custom bridge is involved.

Root `.github` workflows and generic CI configuration were deliberately left to the CI owner and require the coordinated path adaptation before the full monorepo workflow runs. External reference bytes remain tracked under `paper/docs/`; artifact-fetch consumer migration is still pending verified packages. Several guide passages still describe the older multi-repository workflow; broader mechanical guide-policy updates remain coordinator work, not student prose changes in this relocation.
