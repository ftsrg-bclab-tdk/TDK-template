#!/usr/bin/env python3
"""Bounded real TLC/JVM/dispatcher acceptance, independent of student selection."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import project
from ci.config import load_project
from ci.runtime import snapshot
from ci.evidence import verify_report


def main():
    with tempfile.TemporaryDirectory(prefix='tdk-proof-acceptance-') as directory:
        root = Path(directory)
        shutil.copytree(ROOT / 'scripts', root / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT / 'proof', root / 'proof', ignore=shutil.ignore_patterns('.tools', 'results', '__pycache__'))
        config = json.loads((ROOT / 'project.json').read_text())
        for component in config['components'].values():
            component.update(enabled=False, profiles={})
        step = {'name': 'counter', 'kind': 'proof', 'argv': ['python3', 'tlc.py', 'check', '--model', 'examples/tlc/Counter.tla', '--config', 'examples/tlc/Counter.cfg', '--output', 'results/counter.json'],
                'timeout': 90, 'result_file': 'results/counter.json',
                'outputs': ['results/counter.json', 'results/counter.json.logs/Counter.stdout', 'results/counter.json.logs/Counter.stderr'],
                'allow_empty_outputs': ['results/counter.json.logs/Counter.stderr']}
        smoke = {'name': 'smoke', 'kind': 'tests', 'argv': ['python3', 'tlc.py', 'smoke', '--output', 'results/smoke.json'],
                 'timeout': 90, 'result_file': 'results/smoke.json', 'outputs': ['results/smoke.json']}
        config['components']['proof'].update(enabled=True, depends_on=[], profiles={'ordinary': [step, smoke]})
        (root / 'project.json').write_text(json.dumps(config))
        (root / '.gitignore').write_text('.project/\nproof/results/\nproof/.tools/\n__pycache__/\n')
        for args in (['init', '-q'], ['add', '.'], ['-c', 'user.email=acceptance@example.invalid', '-c', 'user.name=Acceptance', 'commit', '-qm', 'fixture']):
            subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
        config, sha = load_project(root)
        args = argparse.Namespace(head=None, base=None, scope='all', component=None, mode='ordinary', profile=None, draft=False)
        plan = project.make_plan(root, config, sha, args)
        runtime = snapshot(root, 'project.json', 'proof')
        report = project.check(root, config, sha, plan, root / '.project/checks', runtime)
        assert report['gate_outcome'] == 'pass', report
        assert report['acceptance_eligible'], report
        verify_report(root / '.project/checks/report.json', repository=config['repository'],
                      tested_sha=plan['source']['tested_sha'], config_sha256=sha, required_components=['proof'])
        positive = json.loads((root / 'proof/results/counter.json').read_text())
        smoke_result = json.loads((root / 'proof/results/smoke.json').read_text())
        assert positive['outcome'] == 'verified'
        assert [r['outcome'] for r in smoke_result['examples']] == ['verified', 'violated']
        for result in [positive, *smoke_result['examples']]:
            assert result['runtime'] == runtime['proof_tools'], 'Commands did not reuse identical TLC/JVM resolution'
        assert (root / 'proof/results/counter.json.logs/Counter.stderr').stat().st_size == 0
        # Exercise TLC's distinct initial-state invariant diagnostic through the adapter.
        model = root / 'proof/examples/tlc/Counter.tla'
        model.write_text(model.read_text().replace('Init == value = 0', 'Init == value = Limit + 1'))
        negative = dict(step, name='initial', argv=[a.replace('results/counter.json', 'results/initial.json') for a in step['argv']],
                        result_file='results/initial.json', outputs=['results/initial.json'], allow_empty_outputs=[])
        result = project.run_check(root, config['components']['proof'], negative, root / '.project/initial', False, runtime=runtime)
        assert result['gate_outcome'] == 'fail', result
        assert json.loads((root / 'proof/results/initial.json').read_text())['outcome'] == 'violated', (root / 'proof/results/initial.json.logs/Counter.stdout').read_text()
        print('PASS: real positive/negative/initial-state TLC, empty stderr, shared resolution, dispatcher acceptance')


if __name__ == '__main__':
    main()
