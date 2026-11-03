import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import badges


class BadgeTests(unittest.TestCase):
    def metadata(self, private=True):
        return {'id': 72, 'full_name': 'students/project', 'default_branch': 'work/main', 'private': private}

    def test_new_project_targets_and_events(self):
        result = badges.render(self.metadata())
        self.assertEqual(result.count('/badge.svg?'), 3)
        self.assertIn('branch=work%2Fmain&event=push', result)
        self.assertEqual(result.count('branch=work%2Fmain&event=workflow_run'), 2)
        self.assertIn('Private results require', result)
        self.assertNotIn('FTSRG', result)
        self.assertNotIn('Private results require', badges.render(self.metadata(False)))

    def test_preserves_prose_frontmatter_and_is_idempotent(self):
        before = '---\r\nstudent: unchanged\r\n---\r\n# Title\r\n\r\n'
        after = '\r\n\r\nStudent prose: do not rewrite.\r\n'
        block = badges.render(self.metadata())
        original = before + badges.START + '\nold\n' + badges.END + after
        output = badges.replace_block(original, block)
        self.assertEqual(output, before + block + after)
        self.assertEqual(badges.replace_block(output, block), output)

    def test_rejects_malformed_markers(self):
        for text in ('none', badges.END + badges.START,
                     badges.START * 2 + badges.END):
            with self.assertRaises(ValueError):
                badges.replace_block(text, 'replacement')

    def test_checks_workflow_existence_and_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                badges.validate_workflows(root)
            directory = root / '.github/workflows'
            directory.mkdir(parents=True)
            for filename, label, _ in badges.WORKFLOWS:
                (directory / filename).write_text(f'name: {label}\non: push\n')
            badges.validate_workflows(root)
            (directory / 'paper-lint.yml').write_text('name: Wrong result\n')
            with self.assertRaises(ValueError):
                badges.validate_workflows(root)

    def receipt(self, root, **updates):
        data = {'schema': 'publication-receipt/v1', 'environment': 'production',
                'operation_id': 'synthetic-test', 'source_sha': 'a' * 40,
                'bundle_receipt_sha256': 'b' * 64,
                'repository_id': 72, 'status': 'partial', 'records': {
                    'research': {'status': 'published', 'deposition_id': 123, 'packages': [],
                                 'version_doi': '10.5281/zenodo.123', 'concept_doi': '10.5281/zenodo.122',
                                 'record_url': 'https://zenodo.org/records/123',
                                 'verified_at': '2026-11-04T00:00:00Z'},
                    'paper': {'status': 'draft', 'deposition_id': 456, 'packages': [],
                              'reserved_doi': '10.5281/zenodo.456'}}}
        data.update(updates)
        path = root / 'publication.json'
        path.write_text(json.dumps(data))
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_only_production_published_individual_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, digest = self.receipt(Path(tmp))
            result = badges.published_badges(path, digest, 72)
            self.assertEqual(len(result), 1)
            self.assertIn('research DOI', result[0])
            self.assertNotIn('456', result[0])
            path, digest = self.receipt(Path(tmp), environment='sandbox')
            self.assertEqual(badges.published_badges(path, digest, 72), [])

    def test_rejects_tampering_wrong_repository_and_reserved_doi(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, digest = self.receipt(Path(tmp))
            for supplied_digest, repo in [('0' * 64, 72), (digest, 73), ('', 72)]:
                with self.assertRaises(ValueError):
                    badges.published_badges(path, supplied_digest, repo)
            path, digest = self.receipt(Path(tmp), records={
                'research': {'status': 'published', 'reserved_doi': '10.5281/zenodo.123'}})
            with self.assertRaises(ValueError):
                badges.published_badges(path, digest, 72)

    def test_all_targets_validated_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / 'README.md'
            good.write_text(badges.START + '\nold\n' + badges.END)
            bad = root / 'bad.md'
            bad.write_text('student content')
            original = good.read_bytes()
            with patch('sys.argv', ['badges.py', '--repo', 'students/project', '--root', tmp,
                                    '--readme', 'README.md', '--readme', 'bad.md', '--write']), \
                    patch.object(badges, 'repository', return_value=self.metadata()), \
                    patch.object(badges, 'validate_workflows'):
                self.assertEqual(badges.main(), 1)
            self.assertEqual(good.read_bytes(), original)

    def test_cli_reads_github_metadata_and_reruns_without_prose_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / '.github/workflows'
            directory.mkdir(parents=True)
            for filename, label, _ in badges.WORKFLOWS:
                (directory / filename).write_text(f'name: {label}\non: push\n')
            fakebin = root / 'bin'
            fakebin.mkdir()
            gh = fakebin / 'gh'
            gh.write_text(f'#!{sys.executable}\nimport sys\n'
                          'assert sys.argv[1:] == ["api", "repos/students/project"]\n'
                          f'print({json.dumps(self.metadata())!r})\n')
            gh.chmod(0o755)
            readme = root / 'README.md'
            readme.write_text('# Student\n' + badges.START + '\nold\n' + badges.END + '\nKeep my text.\n')
            command = [sys.executable, str(Path(badges.__file__).resolve()), '--repo', 'students/project',
                       '--root', tmp, '--readme', 'README.md', '--write']
            env = dict(os.environ, PATH=str(fakebin) + os.pathsep + os.environ['PATH'])
            subprocess.run(command, check=True, env=env, capture_output=True)
            first = readme.read_bytes()
            subprocess.run(command, check=True, env=env, capture_output=True)
            self.assertEqual(first, readme.read_bytes())
            self.assertIn(b'branch=work%2Fmain', first)
            self.assertTrue(first.endswith(b'\nKeep my text.\n'))


if __name__ == '__main__':
    unittest.main()
