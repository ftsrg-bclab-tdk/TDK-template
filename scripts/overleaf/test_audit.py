import subprocess
import tempfile
from pathlib import Path
import unittest

from overleaf.audit import audit


class AuditTests(unittest.TestCase):
    def test_blob_mode_and_unsupported_object_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.run(['git', '-C', tmp, *args], check=True, capture_output=True).stdout.decode().strip()
            git('init', '-q')
            (root/'run.sh').write_text('#!/bin/sh\ntrue\n')
            (root/'run.sh').chmod(0o755)
            git('add', 'run.sh')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'Before')
            before = git('rev-parse', 'HEAD')
            (root/'run.sh').chmod(0o644)
            (root/'link').symlink_to('run.sh')
            (root/'data').write_text('version https://git-lfs.github.com/spec/v1\noid sha256:fixture\n')
            git('add', 'run.sh', 'link', 'data')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'After')
            result = audit(root, before, 'HEAD')
            mode = next(change for change in result['changes'] if change['path'] == 'run.sh')
            self.assertEqual(mode['before']['oid'], mode['after']['oid'])
            self.assertEqual(mode['before']['mode'], '100755')
            self.assertEqual(mode['after']['mode'], '100644')
            self.assertEqual(result['inventory']['symlinks'], ['link'])
            self.assertEqual(result['inventory']['lfs_pointers'], ['data'])
            self.assertEqual(result['unexpected_changes'], ['data', 'link', 'run.sh'])
