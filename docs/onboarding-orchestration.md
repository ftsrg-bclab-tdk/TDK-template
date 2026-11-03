# Onboarding orchestration

The accepted workflow assigns concrete responsibilities:

1. The student creates or reuses GitHub, Overleaf, ORCID, Zotero and Zenodo
   accounts. Setup displays official links, records identifiers locally and
   tracks missing confirmations. The canonical account module owns these rules.
2. The student installs Git, Python, gh and Docker under the agreed host policy.
   Bootstrap verifies tools, daemon access and container execution. Local
   paper/proof/benchmark toolchains follow selected components.
3. The advisor creates the private organization project from the prepared
   template, populates bounded metadata and grants the student write access to
   their project. Students remain outside collaborators. Advisors manage project
   settings/access; organization creation/deletion/transfer remain owner-controlled.
4. The advisor imports the whole repository into premium Overleaf, configures
   root compilation entrypoints and invites the appropriate paper collaborators.
   The advisor handles Zotero group membership; the student accepts invitations.
5. The student clones the repository and prepares their workspace. Paper editing
   in Overleaf and other component editing in normal tools is a convention, not
   a guarantee about executable modes or symlinks during synchronization.
6. Student and advisor verify compilation, both sync directions and access.
   Fresh-clone component execution after the round trip is separate evidence.
7. Automated packaging prepares drafts. The lead student owns Zenodo records
   and deliberately publishes meaningful artifacts after advisor review.
   Account registration alone does not configure credentials or authorize this.

## Working terminal commands

Use Python 3.11 or newer inside a clone. Linux/WSL and macOS are supported hosts;
native Windows must use WSL. Commands below run from the repository root.

```sh
# Read-only preview, including official signup/profile links; no prompts/writes.
python3 scripts/setup.py student --dry-run --smoke

# Prompt for each required account and save each accepted answer before continuing.
python3 scripts/setup.py student

# Actual version and Docker daemon/access checks (no container or image pull).
python3 scripts/setup.py student --skip-accounts --check-bootstrap

# Explicitly pull alpine:latest once, resolve it, and run that digest as a smoke test.
python3 scripts/setup.py student --skip-accounts --check-bootstrap --smoke

# Advisor prepares a shared non-secret configuration for the intended private repo.
python3 scripts/setup.py advisor --init-config FTSRG-BCLab-TDK/example-project

# Edit the value fields in project.json, keeping expected source values intact.
python3 scripts/setup.py advisor
python3 scripts/setup.py advisor --apply-metadata --dry-run
python3 scripts/setup.py advisor --apply-metadata

# Show missing accounts, historical bootstrap evidence and external/manual actions.
python3 scripts/setup.py status
```

Creating the shared configuration does **not** create a GitHub repository.
Replace the example repository name with the advisor's intended project name.
The existing canonical `project.json` is loaded through `ci.config.load_project`.
Initialization replaces its repository identity with the supplied `ORG/REPO`,
populates missing metadata expectations, and preserves role, components and
compilation entrypoints. It does not verify access to that repository. The
editable source is exactly `paper_main`; root compilation proxies are never
metadata targets. If initialization needs to set a different source location,
use `--paper-source paper/draft.tex` explicitly. Missing canonical files/targets
fail; setup does not invent a second CI configuration or fall back to a legacy
file while a different source is declared.
Only the allowlisted title and author/advisor name macros can be changed. Values
are plain text and escaped for LaTeX. All changes are preflighted before writing;
an unexpected source value causes a conflict, preserving student edits. Reruns
are idempotent. Notes, chapter lists, lint phase and Zotero bibliography are never
managed. Unknown shared configuration fields are rejected, including credentials.
`--config other.json` uses the same validator. `repository: null` is structurally
valid and shown as unconfigured; account/bootstrap observations do not establish
project readiness. All config receipts use the SHA-256 of the exact bytes loaded
by the shared loader. Whitespace or other config changes invalidate dependent
stored evidence. An initializer rechecks the prior digest before writing and
never resets existing metadata expectations to bypass a student-edit conflict.

Private state defaults to `.onboarding/`, ignored by the supplied `.gitignore`.
It must remain untracked and owned by the current user with private directory/file
permissions. Symlink paths are rejected. The CLI holds an exclusive writer lock
through prompts/checks/writes; concurrent sessions fail instead of losing answers.
Status/dry-run take a shared lock if state exists and never create state or locks.
Do not run simultaneous sessions against different state directories for one
project. Never commit the private state or copy it into public metadata wholesale.

Without smoke execution, bootstrap readiness stays incomplete and check mode
returns exit 1. Tool/daemon/container failure also returns 1; configuration or
storage errors return 2. Read-only status returns 0 when inspection succeeds,
not when the whole project is ready. In dry run, even `--smoke` only prints the
plan. Real smoke may download an image; it passes no host mounts and disables
container networking. Its receipt stores requested latest tag, resolved digest,
image/platform identity, actual versions, Docker context, timestamp, source SHA,
dirty flag and shared-config digest. Pull failure never silently reuses an old
image. Old successful receipts are historical observations, not current runtime
or remote authorization evidence.

## Installation, workspace and GitHub adapters

```sh
# Preview host-specific commands; no package manager is invoked.
python3 scripts/setup.py student --skip-accounts --install-plan --docker-runtime engine
# Explicitly execute the displayed commands, retaining sudo/package prompts.
python3 scripts/setup.py student --skip-accounts --install-tools --docker-runtime engine
# On macOS choose desktop, or existing if a Docker runtime is already configured.
python3 scripts/setup.py student --skip-accounts --install-plan --docker-runtime desktop
python3 scripts/setup.py student --skip-accounts --workspace
# Read-only authenticated GitHub checks; never changes policy or invites anyone.
python3 scripts/setup.py student --skip-accounts --github-account
python3 scripts/setup.py advisor --inspect-repository --inspect-access STUDENT_USERNAME
```

Package adapters cover Ubuntu/Debian through apt, Arch through pacman and macOS
through an existing Homebrew installation. Unsupported hosts get explicit manual
steps. Only missing required tools are requested; there is no blanket system
upgrade, remote shell installer, group membership change or reboot. Package
installation may itself start services according to the host package policy.
Docker runtime selection is explicit. The WSL Desktop route points to host-side
installation/integration and does not install a competing Linux engine. Homebrew
installation itself and Docker service/user-access setup remain human actions.
A Python older than 3.11 must be upgraded before running this entrypoint.

The workspace command creates `tdk.code-workspace` from existing component
folders and retains root agent guidance. It records the generated hash privately;
modified files are not overwritten, and concurrent edits fail application.

Provisioning and invitation mutations are restricted to disposable repository
names `FTSRG-BCLab-TDK/onboarding-pilot-*` until a real pilot establishes the path.
These commands are implemented but have only been exercised with fake services:

```sh
python3 scripts/setup.py advisor --provision-pilot --dry-run
python3 scripts/setup.py advisor --provision-pilot
python3 scripts/setup.py advisor --invite-pilot STUDENT_USERNAME --dry-run
python3 scripts/setup.py advisor --invite-pilot STUDENT_USERNAME
```

Before the first command, `project.json` must name the disposable destination.
Use unchanged template component/metadata configuration for provisioning; populate
and apply paper metadata locally afterward. The provisioner authenticates the
advisor, verifies organization-owner authority, creates a private repository from
the configured template, and writes `role: project` and the correct repository
identity into its shared config. Readback is mandatory. A lost creation response
is recovered by observing the existing repo on rerun; mismatched private/owner/
template/config values stop the process. No public flip or existing repo deletion
is implemented. Controller/App deployment belongs to the organization owner;
this pilot adapter uses the advisor's existing `gh` authentication.

Invitations require an authenticated organization read with
`two_factor_requirement_enabled: true`, verified private-repo admin access, and
an invitee who is not an organization member. Missing/forbidden policy evidence
blocks the invitation. The command grants write only, preserves a matching pending
invitation without re-sending it, and reports accepted access only after a later
readback. Organization-required 2FA prevents acceptance until the invitee enables
it; a local student receipt is not used as enforcement proof. Existing-account
compliance must be reviewed before the organization owner enables that policy;
setup never toggles it. Personal `--github-account` 2FA output may be unavailable
when the token does not expose private user fields, which is reported explicitly.

Policies are settled: the private `tdk-maintenance` controller uses an organization
App installed on selected registered repositories; the lead student invokes the
project publication workflow with their own Zenodo repository secret after
advisor review of the exact artifact receipt. Deployments/permissions and the
actual pilot remain pending. Imre's agreement is not assumed. Advisor review is
policy, not an enforced boundary on student-writable workflows.

Sources reviewed 2026-11-04: [gh API](https://cli.github.com/manual/gh_api),
[template generation](https://docs.github.com/en/rest/repos/repos#create-a-repository-using-a-template),
[collaborator API](https://docs.github.com/en/rest/collaborators/collaborators),
[authenticated user/2FA fields](https://docs.github.com/en/rest/users/users#get-the-authenticated-user),
[organization 2FA](https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-two-factor-authentication-for-your-organization/requiring-two-factor-authentication-in-your-organization),
[Ubuntu Docker package](https://packages.ubuntu.com/noble/docker.io),
[Docker Desktop Homebrew cask](https://formulae.brew.sh/cask/docker-desktop), and
[WSL integration](https://docs.docker.com/desktop/features/wsl/).

## Shared CI evidence

```sh
python3 scripts/setup.py student --skip-accounts --ingest-ci .project/checks/report.json
```

Setup imports `ci.evidence.verify_report` and requires every enabled component,
current repository/SHA/raw-config digest, clean source, runtime resolution and
valid evidence file hashes. `--report-sha256` optionally binds the exact bytes to
a separately trusted receipt. Missing/failed/tampered reports do not advance the
private `component-checks.json` receipt. That receipt reports component consistency,
not full onboarding readiness. Native Overleaf roundtrip, fresh-clone boundaries
and artifact transport authority remain independent evidence. No arbitrary CLI
timestamp or editable JSON is accepted as verified synchronization. The trusted
pilot adapter may supply a boundary to the ingestion function; the shared verifier
then requires execution to start after it. Presenter notes remain private review
evidence and are never published by setup.

## Local account session

`scripts/onboarding/session.py` wraps the canonical `accounts.py` API. The caller
loads the catalog, selects a private **untracked** state path, supplies structured
prompt rendering/input callbacks, and calls `collect`. No default tracked state
path or public projection is provided. Do not print its full return value: it
contains private identifiers. Present the sanitized progress fields needed by
the student instead.

Each accepted answer is sanitized through the account module, written to a
temporary file with mode 0600, flushed, atomically replaced and directory-flushed
before the next prompt. Save failures propagate without a saved event. EOF or
interrupt retains prior accepted state. A declined sign-in confirmation saves
the pending state and returns instead of repeatedly prompting. Dry run reads
existing state and returns missing prompt descriptors without asking or writing.

The caller must serialize writers and choose a trusted private parent directory.
This is local single-session persistence, not a concurrent controller database.
Symlink state paths and group/world-accessible existing state files are rejected.
No account credentials are accepted; no account module source was duplicated.

Implemented here: terminal rendering, ignored/private path enforcement, per-state
serialized writers, latest-image resolution and Docker observations, bounded
metadata preview/application. Still required for full project onboarding: real disposable service/host pilots,
controller/App deployment, native Overleaf verification, shared paper-guide
placement and authoritative CI artifact-transport integration. The CI owner's
shared interface must be used rather than introducing a competing project-check
command here. No live disposable GitHub/Overleaf pilot has been performed.

`workflow.observations` accepts an injected read-only remote adapter for tests
and later integration. A timeout leaves the step pending; a different project
identity fails; verified evidence requires method/time/reference. The separate GitHub adapters above provide explicit observations; the aggregate
checklist remains pending until the complete pilot evidence is integrated. They cannot be marked complete by account-format checks or
repository/project URL existence.
