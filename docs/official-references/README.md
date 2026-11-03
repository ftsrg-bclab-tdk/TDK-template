# Official reference sources

`sources.json` records the sources checked on 2026-11-04 for BME VIK TDK 2026
and the 38th OTDK in 2027. It is a source inventory, not an accepted package or
a declaration that the faculty requirements are complete.

Eleven official PDFs were retrieved and their signatures and extracted titles
checked: the central call and six annexes, the Informatics call and its annex,
the OTDT ethics code, and the MTA ethics edition linked by the Informatics call.
Their hashes identify the retrieved bytes. The official landing pages establish
which cycle or edition they belong to. Those are separate checks.

The five required faculty records remain unresolved. Direct retrieval of the
2026 portal returns a Blazor application shell, despite HTTP 200. The older VIK
download page links 2011 scoring forms, and its two review-criteria PDFs returned
403 during this check. Neither that page nor the existing 2025 rubric establishes
2026 applicability. A working faculty portal or faculty-issued current documents
are still needed. Do not replace these gaps with diploma requirements, another
faculty's call, or a hash match against last year's file.

## Manifest interface

The exact format is `official-references/v1`:

- `context`: faculty name, faculty year, OTDK number and OTDK year. A new cycle
  requires a reviewed manifest change, even if some source bytes remain unchanged.
- `reviewed_at`: timezone-aware ISO timestamp for this inventory review.
- `sources`: records with unique `id`, descriptive `title`, `publisher`,
  `category` (`faculty`, `otdk`, or `ethics`), and boolean `required`.
- `url`: direct source URL, or null when the actual current document is unknown.
  `discovery_urls` contains the official pages to inspect for replacements.
- `package_path`: proposed relative member name, or null for unresolved/historical
  documents not selected for the current package.
- `retrieval`: `status` (`retrieved`, `unavailable`, `unresolved`), `checked_at`,
  `final_url`, `http_status`, `sha256`, `size`, `media_type`, and explanatory `note`.
  Unknown fields have JSON null values. A retrieved record has an actual SHA256,
  byte size and final URL. A 200 response containing an application shell or error
  page does not satisfy a document retrieval.
- `applicability`: `status` (`confirmed`, `needs_review`, `historical`), `scope`,
  `evidence_urls`, and `note`. Confirmed means the identified source belongs to
  the stated scope, not that a student is eligible or that redistribution is licensed.

The fourth and fifth central annexes are included as context, but are not required
for an ordinary university student setup. The other identified OTDK and ethics
documents are required for the stated conference scope. All five missing faculty
documents are required. Historical records never satisfy their replacements.

## Freshness and artifact integration

The CI owner consumes this manifest for the weekly network check. Compare the
retrieved bytes with the recorded digest and inspect discovery-page links for
replacement editions. Report unreachable sources, changed bytes, and applicability
review separately. Do not automatically accept a changed document or infer
currentness from HTTP success or unchanged bytes. Missing required URLs and
`needs_review` applicability remain explicit failures of reference readiness.

The existing external-inputs tools own package verification and materialization.
The accepted `external-inputs/v1` receipt must bind the raw manifest digest,
archive/member identities, provenance, acceptance and redistribution/access terms.
No such acceptance or publication is claimed here. Public download availability
does not assign these documents the template's MIT or CC BY license.

After acceptance, materialize using `scripts/external_inputs/external_inputs.py`
into a new ignored staging directory. Never overwrite tracked source. The separate
delivery receipt identifies the durable release asset; approved packages must
remain available while referenced, beyond routine Actions artifact expiry.
An outage may reuse only verified accepted bytes, with the reuse identity and
failed freshness check visible. A missing or corrupt required package fails.

No downloaded PDF is added by this change. Existing tracked references and their
lint consumers remain intact until replacement applicability, package acceptance,
delivery and consumer integration are verified. The generic fetcher is not
duplicated here.

## Application to the guide

The [Informatics annex](https://otdk.hu/wp-content/uploads/2026/05/38OTDK_Informatikatudomanyi_Szekcio_felhivas_1_sz_melleklet.pdf)
contains the paper/form requirements and required declarations. Check those against
the guide's OTDK submission instructions separately from the faculty TDK stage.
Its AI-use and results declarations must not be conflated with a faculty form.

The [central AI annex](https://otdk.hu/wp-content/uploads/2026/04/38_OTDK-kozponti-felhivas_6.-sz.-melleklet.pdf)
requires disclosure of AI use and identifies information the declaration must
contain. The [OTDT ethics code](https://otdk.hu/otdt/etikai-kodex/) covers student
research conduct and ethics declarations. These sources should inform the AI and
ethics guidance, without silently rewriting the student's declaration.

The [Informatics call](https://otdk.hu/kezdolap/otdk-2027/szekciok-felhivasai/informatikatudomanyi-szekcio-2/)
explicitly links the MTA 2010 code. The manifest preserves that cited edition;
it does not assert that it is the latest MTA code for every purpose. The OTDT PDF's
2025 upload path likewise does not change its 2020 edition.
