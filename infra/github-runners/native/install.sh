#!/usr/bin/env bash
# Install the measured native sandbox and trusted-runner hardening on this BME host.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root on bclab-runner' >&2; exit 1; }
mode=${1:---dry-run}
[[ $# -le 1 && ( $mode == --apply || $mode == --dry-run ) ]] || exit 2
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
for cmd in python3 systemctl systemd-run bwrap nft apparmor_parser; do command -v "$cmd" >/dev/null; done
service=actions.runner.ftsrg-bclab-tdk.bme-cloud-29136.service
# harden.py itself performs the live-worker guard and never migrates busy jobs.
if [[ $mode == --dry-run ]]; then
  python3 "$here/harden.py"
  echo 'Would install native sandbox, opt-in AppArmor profile and UID-scoped egress policy'
  exit 0
fi
install -d -o root -g root -m 0755 /usr/local/lib/tdk-native
for file in sandbox.py egress.py verify.py harden.py result.py; do
  install -o root -g root -m 0755 "$here/$file" "/usr/local/lib/tdk-native/$file"
done
install -m 0644 "$here/trusted.conf" /usr/local/lib/tdk-native/trusted.conf
install -m 0644 "$here/tdk-native.apparmor" /etc/apparmor.d/tdk-native-sandbox
apparmor_parser -r /etc/apparmor.d/tdk-native-sandbox
if [[ ! -f /etc/systemd/system/$service.d/50-trusted-hardening.conf ]]; then
  python3 /usr/local/lib/tdk-native/harden.py --apply
else
  [[ $(systemctl show "$service" -p User --value) == tdk-ci ]]
  cmp "$here/trusted.conf" "/etc/systemd/system/$service.d/50-trusted-hardening.conf"
fi
install -m 0644 "$here/tdk-ci-egress.service" /etc/systemd/system/tdk-ci-egress.service
systemctl daemon-reload
systemctl enable --now tdk-ci-egress.service
# An idempotent rerun refreshes the table with currently assigned interface subnets.
python3 /usr/local/lib/tdk-native/egress.py --apply
install -m 0644 "$here/60-egress.conf" "/etc/systemd/system/$service.d/60-egress.conf"
systemctl daemon-reload
systemctl is-active "$service"
echo 'Installed. Run sudo /usr/local/lib/tdk-native/verify.py to collect integration evidence.'
