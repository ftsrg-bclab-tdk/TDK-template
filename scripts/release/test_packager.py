import json
import os
from pathlib import Path
import subprocess
import sys
from jsonschema import ValidationError
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import packager
from packager import prepare, digest, encode, zip_bytes, validate


class PackagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.write('code/main.py', b'print("committed")\n')
        self.write('code/Dockerfile', b'FROM python:latest\n')
        self.write('code/README.md', b'Reproduce with Python or the Dockerfile.\n')
        self.write('code/LICENSE', b'MIT fixture\n')
        self.write('scratch/private.md', b'must not be packaged\n')
        self.write('meta.json', b'{"title":"Fixture only"}\n')
        self.manifest = {'schema_version': 1, 'packages': {'research': {
            'filename': 'research.zip', 'license_expression': 'MIT', 'build_profile': None,
            'files': [{'origin': 'tracked', 'path': 'code/' + name, 'archive_path': name}
                      for name in ['main.py', 'Dockerfile', 'README.md', 'LICENSE']]}},
            'records': {'research': {'packages': ['research'], 'metadata_file': 'meta.json', 'access': 'public'}}}
        self.runtime = self.root / 'runtime.json'
        self.runtime.write_bytes(encode({'schema': 'runtime-evidence/v1', 'tools': {'python': 'fixture-version'},
                                        'images': [{'digest': 'sha256:' + 'a' * 64, 'platform': 'linux/amd64'}]}))
        self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE).decode().strip()

    def write(self, path, data):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def commit(self):
        self.write('release.json', encode(self.manifest))
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.sha = self.git('rev-parse', 'HEAD')

    def run_pack(self, name='out', **kwargs):
        return prepare(self.repo, self.sha, 'release.json', self.runtime, self.root / name, **kwargs)

    def test_exact_committed_inventory_and_deterministic_bytes(self):
        self.write('code/main.py', b'dirty\n')
        self.write('code/untracked.txt', b'untracked\n')
        first = self.run_pack()
        second = self.run_pack('again')
        self.assertEqual(first, second)
        self.assertEqual((self.root/'out/research.zip').read_bytes(), (self.root/'again/research.zip').read_bytes())
        with zipfile.ZipFile(self.root/'out/research.zip') as z:
            self.assertEqual(set(z.namelist()), {'main.py', 'Dockerfile', 'README.md', 'LICENSE', 'PROVENANCE.json'})
            self.assertEqual(z.read('main.py'), b'print("committed")\n')
            provenance = json.loads(z.read('PROVENANCE.json'))
            self.assertEqual(provenance['source_sha'], self.sha)
        self.assertEqual((self.root/'out/metadata/research.json').read_bytes(), (self.repo/'meta.json').read_bytes())

    def test_historical_sha_remains_selected_after_new_commit(self):
        old_sha = self.sha
        self.write('code/main.py', b'newer\n')
        self.commit()
        self.sha = old_sha
        self.run_pack()
        with zipfile.ZipFile(self.root/'out/research.zip') as z:
            self.assertEqual(z.read('main.py'), b'print("committed")\n')

    def test_preserve_tracked_executable_mode(self):
        self.git('update-index', '--chmod=+x', 'code/main.py')
        self.git('commit', '-qm', 'executable')
        self.sha = self.git('rev-parse', 'HEAD')
        self.run_pack()
        with zipfile.ZipFile(self.root/'out/research.zip') as z:
            self.assertEqual((z.getinfo('main.py').external_attr >> 16) & 0o777, 0o755)

    def test_no_overwrite_existing_output(self):
        self.run_pack()
        before = (self.root/'out/receipt.json').read_bytes()
        with self.assertRaises(ValueError):
            self.run_pack()
        self.assertEqual(before, (self.root/'out/receipt.json').read_bytes())

    def test_package_bound_includes_provenance_and_zip_overhead(self):
        # Every source input fits, but the complete ZIP must also fit the cap.
        cap = 1024
        self.assertLess((self.repo/'release.json').stat().st_size, cap)
        with patch.object(packager, 'MAX_BYTES', cap):
            with self.assertRaisesRegex(ValueError, 'provenance and ZIP overhead'):
                self.run_pack()
        self.assertFalse((self.root/'out').exists())

    def test_symlink_and_lfs_rejected(self):
        (self.repo/'code/main.py').unlink()
        os.symlink('../scratch/private.md', self.repo/'code/main.py')
        self.commit()
        with self.assertRaises(ValueError):
            self.run_pack()
        (self.repo/'code/main.py').unlink()
        self.write('code/main.py', b'version https://git-lfs.github.com/spec/v1\noid sha256:abc\n')
        self.commit()
        with self.assertRaises(ValueError):
            self.run_pack()
        self.assertFalse((self.root/'out').exists())

    def test_untracked_selected_file_is_not_accepted(self):
        self.manifest['packages']['research']['files'][0]['path'] = 'code/missing.py'
        self.commit()
        self.write('code/missing.py', b'not committed')
        with self.assertRaises(ValueError):
            self.run_pack()

    def test_duplicate_json_key_rejected(self):
        self.write('release.json', b'{"schema_version":1,"schema_version":1}')
        self.git('add', '.')
        self.git('commit', '-qm', 'bad json')
        self.sha = self.git('rev-parse', 'HEAD')
        with self.assertRaises(ValueError):
            self.run_pack()

    def test_archive_parent_file_collision_rejected(self):
        self.manifest['packages']['research']['files'][0]['archive_path'] = 'README.md/child'
        with self.assertRaises(ValueError):
            validate(self.manifest)

    def built_fixture(self):
        built = self.root/'built'
        built.mkdir()
        (built/'result.txt').write_bytes(b'generated result')
        self.manifest['packages']['research']['build_profile'] = 'benchmark-small'
        self.manifest['packages']['research']['files'].append({'origin': 'built', 'path': 'result.txt', 'archive_path': 'result.txt'})
        self.commit()
        receipt = {'schema': 'build-outputs/v1', 'source_sha': self.sha, 'runtime_sha256': digest(self.runtime.read_bytes()),
                   'outputs': {'result.txt': {'sha256': digest(b'generated result'), 'size': 16, 'profile': 'benchmark-small'}}}
        path = self.root/'build.json'
        path.write_bytes(encode(receipt))
        return built, path, receipt

    def test_built_bytes_and_runtime_bound(self):
        built, path, receipt = self.built_fixture()
        self.run_pack(built_dir=built, build_receipt_path=path)
        receipt['runtime_sha256'] = '0'*64
        path.write_bytes(encode(receipt))
        with self.assertRaises(ValueError):
            self.run_pack('bad', built_dir=built, build_receipt_path=path)

    def test_built_byte_tamper_rejected(self):
        built, path, _ = self.built_fixture()
        (built/'result.txt').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.run_pack(built_dir=built, build_receipt_path=path)

    def test_built_symlink_rejected(self):
        built, path, _ = self.built_fixture()
        (built/'result.txt').unlink()
        os.symlink(self.repo/'scratch/private.md', built/'result.txt')
        with self.assertRaises(ValueError):
            self.run_pack(built_dir=built, build_receipt_path=path)

    def reference_fixture(self, access='public', redistribute=True, member='reference.pdf'):
        reference_dir = self.root/'refs'
        reference_dir.mkdir(exist_ok=True)
        self.write('reference-manifest.json', b'{"source":"fixture","applicability":"2026"}\n')
        data = b'%PDF-fixture only'
        archive = zip_bytes({member: (data, 0o644)})
        receipt = {'schema':'external-inputs/v1', 'manifest_sha256': digest((self.repo/'reference-manifest.json').read_bytes()),
                   'package_sha256': digest(archive), 'files':[{'path':member,'sha256':digest(data),'size':len(data)}],
                   'provenance':{'publisher':'Fixture','source':'https://example.invalid/reference','retrieved_at':'2026-11-03','applicability':'2026'},
                   'acceptance':{'status':'accepted','evidence':'fixture acceptance'},'license':'fixture permission','redistribution':redistribute,'access':access}
        raw = encode(receipt)
        binding = {'receipt_sha256':digest(raw), 'package_sha256':digest(archive), 'source_manifest':'reference-manifest.json'}
        (reference_dir/(digest(raw)+'.json')).write_bytes(raw)
        (reference_dir/(digest(archive)+'.zip')).write_bytes(archive)
        self.manifest['references']={'faculty':binding}
        self.manifest['packages']['research']['files'].append({'origin':'verified_reference','reference':'faculty','path':member,'archive_path':'reference.pdf'})
        self.commit()
        return reference_dir, binding, receipt

    def test_reference_exact_bytes_and_acceptance_receipt_preserved(self):
        refs, binding, _ = self.reference_fixture()
        self.run_pack(reference_dir=refs)
        raw=(self.root/'out/references/faculty.json').read_bytes()
        self.assertEqual(digest(raw), binding['receipt_sha256'])
        with zipfile.ZipFile(self.root/'out/research.zip') as z:
            self.assertEqual(z.read('reference.pdf'), b'%PDF-fixture only')

    def test_reference_missing_and_corrupt_fail(self):
        refs, binding, _ = self.reference_fixture()
        package=refs/(binding['package_sha256']+'.zip')
        package.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            self.run_pack(reference_dir=refs)
        package.unlink()
        with self.assertRaises(ValueError):
            self.run_pack(reference_dir=refs)
        self.assertFalse((self.root/'out').exists())

    def test_receipt_tamper_fails(self):
        refs, binding, _ = self.reference_fixture()
        (refs/(binding['receipt_sha256']+'.json')).write_bytes(b'{}')
        with self.assertRaises(ValueError):
            self.run_pack(reference_dir=refs)

    def test_reference_source_manifest_mismatch_fails(self):
        refs, _, _ = self.reference_fixture()
        self.write('reference-manifest.json', b'new applicability')
        self.commit()
        with self.assertRaises(ValueError):
            self.run_pack(reference_dir=refs)

    def test_restricted_reference_not_public(self):
        refs, _, _ = self.reference_fixture(access='restricted')
        with self.assertRaises(ValueError):
            self.run_pack(reference_dir=refs)

    def test_reference_redistribution_must_be_explicit(self):
        refs, _, _ = self.reference_fixture(redistribute=False)
        with self.assertRaises(ValueError):
            self.run_pack(reference_dir=refs)

    def test_reference_archive_traversal_rejected(self):
        refs, _, _ = self.reference_fixture(member='../escape.pdf')
        with self.assertRaises((ValueError, ValidationError)):
            self.run_pack(reference_dir=refs)
        self.assertFalse((self.root/'escape.pdf').exists())

    def test_reference_member_hash_mismatch_even_when_archive_hash_matches(self):
        refs, binding, receipt = self.reference_fixture()
        receipt['files'][0]['sha256'] = '0' * 64
        raw = encode(receipt)
        binding['receipt_sha256'] = digest(raw)
        (refs / (digest(raw) + '.json')).write_bytes(raw)
        self.commit()
        with self.assertRaises(ValueError):
            self.run_pack(reference_dir=refs)

    def test_cli_reports_exact_receipt_digest(self):
        command = [sys.executable, str(Path(__file__).with_name('packager.py')),
                   '--repo', str(self.repo), '--source', self.sha, '--manifest', 'release.json',
                   '--runtime', str(self.runtime), '--out', str(self.root / 'cli')]
        result = json.loads(subprocess.check_output(command))
        self.assertEqual(result['source_sha'], self.sha)
        self.assertEqual(result['receipt_sha256'], digest((self.root / 'cli/receipt.json').read_bytes()))

    def test_review_schema_matches_executable_schema(self):
        here = Path(__file__).resolve().parent
        self.assertEqual((here / 'manifest.schema.json').read_bytes(),
                         (here.parents[1] / 'docs/selective-release/manifest.schema.json').read_bytes())

    def test_mutable_image_tag_is_not_image_identity(self):
        self.runtime.write_bytes(encode({'schema':'runtime-evidence/v1','tools':{'python':'latest-resolved'},
                                        'images':[{'digest':'image:latest','platform':'linux/amd64'}]}))
        with self.assertRaises(ValueError):
            self.run_pack()


if __name__ == '__main__':
    unittest.main()
