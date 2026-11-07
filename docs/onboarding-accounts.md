# Required personal accounts

This is the account guide fragment and integration contract. The onboarding
owner will place the student-facing text in the paper guide and connect the
module to the shared setup command. There is no standalone account CLI yet.

## Student guide text

Create or reuse your own GitHub, Overleaf, ORCID, Zotero and Zenodo accounts.
Sign in to accounts you already have before registering new ones. Keep your
existing ORCID iD throughout your research career; do not create another for
this project. Use a recognisable profile picture on the services you use with
the group, following the guide's existing profile guidance.

| Service | Create an account | Find or check your profile | Identifier requested by setup |
| --- | --- | --- | --- |
| GitHub | [Sign up](https://github.com/signup) | [Official profile instructions](https://docs.github.com/en/account-and-profile/tutorials/personalize-your-profile) | Personal username, not an organization name or repository URL |
| Overleaf | [Register](https://www.overleaf.com/register) | [Account settings](https://www.overleaf.com/user/settings), after signing in | An email address confirmed on your account, for project invitations |
| ORCID | [Register](https://orcid.org/register) | [Your ORCID record](https://orcid.org/my-orcid), after signing in | Your ORCID iD or full `https://orcid.org/…` URL |
| Zotero | [Register](https://www.zotero.org/user/register) | [Profile settings](https://www.zotero.org/settings/profile), after signing in | Your Zotero username |
| Zenodo | [Sign up](https://zenodo.org/signup/) | [Official profile instructions](https://help.zenodo.org/docs/profile/) | The username shown in your Zenodo profile |

Complete any email confirmation requested by the service. For Overleaf, check
the email address in your existing account settings before creating a second
account. You can [manage additional email addresses on the same account](https://docs.overleaf.com/accounts-and-security/email-address-and-login-options/managing-your-email-addresses).
For Zenodo, use the username in the Zenodo profile even if you sign in through
GitHub or ORCID.

Setup asks only for these identifiers and a confirmation that you can sign in
to the account. Enter passwords, tokens and recovery codes only where the
service itself requires them, never into an account identifier prompt. Setup
keeps accepted identifiers locally so you can stop and resume. At the sign-in
confirmation, enter `edit` to correct a saved identifier. A changed identifier resets
that account and its access evidence, preserving the other services. A public
account lookup records existence; it still requires your sign-in confirmation. A missing or
invalid answer leaves that step pending; reuse an existing answer unless you
need to correct it.

A valid identifier format does not establish that an account exists. A manual
sign-in confirmation is recorded as your statement; it is not an API check.
Finding a public account establishes neither that you control it nor that it
can access the project. GitHub repository permissions, Overleaf project access
and Zotero group membership each need their own checks. An account checklist
alone does not complete onboarding.

Registering with Zenodo does not choose who publishes the project's artifacts,
select credentials, enable automatic archiving or authorize publication. Those
decisions belong to the project's separate publication setup.

Your institutional identity is also used by the guide: university email,
Neptun, Moodle, Outlook and Teams. Reuse the university-provided identity and
resolve access through the institution; do not create unrelated personal
accounts to replace it. The guide's later conference-registration requirement
on the [BME TDK portal](https://tdk.bme.hu/) remains a separate dated step.
Optional calendar tools, AI services and anonymous-review tools are not added
to the five required personal accounts.

## Module contract

`scripts/onboarding/accounts.py` uses Python 3.9+ and the standard library.
The caller loads `account-services.json` into a dictionary. Its five service
keys are fixed for catalog version 1. The module performs no IO, network
requests, registration, permission changes, publication, process exits or
automatic interactive main. It does not import the orchestration entrypoint.

Functions:

- `prepare(catalog, existing=None)` returns `accounts` and `diagnostics`.
  It validates saved identifiers, recomputes format status, retains recognized
  evidence, and discards unknown fields or malformed evidence with static
  diagnostics. Pass only the account subtree, not the entire project config.
- `prompts(catalog, existing=None)` returns missing-step descriptors containing
  `service`, `field`, `kind`, `text`, `signup_url`, `profile_url`, and `required`.
  Render both links alongside each prompt. Recompute after each accepted answer
  so an identifier prompt is followed by its sign-in confirmation. Saved raw
  identifiers are absent from display text.
- `apply_answer(catalog, existing, service, field, value, *, checked_at=None)`
  returns `accounts`, `diagnostics`, and `accepted`. Fields are `identifier`
  (string) and `account_attested` (boolean). Attestation requires an ISO timestamp
  with a timezone supplied by the caller. `False` keeps the identifier, clears
  account/access evidence and leaves confirmation pending. A bad answer never
  overwrites the last valid answer. Re-entering the same normalized identifier
  preserves evidence; changing it clears account and access evidence.
- `record_check(catalog, existing, service, *, scope, outcome, method,
  checked_at, resource=None)` records independently obtained evidence. It does
  not perform or authenticate a check. See the accepted combinations below.
- `status(catalog, existing=None)` returns sanitized state, diagnostics and
  service steps with `next_action`, format/account statuses and scoped access
  records. `account_recorded` means only that the account step has evidence.
  Access requirements are explicitly `determined_by_orchestrator`.
- `validate_identifier(service, value)` returns `status` and a normalized
  `identifier` on success, or a static `code` on failure. This is a format check.

Each service's persisted entry has this shape:

```json
{
  "identifier": {"kind": "username", "value": "student-name"},
  "format": {"status": "valid"},
  "account": {
    "status": "manual_attested",
    "method": "manual_sign_in",
    "checked_at": "2026-11-03T21:00:00Z",
    "evidence": {"code": "attested"}
  },
  "access": []
}
```

Unanswered identifiers are `null`, with format `missing` and account `pending`.
Invalid attempted values are returned only as field-specific diagnostic codes;
they are never stored in the subtree. ORCID validation checks its checksum and
normalizes a full official URL to the hyphenated iD. GitHub usernames normalize
to lowercase. Overleaf email domain case normalizes; local-part case is retained.
Zotero/Zenodo username checks accept a conservative ASCII shape, not every
possible historical username. The email check also accepts a common ASCII
subset. An unsupported legitimate identifier needs an explicit validator update;
it must not lead a student to create a duplicate account.

### Evidence and adapter boundary

| Scope | Method | Outcomes | Meaning |
| --- | --- | --- | --- |
| `account` | `manual_sign_in` | `attested` | Student confirmed sign-in; status `manual_attested` |
| `account` | `public_lookup` | `found`, `not_found`, `unreachable`, `stale` | Existence only; respectively `verified`, `failed`, `pending`, `stale` |
| `access` | `authenticated_check` | `allowed`, `denied`, `unreachable`, `stale` | Scoped access; respectively `verified`, `failed`, `pending`, `stale` |
| `access` | `manual_access` | `allowed`, `denied`, `unreachable`, `stale` | Same outcomes, but success is labeled `manual_attested` |

Access records require a resource identifier including the permission tested,
such as `repo:org/project:write`, `overleaf:project-id:edit` or
`zotero:group-id:read`. They use the account evidence fields plus `resource`.
Recording one resource never grants or verifies another. Neither account
existence nor account attestation creates access evidence. Negative or stale
account-existence evidence clears old access evidence.

Adapters must bind observations to the exact saved identifier and authenticated
actor, resource and permission. They must discard results if the identifier has
changed during the request. Public profile lookup cannot prove ownership. An
authenticated adapter must identify the signed-in actor before claiming that
actor's access. Timeouts, authentication failures, rate limits and ambiguous
404s are `unreachable`, not `not_found` or `denied`. There is no default network
adapter or promise of a public lookup API for every service. Manual sign-in is
the available path for all five services.

The orchestrator decides evidence expiry and required resources. It can record
`stale` to request a recheck; timestamps alone do not trigger expiry here.
Evidence stored in a local JSON file is a record, not tamper-proof proof.
Do not use an edited state file as authorization for a privileged operation.

### Persistence and privacy

The orchestrator must write each accepted subtree atomically before asking the
next question. If EOF or interruption occurs before acceptance, keep the last
saved subtree. A save failure must be surfaced; do not report the answer as
durably saved. On resume, call `prepare` and show `status`/`prompts` from the
sanitized result. In dry-run mode, render proposed changes without writing.
The focused tests model save/reload after every answer; disk durability and
interactive interruption handling need orchestration integration tests.

Store state outside tracked files by default, with appropriate local file
permissions. Email addresses and usernames are non-secret but may be private.
Only explicitly approved public author identifiers should be projected into
tracked metadata by the orchestrator. Never log whole answers, account trees,
remote response bodies or authentication headers. Log static diagnostic codes
and service/field names instead. Treat the catalog as maintained application
data, not an untrusted user-supplied source of prompt URLs.

The module allowlists returned fields and evidence codes; there are no password,
token or free-form evidence fields. It rejects common credential prefixes,
assignment-shaped secrets and long hex strings in username fields. This catches
common accidental pastes, not arbitrary secrets: a password shaped exactly like
a valid username is indistinguishable from one. The orchestrator must also reject
secret fields outside this subtree and must not retain rejected raw input.

## Source review and integration notes

Official signup routes and profile routes/instructions were checked on
2026-11-03. The catalog records per-service provenance, date and limitations.
GitHub and Zenodo profile links intentionally lead to official instructions.
Overleaf and Zotero settings redirect to login; ORCID routes serve a JavaScript
application. These checks verify the entry points, not account creation or an
authenticated settings session. ORCID's checksum follows its
[identifier structure documentation](https://support.orcid.org/hc/en-us/articles/360006897674-Structure-of-the-ORCID-Identifier).

The source guide audit covered `guide/01-getting-started.tex`, lifecycle setup
and registration steps, the code/tools chapter, the Zenodo chapter, and other
account mentions across `guide/`. Institutional accounts and the conference
portal are retained as separate handoffs. Reclaim and AI-service mentions do
not establish required new accounts. The existing Zenodo chapter's owner-login
workflow must be reconciled by the publication/onboarding owners; this fragment
does not adopt it as credential policy. Existing ORCID author-metadata work
must be preserved when this fragment moves into `paper/`.

The onboarding owner still needs to connect this API to the common entrypoint,
atomic local storage, UI and required resource checks, then place the student
text in the shared guide. No overall onboarding completion is claimed here.

Run the focused deterministic tests without network access:

```sh
python3 -B -m unittest discover -s scripts/onboarding/tests -v
```
