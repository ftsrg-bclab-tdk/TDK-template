# Source provenance and rights

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
  checkouts is byte-identical.
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
from the group's template. Neither inspected deck supplies a separate license
or original artist credit for that institutional artwork. The BPM checkout also
has no blanket license. The ancestor's MIT notice is preserved for inherited
material; it does not establish trademark permission or independently establish
rights in third-party artwork.

This extraction implements the owner's requested institutional template reuse.
It does not assign a new blanket license to the directory. Before publishing a
standalone public template or selecting a license for an archive, the maintainer
must settle the institutional artwork's redistribution terms and the license for
the BPM-derived additions. This decision belongs with the monorepo publication
policy; it is not silently answered by the ancestor's MIT notice.
