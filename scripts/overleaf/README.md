# Native pilot boundary

This adapter verifies a receipt from an explicitly trusted observer and the evidence
that observer signed. It does not perform synchronization. There is no custom bridge,
no CLI switch that trusts a JSON file, and no production observer key configured.
A signed statement still depends on the observer actually watching native operations.
The signature alone cannot prove a UI action occurred.

`boundary.verify_boundary(receipt_path, signature_path, *, allowed_signers,
principal, repository, tested_sha, config_digest, required_components)` returns an
immutable `VerifiedBoundary`. Pass that object to `onboarding.checks.ingest` as
`verified_boundary`. The adapter runs the shared CI verifier against the receipt's
report; ingestion also binds the report digest. It reports
`trusted_observer_verified`, keeps `onboarding_ready=False`, and does not verify
student invitations, Zotero, conflict recovery or general onboarding readiness.

The calling application must obtain `allowed_signers` and `principal` from an
operator-controlled policy outside the repository and evidence bundle. Never accept
them from receipt fields, student CLI options, repository configuration or downloaded
artifacts. No observer selection or key provisioning is implied by this implementation.
Until that policy exists, leave `verified_boundary=None`. Python objects are an API
misuse guard, not a sandbox against code running inside the verifier process.

## Receipt v1

The JSON root has exactly these fields:

- `schema`: `overleaf-native-pilot/v1`.
- `method`: `observed_native_ui`. Manual attestations remain separate records and fail verification.
- `actor`: the externally configured SSH principal.
- `repository`: exact GitHub `owner/name`; `overleaf_project_id`: the 24-character ID.
- `source_sha`: full GitHub commit observed after the native pull.
- `tested_sha`: full post-push commit, checked out in the fresh clone.
- `config_digest`: SHA-256 from the shared project configuration loader.
- `pull`, `push`, `clone`: each has `commit`, timezone-bearing `completed_at`, and `evidence`.
- `completed_at`: exactly `clone.completed_at`. This is the checkout boundary, before execution starts, not the later receipt signing time.
- `compilation`: keys `paper-draft.tex` and `paper-final.tex`, each an evidence member.
- `tree_audit`: evidence member for the Git audit JSON described below.
- `report`: evidence member for the fresh clone's `project-checks/v1` report.

Each evidence member is `{ "path": "bundle-relative/path", "sha256": "64 lowercase hex digits" }`.
Paths cannot escape the bundle or traverse symlinks. The report retains its own hashed
file inventory. Keep the full bundle outside the tracked source tree. Signing exact
receipt bytes uses OpenSSH SSHSIG namespace `tdk-overleaf-native-pilot-v1`; verification
needs `ssh-keygen` and Python's standard library. Do not put private keys in the bundle.
Test-generated keys and fixtures are synthetic and establish no production trust.

The observer must capture the native pull UI and resulting unique Git-side marker,
then the distinct Overleaf-side edit and native push UI, binding project/repository
and commits. Compilation evidence must include service logs/output for both proxies
and compiler/TeX Live settings. Clone evidence records the clone command, remote,
checked-out SHA and clean state. Run all configured components in that fresh clone
with the shared dispatcher after `clone.completed_at`. Hash its report and artifacts.
An ordinary CI report without these observations cannot establish this boundary.

## Tree audit

Run from any directory, supplying an actual local Git checkout:

```sh
python3 scripts/overleaf/audit.py BEFORE_SHA AFTER_SHA --repo /path/to/pilot > tree-audit.json
```

The read-only command records both complete tree inventories and all path/blob/mode
changes. Every change initially appears in `unexpected_changes`. The observer reviews
the actual diff and execution results, records explanations in the observation log,
and removes only resolved entries from that list before signing. Mode resets must be
recorded, including execution-sensitive paths; do not normalize files to hide changes.
Unresolved entries block the boundary. Symlinks, gitlinks and LFS pointers block it.

Inventories include count, payload bytes, conservative NUL-free text bytes, largest
such file and executable paths. The verifier enforces the contract's 2,000-file,
7,000,000-text-byte and 2,000,000-single-text-byte budgets on both trees. The 100 MB
payload target remains a recommendation. NUL-free classification is a local estimate;
record actual Overleaf limits/classification during import. Successful local budgeting
is not import evidence.

## Current access and scope

On 2026-11-04 (Europe/Budapest), supported browser default-profile checks redirected
Overleaf `/project` to `/login` and GitHub `/settings/profile` to `/login?return_to=...`.
Both sites require advisor login before repository integration/import can be checked.
No disposable repository or Overleaf project was created. The canonical project and
student content were untouched; the check tabs were closed.

Source candidate is assembled commit `808b38032571987ab51450e3960413ee59d9fac0`.
A same-commit local audit measured 309 paths, 7,735,935 payload bytes, 2,209,296
conservative text bytes, largest text file 132,138 bytes, 13 executable paths and no
symlinks, gitlinks or LFS pointers. This is baseline evidence only. Actual native
mode transformations and fresh-clone execution remain pending. Once logged in,
confirm premium ownership and linked repository access before creating a disposable
owner-only pilot from this source; no existing student project is a candidate.
