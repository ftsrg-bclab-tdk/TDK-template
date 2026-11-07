#!/usr/bin/env python3
"""Cache compressed layers of the administrator-selected paper image, never job writes."""
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import time
import uuid

BASE = Path('/var/lib/tdk-paper-images')
DISK = Path('/var/lib/tdk-paper-images.ext4')
REFERENCE = 'docker.io/danteev/texlive:latest'
ROOT = Path('/var/lib/tdk-isolation')


def run(argv, **kwargs):
    return subprocess.run(argv,check=True,stdout=subprocess.DEVNULL,**kwargs)


def public_oci(directory):
    """Public registry blobs must be readable by the unprivileged image parser."""
    for path in [directory,*directory.rglob('*')]:
        if path.is_symlink():raise RuntimeError('unexpected OCI layout symlink')
        path.chmod(0o755 if path.is_dir() else 0o644)


def cache_disk():
    """Resize only our cache, while allocation is serialized and no job uses it."""
    with (ROOT/'control.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        previous=DISK.stat().st_size if DISK.exists() else 0
        wanted=14*1024**3
        if previous<wanted:
            if any((ROOT/'sessions').glob('*.json')):
                raise RuntimeError('cache resize requires an idle host')
            if shutil.disk_usage(DISK.parent).free < wanted-previous+12*1024**3:
                raise RuntimeError('insufficient cache, private job disk and host reserve')
            if os.path.ismount(BASE):run(['umount',str(BASE)])
            run(['fallocate','-l',str(wanted),str(DISK)])
            if previous:
                checked=subprocess.run(['e2fsck','-p',str(DISK)],stdout=subprocess.DEVNULL)
                if checked.returncode not in (0,1):raise RuntimeError('cache filesystem check failed')
                run(['resize2fs',str(DISK)])
            else:run(['mkfs.ext4','-q','-F','-m','0','-E','nodiscard',str(DISK)])
        if not os.path.ismount(BASE):
            run(['mount','-o','loop,nodev,nosuid',str(DISK),str(BASE)])
        BASE.chmod(0o755)


def cleanup_builder():
    journal=BASE/'builder.json'
    if not journal.exists():return
    value=json.loads(journal.read_text());identifier=value['id']
    if not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('invalid builder ID')
    name='tdk-image-build-'+identifier
    subprocess.run(['systemctl','stop',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if Path('/sys/fs/cgroup/system.slice',name+'.service').exists():
        raise RuntimeError('image builder cgroup still exists')
    shutil.rmtree(BASE/('build-'+identifier),ignore_errors=True)
    journal.unlink()


def unpack(dest):
    """Parse OCI as an unprivileged account in an isolated, networkless builder."""
    identifier=uuid.uuid4().hex;workspace=BASE/('build-'+identifier)
    workspace.mkdir(mode=0o700)
    account=pwd.getpwnam('tdk-proxy');os.chown(workspace,account.pw_uid,account.pw_gid)
    journal=BASE/'builder.json';journal.write_text(json.dumps({'id':identifier}));journal.chmod(0o600)
    name='tdk-image-build-'+identifier
    args=['systemd-run','--quiet','--wait','--collect','--expand-environment=no','--unit',name]
    for prop in ['Type=exec','User=tdk-proxy','AppArmorProfile=tdk-native-sandbox',
                 'NoNewPrivileges=yes','CapabilityBoundingSet=','ProtectHome=yes','ProtectSystem=strict',
                 'PrivateTmp=yes','PrivateDevices=yes','MemoryMax=6G','MemorySwapMax=0','TasksMax=128',
                 'CPUQuota=750%','RuntimeMaxSec=1200s','TimeoutStopSec=10s','KillMode=control-group',
                 'LimitCORE=0',f'ReadWritePaths={workspace}']:
        args += ['--property',prop]
    args += ['bwrap','--unshare-all','--uid','0','--gid','0','--cap-drop','ALL','--die-with-parent',
             '--new-session','--ro-bind','/usr','/usr','--symlink','usr/bin','/bin',
             '--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--dir','/etc',
             '--ro-bind','/dev/null','/etc/resolv.conf','--ro-bind','/dev/null','/etc/hosts',
             '--ro-bind','/dev/null','/etc/hostname',
             '--proc','/proc','--dev','/dev','--tmpfs','/tmp',
             '--ro-bind',str(dest/'oci'),'/image','--bind',str(workspace),'/output',
             '--clearenv','--setenv','PATH','/usr/bin:/bin','--setenv','HOME','/tmp',
             '--','/usr/bin/umoci','unpack','--rootless','--image','/image:job','/output/bundle']
    try:
        run(args,timeout=1230)
        if Path('/sys/fs/cgroup/system.slice',name+'.service').exists():
            raise RuntimeError('builder still owns output')
        bundle=workspace/'bundle'
        if not (bundle/'rootfs').is_dir() or (bundle/'rootfs').is_symlink():
            raise RuntimeError('invalid unpacked tree')
        # The builder is gone before root takes ownership. Never follow symlinks
        # while changing ownership/modes in image-controlled directory trees.
        for base,dirs,files in os.walk(bundle,followlinks=False):
            for path in [Path(base),*[Path(base)/part for part in dirs+files]]:
                os.lchown(path,0,0)
                if not path.is_symlink():path.chmod(path.stat().st_mode & ~0o022)
        bundle.chmod(0o755)
        bundle.rename(dest/'bundle')
    finally:cleanup_builder()


def protect_and_prune(digest, operation_id=None):
    """Lease the selected digest before releasing the cache lock to another start."""
    with (ROOT/'control.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if operation_id:
            if not re.fullmatch('[a-f0-9]{32}',operation_id):raise ValueError('invalid operation ID')
            path=ROOT/'operations'/(operation_id+'.json')
            value=json.loads(path.read_text())
            if value['phase']=='preparing':
                value['cache_digest']=digest
                tmp=path.with_suffix('.new')
                with tmp.open('w') as stream:
                    json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
                tmp.replace(path)
        protected={digest}
        for path in (ROOT/'sessions').glob('*.json'):
            value=json.loads(path.read_text());protected.add((value.get('job_image') or {}).get('digest'))
        for path in (ROOT/'operations').glob('*.json'):
            value=json.loads(path.read_text())
            if value['phase']=='preparing':protected.add(value.get('cache_digest'))
    # New preparers cannot pass the cache lock while pruning. Preparers that
    # already passed it have a durable lease above, even before allocation.
    for path in BASE.iterdir():
        if re.fullmatch('[a-f0-9]{64}',path.name) and 'sha256:'+path.name not in protected:
            shutil.rmtree(path)


def prepare(operation_id=None):
    if os.geteuid() != 0:
        raise RuntimeError('root required')
    BASE.mkdir(mode=0o755, exist_ok=True)
    with Path('/run/tdk-paper-image.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cache_disk();cleanup_builder()
        metadata = json.loads(subprocess.check_output([
            'skopeo', 'inspect', '--override-os', 'linux', '--override-arch', 'amd64',
            'docker://'+REFERENCE], text=True, timeout=60))
        digest = metadata['Digest']
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
            raise ValueError('invalid paper image digest')
        protect_and_prune(digest,operation_id)
        dest = BASE/digest.split(':')[1]
        if not (dest/'ready.json').exists():
            # A bounded filesystem contains all image downloads, including a changed
            # upstream image. Never silently fall back to an older cached tag.
            if dest.exists():
                raise RuntimeError('incomplete paper cache requires operator inspection')
            dest.mkdir(mode=0o755)
            dest.chmod(0o755)
            subprocess.run(['skopeo', 'copy', '--override-os', 'linux', '--override-arch', 'amd64',
                'docker://'+metadata['Name']+'@'+digest, 'oci:'+str(dest/'oci')+':job'],
                check=True, stdout=subprocess.DEVNULL, timeout=1200)
            (dest/'ready.json').write_text(json.dumps(metadata))
        dest.chmod(0o755)
        public_oci(dest/'oci')
        if not (dest/'bundle').exists():unpack(dest)
        config=json.loads((dest/'bundle/config.json').read_text())
        def blob(value):return json.loads((dest/'oci/blobs'/value.replace(':','/')).read_text())
        index=json.loads((dest/'oci/index.json').read_text())
        manifest=blob(index['manifests'][0]['digest'])
        image=blob(manifest['config']['digest'])['config']
        return {'reference': REFERENCE, 'digest': digest, 'resolved_at': time.time(),
                'oci': str(dest/'oci'),'rootfs':str(dest/'bundle/rootfs'),'unpacked':True,
                'process':config['process'],'entrypoint':image.get('Entrypoint') or [],
                'cmd':image.get('Cmd') or []}


if __name__ == '__main__':
    print(json.dumps(prepare()))
