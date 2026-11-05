# Source provenance and rights

## PowerPoint alternatives

On 5 November 2026, Martin requested that his confirmed older customized template
be added unchanged as a student alternative and that the current design receive
an editable PowerPoint version.

- `powerpoint/legacy/ftsrg-montserrat-2025.pptx` is the unchanged university
  OneDrive `_Templates/FTSRG Monteserrat template.pptx` file. SHA-256:
  `4b162aaa6eb526f9617181ab1800499c6acf8cabe907a47c1a876218e3750cd9`.
  Its embedded last editor is Farkas Martin and modification date is
  2025-12-09T19:48:32Z. It contains 31 slides, including BPM 2025 talk content.
  The September 2025 Teams copies have byte-identical theme/master/layout parts.
  Martin confirmed that this is the Montserrat customization he meant. It keeps
  its original contents, credits and inherited rights; this repository does not
  relicense the entire legacy presentation as new material.
- `powerpoint/templates/ftsrg-current.pptx` and `.potx` are newly authored native
  Office Open XML versions of the current `theme/bme.css` design. They reuse the
  existing graph artwork and logos unchanged. The fourteen layouts follow the
  BPM 2026 talk at `6f1b07b`, including its inline closing styles, font weights,
  tracking, compact header, cover author block and closing panels. Cover variants
  accommodate a two-line research title or the original portrait/QR arrangement.
  All three covers add a separate editable Advisor(s) line for student talks.
  They include native table/chart examples and a connected native workflow diagram.
  They are a PowerPoint adaptation, not a synchronized export
  of `slides.md`. The examples are instructional; the chart data are synthetic.
- `powerpoint/assets/workflow.png` is a raster copy of `figures/workflow.svg` for
  the picture-placeholder example. The separate native diagram stays editable.
- `powerpoint/assets/qr-project.png` was generated with `qrencode` for
  `https://github.com/ftsrg-bclab-tdk/TDK-template`, which Martin selected as the
  replaceable project example. The covers and closing use this code beside the
  editable URL. It does not reuse the BPM talk's personal or artifact QR links.
- `powerpoint/fonts/` contains static instances of the already supplied Montserrat
  and JetBrains Mono variable fonts, produced with FontTools 4.67.0. Montserrat
  Light, Medium and SemiBold are exposed as separate Office font families to
  preserve the BPM weight hierarchy. Their OFL notices are retained. Both new
  PowerPoint files embed all eight complete static font faces as uncompressed
  EOT font parts, preserving the original TTF bytes and embedding permissions.
  The separate font files remain available for viewers that ignore embedding.

The scoped license policy below applies to original reusable tooling and prose.
Existing artwork and fonts keep the permissions and licenses recorded here.
`powerpoint/SHA256SUMS` identifies the distributed files and derived assets.

## Markdown starter

This starter was extracted on 3 November 2026 for Martin Farkas's TDK template.
It follows his existing BPM/FTSRG presentation rather than introducing a new style.

## Design sources

- Primary source: Martin Farkas's `bpm26-talk` checkout, commit
  `6f1b07b797a994c26ec1e64018fbc8ccf9e9af0e`. Its README identifies the deck as
  *Trust No Pool*, BPM 2026, and records the theme/assets as copied from the
  AVM'26 deck and promotional package. The source checkout is
  `~/Projects/bpm26-talk`; it has no public remote. The theme's last source change
  is `a508cdf26c203da423df967944e35df3860ca554`.
- Ancestor: [Martin Farkas's AVM tutorial](https://github.com/BlackLight54/avn-tamarin-tutorial),
  commit `977b42f237ab6434be0bc5dc11a6196951e48a0e`, `slides/`.
  Its MIT notice is retained verbatim in [LICENSES/AVM-MIT.txt](LICENSES/AVM-MIT.txt).
  The BPM checkout lacks the divider image referenced by its CSS, so
  `assets/divider-graph.jpg` comes from this ancestor. The cover image in both
  checkouts is byte-identical. This ancestor repository is private: its URL
  records provenance, not an anonymous download endpoint for student builds.
  Accepted canonical/project asset packages must supply the required bytes
  without exposing upstream credentials.
- The CSS source credits the *BME Arculati Kézikönyv 2025*, pp. 37–38, for its
  layout, palette and typography. That attribution remains in `theme/bme.css`.
  This records the source's credit, not an independent certification of compliance
  with the current institutional brand manual.

`theme/bme.css` is the BPM theme with small starter fixes appended for closing
links and long header labels. The fonts, graph backgrounds, and selected logos
are copied without modification. `assets.sha256` records their content hashes.
The build scripts, metadata, fictional queue example and workflow diagram were
written for this starter. The BPM talk's research results, coauthor list,
portrait, contact information, QR codes, private planning documents and rehearsal
notes are not included.

## Fonts

- Montserrat regular and italic are copied from the BPM assets together with
  [OFL-Montserrat.txt](assets/fonts/OFL-Montserrat.txt), copyright 2024 The
  Montserrat.Git Project Authors, SIL Open Font License 1.1.
- JetBrains Mono is copied from the BPM assets. Its missing companion notice was
  retrieved from the [upstream OFL](https://github.com/JetBrains/JetBrainsMono/blob/master/OFL.txt)
  on 3 November 2026 and is included as
  [OFL-JetBrainsMono.txt](assets/fonts/OFL-JetBrainsMono.txt), copyright 2020 The
  JetBrains Mono Project Authors, SIL Open Font License 1.1.

Trailing whitespace in the font notices was normalized; their wording is unchanged.
Keep these notices with the fonts when redistributing the presentation source.
Dependency licenses are recorded in `package-lock.json` and installed packages.

## Institutional artwork and distribution

The logos identify BME and FTSRG. The source describes the graph artwork as coming
from the group's template. On 4 November 2026, Martin confirmed in the monorepo
coordinator session that he has redistribution permission for the supplied
artwork. Retain these assets in the public starter and its accepted asset package:

- `assets/cover-graph.jpg` and `assets/divider-graph.jpg`;
- `assets/logos/bme-seal-watermark.png`;
- `assets/logos/bme-vik-mit-ftsrg-white.png`;
- `assets/logos/bme-wordmark-grey.png` and `assets/logos/ftsrg-grey.png`.

This permission record comes from the maintainer's confirmation, not an inferred
grant from the ancestor's MIT notice. Neither inspected deck supplies a separate
artwork license or original artist credit. Preserve the source attribution and
existing notices; do not label the institutional artwork as newly MIT- or
CC-licensed. The original reusable additions follow the scoped policy below;
that policy does not replace the artwork permission or inherited terms.


## Scoped license policy

Martin accepted the reusable-source licensing policy in the monorepo coordinator
session, recorded in `docs/monorepo-plan.md` at commit `25e50bc`:

- Original reusable code and tooling are MIT-licensed.
- Original guide and slide prose are licensed under CC BY 4.0, with attribution
  preserved.
- Inherited material keeps its existing terms, including the AVM MIT notice and
  the font OFL notices above.
- The supplied institutional artwork is retained under Martin's confirmed
  redistribution permission, not relabeled MIT or CC BY.

The monorepo root owns the general license texts and scope boundaries. This
component records provenance and exceptions rather than adding duplicate general
license files. The BPM source's lack of a blanket license is historical context,
not an unresolved decision about the original reusable additions.

Permission and license selection do not establish that asset-package ingestion,
verified delivery, or the public-disclosure acceptance checks have completed.
Keep the existing binaries until accepted-package retrieval and an assembled
fresh-checkout fetch/render/check pass. Latest normal runtime and dependency
resolution are coordinated with CI separately from the identity of accepted
artwork bytes.
