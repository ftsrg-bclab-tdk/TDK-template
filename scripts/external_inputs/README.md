# Accepted external inputs

Standalone implementation preparation for the monorepo. No workflow or package
has been published or enabled. Standard-library Python 3.11+ and authenticated
`gh` are sufficient. Fetches use the consuming project's own GitHub release;
the authorized onboarding/maintenance actor supplies its verified copy.

## Contract

`receipt.schema.json` describes `external-inputs/v1`: accepted archive identity,
source-manifest digest, exact inventory and source/acceptance evidence. It is a byte-identical preparation copy of the canonical `scripts/release/external-inputs.schema.json` owned by the release component; use that canonical schema after integration. Field names are `schema`, `package_sha256`, files `path/sha256/size`, package-level `provenance`, `acceptance`, `license`, `redistribution`, `access`. Store the
receipt in source and pass its SHA256 from the consumer's reviewed configuration.
The digest covers exact UTF-8 file bytes, not reserialized JSON. Acceptance means
an authorized review selected these inputs; this tool does not grant approval or
infer source freshness, license rights, applicability or authentic PDF contents.
The package-producing ingestion step must perform those checks before acceptance.

`delivery.schema.json` describes `external-inputs-delivery/v1`: a consuming
repository's numeric identity, immutable release/tag and numeric archive asset
ID, bound to the receipt and archive digests. Canonical and project deliveries
use different locators but identical archive/receipt bytes. The delivery contains
no credentials. The CLI checks the supplied source-manifest bytes against `manifest_sha256`; validating their semantics and the approval evidence remains with acceptance tooling. A matching receipt hash establishes identity, not authority to approve.

JSON Schema validates structure. `validate_receipt` adds path/case/file-directory
collision, duplicate-key, provenance and total-size checks. The
runtime validator needs no third-party schema package. All hashes are lowercase
SHA256 without a prefix; the GitHub API's `sha256:` prefix is handled separately.

Archives are ZIPs containing exactly the inventoried regular
files. No directory entries, symlinks, encrypted entries,
extra members or duplicate paths. Limits are 2 MiB receipt/delivery JSON, 512 MiB
archive, 512 MiB expanded content, and 2,048 members. These are this initial
reference/asset interface's resource bounds, not a general dataset format.

## Commands

Verify a local accepted package without materializing it:

```sh
python3 scripts/external_inputs/external_inputs.py verify \
  --receipt RECEIPT.json --receipt-sha256 EXPECTED_RECEIPT_SHA256 \
  --manifest SOURCE_MANIFEST.json \
  --archive PACKAGE.zip
```

Use `materialize` instead of `verify` and add `--output NEW_DIRECTORY` to extract
it. Output must not exist; existing tracked files or student directories are
never replaced. Consumers choose an ignored staging directory and explicitly
adapt their own asset paths. The presentation component owns that adaptation.

Fetch and verify an immutable release asset, then materialize it:

```sh
python3 scripts/external_inputs/external_inputs.py fetch \
  --receipt RECEIPT.json --receipt-sha256 EXPECTED_RECEIPT_SHA256 \
  --manifest SOURCE_MANIFEST.json \
  --delivery DELIVERY.json --cache CACHE_DIRECTORY --output NEW_DIRECTORY
```

The CLI emits one JSON result and exits 0 for verified bytes, 2 for failure.
Successful outcomes are `verified_local`, `downloaded_accepted` or
`reused_accepted`; upstream `source_freshness` is always `not_checked`. Fetch
records the delivery and timestamp. When GitHub retrieval is unavailable, a
verified cached copy of exactly the accepted archive can be reused, with a
`retrieval_problem` recorded. No available verified copy means an explicit error.
Corruption or identity/immutability mismatches never become successful fallbacks.
A successful verification does not prove all project checks ran.

The fetcher checks repository ID (not name alone), published immutable release,
tag, numeric asset ID, size, available API digest, archive digest and every member
hash. `gh` owns credential handling; no token appears in arguments, manifests or
result JSON. HTTP credentials are neither copied into project files nor obtained
from the private canonical repository. Downloads are bounded and timed out.

The content-addressed local cache is only an outage aid. Approved release assets
must outlive routine Actions artifacts; package publication/replication, durable
retention/reference tracking and recovery registration are not implemented here.
GitHub authentication and a real immutable-release fixture still need the agreed
pilot. Tests use synthetic packages and a fake transport, without provisioning.

## Validation

```sh
python3 -m unittest discover -s scripts/external_inputs -v
```

Fixtures cover valid extraction, tampering, traversal/collisions, extra members,
symlinks, receipt/locator mismatches, mutable releases, replaced
repositories, missing/corrupt cache, outage reuse and CLI evidence. The release owner has implemented offline verified-reference packaging. The fetch cache uses its expected `<package_sha256>.zip` and `<receipt_sha256>.json` names, preserving raw accepted receipt bytes. Fetch may omit `--output` for packaging-only use. Its surrounding trusted CI/run identity and release transport remain separate integration work.

## Presentation consumer contract

The presentation owner will use presentation-relative ZIP members:
`assets/fonts/*.ttf`, `assets/logos/*.png`, and
`assets/{cover-graph,divider-graph}.jpg`, limited to the nine inventoried runtime
binaries. The acceptance receipt lists exact members, never wildcard selections.
Materialize into a fresh ignored per-run staging root. Component build code then
composes `dist/assets` from these verified binaries plus tracked font notices,
preserving the slides/CSS `assets/...` URLs and self-contained rendering outputs.
The fetcher does not overwrite source or perform that composition.

Carry the accepted receipt, delivery identity and fetch result into run evidence;
`source_freshness` remains `not_checked`. After migration, a missing required
package must not silently use old tracked copies. A verified accepted cache may
satisfy retrieval outages with the explicit `reused_accepted` result.

Migration still requires a real accepted receipt, source manifest and delivery
locator, the agreed integration snapshot, and fresh-clone fetch/render/check
acceptance. The presentation owner retains all nine tracked binaries and #28
until those gates pass. Its consumer tests cover missing/corrupt required inputs
and verified-cache outage handling using this transport rather than reimplementing
storage. This mapping is an agreed integration contract, not a claim that a live
package or end-to-end presentation run exists.
