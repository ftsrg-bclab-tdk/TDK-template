#!/usr/bin/env python3
"""Root-only integration checks on the BME host. Creates only named test units/files."""
import json
import os
from pathlib import Path
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import uuid

SANDBOX = '/usr/local/lib/tdk-native/sandbox.py'
SERVICE = 'actions.runner.ftsrg-bclab-tdk.bme-cloud-29136.service'
checks = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)
    print('PASS ' + name, flush=True)


def unit():
    return 'tdk-sandbox-' + uuid.uuid4().hex


def args(code, name, seconds=30, memory='1G'):
    return [SANDBOX, '--unit', name, '--seconds', str(seconds), '--memory', memory,
            '--', '/usr/bin/python3', '-u', '-c', code]


def invoke(code, seconds=30, memory='1G'):
    name = unit()
    result = subprocess.run(args(code, name, seconds, memory), capture_output=True,
                            text=True, timeout=seconds + 15)
    return name, result


def gone(name):
    return not Path('/sys/fs/cgroup/system.slice/' + name + '.service').exists()


def wait_until(fn, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if fn():
            return
        time.sleep(.1)
    raise AssertionError('deadline waiting for test fixture')


def main():
    if os.geteuid() != 0:
        raise RuntimeError('sudo required')
    with tempfile.TemporaryDirectory(prefix='tdk-isolation-') as tmp:
        tmp = Path(tmp)
        secret = tmp / 'credential-canary'
        secret.write_text('HOST_CANARY_' + uuid.uuid4().hex)
        secret.chmod(0o600)
        host = socket.socket()
        host.bind(('127.0.0.1', 0))
        host.listen()
        port = host.getsockname()[1]
        first = unit()
        log = tmp / 'first.log'
        # A second independent sandbox must not see these files, processes or socket.
        code = f'''import os,socket,time
open('/work/cross-job-marker','w').write('first')
open('/tmp/cross-job-marker','w').write('first')
s=socket.socket(); s.bind(('127.0.0.1',{port})); s.listen()
print('READY',flush=True)
time.sleep(60)
'''
        with log.open('w') as output:
            proc = subprocess.Popen(args(code, first, 30), stdout=output, stderr=output)
        try:
            wait_until(lambda: 'READY' in log.read_text())
            cgroup = Path('/sys/fs/cgroup/system.slice/' + first + '.service')
            host_pids = [int(x) for x in (cgroup / 'cgroup.procs').read_text().split()]
            host_uids = {int(next(line for line in Path('/proc',str(pid),'status').read_text().splitlines() if line.startswith('Uid:')).split()[1]) for pid in host_pids}
            check('job uses unprivileged host UID', 0 not in host_uids)
            probe = '''import json,os,pathlib,socket,subprocess
assert not pathlib.Path('/work/cross-job-marker').exists()
assert not pathlib.Path('/tmp/cross-job-marker').exists()
for p in HOST_PATHS:
    assert not pathlib.Path(p).exists(),p
for pid in HOST_PIDS:
    assert not pathlib.Path('/proc/'+str(pid)).exists(),pid
assert os.getuid()!=0
status=pathlib.Path('/proc/self/status').read_text()
assert 'CapEff:\\t0000000000000000' in status
assert 'NoNewPrivs:\\t1' in status
assert 'GH_TOKEN' not in os.environ
assert subprocess.run(['/usr/bin/unshare','-Ur','true'],capture_output=True).returncode!=0
assert subprocess.run(['/usr/bin/mount','-t','tmpfs','tmpfs','/work'],capture_output=True).returncode!=0
try:
    pathlib.Path('/usr/SHOULD_NOT_EXIST').write_text('bad')
    raise AssertionError('host /usr writable')
except OSError: pass
for family,target in TARGETS:
    sock=socket.socket(family);sock.settimeout(.5)
    try:
        sock.connect(target)
        raise AssertionError('unexpected network access '+str(target))
    except OSError: pass
    finally: sock.close()
print(json.dumps({'uid':os.getuid(),'pid':os.getpid(),'network':'denied'}))
'''
            preamble = 'HOST_PATHS=' + repr([str(secret), '/home/cloud/.ssh',
                '/home/cloud/actions-runner/.credentials', '/var/lib/tdk-ci/.credentials',
                '/run/docker.sock', '/run/dbus/system_bus_socket', '/etc/shadow']) + '\n'
            preamble += 'HOST_PIDS=' + repr(host_pids + [os.getpid()]) + '\n'
            preamble += 'TARGETS=' + repr([(socket.AF_INET, ('127.0.0.1', port)),
                (socket.AF_INET, ('10.9.0.25', 22)), (socket.AF_INET, ('169.254.169.254', 80)),
                (socket.AF_INET, ('1.1.1.1', 443)), (socket.AF_INET6, ('::1', port)),
                (socket.AF_INET6, ('2606:4700:4700::1111', 443))]).replace('<AddressFamily.AF_INET: 2>', '2').replace('<AddressFamily.AF_INET6: 10>', '10') + '\n'
            os.environ['GH_TOKEN'] = 'TEST_CANARY_NOT_A_CREDENTIAL'
            second, result = invoke(preamble + probe)
            os.environ.pop('GH_TOKEN')
            check('concurrent filesystem/process/credential/network/privilege probes',
                  result.returncode == 0)
            check('second job cgroup removed', gone(second))
            check('host credential canary unchanged', secret.read_text().startswith('HOST_CANARY_'))
        finally:
            subprocess.run(['systemctl', 'stop', first], check=False, capture_output=True)
            proc.wait(timeout=10)
            host.close()
        check('cancelled job cgroup removed', gone(first))
        # Background children cannot persist after the main command exits.
        name, result = invoke("import subprocess; subprocess.Popen(['/bin/sleep','600'],start_new_session=True); print('spawned')")
        check('background child cleanup after normal exit', result.returncode == 0 and gone(name))
        name, result = invoke('import time; time.sleep(30)', seconds=2)
        check('host-enforced timeout and cleanup', result.returncode != 0 and gone(name))
        name, result = invoke("a=bytearray(256*1024*1024); print('unexpected')", memory='64M')
        check('host-enforced memory limit and cleanup', result.returncode != 0 and gone(name))
        # SIGKILL bypasses helper finally; the systemd deadline must still work.
        name = unit()
        with (tmp / 'killed-controller.log').open('w') as output:
            proc = subprocess.Popen(args('import time; print("READY",flush=True); time.sleep(60)', name, 3),
                                    stdout=output, stderr=output)
        wait_until(lambda: 'READY' in (tmp / 'killed-controller.log').read_text())
        proc.kill(); proc.wait(timeout=5)
        wait_until(lambda: gone(name), seconds=10)
        check('cleanup survives controller SIGKILL', gone(name))

        # Enter the live service mount namespace, then drop to the SAME UID and
        # privilege state. No payload is injected into the running listener.
        pid = subprocess.check_output(['systemctl','show',SERVICE,'-p','MainPID','--value'],text=True).strip()
        import pwd
        user = pwd.getpwnam('tdk-ci')
        code = '''import pathlib,subprocess
for p in ['/home/cloud/.ssh', '/home/cloud/actions-runner/.credentials']:
 try:
  assert not pathlib.Path(p).exists()
 except PermissionError: pass
assert subprocess.run(['sudo','-n','true'],capture_output=True).returncode != 0
try:
 pathlib.Path('/etc/tdk-test-must-not-write').write_text('bad')
 raise AssertionError('host /etc writable')
except OSError: pass
print('trusted service privilege/filesystem restrictions hold')
'''
        result = subprocess.run(['nsenter','--target',pid,'--mount','--',
            'setpriv',f'--reuid={user.pw_uid}',f'--regid={user.pw_gid}','--clear-groups',
            '--no-new-privs','--bounding-set=-all','/usr/bin/python3','-c',code],capture_output=True,text=True)
        if result.returncode: print(result.stderr,flush=True)
        check('live service mount restrictions and no sudo', result.returncode == 0)
        check('live runner still active', subprocess.run(['systemctl','is-active','--quiet',SERVICE]).returncode == 0)
        # UID-scoped firewall applies in every mount namespace, including the live runner.
        network = '''import socket,urllib.request
assert urllib.request.urlopen('https://github.com',timeout=10).status==200
for host,port in [('127.0.0.1',22),('10.9.0.25',22),('169.254.169.254',80),('1.1.1.1',80)]:
 s=socket.socket();s.settimeout(1)
 try:
  s.connect((host,port));raise AssertionError('forbidden destination reachable')
 except OSError: pass
 finally:s.close()
'''
        result = subprocess.run(['runuser','-u','tdk-ci','--','python3','-c',network],capture_output=True,text=True)
        check('trusted runner HTTPS works; host/private/metadata/plain HTTP denied', result.returncode == 0)

        workload = "import hashlib; b=b'x'*1048576; [hashlib.sha256(b).digest() for _ in range(500)]"
        native, isolated = [], []
        for _ in range(3):
            start=time.monotonic(); subprocess.run(['/usr/bin/python3','-c',workload],check=True); native.append(time.monotonic()-start)
            start=time.monotonic(); _,result=invoke(workload); isolated.append(time.monotonic()-start)
            check('native compute completed in sandbox', result.returncode == 0)
        print(json.dumps({'checks': checks, 'native_seconds':native,'sandbox_seconds':isolated,
            'median_total_overhead_seconds':statistics.median(isolated)-statistics.median(native),
            'note':'3 small samples, includes process/service setup; not a CI throughput benchmark'},indent=2))


if __name__ == '__main__':
    main()
