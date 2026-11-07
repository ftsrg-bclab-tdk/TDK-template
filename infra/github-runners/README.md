# BME cloud runner pilot

BME cloud is the preferred backend. The [native one-job integration](session/README.md)
now runs fresh repository-scoped JIT runners inside host-enforced sandboxes, with
restricted egress, private bounded storage and external cleanup. Native and OCI
container GitHub jobs, artifact transfer, cancellation and controller-loss tests
have been exercised on the existing VM. Automatic admission now uses a root-only,
repository-scoped PAT. The full paper workload passed with an immutable image cache
and private writable job layers. See the [automatic admission evidence](session/evidence-automatic-2026-11-06.md)
and earlier [November 5 lifecycle evidence](session/evidence-2026-11-05.md).

The older persistent org runner has been stopped and disabled after an idle check.
It remains registered offline because the current token cannot administer org
runners. It must not be re-enabled for student workflows. The [November 3 native
prototype and hardening](native/README.md) remain documented for history.

Ordinary paper workflows remain GitHub-hosted; the separate BME acceptance workflow
is opt-in. This directory also retains the
original disposable-VM pilot below. Nothing here creates cloud resources or
changes organization permissions. `smoke.yml.example` is deliberately outside
`.github/workflows/` and has no effect until installed in a separate pilot repo.

## What was verified

During the initial inventory on 2026-11-03, `FTSRG-BCLab-TDK/TDK-template` was private and its repository runner
API returned zero runners. The organization runner API returned HTTP 403 with the
current token; this does not establish that the organization has no runners.
The organization workstream reports a Free organization and student write access.
Students can therefore author arbitrary workflows. A workflow label, approval
convention, or guest cleanup script cannot enforce the trust boundary.

The initial SSH/cloud configuration search yielded no BME access profile.
Later that day Martin added `bclab-runner` SSH access and registered the org
runner under `/home/cloud/actions-runner`; these supersede the initial absence
finding. The native runbook records its current configuration. A local student benchmark report mentions a BME VM; it supplies
no authorization or configuration for this deployment. No cloud credentials were
requested or read. The operator's existing GitHub login was sufficient for the
read-only repository inventory.

[BME's public help](https://ik.cloud.bme.hu/info/help/) describes CIRCLE, template
based VM creation, leases and administrator requests. That instance is marked for
IIT staff. It does **not** identify our allocation, establish access, or establish
an OpenStack API. No provider endpoints, template IDs, network IDs, or quotas are
assumed here. The external CIRCLE lifecycle/network interfaces remain unknown. This does not
prevent the native host-enforced controls implemented later in this task.

## Execution contract

The initial target is an empty, dedicated pilot repository with no student access,
no repository/organization secrets available to its workflows, no environment
credentials, and no cloud OIDC trust. Use only the smoke workflow below. The guest
is a new Ubuntu 24.04 x86-64 VM cloned from a clean image, with no attached store,
shared workspace, home directory, or persistent Docker volume. Start with one VM
and one job; resource size is an allocation decision, not encoded here.

A trusted operator machine creates a repository-scoped, single-job JIT
configuration through GitHub's API. Only this short-lived configuration enters the
guest. The GitHub administration credential and cloud management credentials stay
on the operator machine. Never install `gh` authentication, an SSH private key,
cloud credentials or an agent forwarding socket in the runner image. SSH is for
inbound operator access only and must use independently verified host keys.

The guest consumes one configuration, runs the runner as `runner`, and powers off
after the runner exits or a 45-minute local deadline. It cannot be armed twice
through the supplied script, even after a reboot or failed start. The service is
not enabled at boot. Failure to arm consumes the VM too; destroy it.

Docker access makes the job effectively root **inside the disposable VM**. The
service deadline, consumed marker, environment cleanup and poweroff are operational
precautions, not controls against malicious jobs. A job can defeat them. GitHub's
[JIT guidance](https://docs.github.com/en/actions/reference/security/secure-use)
requires a clean environment as well as single-job registration. All of these
external controls must be demonstrated before admitting student code:

- A fresh VM and fresh writable disks for every job, including failed/cancelled
  jobs; never resume a used VM or snapshot a registered runner.
- Hypervisor/cloud enforced destruction at an absolute deadline, surviving guest
  shutdown of its agents and loss of the controller process. Destroy disks too.
- Network enforcement outside the guest that denies other runners, management
  services, campus/lab private services, cloud metadata, link-local destinations,
  and IPv6 equivalents. BME may use public address space internally; blocking only
  RFC1918 ranges is insufficient. Allow only the approved DNS, GitHub, image and
  dependency endpoints. See GitHub's
  [connectivity requirements](https://docs.github.com/en/actions/reference/runners/self-hosted-runners).
- No shared writable caches across repositories or trust levels. Keep publishing,
  signing and deployment jobs on a separate trusted backend with their credentials.
- Trusted off-guest lifecycle records with VM ID, repository, runner ID, image
  version, job/run URL, start, deadline and confirmed deletion. Forward runner
  diagnostic logs before deletion to restricted storage without logging JIT
  configurations; define retention with the infrastructure owner.

Free-org runner policy capabilities and visibility remain unresolved. Do not base
isolation on selected-workflow restrictions that may be unavailable. A future
controller must check the repository allowlist and job event itself, cap total and
per-repository concurrency, and enforce resource/queue deadlines. Use separate
repository-scoped registrations, never a general organization runner accepting
arbitrary student jobs. Protect the controller source and host from student edits.
Labels select runners; they do not authorize jobs within a repository.

## Files and local checks

- `prepare-image.sh` installs Docker and the checksum-pinned GitHub runner on a
  fresh Ubuntu VM. It refuses other OS versions, non-VM hosts, and repeat installs.
- `pilot.py` prints a registration plan by default. Explicit `--apply` creates a
  repository JIT runner and writes its credential to a new mode-0600 file. It
  refuses existing files and symlinks. API responses are never printed.
- `guest.py arm` accepts the JIT credential on stdin as root; `guest.py run` executes
  it under the service account with a minimal environment and deletes the temporary
  credential file before launching the runner.
- `tdk-runner.service` runs once with a local timeout and best-effort poweroff.
- `smoke.yml.example` exercises Docker without checking out repository code.

Run from the repository root:

```sh
python3 -m unittest discover -s infra/github-runners/tests -v
bash -n infra/github-runners/prepare-image.sh
shellcheck infra/github-runners/prepare-image.sh
```

The hosted `runner kit` CI workflow runs these checks without cloud credentials.
The unit tests use a fake GitHub CLI and mocked guest system calls. They do not
prove VM boot, Docker integration, network isolation or destruction on BME.

## Pilot procedure (blocked on the allocation)

1. Obtain the actual BME dashboard/allocation, its administrator contact, and
   permission to consume existing quota. Confirm image/template access, independent
   maximum lifetime and network controls. No paid provisioning is authorized.
   If the allocation offers only a persistent VM on the campus network, stop here.
   Nested KVM is an alternative only after verifying support and approving a host
   that enforces guest networking and destruction. Shared Docker is insufficient.
2. Create the dedicated pilot repository and identify the permitted runner group
   ID with its administrator. Do not assume the default ID is `1`, request extra
   organization scopes, or change organization policy merely to make this work.
   The [repository JIT endpoint](https://docs.github.com/en/rest/actions/self-hosted-runners#create-configuration-for-a-just-in-time-runner-for-a-repository)
   needs repository administration write permission; use a narrowly installed
   GitHub App for production. Keep its key and installation tokens off guests.
   When an agent needs a new secret, use `request_secret`, never chat or Git.
3. On a fresh expendable image-build VM, transfer this reviewed directory, then run:

   ```sh
   sudo ./prepare-image.sh --disposable-image
   ```

   This is a mutating image-build command, not a command for your laptop or an
   existing research VM. It uses Ubuntu's package repositories and verifies the
   runner archive against the digest from the
   [v2.338.2 release](https://github.com/actions/runner/releases/tag/v2.338.2).
   Record the resulting OS/package/image versions. Rebuild for security fixes and
   runner releases; do not pin an obsolete runner indefinitely. No exact package
   snapshot is claimed. Before saving the clean image, remove build credentials,
   shell history, transfer keys and cloud-provided credentials; reset machine and
   SSH host identities using the allocation's supported image preparation process.
   Do not remove CIRCLE management components without its administrator's guidance.
4. Clone a new pilot VM. Apply an independent 45-minute maximum lifetime and network
   controls before registration. Record its VM ID and deletion deadline outside the
   guest. Verify the guest SSH host key through the cloud console. Provision only
   an operator public key. Do not mount a CIRCLE personal file store.
5. On the trusted operator machine, prepare the plan, then apply it using your
   real pilot repository and verified group ID. These examples require variables
   set by the operator; they contain no cloud defaults:

   ```sh
   python3 infra/github-runners/pilot.py --repo "$PILOT_REPO" \
     --runner-group-id "$PILOT_GROUP_ID"
   python3 infra/github-runners/pilot.py --repo "$PILOT_REPO" \
     --runner-group-id "$PILOT_GROUP_ID" --apply --isolated-disposable-pilot \
     --output "$PRIVATE_JIT_FILE"
   ```

   The output contains a runner ID and unique `bme-pilot-...` label, not the
   credential. Record both. JIT registration is a mutation; only apply when the VM
   is ready. The output directory must be private and outside this checkout and
   shared/synced storage. Never `cat` the credential into a transcript. If API or
   local output fails after registration, inspect the repository runner list for
   the planned name and remove the unused registration before retrying. Do not
   blindly repeat a POST after a timeout.
6. Install `smoke.yml.example` as `.github/workflows/bme-pilot.yml` **only in the
   dedicated pilot repository**. Transfer the credential using stdin with a
   root-capable operator account, strict host-key checking and no forwarding:

   ```sh
   ssh -o StrictHostKeyChecking=yes -o ForwardAgent=no -o ClearAllForwardings=yes \
     "$PILOT_SSH_TARGET" 'sudo -n /usr/local/lib/tdk-runner/guest.py arm' \
     < "$PRIVATE_JIT_FILE"
   rm -- "$PRIVATE_JIT_FILE"
   ```

   The remote account must already have the appropriate sudo permission; do not
   weaken SSH or sudo policy to bypass a failed connection. Dispatch the smoke
   workflow with the exact printed unique label. No registration/PAT secret goes
   into GitHub Actions secrets. Do not enable `GH_DEBUG`, shell tracing or process
   dumps around credential handling. The JIT argument is visible inside its guest;
   it must never be treated as a long-lived management credential.
7. Check the run and off-guest logs. Confirm GitHub removed the runner after its one
   job. Confirm the **VM and disks were deleted**, not merely powered off. Remove
   unused registrations through the repository runner API/settings and destroy
   the VM after any failure. Never revive it for a second attempt.
8. With separate fresh VMs, test a cancelled job, a runner crash and an expired idle
   runner, then a job that disables in-guest cleanup. Confirm the external deadline
   still deletes each VM. Probe blocked network targets with the administrator's
   approved test endpoints. Run two fresh VMs and check disk/cache/network isolation.
   Confirm the next VM contains no marker or workspace from the previous job.
   Collect evidence with timestamps before proposing student workload activation.

These steps are intentionally a manual pilot. Cloud API provisioning, an external
reaper, firewall rules, log transport, an autoscaler and production routing are not
implemented because their BME interfaces and allocation are unknown. A checkbox or
`--isolated-disposable-pilot` cannot attest to infrastructure isolation on its own.

## Fallback and later activation

The current paper workflow stays on `ubuntu-latest`. Once the cloud pilot passes,
review routing separately without changing paper paths. Keep GitHub-hosted as the
default until the fleet has an owner, capacity policy, external cleanup and an
incident procedure. Use a fixed, allowlisted backend selector controlled by
maintainers; student-editable YAML must not grant access to privileged runners.

GitHub does not automatically try `ubuntu-latest` when a self-hosted label has no
runner. A queued job can wait for 24 hours. A later rollout needs a queue watchdog
and an explicit hosted re-dispatch path, with a bounded retry policy. Document and
test this before changing active workflows. During rollback, stop provisioning,
restore hosted routing, cancel affected queued runs and rerun on the hosted path;
verify removal of every pilot registration, VM and disk.

## Documented alternatives

These are options for a later decision, not installed integrations. Check current
pricing, data location, GitHub App permissions, cache isolation and spend limits
before granting access or provisioning. No cost estimate or performance claim is
assumed for the TDK workload.

| Backend | Relevant evidence | What remains to decide |
| --- | --- | --- |
| Blacksmith | [Security documentation](https://www.blacksmith.sh/security) describes microVM isolation and a GitHub integration selecting runner tags. | Approve app access, region and cache boundaries; benchmark the TeX image and Docker workload. |
| Depot | [Runner overview](https://depot.dev/docs/github-actions/overview) and [ephemeral runner guide](https://depot.dev/resources/guides/how-do-ephemeral-github-actions-runners-work) describe managed GitHub runners and VM destruction per job. | Review cache policy and spending; verify Docker jobs and artifact uploads with the same smoke/build tests. |
| Ubicloud | [Quickstart](https://www.ubicloud.com/docs/github-actions-integration/quickstart) documents its GitHub App and runner-label integration, x64 and Arm options. | Review isolation and cache details for the selected service, region and plan. Self-hosting Ubicloud would be a separate infrastructure project, not an assumed BME feature. |

Sources were checked on 2026-11-03. Vendor claims are not evidence that our
particular configuration is safe. GitHub-hosted remains the available fallback
without onboarding another service.
