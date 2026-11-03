# FTSRG TDK project template

<!-- tdk-status:start -->
Repository status links are generated after the project and CI workflows are set up.
No verified published artifact DOI has been supplied.
<!-- tdk-status:end -->

This template brings the paper, implementation, formal verification, evaluation,
research workspace and presentation into one repository. The finished template
is intended for public reuse after disclosure preparation; student projects are
private repositories in the lab organization.

| Component | Contents |
| --- | --- |
| [paper/](paper/README.md) | Paper sources, advisor guide, writing checks and review tools |
| code/ | Implementation, tests, Dockerfiles and build configuration |
| proof/ | Selected optional verification profiles and their assumptions |
| benchmark/ | Evaluation inputs, execution and results interface |
| scratch/ | Tracked research notes; temporary outputs and secrets stay untracked |
| presentation/ | Slides and rendering tools |

Select the components needed by the project. A proof result covers its configured
properties and assumptions, not every claim in the paper. Scratch is excluded
from publication by default, but all tracked files participate in native Overleaf
synchronization. Keep large datasets, installed dependencies and build outputs
outside Git.

## Start a project

1. The student checks existing accounts, enables required 2FA, and installs Git,
   Python, GitHub CLI and Docker. Local build and prover tools depend on the
   selected components.
2. The advisor creates the private organization repository and configures access.
   The student receives WRITE access to their own project as an outside collaborator.
   The advisor imports the repository into premium Overleaf, invites paper
   collaborators and sets up the Zotero group.
3. The student accepts invitations, clones the repository and configures the
   workspace. Student and advisor jointly verify compilation, both directions
   of native GitHub/Overleaf synchronization, and the project checks.

These are the responsibilities of onboarding, not a claim that account setup or
live integration is already complete. Native sync includes the whole repository.
Edit paper files in Overleaf and other components in their usual tools. This
convention does not preserve executable modes or symlinks automatically; verify
code execution after the round trip. There is no custom synchronization bridge.

## Build and check the paper

From the repository root:

```sh
make -C paper draft final
make paper-proxies
make check-final
```

The component build writes `paper/draft.pdf` and `paper/final.pdf`. The root
entrypoints `paper-draft.tex` and `paper-final.tex` are the Overleaf main-document
choices and write root outputs. Run these build routes sequentially in one
checkout because they share chapter auxiliary files. Use XeLaTeX, shell escape,
Inkscape and the dependencies described in the [paper README](paper/README.md).

A successful paper build does not establish submission readiness. Writing
findings remain visible even when CI succeeds; use `make check-submit` and advisor
review before submitting. Open CI results for the tested source, runtime and
scope. Native Overleaf synchronization needs its own verification.

## Publish and improve the template

The lead student owns the Zenodo records and deliberately runs publication after
advisor review. Packaging is automated; advisor review is a policy, not an enforced
boundary in student-writable workflows. The default research record combines
code, proof and benchmark artifacts; project configuration can select independent
records. Prepare metadata first and publish when there is a meaningful artifact.
Only verified published records receive DOI badges. Draft reservations are not
published artifacts.

Keep Dockerfiles and build configuration as source, and record built image digests
in evidence. Immutable GitHub releases do not freeze GHCR image tags. Downloaded
reference packages have their own manifests and retention; embedded paper graphics
remain tracked so the paper can compile in Overleaf.

Weekly or manually requested maintenance proposes reusable template-owned project
changes upstream as template PRs, then template improvements downstream as project
PRs. Neither direction auto-merges. Maintainers select mixed-file edits; student
research and private metadata are excluded. Latest-toolchain compatibility checks
are separate from these contribution/update PRs.

The legacy paper/code/notes template repositories are scheduled for deletion only
after the monorepo replacement is complete and verified. Student repositories are
not deleted; ended projects are archived in the organization, with requested
transfer or full-history copies coordinated with coauthors.

See [LICENSE](LICENSE) and [LICENSES/](LICENSES/) for scoped terms. Original tooling
uses MIT and original guide/slide prose uses CC BY 4.0. Inherited material,
institutional artwork and fonts retain their applicable terms and permissions.

Maintainers and onboarding automation regenerate the marked status block using
[scripts/readme](scripts/readme/README.md) with the actual repository metadata.
