# Monorepo delivery plan

Updated 2026-11-04. Accepted decisions below supersede earlier proposals in the linked conversations. Martin accepted the remaining S1-S7 decisions, with explicit permission to retain the supplied artwork. This file is the coordinator's current plan, not evidence that deployment or the full pilot has finished.

## Outcome and accepted design

Maintain `FTSRG-BCLab-TDK/TDK-template` as the single public reusable monorepo after its contents and history are prepared for public disclosure. Create one private organization-owned repository per student project. The repository is still private today; nothing has been pushed to main or deleted as part of this consolidation.

The layout is `paper/`, `code/`, `benchmark/`, `proof/`, `scratch/`, and `presentation/`. Preserve component history and attribution. Large datasets, dependencies and build outputs stay out of tracked source. Scratch is tracked research work with temporary outputs and secrets ignored; it is excluded from publication by default.

Use native whole-monorepo Overleaf GitHub synchronization. Appropriate collaborators edit the paper in Overleaf and use normal tools for other components. Keep paper sources in `paper/` with unique small root compilation entrypoints. No custom bridge, separate paper repository, or sole-editor restriction is in scope. Editing convention does not prevent Overleaf's mode resets or symlink transformations. Our scripts use explicit interpreters; arbitrary student code must pass a real post-sync execution test, without silent chmod or symlink rewriting.

Offer optional Lean, Tamarin, ProVerif, TLA+ and Rust/Java/Go/Solidity verifier profiles. Supported profiles need real tooling, examples, commands and checks, including a deliberately false example. Documentation-only options must say so. Unconfigured or inconclusive proofs are not verified. The [tool catalog](proof-tool-options.md) supplies sources and limitations; the TLC finite-state invariant profile now has a working adapter, positive/negative examples and actual runtime evidence. Other catalog entries remain explicitly documentation-only.

Benchmark provides a common quick/full invocation and machine-readable command, tool, machine, unit and result evidence. Projects select their workloads and measurement tools. There is no universal performance threshold.

Presentation generalizes Martin's BPM FTSRG deck. Preserve documented AVM MIT and font OFL notices and exact source provenance. Martin confirmed redistribution permission for the supplied institutional artwork on 2026-11-04; retain the supplied logos and graph backgrounds. Do not replace them or infer a new blanket artwork license. Original reusable code/tooling uses MIT; original guide/slide prose uses CC BY 4.0. Inherited material retains its own notices and terms.

Existing-student project migration is long-term work, outside this delivery. Mechanical guide-link and setup-instruction PRs in the six known existing projects are authorized before legacy-template deletion; they do not migrate student research or change project layout.

## People and onboarding

R1-R6 were explicitly accepted:

- The advisor provisions the organization repository and access, imports it into premium Overleaf, invites paper collaborators, and configures the Zotero group.
- Students create or reuse required GitHub, Overleaf, ORCID, Zotero and Zenodo accounts. Both guide and script provide official signup/profile links and non-secret identifier prompts. Account format, account existence and project access are distinct evidence.
- Students install Git, Python, GitHub CLI and Docker, accept invitations, clone the repository and prepare their workspace. Selected local TeX/code/proof/benchmark tools follow project needs. Linux/WSL is primary; macOS uses a tested container route. Native Windows is excluded.
- One resumable tool guides advisor/student steps and reports unfinished work. Include dry-run, safe repetition, atomic local state and bounded metadata edits. Keep credentials out of configuration. Preserve student prose, review notes, chapter choices, lint phase and Zotero-managed bibliography.
- Students receive outside-collaborator write access to their own project only. Advisors control project settings/access; organization base permission is none and owners control repository creation, deletion and transfer.
- Imre Kocsis becomes a second organization owner once he agrees. His agreement and invitation are not yet recorded.
- Require 2FA before admitting new collaborators. Check existing accounts before enabling the requirement; do not assume compliance or Imre's agreement.
- Completed projects remain archived in the organization, with a guaranteed student-requested transfer or full-history copy coordinated with coauthors. Do not delete student projects automatically.

Advisor and student jointly verify builds, access and native synchronization. Operation completion is separate from verification: evidence identifies tested SHA, configuration, timestamp, actor/method and result. URL existence or manual completion alone is not a verified integration.

Institutional identities and BME TDK portal registration are separate handoffs; optional Reclaim/AI services are not new mandatory personal accounts. Notification channels are not authorized merely by preparing a handoff checklist.

## Accepted CI policy

All CI1-CI11 choices are settled. The [CI design](ci-design.md) owns detailed architecture and measured evidence.

- Ordinary writing findings are advisory. Broken compilation/checkers/configuration and missing required reports fail. Keep a separate strict submission check.
- Optional components require explicit configuration and real checks; empty/TODO recipes cannot pass as implemented work.
- Draft PRs get cheap feedback; ready PRs check affected components; default-branch pushes check all enabled ordinary components. Other branches use PRs/manual runs. Unknown or incomplete diffs run broadly.
- Full benchmarks, robustness campaigns and exploratory proof searches are manual initially. Real smoke checks and ordinary selected proof obligations stay routine.
- Provide separate CI, paper-build and lint-report badges, with exact-run evidence and no duplicate TeX builds.
- Weekly maintainer checks report changed/inaccessible/overdue official references. Ordinary checks verify accepted reference packages without refetching publisher websites. Outages may reuse verified accepted bytes, with freshness failure visible; missing/corrupt required bytes fail.
- Scratch lifecycle reports are advisory and do not automatically commit generated files on every push.
- Routine artifacts last 14 days, bulky temporary previews/output 7 days, release candidates 90 days. Preserve required publication and source-package evidence durably before expiration.
- Stay on GitHub Free initially. Report acceptance honestly; private repositories do not have the promised paid-plan merge/environment enforcement.
- Target Linux/WSL and a tested macOS container route, without a second native macOS matrix.
- Use latest normal toolchains/dependencies. Resolve once per run and record actual versions, image/platform digests and dependency resolution. Do not substitute a later same-SHA run's artifacts or silently roll back to older tools. This does not authorize host upgrades/reboots.

Dockerfiles, Docker ignore files, devcontainer and any applicable Compose configuration belong in source integration, CI dependency handling and selected reproduction packages. Record built image identity separately; GitHub release immutability does not freeze GHCR tags.

BME is the preferred runner, with GitHub-hosted fallback and Blacksmith/Depot/Ubicloud documented. The existing persistent BME runner is hardened and connected but remains trusted-only. Its separate offline native sandbox passed reported isolation/cleanup probes. Fresh JIT runner sessions, controlled network/container inputs, cancellation/admission and end-to-end job evidence remain unfinished. No student workload routing change follows from the offline probes.

## External files and releases

The [external input inventory](external-input-inventory.md) identifies actual consumers. Download faculty references and presentation assets into verified packages; keep manifests/provenance in source. The user accepted retaining small embedded paper graphics in Git so native Overleaf can compile. Update review-sheet lint/skim consumers before removing the bundled reference PDF. Metadata-only Overleaf checks must not claim full artifact-dependent rubric verification.

Use accepted package/receipt digests and exact per-file inventories. GitHub Release assets in canonical and consuming project repositories are the chosen implementation proposal: identical package bytes, distinct delivery locators. Project CI reads its own copy without private-maintainer credentials. Required packages remain available while supported baselines/releases reference them; routine Actions expiration is insufficient. Support releases use a distinct `external-inputs/` namespace, are not-latest and do not trigger research/Zenodo publication.

The user accepted repository-wide immutable GitHub releases. Prepare drafts, attach all files, download/verify, then publish. Published file corrections require a new version. Whole-release deletion is still possible, so retain recovery copies. The canonical repository (ID 1437261410) now has this setting enabled, with authenticated API readback on 2026-11-04. No release was published by that settings change. Project copies still need their own verified setup.

The lead student owns the Zenodo records and performs final publication after advisor review. Setup prepares metadata/drafts; publish deliberately at the first meaningful research milestone, not automatically as an empty v0.0.0 scaffold. Default to one combined code/proof/benchmark record, with separate records when independently useful to cite. Scratch stays excluded unless explicitly selected and reviewed.

Packages bind exact source, build/runtime, selected files, licenses, external inputs and hashes. The uploader must consume those bytes, never rebuild in a credentialed job. Publication needs durable operation identity and reconciliation; never blindly retry an ambiguous create/newversion/publish. Version staging requires a token scope that also permits publishing, so workflow stages are not a token-scope boundary.

Verified publication produces reviewable DOI/bibliography/availability writeback. Reserved DOIs are not published artifacts. Preserve Zotero-managed entries and the archived source SHA. The student manually invokes publication in their own project's GitHub workflow, using their own Zenodo token as a repository secret and the exact reviewed receipt. Other writers can exercise that credential through workflow changes; advisor review is recorded policy, not technically enforced by student-editable workflows on Free. Never use a shared advisor token. A central lab publisher is not selected.

## Template maintenance

Weekly and manual maintenance automatically opens eligible upstream PRs after checks, then downstream PRs for merged template changes. The user explicitly rejected a separate approval/hash gate for every upstream PR. Neither direction auto-merges. Keep registered project/baseline identities, provenance and loop prevention. Only established template-owned changes are automatic candidates; mixed files require maintainer-selected edits in the authorized project context. Exclude research content, personal metadata, publication records and credentials.

Use a private `FTSRG-BCLab-TDK/tdk-maintenance` repository for the project registry, maintenance credentials and private logs. Use an organization-owned GitHub App installed only on selected registered repositories, administered initially by Martin, with Imre as backup after he agrees. App tokens must be narrowed per run and selected repository. Contents-write permissions do not technically forbid merges/deletions; the implementation must enforce its no-merge behavior. An App key can be a secret in a public repository; private controller storage is the accepted design for private registry/logs, not a platform prohibition. App creation, installation and controller deployment remain implementation tasks.

## Integration progress and remaining implementation

The coordinator branch contains all 16 open canonical PR heads plus account commit `51a46c4` as ancestors. The combined base `1a051cd` passed the owner's draft/final Docker builds, 210 lint mutations, review/skim, account, runner and presentation checks. Coordinator inspection repaired additional AGENTS truncation in `1edfbb5`; original guidance and student protections are restored with draft/final naming and advisory CI semantics. Source PR branches and dirty main remain untouched.

Committed components now included locally:

| Component | Evidence | Remaining work |
| --- | --- | --- |
| Required accounts and terminal onboarding | Canonical account API plus installer/workspace/provisioning/evidence adapters; 63 assembled tests and student-role initialization fix | Real host/access/new-project pilot; organization 2FA is deferred by the user |
| Shared config and CI execution | `project.json`, dispatcher, latest resolver and exact artifact handoff; manual publication transport integrated, with draft-recovery and project-token fixes | Hosted run on the assembled branch and real publication transport pilot |
| Paper relocation and root proxies | Source/proxy build equivalence proved by owner; updated guide builds draft (127 pages) and final (23 pages) without undefined references/citations | Native Overleaf import, compile and push/pull/mode pilot |
| Code and scratch imports | Source histories and PR intents preserved; scope/lifecycle fixes; real code development image build/list and explicit unconfigured failure | Project research recipes remain intentionally unconfigured; no fake green claims |
| Selective release `2ee930b`, `82e7a21`, `772176a` | Packager, uploader, recovery journal, published receipts, project-owned GitHub journal and manual prepare/publish workflows with immutable candidate recovery | Real sandbox credentials and mutation evidence |
| External inputs and official references | Exact package retrieval/classification and weekly freshness source integrated; 19 assembled external-input tests | Accepted durable package delivery; five current faculty references still unresolved |
| Presentation #28 | Actual latest staged render/check passed in owner's full clean run; attribution/permissions documented | Accepted asset-package delivery; macOS/dual-display validation |
| Benchmark `262a18c` | Real deterministic smoke/full runs and shared dispatcher/verifier passed | Students supply research workloads and select enabled profiles |
| TLC proof `4984ed1` | Actual latest TLC/JVM positive and deliberately false models checked; structured verdicts validated | Other offered tools remain catalog options, not implemented adapters |
| Separate badges and review fetch | Blocks generated from actual workflow files/live repo metadata; exact-run transport fetch repair has 39 review tests | Live hosted workflow/badge state after landing |
| Maintenance ownership `2152f0e` | Exact trusted canonical path policy and 6 tests; controller PR #2 implements automatic eligible two-way proposals and package copying | Controller review/merge and real App-token pilot |
| Runner #27 `035b0bd` | Native offline isolation/cleanup and hosted toolkit checks | GitHub session/container/egress integration and routing evidence |

Main CI source `078363b` and its clean-run fix `b85b7a6` are integrated. The owner's clean local orchestration built both paper PDFs, lint/review evidence, maintainer suites and latest presentation, and the shared verifier accepted its exact clean source report. This is local evidence, not a live GitHub, Overleaf or BME workload result. Root integration added tests for badges, ownership, benchmark, proof, code hygiene and scratch lifecycle to the maintainer source suite.

The controller setup PR #1 passed its plan tests and was merged at `d82d8d7`. The credentialed scan was intentionally skipped on PRs, and the App is not registered. PR #2 has passing fixture tests for the write implementation; actual App tokens and cross-repository operations remain untested. Base organization permission is now none and member repository creation is off. Martin deferred the remaining organization UI changes (2FA and member deletion/transfer/visibility). Keep invitations blocked on authenticated policy readback until those are applied; do not reopen those choices. Merge authority follows repository roles, not an exclusive-Martin policy.

The native Overleaf boundary verifier and tracked-tree audit from `4c50f3b` are integrated.
They verify evidence signed by an explicitly trusted observer; no signer is provisioned,
and a signature is not independent proof of service actions. No native pilot receipt
exists. The supported browser is signed out of Overleaf and GitHub; advisor login and
premium/native-import access are required before the actual disposable pilot.

Setup and CI share one root `project.json` with schema 1. CI owns its loader and component commands; setup preserves those fields while managing repository identity and bounded paper metadata. The editable paper source is separate from the root draft/final compilation entrypoints. Both consumers bind evidence to the exact config bytes. Account identifiers and local operational state stay in the ignored private `.onboarding/` directory.

Delivery order:

1. Done locally: preserve/import code and scratch history and outstanding intent; continue integrating scoped module commits.
2. Done locally: move paper sources and adapt root entrypoints, bibliography/helper cwd, Git-root hygiene, annotations and artifact paths. Do not silently disable Git protections when `.git` is above paper/.
3. Wire configured component execution, latest resolution, separate badges, external references and public template manifests.
4. Complete resumable onboarding, student publication and maintenance using the accepted ownership, credential and licensing policies.
5. Run a disposable new-project pilot through accounts/access, Docker, paper/code/proof/benchmark/presentation, native Overleaf round trip, conflicts/modes/symlinks, release staging/publishing in sandbox and both maintenance directions.
6. Verify public disclosure/licensing, publish the reusable monorepo, then retire the three old templates with fresh recovery exports and repaired links.

## Retirement and public disclosure

Authorized deletion scope is exactly `FTSRG-BCLab-TDK/tdk-paper-template`, `tdk-code-template`, and `tdk-notes-template`, after the monorepo is complete and verified. Do not substitute indefinite archival for the user's deletion instruction, and do not delete them early.

Code PRs #1-#3 and notes PR #2 are imported with history; their source PRs remain open. See `docs/component-import-dispositions.md` for adaptations. Local notes commit `6665d1d` is superseded by the shared root skills; its source commit and the 11 uncommitted notes-main changes remain untouched in the original checkout. Paper PR #1 needs a content comparison with its apparent canonical successor. Six existing student guides link to the retiring templates; authorized mechanical update PRs repair those links and setup instructions separately from migration.

Final recovery exports go to `/home/blacklight/Projects/TDK/retirement-archives/<timestamp>/`, mode 0700. The parent is itself a Git repository; `/retirement-archives/` was added to its local `.git/info/exclude` and verified ignored. The inventory is saved there. Test bundles restore successfully, but final mirror/bundle, PR/settings/comments and selected artifacts/logs must be refreshed immediately before deletion, hashed and test-restored. Check associated packages and live consumers. No repository has been deleted.

Public-disclosure fact finding inspected the proposed branch and reachable remote history. The 134 template-review files are fictional/template evidence, not student assessments; they include local paths and candid policy criticism. Runner history includes actual non-secret service/host details. A real authenticated Overleaf project link and personal author emails also exist in history. Visibility changes expose remote branches and PR history, not only the final tree. Local-only learn/* branches are outside the inspected remote/proposed exposure. A targeted scan found no recognized credentials; it was not a complete artifact/log audit.

Preserve the existing history, including the identified template reviews, local paths, commit author identities and non-secret runner details. Martin accepted this disclosure. Archive the generated review/build evidence before removing it from the current starter tree; do not rewrite history. Original reusable code/tooling is MIT and original guide/slide prose is CC BY 4.0, with attribution preserved. Existing bibliography styles retain their LPPL/GPL notices and presentation fonts retain OFL. Institutional artwork is retained under Martin's confirmed redistribution permission, without a new blanket license. Correct the inherited code template's TODO copyright attribution from source evidence. The matching `avn-tamarin-tutorial` repository is private, so it cannot be an anonymous student download endpoint.

## Interview status

R1-R6, CI1-CI11, maintenance operating choices and S1-S7 are accepted. Martin confirmed the remaining round with "the other questions are all ok" after the artwork/history clarification. No current policy question remains open. This approval is not evidence of implementation, live access, Imre's consent or a passed pilot.

Continue source integration and the agreed implementation. Report concrete missing credentials or third-party actions through their proper channels when reached; do not reopen accepted policy or request repeat approval for routine implementation. Public visibility and legacy deletion retain their accepted completion/verification gates.

## Coordinated workstreams

All questions are answered in this coordinator session. Source threads retain their component ownership:

- Organization/access: <t3-thread://v2/b5ffded3-854d-462a-a89d-25dfae6b2462/4a829ab2-1bb4-46ff-ac15-ca5248aeb741>
- Existing PRs and imports: <t3-thread://v2/b5ffded3-854d-462a-a89d-25dfae6b2462/3440fc2e-4254-47b1-8a08-aa1be16aa600>
- Native Overleaf: <t3-thread://v2/b5ffded3-854d-462a-a89d-25dfae6b2462/0ee76f44-9916-44ba-825b-c083a389f4e5>
- Badges/README: <t3-thread://v2/b5ffded3-854d-462a-a89d-25dfae6b2462/7b1eb4c8-0ce2-44d5-824c-b71528a42f80>
- Onboarding: <t3-thread://v2/b5ffded3-854d-462a-a89d-25dfae6b2462/e9078716-ee77-4ba6-940d-e128a0ddd473>
- Account component: <t3-thread://v2/b5ffded3-854d-462a-a89d-25dfae6b2462/f6b30619-069a-4468-848e-2388361b996c>
- Selected releases: <t3-thread://v2/b5ffded3-854d-462a-a89d-25dfae6b2462/3be31776-740d-406c-88c9-fcb5ad00a0ef>
- Runner infrastructure: <t3-thread://v2/b5ffded3-854d-462a-a89d-25dfae6b2462/mcp:launch:2561fcb5024cf01bd6bcee539765ef4978d5af0c17addb2708e54340e88ef135>
- Presentation: <t3-thread://v2/b5ffded3-854d-462a-a89d-25dfae6b2462/mcp:launch:de761bfb6646f2f78438c53c22500eb4bff32e6555e5a4dfd3c26f14265f705e>
- Overall CI: <t3-thread://v2/b5ffded3-854d-462a-a89d-25dfae6b2462/mcp:launch:f9e3bd55be269a3d6acaf23f87d5adfe355624583ecdb6367a7b416ada081328>
