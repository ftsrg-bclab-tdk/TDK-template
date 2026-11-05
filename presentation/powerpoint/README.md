# PowerPoint options

Students can use PowerPoint without building the Markdown presentation.

| File | Use |
| --- | --- |
| [Current design: PPTX](templates/ftsrg-current.pptx) | Open the editable examples and save a copy for your talk. |
| [Current design: POTX](templates/ftsrg-current.potx) | Open in desktop PowerPoint to start a new presentation from the template. |
| [Legacy Montserrat deck](legacy/ftsrg-montserrat-2025.pptx) | Use Martin's older customized FTSRG template, with its original example slides. |

## Start a presentation

1. Open the PPTX or POTX in desktop PowerPoint. The current files **embed all
   eight static font faces, with their complete character sets for editing**:
   Montserrat Light, Medium and SemiBold; regular, bold, italic and bold italic;
   and JetBrains Mono for code. This preserves the BPM title's SemiBold/Light
   contrast without relying on installed fonts or variable-font support.
   If your viewer ignores embedded fonts, install the `.ttf` files in
   [fonts/](fonts/) and restart it. Keep the OFL licenses with redistributed fonts.
2. Save your talk under a new name,
   for example `presentation/my-talk.pptx`, outside `powerpoint/templates/`.
   Those files are maintained starters; template updates can replace them.
3. Choose **Home > New Slide** and select a named layout. Replace the example
   content and remove unused slides. Each example's speaker notes explain how
   to edit it. The chart data are synthetic; the table is an evaluation plan.
4. Choose **View > Slide Master** to change the shared project label, centered
   event/author line, branding
   or typography. Edit your title, author and contact in Normal view. Use
   **Home > Layout** to switch layouts and **Home > Reset** to restore a moved
   placeholder. Avoid pasting text with formatting from another presentation.
5. Before presenting, use **Review > Check Accessibility** and inspect reading
   order, contrast, font substitution and every slide in Slide Show view. Add
   meaningful Alt Text to replacement figures and charts. Rehearse with the
   actual display and check the exported audience PDF.

PowerPoint for the web can edit a PPTX, but use desktop PowerPoint for master
editing and POTX creation. Test fonts on the computer that will present it.
When saving an editable copy, keep **Embed fonts in the file** enabled and
**Embed all characters** selected in PowerPoint's save settings. Reopen the
saved copy to check the result; some viewers ignore embedded fonts.

## Layouts and editable objects

The 16:9 template uses three masters: light-grey content, dark graph cover and
closing, and purple graph section divider. They share one color/font theme.
The fourteen named layouts are cover, divider, title and text, two columns, three
columns, figure and caption, code and explanation, table, chart, title only,
closing, references/backup, a two-line cover title, and a cover with portrait/QR
placeholders. Every example has a real title placeholder.

Text geometry and styles live on layouts, so new slides inherit them and Reset
can restore them. Body lists have three useful levels; keep deeper detail in
backup slides. Content titles use one short line with a separate topic label
above it. Titles and subtitles use native All Caps formatting: you can type
normal-case text without losing the BPM appearance. The default cover has a
one-line title and a two-line subtitle. Choose **13 Cover with two-line title**
for a longer research title; it keeps the BPM font sizes and reserves room
for both lines. Cover subtitles and divider titles have two lines. Shorten crowded
content instead of reducing the type. Content slides have automatic slide-number fields; cover,
divider and closing slides omit them.

- **Figures:** use the picture placeholder or right-click **Change Picture**.
  Use **Crop > Fit** when the complete image must remain visible. The example
  image has descriptive Alt Text. The title-only slide demonstrates the same
  kind of workflow with editable boxes and attached connectors.
- **Tables:** the example is a native table with a marked header row and no
  merged cells. Use **Table Layout** to edit it. Duplicate the example to retain
  its burgundy header and white cells. A newly inserted table may initially use
  PowerPoint's default table style.
- **Charts:** use **Edit Data** on the native example chart. Its workbook is
  embedded, so it needs no external Excel file. Replace values, categories,
  axis units, Alt Text and the source caption. Add uncertainty when justified
  by your measurements. A new chart uses the theme palette; duplicate the
  example to retain its formatting.
- **Code:** edit the text directly in JetBrains Mono. Keep long listings in
  an appendix or repository. The example is pseudocode, not a verified result.

The default cover aligns the presenter details to the right margin without
reserving empty image slots. Choose **14 Cover with portrait and QR** to use
the BPM cover's portrait and contact QR arrangement. The closing includes a
project QR placeholder. Empty placeholders do not appear in Slide Show; select the picture icon in Normal view to fill them.
For a portrait, use **Picture Format > Crop > Crop to Shape > Oval**. Use a QR
image only after checking its destination and testing it on a phone. The
template supplies no portrait or working QR code for someone else's identity.

The PNG/JPEG artwork and the example figure remain images. Slide text, tables,
chart data and the native diagram remain editable. The PowerPoint files do not
automatically synchronize with `slides.md` or `metadata.json`.

## BPM design reference

The visual reference is Martin's BPM 2026 talk at revision `6f1b07b`, including
both `theme/bme.css` and the closing styles inside `slides.md`. The cover follows
page 1; the header, topic labels and content titles follow the main talk pages;
the closing follows page 27; and the compact table and backup tag follow the
backup pages. The artwork and logos are the same source files.

| Element | BPM size on the 1280 × 720 canvas | PowerPoint size |
| --- | --- | --- |
| Cover title / subtitle | 38 / 32 px | 28.5 / 24 pt |
| Content title | 30 px | 22.5 pt |
| Body / card text | 23 / 20.7 px | 17.25 / 15.525 pt |
| Header / topic label | 13 / 12.5 px | 9.75 / 9.375 pt |
| Code | 18.5 px | 13.875 pt |
| Closing statement | 30 px | 22.5 pt |

The layouts retain BPM's font weights, tracking, header rule at 27 px, 64 px
side margins, column gaps and compact labels. The cover has separate author
and event lines plus a presenter block at the bottom right. The closing has
four translucent panels and a contact block in the same position as the talk.
Text positions were checked against the rendered BPM slides.

The examples use student prompts instead of the talk's research claims and
personal details. The optional purple divider comes from the shared BPM/AVM
CSS; the final BPM talk does not use it. The native chart is an additional
layout using the same typography and colors.

## Legacy option

`legacy/ftsrg-montserrat-2025.pptx` is an unchanged copy of Martin's confirmed
`FTSRG Monteserrat template.pptx`, last saved on 9 December 2025. It includes
31 slides from his BPM 2025 presentation and template examples, along with
original notes, metadata, contact details and embedded objects. Save a copy
and replace that material before presenting your own work.

The September 2025 Teams copies have identical themes, masters and layouts,
but different slide content. This older design is an alternative to the current
CSS-derived design. It is Martin's customization, not the untouched upstream
FTSRG template. See [provenance and rights](../PROVENANCE.md).

## Maintainer build and checks

Students do not need Python, Node.js or LibreOffice to use the checked-in files.
The PPTX/POTX files are intentional distributable templates. Rendered previews
and review files belong in ignored `presentation/dist/`.

From the repository root, Python 3.10 or later builds the new template with no
third-party Python packages:

```sh
python3 presentation/powerpoint/tools/build.py
python3 presentation/powerpoint/tools/check.py
```

The builder writes to `presentation/dist/powerpoint/`. It does not overwrite
student decks or the legacy file. After reviewing a change, copy the two files
into `powerpoint/templates/`, update `SHA256SUMS`, and run the check again.
CI verifies hashes, internal relationships, native object structure, placeholder
inheritance, chart/workbook consistency, and reproducibility from the builder.
It also checks font relationships, family/style mappings, embedding flags and
the complete embedded font bytes against the licensed static sources.
It is not a complete Office Open XML schema or accessibility validator.
Ten regression tests exercise lost title semantics and capitalization,
overlapping cover title/subtitle boxes, an invisible table type, inherited
hanging indents in plain text, stale chart values, an external workbook link,
disabled embedding, missing font styles and corrupt embedded font data.

All fourteen examples were rendered and inspected with LibreOffice. A separate
test restricted Fontconfig to Liberation fonts and used fresh LibreOffice
profiles: the previous unembedded file substituted Liberation Sans; the current
file used its embedded Montserrat weights and JetBrains Mono, confirmed in the
exported PDF. The cover was also compared with the BPM reference using the same
title text. Structural and geometry checks passed. **Microsoft
PowerPoint was not available for a native application check.** Before a release,
also open both formats in desktop PowerPoint: test New Slide, Reset, Change
Picture, Edit Data, editing the shared master, and saving/reopening a copy.
Confirm that no repair prompt appears and run the Accessibility Checker.

A LibreOffice POTX-to-PPTX round trip retained the original twelve slides and notes,
native table and chart, but dropped the separate embedded Excel workbook.
Use the supplied originals for PowerPoint editing; do not distribute a
LibreOffice-resaved copy without checking chart editing again.

For optional visual review with LibreOffice and Poppler:

```sh
mkdir -p presentation/dist/powerpoint/render
libreoffice --headless --convert-to pdf \
  --outdir presentation/dist/powerpoint/render \
  presentation/dist/powerpoint/ftsrg-current.pptx
pdftoppm -scale-to 1600 -png \
  presentation/dist/powerpoint/render/ftsrg-current.pdf \
  presentation/dist/powerpoint/render/slide
```

`assets/workflow.png` is a raster fallback of the existing
`presentation/figures/workflow.svg`, produced with
`rsvg-convert -w 1920 -o presentation/powerpoint/assets/workflow.png presentation/figures/workflow.svg`.
To regenerate the static fonts from the existing variable fonts, use
`uv run --with fonttools==4.67.0 python presentation/powerpoint/tools/prepare_fonts.py`.
FontTools is only needed for that maintainer operation. Keep both OFL notices.
The builder stores full, uncompressed EOT font parts following
[Microsoft's PowerPoint font-part specification](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oe376/1663dabc-5d98-463f-889e-bcd9b77c3d34)
and the [EOT format](https://www.w3.org/submissions/EOT/).

The implementation follows Microsoft's guidance on
[masters and reusable POTX templates](https://support.microsoft.com/en-us/powerpoint/create-and-save-a-powerpoint-template),
[layout placeholders](https://support.microsoft.com/en-us/powerpoint/add-edit-or-remove-a-placeholder-on-a-slide-layout),
and [accessible presentations](https://support.microsoft.com/en-us/accessibility/powerpoint/make-your-powerpoint-presentations-accessible-to-people-with-disabilities).
