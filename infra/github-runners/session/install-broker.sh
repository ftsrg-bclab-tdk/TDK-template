#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root.' >&2; exit 1; }
cd -- "$(dirname -- "$0")"
install -d -m 0700 /etc/tdk-isolation /var/lib/tdk-isolation-controller
install -d -m 0755 /usr/local/lib/tdk-isolation-controller
install -m 0755 broker.py /usr/local/lib/tdk-isolation-controller/
if [[ ! -e /etc/tdk-isolation/broker.json ]]; then
  install -m 0600 broker.example.json /etc/tdk-isolation/broker.json
fi
install -m 0644 tdk-isolation-broker.service /etc/systemd/system/
systemctl daemon-reload
if [[ -s /etc/tdk-isolation/github-token ]]; then
  chmod 0600 /etc/tdk-isolation/github-token
  systemctl enable --now tdk-isolation-broker.service
else
  echo 'Broker installed; activation awaits a narrow credential outside job sandboxes.'
fi
