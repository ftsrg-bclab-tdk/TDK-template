# Repository README status blocks

`badges.py` updates only the text between `<!-- tdk-status:start -->` and
`<!-- tdk-status:end -->`. Student prose and YAML frontmatter outside the block
are preserved. No builds, workflow dispatches or publication actions run here.

Run with Python 3.10 or newer and an authenticated GitHub CLI after the CI
workflows are integrated. Pass the actual created repository, not the template:

```sh
python3 scripts/readme/badges.py --repo OWNER/PROJECT --root . \
  --readme README.md --readme paper/README.md
```

This prints the proposed status block. Add `--write` to replace the blocks.
The tool obtains the canonical repository name, numeric ID, default branch and
visibility through `gh api`; it does not infer them from stale template metadata.
All target files and markers are checked before any write. The integration must
pass the checkout for that repository as `--root`.

The required local workflow filenames and names are the CI owner's interface:

| File | Name | Badge event filter |
| --- | --- | --- |
| `ci.yml` | Project checks | `push` |
| `paper-build.yml` | Paper build | `workflow_run` |
| `paper-lint.yml` | Paper lint report | `workflow_run` |

Generation fails if one is absent or has a different name. Both image and click
target are filtered to the repository's default branch and corresponding event.
Paper consumers inspect the exact producer evidence; they do not compile again.
The generator validates their file/name interface, not their runtime behavior.
The CI owner verifies run-attempt selection, current-head checks, reruns and
out-of-order completion. A no-status badge before the first eligible run is not
a successful check. Private-project results retain authenticated GitHub links.

## Published DOI evidence

Without publication evidence the block says no verified published DOI was supplied.
After publication, pass the release owner's `publication-receipt/v1` JSON and
its independently trusted SHA-256 digest:

```sh
python3 scripts/readme/badges.py --repo OWNER/PROJECT \
  --readme README.md --readme paper/README.md \
  --publication-receipt /path/to/verified-publication.json \
  --publication-sha256 TRUSTED_RECEIPT_SHA256 --write
```

The trusted digest must come from the reviewed publication evidence or trusted
controller/release record. Computing it from arbitrary local JSON establishes
no publication authority. The generator does not authenticate the publisher or
reverify Zenodo remotely. A digest mismatch or repository-ID mismatch fails.
Only production records individually marked `published` with verified version
DOIs are rendered. An overall partial publication can contain published records;
draft/reserved DOIs and sandbox records never become badges. Labels use logical
manifest record IDs, not inferred folder names. Default grouping is combined
code/proof/benchmark; explicitly configured independent records remain separate.
This consumer does not define a second publication receipt schema.

## Integration

Run generation after project creation and after verified publication metadata
changes. Preview and review the block before committing it. The shipped README
markers intentionally contain pending text until real workflow files exist and
repository metadata is available; there are no copied template-status images in
a newly generated project. Rerunning with the same inputs is idempotent.

License terms come from the repository's [LICENSE](../../LICENSE); do not infer
permissions for institutional artwork, fonts or inherited files from the tooling
license. No legacy mirror badges are generated.

```sh
python3 -m unittest discover -s scripts/readme -p 'test_*.py'
```

The compatibility test consumes the release owner's canonical
`scripts/release/fixtures/publication-receipt.synthetic.json` without duplicating
it. In an isolated component checkout, set `TDK_PUBLICATION_TEST_FIXTURE` to that
file in the release checkout. If the component is not integrated and no override
is supplied, that test reports a skip. An explicit missing override fails.
The fixture and its test-computed digest are synthetic test inputs, never actual
publication evidence or a source for README DOI badges.
