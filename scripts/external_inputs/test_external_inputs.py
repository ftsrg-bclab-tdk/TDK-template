import copy
import base64
import os
from unittest.mock import patch
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

import external_inputs as x


class Client:
    def __init__(self, receipt, archive):
        self.receipt, self.archive = receipt, archive
        self.immutable = True
        self.repo_id = 1
        self.unavailable = False

    def metadata(self, path):
        if self.unavailable:
            raise x.Unavailable('fixture outage')
        if '/releases/' not in path:
            return {'id': self.repo_id}
        return {'id': 2, 'tag_name': 'external-inputs/faculty/test', 'draft': False,
                'immutable': self.immutable,
                'assets': [{'id': 3, 'size': len(self.archive),
                            'digest': 'sha256:' + self.receipt['package_sha256']}]}

    def download(self, path, target, limit):
        Path(target).write_bytes(self.archive)


class Packages(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.body = b'%PDF-1.4\nfixture rubric\n'
        self.archive = self.zip_bytes('references/rubric.pdf', self.body)
        self.manifest = self.root / 'source-manifest.json'
        self.manifest.write_bytes(b'{"source":"fixture"}\n')
        self.r = {'schema': 'external-inputs/v1', 'manifest_sha256': x.hashfile(self.manifest),
                  'package_sha256': x.digest(self.archive),
                  'files': [{'path': 'references/rubric.pdf', 'sha256': x.digest(self.body),
                             'size': len(self.body)}],
                  'provenance': {'publisher': 'Fixture', 'source': 'https://example.invalid/ref',
                                 'retrieved_at': '2026-11-03', 'applicability': '2026'},
                  'acceptance': {'status': 'accepted', 'evidence': 'fixture acceptance'},
                  'license': 'fixture permission', 'redistribution': True, 'access': 'restricted'}
        self.receipt = self.root / 'receipt.json'
        self.receipt.write_text(json.dumps(self.r))
        self.receipt_hash = x.hashfile(self.receipt)
        self.d = {'schema': 'external-inputs-delivery/v1',
                  'receipt_sha256': self.receipt_hash, 'package_sha256': self.r['package_sha256'],
                  'repository': 'owner/project', 'repository_id': 1, 'release_id': 2,
                  'tag': 'external-inputs/faculty/test', 'asset_id': 3, 'size': len(self.archive)}
        self.zip = self.root / 'input.zip'
        self.zip.write_bytes(self.archive)
        self.client = Client(self.r, self.archive)

    @staticmethod
    def zip_bytes(name, body, mode=None):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            info = zipfile.ZipInfo(name)
            if mode is not None:
                info.create_system = 3
                info.external_attr = mode << 16
            z.writestr(info, body)
        return buf.getvalue()

    def test_valid_materialization(self):
        x.validate_receipt(self.r)
        x.validate_delivery(self.d, self.r, self.receipt_hash)
        out = self.root / 'materialized'
        x.materialize(self.zip, self.r, out)
        self.assertEqual((out / 'references/rubric.pdf').read_bytes(), self.body)

    def test_no_overwrite_existing_student_work(self):
        out = self.root / 'existing'
        out.mkdir()
        (out / 'student.tex').write_text('keep')
        with self.assertRaises(x.Invalid):
            x.materialize(self.zip, self.r, out)
        self.assertEqual((out / 'student.tex').read_text(), 'keep')

    def test_receipt_digest_and_duplicate_json(self):
        with self.assertRaises(x.Invalid):
            x.read_json(self.receipt, '0' * 64)
        self.receipt.write_text('{"x":1,"x":2}')
        with self.assertRaises(x.Invalid):
            x.read_json(self.receipt)

    def test_rejects_unknown_fields_empty_inventory_and_unaccepted_receipts(self):
        variants = []
        r = copy.deepcopy(self.r); r['surprise'] = 1; variants.append(r)
        r = copy.deepcopy(self.r); r['files'] = []; variants.append(r)
        r = copy.deepcopy(self.r); r['acceptance']['status'] = 'candidate'; variants.append(r)
        for r in variants:
            with self.subTest(receipt=r), self.assertRaises(x.Invalid):
                x.validate_receipt(r)

    def test_missing_provenance_rejected(self):
        del self.r['provenance']['retrieved_at']
        with self.assertRaises(x.Invalid):
            x.validate_receipt(self.r)

    def test_traversal_and_case_collision(self):
        for path in ('../escape', '/absolute', 'x/../escape', 'a//b', 'C:\\escape'):
            r = copy.deepcopy(self.r); r['files'][0]['path'] = path
            with self.subTest(path=path), self.assertRaises(x.Invalid):
                x.validate_receipt(r)
        r = copy.deepcopy(self.r)
        r['files'].append({**r['files'][0], 'path': 'References/RUBRIC.pdf'})
        with self.assertRaises(x.Invalid):
            x.validate_receipt(r)

    def test_archive_and_member_tamper_fail(self):
        self.zip.write_bytes(self.archive + b'tamper')
        with self.assertRaises(x.Invalid):
            x.verify_archive(self.zip, self.r)
        self.zip.write_bytes(self.archive)
        self.r['files'][0]['sha256'] = 'b' * 64
        with self.assertRaises(x.Invalid):
            x.verify_archive(self.zip, self.r)

    def test_symlink_archive_fails_even_if_accepted_hash_matches(self):
        for mode in (stat.S_IFLNK | 0o777,):
            archive = self.zip_bytes('references/rubric.pdf', self.body, mode)
            self.zip.write_bytes(archive)
            r = {**self.r, 'package_sha256': x.digest(archive)}
            with self.subTest(mode=mode), self.assertRaises(x.Invalid):
                x.verify_archive(self.zip, r)

    def test_extra_inventory_member_fails(self):
        archive = self.zip_bytes('secret.txt', self.body)
        self.zip.write_bytes(archive)
        r = {**self.r, 'package_sha256': x.digest(archive)}
        with self.assertRaises(x.Invalid):
            x.verify_archive(self.zip, r)

    def test_fetch_then_outage_reuses_exact_accepted_bytes(self):
        cache = self.root / 'cache'
        path, outcome, problem = x.fetch(self.r, self.d, cache, self.client)
        self.assertEqual(outcome, 'downloaded_accepted')
        self.assertIsNone(problem)
        self.assertEqual(path.read_bytes(), self.archive)
        self.client.unavailable = True
        path, outcome, problem = x.fetch(self.r, self.d, cache, self.client)
        self.assertEqual(outcome, 'reused_accepted')
        self.assertEqual(problem, 'fixture outage')

    def test_outage_without_cache_fails(self):
        self.client.unavailable = True
        with self.assertRaises(x.Unavailable):
            x.fetch(self.r, self.d, self.root / 'cache', self.client)

    def test_corrupt_cache_fails(self):
        cache = self.root / 'cache'; cache.mkdir()
        (cache / (self.r['package_sha256'] + '.zip')).write_bytes(b'corrupt')
        self.client.unavailable = True
        with self.assertRaises(x.Invalid):
            x.fetch(self.r, self.d, cache, self.client)

    def test_mutable_release_and_replaced_repository_never_fall_back(self):
        cache = self.root / 'cache'
        x.fetch(self.r, self.d, cache, self.client)
        self.client.immutable = False
        with self.assertRaises(x.Invalid):
            x.fetch(self.r, self.d, cache, self.client)
        self.client.immutable = True
        self.client.repo_id = 9
        with self.assertRaises(x.Invalid):
            x.fetch(self.r, self.d, cache, self.client)

    def test_cross_receipt_delivery_rejected(self):
        self.d['receipt_sha256'] = 'd' * 64
        with self.assertRaises(x.Invalid):
            x.validate_delivery(self.d, self.r, self.receipt_hash)

    def test_cli_reports_verified_local_and_no_freshness_claim(self):
        result = subprocess.run([sys.executable, str(Path(x.__file__)), 'verify',
                                 '--receipt', str(self.receipt), '--receipt-sha256', self.receipt_hash,
                                 '--manifest', str(self.manifest), '--archive', str(self.zip)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['outcome'], 'verified_local')
        self.assertEqual(report['source_freshness'], 'not_checked')
        self.assertEqual(report['receipt_sha256'], self.receipt_hash)


    def fake_gh(self, body):
        bindir = self.root / 'bin'
        bindir.mkdir(exist_ok=True)
        script = bindir / 'gh'
        script.write_text('#!' + sys.executable + '\n' + body)
        script.chmod(0o755)
        return {'PATH': str(bindir) + os.pathsep + os.environ['PATH']}

    def test_actual_fetch_cli_preserves_receipt_and_materializes(self):
        repository = {'id': 1}
        release = self.client.metadata('repos/owner/project/releases/2')
        body = ('import sys,json,base64\np=sys.argv[-1]\n'
                + 'if p.endswith("/assets/3"): sys.stdout.buffer.write(base64.b64decode('
                + repr(base64.b64encode(self.archive).decode()) + '))\n'
                + 'elif p.endswith("/releases/2"): print(' + repr(json.dumps(release)) + ')\n'
                + 'else: print(' + repr(json.dumps(repository)) + ')\n')
        delivery = self.root / 'delivery.json'; delivery.write_text(json.dumps(self.d))
        cache = self.root / 'cache'; output = self.root / 'output'
        with patch.dict(os.environ, self.fake_gh(body)):
            result = subprocess.run([sys.executable, str(Path(x.__file__)), 'fetch',
                '--receipt', str(self.receipt), '--receipt-sha256', self.receipt_hash,
                '--manifest', str(self.manifest), '--delivery', str(delivery),
                '--cache', str(cache), '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['outcome'], 'downloaded_accepted')
        self.assertEqual((cache / (self.receipt_hash + '.json')).read_bytes(), self.receipt.read_bytes())
        self.assertEqual((output / 'references/rubric.pdf').read_bytes(), self.body)

    def test_transport_size_timeout_and_nonzero_exit(self):
        target = self.root / 'download'
        for body, error, limit in [
            ('print("too much output")\n', x.Invalid, 1),
            ('import sys; sys.exit(1)\n', x.Unavailable, 100),
            ('import time; time.sleep(5)\n', x.Unavailable, 100),
        ]:
            with self.subTest(body=body), patch.dict(os.environ, self.fake_gh(body)):
                with self.assertRaises(error):
                    x.GitHub(timeout=0.2).download('fixture', target, limit)

    def test_manifest_mismatch_is_cli_failure(self):
        self.manifest.write_bytes(b'changed')
        result = subprocess.run([sys.executable, str(Path(x.__file__)), 'verify',
            '--receipt', str(self.receipt), '--receipt-sha256', self.receipt_hash,
            '--manifest', str(self.manifest), '--archive', str(self.zip)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('source manifest digest mismatch', result.stdout)


if __name__ == '__main__':
    unittest.main()
