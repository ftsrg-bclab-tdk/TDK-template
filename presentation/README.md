# FTSRG presentation starter

An independently buildable Marp deck based on Martin Farkas's BPM 2026 presentation.
It retains the graph artwork, BME/FTSRG logos, Montserrat headings, grey content
slides, and dark title and closing slides. See [provenance and licenses](PROVENANCE.md).

## Build

Use Node.js 22 or later, npm, and a local Chrome or Chromium installation.
`npm run check` also needs Poppler's `pdfinfo`, `pdftotext`, and `pdffonts` commands
(`poppler-utils` on Ubuntu/WSL, `poppler` on Arch or Homebrew).

From this directory:

```sh
npm ci --ignore-scripts
npm run build
npm run check
```

From the repository root, use `npm --prefix presentation ci --ignore-scripts`,
`npm --prefix presentation run build`, and `npm --prefix presentation run check`.
The entire directory can also be copied elsewhere and built there. It has no
paper, TeX, Python, or sibling-repository dependency.

The scripts find Chrome/Chromium on `PATH` or in the usual macOS application
locations. Override discovery with `CHROME_PATH=/absolute/path/to/chrome`.
Linux/WSL is the validated native environment; macOS discovery is provided but
has not been tested here. Run Chromium as a regular user with its sandbox enabled.
Dependency installation needs network access; the installed build uses local
fonts and artwork.

Outputs are ignored under `dist/`:

| File | Use |
| --- | --- |
| `slides.html` | Browser slide deck, including presenter notes |
| `slides.pdf` | Audience PDF without note annotations |
| `slides-notes.pdf` | Presenter PDF with note annotations |
| `slides.md` | Generated metadata and slide source for inspection |
| `assets/`, `figures/` | Local resources needed by the HTML deck |

Keep the HTML beside its `assets/` and `figures/` directories when sharing it.
Use the audience PDF when you do not intend to share presenter notes.
`npm run render` also generates `dist/slide.001.png`, etc., for visual review.
Builds overwrite generated files; edit source files instead.

## Make it your talk

1. Edit `metadata.json`: title, subtitle, short header, author(s), affiliation,
   event, date, and project URL. These fields populate the cover, closing slide,
   document metadata, and header. Use a short header to fit beside the logos.
2. Edit `slides.md`. Its `{{field}}` placeholders use the metadata fields;
   unknown fields fail the build. Values are escaped as text. Keep any richer
   formatting in the slide source itself.
3. Replace the fictional queue example with your research question, method,
   evidence, limitations, and supported conclusion. The evaluation slide is a
   plan, not fabricated results. Cite verified sources and mark illustrative data.
4. Add your diagrams under `figures/` and refer to them with relative paths.
   Replace the optional backup material with evidence useful during questions.
5. Build, run the checks, and inspect every page. Long titles, tables, and URLs
   may need shorter wording or another slide. The checks catch missing assets,
   unavailable fonts, external resource requests, and content past slide edges;
   they cannot judge readability, overlap within a slide, or scientific claims.

The example shows `title`, `red` (divider), and `closing` slide classes, plus
`cols`, `cols-3`, and `card` helpers from the original CSS. Use Marp local
comments such as `<!-- _class: title -->` to style one slide. Use `---` on its
own line to separate slides. `theme/bme.css` remains the shared visual design.

## Notes and delivery

HTML comments in `slides.md` hold presenter notes. The examples use `@MM:SS` for
a running clock, `>>` for where to point, `ASK` for audience questions, and `->`
for transitions. Timing is illustrative; rehearse for your actual slot.

Open `dist/slides-notes.pdf` in Pympress for rehearsal. Confirm note annotations
appear in your installed version and test the audience display before the talk.
The template does not rely on animation: use successive slides for progressive
reveals. Live Pympress and dual-display behavior have not been validated by CI.

The presentation is outside the paper-only Overleaf sync. Edit it in Git and
build it locally or use the presentation CI artifact. No root paper command or
Overleaf entrypoint is required.

Known dependency advisories and their build/CI conditions are recorded in
[the dependency triage](DEPENDENCIES.md).

See [Marp CLI](https://github.com/marp-team/marp-cli) for rendering options.
The build enables local files and inline HTML for the supplied theme and slides;
only build slide sources you trust.
