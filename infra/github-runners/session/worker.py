#!/usr/bin/env python3
"""Unprivileged session bootstrap; the actual runner enters the outer sandbox."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

metadata = json.loads(Path(sys.argv[1]).read_text())
rootfs = Path(metadata['runtime']['rootfs'])
work = Path(os.environ['STATE_DIRECTORY'])
runner = work / 'runner'
if runner.exists():
    raise RuntimeError('refusing a reused runner workspace')
shutil.copytree(rootfs / 'home/runner', runner, symlinks=True)
(work / 'containers').mkdir()
jit = Path(os.environ['CREDENTIALS_DIRECTORY']) / 'jit'
args = ['/usr/bin/bwrap', '--unshare-all', '--unshare-user', '--uid', '1001', '--gid', '1001',
        '--cap-drop', 'ALL', '--die-with-parent', '--new-session', '--hostname', 'isolated-job',
        '--ro-bind', str(rootfs), '/', '--bind', str(work), '/job',
        '--bind', str(runner), '/home/runner', '--proc', '/proc', '--dev', '/dev',
        '--tmpfs', '/tmp', '--tmpfs', '/run', '--ro-bind', str(jit), '/run/jit',
        '--ro-bind', metadata['proxy_socket'], '/run/egress.sock',
        '--ro-bind', '/usr', '/infra/usr',
        '--ro-bind', '/etc/containers', '/infra/containers-config',
        '--ro-bind', str(Path(sys.argv[1]).parent/'scripts'), '/infra/scripts',
        '--chdir', '/home/runner', '--clearenv', '--setenv', 'HOME', '/home/runner',
        '--setenv', 'USER', 'runner', '--setenv', 'LANG', 'C.UTF-8',
        '--setenv', 'PATH', '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
        '--setenv', 'https_proxy', 'http://127.0.0.1:3128',
        '--setenv', 'HTTPS_PROXY', 'http://127.0.0.1:3128',
        '--setenv', 'http_proxy', 'http://127.0.0.1:3128',
        '--setenv', 'HTTP_PROXY', 'http://127.0.0.1:3128',
        '--setenv', 'ACTIONS_RUNNER_CONTAINER_HOOKS', '/infra/scripts/hook.js',
        '--', '/bin/bash', '/infra/scripts/entry.sh']
# No controller/admin environment survives. Only the single-job JIT file is exposed.
os.execve(args[0], args, {'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
