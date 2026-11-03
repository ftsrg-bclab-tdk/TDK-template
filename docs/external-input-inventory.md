# External input inventory

Read-only inventory on 2026-11-03. Paper evidence is from `9564ef15`; presentation evidence is from PR #28 at `07bb8bddbe750162a84b64193fbeef0442fc8ef6`. No tracked inputs have been removed. The user requires downloaded external files to be stored as artifacts. This inventory identifies consumers that must be adapted before those files leave source control.

## Faculty reference documents

Three files under the current paper's `docs/` total approximately 658 KB:

| File | Consumer | Required adaptation |
| --- | --- | --- |
| `TDK2025_biralati_pontozolap_hallgatoi.pdf` | Hard-required by `scripts/lint/rules-source.lua:52`; read by `scripts/skim/skim.py:446`; named by reviewer/self-score skills | Fetch and verify before review tooling. Update the literal file requirement and all links. The draft's Overleaf Checks page also invokes this lint rule, so a CI-only download is insufficient without an explicit change to that check's contract. |
| `VIK_Generativ_MI_Hallgatoi_Nyilatkozat.docx` | Referenced by `content/09-ai-declaration.tex:5`; declaration text itself is TeX | Replace bundled-copy references with the accepted package location and official source. |
| `VIK_Generativ_MI_Pelda_Nyilatkozat_Szakdolgozathoz.pdf` | Referenced by the same declaration source | Update documentation links; it is not embedded in either paper PDF. |

The declaration landing page recorded in source is `https://vik.bme.hu/page/1346/`. The example's recorded download is `https://vik.bme.hu/document/7193/original/Generativ_MI_P%C3%A9lda_Nyilatkozat_Szakdolgozathoz.pdf`. This inventory did not verify those remote endpoints. The review sheet has no recorded download URL in its current files or initial import commit `cb9ec69`. Discover and verify source URLs before implementing the fetcher. A newer sheet must not silently replace the applicable reviewed rubric merely because it is newer.

Skim currently degrades to criteria without scoring bands when the review sheet is absent. Required-package validation must detect this before a report claims the full review was performed. Overleaf's source-only Checks page must accurately distinguish checks it can execute from artifact-dependent checks performed elsewhere.

## Paper rendering assets

| Files | Consumer |
| --- | --- |
| `figures/bme_logo.pdf` | All title-page variants, including active `include/titlepage-tdk.tex:4`. Required by draft and reviewer builds. |
| `guide/figures/collage/{bpm2025,bpm2026,eurocybersec2024,tdk2023}.pdf` | Embedded by `guide/04-writing.tex:158–175`. Required by the draft's guide. |
| `guide/figures/{google-calendar-add-by-url,neptun-calendar-export}.png` | Embedded by `guide/01-getting-started.tex:39,44`. Required by the draft's guide. |

The collage examples have paper citations, but no exact download/extraction recipe. The screenshots have no recorded upstream download provenance. These files cannot all be classified as unchanged downloads.

Native Overleaf import has no Actions-artifact materialization hook in this repository. Removing these assets before establishing their delivery breaks compilation. The user accepted retaining small embedded paper assets in Git for native Overleaf, while downloading external reference attachments and presentation assets into verified artifact packages. This is the accepted rendering-asset exception.

`tdkieee.bst` is a locally modified IEEEtranN bibliography style used by the paper and guide. It is maintained source, not an unchanged external binary to replace with an upstream download. Paper fonts are supplied by TeX Live; no paper font binaries are tracked.

## Presentation assets

Nine runtime binaries total approximately 4.05 MB:

- `assets/fonts/{JetBrainsMono,Montserrat,Montserrat-Italic}.ttf`
- `assets/logos/{bme-seal-watermark,bme-vik-mit-ftsrg-white,bme-wordmark-grey,ftsrg-grey}.png`
- `assets/{cover-graph,divider-graph}.jpg`

CSS, `slides.md`, and `scripts/build.mjs` consume these files. Build checks require local assets and verify embedded fonts. Fetching and verifying them before the build can preserve an offline rendering step and self-contained output artifacts. Overleaf does not run the presentation build.

All nine files match local Git object bytes under `slides/assets/` in `BlackLight54/avn-tamarin-tutorial` at `977b42f237ab6434be0bc5dc11a6196951e48a0e`. The match was checked against `presentation/assets.sha256`. This establishes an exact source revision for the existing bytes; remote accessibility was not tested. It does not establish redistribution rights or impose a permanent toolchain pin. Keep OFL notices and asset provenance tracked; the notices were adapted and are not byte-identical ancestor files.

## Other tracked material

`work/template-review/` contains 134 tracked review/build records, screenshots, and generated skim assets. These are generated evidence, not external downloads. Preserve relevant evidence in an appropriate artifact archive before any source cleanup; do not sweep it into a public reusable template.

Inspected code and notes template snapshots contained no reference binaries or vendor bundles. Those snapshots were code `c1c63f4`, code-lessons `7afa71b`, and notes `ebaa9ea`. Existing unrelated notes edits were left untouched.

## Shared implementation contract

Keep a source manifest and an accepted-package receipt with file paths, source/version, retrieval time, hashes, applicability and acceptance evidence, and an immutable storage identity. Validate downloaded content before acceptance, including MIME/content checks. A redirect or HTTP success alone is insufficient.

Required accepted packages must remain retrievable while supported projects or releases reference them. Routine Actions retention of 14 or 7 days does not meet this requirement. Source outages may reuse verified accepted bytes while freshness remains explicitly failed or unknown. Missing or corrupt required bytes fail the dependent check. Ordinary integrity checks should consume the accepted package without refetching publisher websites on every run.

Artifact storage, credentials, and Overleaf delivery are not selected by this inventory. Release selection must identify external inputs as verified references, separately from tracked source or newly built outputs. Before removing files, test a fresh checkout, the relevant local/CI consumers, and native Overleaf compilation where applicable.

## Storage proposal following CI feasibility research

The CI owner proposes GitHub Release assets in the existing canonical repository, copied byte-for-byte to releases in each consuming project by authorized onboarding or maintenance. Each project's CI reads its own release assets; local bootstrap uses existing project read access. This avoids placing canonical-maintainer credentials in student workflows or granting students access to the private maintainer source. No package has been uploaded and no setting has changed.

Accepted package bytes and receipts have identical digests across copies. A separate delivery record identifies each repository, release, tag and asset ID. Retain required packages while supported baselines or research releases reference them. If a project copy disappears, restore the verified canonical bytes under a new delivery identity. Copies within GitHub are not independent provider backups.

Use an `external-inputs/` support-release namespace, mark these releases not-latest, and explicitly exclude them from research-publication/Zenodo triggers. Downloading support files must not create a DOI or select a research publication policy.

The CI owner reports a successful read-only query of the canonical repository's immutable-release setting, currently disabled. The user explicitly accepted enabling this policy for participating repositories, including its effect on all future releases. GitHub documents that published immutable release assets and associated tags cannot be changed; titles and notes can still change. Whole-release deletion remains possible. Prepare a draft, attach and verify all files, then publish. Corrections to published files require a new version. The setting has not yet been changed. See [immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases) and [about releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

The user's Docker reminder also requires Dockerfiles/container build configuration in the integrated source and selected reproduction material. Release receipts must identify actual container images by digest and platform. Repository release immutability does not freeze a separate registry's mutable tags.

An actual package upload, project-copy, authenticated retrieval and recovery pilot remains required. This proposal does not resolve delivery of paper rendering assets into Overleaf or authorize their removal.
