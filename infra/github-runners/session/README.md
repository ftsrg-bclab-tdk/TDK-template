# Native one-job GitHub runner

This path launches the **entire GitHub JIT runner inside the isolation boundary**.
The boundary does not depend on repository YAML, a step wrapper, container hooks,
or the listener cooperating. It executes native CPU instructions, with no nested
KVM or CPU emulation. The older persistent org runner has been stopped and disabled; a condition blocks
restarting it unless an administrator explicitly opts into trusted-only use.

## Boundary and supported jobs

A root controller creates a fresh locked host account, user/PID/mount/IPC/UTS/
network namespaces, a private 8 GiB ext4 disk and a systemd cgroup for each job.
The only shared filesystem data is read-only: the official runner and paper images, host
`/usr` helper tools and an immutable copy of the session scripts. No home directory,
host service socket, host cgroup filesystem, cloud credential, GitHub registration
authority or SSH agent is mounted. Set-ID image metadata can be unpacked, but
`NoNewPrivileges`, capability removal and non-suid mounts prevent elevation.
Fresh accounts are used because systemd 255's DynamicUser forces a chmod filter
that prevents ordinary OCI images from unpacking. Accounts are deleted after the
processes and storage are removed; they never have passwords, sudo or login homes.

The runner receives **only its one-job JIT credential**. Its own job token and any
secrets explicitly supplied by GitHub remain visible to that job, as on a hosted
runner. Never supply shared infrastructure credentials to student-controlled jobs.
This infrastructure does not reduce permissions of GitHub tokens selected in YAML
or make repository secrets safe from repository writers.

Host-enforced controls, independent of job code:

- no external IP route; one AF_UNIX socket admits only the job's host UID;
- HTTPS CONNECT on port 443 to the domain suffixes listed in `proxy.py`;
- every DNS result must be public and outside current host-interface subnets;
  connection uses that validated numeric address, avoiding a second DNS lookup;
- 6 GiB memory, no swap, 512 tasks, 750% CPU, bounded writable disk, at most two jobs;
- a root-selected deadline, control-group kill, and an independent 15-second cleanup
  timer that removes storage, proxy and account even after controller death.

The proxy provides network reachability restrictions, not data-loss prevention.
A job can send its own data to an allowed public service. TLS is end-to-end;
CONNECT filtering does not attest HTTP requests or virtual hosts on shared IPs.
Package managers must use HTTPS and permitted endpoints. Arbitrary new endpoints
require a reviewed host policy update; jobs cannot edit that policy.

Native shell/JavaScript actions, public OCI `container:` jobs, and registry-image
container actions are supported. Nested OCI containers retain the outer network
namespace and job filesystem boundary. Services, custom mounts, Docker options,
private registry credentials, host Docker, Dockerfile builds and inbound ports
are rejected or absent. Images plus compressed layers and source/output must fit
inside the selected disk class. No ordinary paper workflow has
been switched to it. Nested processes within **one** job share job authority; the
isolation unit is a job, not a step or action.

This is a shared-kernel userspace boundary. It assumes the kernel, systemd,
bubblewrap, OCI parsers and trusted controller are not compromised. It does not
provide VM isolation against kernel exploits or hardware side channels. Existing
pending host security updates were not installed by this work. Container hooks
are compatibility code inside the boundary, never the security mechanism.

## Identity and performance

`image.py` resolves `ghcr.io/actions/actions-runner:latest` on every session and
records its digest. That immutable runtime is cached read-only; resolution failure
fails the launch instead of using an older image. Job images resolve once per
image reference per job, then use that digest for copying. Their resolved identity
appears in the job log. Job-image metadata and artifacts are job-produced evidence,
not a trusted attestation of arbitrary workflow behavior. The root receipt records
runtime identity and a SHA-256 over the installed source filenames and contents.
Host helper package versions are recorded separately in acceptance evidence.

Runner startup, disk setup and cleanup add fixed overhead; CPU work is native.
There is no measured whole-paper or proof throughput claim. The runner image is
warm; writable workspaces are never shared across jobs. The paper class also has
a root-selected, immutable cache of the public TeX image. Its latest tag is resolved
on each admission. Each job gets its own OverlayFS upper/work directories on its
private disk. Root idmaps the read-only lower tree to the fresh job identity;
writes copy up into that job's disk. The guest cannot access the upper/work backing
directories directly. This avoids repeated extraction without sharing job writes.
See [live acceptance evidence](evidence-2026-11-05.md).

## Install and launch

On the existing BME VM, install only missing `bubblewrap`, `skopeo`, `umoci`,
`socat`, `python3`, AppArmor and ext4 utilities. `native/tdk-native.apparmor` must
already be loaded. It permits user-namespace creation for root-selected units;
it is explicitly unconfined and is not the sandbox policy. No inbound rule is
needed. This work installed missing packages with `--no-upgrade`; it did not
upgrade host packages or reboot.

Transfer this reviewed directory through the administrator's existing SSH access,
then run `sudo ./install.sh`. The installer installs the lifecycle helpers and
root cleanup timer. It neither registers a persistent runner nor changes workflow
routing. Do not grant workflows sudo access to any helper.

From a trusted controller with `gh` registration authority and the existing SSH
alias, run the isolated acceptance workflow in the dedicated private pilot repo:

```sh
python3 infra/github-runners/session/controller.py --mode probe --output /tmp/probe.json
python3 infra/github-runners/session/controller.py --mode container --output /tmp/container.json
python3 infra/github-runners/session/controller.py --mode cancel --output /tmp/cancel.json
python3 infra/github-runners/session/controller.py --mode timeout --seconds 60 --output /tmp/timeout.json
```

`pilot.yml` is the reproducible manual workflow installed there. It is not an
ordinary project workflow. The controller creates a repository-scoped JIT runner,
sends its credential only through SSH stdin, dispatches using a unique label,
monitors the run, and removes the registration after host cleanup. It never sends
the `gh` token to the VM or job. Class identity is `bme-isolated-native-v1`; the
unique session label prevents unrelated pilot jobs consuming the test runner.

For integration by a trusted CI controller, call root `session.py start --id ID` with JSON
on stdin containing `jit`, `repo`, `runner_id`, and `label`; use `--seconds` to set
a deadline of 10–7200 seconds. Persist the 32-character lowercase hexadecimal ID
before sending the request. IDs are single-use, including cancelled operations.
Omitting `--id` is supported for the interactive pilot, but cannot reconcile a
request that has not returned its generated ID. Start returns the session ID and
runtime/config identity.
Call `session.py status --id ID` to read state and `session.py stop --id ID` to
cancel. Stop is idempotent. **Call stop when cancellation is requested**, without
waiting for the guest or GitHub's UI to acknowledge it. GitHub's cancelled status
can lag after the host has already removed all job resources. The host deadline
remains in force if the controller is unreachable. The `acceptance_fixture` fields in status are diagnostic observations of the known
test payload; a student job can create its own marker and they are not an admission
or trust signal. Host receipts, not the guest's
logs or systemctl's reset state, are authoritative for timeout/OOM/cleanup causes.

## Automatic admission and paper acceptance

`broker.py` polls only repositories in its root-owned allowlist. It admits queued
jobs requesting exactly one configured class, optionally with `self-hosted`,
`Linux`, and `X64`. Unknown labels and hosted jobs are ignored. It records a unique
name before requesting a JIT configuration and a host operation ID before start,
reconciles ambiguous API/host responses
after restart, and uses GitHub's actual runner assignment to track completion.
Cleanup must remove the disk, cgroup and account before a slot is released.
The journal contains identifiers and receipts, never a JIT blob or token.

Root persists a reservation before preparing images. `list` includes pending
operations; they consume slots and disk budget even before a disk is allocated.
The broker keeps these reservations across restart. If a request is still in
transit, `stop --id ID` records cancellation before confirming cleanup, so a late
start with that ID is rejected. Cancellation during preparation prevents later
allocation; a shared-cache download already running may finish, but cannot start
the cancelled job. Preparation does not hold the global lifecycle lock. The root
reaper closes abandoned preparations after 1,350 seconds. Completed and cancelled
operation records are retained to prevent delayed requests from reusing an ID.

| Class | Writable disk | Supported execution |
| --- | --- | --- |
| `bme-isolated-native-v1` | 8 GiB | Native/JS actions and public OCI images that fit |
| `bme-isolated-paper-v2` | 8 GiB | Immutable TeX lower image, private writable upper, paper adapter |

The current VM configuration admits one job at a time, with an 8 GiB admission
budget. The engine independently caps all private disks at 20 GiB and requires
4 GiB host free space beyond the reserved job capacity. Disks use `fallocate` and
formatting disables discard; admission also accounts for any holes made by later
discard. The paper cache is a separate 14 GiB ext4 filesystem holding compressed
layers and the unpacked tree. A networkless, unprivileged builder extracts the
administrator-selected image under memory/CPU/deadline limits. It sees only host
helper binaries, read-only OCI input and its private output directory. After its
cgroup exits, root takes ownership without following symlinks; jobs receive only
the idmapped read-only lower through their private overlay. Builder failures never
promote partial output. A later prepare stops/reclaims an interrupted builder;
the unit has an independent 20-minute deadline.

Cache collection retains digests referenced by live sessions and durable pending
operation leases. Other digests are removed before downloading the new latest
image. A larger/new image that cannot fit fails admission, with no older fallback.
No writable build cache or derived Python environment survives a job. The old
`paper-v1` acceptance route extracted into a 20 GiB disk; it is not configured for
automatic admission. Its measured 470-second initialization and offline-wrapper
failure are retained as failed evidence, not readiness.

Install `install-broker.sh` after the session engine. Configure the repository
allowlist in `/etc/tdk-isolation/broker.json`, based on `broker.example.json`.
Supply a fine-grained token with repository Administration read/write (JIT
registration/removal) and Actions read (queue/status), selecting only the intended
repositories. Store it as root-owned mode 0600 `/etc/tdk-isolation/github-token`.
The unit loads it through systemd credentials, outside all guest mounts. Then run
`systemctl enable --now tdk-isolation-broker.service`. An alternative trusted
external controller can use `--host bclab-runner` and local `gh` authentication;
never run both controllers simultaneously. Broker restarts preserve job units.

The broker reacts to observed completed jobs/runs. GitHub may delay reporting a
cancellation; the independent root deadline still kills the job, and administrators
can call `session.py stop` immediately. Idle registrations are reclaimed after
180 seconds. API failures stop new admission and retain host deadlines. Expired
credentials need replacement and a broker restart to reload the systemd credential.

`.github/workflows/bme-acceptance.yml` is opt-in via repository variable
`BME_ACCEPTANCE_ENABLED=true`; it is separate from ordinary CI. It runs the current
TeX image in a job container, translates only the existing `paper.Dockerfile` pip
recipe, records its hash and actual resolved package versions, then runs the
configured paper checks, review evidence and maintainer checks in an offline
step namespace. `TDK_NETWORK_NONE=1` tells the outer hook to create that namespace
before mapping container UID 0; the adapter verifies that it has no external
interface or reachable proxy. This is a limited recipe adapter, not Dockerfile-build support.
Its offline wrapper is a convention within a job; the outer host network policy
remains enforced even when arbitrary workflow code bypasses the wrapper.
Artifacts include run/attempt/source/config/tool/image identities and timings.
Command timeout, launch failure and handled interruption preserve completed
command records and write a failed `bme-acceptance.json` receipt. A timeout uses
exit 124 and stops subsequent commands. SIGKILL or loss of the entire job can
still prevent a guest receipt; the host receipt remains the cleanup authority.
Publisher jobs and ordinary CI remain on their existing hosted route.

`retire-legacy.py` performed the idle check, stopped/disabled the known persistent
service and installed `90-retired.conf`. Its registration remains offline: deleting
an org runner requires authority the current token lacks. The allow marker
`/etc/tdk-allow-legacy-trusted-runner` is absent. No active job was observed or stopped.
The idle check cannot atomically drain GitHub assignments; use a maintenance window
if the old route ever has traffic.

## Cleanup and rollback

Root records live sessions in `/var/lib/tdk-isolation/sessions` and keeps receipts
in `receipts`. Disk files live in `disks`; root-only JIT staging is removed after
systemd loads it. The timer uses a lock to serialize cleanup with admission.
Failure to clean a session consumes its slot rather than reusing its state.

To remove this deployment, stop admitting sessions, call `stop --id` for each
listed session, and verify their receipts show disk/cgroup/account and image-mount removal.
Then disable `tdk-isolation-reap.timer`, remove its two unit files and the installed
helper directory, and reload systemd. The read-only official-image cache may be
removed after all sessions stop. Keep receipts as needed for audit. Do not enable
the legacy persistent runner for student jobs as an automatic rollback.

For the paper cache, wait for any image-builder unit to finish or stop it, then
unmount `/var/lib/tdk-paper-images` before deleting its `.ext4` backing file. Cache
resize is allowed only while the host is idle. It affects this deployment's cache,
not the host filesystem layout or cloud allocation.

Primary interface references: [GitHub container hooks](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/customize-containers),
[runner hook implementation](https://github.com/actions/runner/blob/main/src/Runner.Worker/Container/ContainerHooks/ContainerHookManager.cs),
[bubblewrap](https://github.com/containers/bubblewrap),
[systemd execution controls](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html).
The live runner used `args.container`, while an example in the documentation used
`jobContainer`; the adapter accepts both and tests the live implementation.
