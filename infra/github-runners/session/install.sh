#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root.' >&2; exit 1; }
cd -- "$(dirname -- "$0")"
for tool in bwrap skopeo umoci socat python3 systemd-run mkfs.ext4 fallocate; do
  command -v "$tool" >/dev/null || { echo "Install missing dependency: $tool" >&2; exit 1; }
done
id tdk-proxy &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin tdk-proxy
install -d -m 0755 /usr/local/lib/tdk-isolation
install -m 0755 image.py job_image.py worker.py session.py proxy.py finish.py hook.py entry.sh /usr/local/lib/tdk-isolation/
install -m 0644 hook.js /usr/local/lib/tdk-isolation/
install -m 0644 tdk-isolation-reap.service tdk-isolation-reap.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now tdk-isolation-reap.timer
