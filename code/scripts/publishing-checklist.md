# Publication review checklist

Keep the project repository private. Publication selects reviewed artifacts through the root
[release preparation and publication tools](../../scripts/release/README.md).
The nested workflows in `code/.github/workflows/` are retained history, not active monorepo
automation. Creating `PUBLISHING.md` does not enable a workflow, and `hygiene.py --publish`
is retired.

Save project-specific review notes in `code/PUBLISHING.md` if useful, and exclude them from
the selected archive. This checklist records human review; it is not a publication credential
or an enforced approval boundary.

- [ ] The selected code, proofs and benchmark results reproduce the paper's claims. Each
      result has its source revision, command, parameters, tool versions and output hashes.
- [ ] Latest dependencies were resolved once for the measured run. The receipt retains the
      actual lockfiles and image/platform digests; a mutable tag is not an immutable image.
- [ ] The release manifest selects only intended files. Scratch notes, private integration
      links, credentials and internal review records are excluded.
- [ ] Creators, title, version, related papers, access and licenses have been reviewed.
      Existing third-party notices and redistribution conditions remain intact.
- [ ] The prepared package bytes and provenance match the exact successful checks and
      reviewed manifest. The candidate is stored durably before transient CI artifacts expire.
- [ ] The advisor reviewed this candidate. The lead student uses their own Zenodo account
      and project secret for the manual publication workflow, selecting sandbox or production
      explicitly. Student-writable workflows do not enforce advisor approval on the Free plan.
- [ ] The published record's files and metadata were verified. Only a production receipt
      with actual published record and DOI evidence supplies README badges and citations.
- [ ] Any separately published research container has an explicit image publication plan,
      the recorded digest/platform and a working reproduction command. The starter image
      alone does not reproduce research results.

Record evidence beside each checked item. Do not make the repository public, enable Zenodo's
release-triggered GitHub integration, or rewrite Git history as a side effect of this process.
