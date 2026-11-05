# Native one-job GitHub runner

This path launches the **entire GitHub JIT runner inside the isolation boundary**.
The boundary does not depend on repository YAML, a step wrapper, container hooks,
or the listener cooperating. It executes native CPU instructions, with no nested
KVM or CPU emulation. The older persistent org runner has been stopped and disabled; a condition blocks
restarting it unless an administrator explicitly opts into trusted-only use.

## Boundary and supported jobs

A root controller creates a fresh locked host account, user/PID/mount/IPC/UTS/
network namespaces, a private 8 GiB ext4 disk and a systemd cgroup for each job.
The only shared filesystem data is read-only: the official runner image, host
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
- 6 GiB memory, no swap, 512 tasks, 750% CPU, 8 GiB writable disk, at most two jobs;
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
inside 8 GiB; full TeX images may exceed this class. No ordinary paper workflow has
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
warm; writable workspaces and job image downloads are not shared across jobs.
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

For integration by a trusted CI controller, call root `session.py start` with JSON
on stdin containing `jit`, `repo`, `runner_id`, and `label`; use `--seconds` to set
a deadline of 10–7200 seconds. It returns a session ID and runtime/config identity.
Call `session.py status --id ID` to read state and `session.py stop --id ID` to
cancel. Stop is idempotent. **Call stop when cancellation is requested**, without
waiting for the guest or GitHub's UI to acknowledge it. GitHub's cancelled status
can lag after the host has already removed all job resources. The host deadline
remains in force if the controller is unreachable. The `acceptance_fixture` fields in status are diagnostic observations of the known
test payload; a student job can create its own marker and they are not an admission
or trust signal. Host receipts, not the guest's
logs or systemctl's reset state, are authoritative for timeout/OOM/cleanup causes.

There is currently no provisioned narrow unattended registration credential on
BME or in `tdk-maintenance`. The local authorized `gh` credential works for these
repository-scoped sessions; org runner administration returns HTTP 403. Deploying
an always-on admission controller requires a narrowly scoped GitHub App or token
outside all job sandboxes, plus the CI owner's routing/admission integration.
No personal token was copied to the VM. Ordinary workflows retain their current
routing and explicit hosted fallback design.

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
listed session, and verify their receipts show disk/cgroup/account removal.
Then disable `tdk-isolation-reap.timer`, remove its two unit files and the installed
helper directory, and reload systemd. The read-only official-image cache may be
removed after all sessions stop. Keep receipts as needed for audit. Do not enable
the legacy persistent runner for student jobs as an automatic rollback.

Primary interface references: [GitHub container hooks](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/customize-containers),
[runner hook implementation](https://github.com/actions/runner/blob/main/src/Runner.Worker/Container/ContainerHooks/ContainerHookManager.cs),
[bubblewrap](https://github.com/containers/bubblewrap),
[systemd execution controls](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html).
The live runner used `args.container`, while an example in the documentation used
`jobContainer`; the adapter accepts both and tests the live implementation.
