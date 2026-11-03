# Project checks and runtime evidence

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
