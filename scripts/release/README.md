# Offline selective release packager

The packager assembles selected bytes without executing builds, fetching references or publishing. Separate uploader/registry/writeback commands below implement publication without executing research source. The lead student owns Zenodo records and performs final publication after advisor review. The student manually dispatches the project GitHub workflow using their own Zenodo repository secret and exact reviewed receipt; advisor review is policy, not an enforced boundary on student-writable workflows. No central lab publisher is selected. The accepted default is one code/proof/benchmark record; the manifest can group packages into independent records. Setup prepares draft metadata, followed by deliberate first meaningful publication.

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

Inventory evidence identifies three faculty documents and nine presentation binaries. Martin confirms redistribution permission for the two existing presentation graph JPGs, four institutional logo PNGs, and paper `bme_logo.pdf`; retain existing notices and coordinator provenance (`fbebde3`). This does not relicense source/prose or cover unrelated fonts/reference documents; their applicable evidence must still be carried into actual package receipts. Accepted reusable-source licenses are MIT for original code/tooling and CC BY 4.0 for original guide/slide prose, preserving inherited terms. Existing history/nonsecret disclosures are retained; generated evidence must be archived before starter-HEAD cleanup. Small embedded paper assets remain tracked under the accepted exception. Review-sheet lint/skim consumers must change before reference files are removed. This packager does not delete or migrate any of those files.

Future GitHub integration must attach and verify bytes in a draft before publishing immutable releases. `external-inputs/` support releases are not-latest, excluded from research/Zenodo triggers, and mint no DOI. Required accepted packages/receipts must survive Actions expiry while project baselines or releases reference them. Retained exact copies remain necessary because whole GitHub releases can be deleted. No release settings or uploads are performed by this component.

## Tests

```sh
uv run --with jsonschema python -m unittest discover -s scripts/release -v
uv run --with jsonschema python docs/selective-release/test_manifest.py
```

Tests use temporary Git repositories and synthetic reference packages only. Schema review copy: `docs/selective-release/manifest.schema.json`; canonical executable schema: this directory. Keep the review copy identical until integration removes the duplication.

## Student publication and durable operation state

`publisher.py` implements `stage`, `reconcile`, `publish`, and `receipt`. It reads and revalidates an already staged directory and never invokes the packager/build scripts, executes selected source, or extracts ZIPs. Metadata files are Zenodo metadata objects with explicit title, description, creators, upload_type, version, publication_date and access_right/license/access conditions. The manifest access must agree. Old/reserved DOIs are rejected in new metadata. A deterministic operation marker is appended to the uploaded description for crash recovery.

```sh
# ZENODO_TOKEN comes from the student's repository secret, never a CLI argument.
python scripts/release/publisher.py --phase stage \
  --bundle /verified/candidate --expected-receipt-sha256 REVIEWED_SHA256 \
  --operation-id study-1 --repository-id 123 --environment sandbox \
  --context /verified/publication-context.json \
  --registry-file /durable/authorized/registry.json --output /output/publication.json
```

Use the same operation/candidate identity for `publish` after advisor review and `reconcile` after an uncertain response. `receipt` also re-verifies remote state. `--environment production` is an explicit target switch, not permission to publish an unreviewed candidate. Sandbox/production registries cannot mix. An incomplete operation writes a status receipt and exits 2; successful phase completion exits 0. Metadata, filenames and states can be private: keep logs/receipts in the authorized project/controller stores.

Context shape (provided by CI's independently verified transport):

```json
{
  "schema": "publication-context/v1", "kind": "research",
  "repository_id": 123, "source_sha": "FULL_SOURCE_SHA", "control_sha": "FULL_CONTROL_SHA",
  "producer_run_id": 123, "producer_run_attempt": 1, "producer_artifact_id": 456,
  "artifact_sha256": "EXACT_TRANSPORT_ARCHIVE_SHA256"
}
```

CI must authenticate the repository/workflow/run/attempt/artifact, require completion and allowed event, enforce dispatch from the default control branch, and keep support `external-inputs/` releases out of research publication. This CLI verifies context consistency but does not substitute for GitHub API attestation. A newer control commit can resume the same candidate; its context is appended to the operation audit while producer identity remains fixed.

The POSIX registry adapter fsyncs atomic files and uses compare-and-swap plus a persistent writer lock. Its path must be durable authorized storage, never merely the ephemeral Actions workspace. The GitHub adapter (`--registry-github OWNER/REPO --registry-ref EXISTING_BRANCH --registry-path PATH`) implements Contents API CAS and verifies uncertain registry PUT results before allowing Zenodo writes. It reads `REGISTRY_GITHUB_TOKEN` separately from `ZENODO_TOKEN`. It does not create repositories or branches. The accepted private maintenance controller owns privileged registry/App access; do not install its key or broad token in a student-writable workflow. Controller/API mounting or scoped registry access must be connected by that owner before live CI use. These adapters do not mean deployment exists.

Intent is durable before every mutation. GETs have bounded retries; POST/PUT/DELETE have no blind retries. Lost create replies recover only from one exact operation-marker match. Missing/ambiguous matches stop. Newversion follows `links.latest_draft`, never assumes the action response is the new deposition. The previous version's inventory is saved; only verified inherited files may be removed from the new draft. Foreign edits stop. Upload readback compares full file inventory, sizes and Zenodo's MD5 checksums while local provenance retains SHA-256. Publication requires a verified published record, exact metadata and files, and API-returned version/concept DOI. A 202/pending response is not publication evidence. Multiple records are independent; published successes survive another record's failure.

Recovery is deliberately separate from ordinary workflow retries. `--phase recover --recover-record KEY --expected-registry-sha256 HASH --adopt-deposition-id ID` adopts a reviewed matching ambiguous create/newversion result. `--retry-missing-write` instead permits a reviewed missing upload or unresolved copied-metadata/inherited-file operation after checking current state. It never replays publish. `--phase unlock --expected-registry-sha256 HASH` clears a crash-left writer lock only after an operator has confirmed the previous process stopped. The digest is SHA-256 of canonical `packager.encode(registry_data)`. Do not auto-steal locks based on age. Zero-match create outcomes remain blocked rather than risk duplicate records; resolving a definitively rejected operation may require operator registry repair.

## Published receipts and DOI writeback

`publication-receipt.schema.json` is the shared `publication-receipt/v1` contract. Consumers need an independently trusted raw receipt digest and matching repository ID. Production badges/writeback require each selected record to be `published`, with version/concept DOI, record URL and verification time. Partial operations can contain published members; drafts/reserved DOIs and sandbox records cannot become production availability claims. The fixture under `fixtures/` is synthetic test data and must never be used for real badges.

```sh
python scripts/release/writeback.py --repo /project --receipt /verified/publication.json \
  --expected-receipt-sha256 TRUSTED_PUBLICATION_RECEIPT_SHA256 --repository-id 123 \
  --out /new/reviewable-writeback
```

This writes a patch and evidence, not changes to the repository. Defaults target README.md, paper/bib/references.bib and a dedicated paper/content/artifact-availability.tex. Supply actual integration paths if different. Only keyed generated blocks are replaced; other text is preserved. The patch adds a concept-DOI badge, exact-version citation and availability sentence. Review sentence placement/inclusion rather than silently rewriting student prose. Zotero-managed bibliography and symlink targets are refused. Applying the same generated patch once then regenerating produces no diff. No tags move and the archived source stays fixed; writeback is a later reviewed commit/PR owned by normal integration.

No authenticated sandbox or production requests have been executed for this implementation. Tests cover local/fake API behavior; live API normalization, credentials, storage connectivity, upload/newversion/publish and DOI propagation still need the authorized sandbox pilot.
