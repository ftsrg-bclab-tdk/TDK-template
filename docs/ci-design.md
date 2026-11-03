# Monorepo CI design

Status: CI1–CI11, M1/M2, R1–R6 and S1–S7 are settled. Source implementation and local/fixture validation are underway, 2026-11-04. There is no remaining CI policy interview. No workflow, runner routing, repository setting or publication action is enabled by this document. Questions belong in the coordinator session, not a separate interview here. This document is owned by the CI design session; `docs/monorepo-plan.md` and `docs/proof-tool-options.md` in the coordinator worktree are read-only inputs.

Coordinator: <t3-thread://v2/b5ffded3-854d-462a-a89d-25dfae6b2462/5b7b9f7e-a45a-4695-b8c4-83321cf38763>.

## Fixed inputs and boundaries

The first CI policy round is complete. Martin accepted CI1/2/3/4/6/7/8/9/10 with “Otherwise ok”; CI5 separate badges and CI11 latest toolchains/dependencies were already settled. Do not ask these defaults again. The accepted operating policies are recorded below.

CI6 additionally requires: “There were some committed external files in the paper and elsewhere, those should be downloaded and stored as an artifact.” Download/artifact handling is required, not merely an option to keep all binary snapshots in Git. The coordinator completed the factual inventory in `docs/external-input-inventory.md`; its consumer findings and the storage proposal below now guide delivery design. No tracked-file deletion is authorized now; compile-essential delivery, including native Overleaf, must be demonstrated first.

The two-way maintenance flow is also accepted: reusable project improvements become template PRs, then merged template improvements become project PRs, with no auto-merge in either direction. Template-owned eligibility, baseline/provenance and exclusion of student research/private metadata are accepted requirements. Weekly/manual cadence and maintainer selection of mixed-field edits are now accepted. Registration/authentication and concrete baseline storage remain open. These decisions do not authorize broad host upgrades, reboots or permission changes.

The accepted bootstrap requires Git, Python, GitHub CLI and Docker; selected local build/prover tools remain optional by component. New student repositories are private and organization-owned. The three old template repositories are to be deleted only after the monorepo is complete and verified, with history/assets/consumers preserved; no deletion is performed here and student repositories are excluded. R1–R6 are explicitly accepted: the finished monorepo becomes the single public reusable template after its contents and history are prepared for disclosure. This is the target state, not evidence that visibility has already changed.

The advisor provisions the organization repository/access, premium Overleaf import/invitations and Zotero group. The student creates or reuses personal accounts, installs required tools, accepts invitations and prepares the clone/workspace. Both verify compilation and the native sync round trip. Students are outside collaborators with write access only to their own project; advisors manage project settings/access. Organization base permission is none, and owners control repository creation, deletion and transfer. Imre Kocsis becomes a second owner once he agrees; no agreement or invitation is assumed. Completed projects remain archived in the organization, with student-requested transfer/full-history copy coordinated with coauthors and no student-project deletion.

The lead student owns the Zenodo records and performs final publication after advisor review; packaging is automated. A central lab publisher is not selected. S1–S7 settle the private maintenance controller/App, pre-invitation 2FA, student-invoked project publication with the student's Zenodo secret, mechanical legacy-guide repairs, scoped licenses/artwork permission and preserved history. The maintenance controller owns project registration/template baselines. Publication journals belong to each student project on publication-state at registry/zenodo.json (sandbox has a separate path), accessed with that project's GITHUB_TOKEN. No maintenance credential enters a student job. Live credentials and deployments are not evidence established by these decisions. Read-only checks and credential-free packaging do not gain publication authority from this decision.

The canonical maintained source is `FTSRG-BCLab-TDK/TDK-template`, currently private and intended to become public after disclosure preparation. Layout is `paper/`, `code/`, `benchmark/`, `proof/`, `scratch/`, `presentation/`, with root paper proxy entrypoints. Native Overleaf sync transports the whole monorepo. Only paper files are edited in Overleaf; students and advisors may collaborate. This convention does not preserve executable modes or symlinks. No custom bridge, separate paper repository or sole-editor restriction is in scope. Native Windows is excluded; Linux/WSL is primary. macOS uses the accepted container route, subject to actual host/architecture validation rather than a native toolchain matrix. Existing-student migration is long-term work.

The integration owner owns stacking/merging and path adaptation. The presentation owner owns its renderer/workflow implementation. Runner infrastructure and isolation belong to the runner owner; the user has authorized that owner's SSH work and requested minimal performance loss. CI design does not mutate that VM. The runner owner has now reported completed native offline sandbox tests; GitHub job integration remains unfinished. The existing persistent runner remains a trusted-workload route.

## Evidence inspected

GitHub API snapshots below were read on 2026-11-03. Successful runs are observations of the listed heads, not acceptance of the future merged monorepo.

| Source | Evidence and consequence |
| --- | --- |
| Canonical current `paper.yml` | PR opened/synchronize/reopened/ready_for_review; main/master pushes; dispatch. Draft PR jobs skipped. Separate `image` and `paper` jobs. Resolves `danteev/texlive:latest` once per run, then uses that digest. This gives within-run identity, not a stable toolchain across runs. Builds both PDFs, runs individual lint rules and again generates JSON, uploads review bundle for 14 days. No cross-component aggregate. |
| Core stack #20 → #22 → #23 → #24 → #25 → #26 → #21 | #20 `dfd951e` renames thesis/reviewer to draft/final, changes commands and review schema to 2. #26 `3929f61` corrects the old `BlackLight54/TDK-template` guard to `FTSRG-BCLab-TDK/TDK-template`. #21 `cfc79d0` includes it. In run 41711816607 the template tests actually execute; earlier green layers can skip them. |
| Side stack #12 → #11 → #17 | #12 `cd07fec` adds `bash scripts/lint-ci.sh`: raw finding exit 1 becomes successful reporting; other exits propagate. PR tests cover 0, 1, 2, 127, 139. Local strict checks remain. #17 `752464a` is draft; run 41334126649 is skipped, not validated. Integration must preserve both this semantic change and #20 naming. |
| #14 → #18, #15, #19 | #14 repaired at `0f53f98`; run 41717380725 passes paper build, but template-only checks are skipped on that base. These side branches need final integrated regression coverage. Their standalone green checks do not establish the final layout or current guard correctness. |
| Public code template `b993375` | `ci.yml` invokes `just build`, `just test`, `just reproduce --smoke`. Actual justfile recipes print TODOs. Demo runs on pushes; evaluation on main pushes; benchmark/robustness weekly and manually. Release only publishes GHCR, not selective Zenodo bundles. A successful scaffold command is not a test result. |
| Public notes template `9dd2e45` | Lifecycle expects submodules and `paper/thesis.tex`, old phases; uses `(age or 999)`, turning age zero into 999; `git -C component log` has no path restriction and therefore observes unrelated monorepo commits. Workflow commits generated outputs with write token. Missing paper suppresses the final failure. Adapt to scratch; do not import its green/readiness semantics. |
| Current paper helper | `include/preamble.tex:239` invokes `texlua scripts/lint.lua ... > lint-checks.tex` through shell escape. A TeX import prefix does not change shell cwd. Root proxies need explicit helper cwd/output handling, aux and bibliography tests. The required-file list in `rules-source.lua:52` hardcodes the 2025 review PDF; this is the preamble completeness list, not the separate companion-citation rule. |
| Presentation #28 | Initial head `882938b` failed hosted browser sandbox setup in run 41720645241 (51-second job); check/upload never ran. Owner reports repair `07bb8bd` with `/opt/google/chrome/chrome`, no sandbox disabling; new run pending at this snapshot. Commands: Node 22, `npm ci --ignore-scripts`, `npm run render`, `npm run check`, Chrome and poppler. Outputs include audience AND notes-bearing presenter PDFs, HTML/assets, PNGs, generated Markdown. Keep this distinction during packaging. |
| Runner #27 | Kit unit/shell checks took 16 seconds in run 41717406973; this validates kit code, not VM isolation. Subsequent owner report describes live service hardening and passing native offline sandbox isolation/cleanup tests; see the dated update below. GitHub jobs still use a persistent runner with shared job-visible credentials/runtime/workspace, so this route remains trusted-only. |

PRs and run evidence: [#12](https://github.com/FTSRG-BCLab-TDK/TDK-template/pull/12), [#20](https://github.com/FTSRG-BCLab-TDK/TDK-template/pull/20), [#26](https://github.com/FTSRG-BCLab-TDK/TDK-template/pull/26), [#28](https://github.com/FTSRG-BCLab-TDK/TDK-template/pull/28), [public code commands](https://github.com/FTSRG-BCLab-TDK/tdk-code-template/blob/b993375ab89cf0e29b2ceb6a2a0f9555640c86ba/justfile), [notes lifecycle](https://github.com/FTSRG-BCLab-TDK/tdk-notes-template/blob/9dd2e451279f0f508ec6a2bef7996eb24d6f9343/scripts/lifecycle.py).

### Observed time and storage

Durations are API job/step timestamps, not projected student performance or billed usage. The sample has four paper runs, no successful integrated code/proof/full-benchmark run.

| Run / source | Image job | Paper job | Container initialization | Draft / final compilation | Template suites | Review artifact |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [41711816607](https://github.com/FTSRG-BCLab-TDK/TDK-template/actions/runs/41711816607), #26 | 7 s | 330 s | 165 s | 32 / 11 s | 28 + 45 s | 1,525,503 bytes |
| [41711837426](https://github.com/FTSRG-BCLab-TDK/TDK-template/actions/runs/41711837426), #21 | 6 s | 319 s | 134 s | 41 / 14 s | 32 + 57 s | 1,530,593 bytes |
| [41717380725](https://github.com/FTSRG-BCLab-TDK/TDK-template/actions/runs/41717380725), #14 | 6 s | 230 s | 133 s | 40 / 14 s | skipped | 1,440,282 bytes |
| [41720644953](https://github.com/FTSRG-BCLab-TDK/TDK-template/actions/runs/41720644953), initial #28 | 6 s | 250 s | 136 s | 44 / 15 s | skipped | 1,440,631 bytes |

These observations favor keeping both paper outputs in one warm job and avoiding a second TeX image for lint badges. They do not establish a target for theorem proving or full benchmarks. Record elapsed time, runner class, cold/warm state and result bytes in the pilot. Set per-profile limits after smoke and representative measurements; do not market a five-minute whole-monorepo guarantee.

The current official Free-org allowance is a $12 monthly compute pool, equivalent to 2,000 baseline Linux minutes only if no other eligible use consumes it; artifact/Packages storage is 500 MB, cache 10 GB/repo. Jobs round up individually. At the listed standard Linux rate, these two-job paper samples would account for 5–7 rounded minutes before other jobs. This is arithmetic from observations, not a billing statement. Self-hosted compute is free from GitHub, but uploaded artifacts still consume storage. [Billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [allowance](https://docs.github.com/en/billing/reference/product-usage-included), [runner prices](https://docs.github.com/en/billing/reference/actions-runner-pricing).

### Runner evidence update, 2026-11-03

The runner owner reports the following live results. This CI session has now inspected the pinned README and evidence report at PR #27 head `035b0bd5535705fa2d75b43485bd240c221057b5`, but has not independently rerun the live probes. The owner reports all eight deployed executable/config files hash-match the sources and an idempotent installer apply passed. These host results remain attributed to that report.

Pinned sources: [execution and unfinished-integration contract](https://github.com/ftsrg-bclab-tdk/TDK-template/blob/035b0bd5535705fa2d75b43485bd240c221057b5/infra/github-runners/native/README.md), [live evidence](https://github.com/ftsrg-bclab-tdk/TDK-template/blob/035b0bd5535705fa2d75b43485bd240c221057b5/infra/github-runners/native/evidence-2026-11-03.md), [reproduction probes](https://github.com/ftsrg-bclab-tdk/TDK-template/blob/035b0bd5535705fa2d75b43485bd240c221057b5/infra/github-runners/native/verify.py). The same directory contains `sandbox.py`, `trusted.conf`, `egress.py`, `install.sh` and `tdk-native.apparmor`. [Runner-kit CI](https://github.com/ftsrg-bclab-tdk/TDK-template/actions/runs/41726320276) passed on this head. The separate paper job was still running when inspected; neither result substitutes for end-to-end sandbox dispatch evidence.

The idle persistent organization runner was migrated from sudo-capable `cloud` to unprivileged `tdk-ci`. The service has NoNewPrivileges, empty capabilities, protected home/strict host filesystem, namespace restrictions and cgroup limits. UID-scoped nft rules allow public TCP 443 and local stub DNS, denying host/private/metadata addresses and other ports. GitHub connectivity remains working. This hardens the host, but job steps still share the runner's credentials, runtime and workspace. Treat it as trusted-only; public HTTPS access also means it is not a no-exfiltration boundary.

A separate root-operated offline command sandbox uses systemd DynamicUser plus bwrap user/PID/mount/IPC/UTS/network namespaces, disposable tmpfs, no host secrets/sockets, zero network and external cgroup resource/cleanup controls. Reported live tests passed concurrent filesystem/process/socket separation, host credential/environment exclusion, privilege/mount/user-namespace denial, cancellation/background-child cleanup, timeout, OOM and controller SIGKILL, with no surviving units. The host kernel is shared. The pinned evidence clarifies that QEMU packages installed during the initial probe were subsequently removed; no QEMU job was launched.

Three small SHA256 workloads produced host median 1.311 s and sandbox median 1.451 s including setup/teardown, approximately 140 ms overhead. These are the owner's microbenchmark observations, not representative TeX/prover/browser throughput or a promised CI penalty.

Current invocation is root-only `sandbox.py --seconds N -- /usr/bin/COMMAND ...`, with explicit transient-unit cancellation, no Docker/socket/host mounts and no network. It is not transparently attached to GitHub. A user-editable workflow wrapper would not confine arbitrary workflow YAML. Broader routing still requires a fresh JIT runner session inside each sandbox, controlled Actions/dependency network access, a per-run resolved image/toolchain identity and input/output/container contract, and external cancellation/admission wiring with demonstrated cleanup of that complete session. The current sandbox shares the host's read-only `/usr`, not a sealed build image; the hardened persistent service does not support Docker/container workflows. The owner reports org runner administration currently returns HTTP 403 for its token, so a registration authority and actual pilot target are still needed for fresh JIT sessions. The offline command probe does not establish these integration properties.

CI integration should consume source/config/runner-class identities plus the runner owner's reproducible test logs, configuration revision and representative workload measurements. Cancellation needs an externally enforced unit/session cleanup receipt; a cancelled job cannot certify its own successful cleanup. No component routing changed, and this update does not authorize one.

### GitHub plan constraints

Private Free organization repositories cannot enforce protected-branch required checks or branch/tag rulesets. Environments are unavailable on private Free; Team enables private environments but not private required-reviewer approval protections, which need Enterprise. Private Free repositories cannot consume organization Actions secrets or variables; repository-level secrets remain available. A dispatch button inside a student-writable repository does not protect a shared advisor token from writers who can change its workflow. These are design constraints, not proposed upgrades. [Branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches), [rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets), [environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments), [secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).

A path-filtered workflow can leave a required check pending; an `if`-skipped job can satisfy GitHub's success requirement. Therefore a stable aggregate must inspect its expected work and result records rather than trusting green/skipped conclusions. [Skipped workflows](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs), [job conditions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions), [required checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).

## Proposed architecture

The implemented workflow names are ci.yml (Project checks), paper-build.yml (Paper build) and paper-lint.yml (Paper lint report). The latter two consume the exact completed default-branch push run/attempt artifact; they execute no producer code and compile no TeX. Source fixtures and clean local orchestration have passed; live GitHub delivery/badge behavior remains a deployment pilot.

Proposed root `ci.yml` (`Project checks`) exposes an always-evaluated `ci/required` aggregate. The original single event-owner proposal needs distinct badge workflow integration under accepted CI5; exact event ownership must now implement accepted CI3 and the separate-badge handoff without duplicate builds. It performs plan → component execution → evidence validation. Keep independent component work parallel, but keep paper compilation/lint/evidence together to reuse the toolchain and generated files. Lightweight structure, official-file integrity and scratch reporting can share a job rather than paying for a runner per tiny check.

Reusable component workflows take explicit source SHA and profile inputs. The presentation owner's workflow can retain its component implementation. Paper build and lint need distinct badge-addressable workflows; a called job alone must not be assumed to provide a separate native badge. Event subscriptions and consumer wiring must be tested before replacing the existing workflow. No simultaneous old/new event triggers. Dedicated `template.yml` (`Template maintenance`) adds generated-project fixtures, template consistency/regression tests, proof adapter positive/negative examples, packaging/config adapters and onboarding tests. It calls the same implementation commands, using the paper outputs already built for that run where possible. Student copies execute their configured work, never skeleton-refresh or template-overwrite targets. Use explicit maintainer role/config and known repository identity checks, with a regression test that a canonical run actually executes expected maintainer jobs. Do not rely on a silently false hardcoded slug.

Other separate entrypoints have distinct purposes: `research-full.yml` for explicitly requested expensive experiments, `references.yml` for maintainer network freshness, `release-prepare.yml` for credential-free immutable bundles. Publication control must implement the accepted lead-student ownership and advisor-review policy once credential location/execution is settled. Do not invent an approval environment on the Free private plan.

### Shared local/CI commands

Native commands remain available. The root Python dispatcher implements this interface; invoking it by interpreter survives Overleaf executable-mode changes:

```
python3 scripts/project.py doctor
python3 scripts/project.py plan --scope affected --base BASE_SHA --head SOURCE_SHA
python3 scripts/project.py check --scope all --report-dir out/checks
python3 scripts/project.py check --component paper --mode submit --report-dir out/checks
python3 scripts/project.py check --component proof --profile lean --report-dir out/checks
python3 scripts/project.py check --component benchmark --mode full --report-dir out/checks
```

The dispatcher reads validated committed configuration, uses explicit component cwd and argument arrays, and records native commands/exits. It does not install dependencies during `check`, infer enabled components from empty directories, use `eval`, change `lintphase`, or pretend example checks validate a student's research. Source SHA is actual `git rev-parse HEAD`; local dirty state is recorded and cannot qualify for immutable release/onboarding evidence. CI executes the same checks, with its event/runner identity added to the report. Raw lint exits remain intact inside that report, regardless of aggregate policy.

| Component | Actual operation / adaptation |
| --- | --- |
| Paper | After #20 integration, `make -C paper draft final`, then one lint JSON execution against final, report generation and strict submission evaluation when requested. Existing `make check-final` / `make check-submit` stay available locally. Render summaries from the same result rather than invoking every rule twice. Root proxies use unique names agreed with Overleaf owner; test both proxy and component build routes in template/pilot checks, and root-proxy changes trigger paper checks. Never claim merely importing TeX fixed shell cwd. |
| Code | Project declares real build/test commands and expected test evidence. The inherited TODO recipes are unconfigured. Separate template-adapter smoke results from project tests. Code-only hygiene is scoped to code; whole-tree hygiene checks generated files/secrets/transport constraints without banning legitimate paper/agent files. |
| Proof | Run only enabled profiles, with implementation dependencies in the graph. Each adapter resolves latest tool/solver once for the run and records the actual versions, selected obligations, bounds/assumptions, supported container/host, limits, and result parser. Enabled profile with no obligations, missing tool, parse failure, incomplete search or timeout cannot pass. |
| Benchmark | Smoke exercises data loading, one small workload and report schema. Full records repetitions/seeds/datasets/measurement hardware/environment and workload parameters. A quick successful run is not performance validation. Paper measurements require declared hardware/method; hosted/noisy results cannot silently replace them. |
| Presentation | Preserve the owner's render/check interface; its current locked `npm ci` installation must be adapted to the accepted latest-resolution policy. Resolve latest dependencies/toolchain once into a run-local resolution/lock artifact, install that resolution without lifecycle scripts as appropriate, and reuse it within the run. Record browser/font/Node versions, resolution and output hashes. A checked-in old lockfile must not silently override latest mode. Build success says rendering checks passed, not scientific quality. Presenter notes are private review material unless release selection explicitly includes them. |
| Scratch | Track research source; ignore temporary outputs/secrets; exclude scratch from public packages by default. Align lifecycle with topic/setup/research/plan/draft/polish/submit. Fix zero-age and restrict history queries to component paths; full history required for age evidence. Missing shallow history means unknown, not stale or fresh. Generate report artifacts; avoid automatic commits on every push. |
| External inputs and official references | Commit source expectations/manifests/provenance where feasible; download external bytes into versioned artifact packages. Validate schema, applicability, MIME/signature and content hashes against an accepted package before consumption. Weekly maintainer freshness checks distinguish changed sources, access failures and overdue review. Reuse a verified accepted package during outages without calling it fresh. Required missing/corrupt package is an explicit error. Durable retention and native Overleaf delivery are mandatory design dependencies; see below. |

Proof catalog coverage is intentionally separate from implementation readiness. Candidate adapters include Lean, Tamarin, ProVerif, TLC, TLAPS, Verus, Kani, OpenJML, KeY, Gobra, Solidity SMTChecker, Certora local/cloud. Maintain a capability table: implemented/tested, experimental or documentation-only. The template CI must exercise both valid and meaningfully false examples for every claimed supported adapter. Lean checks admissions/axioms; protocol models need reachability; bounded/model checks record bounds and completion; solver unknown cannot be normalized to verified. Hosted source upload/credentials are a separate opt-in decision, not an automatic consequence of enabling local Solidity support. Details and primary sources remain in the coordinator's proof catalog.

### Triggers and dependency handling

Accepted first-round event policy (exact wiring remains implementation work):

- Every PR event starts the lightweight planner, including draft PRs. Ready PRs run affected enabled components; drafts initially report only structure/config and clearly identify deferred work. Mark-ready and dispatch run the real checks. Pushes to the configured default branch run all enabled ordinary checks, so its current revision has actual baseline evidence. Other branch pushes use PRs or explicit dispatch, avoiding push+PR duplicates.
- Manual dispatch offers `all`, `submit`, `full` and selected component scopes. Scope is recorded; manual narrow success never means all configured components passed. Strict submission does not mutate the paper's phase.
- Full benchmark/robustness/long proof searches start manually by default. A project can later choose a measured schedule and resource cap. The template maintenance suite exercises every supported adapter on a regular schedule and relevant changes. Official freshness cadence is accepted as weekly, maintainer-only.
- A release request resolves one immutable source SHA, reuses qualifying checks/artifacts for exactly that SHA and config/toolchain identity, or performs missing credential-free work. It never consumes latest-branch assets. Full benchmark obligations required for a particular research artifact must be declared, not inferred from a generic green CI result. Publication uses explicit student workflow_dispatch; tags or published support releases do not start it.

The planner evaluates the full git diff, not GitHub's limited path-filter list. PR changes compare merge base to head; pushes use the actual before/after range. Added/deleted/renamed paths all count. Missing history/base, incomplete diff, unknown shared configuration or unclassified executable/build-helper changes select all relevant components. Record the reason for each selection. Pure documentation exceptions are explicit. Root proxies, shared config, Dockerfiles, `.dockerignore`, devcontainer inputs, any existing Compose files, toolchain resolution inputs, workflow/dispatcher changes and helper paths are graph inputs, not only component directories. Workflow/planner changes force broad validation.

Code changes fan out to dependent proof/benchmarks. Benchmarks or generated figure/table dependencies fan out to paper/presentation when declared. Proof may depend on implementation source, never an untracked stale copy. If optional cross-component outputs are required, represent producer/consumer order explicitly and use the same SHA; reject cycles. No undeclared cross-SHA artifact lookup. When dependency knowledge is uncertain, prefer rerunning to silently missing a check.

Proposed PR checkout is the head SHA, matching existing review evidence, with base and merge-base SHAs recorded. Default-branch CI tests the merged result. Thus PR checks alone do not prove compatibility with a changed base. If merge-preview testing is desired, record tested merge SHA and source head separately; never label a synthetic-merge PDF as the head artifact. Use explicit head-based artifact identity as the implementation proposal consistent with existing evidence, and keep merge-base/default-branch validation limits visible. Exact consumer behavior must be verified; this does not reopen the accepted trigger policy.

### Results, gates and badges

Separate execution from the finding. Suggested report fields:

- Execution: `completed`, `error`, `cancelled`, `not_run`.
- Result: `pass`, `findings`, `violated`, `unknown`, `not_configured`, `unaffected`, `deferred`.
- Scope: component/profile, selected obligations and mode; phase and rule severities where relevant.
- Gate outcome: `pass`, `fail`, `incomplete`, plus machine-readable reasons.

`ci/required` uses `always()` and checks the plan against every expected result. A selected check missing after dependency failure is incomplete/failing; it is not an intentional skip. Enabled proof unknown/timeout, test failure or missing required artifact fails. Writing findings are advisory under accepted CI1, while lint crashes/missing JSON fail. Disabled components are visible as not configured; unaffected PR components are explicitly outside that run's evidence. An empty or TODO-backed enabled component fails configuration. A draft-only report is incomplete and cannot satisfy onboarding/release acceptance, even if lightweight jobs succeed.

An ordinary gate pass means all work required by that run's declared policy passed. It does not establish all optional profiles, final submission readiness, Overleaf synchronization, scientific validity or publication. On the Free private plan this check is informative, not an enforced merge barrier.

CI5 is settled: provide separate CI, paper-build and lint-report badges. The single-badge recommendation is rejected. GitHub native badges address workflows, not jobs, so the implementation needs distinct status-producing workflows, not three differently labelled copies of one workflow's badge. Working names are `ci.yml` / `Project checks`, `paper-build.yml` / `Paper build`, and `paper-lint.yml` / `Paper lint report`; these are proposed interface names pending trigger/handoff validation, not enabled files.

Compile draft/final only once per selected execution. Build and lint can still share one resolved runtime and evidence production job, with distinct workflows consuming the corresponding recorded results; alternatively lint can execute against the exact build bundle without rebuilding TeX. Research the badge branch/event behavior and exact run-attempt selection before choosing the wiring. A build-status consumer must evaluate only actual build success; lint status must distinguish recorded findings from execution errors under accepted CI1. Neither can infer success from the producer workflow's overall color. CI aggregate evaluates all selected obligations.

Every consumer binds to producer repository, source/tested SHA, config digest, run ID, run attempt, artifact ID/digest and runtime resolution identity. A retry of the same source SHA may resolve newer dependencies, so SHA equality alone is insufficient. Missing, expired, cancelled or malformed evidence produces incomplete/failure, never reuse of another run's latest asset. Old consumer completion must not falsely present old evidence as the current default-branch result. Test non-default branches, PR heads/merge refs, reruns, failures and out-of-order completion before adopting native badge URLs. Exact event handling must implement accepted CI3; design acceptance alone is not a request to trigger live runs now.

Private repository badges still need authenticated links; never proxy private status or put tokens in image URLs.

### Evidence and artifacts

Proposed common schema `project-checks/v1` wraps component-native reports (including paper review schema 2) without discarding their detail. Each record includes:

```
source: repository, source_sha, tested_sha, base_sha, dirty
configuration: project_config_sha256, dependency_plan_sha256
control: workflow_sha, checker_sha, toolchain_image_digests, lockfile_hashes
execution: component, profile, mode, commands, cwd, started_at, completed_at,
           actor, method, runner_class, execution_status, raw_exit
result: outcome, obligations, bounds, assumptions, findings, gate_outcome, reasons
transport: run_id, run_attempt, job_id, artifact_id, artifact_name,
           archive_sha256, files[{path, bytes, sha256, audience}], log_reference
```

Before upload, artifact ID is absent. Upload finalization writes a separate transport receipt containing the immutable artifact ID and archive digest. Do not self-hash a receipt or fabricate upload identity inside its own archive. Local evidence uses file hashes/paths and no fake GitHub IDs. A summary links report and logs, identifies source/config/tool versions and always describes incomplete execution. Cancellation may prevent final upload; consumers must reject missing evidence rather than assume success.

Proposed artifact names: `checks-<sha>-<run>-<attempt>`, `paper-<sha>-<run>-<attempt>`, `presentation-<sha>-<run>-<attempt>`, `benchmark-<mode>-<sha>-<run>-<attempt>`, `proof-<profile>-<sha>-<run>-<attempt>`. Use full SHA and immutable IDs as authority, not display name alone. Do not overwrite a retry's earlier evidence. The overall report references component artifacts by ID/digest; avoid uploading the same large outputs twice.

Onboarding accepts exact source SHA/config digest, timestamp, actor/method and evidence references. It distinguishes operation completed from outcome verified and reports stale evidence separately. The native Overleaf pilot additionally records before/after commits, file count/editable-text/total budgets, blob/mode/symlink diff, root-proxy builds, and a fresh-clone run of all configured components AFTER the roundtrip. Ordinary CI cannot manufacture evidence of an Overleaf action. Budget and mode checks inspect all tracked components, including scratch; ignores do not remove tracked files.

Accepted CI8 retention: routine reports/PDFs 14 days; bulky review PNG/video/full-run raw output 7 days unless deliberately retained; pending release bundles 90 days. Release preparation copies the exact selected bytes and provenance to durable release-controlled storage before Actions expiration; publication operation state/receipts survive independently. If source artifacts expired, rebuild/recheck without credentials and create a new receipt for approval, never substitute another SHA. The release owner owns the durable registry and retry semantics. Required accepted external-input/reference packages are a separate durable class, not subject to routine 14/7-day expiry; their retention contract is below. Do not shorten repository-wide run/check history to match short artifact retention; GitHub now applies configured retention to run/check/status history too. [Retention](https://docs.github.com/en/organizations/managing-organization-settings/configuring-the-retention-period-for-github-actions-artifacts-and-logs-in-your-organization).

### Required external-input artifact contract (CI6 refinement)

The coordinator completed the [external-input inventory](/home/blacklight/.t3/worktrees/tdk-template/t3-51114be9/docs/external-input-inventory.md). Consume that evidence rather than running a duplicate audit. It identifies three faculty references, nine presentation runtime binaries and seven embedded paper assets, with actual consumers and provenance gaps. Redistribution/access conditions and delivery tests still need resolution. Authored research, generated output and external downloads are different origins; no blanket binary deletion rule follows from CI6.

Proposed common interface, pending inventory-specific paths/storage choice:

1. Tracked manifests identify publisher/source URLs, expected media type and filename, source/license expectations, applicable year/cycle/edition where relevant, and declared consumers/required paths. Track acceptance/provenance and package identity; keep downloaded bytes in artifacts where feasible.
2. A maintenance fetch produces a candidate package with per-file path, size, digest, detected MIME/signature, actual source URL, retrieval timestamp, response outcome and applicability evidence. Reject a login/error HTML page masquerading as PDF. A new download is not automatically an accepted replacement. Candidate and accepted package states are distinct.
3. Acceptance records reference the exact package content digest and approval/review evidence. Resolve an accepted package to an immutable retrieval identity and verify every required byte before use. The `external-inputs/v1` receipt binds manifest digest, package digest, inventory/file hashes and provenance; a separate `external-inputs-delivery/v1` record binds the storage locator. Consumer reports add the exact receipt digest to their inputs. Different packages cannot be interchanged merely because the project source SHA matches.
4. Source outages remain freshness findings. If an accepted package is available and verifies, the build may use it with `reused_accepted` plus the original retrieval/acceptance identity and a separate failed/unknown freshness result. Never label this as a successful new fetch. Missing/corrupt required bytes cause an explicit dependent-check failure; missing optional references remain visible as missing and cannot count as checked. A live download of different unreviewed bytes is not an outage fallback.
5. Required approved packages and provenance must remain retrievable independently of expiring Actions transport artifacts. Retain versions while referenced by a supported project baseline or release evidence. Do not silently delete a package because it is older than 14/7 days, replace its content at the same identifier or rely on best-effort cache eviction. Storage cleanup must account for references and report unavailable packages. Routine candidate logs/previews may follow CI8; the accepted package does not.
6. Keep artifact origin explicit for selective releases: `verified_reference` binding, not a fake tracked-source or built-output origin. Bind the receipt digest, accepted package digest and selected inventory member hash; source SHA alone is insufficient. Required packages must verify before dependent packaging succeeds. Evidence-only reference files need not be published on Zenodo; publication selection/rights remain with the release owner and coordinator. Release evidence retains the exact package identity and provenance, and required bytes remain durably available while referenced by either project baselines or release evidence.

Implementation status updated: the release owner implemented offline `verified_reference` selection and full-package verification in `scripts/release/packager.py`, with canonical schema `scripts/release/external-inputs.schema.json`. The receipt uses `schema`, `manifest_sha256`, `package_sha256`, `files[path,sha256,size]`, `provenance[publisher,source,retrieved_at,applicability]`, `acceptance[status,evidence]`, `license`, `redistribution`, `access`. This session's fetcher adopts that exact spelling and preserves raw receipt bytes; its isolated schema copy is byte-equality checked and should resolve to the canonical release schema after integration. Trusted acceptance and producer/run authenticity are outer requirements: hashes establish consistency, not authority. No store, uploader or live delivery is implemented by the packager.

The factual GitHub storage proposal below is now available; it has not been provisioned or accepted as a live deployment. Package partitioning and native Overleaf delivery still need integration. GitHub Actions artifacts alone cannot be the durable source and native whole-repository Overleaf does not automatically retrieve them. Before removing a compile-essential file, prove its supported delivery path in a fresh local/CI checkout AND the native Overleaf pilot, including offline/outage behavior. A pre-build fetch in CI alone is insufficient. An explicit retained compile subset may prove necessary, but only the inventory and delivery design can justify its boundaries. No file removal, hidden sync bridge, service provisioning or permission change is authorized by this refinement.

The existing hardcoded 2025 PDF required-file lint must become consumer-aware when migration occurs: validate declared required package inputs/availability rather than require a stale tracked path or ignore missing bytes. Hash/integrity checks remain offline after package retrieval; repository content hygiene must not conflate a verified downloaded artifact with a committed build output.

The latest toolchain policy is unchanged. Per-run tool/dependency resolution and approved reference-package identity are separate records. A freshness outage may reuse an approved reference package; it is not permission to silently fall back to an older compiler or dependency set.

The inventory and official GitHub storage research are complete below. No user file-identification question is needed. Repository-level release immutability and the small embedded-paper-asset exception are now accepted; registration/authentication stays with the coordinator. Do not repeat CI defaults or M1/M2.

### GitHub storage feasibility, verified 2026-11-03

Recommend one existing-GitHub design: accepted external packages as versioned **GitHub Release assets**, with a canonical copy in the existing template repository and exact-byte copies in each consuming project's own releases. The canonical repository is currently private; its accepted future public state requires disclosure and redistribution review of package bytes and provenance as well as Git history. Private upstream material must not become public merely by attaching it to a canonical release. Actions artifacts remain short-lived candidate/report transport. This is a proposal, not provisioning, publication or a visibility change.

Read-only live API evidence: `FTSRG-BCLab-TDK` reports plan `free`; `ftsrg-bclab-tdk/TDK-template` is private (repository ID `1437261410`); its release list is currently empty. `GET /repos/FTSRG-BCLab-TDK/TDK-template/immutable-releases` returned HTTP 200 with `enabled:false, enforced_by_owner:false`. The setting exists on this Free-private repository but is not enabled. No PUT, upload, release creation, access grant or visibility operation was performed. The documentation describes enabling it for future releases; an actual immutable upload/download pilot is still required before claiming end-to-end deployment validation. [Settings API](https://docs.github.com/en/rest/repos/repos#check-if-immutable-releases-are-enabled-for-a-repository).

#### Why this store fits

GitHub Releases support ordinary binary attachments, repository-reader access and API downloads. Official limits are up to 1,000 assets per release and under 2 GiB per file, with no total release-size or bandwidth limit listed. These bounds comfortably cover the inventoried faculty and presentation inputs. Releases are separate repository resources, not expiring workflow artifacts; the release documentation provides explicit deletion rather than Actions' day-based retention. This is suitable durable application storage, not a guarantee against account/repository deletion or provider failure. [Release storage/access](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases), [release management](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).

GitHub's immutable-release feature locks published asset contents and the associated tag; release title/notes can still change. The release itself can still be deleted, and the old immutable tag name cannot be reused. Therefore checksums and retained copies remain necessary. Immutability is a repository setting covering future releases, not a paid protected-branch/environment feature and not a per-asset access boundary. The user accepted enabling it on participating repositories, including the effect on all future support/research releases. Actual settings still await the prepared integration/pilot. Prepare all assets in a draft, verify, then publish; ordinary readers should not be expected to fetch an unpublished draft. [Immutable release behavior](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases), [GA announcement](https://github.blog/changelog/2025-10-28-immutable-releases-are-now-generally-available/).

Actions artifacts expire and require repository access, so increasing their retention or periodically re-uploading them is not the durable source contract. GitHub Packages is available on Free, but normal private registries share the 500 MB Actions/Packages storage allowance and include 1 GB monthly transfer. Container registry storage/bandwidth is currently free; that is a current billing policy, not an indefinite promise. Packages would introduce a registry/client and package-access setup for simple PDF/font/image archives. [Actions expiry](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts), [Packages billing](https://docs.github.com/en/billing/concepts/product-billing/github-packages).

GHCR is a viable alternate transport if a later requirement warrants it: its granular permissions can give selected project workflows package read access without granting repository access, and digest pulls identify exact content. Local users still need supported registry authentication, generally a classic PAT with package-read rights; package administration and deletion/recovery need separate handling. No GHCR package or access grant is required by the proposed Release-asset design. A deleted package/version has a documented restoration window of 30 days when its namespace/version remains available, not indefinite recovery. [Container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry), [package permissions](https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages), [package recovery](https://docs.github.com/en/packages/learn-github-packages/deleting-and-restoring-a-package).

#### Reader and CI access without a shared template credential

A project's `GITHUB_TOKEN` is scoped to that project and cannot read Release assets from a different private template repository. Do not give student-controlled workflows a broad maintainer credential or grant students the entire canonical repository merely to fetch assets. The proposed mirror removes that cross-repository dependency from normal CI and preserves a project-owned recovery copy after the template becomes public. Anonymous canonical retrieval can be tested after public disclosure; it is not the current access evidence. [Token scope](https://docs.github.com/en/actions/concepts/security/github_token).

The authorized onboarding/maintenance actor downloads a selected accepted package from the canonical release, verifies it, then copies the exact archive and receipt into the consuming project. Copying requires source read and destination release-write authority; reuse the coordinator's eventual onboarding/maintenance authentication design. Those credentials stay with that actor and never enter project CI. A trusted actor needs to verify the destination and its intended readers before replication; a release inherits repository visibility. No change to public/private policy, no public export and no new repository is proposed here.

Project CI retrieves its own repository's release asset with `GITHUB_TOKEN` and `contents: read`. Local bootstrap uses the user's authenticated GitHub CLI/API access to that project; a fine-grained token can use repository Contents-read permission if needed. The release-asset endpoint supports GitHub App installation/user tokens and fine-grained PATs; this route does not require a separate classic Packages token. API asset download uses its numeric asset ID with `Accept: application/octet-stream`, handling both a direct response and redirect. Do not log temporary signed URLs or propagate authorization to unrelated redirect hosts. [Release-asset API](https://docs.github.com/en/rest/releases/assets#get-a-release-asset).

Local convenience can use `gh release download TAG --repo OWNER/PROJECT --pattern EXACT_ASSET --dir DEST`, always specifying tag and filename; omitting the tag can select latest. The production fetcher additionally verifies the immutable locator and digests from the receipt. Never use `latest` to identify an approved package. [CLI download semantics](https://cli.github.com/manual/gh_release_download).

Read-only APIs prove the current account can inspect the canonical repository; they do not simulate a student's access or a job-scoped token. Pilot both student read-only local access and same-project CI token access before declaring bootstrap complete. First-time offline bootstrap with neither a mirror nor verified local cache fails explicitly.

#### Content identity, promotion and retention

Use separate package identities for faculty references and presentation runtime assets so acceptance/applicability changes do not unnecessarily replace unrelated assets. The manifest and `external-inputs/v1` receipt remain the authority. Suggested release namespace `external-inputs/<package>/<content-id>` is operational metadata, not a research release version or DOI. A release tag targets the manifest/acceptance commit; the archive digest and per-member hashes identify bytes. Source provenance includes original upstream URL/revision or a truthful legacy-Git origin where no download provenance exists. Do not invent a retrieval date for bytes only recovered from history.

Upload a self-contained archive and its acceptance/inventory receipt. The outer delivery record binds repository numeric ID/name, release ID, tag, asset ID, archive digest, receipt digest, source-manifest commit and package identity. Canonical and project copies have different release/asset IDs but identical archive bytes and accepted package/receipt digest. Record each copy with a separate delivery locator, not a modified acceptance receipt. Never rely on mutable release notes, a filename or tag alone as evidence. Verify size/digest before bounded extraction; reject paths outside the declared inventory and no unapproved executable hooks. Local materialization goes to explicit ignored consumer paths, preserving tracked student files.

Promote by preparing a draft, uploading all package bytes/receipts, downloading and verifying them, then publishing and recording the immutable state. Set these support releases as not-latest; publisher automation must explicitly exclude this namespace/package kind, rather than treat every `release:published` event as a Zenodo research submission. The selective-release owner owns that trigger discrimination. These packages neither mint DOIs nor change publication grouping. [Release API](https://docs.github.com/en/rest/releases/releases#create-a-release).

Accepted packages receive no routine cleanup while any supported project baseline or release evidence references them. Maintenance validates registered references and reports a missing locator or failed integrity check; it does not silently prune old versions. Preserve the canonical archive plus consuming-project copies as operational redundancy. A project writer can still delete a whole release, and all copies use the same GitHub provider; this is not independent disaster recovery. Existing verified local copies can bridge service outages, but do not replace durable storage.

Recovery: if a project copy is lost, the authorized maintenance actor restores the exact canonical bytes under a new release/tag if necessary, verifies hashes and records a replacement delivery locator linked to the original acceptance identity. Never claim the old release/asset ID still exists. If the canonical copy is lost, an authorized verified replica can recover the same bytes. If no matching copy survives, report the package unavailable; re-download/rebuild cannot impersonate the accepted archive unless all required recorded identities verify. Different bytes require a new candidate and acceptance, not a silent locator update.

This architecture stays within existing repositories and avoids a new storage service or ongoing cross-repository read secret in student CI. It supports the accepted future public template and private student projects, subject to each package's reviewed disclosure/redistribution terms. It adds a bounded copy operation to the already planned authorized onboarding/update process. No mirror or source release currently exists, so availability remains a future acceptance test.

#### Inventory-specific delivery limits

The [completed inventory](/home/blacklight/.t3/worktrees/tdk-template/t3-51114be9/docs/external-input-inventory.md) shows that the three faculty attachments are not embedded in the paper PDFs. The review sheet nevertheless is hard-required by source lint, including Overleaf Checks, and skim reads its scoring bands. Package retrieval must precede full local/CI review, and source-only Overleaf checks must explicitly report that artifact-dependent review was not performed there. Do not silently drop the requirement or count skim's degraded mode as a full review.

The presentation owner accepted presentation-relative package members under `assets/fonts/`, `assets/logos/` and the two graph JPGs, with an exact nine-file receipt inventory. Fetch into a fresh ignored per-run staging root; the component composes `dist/assets` from verified binaries and tracked font notices, preserving existing slides/CSS URLs. Render offline with fonts and local assets checked. Receipt/delivery/fetch evidence accompanies run evidence. After migration there is no silent tracked-asset fallback; only explicitly verified accepted-cache reuse during retrieval outages. Real receipt/source-manifest/delivery and an integration snapshot are still needed before fresh-clone fetch/render/check acceptance or removal. Their exact ancestor byte match is provenance evidence; permission to redistribute or source accessibility is not inferred from it. Test removing the tracked copies only after this materialization route works in a fresh checkout.

The coordinator's public-disclosure audit verified through the live GitHub API that `BlackLight54/avn-tamarin-tutorial` is private. The exact match at commit `977b42f237ab6434be0bc5dc11a6196951e48a0e` therefore establishes provenance, not anonymous download availability. Fresh student builds consume accepted canonical/project packages, never require private-upstream access or its credentials. Authorized maintainer ingestion remains viable after redistribution terms are settled. Public-source retrieval is unproven; no binary removal or public upload follows from this finding.

The seven paper assets are actually embedded in draft/title/guide output. Neither Release assets nor Packages makes them automatically available to native Overleaf. The user accepted retaining these small embedded paper assets in Git for native Overleaf. This exception does not cover presentation binaries or faculty attachments. Do not remove the seven retained assets or create a bridge/network fetch in TeX. The locally modified bibliography style is maintained source; the 134 generated review records are evidence, not external inputs, and need separate archive/cleanup handling.

#### Storage decisions now settled

The user accepted repository-level immutable GitHub releases, draft-first attach/verify then publication, and keeping embedded paper assets tracked for native Overleaf. GitHub Release immutability does not freeze GHCR tags; retain image/platform digests separately. No repeated immutability or asset-exception question remains. Settings, authorized package replication and live access tests still await integration; credentials/routing remain with the coordinator.

### Execution environment and permissions

CI11 is settled: use latest toolchains/dependencies in normal CI, not committed-version pin maintenance. Resolve the relevant upstream current versions/images/dependency graph once per run, then reuse that concrete resolution across the run's build, lint and evidence stages. Record actual image digests, tool/solver/browser versions, action resolutions where applicable, dependency lock/resolution contents and hashes. Immutable recorded identities describe what executed; they do not impose source pins on the next run. Historical source references in this document likewise identify evidence, not a toolchain policy.

The paper environment must resolve all required tools (including aspell/detex, poppler and PyMuPDF); each proof adapter records its actual compiler/solver pairing. If latest components are unavailable or incompatible, report the failure and resolution evidence. Do not silently retry an older image/version or keep an old checked-in lock as a hidden default. Resolving latest can make the same source SHA behave differently in later runs, which is accepted; preserve historical built bytes and their runtime evidence rather than claiming reproducibility solely from source identity. Compatibility test work can expose upstream breakage and propose template adaptations; it must not reinstate mandatory pin-update PRs.

Keep proof environments separate from the large paper image. Cache dependencies by the actual current resolution plus OS/architecture, not merely a mutable `latest` label; fresh resolution must precede cache selection. Cached build outputs and gate results are not acceptance evidence. Release preparation uses verified dependency state and recorded output bytes, never arbitrary PR-produced executables from a shared cache. If historical bytes are missing, a new latest-runtime rebuild is a new candidate requiring its own checks and receipt, even at the same source SHA. This CI policy grants no authority to upgrade/reboot the persistent host or alter its installed services. [Cache access model](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching).

Ordinary student checks need read-only token and no shared publication credentials; disable checkout credential persistence. TeX shell escape, code tests, npm rendering and proof tools execute repository-controlled inputs. A student can edit workflow YAML as well as commands: restricting the official wrapper alone does not constrain arbitrary jobs on an accessible persistent runner. The owner has reported successful offline confinement/cleanup probes and small-workload timing; the fresh JIT session, network/image support and end-to-end job evidence remain prerequisites for broader routing. No automatic silent fallback after queue timeout: offer an explicit hosted route with clear source/environment evidence, avoiding simultaneous duplicate jobs.

Use cancellation for superseded read-only PR checks, keyed by workflow/PR (not by SHA, which would prevent replacement). Keep manual full experiments separately scoped. Publish/stage/writeback operations must serialize and must not be cancelled merely because a new push arrives; keep durable idempotency/operation state. The release owner handles remote timeout/partial-publication recovery. No `pull_request_target` checkout/execution of proposed content with elevated credentials and no shared advisor token in student-writable workflows.

Linux is the common build environment. WSL uses that environment but needs an actual host-side onboarding smoke test. macOS support, if accepted, is via the same validated container route, including architecture availability or documented emulation limitations. Do not promise native macOS verifier support or pay for native macOS CI by default. Template compatibility checks test fresh clones on supported hosts after meaningful setup changes and before a template release; ordinary project runs need not triple-run identical Linux containers.

## Design tree and current frontier

Settled roots include the full first CI round, R1–R6 ownership/access/public-template decisions, monorepo/native sync/layout, no sole-editor rule, Linux/WSL plus macOS container route, infrastructure ownership, two-way maintenance flow and no migration rollout now. Do not turn implementation details into repeated approval questions.

### Round CI-1 complete: decision record

| Decision | Accepted policy |
| --- | --- |
| CI1 | Writing findings advisory in ordinary CI; compilation/checker/configuration/report errors fail. Separate strict paper submission check; no automatic phase change. |
| CI2 | Explicit optional-component configuration; unused components visibly not configured. Enabled empty/TODO checks and inconclusive proofs cannot pass. |
| CI3 | Affected checks on ready PRs; all enabled ordinary checks on default-branch pushes; cheap draft feedback until ready; other branches use PRs/manual runs. |
| CI4 | Expensive full benchmarks/robustness/exploratory searches manual initially; schedules follow actual measurements. Routine smoke and configured proof obligations remain. |
| CI5 | Separate CI, paper-build and lint-report badges without duplicate paper builds. One-badge fallback rejected. |
| CI6 | Weekly maintainer freshness checks; deterministic integrity checks for consumers; outages do not block valid accepted inputs. External downloads MUST be stored as artifacts, with manifests/provenance/source expectations tracked where feasible. Inventory and native Overleaf delivery precede tracked-file removal. |
| CI7 | Advisory scratch lifecycle reports; no automatic generated-file commits on every push. Generator failures remain errors. |
| CI8 | Routine reports/PDFs 14 days, bulky previews/raw full-run output 7 days, pending release bundles 90 days; approved release evidence durable. Required approved reference packages also survive independently while referenced. |
| CI9 | Keep Free private plan; visible acceptance check and manual advisor discipline, no false claim of enforced branch/environment gates. |
| CI10 | Linux/WSL builds and tested macOS container route; no native macOS toolchain matrix or native Windows support. |
| CI11 | Latest toolchains/dependencies in normal CI, resolved once per run with actual versions/digests/lock resolution recorded. No mandatory committed pins, silent rollback or blanket host-upgrade authority. |

### Maintenance operating decisions complete (M1/M2)

M1 is accepted: weekly plus manual two-way maintenance, with no auto-merge.
M2 is accepted: automatic proposals only for established template-owned changes; mixed/private/research edits require maintainer selection in the authorized project context. Do not repeat either question. Registration/authentication and baseline storage mechanics remain integration dependencies under the coordinator.

### Two-way maintenance flow (accepted; operating choices open)

Martin explicitly accepted this flow: maintenance runs compare registered student-project revisions with recorded template baselines and propose eligible reusable template-owned improvements as canonical-template PRs. Once improvements merge into the template, maintenance proposes downstream project-update PRs. Neither direction auto-merges. Baseline/provenance and excluding student-authored research and private/project-specific metadata are accepted requirements; overlapping changes must be reported. Do not ask again whether to adopt this flow. Weekly/manual cadence and maintainer selection for mixed fields are settled; registration/authentication, concrete baseline mapping and implementation remain; no workflow has been configured.

Keep three operations distinct:

| Direction or purpose | Operation | Decision state |
| --- | --- | --- |
| Project → template | Propose eligible reusable improvements as canonical-template contribution PRs against the recorded baseline. | Accepted; no auto-merge. |
| Template → project | Propose template updates in project PRs, preserving student work and surfacing conflicts. | Accepted after template improvements merge; no auto-merge. |
| Latest compatibility testing | Exercise current dependencies/toolchains and expose incompatibilities; propose source adaptations where needed. | Latest normal runtime policy accepted; maintenance trigger/report/PR policy remains open. |

Upstream maintenance depends on project registration and read authority, provenance of the original template baseline and later applied updates, current canonical-template revision, path/field ownership maps, and explicit handling of mixed files. A whole-file diff from a template-owned path can still contain private titles, people, paper content or project configuration. Project publication manifests, registry state, DOIs, creators, receipts and onboarding identifiers must not be blindly copied into template PRs. The release owner has flagged these specific consumers. Candidate extraction must retain source/base identities, show omissions/conflicts, and prevent private source material appearing in PR descriptions, patches, logs or artifacts. Template-owned eligibility and research/private-metadata exclusion are accepted requirements. The concrete ownership map must implement the accepted rule: mixed/ambiguous edits are held for maintainer selection. Do not automatically copy a whole mixed file.

The accepted weekly/manual flow now needs project registration, authentication/actor permissions and baseline storage/update mechanics; mixed-file candidates stay for maintainer selection. PR directions are settled: upstream targets the canonical template; downstream targets registered projects. Do not infer account authority or scheduling defaults from acceptance of those directions. Downstream-update metadata should distinguish applied template revisions from local work and proposed upstream contributions to avoid loops. Latest compatibility failure is not by itself permission to copy project content upstream, roll back runtime versions or merge a change. No maintenance workflow or automatic PR creation is enabled.

### Remaining engineering validation (policies settled)

| Prerequisite | Next decisions / remaining evidence |
| --- | --- |
| Publication grouping/scope (CI1 settled) | Which selected paper releases demand strict submit checks; exemptions for early research artifacts; actual release approval wording. |
| Proof-support selection and adapter evidence (CI2 settled) | Initial implemented profile set; measured per-profile limits; hosted source-upload/account policy; experimental adapters' labels. No runtime estimates exist yet. |
| CI3 and CI5 settled; workflow behavior verification | Final workflow names, PR head vs merge-preview semantics, per-component dispatch details and verified separate-workflow exact-run handoff. Single-badge fallback is withdrawn. |
| Representative workload measurements (CI4 settled) | Full-run schedules, duration/memory/size caps, hardware reservation and retention of raw benchmark datasets. |
| Runner owner's GitHub session integration evidence | Offline isolation and cleanup probes now reported passing. Fresh JIT runner inside the sandbox, controlled network/image/input-output support and representative end-to-end tests remain outstanding. Then choose workload routing, labels and explicit hosted fallback; persistent runner remains trusted-only. |
| Student publication workflow accepted and implemented in source | Manual default-branch control workflow; exact reviewed source/bundle/runtime/artifact identities; project-owned publication-state journal; project GITHUB_TOKEN and student Zenodo secret. Fixture tests precede sandbox/live validation. Advisor review remains policy rather than an enforced Free-plan boundary. |
| Measured artifact sizes (CI8 settled) | Actual storage ceilings and export/publisher access controls; routine failure-log limits. |
| Inventory complete; GitHub Release-asset proposal researched | Apply accepted immutability/asset decisions through prepared integration; settle credentials and test canonical-to-project copies, local/CI retrieval, identity/recovery and native Overleaf consumer behavior before removing inputs. |
| Root-proxy implementation and native pilot | Actual entrypoint names, helper cwd/output locations, offline/Overleaf tool parity, whole-tree limits and fresh-clone post-sync acceptance. No substitute “local compile = Overleaf verified.” |
| Two-way maintenance flow accepted | Remaining integration choices: project registration/authentication, baseline storage/update contract and contribution/update loop prevention. Weekly/manual cadence and maintainer selection of mixed changes are accepted. Template-owned eligibility, provenance, exclusion of research/private metadata, PR directions and no auto-merge are settled. Keep latest compatibility testing distinct. |
| All policy rounds settled and implementation authorized | Continue source integration and actual pilots. No repeat policy gate. Public conversion, old-repository deletion and production publication still require their concrete completion evidence. |

## Integration handoff and acceptance

Before implementation, owners receive this proposed command/result/identity contract and return incompatibilities. Integration must finish the existing stacks without this session rebasing or merging them. Then implement in reviewable component changes, followed by a whole-project fixture and an actual native Overleaf pilot.

Acceptance must demonstrate: writing finding vs checker crash; missing/empty enabled code checks; verified/violated/unknown proof result; changed code triggering dependent proof/benchmark; root-proxy-only changes triggering paper; unknown diff falling back safely; canceled/skipped dependencies not passing aggregate; maintainer tests actually running; no template skeleton enforcement in student copies; exact-SHA artifact mismatch rejected; expired artifact handling; current lifecycle age zero and path-specific history; offline artifact integrity vs unreachable remote, verified accepted-package reuse, missing required package failure, retention while referenced and compile-input delivery after tracked-file migration; audience/presenter output separation; fresh-clone execution after roundtrip. Benchmark and adapter examples must test behavior, not just command exit conventions.

The user has confirmed all CI and operating rounds and explicitly instructed implementation without another policy gate. The grilling frontier is closed. Source implementation continues within that authorization; actual credentials, GitHub transport, native Overleaf roundtrip and public-disclosure completion are separate factual acceptance work.

## Concrete preparation delivered in this worktree

- `scripts/external_inputs/external_inputs.py`: standard-library receipt/delivery validation, source-manifest/hash binding, bounded GitHub Release-asset download, immutable release/repository/asset identity checks, full ZIP inventory verification and no-overwrite materialization. Exact accepted cached bytes may be reused on retrieval unavailability; corrupt/mismatched inputs fail. Source freshness is explicitly not checked. Commands and consumer staging contract are in its README.
- `scripts/external_inputs/{receipt,delivery}.schema.json`: canonical release receipt copied exactly for isolated preparation; separate locator schema `external-inputs-delivery/v1`. No acceptance locator mixed into the immutable receipt. Cache stores `<package_sha256>.zip` and exact `<receipt_sha256>.json`, compatible with the release packager input convention.
- `scripts/ci/dependencies.py`: pure changed-path selection with declared transitive component dependencies, root proxy patterns, conservative unknown/incomplete diff handling and explicit Dockerfile/.dockerignore/devcontainer/Compose/shared-helper invalidation. This is a planner, not a passing CI gate or executed workflow.

Validation: 18 external-input tests and 7 dependency-plan tests pass. The external tests include the actual CLI through a fake `gh` process, bounded download/timeout/error behavior, archive tampering/path hazards, identity rejection, outage reuse, missing-package failure and exact receipt retention. A release-owner fixture validates and verifies through this fetcher; JSON schemas validate the fixture and the receipt schema copy is byte-identical to the release owner's canonical file. No real private-release artifact or container execution is claimed.

Container requirements remain actual build plus execution of the selected smoke command, with latest resolution evidence (Docker/BuildKit/tool versions, source/context digests, image config ID versus registry/platform digest distinguished). Docker build configuration is maintained source where baseline ownership establishes that fact; project-customized mixed fields require selection. Selected reproduction packages include necessary Dockerfiles/context rules. No host Docker socket is made available to student jobs, and no BME routing is changed.

Integration owner was notified before source work. Existing workflows, root Makefile, #28 presentation snapshot, external binary assets, other worktrees and repository settings were not edited. All preparation remains local/uncommitted; no live package creation, source removal or legacy-template deletion occurred. Release packager logic remains owned by its component session; this work supplies acquisition/verification and dependency planning only.


## Implemented source and measured acceptance, 2026-11-04

The canonical configuration is ONE root project.json (schema 1), shared with setup.
It contains repository/role, editable paper_main, distinct paper_entrypoints,
managed metadata and explicit component profiles/dependencies. All evidence binds
its raw-byte digest. See scripts/ci/CONTRACT.md for the executable interfaces.

Commits f89c336 and ac9f1ba delivered configuration and doctor/plan/check plus
runtime/result/evidence APIs. Commit 078363b added hosted workflows and exact-run
paper status consumers. The clean orchestration first found a local repository
inference failure in review bundling; b85b7a6 fixed it by passing shared identity.
A fresh clone of b85b7a6 then passed full configured execution and verify_report:
both paper PDFs, advisory lint, the 37-file review bundle, maintainer tests and
presentation render/check against newly resolved npm dependencies. The source
was clean and the report retained 40 evidence files. Ordinary check evidence
still does not establish native Overleaf sync or scientific correctness.

The first local run took about 157 seconds including base-image retrieval; the
corrected clean run took about 95 seconds with the base already present. These
are measurements on this machine, not hosted-runner timings or promised budgets.
No shared cache is required in this implementation. Fresh resolution precedes
installation, and the exact npm lock is retained with the report. The TeX image
manifest, built image reference, Docker-reported local image ID/platform and
Docker/Buildx versions are recorded separately. No host Docker socket is mounted
into component workloads. BME routing remains unchanged.

The real weekly-reference command retrieved the eleven inventoried PDFs and
reported exactly the five required unresolved faculty inputs as failures. It
retains candidate bytes without accepting them or overwriting tracked sources.
Accepted durable reference packages and actual student retrieval remain a pilot;
current compile-essential/tracked assets have not been removed.

Manual release preparation consumes verified existing CI outputs for one source
and runtime, then calls the release owner's packager without executing selected
source. Publication verifies exact artifact and reviewed bundle-receipt digests,
uses default-branch control code and the student's account, and writes its journal
to the same project. The candidate archive and transport receipt are retained in
an immutable, not-latest release-candidates/<receipt-digest> GitHub Release before
Zenodo mutation, so operation recovery does not depend on the 90-day transport
artifact. These support releases mint no DOI and trigger no publication workflow.
Project-level permissions, default control ref and repository numeric identity are
validated before state-branch creation. No App/controller credentials are used.
The source is fixture-tested; no release, registry branch or Zenodo record has
been created by this session.

Raw output sizes in that clean run were 11,197,157 bytes for the main checks directory and 2,014,052 bytes for the native review bundle. These are filesystem sizes, not measured compressed GitHub storage charges. The native bundle repeats PDFs for review-consumer compatibility; compilation is shared.
