# Native Overleaf monorepo pilot contract

Updated 2026-11-03 following the coordinator's latest direction. The current plan is native whole-monorepo GitHub synchronization, with the paper edited in Overleaf by appropriate project collaborators. Code, proof, benchmark, scratch and other components are edited through their normal tools. Keep paper sources in `paper/` and use uniquely named small root compilation entrypoints. No custom bridge or separate paper repository is in scope. The [withdrawn bridge proposal](overleaf-bridge-withdrawn.md) is historical evidence only.

The paper layout and root entrypoints are implemented and locally Docker-verified; see [paper-layout-verification.md](paper-layout-verification.md). This remains a native pilot contract, not evidence that live Overleaf integration works. No live configuration or resource actions are authorized here. The finished TDK-template will become the single public reusable template after its contents and history are prepared for disclosure. Student repositories remain private and organization-owned. Advisors handle repository/access setup, premium Overleaf import/invitations and Zotero group setup; students handle accounts, required Git/Python/gh/Docker, invitation acceptance, cloning and workspace setup. Compilation and synchronization are verified jointly. These assignments do not authorize unrequested live configuration or publication actions. Existing student migration remains long-term only.

## Layout and compilation

The monorepo retains `paper/`, `code/`, `scratch/`, `proof/`, `benchmark/` and `presentation/`. `scratch/` is version-controlled research work, with temporary outputs and secrets ignored and default publication exclusion. Proof profiles remain optional, with their catalog handled separately. All tracked components are included in native synchronization, including scratch material; exclusion from publication does not exclude a file from Overleaf.

Keep paper dependencies self-contained under `paper/` where practical. At the monorepo root, provide uniquely named draft/final entrypoints that import the corresponding paper documents. The entrypoints are `paper-draft.tex` and `paper-final.tex`, importing `paper/draft.tex` and `paper/final.tex`. Do not duplicate a root entrypoint basename inside `paper/`.

Overleaf documents a root proxy using `\RequirePackage{import}` followed by `\import{paper/}{manuscript.tex}`. Its warning about nested main documents and basename collisions supports this candidate, but does not prove the complete template works. Verify main-document selection explicitly: the documentation normally expects a document-class declaration while its proxy example imports that declaration indirectly.

Source: [The Main document](https://docs.overleaf.com/getting-started/recompiling-your-project/the-main-document).

The existing paper launches `texlua scripts/lint.lua` from `include/preamble.tex` and loads Lua modules relative to the paper directory. An import proxy does not change a shell process's working directory. Implementation must establish the paper working directory for lint and arrange the generated output path that TeX reads. Test bibliography/style resolution, guide bibliography, SVG conversion, listings, chapter auxiliary files and draft/final inclusion. Local component builds and root proxy builds need consistent results. Do not hand-edit generated template resources.

## Native synchronization and file constraints

Native GitHub sync operates on the repository, is initialized by the premium project owner and is triggered through Overleaf. Repository visibility to the linked account and any organization OAuth approval must be checked. The intended Overleaf editing scope is the paper, not the other synchronized components. This is a workflow convention, not a permission boundary or a guarantee that synchronization preserves file modes or symlinks. Students are outside collaborators with WRITE access to their own GitHub project only; advisors manage settings/access. The advisor imports and invites the appropriate Overleaf collaborators; record the actual premium owner and project participants during setup. Native sync still needs a two-direction round trip because Git-side edits can diverge from collaborators' Overleaf edits; verify access and editing/sync behavior for the roles once agreed.

Overleaf documents automatic commits resetting executable permissions, symlinks becoming ordinary files, no Git LFS/submodules, and conflict branches requiring a merge. Tracked changes/comments can be displaced by synchronization. Its recommendations include fewer than 100 changed files per commit and total project size below 100 MB; these recommendations are not hard limits.

Source: [GitHub synchronization](https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/github-synchronization).

Our scripts may use explicit interpreters such as `python3 path/to/script.py` and `bash path/to/script.sh`. Audit actual invocation sites in CI, Makefiles, recipes and documentation. Interpreter invocation does not establish compatibility for arbitrary student code, binaries, scripts executed as subprocesses, or programs relying on symlinks. Do not blanket chmod, flatten symlinks, set global Git options, or silently rewrite student code. Unsupported objects or mode-dependent execution are concrete findings to resolve before pilot acceptance.

## Budgets and tracked content

Measure the entire tracked tree at the tested SHA, including code, scratch, proof, benchmark and presentation. Record file count, total bytes, estimated editable bytes, largest editable files, executable modes, symlinks, gitlinks and LFS pointers. Compare against the documented 2,000-file limit, 7 MB editable-content limit and 2 MB individual editable-text limit. Record remaining capacity and the recommended below-100-MB Git project target. Local editable classification is an estimate; verify actual Overleaf classification/import behavior.

Source: [Plan limits](https://docs.overleaf.com/getting-started/free-and-premium-plans/plan-limits).

Keep embedded paper rendering assets tracked, as explicitly accepted. Keep Dockerfiles and build configuration as source; record built image digests as evidence. Immutable GitHub Releases do not themselves freeze GHCR tags. Keep large datasets, build outputs, dependency directories and secrets untracked. Ignore rules do not remove files already tracked: report those explicitly. Preserve legitimate tracked compile inputs, including generated template resources that the paper requires. Track representative small evaluation inputs and provenance where appropriate without assuming every benchmark result belongs in Git. Publication selection remains a separate decision.

## External references and source Checks

The coordinator's `docs/external-input-inventory.md` identifies three faculty documents as candidates for verified artifact packages. The review sheet is currently a literal requirement in `scripts/lint/rules-source.lua` and an input to skim/review tooling; the draft invokes the source lint inside Overleaf. Moving that file therefore requires an explicit check-contract change, not just a CI download.

Distinguish these results in the Checks page and evidence:

- Source-only validation can check reference metadata structure and declared links. It may verify file integrity only when the actual bytes are available and checked against the expected digest. A recorded URL or checksum alone does not establish availability, freshness, integrity or rubric contents.
- Artifact-dependent rubric verification is unavailable when the required document is absent. Report that limitation explicitly; never convert metadata validation into a passing rubric check or claim full review from skim output that lacks the scoring bands.
- Full CI review must materialize the applicable reference package, verify its actual bytes and identity, and supply it to the review consumers before claiming rubric verification. Bind that evidence to the tested SHA, configuration and hashed logs/artifacts. Ordinary source Checks and paper compilation are not substitutes for this evidence.

Native Overleaf synchronization has no established Actions-artifact retrieval mechanism here. Do not invent automatic downloads, credentials or an artifact-materialization hook. No reference or asset may be removed under this contract update.

Seven paper graphics/screenshots are TeX inputs. Retaining embedded paper rendering assets in Git is now explicitly accepted; keep those compile inputs available through native sync. External reference documents still require materialization for full reference checks, and metadata-only Overleaf checks remain distinct. Presentation remains a separate consumer. Pilot acceptance must record which reference checks ran in Overleaf, which required CI artifacts, and whether all actual paper assets were available for compilation.

## Ownership and setup

Record the premium Overleaf owner, linked GitHub account, repository URL/default branch, project URL, compiler/TeX Live version and root entrypoints. Verify the designated owner's access and the repository's visibility through that account's integration before import. Verify the assigned advisor/student project access, including accepted invitations. This contract does not authorize changing organization OAuth policies or repository settings.

Premium ownership supplies project benefits. Reference-manager integration is account-controlled; documentation assigns refreshing imported Zotero files to the owner. Test the actual owner configuration and bibliography path. Private organization-owned student repositories and advisor-led premium Overleaf setup are accepted. Record the designated advisor account without inferring an unnamed individual or credential arrangement.

Source: [Premium features](https://docs.overleaf.com/getting-started/free-and-premium-plans/premium-features).

## Disposable pilot and acceptance evidence

Execute only when the coordinator authorizes a disposable project. No existing student project participates.

1. Freeze the integrated candidate SHA. Inventory all tracked paths, blobs and modes and record the budgets above. Include representative source, proof profile, benchmark and presentation files. Identify unsupported objects and execution-sensitive modes before import; do not silently repair them.
2. Build the paper from its component directory and through each root proxy with matching compiler/TeX Live settings. Exercise the real template, not a minimal TeX sample. Compare semantic PDF content, references, page counts and intended inclusion rules; PDF byte identity is unnecessary. Verify lint actually runs and the Checks page is not silently omitted. Exercise bibliography, glossary, guide, SVG and listings.
3. Using the designated premium project owner's account, create a new Overleaf project through native GitHub repository import. Record project/repository pairing and access evidence for the assigned advisor/student roles. Select the root entrypoint and compiler. No custom transport or additional paper repository is created.
4. Compile draft and final in Overleaf from settings and the file tree, then repeat with clean compilation cache. Check output selection, bibliography, figures, diagnostics, navigation and word count. Keep logs/PDF evidence outside committed build output. Presentation compilation is tested in coordination with its separate workstream, without assuming paper success proves it.
5. Commit a uniquely marked paper edit on GitHub and pull it in Overleaf. Make a different paper edit as an authorized project collaborator in Overleaf and push through native sync. Inspect all resulting commits, including automatic permission resets. Compare every unrelated blob and mode to the baseline, including scratch/proof/benchmark/code assets. Record each transformation explicitly; unexpected content changes fail acceptance.
6. In a disposable fixture, make conflicting edits to the same line on both sides. Verify native conflict handling preserves both versions, merge the resulting conflict branch deliberately and resynchronize. Exercise additions, renames, deletions and a binary figure change. Test an immediate repeat sync for unintended changes. Do not claim tracked-comment preservation beyond what is observed.
7. Fresh-clone the post-roundtrip GitHub revision and run code build/tests, selected optional proof checks, a representative benchmark command, lifecycle checks and paper builds. Verify our script entrypoints execute through explicit interpreters. Exercise actual subprocess and tool invocations to detect execute-bit dependencies. Unsupported or broken student-code behavior blocks acceptance; an interpreter workaround for our tooling is not a universal filesystem guarantee.
8. Refresh the disposable Zotero-linked bibliography as its owner, compile a citation and complete native synchronization. Confirm the managed bibliography remains refreshable, hand-maintained references survive, and source paths are correct.
9. Record source and resulting SHAs, observed automatic commits, manifests, compilation and execution evidence, remaining size capacity and unresolved limitations. Accept only after both sync directions, expected mode behavior and all required component checks are verified. A project URL or successful import alone is insufficient.

Docker component and proxy builds now pass on the committed source, with real lint and review evidence recorded in the verification report. The host lacks a native TeX toolchain; the later Overleaf pilot must still verify the service environment.

## Onboarding integration

Setup owns onboarding tooling. Restore native import configuration and evidence fields: repository URL, default branch, project URL, premium owner, linked GitHub account, root draft/final entrypoints, paper source directory, compiler/TeX Live and Zotero bibliography path. Record organization OAuth approval only where applicable. No bridge remote mapping, common-base journal, scheduler or bridge credentials belong in the accepted interface.

Separate operation state (`pending`, `blocked`, `running`, `failed`, `completed`) from verification state (`pending`, `verified`, `failed`, `stale`). Evidence carries tested SHA, timestamp, config digest, reference, actor and method. Checks cover tracked-content budgets, access/import, proxy compilation, native push/pull, mode/symlink findings, conflict recovery, post-roundtrip code execution, Zotero and component CI. Label manual attestations distinctly from observed evidence. A newer source SHA is untested since the recorded pilot; configuration changes invalidate affected evidence.

## Remaining coordinator decisions

Confirm final root entrypoint names and pilot timing after integration, and resolve concrete unsupported-file or mode-dependent-code findings if any. Public-template disclosure preparation, licensing and the actual designated premium account must be resolved before the corresponding actions. The lead student owns Zenodo records and performs final publication after advisor review, with automated packaging; no central lab publisher is selected. Publication credential location/execution and automation App/controller choices remain downstream decisions. The coordinator’s monorepo plan governs these and other accepted access, maintenance and end-project policies; this pilot does not authorize those actions. Native whole-monorepo synchronization is the current plan; the custom bridge and separate paper repository are out of scope. No further discovery or production action is authorized by this document update.
