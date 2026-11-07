#!/usr/bin/env python3
"""Run a manual acceptance job with local gh authority and a remote one-job sandbox.

The gh credential never leaves this trusted controller. Only JIT is sent over SSH.
"""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
import uuid


def api(path, data=None, method=None):
    cmd=['gh','api',path]
    if method: cmd += ['--method',method]
    if data is not None: cmd += ['--input','-']
    for attempt in range(3 if data is None and method is None else 1):
        result=subprocess.run(cmd,input=json.dumps(data) if data is not None else None,
                              text=True,capture_output=True,timeout=30)
        if result.returncode==0: break
        if attempt<2 and data is None and method is None: time.sleep(2)
    result.check_returncode()
    return json.loads(result.stdout) if result.stdout.strip() else None


def remote(host,action,identifier=None,seconds=600,data=None):
    argv=['sudo','/usr/local/lib/tdk-isolation/session.py',action]
    if identifier: argv += ['--id',identifier]
    if action=='start': argv += ['--seconds',str(seconds)]
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
                           '-o','ForwardAgent=no',host,shlex.join(argv)],
                          input=json.dumps(data) if data is not None else None,
                          text=True,capture_output=True,check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',default='ftsrg-bclab-tdk/tdk-runner-isolation-pilot')
    parser.add_argument('--host',default='bclab-runner')
    parser.add_argument('--mode',choices=['probe','container','cancel','timeout'],default='probe')
    parser.add_argument('--seconds',type=int,default=600)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',args.repo): raise ValueError('invalid repository')
    label='bme-isolation-'+uuid.uuid4().hex
    jit=api(f'repos/{args.repo}/actions/runners/generate-jitconfig',{
        'name':label,'runner_group_id':1,'labels':['bme-isolated-native-v1',label],'work_folder':'_work'},'POST')
    runner_id=jit['runner']['id'];session=None;run=None;report={'repo':args.repo,'runner_id':runner_id,'label':label,'mode':args.mode}
    try:
        session=remote(args.host,'start',seconds=args.seconds,data={
            'jit':jit['encoded_jit_config'],'repo':args.repo,'runner_id':runner_id,'label':label})
        del jit
        report['session']=session
        args.output.write_text(json.dumps(report,indent=2))
        api(f'repos/{args.repo}/actions/workflows/pilot.yml/dispatches',
            {'ref':'main','inputs':{'label':label,'mode':args.mode}},'POST')
        deadline=time.monotonic()+args.seconds+60
        while time.monotonic()<deadline:
            runs=api(f'repos/{args.repo}/actions/workflows/pilot.yml/runs?per_page=30')['workflow_runs']
            run=next((r for r in runs if r['display_title']==label),None)
            if run:
                if not report.get('url'):
                    report.update(url=run['html_url'],run_id=run['id']);print(run['html_url'],flush=True)
                    args.output.write_text(json.dumps(report,indent=2))
                fixture=remote(args.host,'status',session['id'])['acceptance_fixture']
                if fixture['ready']:
                    report['observed_ready_at']=time.time();report['fixture']=fixture
                    args.output.write_text(json.dumps(report,indent=2))
                if args.mode=='cancel' and fixture['ready'] and fixture['listener_stopped']:
                    api(f"repos/{args.repo}/actions/runs/{run['id']}/cancel",{},'POST')
                    report['cancel_requested_at']=time.time()
                    # Host stop does not depend on the listener cooperating with cancellation.
                    report['cancel_cleanup']=remote(args.host,'stop',session['id'])
                    report['cancel_cleaned_at']=time.time()
                    api(f"repos/{args.repo}/actions/runs/{run['id']}/force-cancel",{},'POST')
                    report['conclusion']='cancelled'
                    break
                if run['status']=='completed':
                    report['conclusion']=run['conclusion'];break
            state=remote(args.host,'status',session['id'])
            if state['ActiveState'] in ['inactive','failed']:
                report['host_finished']=state
                # A host timeout can leave a run in progress; cancel it explicitly.
                if run and run['status']!='completed':
                    api(f"repos/{args.repo}/actions/runs/{run['id']}/force-cancel",{},'POST')
                break
            time.sleep(5)
    finally:
        if session:
            try: report['cleanup']=remote(args.host,'stop',session['id'])
            except subprocess.CalledProcessError:
                report['cleanup_error']='SSH cleanup failed; independent host deadline/reaper remains active'
        try: api(f'repos/{args.repo}/actions/runners/{runner_id}',method='DELETE')
        except subprocess.CalledProcessError: pass  # GitHub deletes consumed JIT registrations.
        args.output.write_text(json.dumps(report,indent=2))
        print(json.dumps({k:v for k,v in report.items() if k not in ['session']},indent=2),flush=True)
    receipt=report.get('cleanup',{}).get('receipt') or {}
    if not all(receipt.get(key) for key in ('disk_removed','cgroup_removed','account_removed')):
        raise SystemExit('Host cleanup was not demonstrated')
    if report['mode']=='cancel' and not (report.get('fixture',{}).get('listener_stopped') and report.get('cancel_cleanup')):
        raise SystemExit('Cancellation did not exercise an uncooperative running payload')
    if report['mode']=='timeout' and not (report.get('fixture',{}).get('ready') and receipt.get('result')=='timeout'):
        raise SystemExit('Timeout enforcement on a started payload was not demonstrated')
    if report['mode'] in ['probe','container'] and report.get('conclusion')!='success':
        raise SystemExit('Acceptance workflow did not succeed')


if __name__=='__main__': main()
