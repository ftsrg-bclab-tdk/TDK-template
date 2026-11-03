# Overleaf integration: custom bridge withdrawn

## Current authority: stop custom bridge work

Martin explicitly said "No bridge". This supersedes the earlier acceptance of custom paper-only bidirectional synchronization. Do not implement, schedule or provision a custom bridge. The proposal below is retained solely as historical evidence; its mapping, merge rules, pilot and interface are withdrawn, not accepted requirements.

Native Overleaf GitHub synchronization operates at repository level. The coordinator will resolve whole-monorepo native sync versus a separate paper repository with Martin. Neither option is selected here. Mapping `paper/` to the Overleaf root is no longer settled. Whole-monorepo native sync may require root proxy entrypoints for nested paper sources; the earlier official-support evidence remains useful, but no proxy implementation is authorized by this document.

The `benchmark/`, `scratch/` and `proof/` selections remain in effect. Proof-tool catalog work and other non-Overleaf preparation continue in their respective workstreams. Repository ownership and publication defaults still require the final design summary. No live mutations, implementation, schedules or provisioning were performed in this workstream.

## Historical proposal below: withdrawn in full

The following text records the superseded proposal and its evidence. Statements of acceptance or requirements below describe the prior state only and must not be used as current instructions.

Updated 2026-11-03 after Martin's explicit acceptance in the coordinating session. Paper-only bidirectional sync is accepted; Martin is the sole Overleaf editor. Use `scratch/` for the version-controlled research workspace, with temporary outputs and secrets ignored and publication excluded by default. Use `benchmark/` for evaluation (the coordinator interprets this as a top-level component alongside `code/` and `proof/`), replacing earlier experiments naming. `proof/` must offer optional profiles for Lean, Tamarin, ProVerif, TLA+ and language verifiers for Rust, Java, Go and Solidity; no universal prover is required. The proof-tool catalog is being verified separately in the coordinator’s `docs/proof-tool-options.md`. Keep `presentation/` in its separate workstream. No organization settings, repository ownership, distribution visibility or publication authority follow from these decisions.

This document is a proposal and acceptance contract, not a working bridge. No live project mutations have been made. Existing student migration remains long-term only. Setup owns the onboarding CLI. The shared monorepo plan remains read-only here.

## Accepted mapping and proposed transport

Map each synchronized `paper/<relative-path>` to `<relative-path>` at the Overleaf project root, in both directions. Keep the paper self-contained: TeX sources, bibliography/style files, figures, guide, and build-time lint dependencies needed by an Overleaf compilation must be inside `paper/`. Build locally with the paper directory as working directory; the exported tree compiles from its own root. Monorepo-root TeX proxies are unnecessary with this mapping, subject to the full-template pilot.

Only the paper component crosses this boundary. `scratch/`, `proof/`, `code/`, `benchmark/`, `presentation/`, infrastructure, bridge state and credentials stay outside. A figure or table produced elsewhere must be copied into a tracked paper asset with provenance before synchronization; do not reach outside the component using symlinks or `../` inputs. Source-contained advisor notes remain intact.

Proposed transport: an isolated bridge workspace talks directly to the premium Overleaf project's Git remote and the monorepo. This needs no second canonical GitHub repository and no native whole-monorepo GitHub link. Creating/configuring the disposable Overleaf project is an explicit setup step. Execution location and invocation policy are undecided. Neither local-only execution nor manual command invocation has been accepted. The workspace describes isolation, not a requirement to run on Martin’s machine. The coordinator is explaining the mechanism and collecting that decision; do not put an advisor-wide credential into student-controlled CI by inference.

## Official evidence and its implications

Overleaf recommends root main documents and documents proxies for nested sources. Exporting the paper directory contents instead places the real entrypoints at that root, removing the reason for proxies. Draft/final selection still needs verification against the integrated template's eventual names.

Source: [The Main document](https://docs.overleaf.com/getting-started/recompiling-your-project/the-main-document).

The direct Git interface supports clone/fetch/push. Fetching can materialize an Overleaf history state as a commit. New clones use `main`; older ones can use `master`, so discover the remote branch. It does not support branches, tags, LFS or nested submodules, does not preserve execute bits, and converts symlinks. Renaming files can lose Overleaf comments; renaming directories can leave empty directories. Git changes may displace tracked changes/comments. These are pilot constraints, not reasons to expose the other monorepo components.

Source: [Git integration](https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git-integration).

Native GitHub synchronization has no documented folder selector. It is not the selected bridge. Its owner-initialized GitHub linkage and organization OAuth setup are therefore not required bridge steps. Do not combine that integration with the bridge on the same project and create two competing writers.

Source: [GitHub synchronization](https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/github-synchronization).

Overleaf limits include 2,000 files, 7 MB editable material and 2 MB per editable text file, with a recommended project size below 100 MB for Git use. Budget the exported paper tree, not the whole monorepo. Local editable-byte estimates must disclose classification assumptions; verify actual server acceptance in the pilot.

Source: [Plan limits](https://docs.overleaf.com/getting-started/free-and-premium-plans/plan-limits).

Premium ownership supplies Git access and relevant project benefits. Reference-manager linking is account-controlled, and documentation assigns refreshing imported Zotero files to the owner. Record Martin's actual owner/access configuration in the pilot rather than inferring it from GitHub ownership. Student Overleaf accounts, invitations and multi-editor synchronization are no longer acceptance requirements.

Source: [Premium features](https://docs.overleaf.com/getting-started/free-and-premium-plans/premium-features).

## Paper boundary and merge contract

The following engineering rules are proposed for the accepted bidirectional scope:

- Sync tracked source assets from the agreed paper manifest. Exclude generated PDFs, logs, auxiliary files and generated lint output; exclude transport metadata. Diagnose unexpected incoming paths rather than silently dropping them. Preserve tracked generated template resources that are legitimate compile inputs.
- Reject symlinks, gitlinks, LFS pointers and escaping/ambiguous paths at the transport boundary. No path from Overleaf may write outside `paper/`. Detect case collisions for supported host filesystems.
- Transport ordinary file bytes without execute permissions. Preserve existing monorepo execute modes using the source-side manifest; a server's missing execute bit must never clear a source bit. Assign new imported regular files mode 100644. Do not change global Git configuration or blanket-normalize source permissions.
- Persist the last mutually confirmed paper snapshot plus monorepo commit, Overleaf commit, mapping/config digest and source modes. Git commit hashes across the two histories are not interchangeable common-base identifiers.
- Fetch both current heads and perform a three-way merge against that snapshot. One editor can still make divergent edits in Overleaf and Git; sole-editor status does not justify overwriting either side.
- Stop on same-line, modify/delete, rename or binary conflicts requiring a decision. Preserve both variants and report a concrete resolution path. Never force-push or treat last writer as authoritative.
- Serialize bridge runs. Before applying results, verify the monorepo target has not advanced; otherwise recompute. Use fast-forward-safe Overleaf pushes and re-fetch on rejection. Keep local uncommitted work untouched by operating in an isolated bridge workspace.
- Journal prepared result, each endpoint application and verification. Advance the common snapshot only after both endpoints contain the intended mapped content. If a crash or network timeout leaves one endpoint updated, fetch and reconcile from the journal; never assume a timeout means failure or replay edits blindly.
- On first pairing, require an empty disposable target or an explicit reconciliation of both initial trees. Missing/corrupt state on a later run is not permission to overwrite either endpoint. Repeat synchronization of matching trees must produce no changes.

## Repository-specific observations

The current paper's `include/preamble.tex:239` invokes `texlua scripts/lint.lua` relative to the compile directory; `scripts/lint.lua:24` loads paper-relative modules. Keeping these dependencies inside `paper/` and compiling there locally, then exporting that directory as the Overleaf root, preserves this working-directory model. Shared automation may delegate to it but must not remove required runtime files from the exported component.

Three tracked Python scripts currently have execute modes. The bridge must preserve source modes even when their exported copies lack them. BibTeX styles/inputs, guide bibliography, SVG, listings, auxiliary files and lint must all be checked; a successful minimal TeX export is insufficient. `xelatex`, `texlua` and `latexmk` were absent from PATH during this investigation, so no local build success is claimed.

## Proposed pilot

No live execution is authorized by this document. Use a disposable project after the coordinator authorizes the pilot, never an existing student paper.

1. Freeze a candidate SHA and export its paper manifest to a temporary directory. Check paths, modes, unsupported object types, file/byte budgets and dependency closure. Put sentinel files, executable files and symlinks outside `paper/` to prove exclusion and preservation.
2. Build both entrypoints from `paper/` and from the exported root with matching TeX Live/compiler settings. Compare semantic PDF content, references, page counts, inclusion rules and lint evidence. Exercise BibTeX, glossary, minted/listings, SVG and guide. Verify the Checks page reflects an actual lint run.
3. Create a disposable project for Martin, record project URL/Git remote, access method, selected main document, compiler and TeX Live version. Seed only the export, without a whole-monorepo GitHub link. Verify both entrypoints, clean-cache compilation, navigation and word count.
4. Change paper text on the Git side and synchronize. Change different text as the sole Overleaf editor and synchronize back. Verify mapped bytes and every unrelated source blob/mode. Include an executable file inside the paper manifest to prove mode preservation, and assert no excluded component appears remotely.
5. Edit the same line on both sides, test modify/delete, add/rename/delete and conflicting binary assets. Verify both versions survive a conflict stop, then resolve and resume. Include directory rename behavior and unexpected incoming/path-escape cases.
6. Test concurrent Git advancement and Overleaf advancement, two simultaneous bridge runs, a lost bridge journal, and interruption before/after each endpoint update. Simulate an ambiguous push timeout. Every retry must reconcile without force-push, duplicate edits or premature common-base advancement. An immediate repeat run must be a no-op.
7. Refresh a disposable Zotero-linked bibliography as the owner, compile a citation and synchronize the managed file back to its mapped paper path. Preserve hand-maintained references. Verify that a subsequent unchanged export does not destroy linked-file refresh behavior; if it does, stop and resolve that integration before claiming completion.
8. Run paper, code and lifecycle checks after the round trip. Accept only the intended paper diff, with all outside paths and source modes preserved. Record logs, source/remote SHAs, manifest hashes and unresolved failures. Do not commit build outputs.

## Onboarding interface contract

Setup owns onboarding tooling; this workstream owns bridge semantics and evidence. This interface contract does not prescribe local execution or manual invocation. Configuration should name the monorepo, source directory `paper/`, destination root, paper manifest, entrypoints, Overleaf URL/Git remote, remote branch discovery, expected owner/editor, compiler/TeX Live and Zotero path. A linked GitHub account is not a required field for direct Git transport. Store credentials separately.

Separate operation state (`pending`, `blocked`, `running`, `failed`, `completed`) from verification state (`pending`, `verified`, `failed`, `stale`). Evidence includes tested SHA, timestamp, config digest, reference, actor and method. Manual attestation is not observed round-trip evidence. Checks cover sole-editor access, dependency closure, compilation, each sync direction, excluded-path/mode preservation, conflict recovery, retry recovery, Zotero and post-sync CI. Invalidate affected evidence when mapping, manifest, entrypoints, ownership or transport changes. A later source revision remains untested since the recorded pilot.

Onboarding may prepare the paper export and handoff; project creation, owner authentication and reference-manager configuration stay pending until verified. No student invitation or free-student-account test is required.

## Remaining decisions for the coordinator only

- Confirm direct Overleaf Git transport and the bridge execution location/credential owner.
- Set invocation policy (manual, event-driven, scheduled, or a combination) and how merged incoming edits are accepted into the monorepo. No invocation policy is accepted yet.
- Confirm the final paper entrypoints and source manifest after integration; settle where figure/table provenance is recorded.
- Authorize the disposable pilot when its prerequisites are ready.

These decisions do not reopen the accepted paper-only mapping, sole-editor requirement, `scratch/` rename or `proof/` addition. Presentation remains separate. Other earlier recommendations stay tentative until the coordinator confirms them.
