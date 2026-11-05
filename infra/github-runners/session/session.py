#!/usr/bin/env python3
"""Root-owned BME session lifecycle. No GitHub administrative credential is stored here."""
import argparse
import fcntl
import hashlib
import pwd
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
from image import prepare
from job_image import prepare as prepare_job_image

ROOT = Path('/var/lib/tdk-isolation')
CODE = Path('/usr/local/lib/tdk-isolation')


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs)


def unit(identifier):
    if not re.fullmatch(r'[a-f0-9]{32}', identifier):
        raise ValueError('invalid session ID')
    return 'tdk-session-' + identifier


def start(data, seconds, runtime, disk_gib=8, job_image=None):
    if disk_gib not in (8,20):
        raise ValueError('unsupported disk class')
    if not 10 <= seconds <= 7200:
        raise ValueError('deadline out of range')
    if not re.fullmatch(r'[A-Za-z0-9+/=]+', data['jit']):
        raise ValueError('invalid JIT')
    reap()
    if len(list((ROOT/'sessions').glob('*.json'))) >= 2:
        raise RuntimeError('two job slots already occupied')
    # Existing disks are fully allocated, so free bytes already exclude them.
    if shutil.disk_usage(ROOT).free < (4+disk_gib)*1024**3:
        raise RuntimeError('insufficient reserved disk capacity')
    identifier = uuid.uuid4().hex
    name = unit(identifier)
    control = Path('/run') / ('tdk-control-' + identifier)
    control.mkdir(mode=0o755)
    user = 'tdkj' + identifier[:16]
    proxy_unit = 'tdk-proxy-' + identifier
    proxy_socket = '/run/' + proxy_unit + '/proxy.sock'
    metadata = {key:data[key] for key in ('repo','runner_id','label')}
    source=hashlib.sha256()
    for file in sorted(CODE.iterdir()):
        if file.suffix in ('.py','.sh','.js'):
            source.update(file.name.encode()+b'\0'+file.read_bytes())
    metadata.update(disk_gib=disk_gib,job_image=job_image,configuration_sha256=source.hexdigest(),id=identifier, runtime=runtime, user=user, proxy_socket=proxy_socket,
                    started_at=time.time(), deadline=time.time()+seconds)
    # Placeholder mount points are infrastructure overlays, never writable job data.
    rootfs = Path(runtime['rootfs'])
    for rel in ['job','infra/usr','infra/scripts','infra/containers-config','infra/job-oci']:
        (rootfs / rel).mkdir(parents=True, exist_ok=True)
    shutil.copytree(CODE, control/'scripts')
    (control / 'metadata.json').write_text(json.dumps(metadata))
    if job_image:
        (control / 'job-image.json').write_text(json.dumps(job_image))
    denied = []
    for interface in json.loads(run(['ip','-j','address']).stdout):
        for address in interface.get('addr_info', []):
            denied.append(str(ipaddress.ip_interface(f"{address['local']}/{address['prefixlen']}").network))
    (control / 'policy.json').write_text(json.dumps(denied))
    metadata_path=ROOT/'sessions'/(identifier+'.json')
    temporary=metadata_path.with_suffix('.new')
    with temporary.open('x') as output:
        json.dump(metadata,output);output.flush();os.fsync(output.fileno())
    temporary.replace(metadata_path)
    jit_path = ROOT / 'credentials' / identifier
    with jit_path.open('x') as output:
        jit_path.chmod(0o600)
        output.write(data['jit'])
    try:
        # DynamicUser forces RestrictSUIDSGID even when explicitly disabled; OCI
        # unpack needs to represent those mode bits. This fresh locked account
        # has no login/home/privileges and is deleted only after cgroup+disk cleanup.
        run(['useradd','--system','--no-create-home','--home-dir','/nonexistent',
             '--shell','/usr/sbin/nologin',user])
        disk=ROOT/'disks'/identifier
        run(['fallocate','-l',str(disk_gib)+'G',str(disk)])
        run(['mkfs.ext4','-q','-F','-m','0',str(disk)])
        state=Path('/var/lib')/name
        state.mkdir(parents=True,mode=0o700)
        run(['mount','-o','loop,nodev,nosuid',str(disk),str(state)])
        proxy = ['systemd-run','--quiet','--collect','--expand-environment=no','--unit',proxy_unit]
        for prop in ['Type=exec','User=tdk-proxy','NoNewPrivileges=yes','CapabilityBoundingSet=',
                     'ProtectHome=yes','ProtectSystem=strict','PrivateTmp=yes',
                     'MemoryMax=192M','TasksMax=128','LimitNOFILE=256',
                     f'RuntimeDirectory={proxy_unit}',f'RuntimeMaxSec={seconds+15}s']:
            proxy += ['--property',prop]
        run(proxy + [str(CODE/'proxy.py'),proxy_socket,user,str(control/'policy.json')])
        args = ['systemd-run','--quiet','--expand-environment=no','--unit',name]
        props = ['Type=exec',f'User={user}', 'AppArmorProfile=tdk-native-sandbox',
                 'NoNewPrivileges=yes','CapabilityBoundingSet=','RemoveIPC=yes',
                 'StateDirectoryMode=0700','RestrictSUIDSGID=no','UMask=0077','PrivateTmp=yes','PrivateDevices=yes',
                 'ProtectHome=yes','ProtectSystem=strict','ProtectControlGroups=yes',
                 'ProtectKernelModules=yes','KillMode=control-group','TimeoutStopSec=10s',
                 'MemoryMax=6G','CPUQuota=750%','LogRateLimitIntervalSec=30s','LogRateLimitBurst=100','MemorySwapMax=0','TasksMax=512','LimitCORE=0',
                 f'RuntimeMaxSec={seconds}s',f'StateDirectory={name}',
                 f'LoadCredential=jit:{jit_path}',f'ReadWritePaths={ROOT}',
                 f'ExecStopPost=+{CODE}/finish.py {identifier}']
        for prop in props:
            args += ['--property',prop]
        run(args + [str(CODE/'worker.py'),str(control/'metadata.json')])
        return metadata
    except Exception:
        subprocess.run(['systemctl','stop',name,proxy_unit],capture_output=True)
        raise
    finally:
        # systemd has copied the credential before Type=exec start succeeds.
        jit_path.unlink(missing_ok=True)


def status(identifier):
    name=unit(identifier)
    result=run(['systemctl','show',name,'-p','ActiveState','-p','Result','-p','ExecMainStatus']).stdout
    values=dict(line.split('=',1) for line in result.splitlines() if '=' in line)
    receipt=ROOT/'receipts'/(identifier+'.json')
    fixture={'ready':False,'listener_stopped':False,'host_uids':[]}
    try: fixture['ready']=stat.S_ISREG((Path('/var/lib')/name/'probe-ready').lstat().st_mode)
    except FileNotFoundError: pass
    cgroup=Path('/sys/fs/cgroup/system.slice')/(name+'.service')
    try: pids=(cgroup/'cgroup.procs').read_text().split()
    except FileNotFoundError: pids=[]
    uids=set()
    for pid in pids:
        try: process=dict(x.split(':',1) for x in Path('/proc',pid,'status').read_text().splitlines() if ':' in x)
        except FileNotFoundError: continue
        uids.add(int(process['Uid'].split()[0]))
        if process['Name'].strip()=='Runner.Listener' and process['State'].strip().startswith('T'):
            fixture['listener_stopped']=True
    fixture['host_uids']=sorted(uids)
    return {'id':identifier,**values,'acceptance_fixture':fixture,'receipt':json.loads(receipt.read_text()) if receipt.exists() else None}


def reap():
    for file in (ROOT/'sessions').glob('*.json'):
        metadata=json.loads(file.read_text());identifier=metadata['id'];name=unit(identifier)
        state=status(identifier)
        if state['ActiveState'] in ('active','activating','deactivating') and time.time() < metadata['deadline']+15:
            continue
        subprocess.run(['systemctl','stop',name,'tdk-proxy-'+identifier],check=False,capture_output=True)
        subprocess.run(['systemctl','reset-failed',name],check=False,capture_output=True)
        if Path('/sys/fs/cgroup/system.slice',name+'.service').exists():
            raise RuntimeError('job cgroup still exists; refusing storage/account reuse')
        # Only root-owned UUID-derived paths are traversed. rmtree does not follow
        # symlinks planted inside the untrusted job's private writable directory.
        directory=Path('/var/lib')/name
        # Compatibility with the earlier DynamicUser acceptance sessions.
        if directory.is_symlink():
            directory=Path('/var/lib/private')/name
        if directory.exists():
            if os.path.ismount(directory):
                run(['umount',str(directory)])
            shutil.rmtree(directory)
        (ROOT/'disks'/identifier).unlink(missing_ok=True)
        (ROOT/'credentials'/identifier).unlink(missing_ok=True)
        link=Path('/var/lib')/name
        if link.is_symlink(): link.unlink()
        shutil.rmtree(Path('/run')/('tdk-control-'+identifier),ignore_errors=True)
        receipt=ROOT/'receipts'/(identifier+'.json')
        report=json.loads(receipt.read_text()) if receipt.exists() else {'id':identifier,'result':'startup-failed'}
        report.update(cleaned_at=time.time(),disk_removed=not directory.exists(),
                      cgroup_removed=not Path('/sys/fs/cgroup/system.slice',name+'.service').exists(),
                      runtime=metadata['runtime'],job_image=metadata.get('job_image'),disk_gib=metadata.get('disk_gib',8),configuration_sha256=metadata.get('configuration_sha256'))
        receipt.write_text(json.dumps(report))
        account=metadata['user']
        if not re.fullmatch(r'tdkj[a-f0-9]{16}',account): raise ValueError('invalid account')
        try: pwd.getpwnam(account)
        except KeyError: pass
        else: run(['userdel',account])
        report['account_removed']=True
        receipt.write_text(json.dumps(report))
        file.unlink()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['start','status','stop','reap','list'])
    parser.add_argument('--id')
    parser.add_argument('--seconds',type=int,default=3600)
    parser.add_argument('--disk-gib',type=int,choices=(8,20),default=8)
    args=parser.parse_args()
    if os.geteuid()!=0: raise RuntimeError('root controller required')
    ROOT.mkdir(mode=0o700,exist_ok=True)
    for part in ['sessions','receipts','credentials','disks']:
        (ROOT/part).mkdir(mode=0o700,exist_ok=True)
    runtime=prepare() if args.action=='start' else None
    job_image=prepare_job_image() if args.action=='start' and args.disk_gib==20 else None
    # Serialize setup and reaping. Job units run independently of this lock.
    lock=(ROOT/'control.lock').open('w')
    fcntl.flock(lock,fcntl.LOCK_EX)
    if args.action=='start':
        print(json.dumps(start(json.load(sys.stdin),args.seconds,runtime,args.disk_gib,job_image)))
    elif args.action=='list':
        print(json.dumps([json.loads(p.read_text()) for p in sorted((ROOT/'sessions').glob('*.json'))]))
    elif args.action=='status': print(json.dumps(status(args.id)))
    elif args.action=='stop':
        subprocess.run(['systemctl','stop',unit(args.id)],capture_output=True)
        reap();print(json.dumps(status(args.id)))
    else: reap()


if __name__=='__main__':
    try: main()
    except Exception as error:
        # No request data, API response or JIT content in error output.
        print('Session operation failed: '+type(error).__name__,file=sys.stderr)
        sys.exit(1)
