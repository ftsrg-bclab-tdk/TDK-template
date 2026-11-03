# Monorepo delivery plan

Updated 2026-11-03. Accepted decisions below supersede earlier proposals in the linked conversations. This file is the coordinator's current plan, not evidence that deployment or the full pilot has finished.

## Outcome and accepted design

Maintain `FTSRG-BCLab-TDK/TDK-template` as the single public reusable monorepo after its contents and history are prepared for public disclosure. Create one private organization-owned repository per student project. The repository is still private today; nothing has been pushed to main or deleted as part of this consolidation.

The layout is `paper/`, `code/`, `benchmark/`, `proof/`, `scratch/`, and `presentation/`. Preserve component history and attribution. Large datasets, dependencies and build outputs stay out of tracked source. Scratch is tracked research work with temporary outputs and secrets ignored; it is excluded from publication by default.

Use native whole-monorepo Overleaf GitHub synchronization. Appropriate collaborators edit the paper in Overleaf and use normal tools for other components. Keep paper sources in `paper/` with unique small root compilation entrypoints. No custom bridge, separate paper repository, or sole-editor restriction is in scope. Editing convention does not prevent Overleaf's mode resets or symlink transformations. Our scripts use explicit interpreters; arbitrary student code must pass a real post-sync execution test, without silent chmod or symlink rewriting.

Offer optional Lean, Tamarin, ProVerif, TLA+ and Rust/Java/Go/Solidity verifier profiles. Supported profiles need real tooling, examples, commands and checks, including a deliberately false example. Documentation-only options must say so. Unconfigured or inconclusive proofs are not verified. The [tool catalog](proof-tool-options.md) supplies sources and limitations; the adapters are not implemented yet.

Benchmark provides a common quick/full invocation and machine-readable command, tool, machine, unit and result evidence. Projects select their workloads and measurement tools. There is no universal performance threshold.

Presentation generalizes Martin's BPM FTSRG deck. Preserve documented AVM MIT and font OFL notices and exact source provenance. Public artwork and other inherited-material terms remain to resolve.

Existing-student project migration is long-term work, outside this delivery. Mechanical guide-link repairs needed before legacy-template deletion are a separate pending choice.

## People and onboarding

R1-R6 were explicitly accepted:

- The advisor provisions the organization repository and access, imports it into premium Overleaf, invites paper collaborators, and configures the Zotero group.
- Students create or reuse required GitHub, Overleaf, ORCID, Zotero and Zenodo accounts. Both guide and script provide official signup/profile links and non-secret identifier prompts. Account format, account existence and project access are distinct evidence.
- Students install Git, Python, GitHub CLI and Docker, accept invitations, clone the repository and prepare their workspace. Selected local TeX/code/proof/benchmark tools follow project needs. Linux/WSL is primary; macOS uses a tested container route. Native Windows is excluded.
- One resumable tool guides advisor/student steps and reports unfinished work. Include dry-run, safe repetition, atomic local state and bounded metadata edits. Keep credentials out of configuration. Preserve student prose, review notes, chapter choices, lint phase and Zotero-managed bibliography.
- Students receive outside-collaborator write access to their own project only. Advisors control project settings/access; organization base permission is none and owners control repository creation, deletion and transfer.
- Imre Kocsis becomes a second organization owner once he agrees. His agreement and invitation are not yet recorded.
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

The user accepted repository-wide immutable GitHub releases. Prepare drafts, attach all files, download/verify, then publish. Published file corrections require a new version. Whole-release deletion is still possible, so retain recovery copies. No setting has been enabled yet.

The lead student owns the Zenodo records and performs final publication after advisor review. Setup prepares metadata/drafts; publish deliberately at the first meaningful research milestone, not automatically as an empty v0.0.0 scaffold. Default to one combined code/proof/benchmark record, with separate records when independently useful to cite. Scratch stays excluded unless explicitly selected and reviewed.

Packages bind exact source, build/runtime, selected files, licenses, external inputs and hashes. The uploader must consume those bytes, never rebuild in a credentialed job. Publication needs durable operation identity and reconciliation; never blindly retry an ambiguous create/newversion/publish. Version staging requires a token scope that also permits publishing, so workflow stages are not a token-scope boundary.

Verified publication produces reviewable DOI/bibliography/availability writeback. Reserved DOIs are not published artifacts. Preserve Zotero-managed entries and the archived source SHA. Credential location and the student's concrete publication execution method remain pending; a central lab publisher is not selected.

## Template maintenance

Weekly and manual maintenance proposes reusable project improvements upstream, then merged template changes downstream. Neither direction auto-merges. Keep registered project/baseline identities, provenance and loop prevention. Only established template-owned changes are automatic candidates; mixed files require maintainer-selected edits in the authorized project context. Exclude research content, personal metadata, publication records and credentials.

A scoped GitHub App and private maintenance controller are proposed for cross-repository PRs/package copies and private registry/logs. App tokens should be narrowed per run and selected repository. Contents-write permissions do not technically forbid merges/deletions; the implementation must enforce its no-merge behavior. An App key can be a secret in a public repository; private controller storage is a design choice for private registry/logs, not a platform prohibition.

## Integration progress and remaining implementation

The coordinator branch contains all 16 open canonical PR heads plus account commit `51a46c4` as ancestors. The combined base `1a051cd` passed the owner's draft/final Docker builds, 210 lint mutations, review/skim, account, runner and presentation checks. Coordinator inspection repaired additional AGENTS truncation in `1edfbb5`; original guidance and student protections are restored with draft/final naming and advisory CI semantics. Source PR branches and dirty main remain untouched.

Committed components now included locally:

| Component | Evidence | Remaining work |
| --- | --- | --- |
| Required accounts `51a46c4` | 14 deterministic tests, used by terminal setup | Real access evidence and guide integration |
| Docker bootstrap `f9ff699` | 20 combined account/bootstrap tests pass here | Actual OS adapters/runtime smoke and full onboarding |
| Terminal setup `9d17bf9` + source discovery `17fa890` | 40 onboarding tests; advisor dry-run against current draft source | Shared-config adapter, installation/workspace/provisioning adapters and real pilot |
| Shared project config `54334d6` + corrections `efd2725` | 17 config/planner tests; strict metadata and actual presentation output paths | Dispatcher and setup must consume the same loader/digest; declared paper paths await relocation |
| Selective packager `2ee930b` | 23 packager + 13 schema tests; complete-ZIP size-bound regression repaired | Uploader, durable publication state and live sandbox verification |
| External inputs + dependency planner `6644ddb` | 18 fetch/verify fixtures + 7 planner tests reported passing in assembled tree; canonical receipt schema matches | Real immutable-release delivery/copy, consumers and workflows |
| Presentation #28 `07bb8bd` | Local/hosted builds, visual and audience/presenter checks | Latest-runtime integration, accepted asset fetch and public terms |
| Runner #27 `035b0bd` | Native offline isolation/cleanup and hosted toolkit checks | GitHub session/container/egress integration and routing evidence |

Code/scratch imports and paper relocation/root proxies are underway in their existing workstreams. Workflow execution/badge handoff, proof adapters, real benchmark scaffold, full onboarding and maintenance automation remain unfinished. Tests of isolated components are not evidence that the whole monorepo works.

Setup and CI share one root `project.json` with schema 1. CI owns its loader and component commands; setup preserves those fields while managing repository identity and bounded paper metadata. The editable paper source is separate from the root draft/final compilation entrypoints. Both consumers bind evidence to the exact config bytes. Account identifiers and local operational state stay in the ignored private `.onboarding/` directory.

Delivery order:

1. Preserve/import code and scratch history and outstanding intent; integrate scoped module commits.
2. Move paper sources and adapt root entrypoints, bibliography/helper cwd, Git-root hygiene, annotations and artifact paths. Do not silently disable Git protections when `.git` is above paper/.
3. Wire configured component execution, latest resolution, separate badges, external references and public template manifests.
4. Complete resumable onboarding and maintenance; settle remaining credentials/licensing choices.
5. Run a disposable new-project pilot through accounts/access, Docker, paper/code/proof/benchmark/presentation, native Overleaf round trip, conflicts/modes/symlinks, release staging/publishing in sandbox and both maintenance directions.
6. Verify public disclosure/licensing, publish the reusable monorepo, then retire the three old templates with fresh recovery exports and repaired links.

## Retirement and public disclosure

Authorized deletion scope is exactly `FTSRG-BCLab-TDK/tdk-paper-template`, `tdk-code-template`, and `tdk-notes-template`, after the monorepo is complete and verified. Do not substitute indefinite archival for the user's deletion instruction, and do not delete them early.

Code PRs #1-#3 remain open and change Docker/CI/publication hygiene. Notes PR #2 changes draft/final references. Import or explicitly supersede them. Preserve local notes commit `6665d1d` and assess 11 uncommitted notes-main changes without modifying that dirty checkout. Paper PR #1 needs a content comparison with its apparent canonical successor. Six existing student guides link to the retiring templates; mechanical update PRs are proposed separately from migration.

Final recovery exports go to `/home/blacklight/Projects/TDK/retirement-archives/<timestamp>/`, mode 0700. The parent is itself a Git repository; `/retirement-archives/` was added to its local `.git/info/exclude` and verified ignored. The inventory is saved there. Test bundles restore successfully, but final mirror/bundle, PR/settings/comments and selected artifacts/logs must be refreshed immediately before deletion, hashed and test-restored. Check associated packages and live consumers. No repository has been deleted.

Public-disclosure fact finding inspected the proposed branch and reachable remote history. The 134 template-review files are fictional/template evidence, not student assessments; they include local paths and candid policy criticism. Runner history includes actual non-secret service/host details. A real authenticated Overleaf project link and personal author emails also exist in history. Visibility changes expose remote branches and PR history, not only the final tree. Local-only learn/* branches are outside the inspected remote/proposed exposure. A targeted scan found no recognized credentials; it was not a complete artifact/log audit.

Preserve history, consistent with the publication guide. Removing a file from HEAD does not erase its historical disclosure. Decide retention/disclosure of the identified non-secret history explicitly. Public source assets are not automatically licensed: paper/guide/notes have no blanket grant; code's MIT attribution still says TODO Name; bibliography styles have their own LPPL/GPL notices. Presentation fonts/AVM notices exist, but institutional artwork and BPM additions need terms. The matching `avn-tamarin-tutorial` repository is private, so it cannot be an anonymous student download endpoint.

## Remaining decision frontier

R1-R6 and operating Q1-Q10 are settled. Ask only the newly answerable branches:

- Private maintenance controller/GitHub App ownership and installation.
- Require 2FA before admitting new organization collaborators.
- Student publication through a manually invoked project workflow versus a local credentialed command; advisor review is not automatically enforced by a student-writable workflow on Free.
- Mechanical guide-link/setup-instruction PRs in existing projects before deleting legacy templates.
- Licenses for original reusable tooling/prose and treatment of institutional/third-party assets lacking recorded redistribution permission.
- Acceptance of identified non-secret historical disclosures while preserving history and moving generated evidence out of the starter tree.

After these choices, present one final shared-understanding summary before activating unresolved external choices. Continue already authorized source integration and implementation in parallel with the interview. Do not invent further approval questions for routine implementation details or commits.

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
