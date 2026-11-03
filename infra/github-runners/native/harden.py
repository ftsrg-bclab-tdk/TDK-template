#!/usr/bin/env python3
"""Migrate the known BME service to an unprivileged account; refuse busy runners."""
import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys

SERVICE = 'actions.runner.ftsrg-bclab-tdk.bme-cloud-29136.service'
SOURCE = Path('/home/cloud/actions-runner')
DEST = Path('/var/lib/tdk-ci')
DROPIN = Path('/etc/systemd/system') / (SERVICE + '.d') / '50-trusted-hardening.conf'
BACKUP = Path('/var/lib/tdk-runner-hardening')


def call(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def workers():
    return [p.parent.name for p in Path('/proc').glob('[0-9]*/comm')
            if p.exists() and p.read_text().strip() == 'Runner.Worker']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--rollback', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('run with sudo')
    if workers():
        raise RuntimeError('Runner.Worker is active; no service changes made')
    if not args.apply:
        print(json.dumps({'service': SERVICE, 'busy': False, 'destination': str(DEST),
                          'operation': 'rollback' if args.rollback else 'harden'}))
        return
    if args.rollback:
        if not DROPIN.exists():
            raise RuntimeError('hardening drop-in not present')
        call('systemctl', 'stop', SERVICE)
        DROPIN.unlink()
        (DROPIN.parent / '60-egress.conf').unlink(missing_ok=True)
        call('systemctl', 'daemon-reload')
        call('systemctl', 'start', SERVICE)
        print('Original service restored; stopped copy retained for administrator inspection')
        return
    if DROPIN.exists() or DEST.exists() or BACKUP.exists():
        raise RuntimeError('existing hardening state; inspect before retrying')
    # Freeze only long enough to check that no Worker appeared between preflight and
    # stop. A busy runner is thawed unchanged. Never kill a running job to migrate.
    call('systemctl', 'freeze', SERVICE)
    try:
        if workers():
            raise RuntimeError('job started during preflight; retry after it completes')
    finally:
        call('systemctl', 'thaw', SERVICE)
    # GitHub has no atomic drain API available to this token. Stop immediately after
    # the second check; service's normal graceful stop handles its listener.
    call('systemctl', 'stop', SERVICE)
    try:
        if workers():
            raise RuntimeError('worker still active; migration refused')
        BACKUP.mkdir(mode=0o700)
        (BACKUP / 'unit-before.txt').write_text(call('systemctl', 'cat', SERVICE))
        try:
            pwd.getpwnam('tdk-ci')
            raise RuntimeError('tdk-ci already exists; refusing to reuse unknown account')
        except KeyError:
            call('useradd', '--system', '--home-dir', str(DEST), '--shell', '/usr/sbin/nologin', 'tdk-ci')
        shutil.copytree(SOURCE, DEST, symlinks=True)
        user = pwd.getpwnam('tdk-ci')
        call('chown', '-hR', f'{user.pw_uid}:{user.pw_gid}', str(DEST))
        DEST.chmod(0o700)
        for name in ('.credentials', '.credentials_rsaparams', '.runner', '.env'):
            path = DEST / name
            if path.exists():
                path.chmod(0o600)
        DROPIN.parent.mkdir(exist_ok=True)
        shutil.copyfile(Path(__file__).with_name('trusted.conf'), DROPIN)
        DROPIN.chmod(0o644)
        call('systemctl', 'daemon-reload')
        call('systemctl', 'start', SERVICE)
        print('Dedicated-user service started. Verify GitHub connection before declaring success.')
    except Exception:
        DROPIN.unlink(missing_ok=True)
        call('systemctl', 'daemon-reload')
        call('systemctl', 'start', SERVICE)
        raise


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        sys.exit(1)
