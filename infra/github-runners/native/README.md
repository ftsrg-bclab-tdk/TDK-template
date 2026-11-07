# Native isolation and the running BME service

This is the November 3 prototype and hardening record. The newer
[one-job JIT integration](../session/README.md) supersedes its unfinished integration
list. On November 5 the persistent service was stopped and disabled after an idle
check; it is no longer an active route. The following table describes the earlier
state, not the current deployment.

| Path | Current state | Boundary |
| --- | --- | --- |
| `bme-cloud-29136` GitHub org runner | Running as `tdk-ci`, connected and listening | Restricted trusted jobs. Persistent runner credentials, runtime and workspace remain shared with its job processes. |
| `sandbox.py` | Installed; live integration tests passed | Root-operated offline command sandbox, fresh users/namespaces/tmpfs/cgroup per invocation. **Not attached to GitHub job dispatch.** |

The native approach executes normal machine code. It uses no nested KVM and no
software CPU emulation. In the measured small compute test, median sandbox
setup/teardown added about 140 ms. This is not a paper-build or CI throughput
benchmark. See [the evidence](evidence-2026-11-03.md).

## What changed on the host

The runner was idle (no `Runner.Worker`, and the journal showed only listening).
Its service was stopped, migrated from `/home/cloud/actions-runner` to
`/var/lib/tdk-ci`, and restarted under a dedicated system account with no sudo
membership. `trusted.conf` applies no-new-privileges, empty capabilities,
protected homes, private devices/temp, a read-only host filesystem, writable
runner directory only, namespace creation denial, a 6 GiB memory limit and a
512-task limit. Files are private by default. The original installation remains
available for rollback; its `.credentials` permissions were corrected to `0600`.

`harden.py` checks for workers before migration and again after temporarily
freezing the service. If a worker exists, it thaws and refuses migration. It then
uses the service's normal graceful stop. There is no atomic GitHub queue-drain API
available to the current token, so an assignment racing the stop can still need a
retry. This is why installation is for a verified idle maintenance window, not a
method of interrupting or migrating running jobs. The observed migration did not
interrupt a job.

`egress.py` installs a separate nftables table scoped only to the `tdk-ci` UID.
It permits DNS to the host's loopback stub, existing connections and outbound
TCP 443. It rejects private, loopback, link-local/metadata, multicast, and current
host-interface subnets before permitting HTTPS; other ports are rejected. It
never flushes the host ruleset. SSH and other accounts retain their existing
policy. The runner requires the egress unit on future starts. Address changes
require rerunning the egress script; it discovers interface subnets at application
time, not continuously.

This is **not a GitHub-domain allowlist**. Public HTTPS destinations outside the
denied networks remain reachable, including any campus service on other public
ranges. Established connections are retained. That rule avoids disrupting the
connected listener but is not proof that an existing compromised session is safe.
No additional inbound ports were opened. Docker is absent; privileged/container
workflows are not supported by this hardened service.

## Offline sandbox contract

Only a trusted root controller can invoke the helper. Do not give `tdk-ci`, a
workflow, or a student sudo access to it. Example on the BME host:

```sh
sudo /usr/local/lib/tdk-native/sandbox.py --seconds 60 --memory 1G -- \
  /usr/bin/python3 -c 'print("native sandbox")'
```

The payload is passed as an argv array, never evaluated by a host shell. Each
invocation creates a unique systemd transient unit with a DynamicUser and fresh
user, PID, mount, IPC, UTS, cgroup and network namespaces. Bubblewrap maps the
unprivileged host user to UID 65534 inside the sandbox, drops all capabilities,
disables further user namespaces, and clears inherited environment variables.
Only `/usr` and the loader cache are shared read-only. `/proc` shows the private
PID namespace; `/dev` contains minimal devices. `/work` and `/tmp` are fresh
bounded tmpfs mounts. No host home, runner credential, service socket, source tree,
cache, Docker socket or cloud secret is mounted. Hosts must not store secrets
under the shared `/usr` tree. The current toolchain is the host's `/usr`, not a
versioned or sealed build image.

Network is completely absent except private loopback. Even loopback sockets in a
second job are unreachable. The job cannot bypass this by changing environment
variables or ignoring a workflow wrapper. The systemd unit enforces memory, swap,
process count and wall-clock limits outside the sandbox. It kills the cgroup on
completion/cancellation. A killed controller does not cancel the external
deadline. Anonymous filesystems disappear when the namespace is destroyed.

Ubuntu's global AppArmor user-namespace restriction initially prevented the
unprivileged setup. `tdk-native.apparmor` supplies an explicit **unconfined**
profile permitting namespace creation only when a root-created unit selects it.
It is not the sandbox confinement policy. Bubblewrap, permissions, namespaces and
cgroups provide that policy. The global AppArmor sysctl is unchanged. Live tests
confirmed that the payload runs under a non-root host UID, not just a cosmetic
non-root UID inside a user namespace.

The threat model covers arbitrary userspace payloads attempting normal filesystem,
process, credential, network and lifecycle access. It assumes the host kernel,
systemd, bubblewrap and read-only toolchain are trusted and patched. It does not
protect against a host-kernel exploit, hardware side channels, or a malicious
root administrator. No VM-grade boundary is claimed. The host has pending package
updates; a complete patch/reboot cycle was not performed during this running-job
maintenance task.

## Reproduce and roll back

The reviewed sources must be transferred by a trusted administrator to the BME
host. The installer is specific to the discovered service name and source path;
it does not guess another runner. Requirements already present on the host:
Ubuntu 24.04, systemd 255, bubblewrap 0.9, nftables 1.0.9, AppArmor and Python 3.

```sh
sudo ./install.sh --dry-run
sudo ./install.sh --apply
sudo /usr/local/lib/tdk-native/verify.py
```

The installer does not open firewall ports, reboot, register a runner or change
workflow routing. Repeating it refreshes its own firewall table and verifies the
existing service configuration. A modified service configuration fails review
rather than being silently overwritten. `verify.py` creates and removes named
test units and temporary credential canaries; it never reads real credential
contents. It also checks the live service's mount namespace with dropped
privileges without injecting a command into the listener.

To cancel a sandbox manually, use the root-selected unit name:

```sh
sudo systemctl stop tdk-sandbox-<uuid>.service
```

For rollback, wait for the GitHub runner to be idle. The script refuses an active
worker, removes its hardening/egress dependency drop-ins and starts the original
service. This restores the original, less restricted `cloud` account:

```sh
sudo /usr/local/lib/tdk-native/harden.py --rollback --apply
sudo systemctl disable --now tdk-ci-egress.service
```

The original credential copy, migrated directory and root-only unit backup are
retained for operator inspection. Do not run both runner copies simultaneously.
The helper/profile can remain installed without running any job. To fully remove
them, first verify no `tdk-sandbox-*` units remain, unload
`/etc/apparmor.d/tdk-native-sandbox` with `apparmor_parser -R`, then remove that
profile and `/usr/local/lib/tdk-native`. Remove the unused egress unit and reload
systemd. No cloud resource cleanup is required.

## November 5 follow-up

The [one-job JIT integration](../session/README.md) now places the entire listener
inside the outer sandbox, adds controlled HTTPS egress and per-run image identity,
exercises real native/container jobs and artifacts, and connects cancellation to
root-owned cleanup. Ordinary project routing is still unchanged. The persistent
service is stopped and disabled; no wrapper can accidentally make it a safe route.

The offline helper also received three audit repairs: systemd environment expansion
is disabled to preserve literal dollar arguments; timeout/OOM checks require
payload readiness and the host-recorded termination cause; an explicit unit name
cannot make the helper stop a unit owned by another invocation. Root receipts are
written by `result.py`. These repairs were installed and tested while the legacy
service was still active. Its historical mount/firewall probes require that old
service; do not re-enable it merely to repeat them. The session acceptance tests
are the current integration checks.

Technical references: [bubblewrap](https://github.com/containers/bubblewrap),
[systemd execution controls](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html),
[GitHub runner hooks](https://docs.github.com/en/enterprise-cloud%40latest/actions/how-tos/manage-runners/self-hosted-runners/run-scripts).
The installed systemd 255 behavior was tested directly; current documentation can
include options unavailable on that version.
