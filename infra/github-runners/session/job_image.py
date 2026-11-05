#!/usr/bin/env python3
"""Cache compressed layers of the administrator-selected paper image, never job writes."""
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

BASE = Path('/var/lib/tdk-paper-images')
DISK = Path('/var/lib/tdk-paper-images.ext4')
REFERENCE = 'docker.io/danteev/texlive:latest'


def prepare():
    if os.geteuid() != 0:
        raise RuntimeError('root required')
    BASE.mkdir(mode=0o755, exist_ok=True)
    with Path('/run/tdk-paper-image.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not os.path.ismount(BASE):
            if not DISK.exists():
                if shutil.disk_usage(BASE).free < 28*1024**3:
                    raise RuntimeError('insufficient paper cache and job capacity')
                subprocess.run(['fallocate','-l','4G',str(DISK)],check=True)
                subprocess.run(['mkfs.ext4','-q','-F','-m','0','-E','nodiscard',str(DISK)],check=True)
            subprocess.run(['mount','-o','loop,nodev,nosuid,noexec',str(DISK),str(BASE)],check=True)
            BASE.chmod(0o755)
        metadata = json.loads(subprocess.check_output([
            'skopeo', 'inspect', '--override-os', 'linux', '--override-arch', 'amd64',
            'docker://'+REFERENCE], text=True, timeout=60))
        digest = metadata['Digest']
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
            raise ValueError('invalid paper image digest')
        dest = BASE/digest.split(':')[1]
        if not (dest/'ready.json').exists():
            # A 4 GiB filesystem bounds all image downloads, including a changed
            # upstream image. Never silently fall back to an older cached tag.
            if dest.exists():
                raise RuntimeError('incomplete paper cache requires operator inspection')
            dest.mkdir(mode=0o755)
            subprocess.run(['skopeo', 'copy', '--override-os', 'linux', '--override-arch', 'amd64',
                'docker://'+metadata['Name']+'@'+digest, 'oci:'+str(dest/'oci')+':job'],
                check=True, stdout=subprocess.DEVNULL, timeout=1200)
            (dest/'ready.json').write_text(json.dumps(metadata))
        return {'reference': REFERENCE, 'digest': digest, 'resolved_at': time.time(),
                'oci': str(dest/'oci')}


if __name__ == '__main__':
    print(json.dumps(prepare()))
