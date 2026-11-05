#!/usr/bin/env python3
"""OCI compatibility hooks inside the job. Host security never depends on this code."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

BASE = Path('/job/containers')
LOADER = '/infra/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'
LIBS = '/infra/usr/lib/x86_64-linux-gnu'


def host_tool(name, args, capture=False):
    return subprocess.run([LOADER, '--library-path', LIBS, '/infra/usr/bin/'+name, *args],
                          check=True, text=True, stdout=subprocess.PIPE if capture else sys.stderr)


def restrictions(args):
    for key in ('createOptions', 'userMountVolumes', 'portMappings', 'registry', 'dockerfile'):
        if args.get(key):
            raise ValueError('unsupported container field: '+key)


def image(reference):
    if not re.fullmatch(r'[a-zA-Z0-9._/@:-]+', reference) or reference.startswith('-'):
        raise ValueError('invalid OCI image reference')
    if '/' not in reference: reference='docker.io/library/'+reference
    elif '.' not in reference.split('/')[0] and ':' not in reference.split('/')[0]: reference='docker.io/'+reference
    key=hashlib.sha256(reference.encode()).hexdigest()
    directory=BASE/key
    if (directory/'metadata.json').exists(): return json.loads((directory/'metadata.json').read_text())
    directory.mkdir()
    meta=json.loads(host_tool('skopeo',['inspect','--override-os','linux','--override-arch','amd64',
                                      'docker://'+reference],True).stdout)
    digest=meta['Digest']
    if not re.fullmatch('sha256:[a-f0-9]{64}',digest): raise ValueError('invalid OCI digest')
    # Inspect and copy the same immutable manifest; no fallback to a previous tag.
    name=meta['Name']+'@'+digest
    host_tool('skopeo',['copy','--override-os','linux','--override-arch','amd64',
                       '--policy','/infra/containers-config/policy.json',
                       'docker://'+name,'oci:'+str(directory/'oci')+':job'])
    host_tool('bwrap',['--unshare-user','--uid','0','--gid','0','--bind','/','/',
                       '--',LOADER,'--library-path',LIBS,'/infra/usr/bin/umoci',
                       'unpack','--rootless','--image',str(directory/'oci')+':job',str(directory/'bundle')])
    config=json.loads((directory/'bundle/config.json').read_text())
    def blob(digest): return json.loads((directory/'oci/blobs'/digest.replace(':','/')).read_text())
    index=json.loads((directory/'oci/index.json').read_text())
    manifest=blob(index['manifests'][0]['digest'])
    image_config=blob(manifest['config']['digest'])['config']
    resolved={'reference':reference,'digest':digest,'resolved_at':time.time(),
              'rootfs':str(directory/'bundle/rootfs'),'process':config['process'],
              'entrypoint':image_config.get('Entrypoint') or [],'cmd':image_config.get('Cmd') or []}
    (directory/'metadata.json').write_text(json.dumps(resolved))
    print('Resolved job image '+reference+' -> '+digest,flush=True)
    return resolved


def container(meta, args, command, extra_env=None):
    restrictions(args)
    root=Path(meta['rootfs'])
    bwrap=['--unshare-all','--share-net','--uid','0','--gid','0','--cap-drop','ALL',
           '--die-with-parent','--new-session','--bind',str(root),'/',
           '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--tmpfs','/run']
    for mount in args.get('systemMountVolumes',[]):
        if mount['targetVolumePath']=='/var/run/docker.sock':
            continue  # Runner supplies this by default; host Docker is never exposed.
        source=Path(mount['sourceVolumePath']).resolve()
        if not source.is_relative_to('/home/runner'):
            raise ValueError('system mount outside job runner workspace: '+str(source))
        target=mount['targetVolumePath']
        if not target.startswith(('/__w','/__e','/github/')) or '..' in Path(target).parts:
            raise ValueError('unsupported system mount destination')
        source.mkdir(parents=True,exist_ok=True)
        bwrap += ['--ro-bind' if mount.get('readOnly') else '--bind',str(source),target]
    env=dict(x.split('=',1) for x in meta['process'].get('env',[]) if '=' in x)
    env.update(args.get('environmentVariables') or {})
    env.update(extra_env or {})
    env.update(https_proxy='http://127.0.0.1:3128',HTTPS_PROXY='http://127.0.0.1:3128',
               http_proxy='http://127.0.0.1:3128',HTTP_PROXY='http://127.0.0.1:3128')
    env['PATH']=':'.join(args.get('prependPath',[])+[env.get('PATH','/usr/local/bin:/usr/bin:/bin')])
    bwrap += ['--clearenv']
    for key,value in env.items(): bwrap += ['--setenv',key,str(value)]
    bwrap += ['--chdir',args.get('workingDirectory') or '/', '--', *command]
    return subprocess.run([LOADER,'--library-path',LIBS,'/infra/usr/bin/bwrap',*bwrap],
                          env={'PATH':'/usr/bin:/bin'}).returncode


def main(request):
    action=request['command'];args=request.get('args') or {};state=request.get('state') or {}
    if action=='prepare_job':
        if args.get('services'): raise ValueError('service containers are not supported')
        job=args.get('container') or args.get('jobContainer')
        if not job: raise ValueError('prepare_job requires a job container')
        restrictions(job);meta=image(job['image'])
        response={'state':{'job':job,'image':meta},'context':{'container':{'id':meta['digest']},
                  'isAlpine':(Path(meta['rootfs'])/'etc/alpine-release').exists()},
                  'isAlpine':(Path(meta['rootfs'])/'etc/alpine-release').exists()}
        Path(request['responseFile']).write_text(json.dumps(response));return 0
    if action=='run_script_step':
        merged=dict(state['job']);merged.update(args)
        # Mounts originate from prepare_job; run_script_step does not supply them.
        return container(state['image'],merged,[args['entryPoint'],*args.get('entryPointArgs',[])])
    if action=='run_container_step':
        restrictions(args);meta=image(args['image'])
        command=([args['entryPoint']] if args.get('entryPoint') else meta['entrypoint'])+(args.get('entryPointArgs') or meta['cmd'])
        return container(meta,args,command)
    if action=='cleanup_job':
        # The outer systemd unit owns cleanup, including hostile background children.
        return 0
    raise ValueError('unsupported hook command')


if __name__=='__main__':
    try: sys.exit(main(json.load(sys.stdin)))
    except Exception as error:
        print('Container hook failed: '+str(error),file=sys.stderr)
        sys.exit(1)
