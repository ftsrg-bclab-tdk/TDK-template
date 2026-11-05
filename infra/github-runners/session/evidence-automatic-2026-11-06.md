# Automatic BME runner acceptance, 2026-11-06

The permanent root controller provisioned two isolation probes and the full paper
workload using its repository-scoped PAT. All three succeeded. Root receipts
confirm removal of each job's processes, disk, image mounts and locked account.
The [machine-readable evidence](evidence-automatic-2026-11-06.json) records exact
identities, timestamps, artifact verification and host observations.

The deployed implementation is [27ccc3d](https://github.com/ftsrg-bclab-tdk/TDK-template/commit/27ccc3db14b197ec106f414bdc7cad6287574d3a).
Installed engine SHA-256 is `8bd2924720c6d4c0621f126aebf89c1e75508c3f45e521ef3a85f27da0a52ced`;
broker SHA-256 is `055808cbf9c744342e4dcafa12ed8d11540937ab1154692776059bf6fa1e6e84`.
Hash installed `.py`, `.sh` and `.js` engine files sorted by filename, each filename
followed by a NUL byte and its contents. Broker configuration and its separate
hash are in the JSON receipt. Later documentation commits do not change these
installed files. Independent Sol review found no actionable defect at this source;
50 runner tests and Python Ruff F/diff checks passed.

## Permanent service and cross-job writes

`tdk-isolation-broker.service` is enabled and active. Only the template and private
pilot repositories are allowed. The PAT and controller journal are root-owned
mode 0600. Actual job UIDs could not read the PAT or write the shared image lower
tree. GitHub JIT creation, actual job assignment and registration removal succeeded
without a local helper. No org permission was added.

The [first](https://github.com/ftsrg-bclab-tdk/tdk-runner-isolation-pilot/actions/runs/42124395621)
and [second](https://github.com/ftsrg-bclab-tdk/tdk-runner-isolation-pilot/actions/runs/42124400987)
probes used fixture commit `3f38f25932aa9dcc049160af959a2d0d71dc399a`.
Both observed no previous job markers, then wrote workspace, temporary-directory
and image markers and replaced the image's `/etc/debian_version`. The second job
saw the original image. Raw upper/work directories were absent from the guest.
The root-owned lower file's SHA-256 stayed
`3c84b36be589a13576e4d54126a87ca950fe4b01716c42ef4ceb462e7445401c`, and its marker remained absent.

Both jobs positively logged `PAYLOAD_READY` after checking zero capabilities,
no-new-privileges, hidden host paths/credentials, blocked direct host/metadata/public
network access and proxy denial of private, unapproved, lookalike or non-443
targets. Allowed GitHub HTTPS, a registry container action and artifact upload
succeeded. Detached children disappeared with their cgroups. Downloaded artifact
archives matched GitHub's SHA-256, and their `evidence.txt` contents matched the
fixture. The JSON records each artifact ID/digest and the actual assigned job ID,
which can differ from the queued job that prompted admission.

Cleanup followed process termination after 10.23 and 3.97 seconds respectively.
Earlier [frozen-listener cancellation and controller-loss tests](evidence-2026-11-05.md)
retain their original source identities; they are not relabelled as reruns of this
revision. A live broker restart during paper-image preparation preserved the same
operation ID and single registration. The pending-operation snapshot is retained
in this receipt. Unit tests additionally cover delayed starts, restart, cancellation
tombstones and idle allowance beginning only after preparation.

## Representative paper workload

[Run 42126798775](https://github.com/ftsrg-bclab-tdk/TDK-template/actions/runs/42126798775)
succeeded at `27ccc3db14b197ec106f414bdc7cad6287574d3a`, attempt 1, on the permanent controller.
The shared report verifier accepted the committed project configuration digest
`9a87c7ec2419ae414e01d74cb36afdb1a74b0261e691935b248faf1010350046`, clean source before and after execution, required
paper runtime identities and all 10 declared evidence files.
Draft, final and lint gates passed. This was paper-only acceptance; the report
correctly leaves whole-project `acceptance_eligible` false.
The coordinator independently downloaded and verified this final service-mode
artifact and report, as well as both overlay probe artifacts/readiness logs.

Artifact ID is `13460503589`, archive SHA-256
`2b9bd775e7eeaecdec15e63d1e60139d9b01124a62c1f8d2a15d3e19d6a163ad`, and report SHA-256
`fd5446eaef2397b4068e78c7184d2bbc0122d821a40e37a7022f3c4a95665660`. The previous successful run
[42123545307](https://github.com/ftsrg-bclab-tdk/TDK-template/actions/runs/42123545307)
at `dc443a1` was independently downloaded and verified by the coordinator. Both
results retain their own source/configuration identities.

The paper image resolved to
`sha256:0d9a3e04eb3a6918c64c502c2129e9ffbf5ec0c55ea74f0eff277bc564ae5c41`. Latest image resolution happens on
every admission. The existing `paper.Dockerfile` pip recipe ran inside this job's
private image layer; its recipe hash and actual package/tool versions are in the
artifact. No writable Python environment or job output is cached between jobs.
All paper checks ran in a step namespace with no external interface or proxy.
This extra offline step is a workflow convention; the outer host boundary still
enforces restricted network/storage/process access if YAML bypasses it.

| Command | Observed elapsed seconds | Exit |
| --- | ---: | ---: |
| runtime | 1.02 | 0 |
| paper | 92.65 | 0 |
| review | 1.42 | 0 |
| maintainer | 117.35 | 0 |

Warm container initialization began and ended within GitHub's same one-second
timestamp interval. This avoids repeated image extraction. The first successful
bounded cache unpack took 576.7 seconds. The systemd journal rounded its peak to
6.0G under a 6 GiB memory limit; it used no swap. That cold cost excludes download and root publication.
A changed latest image must be rebuilt and fit the 14 GiB cache. Failure does not
silently reuse an older image.

The old compressed-cache route spent 470 seconds initializing, then failed on an
inner user-namespace mapping before executing paper checks. Its failure is retained,
not counted as readiness. The outer hook now creates the offline network namespace
before the nested UID mapping. These measurements do not establish a controlled
BME-versus-hosted throughput comparison.

## Capacity and final host state

The controller admits one job at a time on this 8-vCPU, approximately 15-GiB RAM,
48-GB-disk VM. Each job reserves an 8 GiB ext4 disk, with a 6 GiB memory limit, no
swap, 750% CPU, 512 tasks and a 45-minute host deadline. The engine also enforces
its aggregate disk cap and free-space reserve independently of the broker.
Actual systemd properties during the paper run are in the JSON evidence.

Five-second host samples observed at most
1.51 GiB of cgroup memory peak and
1.05 GiB of used private filesystem
space. The minimum sampled host free space was
6.78 GiB with the full private disk
reserved. These are sampled observations, not exhaustive disk high-water marks.
Samples after cgroup removal are excluded and retained separately in the JSON:
after unmount, the old directory can report the host filesystem's usage.
The guest's acceptance receipt records filesystem capacity and free space after
checks. After cleanup the host had 14.76 GiB available;
the bounded image cache had 0.96 GiB available.

Final inspection found no sessions, private disks, JIT staging files, job accounts,
job cgroups, control directories or job mounts. The shared lower image stayed
unchanged. The controller and cleanup timer remained active; SSH remained usable.
The persistent legacy runner stayed disabled, with its allow marker absent.
The acceptance opt-in was reset to false after the verified runs, so documentation
pushes do not launch more paper jobs. Ordinary CI and publisher routes remain hosted.

The service-mode trial initially failed before taking a job because `UMask=0077`
made public bootstrap files unreadable. Explicit public metadata/image permissions
fixed that defect while keeping credential/JIT/journal data private. Those failed
starts were cleaned and are recorded separately from successful payload execution.

## Integration boundary

Select `bme-isolated-native-v1` for supported 8 GiB native/public-OCI jobs, or
`bme-isolated-paper-v2` for the validated paper adapter. Only the configured class
plus optional `self-hosted`, `Linux`, `X64` labels is admitted. There is no host
Docker, Dockerfile build, service container, custom mount, inbound port or private
registry credential support. The ordinary CI execution path currently builds a
Dockerfile and therefore needs an explicit adapter/routing change by its owner.
The existing acceptance workflow supplies the concrete supported invocation and
preserves source/config/runtime/run/attempt/artifact identity. Hosted fallback must
be explicit; it is not an automatic timeout race.

This is isolation for arbitrary workflow code within a shared-kernel threat model.
Kernel exploits, hardware side channels and compromised trusted host components
are excluded. Jobs retain their own GitHub token and any repository secrets GitHub
supplies. Shared infrastructure credentials and publisher credentials remain
outside these jobs. No cloud allocation, host upgrade, reboot or inbound firewall
change was made. The narrow remaining work is CI routing integration under this
contract, not missing SSH, registration credentials or paper-capacity evidence.

## Recheck the retained evidence

While the seven-day artifact is retained, download its archive and compare its
SHA-256 with the value above. These commands write only under `/tmp`:

```sh
gh api repos/ftsrg-bclab-tdk/TDK-template/actions/artifacts/13460503589/zip > /tmp/bme-paper.zip
sha256sum /tmp/bme-paper.zip
unzip /tmp/bme-paper.zip -d /tmp/bme-paper-proof
PYTHONPATH=scripts python3 - <<'PY'
from ci.evidence import verify_report
verify_report(
    '/tmp/bme-paper-proof/checks/paper/report.json',
    repository='ftsrg-bclab-tdk/TDK-template',
    tested_sha='27ccc3db14b197ec106f414bdc7cad6287574d3a',
    config_sha256='9a87c7ec2419ae414e01d74cb36afdb1a74b0261e691935b248faf1010350046',
    required_components=['paper'],
    expected_report_sha256='fd5446eaef2397b4068e78c7184d2bbc0122d821a40e37a7022f3c4a95665660',
)
print('Paper identity, clean source, runtime, gates and evidence files verified')
PY
```

On the host, root receipts remain under
`/var/lib/tdk-isolation/receipts/<session_id>.json`. The JSON evidence names all
three session IDs. Read those files with the existing SSH/sudo access; do not read
or export the adjacent credential directory. `session.py list` reports live and
pending operations, and `systemctl is-active tdk-isolation-broker.service` checks
the permanent controller. An idle runner inventory is expected: each listener
exists for one job only.
