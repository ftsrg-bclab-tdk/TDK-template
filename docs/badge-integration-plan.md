# Badge and README integration inventory

Read-only inventory of GitHub sources on 2026-11-03, updated with Martin's subsequent layout and Overleaf decisions relayed by the coordinator. The inventory below is historical; the implementation update records current delivery. Public-template/private-project visibility is settled. No workflow, visibility, publication or infrastructure actions were performed here.

## Implementation update, 2026-11-04

All current design interview choices are closed; the coordinator's `docs/monorepo-plan.md` at decision commit `25e50bc` supersedes earlier open-choice wording in this inventory. S1-S7 include the private maintenance controller and scoped organization App, checking accounts then requiring 2FA before invitations, lead-student manual publication with their own project Zenodo secret and reviewed receipt, mechanical guide/setup PRs for six existing projects, scoped MIT/CC BY 4.0 with inherited terms preserved, permitted supplied institutional artwork without blanket relabeling, and Git-history preservation with generated evidence archived before starter cleanup. These decisions do not establish Imre's agreement, live credentials or a completed pilot. Public visibility and legacy deletion still wait for verified completion.

Implemented `scripts/readme/badges.py` with explicit repository selection, GitHub API metadata, exact workflow file/name validation, branch/event-filtered separate badges, marked-block replacement and a trusted publication-receipt digest gate. Current CI interface from its owner is `ci.yml` / Project checks / push, `paper-build.yml` / Paper build / workflow_run, and `paper-lint.yml` / Paper lint report / workflow_run. Consumer workflow runtime behavior remains the CI owner's validation responsibility. This generator neither builds paper outputs nor dispatches workflows.

Root `README.md` is rewritten for the integrated monorepo and `paper/README.md` follows relocation head `7e36d9a`: paper/draft.tex, paper/final.tex and root paper-draft.tex/paper-final.tex, sequential build routes, component-cwd checks. Root obsolete mirror/Overleaf-owner metadata is removed; student-generated prose is preserved by later marked-block updates. Licensing links point to the coordinator's root LICENSE/LICENSES, not a competing license source. Initial blocks stay pending until integrated workflow files exist, preventing false live status. The release owner's canonical publication-receipt schema is consumed without introducing another schema. Production records need per-record published verification and an independently trusted receipt digest; reserved and sandbox DOIs never qualify.

Tests cover target/event encoding, private/public wording, frontmatter/prose preservation, idempotence, missing/wrong workflow identity, trusted receipt gates, partial publication, and actual CLI execution through a fake GitHub API client. Integration must still generate the blocks against actual repository metadata after CI files land and verify native badge run behavior through the CI owner. No current successful run or publication is claimed by local tests.

## Accepted direction and remaining assumptions

Use `scratch/` as a version-controlled research workspace, with temporary outputs and secrets ignored and exclusion from publication by default. Add `proof/` with optional profiles offering Lean, Tamarin, ProVerif, TLA+ and language verifiers for Rust, Java, Go and Solidity. No universal prover is required. Exact tool choices and their capabilities come from the coordinator's separately researched `docs/proof-tool-options.md`; this badge proposal does not assert that those profiles are implemented.

Use `benchmark/` for the evaluation component, replacing the earlier experiments naming. The coordinator interprets it as a top-level component alongside `code/` and `proof/`. `presentation/` is being handled in a separate session. Other earlier recommendations remain tentative: this report grants no authority to change organization settings, repository visibility or publication state. Existing student migration remains long-term only.

Martin's explicit **No bridge** decision stands. The coordinator now plans native whole-monorepo GitHub synchronization with `paper/` sources and unique small root compilation entrypoints. Appropriate project collaborators edit the paper in Overleaf; code, proof, benchmark, scratch and other components are edited through their normal tools. This editing scope is a workflow convention, not a guarantee that native sync preserves file modes or symlinks. Advisor/student roles are settled below; credential and automation implementation remains open. No custom bridge or separate paper repository is planned. Do not implement, schedule or provision a bridge. The earlier selective export proposal remains withdrawn below. No live configuration or resource actions are authorized by this plan update.

## Existing repositories

All repositories below belong to `FTSRG-BCLab-TDK` and use `main`. The longer organization name redirects. Every tracked Markdown file and workflow at the listed commits was inspected through the GitHub API.

| Repository | Visibility / template | Inspected commit | Existing badges | Workflows |
| --- | --- | --- | --- | --- |
| `TDK-template` | Private / no | `9564ef15e70b1ef4d69f1b9f0a0feba7c6e59f9b` | None | `paper.yml` |
| `tdk-paper-template` | Public / yes | `9786321b4c578c7f0e7de0cb8eadcacf53f96202` | None | `paper.yml` |
| `tdk-code-template` | Public / yes | `b993375ab89cf0e29b2ceb6a2a0f9555640c86ba` | README contains unresolved `10.5281/zenodo.TODO` DOI badge | `ci.yml`, `demo.yml`, `evaluate.yml`, `benchmark.yml`, `robustness.yml`, `release.yml` |
| `tdk-notes-template` | Public / yes | `9dd2e451279f0f508ec6a2bef7996eb24d6f9343` | None | `lifecycle.yml` |

The paper README still names the old owner and says Overleaf creates the student's repository. The public mirror also calls itself the canonical source. Integration must reconcile these descriptions with the eventual native-sync, distribution and onboarding decisions, including README YAML metadata. PR #26 already changes organization links; avoid duplicating its changes.

The notes README describes submodules and `slides/`. Its workflow checks out recursive submodules, expects `paper/thesis.tex`, commits lifecycle/burn-down outputs, and suppresses missing-row failure when no paper is present. A green template lifecycle badge therefore does not establish student readiness. Its latest listed successful run is for `995a0754`, before the inspected generated-output commit.

The code CI runs build, tests and smoke reproduction. Demo runs on pushes; evaluation runs on main pushes; benchmark and robustness run weekly/on demand. Release publishes a GHCR container on a published GitHub release. The returned latest main runs passed for all except release, for which the sampled run list contained no run. The latest canonical and mirror paper runs passed at their inspected heads. These observations are a dated snapshot, not acceptance evidence for future integration.

## Current concrete targets

For each row, use `https://github.com/FTSRG-BCLab-TDK/{repository}/actions/workflows/{file}` as the click target, and append `/badge.svg?branch=main` for the badge image. The paths below already exist.

| Repository | File | Honest label / meaning |
| --- | --- | --- |
| `TDK-template` | `paper.yml` | Paper checks; combined build, lint and template checks |
| `tdk-paper-template` | `paper.yml` | Paper checks; same combined meaning |
| `tdk-code-template` | `ci.yml` | Code CI; build, tests, smoke reproduction |
| `tdk-notes-template` | `lifecycle.yml` | Lifecycle automation; see readiness caveat above |

Example for the public paper mirror:

```markdown
[![Paper checks](https://github.com/FTSRG-BCLab-TDK/tdk-paper-template/actions/workflows/paper.yml/badge.svg?branch=main)](https://github.com/FTSRG-BCLab-TDK/tdk-paper-template/actions/workflows/paper.yml?query=branch%3Amain)
```

There is no independent paper-build or lint workflow to badge today. Repeating the same badge three times with different alt text would report the same combined result. GitHub's native badge addresses a workflow, not an individual job; workflow names provide its visible label.

## Proposed monorepo contract

Cross-component CI architecture, triggers, status semantics and artifact interfaces now belong to the dedicated [CI design session](t3-thread://v2/b5ffded3-854d-462a-a89d-25dfae6b2462/mcp:launch:f9e3bd55be269a3d6acaf23f87d5adfe355624583ecdb6367a7b416ada081328). This report supplies badge/README requirements to that owner; it does not establish a competing CI design. All user-facing questions return to the coordinator. README integration and generated-project badge adaptation remain owned here. No independent workflow, VM or runner-routing changes are authorized.

Keep workflows under root `.github/workflows/` regardless of component layout. The following filenames are provisional interface requests for the CI owner to settle:

| Filename | Visible workflow name | Meaning of success |
| --- | --- | --- |
| `ci.yml` | CI | Required technical checks for selected components completed successfully |
| `paper-build.yml` | Paper build | Both agreed paper outputs compiled successfully |
| `paper-lint.yml` | Paper lint report | Lint executed and its report was produced; writing findings can remain |

Run paper build and lint commands in `paper/`. Keep their source inputs, bibliography, figures, include files and required scripts inside that component. Artifact upload paths must explicitly include `paper/`; a shell working directory does not relocate an action's path inputs. Adapt changed-path filters to `paper/**`, the unique root compilation entrypoints, and relevant root workflow/configuration files. Validate both the component build and the root entrypoints used by Overleaf; record their actual output paths rather than assuming root compilation writes into `paper/`. Code checks run in `code/`; evaluation checks target `benchmark/` and any declared code/proof dependencies. Add proof, benchmark and presentation status links only when their checks actually exist. Scratch lifecycle reporting retains its own meaning and must not be presented as paper readiness.

A proof badge must name the selected verification profile and link to its checked revision, properties and assumptions. A passing workflow means the configured checks succeeded; it does not establish correctness of the entire project or coverage by every offered tool. Unselected optional profiles are not passing proofs. Keep detailed profile results in `proof/README.md` and the run report rather than filling the root README with badges for unused tools.

Use native image URL `https://github.com/{owner}/{repo}/actions/workflows/{file}/badge.svg?branch={encoded-default-branch}` and a workflow-page link filtered to that branch. Explicit branch selection prevents fallback to an unrelated branch before the first default-branch run. Do not show static green placeholders before that run.

Keep technical failures fatal, including lint execution errors and missing required reports. Preserve lint findings, phase and exit evidence in the summary and review bundle. PR #12 introduces `scripts/lint-ci.sh` to keep writing findings advisory while preserving technical failures; integrate that work before fixing the final badge wording. A passing lint-report workflow means reporting succeeded, not that the paper passed submission review. Put that sentence immediately below the badges. Leave the strict local submission check available.

Splitting native badge targets requires real workflows, not just extra jobs. Coordinate the split with CI owners: build once, pass outputs by an exact run/commit identity, and preserve failed-build evidence. Never fetch an arbitrary latest artifact to populate a lint report. This artifact-selection constraint does not restrict the accepted latest-toolchain policy below. Avoid duplicate expensive TeX builds merely to obtain separate badges. An aggregate CI result must account for dependency failures and intentional component skips explicitly.

CI5 is answered: Martin requires separate badges. One Project checks image plus component links does not satisfy this decision. The CI owner must now settle distinct native badge workflows and exact-run handoff; the first CI policy round is now accepted, while concrete filenames and exact event/handoff implementation still require the CI owner's validated interface. Do not substitute three copies of a combined status or present a single-badge fallback as accepted.

## Latest CI toolchains and evidence

CI11 is answered: use latest toolchains and dependencies in normal CI rather than maintaining committed version pins. Resolve each dependency/toolchain identity once per run and share that resolution across same-run outputs. Evidence must record actual versions, image digests and dependency/lock resolution. Historical artifacts retain their built-byte identity and recorded runtime; they are not relabelled when latest changes. Do not silently fall back to older versions or recast evidence capture as mandatory source pin maintenance. This policy does not authorize remote-host upgrades or reboots.

Badge/report wording should identify the checked source SHA and actual runtime resolution. A passing latest-compatibility run establishes the result for that recorded combination, not indefinite compatibility with future releases. Implementation details of resolution and receipts remain with the CI owner. Martin accepted CI1/2/3/4/6/7/8/9/10 with “Otherwise ok”; CI5 and CI11 were already settled. The first CI policy round is complete. Do not reopen those defaults; only genuinely new downstream decisions return through the coordinator. Whole-project access/publication questions remain separate.

## Required external-file artifacts

CI6 adds Martin's requirement: “There were some committed external files in the paper and elsewhere, those should be downloaded and stored as an artifact.” External-file download and artifact storage are required, not an optional alternative to keeping binary snapshots in Git. Prefer committed manifests, provenance and source expectations over downloaded reference bytes where feasible.

Embedded paper assets are explicitly accepted to remain tracked. The coordinator's inventory of other external files and consumers across paper/presentation determines their artifact implementation. Do not delete tracked files or remove compile-essential assets before their dependencies and delivery path are established. Native whole-repository Overleaf sync cannot automatically consume Actions artifacts; README instructions must describe the verified delivery mechanism once settled, without inventing one or reinstating a custom bridge.

A source outage may reuse a verified accepted artifact, with its identity and reuse visible in the report. Reuse is not proof that the external source was freshly checked. A missing required artifact must be explicit and cannot yield a passing required check. Badge/result links must expose acquisition/freshness and consumer-build evidence separately where relevant.

Approved reference packages needed by later builds must not disappear silently under routine 14-day report/PDF or 7-day bulky-preview expiry. The CI owner must settle versioned package identity, durable retention/retrieval and expiry handling from the inventory before README instructions promise continued availability. Routine outputs and required reference packages need distinct lifecycle treatment. This refinement grants no deletion, live configuration, broad host or permission-change authority.

## Accepted template contribution flow

Weekly and manually initiated two-way maintenance is accepted. Compare registered project revisions with their recorded template baseline and propose eligible template-owned improvements as canonical-template PRs; propose merged template improvements downstream as project-update PRs. Neither direction auto-merges. Only template-owned changes qualify for automatic contributions; maintainers select mixed-file edits. Exclude student-authored research and private fields and report overlaps. Concrete registration, credentials and implementation remain with their owners; policy acceptance does not provision a job here.

README instructions must distinguish upstream contribution PRs (project improvements back to the template), downstream template-update PRs (template changes into projects), and latest compatibility testing (execution evidence). None implies that the other two occurred. Before describing an operational contribution flow or adding its status, obtain the coordinator's accepted project registration, baseline, ownership/exclusion, destination and PR policy. Do not choose parallel defaults here or expose private project details through badge labels or reports.

## README and onboarding adaptation

1. Put the compact status row below the root README title, after any YAML frontmatter. Component READMEs link to the relevant workflow and component instructions. Do not add badges to every guide or policy Markdown file.
2. Generate badge owner/repository/default-branch values from the newly created repository's API metadata. Markdown does not expand GitHub Actions expressions. Replace only a marked status block so rerunning setup preserves student prose. Include the same rewrite in any public export process.
3. Test generated metadata against a second owner/repository and a non-main branch. No generated student badge may point to the maintainer repository. Template-maintenance status, if retained, needs an explicit separate label.
4. Replace the code template's fake DOI badge with ordinary pending-publication text until verified publication metadata exists. Coordinate the exact DOI/version target with the publication thread; reserved drafts must not appear as published artifacts.
5. Legacy paper/code/notes READMEs are temporary during integration. The accepted final plan deletes `tdk-paper-template`, `tdk-code-template` and `tdk-notes-template` only after the monorepo is complete and verified. Do not design ongoing mirror-maintenance badges. Deletion belongs to the coordinator/organization owner, is not authorized now, and excludes student repositories. The finished `TDK-template` becomes the single public reusable template after its contents and history are prepared for disclosure; student projects remain private.

The root README should link to `paper/`, `code/`, `benchmark/`, `scratch/`, `proof/` and the separately integrated `presentation/`. Describe scratch as tracked research work with ignored temporary outputs/secrets and default publication exclusion. Remove the former submodule setup and incorrect sole-editor assumption from onboarding prose. Describe paper collaboration using the accepted advisor/student responsibilities below.

The accepted default is one combined code/proof/benchmark DOI record, with configurable independent records. Display badges only for actual verified published records and label their coverage accurately. Prepare draft metadata first; the lead student owns the Zenodo records and performs final publication after advisor review, with packaging automated. A central lab publisher is not selected. The first meaningful publication is deliberate, not an automatic bootstrap side effect. Version versus concept DOI display follows the publication owner's concrete metadata contract. No draft DOI is a published-record badge. Badge repository targets come from actual source-repository metadata, not legacy template names.

A green paper-build badge establishes compilation of its Git commit, not that Overleaf currently matches it. Badge targets refer to the monorepo; component README links retain the monorepo directory structure under native sync. Do not add a custom bridge or sync-status workflow.

GitHub states that private-repository workflow badges are inaccessible externally. Use authenticated GitHub workflow/run links for private projects; do not promise these badges will work in external rendered Markdown or public exports. Never embed access tokens or introduce a public status proxy implicitly. Source: [GitHub workflow badge documentation](https://docs.github.com/en/actions/how-tos/monitor-workflows/add-a-status-badge).

## Accepted onboarding and release documentation inputs

Bootstrap requires Git, Python, GitHub CLI and Docker. Selected local build/prover tools remain optional by component. The real benchmark interface is accepted; document its implemented commands rather than placeholders. The advisor creates the organization repository, configures access, imports it into premium Overleaf, invites paper collaborators and sets up the Zotero group. The student creates personal accounts, installs required tools, accepts invitations, clones and configures the workspace. They jointly verify compilation and native sync. The setup owner supplies the concrete commands and completion evidence; do not describe unimplemented automation as available.

Students are outside collaborators with WRITE access only to their own project. Advisors handle settings/access, organization base permission is none, and owners control repository creation, deletion and transfer. Imre Kocsis becomes second owner only once he agrees; no agreement or contact is implied. Ended projects are archived in the organization, with student-requested transfer or full-history copy coordinated with coauthors, not student-repository deletion.

The finished `TDK-template` is the single public reusable template after contents/history disclosure preparation; project repositories remain private and organization-owned. The public README can show the template's own verified workflow badges, while generated private-project READMEs use their own metadata and authenticated result links. Public template status must never stand in for private project status.

Repository-wide immutable GitHub releases are accepted. Include Dockerfiles and build configuration as source, and record actual built image digests as evidence. Immutable GitHub releases do not freeze GHCR tags; image references must preserve the recorded digest identity. This does not choose credentials, publication visibility or automatic publication.

## Native Overleaf pilot and README acceptance

Prepare instructions for native GitHub import, choosing the agreed compiler and unique root main document, compilation, and native push/pull. The root entrypoints must have distinct names from component TeX entrypoints. Document the validated commands and paths after the pilot; do not claim that a successful local build proves the Overleaf root entrypoint works. The pilot is a future acceptance activity, not authorization for live configuration now.

Before import, measure all tracked components, including scratch, proof, benchmark and presentation. Record tracked file count, total editable-text bytes, largest editable text file and total tracked payload against the coordinator's verified Overleaf limits. The earlier shared-plan snapshot lists 2,000 files, 7 MB editable material, 2 MB per editable file and a recommendation below 100 MB for Git-backed projects; treat these as dated inputs requiring confirmation before execution, not newly verified service guarantees. Set explicit project budgets with growth headroom and report remaining capacity. Keep large data, build outputs and installed dependencies untracked; ignore patterns do not remove files already tracked.

Inspect tracked executable modes and symlinks before import and compare them after the round trip. Account for executable-mode resets; do not assume native sync preserves executable bits or symlink semantics. Flag affected files and stop unsupported cases for a concrete resolution. Do not flatten symlinks, blanket-normalize modes in arbitrary student code, or promise filesystem compatibility without evidence. Template-owned scripts can use explicit interpreters, such as `bash path/to/script.sh` or `python3 path/to/script.py`, in documented commands and CI. Student tools needing executable files or symlinks need an individually verified approach.

The pilot should record the starting and resulting Git commits, import the whole repository, compile through the root entrypoints, make a harmless Overleaf edit and push it to GitHub, then make a Git-side edit and pull it into Overleaf. Verify both edits survive, inspect unexpected content/mode/symlink changes across all components, and rebuild. Use native conflict handling when concurrent Git-side work exists; do not assume the editing-scope convention prevents divergence or sync-induced metadata changes.

From a fresh checkout of the resulting Git revision, run the documented code build/tests and benchmark smoke checks, plus checks for enabled proof profiles. Verify invocation actually works after the round trip, rather than only comparing file contents. Keep dependencies and outputs untracked during these checks. Report native-sync pilot evidence separately from the ordinary paper-build badge; the badge does not certify current Overleaf synchronization or completion of this pilot.

## Decisions returned to the coordinator

- Student repositories are private and organization-owned. Derive badge targets from actual repository metadata; the finished template becomes public only after contents/history disclosure preparation. Credential location/execution, 2FA, automation App/controller, public licensing and mechanical old-guide fixes remain downstream choices; do not infer them.
- Confirm unique root compilation entrypoint names and documented native import/compile/push-pull steps for the planned whole-monorepo sync. Custom bridge execution and a separate paper repository are not planned options.
- Obtain the dedicated CI owner's settled filenames, display names, trigger/filter behavior, success/failure/skipped semantics and run/commit-bound artifact/report interface before introducing the three advertised statuses. Send architecture questions to that owner and user questions through the coordinator.
- Legacy template deletion follows a complete, verified monorepo and is owned by the coordinator/organization. No ongoing mirror badges; no deletion now or student-repository deletion. Existing student migration remains long-term only.
- Apply the combined code/proof/benchmark DOI default and any explicitly configured independent records to verified published metadata. Deliberate publication and actual record creation remain with the publication owner.

After those decisions: implement the README blocks and setup rewrite, validate every workflow path and generated target, inspect authenticated/private and unauthenticated/public behavior, and confirm the first default-branch runs. Demonstrate separately that a writing finding leaves technical build green and that a compilation/lint execution failure turns its technical status red. No live workflow reruns or paper builds were needed for this inventory.

## Withdrawn custom-bridge proposal (historical evidence only)

The text below records the earlier proposal and its validation plan. Martin's later **No bridge** decision supersedes it entirely; it is not an accepted requirement or implementation backlog. Its sole-editor and exclusion-of-multiple-editors statements were also based on a misinterpretation, since corrected: project collaborators may edit the paper in Overleaf.

> Keep `paper/README.md` usable both inside the monorepo and at the exported Overleaf root: paper-local instructions use component-relative links and commands, while links back to monorepo workflows use explicit repository URLs. Do not export root README links such as `../code/` into Overleaf or assume `.github/workflows/` travels with the paper. The paper README's badges describe monorepo CI and need no rewrite merely because `paper/` became the Overleaf root. Any later standalone public repository export is a different distribution target and needs its own badge values.
>
> Describe synchronization separately from compilation. Git-side changes and Martin's Overleaf edits must both survive round trips. A single Overleaf editor simplifies collaboration but does not eliminate divergent edits, interrupted transfers or retries. The sync owner must preserve a common base, stop on unresolved conflicts and make retries safe. A green paper-build badge establishes compilation of its Git commit, not that Overleaf currently matches it. If a sync status link is added later, its report must identify the compared revisions and distinguish success, conflict and pending work; do not infer synchronization from a passing build. The exported paper must build without files from `scratch/`, `proof/`, `code/` or `presentation/`.
>
> For the paper-only mapping, also validate README links in both locations and build an isolated export containing only `paper/` contents. Coordinate sync acceptance evidence with its owner: Git-only edits, Overleaf-only edits, divergent edits against the common base, and retry after interruption. Multiple-editor collaboration is outside this workflow's requirements.
