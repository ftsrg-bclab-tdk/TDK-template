"""Synthetic signed fixtures test validation; they are not native pilot evidence."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci.evidence import canonical_digest
from onboarding.checks import ingest
from overleaf.boundary import NAMESPACE, VerifiedBoundary, verify_boundary


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key = self.root/'observer'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(self.key)], check=True)
        self.trust = self.root/'allowed'
        self.trust.write_text('fixture-observer ' + self.key.with_suffix('.pub').read_text())
        self.sha, self.digest = 'b'*40, 'c'*64
        source = {'repository': 'org/pilot', 'source_sha': self.sha, 'tested_sha': self.sha, 'dirty': False}
        config = {'project_config_sha256': self.digest}
        plan = {'source': source, 'configuration': dict(config), 'draft': False,
                'components': {'paper': {'selected': True}}}
        config['dependency_plan_sha256'] = canonical_digest(plan)
        runtime = {'schema': 'runtime-resolution/v1', 'source_sha': self.sha, 'project_config_sha256': self.digest,
                   'components': ['paper'],
                   'tools': {name: 'synthetic fixture version' for name in ('python', 'git', 'tex', 'latexmk', 'inkscape', 'pdfinfo', 'python_packages')}}
        self.report = {'schema': 'project-checks/v1', 'source': source, 'source_after': dict(source), 'configuration': config,
                       'execution': {'started_at': '2026-01-01T00:04:00Z', 'completed_at': '2026-01-01T00:05:00Z',
                                     'actor': 'fixture', 'method': 'test-only', 'log_reference': 'log.txt'},
                       'plan': plan, 'gate_outcome': 'pass', 'runtime': runtime, 'runtime_sha256': canonical_digest(runtime),
                       'components': {'paper': {'execution_status': 'completed', 'gate_outcome': 'pass', 'outcome': 'pass',
                                               'checks': [{'execution_status': 'completed', 'gate_outcome': 'pass'}]}},
                       'files': [{'path': 'log.txt', 'bytes': 7, 'sha256': hashlib.sha256(b'fixture').hexdigest()}]}
        self.artifact('log.txt', b'fixture')
        proof = self.artifact('observation.txt', b'SYNTHETIC UNIT TEST ONLY')
        audit = {'before_commit': 'a'*40, 'after_commit': self.sha, 'unexpected_changes': [], 'changes': [],
                 'inventory': {'tracked_files': 1, 'payload_bytes': 1, 'text_bytes': 1, 'largest_text_bytes': 1,
                               'executables': [], 'symlinks': [], 'gitlinks': [], 'lfs_pointers': []}}
        audit['before_inventory'] = copy.deepcopy(audit['inventory'])
        self.receipt = {'schema': 'overleaf-native-pilot/v1', 'method': 'observed_native_ui', 'actor': 'fixture-observer',
                        'repository': 'org/pilot', 'overleaf_project_id': 'd'*24, 'source_sha': 'a'*40,
                        'tested_sha': self.sha, 'config_digest': self.digest, 'completed_at': '2026-01-01T00:03:00Z',
                        'pull': {'commit': 'a'*40, 'completed_at': '2026-01-01T00:01:00Z', 'evidence': proof},
                        'push': {'commit': self.sha, 'completed_at': '2026-01-01T00:02:00Z', 'evidence': proof},
                        'clone': {'commit': self.sha, 'completed_at': '2026-01-01T00:03:00Z', 'evidence': proof},
                        'compilation': {'paper-draft.tex': proof, 'paper-final.tex': proof},
                        'tree_audit': self.artifact('audit.json', json.dumps(audit).encode()),
                        'report': self.artifact('report.json', json.dumps(self.report).encode())}

    def artifact(self, path, raw):
        (self.root/path).write_bytes(raw)
        return {'path': path, 'sha256': hashlib.sha256(raw).hexdigest()}

    def sign(self):
        path = self.root/'receipt.json'
        path.write_text(json.dumps(self.receipt))
        path.with_suffix('.json.sig').unlink(missing_ok=True)
        subprocess.run(['ssh-keygen', '-Y', 'sign', '-f', str(self.key), '-n', NAMESPACE, str(path)],
                       check=True, capture_output=True)

    def verify(self, **overrides):
        args = dict(allowed_signers=self.trust, principal='fixture-observer', repository='org/pilot',
                    tested_sha=self.sha, config_digest=self.digest, required_components=['paper'])
        args.update(overrides)
        return verify_boundary(self.root/'receipt.json', self.root/'receipt.json.sig', **args)

    def test_signed_bundle_and_ingestion(self):
        self.sign()
        boundary = self.verify()
        config = {'repository': 'org/pilot', 'components': {'paper': {'enabled': True}}}
        result = ingest(self.root/'report.json', config, self.digest, self.sha, verified_boundary=boundary)
        self.assertEqual(result['roundtrip_and_clone'], 'trusted_observer_verified')
        self.assertFalse(result['onboarding_ready'])
        self.report['execution']['actor'] = 'another'
        (self.root/'report.json').write_text(json.dumps(self.report))
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            ingest(self.root/'report.json', config, self.digest, self.sha, verified_boundary=boundary)

    def test_signed_postrun_identity_and_future_completion_rejected(self):
        original = copy.deepcopy(self.report)
        for key, value in (("tested_sha", "e" * 40), ("source_sha", "e" * 40), ("repository", "other/repository")):
            self.report = copy.deepcopy(original)
            self.report["source_after"][key] = value
            self.receipt["report"] = self.artifact("report.json", json.dumps(self.report).encode())
            self.sign()
            with self.assertRaisesRegex(ValueError, "Post-run"):
                self.verify()
        self.report = copy.deepcopy(original)
        self.report["execution"]["completed_at"] = "2999-01-01T00:00:00Z"
        self.receipt["report"] = self.artifact("report.json", json.dumps(self.report).encode())
        self.sign()
        with self.assertRaisesRegex(ValueError, "interval"):
            self.verify()

    def test_no_dict_or_direct_constructor_authority(self):
        for value in ({}, {'completed_at': '2026-01-01T00:03:00Z'}):
            with self.assertRaisesRegex(ValueError, 'not local JSON'):
                ingest('absent', {'components': {}}, self.digest, self.sha, verified_boundary=value)
        with self.assertRaises(ValueError):
            VerifiedBoundary()

    def test_signature_identity_and_tampering(self):
        self.sign()
        with self.assertRaises(ValueError):
            self.verify(principal='someone-else')
        (self.root/'receipt.json').write_text(json.dumps(dict(self.receipt, actor='forged')))
        with self.assertRaisesRegex(ValueError, 'signature'):
            self.verify()
        self.sign()
        (self.root/'observation.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'modified'):
            self.verify()

    def test_symlink_and_unsigned_input_fail(self):
        self.sign()
        (self.root/'observation.txt').unlink()
        (self.root/'observation.txt').symlink_to('log.txt')
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            self.verify()
        (self.root/'receipt.json.sig').write_text('unsigned')
        with self.assertRaisesRegex(ValueError, 'signature'):
            self.verify()

    def test_signed_manual_stale_and_missing_checks_fail(self):
        original = copy.deepcopy(self.receipt)
        for field, value in [('method', 'manual_attestation'), ('tested_sha', 'e'*40),
                             ('config_digest', 'e'*64), ('repository', 'org/other'),
                             ('completed_at', '2026-01-01T00:06:00Z')]:
            self.receipt = dict(original, **{field: value})
            self.sign()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify()
        self.receipt = original
        self.sign()
        with self.assertRaises(ValueError):
            self.verify(required_components=['paper', 'code'])

    def test_traversal_symlink_and_unresolved_modes_fail(self):
        for path in ['../outside', '/tmp/outside']:
            self.receipt['pull']['evidence']['path'] = path
            self.sign()
            with self.assertRaises(ValueError):
                self.verify()
        self.receipt['pull']['evidence']['path'] = 'observation.txt'
        audit = json.loads((self.root/'audit.json').read_text())
        audit['unexpected_changes'] = ['code/run mode reset breaks subprocess']
        self.receipt['tree_audit'] = self.artifact('audit.json', json.dumps(audit).encode())
        self.sign()
        with self.assertRaisesRegex(ValueError, 'Unresolved'):
            self.verify()
