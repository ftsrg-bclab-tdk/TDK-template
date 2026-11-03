#!/usr/bin/env bash
# Only on a new, dedicated Ubuntu VM. Not on a workstation or an existing cloud VM.
set -euo pipefail
[[ ${1:-} == --disposable-image && $# == 1 ]] || {
  echo 'Usage: sudo ./prepare-image.sh --disposable-image (fresh Ubuntu 24.04 x64 VM only)' >&2; exit 2;
}
[[ $EUID == 0 ]] || { echo 'Root required' >&2; exit 1; }
# shellcheck source=/dev/null
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 && $(uname -m) == x86_64 ]]
systemd-detect-virt --vm >/dev/null
[[ ! -e /opt/actions-runner && ! -e /var/lib/tdk-runner ]]
if id runner &>/dev/null; then
  echo "Existing runner account; discard this image" >&2; exit 1
fi
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# This marker also prevents retries after an incomplete bake. Discard that image.
install -d -m 0700 /var/lib/tdk-runner
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git jq python3 docker.io
systemctl enable --now docker
useradd --create-home --shell /bin/bash runner
usermod -aG docker runner
install -d -m 0755 /opt/actions-runner /usr/local/lib/tdk-runner
archive=$(mktemp)
trap 'rm -f -- "$archive"' EXIT
version=2.338.2
sha256=baebf204307bac6193480852732f0aba2ae97b6c5597c244f4d5558390147c40
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "https://github.com/actions/runner/releases/download/v${version}/actions-runner-linux-x64-${version}.tar.gz" \
  --output "$archive"
printf '%s  %s\n' "$sha256" "$archive" | sha256sum --check --status
tar -xzf "$archive" -C /opt/actions-runner
/opt/actions-runner/bin/installdependencies.sh
chown -R runner:runner /opt/actions-runner
install -m 0755 "$here/guest.py" /usr/local/lib/tdk-runner/guest.py
install -m 0644 "$here/tdk-runner.service" /etc/systemd/system/tdk-runner.service
systemctl daemon-reload
# No enable/start, JIT configuration, admin token, SSH key, or cloud credential in the image.
echo 'Image software prepared. Follow README image sanitization before snapshotting.'
