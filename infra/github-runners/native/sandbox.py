#!/usr/bin/env python3
"""Root-operated, offline native job sandbox. Not a GitHub runner integration."""
import argparse
import os
import re
import subprocess
import sys
import uuid


def command(payload, unit, seconds=60, memory='1G'):
    if not re.fullmatch(r'tdk-sandbox-[a-f0-9]{32}', unit):
        raise ValueError('invalid transient unit name')
    if not 1 <= seconds <= 3600 or not re.fullmatch(r'[1-9][0-9]*[MG]', memory):
        raise ValueError('invalid resource limit')
    if not payload or not payload[0].startswith('/'):
        raise ValueError('command must be an absolute sandbox path')
    # systemd allocates a distinct unprivileged host UID to each live unit.
    # Bubblewrap maps it to nobody inside new user/PID/mount/network namespaces.
    uid = 65534
    props = ['Type=exec', 'DynamicUser=yes', 'AppArmorProfile=tdk-native-sandbox', f'RuntimeMaxSec={seconds}s', 'TimeoutStopSec=2s',
             'KillMode=control-group', f'MemoryMax={memory}', 'MemorySwapMax=0',
             'TasksMax=128', 'LimitCORE=0', 'NoNewPrivileges=yes', 'UMask=0077',
             'PrivateTmp=yes', 'PrivateDevices=yes', 'ProtectHome=yes',
             'ProtectSystem=strict', 'ProtectKernelModules=yes', 'ProtectControlGroups=yes']
    args = ['/usr/bin/systemd-run', '--quiet', '--wait', '--pipe', '--collect',
            '--unit', unit]
    for prop in props:
        args.extend(['--property', prop])
    args += ['/usr/bin/bwrap', '--unshare-all', '--unshare-user', '--disable-userns',
             '--assert-userns-disabled', '--uid', str(uid), '--gid', str(uid),
             '--cap-drop', 'ALL', '--die-with-parent', '--new-session',
             '--hostname', 'job', '--ro-bind', '/usr', '/usr',
             '--symlink', 'usr/bin', '/bin', '--symlink', 'usr/lib', '/lib',
             '--symlink', 'usr/lib64', '/lib64', '--proc', '/proc', '--dev', '/dev',
             '--dir', '/etc', '--ro-bind', '/etc/ld.so.cache', '/etc/ld.so.cache',
             '--size', '536870912', '--tmpfs', '/tmp',
             '--size', '536870912', '--tmpfs', '/work', '--chdir', '/work',
             '--clearenv', '--setenv', 'PATH', '/usr/bin:/bin',
             '--setenv', 'HOME', '/work', '--setenv', 'LANG', 'C.UTF-8',
             '--remount-ro', '/', '--'] + payload
    return args


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--memory', default='1G')
    parser.add_argument('--unit', default='tdk-sandbox-' + uuid.uuid4().hex)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('payload', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    payload = args.payload[1:] if args.payload[:1] == ['--'] else args.payload
    cmd = command(payload, args.unit, args.seconds, args.memory)
    if args.dry_run:
        import json
        print(json.dumps(cmd))
        return 0
    if os.geteuid() != 0:
        raise RuntimeError('root controller required; never grant workflows sudo access to this helper')
    try:
        return subprocess.run(cmd, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
                              stdin=subprocess.DEVNULL).returncode
    finally:
        # A killed controller cannot execute this; systemd still enforces RuntimeMaxSec.
        subprocess.run(['/usr/bin/systemctl', 'stop', args.unit],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
