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

Use Python 3.9 or newer inside a clone. Linux/WSL and macOS are supported hosts;
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

# Edit the value fields in onboarding.json, keeping expected source values intact.
python3 scripts/setup.py advisor
python3 scripts/setup.py advisor --apply-metadata --dry-run
python3 scripts/setup.py advisor --apply-metadata

# Show missing accounts, historical bootstrap evidence and external/manual actions.
python3 scripts/setup.py status
```

Creating the shared configuration does **not** create a GitHub repository.
Replace the example repository name with the advisor's intended project name.
The generated JSON selects `paper/thesis.tex` if present, otherwise `thesis.tex`.
Only the allowlisted title and author/advisor name macros can be changed. Values
are plain text and escaped for LaTeX. All changes are preflighted before writing;
an unexpected source value causes a conflict, preserving student edits. Reruns
are idempotent. Notes, chapter lists, lint phase and Zotero bibliography are never
managed. Unknown shared configuration fields are rejected, including credentials.

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

Host installation remains explicit under the platform's chosen policy. Missing
tools are reported; this command does not install packages, enable daemons,
change group permissions or choose Docker Desktop. The same CLI runs inside WSL;
desktop VS Code, browser and Zotero setup may be on the Windows host.

These are responsibilities, not claims that remote automation is implemented.
Controller authentication, credential placement/final publication execution and
2FA policy remain explicit unresolved integration inputs. There are no live
service mutations in the current onboarding modules.

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
metadata preview/application. Still required for full project onboarding: host
installation adapters, workspace generation, remote actions with identity/access
checks, shared paper-guide placement and CI evidence ingestion. The CI owner's
shared interface must be used rather than introducing a competing project-check
command here. No live disposable GitHub/Overleaf pilot has been performed.

`workflow.observations` accepts an injected read-only remote adapter for tests
and later integration. A timeout leaves the step pending; a different project
identity fails; verified evidence requires method/time/reference. No real remote
adapter is wired to the CLI, so external steps remain pending with their exact
actor and action. They cannot be marked complete by account-format checks or
repository/project URL existence.
