#!/usr/bin/env python3
"""Resolve the current official runner image, then cache only that immutable digest."""
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import time

BASE = Path('/var/lib/tdk-isolation-images')
REFERENCE = 'ghcr.io/actions/actions-runner:latest'


def prepare():
    if os.geteuid() != 0:
        raise RuntimeError('root required')
    BASE.mkdir(mode=0o755, exist_ok=True)
    with (BASE / 'prepare.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        metadata = json.loads(subprocess.check_output([
            'skopeo', 'inspect', '--override-os', 'linux', '--override-arch', 'amd64',
            'docker://' + REFERENCE], text=True))
        digest = metadata['Digest']
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
            raise RuntimeError('invalid image digest')
        dest = BASE / digest.split(':')[1]
        if not (dest / 'ready.json').exists():
            if dest.exists():
                raise RuntimeError('incomplete image cache; inspect before retry: ' + str(dest))
            dest.mkdir(mode=0o755)
            subprocess.run(['skopeo', 'copy', '--override-os', 'linux', '--override-arch', 'amd64',
                            'docker://ghcr.io/actions/actions-runner@' + digest,
                            'oci:' + str(dest / 'oci') + ':runtime'], check=True)
            subprocess.run(['umoci', 'unpack', '--rootless', '--image', str(dest / 'oci') + ':runtime',
                            str(dest / 'bundle')], check=True)
            if not (dest / 'bundle/rootfs/home/runner/run.sh').is_file():
                raise RuntimeError('official image layout changed')
            (dest / 'ready.json').write_text(json.dumps(metadata))
        # OCI permissions may include world-writable directories; cache is root-owned.
        (dest / 'bundle').chmod(0o755)
        for base, dirs, files in os.walk(dest / 'bundle/rootfs'):
            for path in [Path(base)] + [Path(base)/x for x in files]:
                if not path.is_symlink(): path.chmod(path.stat().st_mode & ~0o022)
        return {'reference': REFERENCE, 'digest': digest, 'resolved_at': time.time(),
                'rootfs': str(dest / 'bundle/rootfs')}


if __name__ == '__main__':
    print(json.dumps(prepare()))
