#!/usr/bin/env python3
"""Disable the known idle persistent runner after isolated-session acceptance."""
import json
import os
from pathlib import Path
import subprocess

SERVICE='actions.runner.ftsrg-bclab-tdk.bme-cloud-29136.service'
MARKER=Path('/etc/tdk-allow-legacy-trusted-runner')


def command(*args):
    return subprocess.run(args,check=True,capture_output=True,text=True).stdout.strip()


def busy():
    group=command('systemctl','show',SERVICE,'-p','ControlGroup','--value')
    if not group:return False
    for file in (Path('/sys/fs/cgroup')/group.lstrip('/')).rglob('cgroup.procs'):
        for pid in file.read_text().split():
            try:
                if Path('/proc',pid,'comm').read_text().strip()=='Runner.Worker':return True
            except FileNotFoundError:pass
    return False


if __name__=='__main__':
    if os.geteuid()!=0:raise SystemExit('root required')
    if MARKER.exists():raise SystemExit('explicit legacy allow marker exists; inspect before retiring')
    if busy():raise SystemExit('runner busy; no changes made')
    active=command('systemctl','show',SERVICE,'-p','ActiveState','--value')=='active'
    if active:
        command('systemctl','freeze',SERVICE)
        try:
            if busy():raise RuntimeError('job appeared during preflight; retirement refused')
            # systemd thaws stopped units automatically; no job Worker was present.
            command('systemctl','stop',SERVICE)
        finally:
            subprocess.run(['systemctl','thaw',SERVICE],capture_output=True)
    command('systemctl','disable',SERVICE)
    directory=Path('/etc/systemd/system')/(SERVICE+'.d')
    directory.mkdir(exist_ok=True)
    (directory/'90-retired.conf').write_text('[Unit]\nConditionPathExists='+str(MARKER)+'\n')
    command('systemctl','daemon-reload')
    print(json.dumps({'service':SERVICE,'active':command('systemctl','show',SERVICE,'-p','ActiveState','--value'),
                      'enabled':command('systemctl','show',SERVICE,'-p','UnitFileState','--value'),
                      'restart_requires':str(MARKER)}))
