#!/usr/bin/env python3
"""Acceptance adapter for the current paper recipe inside an isolated OCI job."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time


def recipe(path):
    lines=[line.strip() for line in path.read_text().splitlines()
           if line.strip() and not line.lstrip().startswith('#')]
    if len(lines)!=4 or lines[:2]!=['ARG TEX_IMAGE=danteev/texlive:latest','FROM ${TEX_IMAGE}'] or lines[3]!='ENV PYTHONDONTWRITEBYTECODE=1':
        raise ValueError('Paper recipe changed; this adapter requires a reviewed translation')
    argv=shlex.split(lines[2].removeprefix('RUN '))
    if not lines[2].startswith('RUN ') or argv[:4]!=['python3','-m','pip','install'] or any(x in argv for x in ['&&',';','|']):
        raise ValueError('Only the current single pip-install recipe is supported')
    return argv


def prepare():
    directory=Path('.project');directory.mkdir(exist_ok=True)
    output=directory/'image.json'
    if output.exists():raise ValueError('Run-local image receipt already exists')
    digest=os.environ['TDK_CONTAINER_IMAGE_DIGEST']
    reference=os.environ['TDK_CONTAINER_IMAGE_REFERENCE']
    if reference!='docker.io/danteev/texlive:latest' or not re.fullmatch(r'sha256:[a-f0-9]{64}',digest):
        raise ValueError('Expected the freshly resolved paper job image')
    path=Path('scripts/ci/paper.Dockerfile')
    started=time.time()
    subprocess.run(recipe(path),check=True)
    output.write_text(json.dumps({'requested':reference,'manifest_digest':digest,
        'resolved':reference.rsplit(':',1)[0]+'@'+digest,
        'resolved_at':float(os.environ['TDK_CONTAINER_RESOLVED_AT']),
        'dockerfile_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'construction':'fresh OCI extraction plus the recorded pip recipe; no Docker image build',
        'platform':'linux/amd64','dependency_install_seconds':time.time()-started},indent=2)+'\n')


def check():
    output=Path('.project/checks');output.mkdir(parents=True,exist_ok=False)
    commands=[
        ('runtime',['python3','scripts/ci/runtime.py','snapshot','--component','paper','--image','.project/image.json','--out','.project/paper-runtime.json']),
        ('paper',['python3','scripts/project.py','check','--component','paper','--no-dependencies','--mode','ordinary','--report-dir','.project/checks/paper','--runtime','.project/paper-runtime.json']),
        ('review',['python3','scripts/ci/paper_evidence.py']),
    ]
    if json.loads(Path('project.json').read_text())['role']=='template':
        commands.append(('maintainer',['python3','scripts/ci/template.py','paper']))
    records=[]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    try:
        for name,argv in commands:
            start=time.time()
            record={'name':name,'started_at':start}
            try:
                with (output/(name+'.log')).open('w') as log:
                    result=subprocess.run(['unshare','--user','--map-root-user','--net','--',*argv],
                                          env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
                record['exit_code']=result.returncode
            except subprocess.TimeoutExpired:
                record.update(exit_code=124,error='timeout',timeout_seconds=1800)
            except OSError as error:
                record.update(exit_code=127,error=type(error).__name__)
            except BaseException as error:
                record.update(exit_code=130,error=type(error).__name__)
                raise
            finally:
                record.update(completed_at=time.time(),seconds=time.time()-start)
                records.append(record)
                print(json.dumps(record),flush=True)
            if record.get('error') or (name=='runtime' and record['exit_code']):break
    finally:
        stat=os.statvfs('.')
        (output/'bme-acceptance.json').write_text(json.dumps({'schema':'bme-paper-acceptance/v1',
            'runner_class':'bme-isolated-paper-v1','run_id':os.environ.get('GITHUB_RUN_ID'),
            'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'source_sha':os.environ.get('GITHUB_SHA'),
            'commands':records,'filesystem_bytes':stat.f_blocks*stat.f_frsize,
            'free_bytes_after_checks':stat.f_bavail*stat.f_frsize,
            'network':'new network namespace for each check command'},indent=2)+'\n')
    return int(any(record['exit_code'] for record in records))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','check'])
    args=parser.parse_args()
    if args.action=='prepare':prepare()
    else:raise SystemExit(check())
