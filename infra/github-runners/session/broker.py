#!/usr/bin/env python3
"""Allowlisted GitHub queue admission; administrative authority never enters a job."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time
import urllib.error
import urllib.request
import uuid


class APIError(RuntimeError):
    def __init__(self, status):
        super().__init__('GitHub API status '+str(status))
        self.status=status


class GitHub:
    def __init__(self, credential=None):
        self.credential=credential

    def request(self, path, method='GET', data=None):
        if self.credential is None:
            cmd=['gh','api',path,'--method',method]
            if data is not None:cmd += ['--input','-']
            result=subprocess.run(cmd,input=json.dumps(data) if data is not None else None,
                                  text=True,capture_output=True,timeout=40)
            if result.returncode:
                match=re.search(r'HTTP (\d{3})',result.stderr)
                raise APIError(int(match[1]) if match else 0)
            return json.loads(result.stdout) if result.stdout.strip() else None
        token=self.credential.read_text().strip()
        request=urllib.request.Request('https://api.github.com/'+path,method=method,
            data=json.dumps(data).encode() if data is not None else None,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                     'X-GitHub-Api-Version':'2022-11-28','User-Agent':'tdk-bme-runner-broker',
                     'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=30) as response:
                body=response.read();return json.loads(body) if body else None
        except urllib.error.HTTPError as error:raise APIError(error.code) from None

    def pages(self, path, key):
        values=[]
        for page in range(1,6):
            separator='&' if '?' in path else '?'
            result=self.request(path+separator+f'per_page=100&page={page}')[key]
            values.extend(result)
            if len(result)<100:return values
        # Do not silently act on a truncated inventory.
        raise RuntimeError('GitHub inventory exceeded the configured bound')


class Engine:
    def __init__(self, host=None):self.host=host

    def call(self, action, identifier=None, data=None, seconds=2700, disk_gib=8):
        cmd=['/usr/local/lib/tdk-isolation/session.py',action]
        if identifier:cmd += ['--id',identifier]
        if action=='start':cmd += ['--seconds',str(seconds),'--disk-gib',str(disk_gib)]
        if self.host:
            cmd=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ForwardAgent=no',
                 self.host,shlex.join(['sudo',*cmd])]
        result=subprocess.run(cmd,input=json.dumps(data) if data is not None else None,
                              text=True,capture_output=True,timeout=1350 if action=='start' else 45)
        if result.returncode:raise RuntimeError('Host lifecycle operation failed: '+action)
        return json.loads(result.stdout) if result.stdout.strip() else None


def atomic_json(path, value):
    tmp=path.with_name(path.name+'.new')
    with tmp.open('w') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    tmp.replace(path)


def configuration(path):
    value=json.loads(path.read_text())
    if not value.get('repositories') or any(not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',r) for r in value['repositories']):
        raise ValueError('Explicit repository allowlist required')
    if not re.fullmatch(r'[a-z0-9-]{1,32}',value['controller_id']):raise ValueError('Invalid controller ID')
    if not 1<=value.get('max_sessions',2)<=2:raise ValueError('Invalid admission bound')
    if not 60<=value.get('deadline_seconds',2700)<=7200:raise ValueError('Invalid job deadline')
    return value


class Broker:
    def __init__(self, config, state_path, github, engine):
        self.config=config;self.path=state_path;self.github=github;self.engine=engine
        self.state=json.loads(state_path.read_text()) if state_path.exists() else {'sessions':{},'completed':[]}
        self.prefix='bme-auto-'+config['controller_id']+'-'
        self.profiles=config.get('profiles',{config.get('label','bme-isolated-native-v1'):8})
        if any(disk not in (8,20) for disk in self.profiles.values()):raise ValueError('unsupported disk class')
        self.labels=['self-hosted','Linux','X64']

    def save(self):atomic_json(self.path,self.state)

    def emit(self,event,**fields):print(json.dumps({'event':event,'time':time.time(),**fields}),flush=True)

    def eligible(self,job):
        labels={x.lower() for x in job.get('labels',[])}
        selected=labels & set(self.profiles)
        return job['status']=='queued' and len(selected)==1 and labels<=set(x.lower() for x in self.labels)|selected

    def profile(self,job):
        return next(label.lower() for label in job['labels'] if label.lower() in self.profiles)

    def inventory(self,repo):
        runs={}
        for state in ['queued','in_progress']:
            for run in self.github.pages(f'repos/{repo}/actions/runs?status={state}','workflow_runs'):
                runs[run['id']]=run
        jobs=[]
        for run in runs.values():
            jobs.extend(self.github.pages(f"repos/{repo}/actions/runs/{run['id']}/jobs?filter=latest",'jobs'))
        return jobs

    def remove_registration(self,entry):
        if entry.get('runner_id'):
            try:self.github.request(f"repos/{entry['repo']}/actions/runners/{entry['runner_id']}",'DELETE')
            except APIError as error:
                if error.status!=404:raise

    def finish(self,name,entry):
        if entry.get('session_id'):
            result=self.engine.call('stop',entry['session_id'])
            receipt=result.get('receipt') or {}
            if not all(receipt.get(k) for k in ('disk_removed','cgroup_removed','account_removed')):
                raise RuntimeError('Host cleanup has not completed')
            entry['receipt']=receipt
        self.remove_registration(entry)
        self.state['completed'].append({**entry,'name':name,'reconciled_at':time.time()})
        self.state['completed']=self.state['completed'][-100:]
        del self.state['sessions'][name];self.save()
        self.emit('session_removed',name=name,repo=entry['repo'])

    def tick(self):
        host_sessions=self.engine.call('list')
        # Reconcile root-owned sessions before admitting any new work. This also
        # recovers a crash after host start but before the response was journaled.
        for session in host_sessions:
            name=session['label']
            if name.startswith(self.prefix) and session['repo'] in self.config['repositories']:
                entry=self.state['sessions'].setdefault(name,{'repo':session['repo'],'created_at':session['started_at']})
                entry.update(runner_id=session['runner_id'],session_id=session['id'],disk_gib=session.get('disk_gib',8))
                entry.setdefault('profile',next((p for p,d in self.profiles.items() if d==entry['disk_gib']),None))
        self.save()
        jobs={repo:self.inventory(repo) for repo in self.config['repositories']}
        registrations={repo:self.github.pages(f'repos/{repo}/actions/runners','runners') for repo in jobs}
        for name,entry in list(self.state['sessions'].items()):
            repo=entry['repo']
            # Pending API writes are journaled by name before the request. An
            # ambiguous response is reconciled, never blindly repeated.
            if not entry.get('runner_id'):
                match=next((r for r in registrations[repo] if r['name']==name),None)
                if match:entry['runner_id']=match['id']
            if not entry.get('session_id'):
                self.finish(name,entry);continue
            if not any(s['id']==entry['session_id'] for s in host_sessions):
                # The request may still be in transit, or preparation may have
                # died. Root must tombstone this ID before its slot is freed.
                self.finish(name,entry);continue
            assigned=next((j for j in jobs[repo] if j.get('runner_id')==entry['runner_id']),None)
            if assigned:entry['job_id']=assigned['id'];entry['run_id']=assigned['run_id'];self.save()
            if entry.get('job_id'):
                job=self.github.request(f"repos/{repo}/actions/jobs/{entry['job_id']}")
                run=self.github.request(f"repos/{repo}/actions/runs/{job['run_id']}")
                if job['status']=='completed' or run['status']=='completed':
                    self.finish(name,entry);continue
            status=self.engine.call('status',entry['session_id'])
            if status.get('phase')=='preparing':
                # Root retains the reservation and a preparation deadline. Do
                # not apply the idle-listener timeout before a listener exists.
                continue
            if status['ActiveState'] in ['inactive','failed']:
                self.finish(name,entry);continue
            runner=next((r for r in registrations[repo] if r['id']==entry['runner_id']),None)
            if runner is None:
                self.finish(name,entry);continue
            if not entry.get('job_id') and not (runner or {}).get('busy') and time.time()-entry['created_at']>180:
                self.finish(name,entry)
        self.save()
        for repo,items in jobs.items():
            queued=[job for job in items if self.eligible(job)]
            idle={profile:sum(e['repo']==repo and e.get('profile',next(iter(self.profiles)))==profile and not e.get('job_id') for e in self.state['sessions'].values()) for profile in self.profiles}
            for job in queued:
                profile=self.profile(job)
                if idle[profile]:
                    idle[profile]-=1;continue
                if len(self.state['sessions'])>=self.config.get('max_sessions',2):return
                used=sum(e.get('disk_gib',self.profiles.get(e.get('profile'),8)) for e in self.state['sessions'].values())
                if used+self.profiles[profile]>self.config.get('disk_budget_gib',20):continue
                name=self.prefix+uuid.uuid4().hex
                entry={'repo':repo,'created_at':time.time(),'queued_job_id':job['id'],'profile':profile,'disk_gib':self.profiles[profile]}
                self.state['sessions'][name]=entry;self.save()
                jit=self.github.request(f'repos/{repo}/actions/runners/generate-jitconfig','POST',{
                    'name':name,'runner_group_id':self.config.get('runner_group_id',1),
                    'labels':self.labels+[profile,name],'work_folder':'_work'})
                # Persist the host operation identity before sending any start.
                # A lost response must be reconciled/cancelled using this ID.
                entry['runner_id']=jit['runner']['id'];entry['session_id']=uuid.uuid4().hex;self.save()
                session=self.engine.call('start',entry['session_id'],data={'jit':jit['encoded_jit_config'],'repo':repo,
                    'runner_id':entry['runner_id'],'label':name},seconds=self.config.get('deadline_seconds',2700),disk_gib=self.profiles[profile])
                if session['id']!=entry['session_id']:
                    raise RuntimeError('Host returned a different operation identity')
                self.save()
                self.emit('session_started',name=name,repo=repo,queued_job_id=job['id'],session_id=session['id'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--host',help='SSH lifecycle transport for an external trusted controller')
    parser.add_argument('--credential',type=Path,help='Private token file; omitted only for local gh authentication')
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args();os.umask(0o077)
    args.state.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    lock=args.state.with_suffix('.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    config=configuration(args.config)
    broker=Broker(config,args.state,GitHub(args.credential),Engine(args.host))
    while True:
        try:broker.tick()
        except Exception as error:
            # Never log API response bodies, tokens, JIT blobs or job-controlled names.
            broker.emit('reconcile_failed',error=type(error).__name__,status=getattr(error,'status',None))
            if args.once:raise SystemExit(1) from None
        if args.once:break
        time.sleep(config.get('poll_seconds',20))


if __name__=='__main__':main()
