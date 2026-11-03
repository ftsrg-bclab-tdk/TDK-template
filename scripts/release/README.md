# Offline selective release packager

This component assembles selected bytes. It does not execute builds, fetch references, create GitHub releases, upload to Zenodo, or publish. Account/approval decisions remain with the coordinator. The accepted default is one code/proof/benchmark record; the manifest can group packages into independent records. Setup prepares draft metadata, followed by deliberate first meaningful publication.

Run from the repository root:

```sh
uv run --with jsonschema python scripts/release/packager.py \
  --repo . --source COMMIT_OR_TAG --manifest release/manifest.json \
  --runtime /path/to/runtime.json --out /path/to/new-bundle
```

`--manifest` and record `metadata_file` paths are read from the resolved source commit, not the working tree. `--source` resolves once; the returned full SHA is the resume identity. A caller resuming a plan must pass that SHA and reject a moved input tag. The CLI does not implement a durable operation registry. ZIPs use sorted entries, fixed timestamps and stored compression. Tracked executable modes are preserved; symlinks, gitlinks, LFS pointers, unsafe paths, case/Unicode collisions, missing files and untracked selections fail. V1 limits each input/package and expanded reference package to 512 MiB; larger releases need a streaming extension rather than bypassing checks.

Output is a new directory containing selected ZIPs, `receipt.json`, exact manifest/runtime/metadata bytes and any build/reference receipts. Existing output is never intentionally overwritten. Each ZIP contains member hashes and source/manifest/runtime/tool identities in `PROVENANCE.json`; package hashes appear only in the external receipt, avoiding self-hashing. The transport layer must bind that receipt digest to the exact CI run, attempt and artifact identity. The packager reports its actual Python/jsonschema versions and script/schema digests; control commit/config/run identities remain the caller's evidence envelope.

Runtime evidence is supplied by the producing run. Example shape (replace every example identity):

```json
{
  "schema": "runtime-evidence/v1",
  "tools": {"python": "actual resolved version", "prover": "selected tool version"},
  "images": [{"digest": "sha256:<64 hexadecimal digits>", "platform": "linux/amd64"}],
  "dependency_resolution": {"description": "actual lock/resolution identity from this run"}
}
```

Resolve latest tools/dependencies once per run; retaining this evidence does not require committed version pins. A later same-source build can use different tools and must not replace already verified candidate bytes. Dockerfiles and container build configuration are selected as tracked source. An image digest/platform is evidence, not an image archive; include an OCI archive only as an explicitly selected built file. GHCR tags are not frozen by immutable GitHub releases.

For `built` inputs, pass `--built-dir` and `--build-receipt`. The receipt must bind the same source and raw runtime-file SHA-256:

```json
{
  "schema": "build-outputs/v1",
  "source_sha": "resolved full commit ID",
  "runtime_sha256": "SHA-256 of exact runtime.json bytes",
  "outputs": {
    "result.txt": {"sha256": "SHA-256 of output", "size": 16, "profile": "benchmark-small"}
  }
}
```

The manifest's package `build_profile` must match each selected output. The packager verifies bytes, not the truth of a caller's claim that a test ran. CI must establish producer identity, completion and trust; cancelled runs are not sufficient evidence. Packaging does not replace scope-specific checks or metadata/license/content review.

## Verified references

The concrete local receipt schema is `external-inputs.schema.json`, using `external-inputs/v1`. Field spelling is an integration contract to reconcile with the CI owner. It includes accepted package and tracked source-manifest hashes, complete inventory with per-file hashes/sizes, publisher/source/retrieval/applicability, acceptance evidence, license, redistribution declaration and access. It intentionally excludes delivery locators so exact mirror copies retain receipt identity. Acceptance authority/authenticity must be established upstream; checking a hash does not establish approval or legal rights.

Manifest binding:

```json
{
  "references": {
    "faculty": {
      "receipt_sha256": "SHA-256 of exact acceptance receipt bytes",
      "package_sha256": "SHA-256 of complete accepted ZIP",
      "source_manifest": "references/faculty.json"
    }
  }
}
```

A package file then selects `{ "origin": "verified_reference", "reference": "faculty", "path": "rubric.pdf", "archive_path": "references/rubric.pdf" }`. Supply `--reference-dir` containing `<receipt_sha256>.json` and `<package_sha256>.zip`. The packager validates the entire ZIP against the receipt before selecting any member, checks the tracked source-manifest digest, and preserves exact receipt bytes in the output. No network requests or automatic fallback happen here: upstream may provide verified accepted outage-reuse bytes, reporting failed/unknown freshness separately. Missing/corrupt required packages fail. Public outputs reject restricted/embargoed reference input; redistribution must be explicitly allowed in the receipt. This conservative local rule is not a full embargo/access-policy engine.

Inventory evidence identifies three faculty documents and nine presentation binaries; source/rights for actual packages still need verification. Small embedded paper assets remain tracked under the accepted exception. Review-sheet lint/skim consumers must change before reference files are removed. This packager does not delete or migrate any of those files.

Future GitHub integration must attach and verify bytes in a draft before publishing immutable releases. `external-inputs/` support releases are not-latest, excluded from research/Zenodo triggers, and mint no DOI. Required accepted packages/receipts must survive Actions expiry while project baselines or releases reference them. Retained exact copies remain necessary because whole GitHub releases can be deleted. No release settings or uploads are performed by this component.

## Tests

```sh
uv run --with jsonschema python -m unittest discover -s scripts/release -v
uv run --with jsonschema python docs/selective-release/test_manifest.py
```

Tests use temporary Git repositories and synthetic reference packages only. Schema review copy: `docs/selective-release/manifest.schema.json`; canonical executable schema: this directory. Keep the review copy identical until integration removes the duplication.
