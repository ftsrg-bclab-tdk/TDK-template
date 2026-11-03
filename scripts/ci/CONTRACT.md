# Project checks and runtime evidence

Requires Python 3.11 or newer. The dispatcher and runtime/evidence helpers use the
standard library. Release transport and its integration tests also need the
release component's `jsonschema` dependency; CI resolves its current version.

`project.json` is the only project identity/configuration authority. Both setup and
checks call `ci.config.load_project(root, relative="project.json")`, returning the
validated object and SHA256 of its exact bytes. Declared paths need not exist yet;
consumers check existence. Repository `null` means setup is unfinished.

Run from the repository root:

```sh
python3 scripts/project.py doctor
python3 scripts/project.py plan --scope affected --base BASE_SHA
python3 scripts/project.py check --component paper --report-dir .project/checks
python3 scripts/project.py check --component paper --mode submit --report-dir .project/submit
```

`doctor` checks configuration, paths and executable discovery. It does not verify
service access, Docker execution or component results. `plan` records the full Git
diff and dependencies; unavailable history selects broadly. Draft plans defer real
checks. `check` runs argv arrays in component cwd, records exits/logs and checks
declared outputs. It installs nothing. Each report directory must be new.
Configured tests/proofs/benchmarks must emit a new `result_file`; existing results
are rejected. Optional disabled components remain `not_configured`.

## Adapter result files

Use `schema: "component-result/v1"`, `kind: "tests"|"proof"|"benchmark"` and
`outcome: "pass"|"verified"|"violated"|"unknown"`. Additional native evidence is
allowed. The outer project report supplies source/config/runtime/run identity.

* Tests require `tests: {passed, failed, skipped}` nonnegative integers and at
  least one executed test. A passing summary cannot contain failed tests.
* Proofs require nonempty unique `obligations: [{id, outcome}]`, `bounds: {}` and
  `assumptions: []`. Obligation outcomes are verified, violated or unknown. The
  summary must agree: violated takes precedence, then unknown, then verified.
* Benchmarks require `mode: "smoke"|"full"`, `parameters: {}` and nonempty
  `measurements: [{name, value, unit}]`. Values must be finite numbers. Record
  repetitions/seeds/input/hardware/method in native evidence. Smoke success is
  not a scientific performance claim.

Unknown proofs, empty tests, missing result files and command errors cannot pass.
Writing lint uses its native JSON, preserving rc 1 as advisory in ordinary mode;
rc 2, malformed JSON and rule status `error` fail. Submit mode is strict.

## Runtime resolution

`runtime.py oci --out .project/image.json` resolves `danteev/texlive:latest` once
to a registry manifest digest. Reuse that receipt within the run. An existing
receipt is not overwritten. No committed source pin or old-version fallback is
introduced.

For presentation, run `runtime.py snapshot --component presentation --npm-stage
.project/runtime/presentation --out .project/runtime.json`. It copies component
source to staging, requests latest direct dependencies, creates one run-local
lock and installs exactly that lock. Source package/lock files stay unchanged.
`project.py check --component presentation --runtime .project/runtime.json`
renders/checks the staged tree. Runtime reports record source/config identity,
actual tool versions, lock digest/resolved versions and stage path. Local checks
without runtime evidence are useful but cannot qualify as acceptance evidence.

## Portable verification API

`ci.evidence.verify_report(report_path, *, repository, tested_sha, config_sha256,
required_components, expected_report_sha256=None, after=None, require_clean=True,
require_runtime=True)` returns the validated `project-checks/v1` object or raises
`ValueError`. `after` is an aware ISO timestamp for the caller's verified
roundtrip/fresh-clone boundary; checks must have started after it. The caller
must establish that boundary separately. Neither a green report nor its hash
proves that Overleaf sync or a fresh clone occurred.

The verifier checks source/config/plan/runtime identities, clean source, actual
completed required components, execution timestamps/actor/method/log reference,
and the complete declared file inventory's sizes and SHA256 hashes. The exact
raw report hash can be supplied from a trusted receipt. Hashes establish
consistency; the CI transport must separately verify repository, workflow,
run/attempt and immutable artifact ID/digest. Artifact paths remain private
review evidence, including presenter notes. No remote publication is performed.

## Hosted workflows and separate badges

`ci.yml` / **Project checks** owns automatic PR/default-branch work and manual
component, strict-submit and full-benchmark runs. PRs test the head SHA; default
branch pushes test the merged commit. Drafts get source feedback and an explicitly
incomplete component report. Unknown/incomplete diffs select broadly.
`ci/required` rejects missing, skipped or failed expected jobs. The source job
resolves Python once and supplies that version to execution. Paper uses one
latest-resolved image and build for lint/review/maintainer tests. Presentation
uses one staged latest resolution. Optional disabled components remain visible.

`paper-build.yml` / **Paper build** and `paper-lint.yml` / **Paper lint report**
consume only default-branch push runs of Project checks. Badge URLs use the
configured default branch and `event=workflow_run`; the CI badge uses `event=push`.
Consumers check the producer repository ID/workflow/run/attempt/head SHA, exact
artifact name/ID/API digest and downloaded bytes. They inspect data with default
branch consumer code and execute no artifact content. A build failure cannot be
hidden behind a successful lint result or producer color. Unselected paper,
expired evidence, stale default-branch SHA and missing required data fail.

The primary artifact is `checks-<full-source-sha>-<run-id>-<attempt>` (14 days).
The native paper review bundle and presentation PNG previews are separate
7-day artifacts. PDFs remain in the primary evidence; the native review bundle
also contains its PDFs for compatibility with the review consumer. No duplicate
TeX compilation is performed. Release candidates use 90-day Actions transport.

## Release transport and publication state

`release-prepare.yml` is manual and reads selected source through Git plus an
exact successful checks artifact. It verifies all enabled components and rejects
selection from an unconfigured component. Selected paper files require strict
submit evidence. It exports existing built bytes and resolved runtime evidence
to the release packager; it does not rebuild or execute selected source. Built
paths retain component cwd prefixes, with profiles `<component>:<profile>`.

`publication.yml` is manual, from the current default-branch control ref, with an
explicit operation ID, phase, service, producer run/attempt/artifact identity,
source SHA, artifact digest and reviewed bundle-receipt digest. Source SHA may
differ from the release-preparation control SHA; the transport records both.
The publisher job alone gets `contents: write` plus `actions: read`. It uses the
project GITHUB_TOKEN for its own journal and the student's `ZENODO_TOKEN` or
`ZENODO_SANDBOX_TOKEN`. A missing sandbox token never falls back to production.
Advisor review is policy, not an enforced boundary in student-writable workflows.

Before a Zenodo mutation, verified candidate bytes and their transport receipt
are retained in a published immutable, not-latest GitHub support release named
`release-candidates/<reviewed-receipt-sha256>`. Draft assets are downloaded and
verified before publication; promotion requires the accepted immutable-release
setting. An expired Actions artifact can be replaced only by this matching
immutable copy. Changed bytes, mismatched producer identity and missing copies
fail; there is no same-source rebuild fallback. This support release creates no
DOI and starts no publication workflow automatically.

The dedicated `publication-state` branch starts with an isolated root commit,
without copied research history. The release component owns CAS/operation locks
in `registry/zenodo.json`, or `registry/zenodo-sandbox.json`. CI validates numeric
repository identity and current default control SHA before branch creation.
Branch bootstrap reconciles an ambiguous create by reading and never blindly
replays POST. Workflow concurrency serializes publication without automatic
cancellation. No maintenance App/controller credential enters this job.

These are implemented source interfaces and fixture-tested transports. No real
registry branch, GitHub release, secret or Zenodo record has been provisioned by
the CI session. Native Overleaf roundtrip and live Actions transport remain
separate acceptance evidence.
